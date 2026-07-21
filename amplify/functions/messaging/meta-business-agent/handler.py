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

from lambda_utils.middleware import require_auth

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

# agent_config/settings enum constraints (per Meta Business Agent spec)
_AI_AUDIENCES = {"ALLOWLISTED_ONLY", "EVERYONE"}
_FOLLOWUP_INTERVALS = {0, 300, 900, 1800, 3600, 7200, 28800, 86400}

_token_cache = {}
CORS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


import hmac
import hashlib


def _creds():
    if "t" in _token_cache:
        return _token_cache["t"], _token_cache["s"]
    resp = secrets_client.get_secret_value(SecretId=META_TOKEN_SECRET)
    data = json.loads(resp["SecretString"])
    _token_cache["t"] = (data.get("access_token") or "").strip()
    _token_cache["s"] = (data.get("app_secret") or "").strip()
    return _token_cache["t"], _token_cache["s"]


def _appsecret_proof(token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


# ─────────────────────────────────────────────────────────────────────────
# Agent Tool endpoint — the target that Meta Business Agent connector tools call.
# Public route (POST /agent-tool) but GATED by a scoped static token in the
# X-Agent-Token header (secret wecare/agent-connector-token). Read-only.
# ─────────────────────────────────────────────────────────────────────────
AGENT_TOOL_SECRET = os.environ.get("AGENT_TOOL_SECRET", "wecare/agent-connector-token")
# WABA phone-number-id -> its Meta product catalog id
_CATALOG_BY_ENTITY = {
    "1016149501586345": "1607047307067517",   # WABA1 wecare_catalog
    "1055232054343117": "1424934879646296",   # WABA2 Catalogue_Products
}


def _agent_tool_token() -> str:
    if "agent_tool" in _token_cache:
        return _token_cache["agent_tool"]
    try:
        resp = secrets_client.get_secret_value(SecretId=AGENT_TOOL_SECRET)
        tok = (json.loads(resp["SecretString"]).get("token") or "").strip()
    except Exception:
        tok = ""
    _token_cache["agent_tool"] = tok
    return tok


def _tool_product_lookup(body: dict):
    """Return catalog products matching a query (name substring) or retailer_id.
    Read-only; used by the agent to answer product/price/availability questions."""
    query = (body.get("query") or body.get("product") or "").strip().lower()
    retailer_id = (body.get("retailer_id") or "").strip()
    entity_id = str(body.get("entity_id") or "1016149501586345")
    catalog_id = _CATALOG_BY_ENTITY.get(entity_id, "1607047307067517")
    token, secret = _creds()
    fields = "retailer_id,name,price,sale_price,availability,description,url"
    url = f"https://graph.facebook.com/v22.0/{catalog_id}/products?fields={fields}&limit=100&access_token={token}"
    if secret:
        url += "&appsecret_proof=" + _appsecret_proof(token, secret)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read().decode())
        products = data.get("data", [])
    except Exception as e:
        return {"statusCode": 200, "headers": CORS,
                "body": json.dumps({"status": "error", "error": str(e)[:120], "products": []})}
    out = []
    for p in products:
        rid = p.get("retailer_id", "")
        name = (p.get("name") or "")
        if retailer_id and rid != retailer_id:
            continue
        if query and query not in name.lower():
            continue
        out.append({"retailer_id": rid, "name": name, "price": p.get("price"),
                    "sale_price": p.get("sale_price"), "availability": p.get("availability"),
                    "description": p.get("description"), "url": p.get("url")})
    if not out and not query and not retailer_id:
        out = [{"retailer_id": p.get("retailer_id"), "name": p.get("name"), "price": p.get("price"),
                "availability": p.get("availability")} for p in products]
    return {"statusCode": 200, "headers": CORS, "body": json.dumps({"status": "success", "products": out})}


