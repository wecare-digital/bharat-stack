"""
WeCare WhatsApp AI Voice Bot — Pipecat + AWS Services

Handles incoming WhatsApp voice calls with real-time AI:
  Caller audio → AWS Transcribe (STT) → Bedrock Nova Lite (LLM) → Polly Kajal (TTS) → Caller

Runs on Lightsail $3.50/mo or t4g.nano ~$3/mo.
Supports dual WABA (WABA1 + WABA2) with separate tokens.
Loads Meta tokens from AWS Secrets Manager (same secret as Lambda handler).

Endpoints:
  GET  /whatsapp       — Meta webhook verification
  POST /whatsapp       — Meta call webhook events (connect, terminate)
  GET  /health         — Health check
  POST /call           — Manual trigger from Lambda (forwarded call event)
"""

import os
import asyncio
import logging
import json
import hmac
import hashlib
from typing import Optional

import aiohttp
import boto3
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import uvicorn

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.aws.stt import AWSTranscribeSTTService
from pipecat.services.aws.tts import AWSPollyTTSService
from pipecat.services.aws.llm import AWSBedrockLLMService
from pipecat.transports.whatsapp.client import WhatsAppClient
from pipecat.transports.whatsapp.api import WhatsAppWebhookRequest, WhatsAppApi
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame
from pipecat.transcriptions.language import Language

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("wecare-bot")

