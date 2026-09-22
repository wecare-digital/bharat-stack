"""WECARE.DIGITAL site language service.

Public website-facing language primitives backed by Amazon Translate and Polly.
The service discovers languages/voices from AWS at runtime; it does not keep a
hardcoded language catalogue.

Routes (API Gateway HTTP API):
  GET  /site-language/languages
  POST /site-language/translate
  GET  /site-language/voices
  POST /site-language/tts

Translation results are cached in DynamoDB. TTS responses are intentionally
limited to short/medium passages; long-form blog audio should be generated and
stored asynchronously in S3 in a later phase.

Translation provider
--------------------
Google Cloud Translation v2 is preferred when a key is available, because its
Indic output is materially better than Amazon Translate's. Amazon Translate is
the automatic fallback and remains the only provider for TTS (Polly).

The Google key is read from Secrets Manager AT RUNTIME and never leaves this
process: it is not an env var, not a build input, and never reaches the browser.
That is the whole reason this route exists as a server. A browser widget cannot
hold a key - anything shipped to the page is readable in devtools - so the page
posts here and this function holds the credential.

This replaces the Cloud Run relay the widget used to call
(wecare-translation-relay). That relay checked the Origin header, which stops
another website embedding it but not a plain HTTP client, and it billed a Google
project directly with no request cap. Here the same work sits behind the
per-route API Gateway throttle in scripts/deploy_site_language.py and the
DynamoDB cache below, which is what actually holds the bill down.

Only handler.py is packaged (see package() in scripts/deploy_site_language.py),
so there is no `requests` in the bundle - HTTP goes through urllib from stdlib.
"""

import base64
import concurrent.futures
import hashlib
import html
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
CACHE_TABLE = os.environ.get("SITE_LANGUAGE_CACHE_TABLE", "stack-wecare-digital-SiteLanguageCache")
CACHE_TTL_SECONDS = int(os.environ.get("SITE_LANGUAGE_CACHE_TTL_SECONDS", str(90 * 24 * 3600)))
MAX_TEXTS = int(os.environ.get("SITE_LANGUAGE_MAX_TEXTS", "40"))
MAX_TEXT_BYTES = int(os.environ.get("SITE_LANGUAGE_MAX_TEXT_BYTES", "9000"))
MAX_TOTAL_BYTES = int(os.environ.get("SITE_LANGUAGE_MAX_TOTAL_BYTES", "30000"))
MAX_TTS_CHARS = int(os.environ.get("SITE_LANGUAGE_MAX_TTS_CHARS", "2800"))

# "auto" uses Google when a key resolves and silently falls back to Amazon
# Translate when it does not, so this ships and serves traffic before the key is
# provisioned. "aws" and "google" pin one provider for debugging.
TRANSLATE_PROVIDER = os.environ.get("SITE_LANGUAGE_TRANSLATE_PROVIDER", "auto").strip().lower()

# wecare/google/cloud already exists in account 775261844268 and holds the
# unified Google API key (see scripts/store_provider_secret.py, which records the
# canonical id for every provider). Do NOT point this at a new secret: a parallel
# id means rotation updates one copy and consumers keep reading the other.
GOOGLE_SECRET_NAME = os.environ.get("SITE_LANGUAGE_GOOGLE_SECRET", "wecare/google/cloud")
GOOGLE_SECRET_FIELD = os.environ.get("SITE_LANGUAGE_GOOGLE_SECRET_FIELD", "api_key")
GOOGLE_ENDPOINT = "https://translation.googleapis.com/language/translate/v2"
# v2 accepts up to 128 q values per call. MAX_TEXTS is 40, so one HTTP request
# covers a whole batch - versus one AWS API call per string today.
GOOGLE_MAX_BATCH = max(1, int(os.environ.get("SITE_LANGUAGE_GOOGLE_MAX_BATCH", "64")))
GOOGLE_TIMEOUT_SECONDS = float(os.environ.get("SITE_LANGUAGE_GOOGLE_TIMEOUT", "8"))

