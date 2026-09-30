#!/usr/bin/env python3
"""Register this Google Cloud project with a Merchant Center account. Read-only by default.

    python scripts/merchant_center_register.py --probe
    python scripts/merchant_center_register.py --account 1234567 --email you@example.com
    python scripts/merchant_center_register.py --account 1234567 --email you@example.com --apply

WHY THIS EXISTS, AND WHY IT NEEDS AN ARGUMENT IT CANNOT DISCOVER
---------------------------------------------------------------
Merchant Center is the one blocked Google surface whose gate is an API call rather
than a support form, so unlike Google Ads (Explorer enrolment) and Business Profile
(Basic API Access application) it can actually be resolved from here.

The gate, measured rather than assumed:

    GET content/v2.1/accounts/authinfo     -> HTTP 200, and NO accountIdentifiers
    GET merchantapi/accounts/v1/accounts   -> HTTP 401 "GCP project with id
                                              wecaredigitalbw and number 756034744787
                                              is not registered with the merchant
                                              account"

Both say the same thing from different angles: authentication works, the service
account is a user, and the CLOUD PROJECT is not linked to the merchant account.
Adding a user cannot fix it - that is the whole reason this is a separate script
rather than another grant.

THE CHICKEN AND EGG, which is why --account is mandatory. Registration is per
merchant account:

    POST accounts/v1/accounts/{ACCOUNT_ID}/developerRegistration:registerGcp

so it needs the account id. Listing accounts to FIND the id requires being
registered. There is no bootstrap: `authinfo` returns an empty body precisely
because nothing is linked yet. So the id has to come from a human reading it out of
the Merchant Center UI (top right, next to the account name). Every automated route
to it was tried and each one dead-ends:

  * Content API v2.1 `accounts.list` needs a merchant id as the PATH parameter, so
    it cannot enumerate;
  * Google Ads exposes a MerchantCenterLink resource that would name linked
    accounts, but every Ads production query on this project returns
    CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION until Explorer access lands - so it is
    blocked behind a different gate;
  * nothing in this repository references a Merchant Center account at all, so there
    is no recorded id to read. That absence is itself worth checking before running
    this: it may mean no account has ever been created, in which case there is
    nothing to register and step zero is creating one.

WHAT REGISTRATION ACTUALLY DOES, so --apply is an informed choice. It assigns the
API developer role to `--email` on the merchant account and associates this Cloud
project with it, so Google can send API service announcements to a named technical
contact. It is additive and does not touch products, feeds, prices or any ad
spend. It is also not a no-op on permissions: the named email gains a role on the
merchant account, which is why the email is an explicit argument rather than
defaulting to whoever happens to be authenticated.

Auth is the impersonated service account - no browser, no key file, no secret read
or printed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

SA = "automation@wecaredigitalbw.iam.gserviceaccount.com"
PROJECT_ID = "wecaredigitalbw"
PROJECT_NUMBER = "756034744787"
SCOPE = "https://www.googleapis.com/auth/content"

MERCHANT = "https://merchantapi.googleapis.com/accounts/v1"
CONTENT = "https://shoppingcontent.googleapis.com/content/v2.1"


def token() -> str:
    p = subprocess.run(
        ["gcloud", "auth", "print-access-token",
         f"--impersonate-service-account={SA}", f"--scopes={SCOPE}"],
        capture_output=True, text=True, timeout=180)
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit(f"could not mint a token: {p.stderr.strip()[:200]}")
    return p.stdout.strip()


def call(method: str, url: str, tok: str, body: dict | None = None
         ) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {tok}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": " ".join(raw.split())[:300]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": {"message": type(e).__name__}}


def why(body: Any) -> str:
    entry = body[0] if isinstance(body, list) and body else body
    if isinstance(entry, dict):
        err = entry.get("error")
        if isinstance(err, dict):
            return f"{err.get('status', '')}: {err.get('message', '')}".strip()[:400]
        if "raw" in entry:
            return str(entry["raw"])[:300]
    return str(entry)[:300]


def probe(tok: str) -> bool:
    """Report the gate. Returns True if the project already appears registered."""
    print("-- current state --")
    st, body = call("GET", f"{CONTENT}/accounts/authinfo", tok)
    ids = body.get("accountIdentifiers") if isinstance(body, dict) else None
    print(f"   content v2.1 authinfo      : http {st}")
    if st == 200:
        if ids:
            print(f"      {len(ids)} accessible merchant account(s):")
            for i in ids:
                print(f"        {json.dumps(i)}")
        else:
            # A 200 with no body is the single most misleading answer here: it looks
            # like a successful empty result and it means "nothing is linked".
            print("      NO accountIdentifiers - zero merchant accounts accessible.")
    else:
        print(f"      {why(body)}")

    st, body = call("GET", f"{MERCHANT}/accounts", tok)
    print(f"   merchant api v1 accounts   : http {st}")
    registered = st == 200
    if st == 200:
        accounts = body.get("accounts") or []
        print(f"      {len(accounts)} account(s)")
        for a in accounts:
            print(f"        {a.get('name')} | {a.get('accountName')}")
    else:
        print(f"      {why(body)}")
        if "not registered" in why(body).lower():
            print("      ^ this is the gate: the PROJECT is unregistered, not the user")
    return registered and bool(ids)


def register(tok: str, account: str, email: str, apply: bool) -> int:
    url = (f"{MERCHANT}/accounts/{account}/developerRegistration:registerGcp")
    payload = {"developerEmail": email}
    print(f"\n-- register project {PROJECT_ID} ({PROJECT_NUMBER}) "
          f"with merchant account {account} --")
    print(f"   POST {url}")
    print(f"   body {json.dumps(payload)}")
    if not apply:
        print("   DRY RUN - nothing sent. Re-run with --apply.")
        return 0

    st, body = call("POST", url, tok, payload)
    print(f"   http {st}")
    if st not in (200, 201):
        print(f"   FAILED: {why(body)}")
        if st == 403:
            print("   403 usually means the authenticated principal is not a user on "
                  f"merchant account {account}, or lacks admin there.")
        if st == 404:
            print(f"   404 usually means account id {account} does not exist. Read it "
                  "from the Merchant Center UI, top right - digits only, no dashes.")
        return 1
    print(f"   registered: {json.dumps(body)[:400]}")
    print("\n-- verifying (Google documents up to ~5 minutes of propagation) --")
    ok = probe(tok)
    print("\n   " + ("VERIFIED - the project can now list merchant accounts."
                     if ok else
                     "not visible yet. Wait a few minutes and re-run --probe; the "
                     "registration call itself succeeded."))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", help="Merchant Center account id, digits only")
    ap.add_argument("--email", help="email to hold the API developer role")
    ap.add_argument("--apply", action="store_true", help="perform the registration")
    ap.add_argument("--probe", action="store_true", help="report state and exit")
    args = ap.parse_args()

    print("=" * 74)
    print("MERCHANT CENTER - Google Cloud project registration")
    print(f"project {PROJECT_ID} ({PROJECT_NUMBER})   auth: impersonated {SA}")
    print("=" * 74)

    tok = token()
    already = probe(tok)

    if args.probe:
        return 0 if already else 1
    if already:
        print("\nalready registered and able to list accounts - nothing to do.")
        return 0
    if not args.account or not args.email:
        print("\nNEED TWO VALUES THIS SCRIPT CANNOT DISCOVER:")
        print("   --account  the Merchant Center account id (Merchant Center UI, top")
        print("              right, beside the account name). Digits only.")
        print("   --email    the address to hold the API developer role. It receives")
        print("              Google's API service announcements, so it should be a")
        print("              person who would act on a breaking-change notice.")
        print("\nIf no Merchant Center account exists yet, there is nothing to register")
        print("and creating one is the prior step - this repository contains no")
        print("reference to a merchant account, so that is a real possibility.")
        return 2
    return register(tok, args.account, args.email, args.apply)


if __name__ == "__main__":
    sys.exit(main())