def _agent_tool(event: dict):
    """Token-gated, read-only endpoint the Meta agent connector tools call."""
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    supplied = headers.get("x-agent-token", "")
    expected = _agent_tool_token()
    if not expected or supplied != expected:
        return {"statusCode": 401, "headers": CORS, "body": json.dumps({"error": "unauthorized"})}
    body = {}
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
        except Exception:
            body = {}
    elif isinstance(event.get("body"), dict):
        body = event["body"]
    op = (body.get("op") or "product_lookup").lower()
    if op == "product_lookup":
        return _tool_product_lookup(body)
    return {"statusCode": 400, "headers": CORS, "body": json.dumps({"error": "unknown op", "supported": ["product_lookup"]})}


def _resp(status, body):
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body)}


def _pass_status(status, ok=(200,), success_status=None):
    """Map an upstream Meta status to the HTTP status we return to the caller.

    A non-2xx from Meta is NOT a gateway failure. In particular Meta returns
    403 when the Business AI Terms of Service have not been accepted for the
    WABA. Surfacing that as 502 falsely trips the apigw-5xx CloudWatch alarm.

    - success (status in `ok`) -> success_status (or the upstream status)
    - upstream client error (4xx) -> surface the SAME 4xx (e.g. 403) so API
      Gateway records a 4xx, not a 5xx
    - genuine upstream 5xx / network error -> 502 Bad Gateway
    """
    if status in ok:
        return success_status or status
    if 400 <= status < 500:
        return status
    return 502


def _meta_request(method: str, url: str, payload: dict | None):
    token, secret = _creds()
    if secret:  # api.facebook.com requires appsecret_proof
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}appsecret_proof={_appsecret_proof(token, secret)}"
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body if method != "GET" else None, method=method)
    req.add_header("Authorization", f"Bearer {token}")
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
    return _resp(_pass_status(status, (200, 201)), {"onboarding": data, "entityId": entity_id, "channel": channel})


GRAPH = os.environ.get("META_GRAPH_BASE", "https://graph.facebook.com/v22.0")
# WABA IDs (not phone-number IDs) — subscribed_apps is per WABA
WABA_IDS = {"WABA1": "2094615664435155", "WABA-T": "2513394156072604"}


def _readiness(body: dict):
    """Step 6/7 check: is the app subscribed to each WABA, and which webhook
    fields are set? (Uses Graph API, not the ToS-gated agent API.)"""
    out = {}
    for name, waba in WABA_IDS.items():
        status, data = _meta_request("GET", f"{GRAPH}/{waba}/subscribed_apps", None)
        out[name] = {"waba": waba, "httpStatus": status, "subscribed_apps": data}
    return _resp(200, {"readiness": out,
                       "need_fields": ["messages", "standby", "messaging_handovers"]})


def _eligibility(body: dict):
    """GET /{entity_id}/agent_eligibility/ -> {is_eligible: bool}"""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    status, data = _meta_request("GET", f"{GRAPH_HOST}/{entity_id}/agent_eligibility/", None)
    return _resp(_pass_status(status, (200,)), {"eligibility": data, "entityId": entity_id})


def _settings_url(entity_id: str, agent_id: str | None) -> str:
    url = f"{GRAPH_HOST}/{entity_id}/agent_config/settings"
    return f"{url}?agent_id={agent_id}" if agent_id else url


def _settings_get(body: dict):
    """GET /{entity_id}/agent_config/settings  -> array of settings."""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    status, data = _meta_request("GET", _settings_url(entity_id, body.get("agentId")), None)
    return _resp(_pass_status(status, (200,)), {"settings": data, "entityId": entity_id})