translate_client = boto3.client("translate", region_name=REGION)
polly_client = boto3.client("polly", region_name=REGION)
secrets_client = boto3.client("secretsmanager", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
cache_table = dynamodb.Table(CACHE_TABLE)

_language_cache: Dict[str, Any] = {"at": 0, "items": []}
_voice_cache: Dict[str, Any] = {"at": 0, "items": []}
CATALOG_TTL_SECONDS = 6 * 3600

# Resolved once per container and reused across warm invocations, same pattern as
# _get_gmaps_key() in messaging/whatsapp-templates. "loaded" is the negative
# cache: a missing or malformed secret must not re-hit Secrets Manager on every
# request, and must not turn into a 500 either - it just means "use AWS".
_google_key_cache: Dict[str, Any] = {"loaded": False, "key": ""}

ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "SITE_LANGUAGE_ALLOWED_ORIGINS",
        "https://www.wecare.digital,https://wecare.digital",
    ).split(",")
    if origin.strip()
}


def _origin(event: Dict[str, Any]) -> str:
    headers = event.get("headers") or {}
    candidate = headers.get("origin") or headers.get("Origin") or ""
    return candidate if candidate in ALLOWED_ORIGINS else "https://www.wecare.digital"


def _response(event: Dict[str, Any], status: int, body: Any) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": _origin(event),
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Vary": "Origin",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }


def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError, UnicodeDecodeError):
        return {}


def _path_method(event: Dict[str, Any]) -> tuple[str, str]:
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = (http.get("method") or event.get("httpMethod") or "GET").upper()
    path = http.get("path") or event.get("rawPath") or event.get("path") or "/"
    return path.rstrip("/") or "/", method


def _list_languages() -> List[Dict[str, str]]:
    now = time.time()
    if _language_cache["items"] and now - _language_cache["at"] < CATALOG_TTL_SECONDS:
        return _language_cache["items"]

    items: List[Dict[str, str]] = []
    token: Optional[str] = None
    while True:
        kwargs: Dict[str, Any] = {"DisplayLanguageCode": "en", "MaxResults": 500}
        if token:
            kwargs["NextToken"] = token
        result = translate_client.list_languages(**kwargs)
        items.extend(
            {"code": row["LanguageCode"], "name": row["LanguageName"]}
            for row in result.get("Languages", [])
            if row.get("LanguageCode") and row.get("LanguageName")
        )
        token = result.get("NextToken")
        if not token:
            break

    items.sort(key=lambda row: row["name"].casefold())
    _language_cache.update({"at": now, "items": items})
    return items


def _list_voices() -> List[Dict[str, Any]]:
    now = time.time()
    if _voice_cache["items"] and now - _voice_cache["at"] < CATALOG_TTL_SECONDS:
        return _voice_cache["items"]

    voices: List[Dict[str, Any]] = []
    token: Optional[str] = None
    while True:
        kwargs: Dict[str, Any] = {"IncludeAdditionalLanguageCodes": True}
        if token:
            kwargs["NextToken"] = token
        result = polly_client.describe_voices(**kwargs)
        for row in result.get("Voices", []):
            voices.append(
                {
                    "id": row.get("Id", ""),
                    "name": row.get("Name", ""),
                    "languageCode": row.get("LanguageCode", ""),
                    "languageName": row.get("LanguageName", ""),
                    "gender": row.get("Gender", ""),
                    "supportedEngines": row.get("SupportedEngines", []),
                    "additionalLanguageCodes": row.get("AdditionalLanguageCodes", []),
                }
            )
        token = result.get("NextToken")
        if not token:
            break

    voices.sort(key=lambda row: (row["languageName"], row["name"]))
    _voice_cache.update({"at": now, "items": voices})
    return voices