# ─── Config ──────────────────────────────────────────────────────────

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
POLLY_VOICE = os.getenv("POLLY_VOICE_ID", "Kajal")
POLLY_ENGINE = os.getenv("POLLY_ENGINE", "neural")
POLLY_LANGUAGE = os.getenv("POLLY_LANGUAGE", "en-IN")
TRANSCRIBE_LANG = os.getenv("TRANSCRIBE_LANGUAGE", "en-IN")
CALL_TIMEOUT = int(os.getenv("CALL_TIMEOUT", "30"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8765"))
VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN", "wecare_calling_verify_2026")
LAMBDA_CALLBACK = os.getenv("LAMBDA_CALLBACK_URL", "")
META_TOKEN_SECRET = os.getenv("META_TOKEN_SECRET", "wecare/meta-system-user-token")

# Phone number IDs
PHONE1_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "960395407161423")
PHONE2_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID_WABA2", "997428863451102")


# ─── Load Meta Tokens from Secrets Manager ───────────────────────────

_secrets_cache: dict = {}


def _load_meta_secrets():
    """Load Meta tokens + app secrets from AWS Secrets Manager (cached).
    Same secret structure as the Lambda handler uses."""
    if _secrets_cache:
        return
    try:
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        resp = client.get_secret_value(SecretId=META_TOKEN_SECRET)
        secret = resp.get("SecretString", "")
        data = json.loads(secret)
        _secrets_cache["token1"] = (data.get("access_token") or "").strip()
        _secrets_cache["token2"] = (data.get("access_token_waba2") or data.get("access_token") or "").strip()
        _secrets_cache["app_secret1"] = (data.get("app_secret") or "").strip()
        _secrets_cache["app_secret2"] = (data.get("app_secret_waba2") or "").strip()
        logger.info(
            f"Loaded Meta secrets: token1={len(_secrets_cache['token1'])}chars, "
            f"token2={len(_secrets_cache['token2'])}chars, "
            f"has_app_secrets={bool(_secrets_cache.get('app_secret1'))}"
        )
    except Exception as e:
        logger.error(f"Failed to load Meta secrets from {META_TOKEN_SECRET}: {e}")
        # Fallback to env vars if Secrets Manager fails
        _secrets_cache["token1"] = os.getenv("WHATSAPP_TOKEN", "")
        _secrets_cache["token2"] = os.getenv("WHATSAPP_TOKEN_WABA2", os.getenv("WHATSAPP_TOKEN", ""))
        _secrets_cache["app_secret1"] = os.getenv("WHATSAPP_APP_SECRET", "")
        _secrets_cache["app_secret2"] = os.getenv("WHATSAPP_APP_SECRET_WABA2", "")
        if _secrets_cache["token1"]:
            logger.info("Using fallback env var tokens")
        else:
            logger.error("NO META TOKENS AVAILABLE — bot will not be able to answer calls")


# Load on import
_load_meta_secrets()

# Build WABA configs from loaded secrets
WABA_CONFIGS = {
    PHONE1_ID: {
        "token": _secrets_cache.get("token1", ""),
        "app_secret": _secrets_cache.get("app_secret1", ""),
        "phone_number_id": PHONE1_ID,
    },
    PHONE2_ID: {
        "token": _secrets_cache.get("token2", ""),
        "app_secret": _secrets_cache.get("app_secret2", ""),
        "phone_number_id": PHONE2_ID,
    },
}

SYSTEM_PROMPT = """You are a friendly AI assistant for WeCare Digital, a business communication platform.
You are answering a WhatsApp voice call. Keep responses short (1-2 sentences max) and conversational.
Speak naturally as if on a phone call. If you don't know something, say so briefly and offer to help
the caller connect with a human agent. Respond in the same language the caller uses.
Start by greeting the caller warmly."""


# ─── appsecret_proof + v20.0 ─────────────────────────────────────────
# Pipecat's WhatsAppApi is patched at the source level (patch_pipecat.py)
# to include appsecret_proof in all API calls and use v20.0.
# The WhatsAppClient passes whatsapp_secret → WhatsAppApi stores it as _app_secret.
# No monkey-patching needed — the installed source files are modified directly.
logger.info(f"WhatsAppApi.BASE_URL = {WhatsAppApi.BASE_URL}")

# Track active calls
active_calls: dict[str, PipelineTask] = {}

app = FastAPI(title="WeCare WhatsApp Voice Bot")


# ─── Helpers ─────────────────────────────────────────────────────────

def _get_waba_config(phone_number_id: str) -> dict:
    """Get WABA config for a phone number, fallback to first config."""
    if phone_number_id in WABA_CONFIGS:
        return WABA_CONFIGS[phone_number_id]
    # Fallback to first configured WABA
    return next(iter(WABA_CONFIGS.values()))


def _map_transcribe_language(lang: str) -> Language:
    """Map language string to Pipecat Language enum."""
    lang_map = {
        "en-IN": Language.EN_IN,
        "en-US": Language.EN_US,
        "en-GB": Language.EN_GB,
        "hi-IN": Language.HI,
    }
    return lang_map.get(lang, Language.EN_IN)


async def _notify_lambda(event_type: str, data: dict):
    """Notify the Lambda callback URL about call events (fire-and-forget)."""
    if not LAMBDA_CALLBACK:
        return
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                LAMBDA_CALLBACK,
                json={"source": "pipecat_bot", "event": event_type, **data},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception as e:
        logger.warning(f"Lambda callback failed: {e}")


# ─── Bot Pipeline ────────────────────────────────────────────────────

async def run_bot(
    webrtc_connection,
    phone_number_id: str,
    call_id: str,
    from_number: str,
    from_bsuid: str = '',
    caller_username: str = '',
):
    """Create and run the Pipecat AI pipeline for a single call."""
    logger.info(f"Starting bot for call {call_id} from {from_number} (BSUID: {from_bsuid or 'N/A'}, username: {caller_username or 'N/A'}) on {phone_number_id}")

    # AWS Transcribe — real-time STT
    stt = AWSTranscribeSTTService(
        region=AWS_REGION,
        settings=AWSTranscribeSTTService.Settings(
            language=_map_transcribe_language(TRANSCRIBE_LANG),
        ),
    )

    # AWS Bedrock — LLM (Nova Lite for cost efficiency)
    llm = AWSBedrockLLMService(
        settings=AWSBedrockLLMService.Settings(
            model=BEDROCK_MODEL,
            max_tokens=256,
            temperature=0.7,
        ),
        aws_region=AWS_REGION,
    )

    # AWS Polly — TTS (Kajal neural voice, en-IN)
    tts = AWSPollyTTSService(
        region=AWS_REGION,
        settings=AWSPollyTTSService.Settings(
            voice=POLLY_VOICE,
            engine=POLLY_ENGINE,
            language=_map_transcribe_language(POLLY_LANGUAGE),
        ),
    )

    # WebRTC transport for the WhatsApp call
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    # Build the pipeline: audio in → STT → LLM → TTS → audio out
    pipeline = Pipeline([
        transport.input(),
        stt,
        llm,
        tts,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
        ),
    )

    # Set system prompt + initial greeting
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    context = OpenAILLMContext(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "[Call connected. Greet the caller warmly and briefly.]"},
        ],
    )
    await task.queue_frames([context.create_context_frame()])

    # Track active call
    active_calls[call_id] = task

    # Auto-hangup after CALL_TIMEOUT seconds
    async def _auto_hangup():
        await asyncio.sleep(CALL_TIMEOUT)
        if call_id in active_calls:
            logger.info(f"Auto-hangup: call {call_id} after {CALL_TIMEOUT}s")
            await task.queue_frame(EndFrame())

    asyncio.create_task(_auto_hangup())

    # Run the pipeline
    runner = PipelineRunner()
    try:
        await runner.run(task)
    except Exception as e:
        logger.error(f"Pipeline error for call {call_id}: {e}", exc_info=True)
    finally:
        active_calls.pop(call_id, None)
        logger.info(f"Call {call_id} ended")
        await _notify_lambda("call_ended", {
            "call_id": call_id,
            "from_number": from_number,
            "phone_number_id": phone_number_id,
            "from_bsuid": from_bsuid,
            "caller_username": caller_username,
        })


