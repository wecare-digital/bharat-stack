"""
Idempotency utilities (webhook dedupe + admin action keys).

Webhook dedupe is backed by the existing WebhookDedup model via lambda_utils.webhook_dedup.
"""
import hashlib
import json
from typing import Any, Dict, Optional

from lambda_utils.webhook_dedup import claim_event, is_duplicate  # re-export


def make_webhook_dedupe_key(payload: Dict[str, Any]) -> Optional[str]:
    """Derive a stable dedupe key from a webhook payload.
    Prefers a message/status/call id; falls back to a hash of the change value."""
    try:
        entry = (payload.get('entry') or [{}])[0]
        change = (entry.get('changes') or [{}])[0]
        value = change.get('value', {}) or {}
        msgs = value.get('messages') or []
        if msgs and msgs[0].get('id'):
            return f"msg:{msgs[0]['id']}"
        statuses = value.get('statuses') or []
        if statuses and statuses[0].get('id'):
            st = statuses[0]
            return f"status:{st['id']}:{st.get('status', '')}"
        calls = value.get('calls') or []
        if calls and calls[0].get('id'):
            return f"call:{calls[0]['id']}:{calls[0].get('event', '')}"
        # Fallback: hash the value block
        digest = hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:32]
        return f"hash:{digest}"
    except Exception:
        return None


def check_and_put_dedupe(event_id: Optional[str], ttl: int = 7 * 24 * 60 * 60, source: str = 'whatsapp') -> bool:
    """Conditional-write dedupe. Returns True if this is a NEW event (process it),
    False if duplicate (skip). `ttl` is seconds."""
    return claim_event(event_id, source=source, ttl_days=max(1, ttl // (24 * 60 * 60)))


def make_admin_idempotency_key(actor: str, action: str, body_hash: str) -> str:
    """Stable key for admin write idempotency."""
    return f"admin:{actor}:{action}:{body_hash}"


def body_hash(body: Any) -> str:
    raw = body if isinstance(body, str) else json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def safe_replay_key(original_event_id: str, replay_id: str) -> str:
    """Key that lets a deliberate replay through while still deduping accidental repeats."""
    return f"replay:{original_event_id}:{replay_id}"


__all__ = [
    'make_webhook_dedupe_key', 'check_and_put_dedupe', 'make_admin_idempotency_key',
    'safe_replay_key', 'body_hash', 'claim_event', 'is_duplicate',
]