def _google_key() -> str:
    """The Google API key, or "" when unavailable. Never logged, never returned."""
    if _google_key_cache["loaded"]:
        return _google_key_cache["key"]

    key = ""
    try:
        raw = secrets_client.get_secret_value(SecretId=GOOGLE_SECRET_NAME)
        data = json.loads(raw.get("SecretString") or "{}")
        if isinstance(data, dict):
            key = str(data.get(GOOGLE_SECRET_FIELD) or "").strip()
    except Exception as exc:
        # Log the failure class only. str(exc) on a Secrets Manager error carries
        # the secret NAME, which is fine, but never the value.
        logger.warning("google key unavailable (%s), using amazon translate", type(exc).__name__)

    _google_key_cache.update({"loaded": True, "key": key})
    # Deliberately no logging here, and this getter has no side effects.
    #
    # It previously logged which provider had been resolved, as
    # "google" if key else "aws" - a string literal, so no key could ever reach
    # the output. CodeQL still failed the build on it
    # (py/clear-text-logging-sensitive-data): the secret appears INSIDE a logging
    # expression, and its taint analysis cannot see that the ternary discards the
    # value. CodeQL is structurally right regardless of this instance - this repo
    # lost four live credentials to exactly this class of mistake, see
    # .kiro/steering/secret-handling.md - so the rule wins over the reasoning.
    #
    # The resolved provider is logged in _translate_texts instead, where the
    # value comes from _google_enabled() returning a bool and nothing in scope
    # holds the key.
    return key


def _google_enabled() -> bool:
    if TRANSLATE_PROVIDER == "aws":
        return False
    return bool(_google_key())


def _google_translate_batch(texts: List[str], target: str, source: str) -> List[Dict[str, str]]:
    """Translate a batch in ONE HTTP call. Raises on any failure so the caller falls back."""
    key = _google_key()
    if not key:
        raise RuntimeError("google key unavailable")

    body: Dict[str, Any] = {"q": texts, "target": target, "format": "text"}
    if source and source != "auto":
        body["source"] = source

    request = urllib.request.Request(
        GOOGLE_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            # Header, not ?key= - Google's own API key best practices call out
            # that a key in the query string is exposed to URL scans and lands in
            # request logs. This way the key never enters a URL.
            "x-goog-api-key": key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Surface WHY. The overwhelmingly likely 403s here are SERVICE_DISABLED
        # (Cloud Translation not enabled on the project) and API_KEY_SERVICE_BLOCKED
        # (key restricted to other APIs, e.g. Maps only). Both are one console
        # click to fix and indistinguishable without this. The error body carries
        # a status and a message but never the key.
        detail = ""
        try:
            error = (json.loads(exc.read().decode("utf-8")) or {}).get("error") or {}
            detail = str(error.get("status") or "") or str(error.get("message") or "")
        except Exception:
            detail = ""
        raise RuntimeError(f"google http {exc.code}{': ' + detail if detail else ''}") from None

    rows = ((payload.get("data") or {}).get("translations") or [])
    if len(rows) != len(texts):
        raise RuntimeError(f"google returned {len(rows)} rows for {len(texts)} texts")

    results: List[Dict[str, str]] = []
    for index, row in enumerate(rows):
        translated = str(row.get("translatedText") or "")
        if not translated:
            raise RuntimeError("google returned an empty translation")
        # format="text" still escapes &, < and > in v2 output. The Velo widget
        # decodes entities client-side for the same reason; do it once here so
        # every consumer gets clean text.
        results.append(
            {
                "translatedText": html.unescape(translated),
                "sourceLanguage": str(row.get("detectedSourceLanguage") or source or "auto"),
            }
        )
    return results


def _translation_key(text: str, source: str, target: str, provider: str = "aws") -> str:
    # The "aws" payload is byte-identical to the pre-Google version on purpose:
    # the existing cache stays warm. Google gets its own namespace so enabling it
    # does not serve back Amazon output that a visitor already paid for, and so
    # pinning the provider for debugging gives a clean comparison.
    prefix = "v1" if provider == "aws" else f"v1\0{provider}"
    payload = f"{prefix}\0{source}\0{target}\0{text}".encode("utf-8")
    return "tr#" + hashlib.sha256(payload).hexdigest()


def _cached_translation(text: str, source: str, target: str, provider: str = "aws") -> Optional[Dict[str, str]]:
    try:
        item = cache_table.get_item(Key={"cacheKey": _translation_key(text, source, target, provider)}).get("Item")
        if not item or not item.get("translatedText"):
            return None
        return {
            "translatedText": item["translatedText"],
            "sourceLanguage": item.get("sourceLanguage", source),
        }
    except Exception as exc:
        logger.warning("translation cache read failed: %s", exc)
        return None


def _save_translation(
    text: str, source: str, target: str, translated: str, detected: str, provider: str = "aws"
) -> None:
    try:
        now = int(time.time())
        cache_table.put_item(
            Item={
                "cacheKey": _translation_key(text, source, target, provider),
                "kind": "translation",
                "provider": provider,
                "sourceLanguage": detected,
                "targetLanguage": target,
                "sourceHash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "translatedText": translated,
                "createdAt": now,
                "expiresAt": now + CACHE_TTL_SECONDS,
            }
        )
    except Exception as exc:
        logger.warning("translation cache write failed: %s", exc)


def _aws_translate_one(text: str, target: str, source: str) -> Dict[str, str]:
    result = translate_client.translate_text(
        Text=text,
        SourceLanguageCode=source,
        TargetLanguageCode=target,
    )
    return {
        "translatedText": result.get("TranslatedText", text),
        "sourceLanguage": result.get("SourceLanguageCode", source),
    }


def _aws_translate_batch(texts: List[str], target: str, source: str) -> List[Dict[str, str]]:
    """Amazon Translate has no batch text API, so fan out. Order is preserved by map()."""
    if not texts:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(texts))) as pool:
        return list(pool.map(lambda text: _aws_translate_one(text, target, source), texts))


