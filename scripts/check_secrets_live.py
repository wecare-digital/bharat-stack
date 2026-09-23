#!/usr/bin/env python3
"""Ask each provider whether the credential in Secrets Manager actually works.

Rotating a key by hand has two failure modes that look identical from the outside:
the new value was typed wrong, or the new value was never activated at the
provider. Both leave Secrets Manager looking perfectly healthy. The only way to
tell is to spend the credential against the provider and read the answer.

Run this after every manual rotation. VALID means the provider accepted it just
now, not that a field is non-empty.

    python scripts/check_secrets_live.py
    python scripts/check_secrets_live.py --only razorpay
    python scripts/check_secrets_live.py --json

Statuses:
    VALID       the provider accepted the credential
    INVALID     the provider rejected it - the rotation is not finished
    UNTESTABLE  no read-only endpoint can validate it alone (documented per item)
    ERROR       the check itself failed (network, timeout, unexpected response)

Values are read into memory, reported as a sha256 prefix, and never printed,
logged or placed on a command line. Exit status is 1 if anything is INVALID.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
TIMEOUT = 20


def fp(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def http(url: str, *, headers=None, data=None, method=None) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw[:200].decode(errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return e.code, raw[:200].decode(errors="replace")


def basic(user: str, password: str) -> dict:
    tok = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {tok}"}


# --------------------------------------------------------------------------
# Per-provider checks. Each returns (status, detail).
# --------------------------------------------------------------------------
def check_meta(s: dict) -> list[tuple[str, str, str, str]]:
    out = []
    token, app_id, app_secret = s.get("access_token"), s.get("app_id"), s.get("app_secret")
    if token and app_secret:
        proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        code, body = http("https://graph.facebook.com/v25.0/me?" + urllib.parse.urlencode(
            {"access_token": token, "appsecret_proof": proof, "fields": "id,name"}))
        if code == 200:
            out.append(("access_token + app_secret", "VALID",
                        f"Graph /me answered for id={body.get('id','?')}", fp(token)))
        else:
            err = body.get("error", {}) if isinstance(body, dict) else {}
            out.append(("access_token + app_secret", "INVALID",
                        f"HTTP {code}: {str(err.get('message'))[:90]}", fp(token)))
    if app_id and app_secret:
        code, body = http("https://graph.facebook.com/v25.0/" + app_id + "?" +
                          urllib.parse.urlencode({"access_token": f"{app_id}|{app_secret}",
                                                  "fields": "id"}))
        out.append(("app_secret (app token)", "VALID" if code == 200 else "INVALID",
                    f"HTTP {code}", fp(app_secret)))
    for field in ("client_token", "client_token_waba2"):
        if s.get(field):
            out.append((field, "UNTESTABLE",
                        "client tokens only authenticate client-side SDK calls; "
                        "no server endpoint validates one alone", fp(s[field])))
    if s.get("waba_t_verify_token"):
        out.append(("waba_t_verify_token", "UNTESTABLE",
                    "self-chosen value; validated by the webhook handshake - "
                    "see the wecare-whatsapp-calling smoke test", fp(s["waba_t_verify_token"])))
    return out


def check_razorpay(s: dict) -> list[tuple[str, str, str, str]]:
    kid, ksec = s.get("key_id"), s.get("key_secret")
    if not (kid and ksec):
        return [("key_id/key_secret", "ERROR", "field missing", "")]
    code, body = http("https://api.razorpay.com/v1/payments?count=1", headers=basic(kid, ksec))
    if code == 200:
        n = len(body.get("items", [])) if isinstance(body, dict) else 0
        return [("key_id + key_secret", "VALID", f"payments API answered, {n} item(s)", fp(ksec))]
    desc = ""
    if isinstance(body, dict):
        desc = str(body.get("error", {}).get("description", ""))[:90]
    return [("key_id + key_secret", "INVALID", f"HTTP {code}: {desc}", fp(ksec))]


def check_plivo(s: dict) -> list[tuple[str, str, str, str]]:
    aid, tok = s.get("auth_id"), s.get("auth_token")
    if not (aid and tok):
        return [("auth_id/auth_token", "ERROR", "field missing", "")]
    code, body = http(f"https://api.plivo.com/v1/Account/{aid}/", headers=basic(aid, tok))
    if code == 200:
        name = body.get("name", "?") if isinstance(body, dict) else "?"
        return [("auth_id + auth_token", "VALID", f"account API answered for '{name}'", fp(tok))]
    return [("auth_id + auth_token", "INVALID", f"HTTP {code}", fp(tok))]


def check_google_key(s: dict, field: str) -> list[tuple[str, str, str, str]]:
    key = s.get(field)
    if not key:
        return []
    code, body = http("https://maps.googleapis.com/maps/api/geocode/json?" +
                      urllib.parse.urlencode({"address": "New Delhi", "key": key}))
    status = body.get("status") if isinstance(body, dict) else "?"
    if code == 200 and status in ("OK", "ZERO_RESULTS"):
        return [(field, "VALID", f"Geocoding answered status={status}", fp(key))]
    if status == "REQUEST_DENIED":
        msg = str(body.get("error_message", ""))[:90] if isinstance(body, dict) else ""
        verdict = "INVALID" if "api key" in msg.lower() or "expired" in msg.lower() else "UNTESTABLE"
        return [(field, verdict, f"REQUEST_DENIED: {msg}", fp(key))]
    return [(field, "ERROR", f"HTTP {code} status={status}", fp(key))]


def check_openai(s: dict) -> list[tuple[str, str, str, str]]:
    """401 means the key is dead. 403 means it authenticated and lacks a scope.

    Treating both as failure is wrong and actively misleading during a rotation:
    a scope-restricted service-account key is working exactly as issued, and
    reporting it as INVALID sends someone to re-rotate a perfectly good key.

    The OpenAI-Organization header is deliberately not sent. The organization_id
    stored beside this key no longer matches the key's own organization, and
    supplying it turns a working request into `mismatched_organization`.
    """
    out = []
    for field in ("ads_service_account_api_key", "project_api_key"):
        key = s.get(field)
        if not key:
            continue
        code, body = http("https://api.openai.com/v1/models",
                          headers={"Authorization": f"Bearer {key}"})
        msg = ""
        if isinstance(body, dict):
            err = body.get("error")
            msg = err if isinstance(err, str) else str((err or {}).get("message", ""))
        if code == 200:
            n = len(body.get("data", [])) if isinstance(body, dict) else 0
            out.append((field, "VALID", f"{n} model(s) listed", fp(key)))
        elif code == 403 and ("scope" in msg.lower() or "permission" in msg.lower()):
            out.append((field, "VALID",
                        "authenticated; scope-restricted by design "
                        f"({msg.split('.')[0][:60]})", fp(key)))
        else:
            out.append((field, "INVALID", f"HTTP {code}: {msg[:80]}", fp(key)))
    return out


def check_wix(s: dict) -> list[tuple[str, str, str, str]]:
    key, site = s.get("api_key"), s.get("site_id")
    if not key:
        return []
    headers = {"Authorization": key, "Content-Type": "application/json"}
    if site:
        headers["wix-site-id"] = site
    code, body = http("https://www.wixapis.com/stores-reader/v1/products/query",
                      headers=headers, data=b'{"query":{"paging":{"limit":1}}}', method="POST")
    if code == 200:
        return [("api_key", "VALID", "Wix stores API answered", fp(key))]
    if code in (401, 403):
        return [("api_key", "INVALID", f"HTTP {code}", fp(key))]
    return [("api_key", "UNTESTABLE", f"HTTP {code} - key may be scoped elsewhere", fp(key))]


def check_shared_secret(s: dict, field: str, what: str) -> list[tuple[str, str, str, str]]:
    v = s.get(field)
    if not v:
        return []
    return [(field, "UNTESTABLE", what, fp(v))]


CHECKS = {
    "wecare/meta-system-user-token": check_meta,
    "wecare/razorpay/api": check_razorpay,
    "wecare/plivo/api": check_plivo,
    "wecare/openai/api": check_openai,
    "wecare/google-api-key": lambda s: check_google_key(s, "api_key"),
    "wecare/google/cloud": lambda s: check_google_key(s, "unified_google_api_key"),
    "wecare/razorpay-webhook": lambda s: check_shared_secret(
        s, "webhook_secret",
        "shared HMAC secret - no endpoint validates it; proven only when Razorpay "
        "delivers a webhook whose signature verifies"),
    "wecare/plivo-answer": lambda s: check_shared_secret(
        s, "token", "our own callback gate token, not a provider credential"),
    "wecare/google/ads": lambda s: check_shared_secret(
        s, "developer_token",
        "Google Ads needs the developer token plus an OAuth credential together"),
    "wecare/seo/google-oauth": lambda s: check_shared_secret(
        s, "client_secret", "OAuth client secret is only exercised by a full auth flow"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="substring filter on the secret id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    sm = boto3.client("secretsmanager", region_name=REGION)
    print("=" * 78)
    print("LIVE CREDENTIAL CHECK - each value is spent against its provider")
    print("=" * 78)

    rows, tally = [], {"VALID": 0, "INVALID": 0, "UNTESTABLE": 0, "ERROR": 0}
    for sid, fn in sorted(CHECKS.items()):
        if args.only and args.only not in sid:
            continue
        try:
            doc = json.loads(sm.get_secret_value(SecretId=sid)["SecretString"])
        except ClientError as exc:
            print(f"\n{sid}\n  ERROR       cannot read: {exc.response['Error']['Code']}")
            tally["ERROR"] += 1
            continue
        except json.JSONDecodeError:
            print(f"\n{sid}\n  ERROR       not JSON")
            tally["ERROR"] += 1
            continue
        print(f"\n{sid}")
        try:
            results = fn(doc)
        except Exception as exc:  # noqa: BLE001
            results = [("(check)", "ERROR", f"{type(exc).__name__}: {exc}"[:90], "")]
        if not results:
            print("  (no checkable field present)")
        for field, status, detail, digest in results:
            tally[status] = tally.get(status, 0) + 1
            tag = f"sha256:{digest}" if digest else ""
            print(f"  {status:11s} {field:26s} {detail}")
            if tag:
                print(f"              {tag}")
            rows.append({"secret": sid, "field": field, "status": status,
                         "detail": detail, "fp": digest})

    print("\n" + "=" * 78)
    print(f"VALID {tally['VALID']}   INVALID {tally['INVALID']}   "
          f"UNTESTABLE {tally['UNTESTABLE']}   ERROR {tally['ERROR']}")
    print(f"RESULT: {'PASS' if tally['INVALID'] == 0 else 'FAIL - a rotation is incomplete'}")
    print("=" * 78)
    if args.json:
        print(json.dumps(rows, indent=2))
    return 1 if tally["INVALID"] else 0


if __name__ == "__main__":
    sys.exit(main())
