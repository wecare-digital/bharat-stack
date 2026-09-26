#!/usr/bin/env python3
"""Read and repoint the RCS delivery-receipt webhook on the ACL / Sinch Conversation API.

WHAT THIS TALKS TO
------------------
Not Sinch's own endpoints. India RCS here runs on ACL Mobile's white-labelled
Conversation API:

    token : POST https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/openid-connect/token
            grant_type=password, client_id=ipmessaging-client
    api   : https://convapi.aclwhatsapp.com/v1/projects/{projectId}/...

`messages:send` is the only edge this repository used before, which is why an earlier
audit recorded "no API path" for the webhook. The path shape is identical to Sinch's
Conversation API (`/v1/projects/{project}/...`), so the standard `webhooks` collection
is probed here rather than assumed absent.

CREDENTIALS
-----------
`username` and `password` come from Secrets Manager `wecare/sinch/rcs` in memory,
exactly as `lambda_utils/sinch_rcs.py` already does. Never in argv, never printed,
never written to a snapshot. The bearer token is held in memory only.

WHY THE WEBHOOK SECRET MATTERS HERE
-----------------------------------
`wecare/sinch/rcs` has no `webhook_secret`, so `rcs-dlr` fail-closes and answers 503
to every callback — 825 refusals in the 14 days before this was investigated, meaning
delivery receipts have been dropped for months. Repointing the URL does NOT fix that.
If this API returns a secret when a webhook is created or updated, it has to be stored
under `webhook_secret` for callbacks to start being accepted. That storing step is a
credential write and is deliberately NOT done here.

Usage:
    python scripts/rcs_webhook_control_plane.py                 # discover + read
    python scripts/rcs_webhook_control_plane.py --plan <url>
    python scripts/rcs_webhook_control_plane.py --apply <url>

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
SECRET_ID = os.environ.get("SINCH_RCS_SECRET_ID", "wecare/sinch/rcs")
AUTH_URL = ("https://auth.aclwhatsapp.com/realms/ipmessaging/"
            "protocol/openid-connect/token")
CLIENT_ID = "ipmessaging-client"
API_HOST = os.environ.get("RCS_API_HOST", "https://convapi.aclwhatsapp.com")
TIMEOUT = 30


def _creds() -> dict:
    sm = boto3.client("secretsmanager", region_name=REGION)
    raw = sm.get_secret_value(SecretId=SECRET_ID)["SecretString"]
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise SystemExit(f"{SECRET_ID} is not JSON")
    missing = [k for k in ("username", "password", "project_id") if not (d.get(k) or "").strip()]
    if missing:
        raise SystemExit(f"{SECRET_ID} is missing: {', '.join(missing)}")
    return d


def _token(username: str, password: str) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": username,
        "password": password,
    }).encode()
    req = urllib.request.Request(
        AUTH_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            tok = json.loads(r.read().decode()).get("access_token", "")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"token endpoint -> {exc.code}; credentials rejected")
    if not tok:
        raise SystemExit("token endpoint returned no access_token")
    return tok


def _call(method: str, path: str, token: str, payload: dict | None = None):
    url = f"{API_HOST}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() or ""
        try:
            return exc.code, json.loads(raw or "{}")
        except Exception:  # noqa: BLE001
            return exc.code, {"_raw": raw[:300]}
    except Exception as exc:  # noqa: BLE001
        return 0, {"_error": type(exc).__name__}


def _redact(obj):
    """Strip anything secret-shaped before printing. The webhook object may carry a
    signing secret, and this script prints its findings."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in ("secret", "token", "password", "key")):
                out[k] = f"<present, {len(str(v))} chars, not shown>" if v else "<empty>"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--plan", metavar="URL")
    g.add_argument("--apply", metavar="URL")
    args = ap.parse_args(argv)

    d = _creds()
    project, app_id = d["project_id"].strip(), (d.get("app_id") or "").strip()
    print(f"secret {SECRET_ID}  project {project}  app {app_id or '(none)'}")
    print(f"username matches 'wecaretrans': {d['username'].strip() == 'wecaretrans'}")
    print(f"webhook_secret present in secret: {bool((d.get('webhook_secret') or '').strip())}")
    print()

    token = _token(d["username"].strip(), d["password"])
    print("token obtained (not shown)\n")

    paths = [
        f"/v1/projects/{project}/webhooks",
        f"/v1/projects/{project}/apps/{app_id}/webhooks" if app_id else None,
        f"/v1/projects/{project}/apps/{app_id}" if app_id else None,
    ]
    found = None
    for p in [x for x in paths if x]:
        status, body = _call("GET", p, token)
        print(f"  GET {p}")
        print(f"      -> {status}  {json.dumps(_redact(body))[:300]}")
        if status == 200:
            found = (p, body)
            break

    if not found:
        print("\nNo webhooks collection answered 200. This white-label may not expose "
              "webhook management, in which case the callback is an ACL-side setting and "
              "must be raised with them.")
        return 2

    path, body = found
    print(f"\nwebhooks collection: {path}")
    print(json.dumps(_redact(body), indent=2)[:1500])

    target = args.plan or args.apply
    if not target:
        print("\nread-only; pass --plan or --apply <url> to change anything")
        return 0

    hooks = body.get("webhooks") or []
    todo = [h for h in hooks if h.get("target") != target]
    if not todo:
        print("\nalready pointing at the target; nothing to do")
        return 0

    print("\nPLAN:")
    for h in todo:
        print(f"  {h.get('id')}: {h.get('target')}")
        print(f"      -> {target}   restating {len(h.get('triggers') or [])} trigger(s)")
    if not args.apply:
        print("\nplan only; re-run with --apply to write")
        return 0

    for h in todo:
        wid = h["id"]
        # Full restate. The update semantics of this white-label are not documented, so
        # every field that matters is sent back rather than trusting a partial PATCH to
        # leave them alone. `secret` in particular: omitting it on a replacing endpoint
        # would clear the provider-side signing secret, and a webhook that stops being
        # signed is worse than one pointing at the wrong host. It is carried through in
        # memory and never printed.
        payload = {
            "target": target,
            "target_type": h.get("target_type") or "HTTP",
            "triggers": h.get("triggers") or [],
        }
        if h.get("secret"):
            payload["secret"] = h["secret"]
        if h.get("client_credentials") is not None:
            payload["client_credentials"] = h["client_credentials"]

        # The individual webhook is NOT nested under /apps/. Sinch's Conversation API
        # lists webhooks per app but addresses each one at the project level, and this
        # white-label follows that: `GET /projects/{p}/apps/{a}/webhooks` returns 200
        # while `PATCH /projects/{p}/apps/{a}/webhooks/{id}` is 404. The project-level
        # LIST returning 501 UNIMPLEMENTED is a separate thing and does not imply the
        # project-level RESOURCE is absent — which is the wrong inference to draw, and
        # the reason both shapes are tried explicitly.
        attempts = [
            ("PATCH", f"/v1/projects/{project}/webhooks/{wid}"),
            ("PUT",   f"/v1/projects/{project}/webhooks/{wid}"),
            ("PATCH", f"{path}/{wid}"),
            ("PUT",   f"{path}/{wid}"),
        ]
        status, resp, used = 0, {}, None
        for verb, wpath in attempts:
            status, resp = _call(verb, wpath, token, payload)
            print(f"  {verb:5} {wpath} -> {status}")
            if status in (200, 201, 204):
                used = f"{verb} {wpath}"
                break
        if not used:
            print(f"\nFAIL: no verb/path combination was accepted for {wid}. The webhook "
                  f"is unchanged. Confirm the update route with ACL rather than retrying.")
            return 1
        print(f"  accepted via {used}  {json.dumps(_redact(resp))[:200]}")

    # Read back. The response body is not evidence; the persisted collection is.
    status, after = _call("GET", path, token)
    if status != 200:
        print(f"FAIL: read-back GET -> {status}")
        return 1
    print("\nAFTER:")
    print(json.dumps(_redact(after), indent=2)[:900])

    problems = []
    for h in after.get("webhooks") or []:
        if h.get("target") != target:
            problems.append(f"{h.get('id')} target is {h.get('target')}")
        before = next((b for b in todo if b["id"] == h.get("id")), None)
        if before:
            lost = set(before.get("triggers") or []) - set(h.get("triggers") or [])
            if lost:
                problems.append(f"{h.get('id')} lost triggers {sorted(lost)}")
            if before.get("secret") and not h.get("secret"):
                problems.append(f"{h.get('id')} LOST ITS SIGNING SECRET")
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    old = sorted({h.get("target") for h in todo})
    print(f"\nOK: target is {target}, triggers intact, signing secret still present")
    print(f"Rollback: python {sys.argv[0]} --apply {old[0]}")
    print("\nNOTE: this does NOT fix the 503s. The provider signs callbacks with the "
          "secret above, and `wecare/sinch/rcs` has no `webhook_secret`, so `rcs-dlr` "
          "still cannot verify them. Storing it is a credential write and is not done "
          "here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