def _translate_texts(texts: List[str], target: str, source: str) -> Tuple[List[Dict[str, str]], str]:
    """Translate in request order. Returns (rows, provider_actually_used).

    Cache first, then dedupe, then one provider call for whatever is left. Dedupe
    matters more than it looks: the widget walks every text node on the page, so a
    nav label or a repeated CTA arrives many times in one batch and used to be
    billed once per occurrence.
    """
    # Derived from a bool, so the key is not in scope for this log line. See the
    # note in _google_key() for why that distinction is load-bearing.
    provider = "google" if _google_enabled() else "aws"
    logger.info(
        json.dumps({"event": "translate_provider_resolved",
                    "provider": provider,
                    "secret": GOOGLE_SECRET_NAME})
    )
    rows: List[Optional[Dict[str, str]]] = [None] * len(texts)
    pending: Dict[str, List[int]] = {}

    for index, text in enumerate(texts):
        if not text or (source != "auto" and source == target):
            rows[index] = {"translatedText": text, "sourceLanguage": source, "cached": True}
            continue
        hit = _cached_translation(text, source, target, provider)
        if hit:
            hit["cached"] = True
            rows[index] = hit
            continue
        pending.setdefault(text, []).append(index)

    if pending:
        unique = list(pending.keys())
        fresh: List[Dict[str, str]] = []
        if provider == "google":
            try:
                for start in range(0, len(unique), GOOGLE_MAX_BATCH):
                    fresh.extend(_google_translate_batch(unique[start:start + GOOGLE_MAX_BATCH], target, source))
            except Exception as exc:
                # Any Google failure - bad key, API not enabled on the project,
                # key restricted to other APIs, quota, timeout - degrades to
                # Amazon rather than failing the visitor's page.
                #
                # Only OUR OWN RuntimeError text is logged verbatim, because
                # _google_translate_batch builds it from the HTTP status and
                # Google's error.status field and nothing else. Every other
                # exception contributes its type only.
                #
                # This is stricter than necessary: the key travels in the
                # x-goog-api-key header, and no urllib exception carries request
                # headers, so str(exc) could not echo it. But "I reasoned it cannot
                # leak" is what the previous version of this file said one line
                # before CodeQL failed the build on it, and a diagnostic is not
                # worth arguing with a secrets rule over. No detail is lost: the
                # useful 403 reason is already inside the RuntimeError.
                detail = str(exc) if isinstance(exc, RuntimeError) else ""
                logger.warning(
                    json.dumps({"event": "google_translate_failed",
                                "errorType": type(exc).__name__,
                                "detail": detail,
                                "fallback": "aws"})
                )
                provider = "aws"
                fresh = []
        if not fresh:
            provider = "aws"
            fresh = _aws_translate_batch(unique, target, source)

        for text, row in zip(unique, fresh):
            _save_translation(text, source, target, row["translatedText"], row["sourceLanguage"], provider)
            for index in pending[text]:
                rows[index] = {**row, "cached": False}

    # Nothing may stay None: every index is either short-circuited, a cache hit,
    # or filled from a provider call above.
    return [row or {"translatedText": texts[i], "sourceLanguage": source, "cached": False}
            for i, row in enumerate(rows)], provider