def _settings_update(body: dict):
    """PUT /{entity_id}/agent_config/settings — full replace, so we GET current
    settings and merge the requested changes to avoid clobbering other fields.
    Accepted inputs: enabled(bool), handoff{enabled,message}, followup{enabled,
    followup_interval_in_seconds,message}, aiAudience(ALLOWLISTED_ONLY|EVERYONE)."""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    agent_id = body.get("agentId")

    # ── validate enum fields against the Meta spec (fail fast with a clear 400) ──
    if "aiAudience" in body and body["aiAudience"] not in _AI_AUDIENCES:
        return _resp(400, {"error": f"aiAudience must be one of {sorted(_AI_AUDIENCES)}"})
    if "followup" in body and isinstance(body["followup"], dict):
        _iv = body["followup"].get("followup_interval_in_seconds")
        if _iv is not None and _iv not in _FOLLOWUP_INTERVALS:
            return _resp(400, {"error": f"followup_interval_in_seconds must be one of {sorted(_FOLLOWUP_INTERVALS)}"})

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
    return _resp(_pass_status(status, (200,)), {"settings": data, "entityId": entity_id})


def _allowlist_url(entity_id: str, entry_id: str | None = None) -> str:
    base = f"{GRAPH_HOST}/{entity_id}/agent_config/allowlist"
    return f"{base}/{entry_id}" if entry_id else base


def _allowlist_list(body: dict):
    """GET /{entity_id}/agent_config/allowlist -> [{id, consumer_phone_number}]"""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    if not entity_id:
        return _resp(400, {"error": "entityId required"})
    status, data = _meta_request("GET", _allowlist_url(entity_id), None)
    return _resp(_pass_status(status, (200,)), {"allowlist": data, "entityId": entity_id})


def _allowlist_add(body: dict):
    """POST /{entity_id}/agent_config/allowlist  {consumer_phone_number} (E.164)"""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    phone = (body.get("consumerPhoneNumber") or body.get("phone") or "").strip()
    if not entity_id or not phone:
        return _resp(400, {"error": "entityId and consumerPhoneNumber (E.164, e.g. +15551234567) required"})
    status, data = _meta_request("POST", _allowlist_url(entity_id), {"consumer_phone_number": phone})
    return _resp(_pass_status(status, (200, 201)), {"entry": data, "entityId": entity_id})


def _allowlist_remove(body: dict):
    """DELETE /{entity_id}/agent_config/allowlist/{entry_id} -> 204"""
    entity_id = body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")
    entry_id = (body.get("entryId") or "").strip()
    if not entity_id or not entry_id:
        return _resp(400, {"error": "entityId and entryId required"})
    status, data = _meta_request("DELETE", _allowlist_url(entity_id, entry_id), None)
    return _resp(_pass_status(status, (200, 204), success_status=200), {"deleted": status in (200, 204), "detail": data})


# ─────────────────────────────────────────────────────────────────────────
# Configure group — skills, knowledge, connectors.
# Paths follow the agent_config/ + agent_knowledge/ convention used by the
# settings/allowlist endpoints above. Request bodies mirror Meta's docs; verify
# exact shapes against the per-endpoint OpenAPI specs when refining.
# ─────────────────────────────────────────────────────────────────────────

_KNOWLEDGE = {"business_info", "faqs", "websites", "files"}


def _entity(body: dict) -> str:
    return body.get("entityId") or DEFAULT_ENTITIES.get(body.get("waba", ""), "")


def _with_agent(url: str, agent_id: str | None) -> str:
    return f"{url}?agent_id={agent_id}" if agent_id else url


def _skills_get(body: dict):
    """GET /{entity_id}/agent_config/skills — system instructions that shape replies."""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", _with_agent(f"{GRAPH_HOST}/{eid}/agent_config/skills", body.get("agentId")), None)
    return _resp(_pass_status(st, (200,)), {"skills": d, "entityId": eid})


def _skill_payload(body: dict) -> dict:
    """Build a BizAIOmniChannelSkillsRequest: {title, description, skill}.
    `title` must be lowercase letters/numbers/hyphens; `skill` is the instruction body."""
    return {k: v for k, v in {
        "title": body.get("title"),
        "description": body.get("description"),
        "skill": body.get("skill") or body.get("instruction"),  # `skill` is the instruction text
    }.items() if v is not None}


