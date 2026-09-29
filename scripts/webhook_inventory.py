#!/usr/bin/env python3
"""Inventory every inbound webhook this platform expects, and audit Razorpay's live config.

Writes a non-secret report to docs/WEBHOOK-INVENTORY.md and prints a summary.
Credentials are read from Secrets Manager in memory for the read-only Razorpay
query; nothing is printed and nothing is written that contains a value.

    python scripts/webhook_inventory.py            # report, always exits 0
    python scripts/webhook_inventory.py --gate     # exit 1 on a violated expectation

`--gate` is opt-in because this script also performs a live provider query that can
fail for reasons unrelated to the endpoint table, and a reporting run should not go
red on Razorpay being slow. See the comment above ENDPOINTS for what an expectation
is and why three of the ten rows expect *absence*.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import boto3

GATE = "--gate" in sys.argv

REGION = "us-east-1"
API_ID = "zllr9lrg7j"
BASE = "https://wecare.digital/api"
ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "amplify/functions/payments/razorpay-webhook/handler.py"


# Names the handler mentions that Razorpay does NOT accept as event
# subscriptions. Verified 2026-09-19 by a live PUT, which returned
# BAD_REQUEST_ERROR "Invalid event name/names".
NOT_REAL_EVENTS = {
    # A dict-key lookup at handler.py:1386, not an event type. The real events
    # fund_account.validation.completed / .failed are handled and subscribed.
    "fund_account.validation",
    # A live `elif event_type == 'payment.pending'` branch at handler.py:120, but
    # Razorpay has no such event, so that branch is unreachable. See GAP.
    "payment.pending",
}


def razorpay_events() -> list[str]:
    """Event names the handler dispatches on AND Razorpay actually accepts."""
    src = HANDLER.read_text()
    pat = (r"'((?:payment|order|subscription|invoice|settlement|refund|payment_link"
           r"|virtual_account|fund_account|transfer|account|qr_code)\.[a-z_.]+)'")
    return sorted(set(re.findall(pat, src)) - NOT_REAL_EVENTS)


def razorpay_live_webhooks() -> tuple[list[dict], str]:
    sm = boto3.client("secretsmanager", region_name=REGION)
    d = json.loads(sm.get_secret_value(SecretId="wecare/razorpay/api")["SecretString"])
    token = base64.b64encode(f"{d['key_id']}:{d['key_secret']}".encode()).decode()
    for path in ("/v1/webhooks", f"/v1/accounts/{d.get('account_id','')}/webhooks"):
        req = urllib.request.Request(
            f"https://api.razorpay.com{path}?count=100",
            headers={"Authorization": f"Basic {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
            return body.get("items", body.get("entity") and [body] or []), f"OK via {path}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code} on {path}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__} on {path}"
    return [], last


def gateway_routes() -> list[str]:
    api = boto3.client("apigatewayv2", region_name=REGION)
    items = api.get_routes(ApiId=API_ID, MaxResults="1000")["Items"]
    return sorted(r["RouteKey"] for r in items)


# Provider -> (endpoint, method, auth model, consuming Lambda, expectation)
#
# THE FIFTH FIELD, added 2026-09-29, and why it is not decoration.
#
# This table used to hold ten rows and the report marked any absent route **MISSING**.
# Three of the ten had been deliberately retired, so the check emitted three permanent
# failures that were all correct behaviour:
#
#   /webhook/sinch-dlr    Sinch SMS DLR. Sinch is approved for India RCS ONLY; its SMS
#                         surface is a prohibited provider. Routes deleted 2026-09-21 and
#                         API 79g3bbufdh deleted entirely. docs/prohibited-provider-retirement.md
#   /sms-in/airtel        Airtel messaging, prohibited provider. Lambda and routes gone.
#   /voice-cdr-webhook    Deleted 2026-09-20 because it carried an UNAUTHENTICATED
#                         `DELETE /voice-cdr-webhook/clear-logs`. That hole is what caused
#                         scripts/audit_route_auth.py to be written at all.
#                         docs/deleted-routes-unauthenticated-cdr-20260920-0822.json
#
# A check whose output is three standing MISSINGs teaches its reader to skim past the word,
# which is precisely how a real missing route would then go unnoticed. Same defect as the
# stale-dimension alarms that were permanently green, and the same fix: assert the state
# that is actually intended.
#
# So `expect` is `"live"` or a retirement reason, and the gate is now two-sided - a route
# that should be live and is absent fails, and a RETIRED route that has come back fails
# too. The second half is the one worth having: an IaC deploy or a well-meaning
# re-provision is exactly how a prohibited-provider endpoint returns, and nothing else here
# would catch it.
ENDPOINTS = [
    ("Razorpay", "/razorpay-webhook", "POST",
     "HMAC SHA256 X-Razorpay-Signature vs webhook_secret", "wecare-razorpay-webhook", "live"),
    ("Meta / WhatsApp Cloud", "/whatsapp/inbound", "POST",
     "X-Hub-Signature-256 vs app_secret + verify_token on GET", "wecare-inbound-whatsapp", "live"),
    ("Meta / WhatsApp (business)", "/wa-business/webhooks", "POST",
     "X-Hub-Signature-256", "wecare-whatsapp-business-api", "live"),
    ("Plivo (voice IVR)", "/plivo/answer", "POST",
     "optional ?token= shared secret (PLIVO_ANSWER_TOKEN); Plivo does not sign answer_url",
     "wecare-plivo-answer", "live"),
    ("Sinch (SMS DLR)", "/webhook/sinch-dlr", "POST", "provider callback", "wecare-sinch-dlr",
     "RETIRED 2026-09-21 — Sinch SMS is a prohibited provider (RCS India only). "
     "Routes and API 79g3bbufdh deleted; see docs/prohibited-provider-retirement.md"),
    ("Sinch (RCS)", "/webhook/sinch-rcs", "POST", "provider callback", "wecare-rcs-dlr", "live"),
    ("Airtel IQ (SMS inbound)", "/sms-in/airtel", "POST", "provider callback",
     "wecare-sms-in-airtel",
     "RETIRED — Airtel messaging is a prohibited provider; Lambda and routes deleted"),
    ("Airtel IQ (voice C2C)", "/voice-in/c2c", "POST", "provider callback", "wecare-voice-in-c2c", "live"),
    ("Airtel IQ (voice OBD)", "/voice-in/obd", "POST", "provider callback", "wecare-voice-in-obd", "live"),
    ("Voice CDR", "/voice-cdr-webhook", "POST", "provider callback", "wecare-voice-cdr-read",
     "RETIRED 2026-09-20 — carried an unauthenticated DELETE .../clear-logs; see "
     "docs/deleted-routes-unauthenticated-cdr-20260920-0822.json"),
]


def main() -> int:
    events = razorpay_events()
    routes = set(gateway_routes())
    live, status = razorpay_live_webhooks()

    print(f"Razorpay events handled in code : {len(events)}")
    print(f"Razorpay live webhook query     : {status}")
    print(f"Razorpay webhooks configured    : {len(live)}")

    configured_urls = {w.get("url", "") for w in live}
    configured_events: set[str] = set()
    for w in live:
        ev = w.get("events")
        if isinstance(ev, dict):
            configured_events |= {k for k, v in ev.items() if v}
        elif isinstance(ev, list):
            configured_events |= set(ev)

    missing = [e for e in events if e not in configured_events]
    extra = sorted(configured_events - set(events))

    lines: list[str] = []
    add = lines.append
    add("# Webhook inventory\n")
    add("Generated by `scripts/webhook_inventory.py`. No credential values here.\n")
    add(f"- API Gateway: `{API_ID}` · base `{BASE}`")
    add(f"- Razorpay live query: {status}\n")

    add("## Endpoints to configure at each provider\n")
    add("A retired endpoint being absent is the intended state, not a gap — the fourth")
    add("column says which is which, and `scripts/webhook_inventory.py --gate` fails on a")
    add("live route that is missing **and** on a retired route that has reappeared.\n")
    add("| Provider | URL | Method | Route state | Auth | Lambda |")
    add("|---|---|---|---|---|---|")
    for prov, path, method, auth, fn, expect in ENDPOINTS:
        present = f"{method} {path}" in routes
        if expect == "live":
            state = "YES" if present else "**MISSING**"
        else:
            state = "**RESURRECTED — should not exist**" if present else "retired, absent as intended"
        add(f"| {prov} | `{BASE}{path}` | {method} | {state} | {auth} | `{fn}` |")

    retired = [(p, e) for _pr, p, _m, _a, _f, e in ENDPOINTS if e != "live"]
    if retired:
        add(f"\n### Retired endpoints ({len(retired)}) — absence is correct\n")
        for path, why in retired:
            add(f"- `{path}` — {why}")
        add("")

    add("\n## Razorpay — current state\n")
    if live:
        add("| # | URL | Status | Events |")
        add("|---|---|---|---|")
        for i, w in enumerate(live, 1):
            ev = w.get("events")
            n = len([k for k, v in ev.items() if v]) if isinstance(ev, dict) else len(ev or [])
            add(f"| {i} | `{w.get('url','')}` | {w.get('status','')} | {n} |")
    else:
        add("No webhooks returned by the API. Either none are configured, or the\n"
            "webhook endpoints are not exposed to this key type (Razorpay restricts\n"
            "`/v1/webhooks` on some account types) - in that case configure in the\n"
            "dashboard: **Settings → Webhooks → Add New Webhook**.\n")

    add(f"\n### Events the handler processes ({len(events)})\n")
    add("Subscribe exactly these. Anything else is ignored by the handler.\n")
    add("```")
    for e in events:
        add(e)
    add("```")

    if configured_events:
        add(f"\n### Not yet subscribed ({len(missing)})\n")
        add("```")
        for e in missing:
            add(e)
        add("```")
        if extra:
            add(f"\n### Subscribed but NOT handled ({len(extra)}) — harmless, just noise\n")
            add("```")
            for e in extra:
                add(e)
            add("```")

    add("\n## Razorpay setup, manual\n")
    add(f"1. Dashboard → **Settings → Webhooks → Add New Webhook**")
    add(f"2. Webhook URL: `{BASE}/razorpay-webhook`")
    add("3. Secret: must match the `webhook_secret` field in Secrets Manager secret\n"
        "   `wecare/razorpay-webhook`. If you change one, change both, or signature\n"
        "   verification fails and every payment webhook is rejected.")
    add("4. Select the events listed above.")
    add("5. Save, then use **Send Test Webhook** and confirm a 200.\n")

    add("## Razorpay setup, via API\n")
    add("`POST https://api.razorpay.com/v1/webhooks` with Basic auth "
        "(`key_id:key_secret`). Never put those on a command line - read them from\n"
        "Secrets Manager in a script. Body shape:\n")
    add("```json")
    add(json.dumps({
        "url": f"{BASE}/razorpay-webhook",
        "alert_email": "admin@wecare.digital",
        "secret": "<value of wecare/razorpay-webhook:webhook_secret>",
        "events": {e: 1 for e in events},
    }, indent=2))
    add("```")

    out = ROOT / "docs" / "WEBHOOK-INVENTORY.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out} ({out.stat().st_size} bytes)")

    print("\nendpoint route check:")
    failures: list[str] = []
    for prov, path, method, _a, fn, expect in ENDPOINTS:
        present = f"{method} {path}" in routes
        if expect == "live":
            mark = "ok      " if present else "MISSING "
            if not present:
                failures.append(f"{method} {path} should be live but no route exists "
                                f"(target {fn})")
        elif present:
            mark = "RETURNED"
            failures.append(f"{method} {path} is RETIRED but a route exists again — "
                            f"{expect}")
        else:
            mark = "retired "
        print(f"  {mark} {method:5s} {path:28s} -> {fn}")

    print(f"\n{len(ENDPOINTS)} endpoint(s): "
          f"{sum(1 for e in ENDPOINTS if e[5] == 'live')} expected live, "
          f"{sum(1 for e in ENDPOINTS if e[5] != 'live')} retired")
    if failures:
        print(f"\nFAIL — {len(failures)} endpoint expectation(s) violated:")
        for f in failures:
            print(f"  {f}")
        return 1 if GATE else 0
    print("WEBHOOK ENDPOINT EXPECTATIONS OK — every live route exists and no retired "
          "route has come back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
