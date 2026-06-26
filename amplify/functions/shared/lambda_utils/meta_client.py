"""
Shared Meta Graph API client.

Single place for: per-WABA token + app_secret loading (Secrets Manager, cached),
appsecret_proof, retry with exponential backoff on transient errors, cursor pagination,
normalized error shape, and masked logging. Replaces the per-Lambda `_graph_api` copies.

Usage:
    from lambda_utils.meta_client import MetaClient
    meta = MetaClient()                       # uses env defaults
    res = meta.graph("<phone_id>/messages", method="POST", payload={...}, phone_id="<phone_id>")
    if MetaClient.is_error(res):
        err = res["error"]                    # {message,type,code,error_subcode,fbtrace_id}
    for item in meta.paginate("<waba_id>/message_templates", waba_id="<waba_id>"):
        ...
"""
import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, Iterator

import boto3

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
DEFAULT_API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
# Comma-separated WABA2 / phone-2 identifiers that should use the WABA2 token/app_secret.
_WABA2_ENV = os.environ.get('WABA2_IDS', '2513394156072604,1055232054343117')
DEFAULT_WABA2_IDS = {x.strip() for x in _WABA2_ENV.split(',') if x.strip()}

# Transient HTTP statuses worth retrying (network/5xx/throttle)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = int(os.environ.get('META_MAX_RETRIES', '3'))
_TIMEOUT = int(os.environ.get('META_TIMEOUT', '15'))


def _mask(token: str) -> str:
    if not token:
        return ''
    return token[:6] + '…' + token[-4:] if len(token) > 12 else '***'


class MetaClient:
    """Reusable Meta Graph API client with token caching, retries and pagination."""

    # class-level cache shared across instances within a warm Lambda
    _cache: Dict[str, Any] = {}

    def __init__(self, secret_id: str = DEFAULT_SECRET, api_version: str = DEFAULT_API_VERSION,
                 waba2_ids: Optional[set] = None, region: Optional[str] = None):
        self.secret_id = secret_id
        self.api_version = api_version
        self.graph_base = f'https://graph.facebook.com/{api_version}'
        self.waba2_ids = waba2_ids if waba2_ids is not None else set(DEFAULT_WABA2_IDS)
        self._secrets = boto3.client('secretsmanager', region_name=region or os.environ.get('AWS_REGION', 'us-east-1'))

    # ── credentials ──
    def _ensure_loaded(self) -> None:
        if self._cache.get('loaded'):
            return
        resp = self._secrets.get_secret_value(SecretId=self.secret_id)
        raw = resp.get('SecretString', '') or ''
        try:
            secret = json.loads(raw)
            t1 = (secret.get('access_token') or '').strip()
            t2 = (secret.get('access_token_waba2') or t1).strip()
            s1 = (secret.get('app_secret') or '').strip()
            s2 = (secret.get('app_secret_waba2') or s1).strip()
        except json.JSONDecodeError:
            t1 = t2 = raw.strip()
            s1 = s2 = ''
        self._cache.update({'token1': t1, 'token2': t2, 'app_secret': s1, 'app_secret_waba2': s2, 'loaded': True})

    def _use_waba2(self, waba_id: Optional[str], phone_id: Optional[str]) -> bool:
        return (waba_id in self.waba2_ids) or (phone_id in self.waba2_ids)

    def _creds(self, waba_id: Optional[str], phone_id: Optional[str]):
        self._ensure_loaded()
        if self._use_waba2(waba_id, phone_id):
            return self._cache['token2'], self._cache['app_secret_waba2']
        return self._cache['token1'], self._cache['app_secret']

    # ── error helpers ──
    @staticmethod
    def is_error(result: Dict) -> bool:
        return isinstance(result, dict) and 'error' in result

    @staticmethod
    def normalize_error(body: Any, http_code: Optional[int] = None) -> Dict:
        """Return a consistent error envelope: {message,type,code,error_subcode,fbtrace_id,is_transient}."""
        err: Dict[str, Any] = {}
        if isinstance(body, dict):
            err = body.get('error', body) if isinstance(body.get('error'), dict) else body
        elif isinstance(body, str):
            try:
                parsed = json.loads(body)
                err = parsed.get('error', parsed) if isinstance(parsed, dict) else {'message': body}
            except (json.JSONDecodeError, TypeError, ValueError):
                err = {'message': body}
        out = {
            'message': err.get('message', 'Unknown Meta API error'),
            'type': err.get('type', 'GraphAPIError'),
            'code': err.get('code', http_code),
            'error_subcode': err.get('error_subcode'),
            'fbtrace_id': err.get('fbtrace_id'),
            'is_transient': bool(err.get('is_transient', http_code in _RETRYABLE_STATUS if http_code else False)),
        }
        return {'error': out}

    # ── core request ──
    def graph(self, endpoint: str, method: str = 'GET', payload: Optional[Dict] = None,
              params: Optional[Dict] = None, waba_id: Optional[str] = None,
              phone_id: Optional[str] = None) -> Dict:
        token, app_secret = self._creds(waba_id, phone_id)
        if not token:
            return {'error': {'message': 'No Meta access token available', 'type': 'ConfigError', 'code': None}}

        qs = {k: v for k, v in (params or {}).items() if v is not None}
        if app_secret:
            qs['appsecret_proof'] = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        url = f'{self.graph_base}/{endpoint}'
        if qs:
            url += '?' + urllib.parse.urlencode(qs)

        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = json.dumps(payload).encode('utf-8') if payload is not None else None

        last_err: Dict = {'error': {'message': 'request not attempted', 'code': None}}
        for attempt in range(1, _MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read().decode('utf-8')
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8') if e.fp else str(e)
                last_err = self.normalize_error(body, e.code)
                transient = e.code in _RETRYABLE_STATUS or last_err['error'].get('is_transient')
                logger.warning(json.dumps({
                    'event': 'meta_graph_http_error', 'endpoint': endpoint, 'status': e.code,
                    'attempt': attempt, 'transient': bool(transient), 'token': _mask(token),
                    'fbtrace_id': last_err['error'].get('fbtrace_id'),
                }))
                if not transient or attempt == _MAX_RETRIES:
                    return last_err
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                last_err = {'error': {'message': str(e), 'type': 'NetworkError', 'code': None, 'is_transient': True}}
                logger.warning(json.dumps({'event': 'meta_graph_network_error', 'endpoint': endpoint,
                                           'attempt': attempt, 'error': str(e)}))
                if attempt == _MAX_RETRIES:
                    return last_err
            # exponential backoff: 0.5, 1, 2 …
            time.sleep(0.5 * (2 ** (attempt - 1)))
        return last_err

    # ── pagination ──
    def paginate(self, endpoint: str, params: Optional[Dict] = None, waba_id: Optional[str] = None,
                 phone_id: Optional[str] = None, max_pages: int = 50) -> Iterator[Dict]:
        """Yield each item across cursor-paged Graph results (follows paging.cursors.after)."""
        page_params = dict(params or {})
        for _ in range(max_pages):
            result = self.graph(endpoint, params=page_params, waba_id=waba_id, phone_id=phone_id)
            if self.is_error(result):
                logger.warning(json.dumps({'event': 'meta_paginate_error', 'endpoint': endpoint,
                                           'error': result['error']}))
                return
            for item in result.get('data', []):
                yield item
            after = (result.get('paging', {}).get('cursors', {}) or {}).get('after')
            if not after or not result.get('data'):
                return
            page_params['after'] = after
