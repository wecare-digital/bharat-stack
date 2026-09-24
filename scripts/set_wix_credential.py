#!/usr/bin/env python3
"""Store the Wix Headless API key in AWS Secrets Manager. Hidden input only.

Why the key is typed at a prompt rather than passed as an argument
-----------------------------------------------------------------
On 2026-09-19 four live credentials ended up in plaintext inside Kiro's own
permissions file, because commands had been run with the credential inline and
"Always allow" recorded the whole command string. A credential in argv also lands in
shell history, in `ps` output for the life of the process, and in any CI log.

So this script takes the value through `getpass` and refuses to accept it any other
way. It prints metadata only - never the value, not even truncated. A fingerprint is
printed instead, which is enough to confirm two machines hold the same key without
either of them displaying it.

Usage
-----
    python scripts/set_wix_credential.py                 # store / replace the key
    python scripts/set_wix_credential.py --verify        # store, then prove it works
    python scripts/set_wix_credential.py --set-env       # also point the Lambda at it
    python scripts/set_wix_credential.py --enable        # also clear the kill switch
    python scripts/set_wix_credential.py --status        # read nothing, report state

`--set-env` writes only the secret's NAME into the function environment, which is not
a credential. `--enable` clears `WIX_CREDENTIALS_DISABLED`, and is deliberately a
separate flag because it is the step that makes Wix live again.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
SECRET_NAME = "wecare/wix/headless"
FUNCTION = "wecare-wix-store"

# Non-secret identifiers. Safe to hold in source: they name resources, they do not
# grant access to them. Confirmed against the live function config on 2026-09-23,
# where WIX_ACCOUNT_ID and WIX_SITE_ID already carried exactly these values.
WIX_ACCOUNT_ID = "15f02319-40ff-4288-b8e6-69c791adae5e"
WIX_SITE_ID = "fcd82f0c-9572-49c7-acfb-88fb05042ece"
WIX_CLIENT_ID = "197cd718-e4ec-4e2e-b380-46c297eb18a2"
WIX_CLIENT_NAME = "apiwx"

WIX_API_BASE = "https://www.wixapis.com"


def fingerprint(value: str) -> str:
    """A stable, non-reversible identity for a secret value.

    Twelve hex characters of SHA-256. Enough to confirm that the key in AWS is the one
    you meant to store, without displaying any part of it. Never print a prefix or a
    suffix of a credential - an issuer prefix plus a length is a meaningful head start.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def refuse_argv_secrets(argv: list) -> None:
    """Refuse if the key looks like it was passed on the command line."""
    for arg in argv:
        if arg.startswith("IST.") or len(arg) > 80:
            sys.exit(
                "REFUSED: that looks like a credential passed as an argument.\n"
                "Run the script with no value and paste it at the hidden prompt. A "
                "credential in argv lands in shell history and in ps output."
            )
    for name in ("WIX_API_KEY", "WIX_KEY", "WIX_TOKEN"):
        if os.environ.get(name):
            sys.exit(
                f"REFUSED: {name} is set in the environment.\n"
                "Unset it and use the hidden prompt. An environment variable holding a "
                "credential is readable by every child process."
            )


def read_key_hidden() -> str:
    """Read the key without echoing it. Validates shape without printing any of it."""
    print("Paste the Wix Headless API key. It will NOT be displayed.")
    print("(Wix shows it once, at creation, in Headless > API keys.)")
    key = getpass.getpass("Wix API key: ").strip()

    if not key:
        sys.exit("REFUSED: empty value.")
    if len(key) < 60:
        sys.exit(f"REFUSED: value is {len(key)} characters, too short for a Wix API "
                 f"key. Nothing was written.")
    if not key.startswith("IST."):
        print("WARNING: value does not begin with the usual Wix API key marker.")
        if input("Continue anyway? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted. Nothing was written.")

    again = getpass.getpass("Paste it again to confirm: ").strip()
    if again != key:
        sys.exit("REFUSED: the two entries differ. Nothing was written.")
    return key


def store(key: str) -> dict:
    """Create or replace the secret. Returns metadata only."""
    client = boto3.client("secretsmanager", region_name=REGION)
    payload = json.dumps({
        # `api_key` is the field name `wix-store`'s loader looks for first.
        "api_key": key,
        "account_id": WIX_ACCOUNT_ID,
        "site_id": WIX_SITE_ID,
        "client_id": WIX_CLIENT_ID,
        "client_name": WIX_CLIENT_NAME,
    })

    try:
        response = client.create_secret(
            Name=SECRET_NAME,
            Description="Wix Headless API key and non-secret ids for wecare-wix-store.",
            SecretString=payload,
        )
        action = "created"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceExistsException":
            raise
        response = client.put_secret_value(SecretId=SECRET_NAME, SecretString=payload)
        action = "replaced"

    return {
        "action": action,
        "arn": response.get("ARN"),
        "versionId": response.get("VersionId"),
        "fields": ["api_key", "account_id", "site_id", "client_id", "client_name"],
        "apiKeyLength": len(key),
        "apiKeyFingerprint": fingerprint(key),
    }


