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
"""

import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

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

translate_client = boto3.client("translate", region_name=REGION)
polly_client = boto3.client("polly", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
cache_table = dynamodb.Table(CACHE_TABLE)

_language_cache: Dict[str, Any] = {"at": 0, "items": []}
_voice_cache: Dict[str, Any] = {"at": 0, "items": []}
CATALOG_TTL_SECONDS = 6 * 3600

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


def _translation_key(text: str, source: str, target: str) -> str:
    payload = f"v1\0{source}\0{target}\0{text}".encode("utf-8")
    return "tr#" + hashlib.sha256(payload).hexdigest()


def _cached_translation(text: str, source: str, target: str) -> Optional[Dict[str, str]]:
    try:
        item = cache_table.get_item(Key={"cacheKey": _translation_key(text, source, target)}).get("Item")
        if not item or not item.get("translatedText"):
            return None
        return {
            "translatedText": item["translatedText"],
            "sourceLanguage": item.get("sourceLanguage", source),
        }
    except Exception as exc:
        logger.warning("translation cache read failed: %s", exc)
        return None


def _save_translation(text: str, source: str, target: str, translated: str, detected: str) -> None:
    try:
        now = int(time.time())
        cache_table.put_item(
            Item={
                "cacheKey": _translation_key(text, source, target),
                "kind": "translation",
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


def _translate_one(text: str, target: str, source: str) -> Dict[str, str]:
    if source != "auto" and source == target:
        return {"translatedText": text, "sourceLanguage": source}

    hit = _cached_translation(text, source, target)
    if hit:
        hit["cached"] = True
        return hit

    result = translate_client.translate_text(
        Text=text,
        SourceLanguageCode=source,
        TargetLanguageCode=target,
    )
    translated = result.get("TranslatedText", text)
    detected = result.get("SourceLanguageCode", source)
    _save_translation(text, source, target, translated, detected)
    return {
        "translatedText": translated,
        "sourceLanguage": detected,
        "cached": False,
    }


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

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(texts))) as pool:
        rows = list(pool.map(lambda text: _translate_one(text, target, source), texts))

    return _response(
        event,
        200,
        {
            "targetLanguage": target,
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