def _validate_texts(texts: Any) -> List[str]:
    if not isinstance(texts, list) or not texts:
        raise ValueError("texts must be a non-empty array")
    if len(texts) > MAX_TEXTS:
        raise ValueError(f"maximum {MAX_TEXTS} texts per request")

    clean: List[str] = []
    total = 0
    for value in texts:
        if not isinstance(value, str):
            raise ValueError("every text must be a string")
        text = value.strip()
        size = len(text.encode("utf-8"))
        if size > MAX_TEXT_BYTES:
            raise ValueError(f"one text exceeds {MAX_TEXT_BYTES} UTF-8 bytes")
        total += size
        clean.append(text)
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"request exceeds {MAX_TOTAL_BYTES} UTF-8 bytes")
    return clean


def _pick_voice(language: str, requested_voice: str = "") -> Optional[Dict[str, Any]]:
    voices = _list_voices()
    if requested_voice:
        exact = next((v for v in voices if v["id"] == requested_voice), None)
        if exact:
            return exact

    lang = language.lower()
    candidates = [
        v for v in voices
        if v["languageCode"].lower() == lang
        or v["languageCode"].lower().startswith(lang + "-")
        or any(code.lower() == lang or code.lower().startswith(lang + "-") for code in v["additionalLanguageCodes"])
    ]
    if not candidates:
        return None

    # Indian locale first, then neural, then name. Without the locale term a
    # bare "en" resolves to Amy/en-GB purely because she is neural and sorts
    # early, which gives an Indian brand a British voice.
    candidates.sort(
        key=lambda v: (
            not _is_indian(v),
            "neural" not in v["supportedEngines"],
            v["name"],
        )
    )
    return candidates[0]


def _is_indian(voice: Dict[str, Any]) -> bool:
    codes = [voice.get("languageCode", "")] + list(voice.get("additionalLanguageCodes") or [])
    return any(str(code).lower().endswith("-in") for code in codes)


def _resolve_locale(voice: Dict[str, Any], language: str) -> str:
    """Locale to synthesise in.

    Bilingual voices such as Kajal are listed under one primary languageCode
    (hi-IN) while also supporting others (en-IN). Passing the primary code would
    speak English text with Hindi pronunciation, so match the request instead.
    """
    lang = language.lower()
    for code in [voice.get("languageCode", "")] + list(voice.get("additionalLanguageCodes") or []):
        candidate = str(code).lower()
        if candidate == lang or candidate.startswith(lang + "-"):
            return str(code)
    return str(voice.get("languageCode", ""))


