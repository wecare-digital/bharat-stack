"""
Meta Business Agent — WECARE.DIGITAL

Backend for onboarding/configuring Meta's Business AI Agent on WhatsApp.
Docs (scraped to s3://app.wecare.digital/stream/docs/meta-business-agent/):
  Onboarding: POST https://api.facebook.com/{entity_id}/agent_onboarding/?channel=whatsapp
    headers: Authorization: Bearer <token>, X-API-Version: 2.0.0
    entity_id = WhatsApp Business Phone Number ID (or FB Page ID)
    body: {} -> 201 (creates entities + schedules async data-prep jobs)

Auth token comes from Secrets Manager (wecare/meta-system-user-token), same as
the other WhatsApp handlers — never from env.

Actions (event.action or API route):
  - onboard        : trigger onboarding for an entity+channel
  - status         : (placeholder) read onboarding status
NOTE: configure/operate endpoints (skills, knowledge, connectors, eval, test)
will be added from the per-endpoint OpenAPI specs — see README.
"""

import os
import json
import logging
import urllib.request
import urllib.error

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
secrets_client = boto3.client("secretsmanager", region_name=REGION)
META_TOKEN_SECRET = os.environ.get("META_TOKEN_SECRET", "wecare/meta-system-user-token")
API_VERSION = os.environ.get("META_AGENT_API_VERSION", "2.0.0")
GRAPH_HOST = os.environ.get("META_AGENT_HOST", "https://api.facebook.com")

# Default WhatsApp Business phone-number IDs (entity_id candidates)
DEFAULT_ENTITIES = {
    "WABA1": "1016149501586345",   # +91 93309 94400
    "WABA-T": "1055232054343117",  # +91 99033 00044
}

_token_cache = {}
CORS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def _token() -> str:
    if "t" in _token_cache:
        return _token_cache["t"]
    resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
    data = json.loads(resp["SecretString"])
    _token_cache["t"] = (data.get("access_token") or "").strip()
    return _token_cache["t"]


def _resp(status, body):
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body)}


def _meta_request(method: str, url: str, payload: dict | None):
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body if method != "GET" else None, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Version", API_VERSION)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8")
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)
        except Exception:
            pass
        return e.code, {"error": detail}
    except Exception as e:
        return 502, {"error": str(e)}


CHANNELS = {"email", "instagram", "line", "messenger", "sms", "tiktok", "unknown", "webchat", "whatsapp"}


def _onboard(body: dict):
    """POST /{entity_id}/agent_onboarding/?channel=<channel>"""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    channel = (body.get("channel") or "whatsapp").lower()
    if not entity_id:
        return _resp(400, {"error": "entityId (WhatsApp Business Phone Number ID) required"})
    if channel not in CHANNELS:
        return _resp(400, {"error": f"channel must be one of {sorted(CHANNELS)}"})
    url = f"{GRAPH_HOST}/{entity_id}/agent_onboarding/?channel={channel}"
    status, data = _meta_request("POST", url, {})
    logger.info(json.dumps({"event": "agent_onboard", "entity": entity_id, "channel": channel, "status": status}))
    return _resp(status if status in (200, 201) else 502, {"onboarding": data, "entityId": entity_id, "channel": channel})


def _settings_url(entity_id: str, agent_id: str | None) -> str:
    url = f"{GRAPH_HOST}/{entity_id}/agent_config/settings"
    return f"{url}?agent_id={agent_id}" if agent_id else url


def _settings_get(body: dict):
    """GET /{entity_id}/agent_config/settings  -> array of settings."""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    status, data = _meta_request("GET", _settings_url(entity_id, body.get("agentId")), None)
    return _resp(status if status == 200 else 502, {"settings": data, "entityId": entity_id})


def _settings_update(body: dict):
    """PUT /{entity_id}/agent_config/settings — full replace, so we GET current
    settings and merge the requested changes to avoid clobbering other fields.
    Accepted inputs: enabled(bool), handoff{enabled,message}, followup{enabled,
    followup_interval_in_seconds,message}, aiAudience(ALLOWLISTED_ONLY|EVERYONE)."""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    agent_id = body.get("agentId")

    # merge base = current settings (if any)
    _, cur = _meta_request("GET", _settings_url(entity_id, agent_id), None)
    current = cur[0] if isinstance(cur, list) and cur else (cur if isinstance(cur, dict) else {})
    payload = {
        "rollout": current.get("rollout") or {"enabled": False},
        "handoff": current.get("handoff"),
        "followup": current.get("followup"),
        "ai_audience": current.get("ai_audience"),
    }
    if "enabled" in body:
        payload["rollout"] = {"enabled": bool(body["enabled"])}
    if "handoff" in body:
        payload["handoff"] = body["handoff"]
    if "followup" in body:
        payload["followup"] = body["followup"]
    if "aiAudience" in body:
        payload["ai_audience"] = body["aiAudience"]
    payload = {k: v for k, v in payload.items() if v is not None}

    status, data = _meta_request("PUT", _settings_url(entity_id, agent_id), payload)
    logger.info(json.dumps({"event": "agent_settings_update", "entity": entity_id,
                            "enabled": payload.get("rollout", {}).get("enabled"), "status": status}))
    return _resp(status if status == 200 else 502, {"settings": data, "entityId": entity_id})


def lambda_handler(event, context):
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception:
            event = {}
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}
    body = {}
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
        except Exception:
            body = {}
    body = {**event, **body}
    action = body.get("action") or ("onboard" if "onboard" in (event.get("routeKey", "") + event.get("rawPath", "")) else "")

    if action == "onboard":
        return _onboard(body)
    if action in ("settings", "settings_get"):
        return _settings_get(body)
    if action in ("settings_update", "enable", "disable"):
        if action == "enable":
            body["enabled"] = True
        elif action == "disable":
            body["enabled"] = False
        return _settings_update(body)
    if action == "entities":
        return _resp(200, {"entities": DEFAULT_ENTITIES, "channels": sorted(CHANNELS)})
    return _resp(400, {"error": "unknown action",
                       "supported": ["onboard", "settings", "settings_update", "enable", "disable", "entities"]})