def _skills_create(body: dict):
    """POST /{entity_id}/agent_config/skills — create a skill {title, description, skill}."""
    eid = _entity(body)
    payload = _skill_payload(body)
    if not eid or not payload.get("title") or not payload.get("skill"):
        return _resp(400, {"error": "entityId, title (lowercase-hyphen) and skill (instruction text) required"})
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_config/skills", payload)
    return _resp(_pass_status(st, (200, 201)), {"skill": d, "entityId": eid})


def _skills_update(body: dict):
    """PUT /{entity_id}/agent_config/skills/{skill_id} — replace one skill."""
    eid = _entity(body)
    sid = (body.get("skillId") or "").strip()
    payload = _skill_payload(body)
    if not eid or not sid or not payload.get("skill"):
        return _resp(400, {"error": "entityId, skillId and skill (instruction text) required"})
    st, d = _meta_request("PUT", f"{GRAPH_HOST}/{eid}/agent_config/skills/{sid}", payload)
    return _resp(_pass_status(st, (200,)), {"skill": d, "entityId": eid})


def _skills_delete(body: dict):
    """DELETE /{entity_id}/agent_config/skills/{skill_id} -> 204"""
    eid = _entity(body)
    sid = (body.get("skillId") or "").strip()
    if not eid or not sid:
        return _resp(400, {"error": "entityId and skillId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_config/skills/{sid}", None)
    return _resp(_pass_status(st, (200, 204), success_status=200), {"deleted": st in (200, 204), "detail": d})


# ── Business Info (agent_config/business_info) — VERIFIED paths ──
_BUSINESS_INFO_FIELDS = {"payment_method", "return_policy", "purchase_info",
                         "delivery_and_shipping", "business_description", "contact_info"}


def _business_info_get(body: dict):
    """GET /{entity_id}/agent_config/business_info"""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", f"{GRAPH_HOST}/{eid}/agent_config/business_info", None)
    return _resp(_pass_status(st, (200,)), {"business_info": d, "entityId": eid})


def _business_info_update(body: dict):
    """PUT /{entity_id}/agent_config/business_info — full replace with provided fields."""
    eid = _entity(body)
    info = body.get("businessInfo") or body.get("business_info") or {}
    if not eid or not isinstance(info, dict) or not info:
        return _resp(400, {"error": "entityId and businessInfo{} required"})
    payload = {k: v for k, v in info.items() if k in _BUSINESS_INFO_FIELDS}
    st, d = _meta_request("PUT", f"{GRAPH_HOST}/{eid}/agent_config/business_info", payload)
    return _resp(_pass_status(st, (200,)), {"business_info": d, "entityId": eid})


def _business_info_reset(body: dict):
    """DELETE /{entity_id}/agent_config/business_info — reset to defaults."""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_config/business_info", None)
    return _resp(_pass_status(st, (200,)), {"business_info": d, "entityId": eid})


# ── FAQs (agent_config/faq) — VERIFIED paths ──
def _faq_list(body: dict):
    """GET /{entity_id}/agent_config/faq -> [{id, question, answer, created_at}]"""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", f"{GRAPH_HOST}/{eid}/agent_config/faq", None)
    return _resp(_pass_status(st, (200,)), {"faqs": d, "entityId": eid})


def _faq_create(body: dict):
    """POST /{entity_id}/agent_config/faq  {question, answer, metadata?}"""
    eid = _entity(body)
    q = (body.get("question") or "").strip()
    a = (body.get("answer") or "").strip()
    if not eid or not q or not a:
        return _resp(400, {"error": "entityId, question and answer required"})
    item = {"question": q, "answer": a}
    if isinstance(body.get("metadata"), dict):
        item["metadata"] = body["metadata"]
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_config/faq", item)
    return _resp(_pass_status(st, (200, 201)), {"faq": d, "entityId": eid})


def _faq_update(body: dict):
    """PUT /{entity_id}/agent_config/faq/{faq_id}  {question, answer}"""
    eid = _entity(body)
    fid = (body.get("faqId") or "").strip()
    q = (body.get("question") or "").strip()
    a = (body.get("answer") or "").strip()
    if not eid or not fid or not q or not a:
        return _resp(400, {"error": "entityId, faqId, question and answer required"})
    item = {"question": q, "answer": a}
    if isinstance(body.get("metadata"), dict):
        item["metadata"] = body["metadata"]
    st, d = _meta_request("PUT", f"{GRAPH_HOST}/{eid}/agent_config/faq/{fid}", item)
    return _resp(_pass_status(st, (200,)), {"faq": d, "entityId": eid})


def _faq_delete(body: dict):
    """DELETE /{entity_id}/agent_config/faq/{faq_id} -> 204"""
    eid = _entity(body)
    fid = (body.get("faqId") or "").strip()
    if not eid or not fid:
        return _resp(400, {"error": "entityId and faqId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_config/faq/{fid}", None)
    return _resp(_pass_status(st, (200, 204), success_status=200), {"deleted": st in (200, 204), "detail": d})


# ── Websites (agent_config/websites) — crawled knowledge sources ──
def _websites_list(body: dict):
    """GET /{entity_id}/agent_config/websites -> [{id, url, crawl_status}]"""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", f"{GRAPH_HOST}/{eid}/agent_config/websites", None)
    return _resp(_pass_status(st, (200,)), {"websites": d, "entityId": eid})


def _websites_add(body: dict):
    """POST /{entity_id}/agent_config/websites  {url}"""
    eid = _entity(body)
    url = (body.get("url") or "").strip()
    if not eid or not url:
        return _resp(400, {"error": "entityId and url required"})
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_config/websites", {"url": url})
    return _resp(_pass_status(st, (200, 201)), {"website": d, "entityId": eid})


def _websites_remove(body: dict):
    """DELETE /{entity_id}/agent_config/websites/{website_id}"""
    eid = _entity(body)
    wid = (body.get("websiteId") or "").strip()
    if not eid or not wid:
        return _resp(400, {"error": "entityId and websiteId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_config/websites/{wid}", None)
    return _resp(_pass_status(st, (200, 204), success_status=200), {"deleted": st in (200, 204), "detail": d})


# ── Connectors + Tools (agent_connectors/{connector_id}/tools) — lets the AI call our APIs ──
def _connectors_list(body: dict):
    """GET /{entity_id}/agent_connectors — external APIs the agent can call."""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", f"{GRAPH_HOST}/{eid}/agent_connectors", None)
    return _resp(_pass_status(st, (200,)), {"connectors": d, "entityId": eid})


def _connectors_add(body: dict):
    """POST /{entity_id}/agent_connectors  {connector...}"""
    eid = _entity(body); spec = body.get("connector") or {}
    if not eid or not spec:
        return _resp(400, {"error": "entityId and connector{} required"})
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_connectors", spec)
    return _resp(_pass_status(st, (200, 201)), {"created": d, "entityId": eid})


def _connectors_remove(body: dict):
    """DELETE /{entity_id}/agent_connectors/{connector_id}"""
    eid = _entity(body); cid = body.get("connectorId", "")
    if not eid or not cid:
        return _resp(400, {"error": "entityId and connectorId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_connectors/{cid}", None)
    return _resp(_pass_status(st, (200, 204), success_status=200), {"deleted": st in (200, 204), "detail": d})


def _tools_list(body: dict):
    """GET /{entity_id}/agent_connectors/{connector_id}/tools"""
    eid = _entity(body); cid = body.get("connectorId", "")
    if not eid or not cid:
        return _resp(400, {"error": "entityId and connectorId required"})
    st, d = _meta_request("GET", f"{GRAPH_HOST}/{eid}/agent_connectors/{cid}/tools", None)
    return _resp(_pass_status(st, (200,)), {"tools": d, "entityId": eid})


def _tools_add(body: dict):
    """POST /{entity_id}/agent_connectors/{connector_id}/tools  {tool...}"""
    eid = _entity(body); cid = body.get("connectorId", ""); spec = body.get("tool") or {}
    if not eid or not cid or not spec:
        return _resp(400, {"error": "entityId, connectorId and tool{} required"})
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_connectors/{cid}/tools", spec)
    return _resp(_pass_status(st, (200, 201)), {"created": d, "entityId": eid})


def _tools_remove(body: dict):
    """DELETE /{entity_id}/agent_connectors/{connector_id}/tools/{tool_id}"""
    eid = _entity(body); cid = body.get("connectorId", ""); tid = body.get("toolId", "")
    if not eid or not cid or not tid:
        return _resp(400, {"error": "entityId, connectorId and toolId required"})
    st, d = _meta_request("DELETE", f"{GRAPH_HOST}/{eid}/agent_connectors/{cid}/tools/{tid}", None)
    return _resp(_pass_status(st, (200, 204), success_status=200), {"deleted": st in (200, 204), "detail": d})


def _tools_run(body: dict):
    """POST /{entity_id}/agent_connectors/{connector_id}/tools/{tool_id}/run  {input}"""
    eid = _entity(body); cid = body.get("connectorId", ""); tid = body.get("toolId", "")
    if not eid or not cid or not tid:
        return _resp(400, {"error": "entityId, connectorId and toolId required"})
    payload = {"input": body.get("input") or "{}"}
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_connectors/{cid}/tools/{tid}/run", payload)
    return _resp(_pass_status(st, (200,)), {"result": d, "entityId": eid})


# ─────────────────────────────────────────────────────────────────────────
# Operate group — thread control, agent events, test, eval.
# ─────────────────────────────────────────────────────────────────────────

def _thread_control(body: dict):
    """Cloud API handover: pass control back to the agent, or take it.
    op: pass|take ; recipient = consumer phone (E.164)."""
    eid = _entity(body); recipient = (body.get("recipient") or "").strip()
    op = (body.get("op") or "pass").lower()
    if not eid or not recipient:
        return _resp(400, {"error": "entityId and recipient required"})
    verb = "pass_thread_control" if op == "pass" else "take_thread_control"
    st, d = _meta_request("POST", f"{GRAPH}/{eid}/{verb}",
                          {"messaging_product": "whatsapp", "recipient": recipient})
    return _resp(_pass_status(st, (200, 201)), {"thread_control": d, "op": op, "entityId": eid})


def _agent_event(body: dict):
    """POST /{entity_id}/agent_event — trigger an agent action for a business event."""
    eid = _entity(body); payload = body.get("event") or {}
    if not eid or not payload:
        return _resp(400, {"error": "entityId and event{} required"})
    st, d = _meta_request("POST", f"{GRAPH_HOST}/{eid}/agent_event", payload)
    return _resp(_pass_status(st, (200, 201)), {"event": d, "entityId": eid})


def _agent_test(body: dict):
    """POST /{entity_id}/agent_test — send a test message to the agent."""
    eid = _entity(body); msg = body.get("message")
    if not eid or not msg:
        return _resp(400, {"error": "entityId and message required"})
    st, d = _meta_request("POST", _with_agent(f"{GRAPH_HOST}/{eid}/agent_test", body.get("agentId")), {"message": msg})
    return _resp(_pass_status(st, (200, 201)), {"result": d, "entityId": eid})


def _agent_eval(body: dict):
    """GET /{entity_id}/agent_eval — agent performance metrics."""
    eid = _entity(body)
    if not eid:
        return _resp(400, {"error": "entityId required"})
    st, d = _meta_request("GET", _with_agent(f"{GRAPH_HOST}/{eid}/agent_eval", body.get("agentId")), None)
    return _resp(_pass_status(st, (200,)), {"eval": d, "entityId": eid})


def lambda_handler(event, context):
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception:
            event = {}
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    # Agent Tool endpoint (POST /agent-tool) — called by Meta's agent connector,
    # gated by the X-Agent-Token header (NOT Cognito). Must run before require_auth.
    _path = (event.get("rawPath") or event.get("requestContext", {}).get("http", {}).get("path", "")
             or event.get("routeKey", ""))
    if "agent-tool" in _path:
        return _agent_tool(event)

    # Inbound auth: require a valid Cognito token (gateway routes are NONE, so
    # protection is enforced here — consistent with the platform middleware).
    auth = require_auth(event)
    if auth is not None:
        return auth

    body = {}
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
        except Exception:
            body = {}
    body = {**event, **body}
    action = body.get("action") or ("onboard" if "onboard" in (event.get("routeKey", "") + event.get("rawPath", "")) else "")

    if action == "readiness":
        return _readiness(body)
    if action == "eligibility":
        return _eligibility(body)
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
    if action in ("allowlist", "allowlist_list"):
        return _allowlist_list(body)
    if action == "allowlist_add":
        return _allowlist_add(body)
    if action == "allowlist_remove":
        return _allowlist_remove(body)
    # Configure group
    if action in ("skills", "skills_list"):
        return _skills_get(body)
    if action == "skills_create":
        return _skills_create(body)
    if action == "skills_update":
        return _skills_update(body)
    if action == "skills_delete":
        return _skills_delete(body)
    # Business info (knowledge)
    if action in ("business_info", "business_info_get"):
        return _business_info_get(body)
    if action == "business_info_update":
        return _business_info_update(body)
    if action == "business_info_reset":
        return _business_info_reset(body)
    # FAQs
    if action in ("faq", "faq_list", "faqs"):
        return _faq_list(body)
    if action == "faq_create":
        return _faq_create(body)
    if action == "faq_update":
        return _faq_update(body)
    if action == "faq_delete":
        return _faq_delete(body)
    # Websites
    if action in ("websites", "websites_list"):
        return _websites_list(body)
    if action == "websites_add":
        return _websites_add(body)
    if action == "websites_remove":
        return _websites_remove(body)
    # Connectors + tools
    if action in ("connectors", "connectors_list"):
        return _connectors_list(body)
    if action == "connectors_add":
        return _connectors_add(body)
    if action == "connectors_remove":
        return _connectors_remove(body)
    if action in ("tools", "tools_list"):
        return _tools_list(body)
    if action == "tools_add":
        return _tools_add(body)
    if action == "tools_remove":
        return _tools_remove(body)
    if action == "tools_run":
        return _tools_run(body)
    # Operate group
    if action == "thread_control":
        return _thread_control(body)
    if action == "agent_event":
        return _agent_event(body)
    if action == "agent_test":
        return _agent_test(body)
    if action == "agent_eval":
        return _agent_eval(body)
    if action == "entities":
        return _resp(200, {"entities": DEFAULT_ENTITIES, "channels": sorted(CHANNELS)})
    return _resp(400, {"error": "unknown action", "supported": [
        "eligibility", "onboard", "readiness", "settings", "settings_update", "enable", "disable",
        "allowlist", "allowlist_add", "allowlist_remove",
        "skills", "skills_create", "skills_update", "skills_delete",
        "business_info", "business_info_update", "business_info_reset",
        "faq", "faq_create", "faq_update", "faq_delete",
        "websites", "websites_add", "websites_remove",
        "connectors", "connectors_add", "connectors_remove",
        "tools", "tools_add", "tools_remove", "tools_run",
        "thread_control", "agent_event", "agent_test", "agent_eval", "entities"]})