def set_env_pointer() -> dict:
    """Point the Lambda at the secret by NAME. Not a credential."""
    client = boto3.client("lambda", region_name=REGION)
    current = client.get_function_configuration(FunctionName=FUNCTION)
    env = dict((current.get("Environment") or {}).get("Variables", {}) or {})
    before = sorted(env)

    env["WIX_API_KEY_SECRET"] = SECRET_NAME
    env.setdefault("WIX_ORDER_IDS_TABLE", "stack-wecare-digital-WixOrderIds")

    client.update_function_configuration(
        FunctionName=FUNCTION, Environment={"Variables": env})
    after = client.get_function_configuration(FunctionName=FUNCTION)
    keys = sorted((after.get("Environment") or {}).get("Variables", {}))
    return {"before": before, "after": keys, "added": sorted(set(keys) - set(before))}


def enable() -> dict:
    """Clear WIX_CREDENTIALS_DISABLED. The step that makes Wix live again.

    Separate flag on purpose: storing a key is reversible and inert, whereas clearing
    the switch changes what the running system does.
    """
    client = boto3.client("lambda", region_name=REGION)
    current = client.get_function_configuration(FunctionName=FUNCTION)
    env = dict((current.get("Environment") or {}).get("Variables", {}) or {})
    was = env.pop("WIX_CREDENTIALS_DISABLED", None)
    env.pop("CREDENTIAL_PURGE_EPOCH", None)
    client.update_function_configuration(
        FunctionName=FUNCTION, Environment={"Variables": env})
    return {"wasDisabled": was, "nowDisabled": False}


def verify() -> dict:
    """One live READ against Wix to prove the stored key works.

    Reads the value straight from Secrets Manager into memory for a single request and
    never logs it. This is the one place a read is unavoidable - the point of the
    exercise is to prove the provider accepts it, and only the provider can say.
    """
    raw = boto3.client("secretsmanager", region_name=REGION).get_secret_value(
        SecretId=SECRET_NAME)["SecretString"]
    key = json.loads(raw)["api_key"]

    request = urllib.request.Request(
        f"{WIX_API_BASE}/site-list/v2/sites/query",
        data=json.dumps({"query": {"paging": {"limit": 1}}}).encode(),
        headers={
            "Authorization": key,
            "Content-Type": "application/json",
            "wix-account-id": WIX_ACCOUNT_ID,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode() or "{}")
        sites = body.get("sites") or []
        return {
            "accepted": True,
            "httpStatus": 200,
            "sitesVisible": len(sites),
            # Confirms the key is scoped to the account we think it is.
            "firstSiteId": (sites[0].get("id") if sites else None),
            "matchesConfiguredSiteId": any(
                s.get("id") == WIX_SITE_ID for s in sites),
        }
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = (exc.read().decode() or "")[:200]
        except Exception:  # noqa: BLE001
            pass
        return {"accepted": False, "httpStatus": exc.code, "detail": detail}
    except Exception as exc:  # noqa: BLE001
        return {"accepted": False, "error": type(exc).__name__}


def status() -> dict:
    """Report state without reading any secret value."""
    sm = boto3.client("secretsmanager", region_name=REGION)
    out = {}
    try:
        described = sm.describe_secret(SecretId=SECRET_NAME)
        out["secret"] = {
            "name": described.get("Name"),
            "arn": described.get("ARN"),
            "lastChanged": str(described.get("LastChangedDate")),
            "exists": True,
        }
    except ClientError:
        out["secret"] = {"name": SECRET_NAME, "exists": False}

    config = boto3.client("lambda", region_name=REGION).get_function_configuration(
        FunctionName=FUNCTION)
    env = dict((config.get("Environment") or {}).get("Variables", {}) or {})
    out["function"] = {
        "name": FUNCTION,
        "apiKeySecretName": env.get("WIX_API_KEY_SECRET"),
        "accountId": env.get("WIX_ACCOUNT_ID"),
        "siteId": env.get("WIX_SITE_ID"),
        "credentialsDisabled": env.get("WIX_CREDENTIALS_DISABLED"),
        "accountIdMatchesExpected": env.get("WIX_ACCOUNT_ID") == WIX_ACCOUNT_ID,
        "siteIdMatchesExpected": env.get("WIX_SITE_ID") == WIX_SITE_ID,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true",
                        help="report state and exit; reads no secret value")
    parser.add_argument("--set-env", action="store_true",
                        help="point the Lambda at the secret by name")
    parser.add_argument("--enable", action="store_true",
                        help="clear WIX_CREDENTIALS_DISABLED")
    parser.add_argument("--verify", action="store_true",
                        help="make one live read against Wix to prove the key works")
    args = parser.parse_args()

    refuse_argv_secrets(sys.argv[1:])

    if args.status:
        print(json.dumps(status(), indent=2))
        return 0

    key = read_key_hidden()
    result = store(key)
    # Drop the local reference promptly. Not a guarantee in CPython, but it costs
    # nothing and narrows the window.
    key = ""
    print("\nstored:", json.dumps(result, indent=2))

    if args.set_env:
        print("env pointer:", json.dumps(set_env_pointer(), indent=2))
    if args.enable:
        print("kill switch:", json.dumps(enable(), indent=2))
    if args.verify:
        print("provider verification:", json.dumps(verify(), indent=2))

    print("\nThe value was never printed, logged, or passed as an argument.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
