"""
Shared Meta Graph API client (single client for every WhatsApp Lambda).

Handles: per-WABA token + app_secret (Secrets Manager, cached), appsecret_proof,
retry with exponential backoff on transient errors only (network / 5xx / is_transient),
cursor pagination, multipart upload, normalized error envelope, masked logging.

Usage:
    from lambda_utils.meta_client import MetaGraphClient
    meta = MetaGraphClient()
    res = meta.post(f"{phone_id}/messages", payload={...}, token_context={'phone_id': phone_id})
    if meta.is_error(res): err = res['error']
    for tpl in meta.paginate(f"{waba_id}/message_templates", token_context={'waba_id': waba_id}):
        ...
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import uuid
from typing import Dict, Any, Optional, Iterator

import boto3

from lambda_utils.logging import get_logger
from lambda_utils import graph_errors
from lambda_utils.appsecret import build_appsecret_proof
from lambda_utils.masking import mask_text

logger = get_logger(__name__)

DEFAULT_SECRET = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
DEFAULT_API_VERSION = os.environ.get('META_API_VERSION', 'v25.0')
GRAPH_BASE = 'https://graph.facebook.com'
_WABA2_ENV = os.environ.get('WABA2_IDS', '2513394156072604,1055232054343117')
DEFAULT_WABA2_IDS = {x.strip() for x in _WABA2_ENV.split(',') if x.strip()}

_MAX_RETRIES = int(os.environ.get('META_MAX_RETRIES', '3'))
_TIMEOUT = int(os.environ.get('META_TIMEOUT', '15'))


def _ctx(token_context: Optional[Dict], waba_id: Optional[str], phone_id: Optional[str]):
    """Resolve (waba_id, phone_id) from either explicit args or a token_context dict."""
    if token_context:
        return token_context.get('waba_id') or waba_id, token_context.get('phone_id') or phone_id
    return waba_id, phone_id


class MetaGraphClient:
    """Reusable Meta Graph API client with token caching, retries and pagination."""

    _cache: Dict[str, Any] = {}  # warm-Lambda credential cache

    def __init__(self, secret_id: str = DEFAULT_SECRET, api_version: str = DEFAULT_API_VERSION,
                 waba2_ids: Optional[set] = None, region: Optional[str] = None):
        self.secret_id = secret_id
        self.api_version = api_version
        self.graph_base = f'{GRAPH_BASE}/{api_version}'
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

    # ── static helpers ──
    @staticmethod
    def is_error(result: Any) -> bool:
        return graph_errors.is_error(result)

    @staticmethod
    def normalize_error(body: Any, http_status: Optional[int] = None) -> Dict:
        return graph_errors.normalize(body, http_status)

    @staticmethod
    def build_appsecret_proof(access_token: str, app_secret: str) -> str:
        return build_appsecret_proof(access_token, app_secret)

    def build_endpoint(self, object_id: str, edge: Optional[str] = None, version: Optional[str] = None) -> str:
        base = f"{GRAPH_BASE}/{version or self.api_version}/{object_id}"
        return f"{base}/{edge}" if edge else base

    # ── core request ──
    def graph_api(self, endpoint: str, method: str = 'GET', payload: Optional[Dict] = None,
                  params: Optional[Dict] = None, token_context: Optional[Dict] = None,
                  waba_id: Optional[str] = None, phone_id: Optional[str] = None,
                  headers: Optional[Dict] = None) -> Dict:
        waba_id, phone_id = _ctx(token_context, waba_id, phone_id)
        token, app_secret = self._creds(waba_id, phone_id)
        if not token:
            return {'error': {'message': 'No Meta access token available', 'type': 'ConfigError',
                              'code': None, 'retryable': False, 'is_transient': False}}

        qs = {k: v for k, v in (params or {}).items() if v is not None}
        proof = build_appsecret_proof(token, app_secret)
        if proof:
            qs['appsecret_proof'] = proof
        url = f'{self.graph_base}/{endpoint}'
        if qs:
            url += '?' + urllib.parse.urlencode(qs)

        req_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        if headers:
            req_headers.update(headers)
        data = json.dumps(payload).encode('utf-8') if payload is not None else None

        last_err: Dict = {'error': {'message': 'request not attempted', 'code': None}}
        for attempt in range(1, _MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read().decode('utf-8')
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8') if e.fp else str(e)
                last_err = graph_errors.normalize(body, e.code)
                retryable = graph_errors.is_retryable(e.code, body)
                logger.warning(mask_text(json.dumps({
                    'event': 'meta_graph_http_error', 'endpoint': endpoint, 'status': e.code,
                    'attempt': attempt, 'retryable': bool(retryable),
                    'fbtrace_id': last_err['error'].get('fbtrace_id'),
                })))
                if not retryable or attempt == _MAX_RETRIES:
                    return last_err
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                last_err = {'error': {'message': str(e), 'type': 'NetworkError', 'code': None,
                                      'is_transient': True, 'retryable': True}}
                logger.warning(json.dumps({'event': 'meta_graph_network_error', 'endpoint': endpoint,
                                           'attempt': attempt, 'error': str(e)[:160]}))
                if attempt == _MAX_RETRIES:
                    return last_err
            time.sleep(0.5 * (2 ** (attempt - 1)))
        return last_err

    # ── verb shortcuts ──
    def get(self, endpoint: str, params: Optional[Dict] = None, token_context: Optional[Dict] = None,
            waba_id: Optional[str] = None, phone_id: Optional[str] = None) -> Dict:
        return self.graph_api(endpoint, 'GET', params=params, token_context=token_context, waba_id=waba_id, phone_id=phone_id)

    def post(self, endpoint: str, payload: Optional[Dict] = None, params: Optional[Dict] = None,
             token_context: Optional[Dict] = None, waba_id: Optional[str] = None, phone_id: Optional[str] = None) -> Dict:
        return self.graph_api(endpoint, 'POST', payload=payload, params=params, token_context=token_context, waba_id=waba_id, phone_id=phone_id)

    def delete(self, endpoint: str, payload: Optional[Dict] = None, params: Optional[Dict] = None,
               token_context: Optional[Dict] = None, waba_id: Optional[str] = None, phone_id: Optional[str] = None) -> Dict:
        return self.graph_api(endpoint, 'DELETE', payload=payload, params=params, token_context=token_context, waba_id=waba_id, phone_id=phone_id)

    # ── multipart upload (media / flow assets) ──
    def upload_multipart(self, endpoint: str, files: Dict[str, bytes], data: Optional[Dict] = None,
                         token_context: Optional[Dict] = None, waba_id: Optional[str] = None,
                         phone_id: Optional[str] = None) -> Dict:
        waba_id, phone_id = _ctx(token_context, waba_id, phone_id)
        token, app_secret = self._creds(waba_id, phone_id)
        if not token:
            return {'error': {'message': 'No Meta access token available', 'type': 'ConfigError', 'code': None}}
        boundary = f'----meta{uuid.uuid4().hex}'
        body = bytearray()
        for k, v in (data or {}).items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for field, content in files.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{field}"\r\n'.encode()
            body += b'Content-Type: application/octet-stream\r\n\r\n' + content + b'\r\n'
        body += f'--{boundary}--\r\n'.encode()

        url = f'{self.graph_base}/{endpoint}'
        proof = build_appsecret_proof(token, app_secret)
        if proof:
            url += '?' + urllib.parse.urlencode({'appsecret_proof': proof})
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': f'multipart/form-data; boundary={boundary}'}
        req = urllib.request.Request(url, data=bytes(body), headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=max(_TIMEOUT, 60)) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            return graph_errors.normalize(e.read().decode('utf-8') if e.fp else str(e), e.code)
        except Exception as e:  # noqa: BLE001
            return {'error': {'message': str(e), 'type': 'NetworkError', 'code': None}}

    # ── pagination ──
    def paginate(self, endpoint: str, params: Optional[Dict] = None, token_context: Optional[Dict] = None,
                 waba_id: Optional[str] = None, phone_id: Optional[str] = None, limit_pages: int = 50) -> Iterator[Dict]:
        page_params = dict(params or {})
        for _ in range(limit_pages):
            result = self.get(endpoint, params=page_params, token_context=token_context, waba_id=waba_id, phone_id=phone_id)
            if self.is_error(result):
                return
            for item in result.get('data', []) or []:
                yield item
            after = ((result.get('paging') or {}).get('cursors') or {}).get('after')
            if not after or not result.get('data'):
                return
            page_params['after'] = after


# Backward-compatible aliases (earlier code/tests used MetaClient.graph)
MetaClient = MetaGraphClient
MetaGraphClient.graph = MetaGraphClient.graph_api  # type: ignore[attr-defined]
