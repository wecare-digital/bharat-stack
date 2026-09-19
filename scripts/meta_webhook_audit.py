#!/usr/bin/env python3
"""Audit Meta/WhatsApp webhook configuration: app-level callback + per-WABA subscriptions.

Answers: why are there two Meta endpoints, and can they be consolidated?
Reads the token from Secrets Manager in memory. Prints no secret value.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import boto3

REGION = "us-east-1"
GRAPH = "https://graph.facebook.com/v25.0"

WABAS = {
    "WABA1": "2094615664435155",
    "WABA2 / WABA-T": "2513394156072604",
    "WABA3": "1055232054343117",
}


def creds() -> tuple[str, str, str]:
    sm = boto3.client("secretsmanager", region_name=REGION)
    d = json.loads(sm.get_secret_value(SecretId="wecare/meta-system-user-token")["SecretString"])
    return d.get("access_token", ""), d.get("app_id", ""), d.get("app_secret", "")


def get(path: str, token: str, params: dict | None = None, secret: str = "") -> dict:
    q = dict(params or {})
    q["access_token"] = token
    if secret:
        import hashlib, hmac
        q["appsecret_proof"] = hmac.new(secret.encode(), token.encode(),
                                        hashlib.sha256).hexdigest()
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(q)}"
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        return {"_error": f"HTTP {exc.code}", "_detail": body}
    except Exception as exc:  # noqa: BLE001
        return {"_error": type(exc).__name__}


def main() -> int:
    token, app_id, secret = creds()
    if not token:
        print("no access_token in wecare/meta-system-user-token")
        return 1

    print(f"app_id: {app_id}\n")

    print("=== APP-LEVEL webhook subscription (this is where the callback URL lives) ===")
    subs = get(f"{app_id}/subscriptions", token, secret=secret)
    if "_error" in subs:
        print(f"  {subs['_error']}  {subs.get('_detail','')[:160]}")
    else:
        for s in subs.get("data", []):
            obj = s.get("object")
            url = s.get("callback_url", "")
            active = s.get("active")
            fields = s.get("fields", [])
            names = sorted(f.get("name", "") for f in fields) if fields and isinstance(fields[0], dict) else sorted(fields)
            print(f"  object={obj}  active={active}")
            print(f"    callback_url : {url}")
            print(f"    fields ({len(names)}): {', '.join(names[:14])}"
                  + (" …" if len(names) > 14 else ""))

    print("\n=== PER-WABA app subscription (which app receives that WABA's events) ===")
    for label, waba in WABAS.items():
        r = get(f"{waba}/subscribed_apps", token, secret=secret)
        if "_error" in r:
            print(f"  {label:16s} {waba}  {r['_error']}")
            continue
        apps = r.get("data", [])
        if not apps:
            print(f"  {label:16s} {waba}  NO APP SUBSCRIBED")
        for a in apps:
            w = a.get("whatsapp_business_api_data", {})
            print(f"  {label:16s} {waba}  app={w.get('id')} ({w.get('name','')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
