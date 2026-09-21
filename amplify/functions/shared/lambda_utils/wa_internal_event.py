"""The internal contract between the WhatsApp ingress and the inbound worker.

What was here before
--------------------
`wecare-whatsapp-calling` verifies Meta's signature on `/whatsapp`, then forwards
non-call events to `wecare-inbound-whatsapp` by `lambda_client.invoke`. It wrapped
them in a *synthetic SNS envelope*:

    {"Records": [{"Sns": {"Message": "{\\"whatsAppWebhookEntry\\": \\"{...}\\"}"}}]}

That shape is a fossil. It dates from an architecture where Meta delivered through
AWS End User Messaging Social into an SNS topic, and it no longer describes
anything: there is no SNS topic subscription to this function in
`amplify/backend.ts`, in `amplify/backend-resources.ts`, or in the live
event-source mappings - the only SNS references left in IaC are CloudWatch alarm
topics. The AWS account has no linked WABA.

It cost three things:

  * The webhook entry was **double JSON-encoded** - a string inside a string
    inside a dict - so every consumer paid two `json.loads` and any logging of the
    envelope was unreadable.
  * It lied about the source. A reader seeing `Records[].Sns` reasonably concludes
    a topic exists and looks for a subscription that was never there. Two
    documents in `docs/meta-whatsapp/` still describe that ingress.
  * It made the boundary untyped. Nothing declared which fields the worker needs,
    so `dlq-replay` stores an `originalRecord` and invokes with it directly,
    never rebuilding this envelope - meaning replay of an inbound failure does
    not reproduce the shape the worker parses.

The contract
------------
`build()` emits a flat, self-describing event. `parse()` accepts it **and** the
legacy envelope, and returns a uniform list of work items either way.

Accepting both is not indecision. The producer and the consumer are separate
Lambdas deployed separately, and the invoke is asynchronous: at the moment the new
producer ships there can be in-flight events carrying the old shape, and
`dlq-replay` may hold stored payloads in it for as long as its DLQ retention. The
legacy arm is therefore load-bearing until both have drained, and `parse()` reports
which shape it saw so that can be measured rather than assumed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

SOURCE_META_DIRECT = "meta-direct"
CONTRACT_VERSION = 1


def build(*, entry: Dict[str, Any], waba_id: str,
          meta_phone_number_ids: List[str], request_id: str) -> Dict[str, Any]:
    """The typed event the ingress sends to the inbound worker.

    `entry` is the Meta webhook entry as a dict - not a JSON string. It was
    double-encoded in the legacy shape for no reason other than SNS carrying a
    string body.
    """
    return {
        "source": SOURCE_META_DIRECT,
        "version": CONTRACT_VERSION,
        "wabaId": waba_id,
        "metaPhoneNumberIds": list(meta_phone_number_ids or []),
        "requestId": request_id,
        "entry": entry,
    }


def _from_legacy_sns(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Unwrap the synthetic SNS envelope. Tolerates the double encoding."""
    items: List[Dict[str, Any]] = []
    for record in event.get("Records") or []:
        raw = ((record or {}).get("Sns") or {}).get("Message") or "{}"
        try:
            message = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        ctx = message.get("context") or {}
        entry_raw = message.get("whatsAppWebhookEntry") or "{}"
        try:
            entry = json.loads(entry_raw) if isinstance(entry_raw, str) else (entry_raw or {})
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        waba_ids = ctx.get("MetaWabaIds") or []
        items.append({
            "shape": "legacy-sns",
            "entry": entry,
            "waba_ids": list(waba_ids),
            "waba_id": waba_ids[0] if waba_ids else "",
            "phone_number_ids": list(ctx.get("MetaPhoneNumberIds") or []),
            "message_id": message.get("messageId") or "",
        })
    return items


def _from_typed(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    entry = event.get("entry") or {}
    if isinstance(entry, str):
        # Defensive: a producer that stringified it anyway.
        try:
            entry = json.loads(entry)
        except (json.JSONDecodeError, TypeError, ValueError):
            entry = {}
    waba_id = event.get("wabaId") or ""
    return [{
        "shape": "typed",
        "entry": entry,
        "waba_ids": [waba_id] if waba_id else [],
        "waba_id": waba_id,
        "phone_number_ids": list(event.get("metaPhoneNumberIds") or []),
        "message_id": event.get("requestId") or "",
    }]


def parse(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize either shape into a list of work items.

    Each item carries `entry` (a dict), `waba_ids`, `waba_id`,
    `phone_number_ids`, `message_id`, and `shape` so the caller can log which
    form arrived and know when the legacy arm has stopped being used.

    Returns an empty list for anything unrecognised; the caller decides whether
    that is worth an error. It is never an exception, because this sits at the top
    of an async worker where raising would send a poison event to the DLQ on every
    retry.
    """
    if not isinstance(event, dict):
        return []
    if event.get("source") == SOURCE_META_DIRECT or "entry" in event:
        return _from_typed(event)
    if event.get("Records"):
        return _from_legacy_sns(event)
    return []


def is_internal_event(event: Dict[str, Any]) -> bool:
    """True when this looks like either internal shape rather than an HTTP request."""
    return bool(parse(event))