def _handle_translate(event: Dict[str, Any]) -> Dict[str, Any]:
    body = _body(event)
    texts = _validate_texts(body.get("texts"))
    target = str(body.get("targetLanguage") or "").strip()
    source = str(body.get("sourceLanguage") or "auto").strip()
    if not target:
        raise ValueError("targetLanguage is required")

    supported = {row["code"] for row in _list_languages()}
    if target not in supported:
        raise ValueError("unsupported targetLanguage")
    if source != "auto" and source not in supported:
        raise ValueError("unsupported sourceLanguage")

    rows, provider = _translate_texts(texts, target, source)

    return _response(
        event,
        200,
        {
            "targetLanguage": target,
            # Reported so a failed Google call is visible in the browser's network
            # tab instead of silently costing quality. The client does not branch
            # on it - one endpoint, one response shape.
            "provider": provider,
            "translations": rows,
        },
    )


def _handle_tts(event: Dict[str, Any]) -> Dict[str, Any]:
    body = _body(event)
    text = str(body.get("text") or "").strip()
    language = str(body.get("language") or "").strip()
    requested_voice = str(body.get("voiceId") or "").strip()
    if not text:
        raise ValueError("text is required")
    if not language:
        raise ValueError("language is required")
    if len(text) > MAX_TTS_CHARS:
        raise ValueError(f"text exceeds {MAX_TTS_CHARS} characters")

    voice = _pick_voice(language, requested_voice)
    if not voice:
        return _response(event, 422, {"error": "No Amazon Polly voice is available for this language"})

    engines = voice.get("supportedEngines") or []
    engine = "neural" if "neural" in engines else (engines[0] if engines else "standard")
    locale = _resolve_locale(voice, language)
    result = polly_client.synthesize_speech(
        Engine=engine,
        LanguageCode=locale,
        OutputFormat="mp3",
        Text=text,
        TextType="text",
        VoiceId=voice["id"],
    )
    audio = result["AudioStream"].read()
    return _response(
        event,
        200,
        {
            "audioBase64": base64.b64encode(audio).decode("ascii"),
            "mimeType": result.get("ContentType", "audio/mpeg"),
            "voice": voice,
            "locale": locale,
            "engine": engine,
            "requestCharacters": result.get("RequestCharacters", len(text)),
        },
    )


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    path, method = _path_method(event)
    if method == "OPTIONS":
        return _response(event, 200, {})
    # INTENTIONALLY PUBLIC - do not add require_auth here.
    #
    # LanguageBar renders from pages/_app.tsx on every page including public
    # ones, so anonymous visitors must be able to list languages and voices and
    # request translation and TTS. Requiring a Cognito token would blank the
    # language bar for every signed-out visitor.
    #
    # It also cannot work mechanically: this function is packaged standalone
    # (see scripts/deploy_all_lambdas.py) and does not bundle lambda_utils, so
    # importing the shared middleware fails the pre-upload import validation.
    # That validation is what caught this before it shipped.
    #
    # The real exposure on these four routes is COST, not data:
    # /site-language/tts drives Polly and /translate drives Translate. The
    # correct mitigation is per-route API Gateway throttling, not
    # authentication. Not yet applied - tracked as an improvement.
    try:
        if path.endswith("/site-language/languages") and method == "GET":
            return _response(event, 200, {"languages": _list_languages()})
        if path.endswith("/site-language/translate") and method == "POST":
            return _handle_translate(event)
        if path.endswith("/site-language/voices") and method == "GET":
            return _response(event, 200, {"voices": _list_voices()})
        if path.endswith("/site-language/tts") and method == "POST":
            return _handle_tts(event)
        return _response(event, 404, {"error": "Not found"})
    except ValueError as exc:
        return _response(event, 400, {"error": str(exc)})
    except Exception as exc:
        logger.exception("site-language failure")
        return _response(event, 500, {"error": "Language service unavailable"})