# ─── WhatsApp Client (handles webhook → WebRTC) ─────────────────────

# We create one WhatsAppClient per WABA phone number
whatsapp_clients: dict[str, WhatsAppClient] = {}


async def _get_or_create_client(phone_number_id: str, session: aiohttp.ClientSession) -> WhatsAppClient:
    """Get or create a WhatsAppClient for the given phone number."""
    if phone_number_id not in whatsapp_clients:
        config = _get_waba_config(phone_number_id)
        client = WhatsAppClient(
            whatsapp_token=config["token"],
            phone_number_id=config["phone_number_id"],
            session=session,
            whatsapp_secret=config["app_secret"] or None,
        )
        whatsapp_clients[phone_number_id] = client
        logger.info(f"Created WhatsAppClient for phone {phone_number_id}")
    return whatsapp_clients[phone_number_id]


# Global aiohttp session
_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


# ─── FastAPI Routes ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "active_calls": len(active_calls),
        "waba_phones": list(WABA_CONFIGS.keys()),
    })


@app.get("/whatsapp")
async def whatsapp_verify(request: Request):
    """Meta webhook verification (hub.challenge)."""
    params = dict(request.query_params)
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info(f"Webhook verified, challenge: {challenge}")
        return PlainTextResponse(challenge)

    logger.warning(f"Webhook verification failed: mode={mode}")
    return JSONResponse({"error": "Verification failed"}, status_code=403)


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp call webhook events from Meta.
    Delegates to WhatsAppClient which handles SDP negotiation internally."""
    body = await request.json()
    raw_body = await request.body()
    sha256_sig = request.headers.get("X-Hub-Signature-256", "").replace("sha256=", "")
    logger.info(f"Webhook received: {json.dumps(body)[:1000]}")

    obj = body.get("object", "")
    if obj != "whatsapp_business_account":
        return JSONResponse({"status": "ignored"})

    # Determine phone_number_id from the webhook payload
    phone_number_id = ""
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "calls":
                phone_number_id = change.get("value", {}).get("metadata", {}).get("phone_number_id", "")
                break

    session = await _get_session()
    client = await _get_or_create_client(phone_number_id or PHONE1_ID, session)

    # Parse the webhook body into Pipecat's model
    try:
        webhook_request = WhatsAppWebhookRequest(**body)
    except Exception as e:
        logger.error(f"Failed to parse webhook: {e}")
        return JSONResponse({"status": "parse_error"})

    # connection_callback is called when a new call connects
    async def on_new_connection(connection):
        """Called by WhatsAppClient when WebRTC connection is established."""
        # Extract call info from the webhook body
        call_id = ""
        from_number = ""
        from_bsuid = ""
        caller_username = ""
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "calls":
                    value = change.get("value", {})
                    calls = value.get("calls", [])
                    contacts = value.get("contacts", [])
                    if calls:
                        call_id = calls[0].get("id", "")
                        from_number = calls[0].get("from", "")
                        from_bsuid = calls[0].get("from_user_id", "")
                    if contacts:
                        caller_username = contacts[0].get("profile", {}).get("username", "")
                        if not from_bsuid:
                            from_bsuid = contacts[0].get("user_id", "")

        logger.info(f"WebRTC connected for call {call_id} from {from_number} (BSUID: {from_bsuid or 'N/A'})")
        asyncio.create_task(run_bot(
            webrtc_connection=connection,
            phone_number_id=phone_number_id,
            call_id=call_id,
            from_number=from_number,
            from_bsuid=from_bsuid,
            caller_username=caller_username,
        ))
        await _notify_lambda("call_answered", {
            "call_id": call_id,
            "from_number": from_number,
            "phone_number_id": phone_number_id,
            "answered_by": "pipecat_bot",
            "from_bsuid": from_bsuid,
            "caller_username": caller_username,
        })

    # Let WhatsAppClient handle everything (SDP negotiation, pre_accept, accept)
    handled = await client.handle_webhook_request(
        request=webhook_request,
        connection_callback=on_new_connection,
        raw_body=raw_body if sha256_sig else None,
        sha256_signature=sha256_sig or None,
    )

    if not handled:
        logger.warning("WhatsAppClient did not handle the webhook")

    return JSONResponse({"status": "processed"})


@app.post("/call")
async def lambda_forwarded_call(request: Request):
    """
    Handle call events forwarded from the Lambda handler.
    Lambda sends: { call_id, phone_number_id, from_number, sdp_offer, event_type, caller_name }
    We reconstruct a WhatsApp webhook payload and pass it to WhatsAppClient.
    """
    body = await request.json()
    call_id = body.get("call_id", "")
    phone_number_id = body.get("phone_number_id", "")
    from_number = body.get("from_number", "")
    event_type = body.get("event_type", "connect")
    sdp_offer = body.get("sdp_offer", "")
    from_bsuid = body.get("from_bsuid", "")
    caller_username = body.get("caller_username", "")

    logger.info(f"Lambda forwarded call: {call_id} from {from_number} (BSUID: {from_bsuid or 'N/A'}), event={event_type}, has_sdp={bool(sdp_offer)}")

    if event_type == "connect":
        session = await _get_session()
        client = await _get_or_create_client(phone_number_id, session)
        config = _get_waba_config(phone_number_id)

        # Reconstruct a full WhatsApp webhook payload matching Pipecat's model
        import time as _time
        webhook_body = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "forwarded",
                "changes": [{
                    "field": "calls",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": "",
                        },
                        "contacts": [{
                            "wa_id": from_number,
                            "user_id": from_bsuid,
                            "profile": {
                                "name": body.get("caller_name", ""),
                                "username": caller_username,
                            },
                        }],
                        "calls": [{
                            "id": call_id,
                            "from": from_number,
                            "from_user_id": from_bsuid,
                            "to": phone_number_id,
                            "direction": "USER_INITIATED",
                            "event": "connect",
                            "timestamp": str(int(_time.time())),
                            "session": {
                                "sdp": sdp_offer,
                                "sdp_type": "offer",
                            },
                        }],
                    },
                }],
            }],
        }

        try:
            webhook_request = WhatsAppWebhookRequest(**webhook_body)
        except Exception as e:
            logger.error(f"Failed to construct webhook request: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

        # Self-sign the payload so WhatsAppClient's signature validation passes
        # (Lambda-forwarded calls don't have Meta's X-Hub-Signature-256)
        raw_body = json.dumps(webhook_body).encode("utf-8")
        app_secret = config.get("app_secret", "")
        if app_secret:
            sig = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        else:
            sig = ""

        bot_started = False

        async def on_new_connection(connection):
            nonlocal bot_started
            bot_started = True
            logger.info(f"WebRTC connected for forwarded call {call_id}")
            asyncio.create_task(run_bot(
                webrtc_connection=connection,
                phone_number_id=phone_number_id,
                call_id=call_id,
                from_number=from_number,
                from_bsuid=from_bsuid,
                caller_username=caller_username,
            ))

        handled = await client.handle_webhook_request(
            request=webhook_request,
            connection_callback=on_new_connection,
            raw_body=raw_body,
            sha256_signature=f"sha256={sig}",
        )

        if handled and bot_started:
            return JSONResponse({"success": True, "call_id": call_id, "status": "bot_started"})
        elif handled:
            # Webhook was handled but connection not yet established (async)
            return JSONResponse({"success": True, "call_id": call_id, "status": "connecting"})
        else:
            return JSONResponse({"success": False, "error": "WhatsApp client did not handle the call"}, status_code=500)

    elif event_type == "terminate":
        task = active_calls.get(call_id)
        if task:
            await task.queue_frame(EndFrame())
        return JSONResponse({"success": True, "call_id": call_id, "status": "terminated"})

    return JSONResponse({"success": False, "error": f"Unknown event: {event_type}"})


@app.on_event("shutdown")
async def shutdown():
    """Clean up on server shutdown."""
    logger.info("Shutting down — terminating active calls")
    for client in whatsapp_clients.values():
        try:
            await client.terminate_all_calls()
        except Exception as e:
            logger.warning(f"Error terminating calls: {e}")
    global _session
    if _session and not _session.closed:
        await _session.close()


# ─── Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting WeCare WhatsApp Voice Bot on {HOST}:{PORT}")
    logger.info(f"WABA phones: {list(WABA_CONFIGS.keys())}")
    logger.info(f"AI: Transcribe({TRANSCRIBE_LANG}) → Bedrock({BEDROCK_MODEL}) → Polly({POLLY_VOICE})")
    logger.info(f"Call timeout: {CALL_TIMEOUT}s")
    uvicorn.run(app, host=HOST, port=PORT)
