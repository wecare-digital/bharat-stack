#!/usr/bin/env python3
"""Read and repoint the Meta app webhook callback URL through the Graph API.

WHY THIS EXISTS
---------------
The WhatsApp callback URL is app-level configuration (`/{app-id}/subscriptions`),
and nothing in this repository wrote it before — the only subscription code here is
`subscribed_apps`, which is a per-WABA *field* subscription and a different thing
entirely. So repointing the callback meant either the Meta console or this.

CREDENTIALS
-----------
`app_secret` is read from Secrets Manager `wecare/meta-system-user-token` in memory,
exactly as the Lambdas already do via `_load_meta_secrets()`. It is never passed on a
command line, never printed, and never written to a snapshot. The app access token is
built as `{app_id}|{app_secret}` in memory and only ever sent to graph.facebook.com.

`GET /{app-id}/subscriptions` and `POST /{app-id}/subscriptions` both require an APP
access token specifically — a system-user token is not accepted on this edge, which
is why this does not reuse the handlers' `_graph_api`.

WHY A FAILED CHANGE IS SAFE
---------------------------
Meta verifies the new URL before it accepts it: it issues `GET <callback_url>` with
`hub.mode`, `hub.verify_token` and `hub.challenge`, and requires the challenge echoed
back. If verification fails the POST returns an error and the **existing callback is
left in place**. So the failure mode is "the change did not apply", not "inbound
WhatsApp is silently broken". That property is the reason this is safe to automate at
all, and it is why the verify token must be unchanged on the new URL.

`hub.challenge` is echoed only when `hub.verify_token` matches the stored
`waba_t_verify_token`. Both the old and new URL are served by the same Lambda reading
the same secret, so a host change cannot alter that outcome.

Usage:
    python scripts/meta_webhook_control_plane.py                  # read, change nothing
    python scripts/meta_webhook_control_plane.py --plan <url>     # show the diff
    python scripts/meta_webhook_control_plane.py --apply <url>    # write, then read back

Exit 0 on success. Non-zero names what failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import boto3

REGION = "us-east-1"
SECRET_ID = os.environ.get("META_TOKEN_SECRET", "wecare/meta-system-user-token")
APP_ID = os.environ.get("META_APP_ID", "2238810740192680")
GRAPH = "https://graph.facebook.com/v23.0"
OBJECT = "whatsapp_business_account"
TIMEOUT = 30


def _app_access_token() -> str:
    """`{app_id}|{app_secret}`, assembled in memory. Never printed, never in argv."""
    sm = boto3.client("secretsmanager", region_name=REGION)
    raw = sm.get_secret_value(SecretId=SECRET_ID)["SecretString"]
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise SystemExit("secret is not JSON; cannot locate app_secret")
    # An app access token is `{app_id}|{app_secret}` and the pair must match. Pairing
    # app 1's secret with app 2's id returns OAuthException 190 "Invalid OAuth access
    # token signature", which reads like an expired token but is really a mismatch.
    # The secret carries two, so the field is selectable.
    field = os.environ.get("META_APP_SECRET_FIELD", "app_secret")
    secret = (data.get(field) or "").strip()
    if not secret:
        raise SystemExit(f"no {field} in {SECRET_ID}")
    return f"{APP_ID}|{secret}"


def _call(method: str, path: str, token: str, payload: dict | None = None):
    url = f"{GRAPH}/{path}"
    body = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode({"access_token": token})
    else:
        body = urllib.parse.urlencode({**(payload or {}), "access_token": token}).encode()
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode() or "{}")
        except Exception:  # noqa: BLE001
            return exc.code, {}


def read_subscriptions(token: str) -> list[dict]:
    status, body = _call("GET", f"{APP_ID}/subscriptions", token)
    if status != 200:
        raise SystemExit(f"GET subscriptions -> {status} {json.dumps(body)[:400]}")
    return body.get("data", [])


def _wa(subs: list[dict]) -> dict | None:
    for s in subs:
        if s.get("object") == OBJECT:
            return s
    return None


def report(subs: list[dict]) -> None:
    if not subs:
        print("  no subscriptions returned")
        return
    for s in subs:
        print(f"  object       : {s.get('object')}")
        print(f"  callback_url : {s.get('callback_url')}")
        print(f"  active       : {s.get('active')}")
        fields = s.get("fields") or []
        names = sorted(f.get("name") for f in fields if isinstance(f, dict) and f.get("name"))
        print(f"  fields ({len(names)}) : {', '.join(names) if names else '(none reported)'}")
        print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--plan", metavar="URL", help="show the diff without writing")
    g.add_argument("--apply", metavar="URL", help="write the callback URL, then read back")
    args = ap.parse_args(argv)

    token = _app_access_token()
    print(f"app {APP_ID}  secret {SECRET_ID}  (value never printed)\n")

    subs = read_subscriptions(token)
    print("CURRENT:")
    report(subs)

    target = args.plan or args.apply
    if not target:
        print("read-only; pass --plan or --apply <url> to change anything")
        return 0

    # EVERY object on the app, not just whatsapp_business_account. App 2238810740192680
    # carries two — `whatsapp_business_account` (32 fields) and `catalog` (2) — and both
    # point at the same callback. Repointing only the first would leave catalog webhooks
    # aimed at a host about to be deleted, which is the sort of thing that surfaces weeks
    # later as "product feed updates stopped arriving".
    todo = [s for s in subs if s.get("callback_url") != target]
    if not todo:
        print("\nevery subscription already points at the target; nothing to do")
        return 0

    print("PLAN:")
    for s in todo:
        fields = sorted(f.get("name") for f in (s.get("fields") or [])
                        if isinstance(f, dict) and f.get("name"))
        print(f"  {s.get('object')}: {s.get('callback_url')}")
        print(f"      -> {target}   restating {len(fields)} field(s)")
    if not args.apply:
        print("\nplan only; re-run with --apply to write")
        return 0

    # The verify token must be the one the endpoint already expects. It is read from
    # the same secret the Lambda reads, so the old and new URL behave identically.
    sm = boto3.client("secretsmanager", region_name=REGION)
    data = json.loads(sm.get_secret_value(SecretId=SECRET_ID)["SecretString"])
    verify_token = (data.get("waba_t_verify_token") or "").strip()
    if not verify_token:
        print(f"FAIL: no waba_t_verify_token in {SECRET_ID}; Meta's verification would "
              f"fail and the change would be rejected")
        return 1

    # Fields are restated per object because this edge replaces the subscription.
    before_fields = {}
    for s in todo:
        obj = s.get("object")
        fields = sorted(f.get("name") for f in (s.get("fields") or [])
                        if isinstance(f, dict) and f.get("name"))
        before_fields[obj] = set(fields)
        payload = {
            "object": obj,
            "callback_url": target,
            "verify_token": verify_token,
            "fields": ",".join(fields),
        }
        status, body = _call("POST", f"{APP_ID}/subscriptions", token, payload)
        print(f"\n  POST {obj} -> {status} {json.dumps(body)[:220]}")
        if status != 200 or not body.get("success", True):
            print(f"\nFAIL on '{obj}': Meta rejected the change. The previous callback "
                  f"URL is still in place for it — this edge verifies the new URL before "
                  f"switching, so a rejection leaves inbound traffic untouched.")
            return 1

    after = read_subscriptions(token)
    print("\nAFTER:")
    report(after)

    problems = []
    for s in after:
        obj = s.get("object")
        if s.get("callback_url") != target:
            problems.append(f"{obj} callback is {s.get('callback_url')}, expected {target}")
        got = {f.get("name") for f in (s.get("fields") or [])
               if isinstance(f, dict) and f.get("name")}
        lost = before_fields.get(obj, set()) - got
        if lost:
            problems.append(f"{obj} lost fields {sorted(lost)}")
        if not s.get("active"):
            problems.append(f"{obj} is no longer active")
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    print(f"OK: {len(after)} subscription(s) on {target}, all fields intact, all active")
    olds = sorted({s.get("callback_url") for s in todo})
    print(f"Rollback: python {sys.argv[0]} --apply {olds[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
