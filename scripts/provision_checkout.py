#!/usr/bin/env python3
"""Provision and verify the customer checkout Lambda.

What it stands up
-----------------
- A least-privilege execution role: logs; read of the Wix admin API key secret; read/write on the
  payment-attempts table and the commerce-keys (reference reservation) table; and
  `lambda:InvokeFunction` on the WhatsApp business Lambda (used for the readiness payment-config
  read and, once initiation is enabled, the in-chat order_details send). It has NO Cognito IAM
  permission — `customer_auth.authenticate` calls `GetUser` with the *customer's own* access token,
  which authorises itself and needs no role permission. It has NO order-creation permission of any
  kind, because checkout never creates an order.
- The function `wecare-checkout`, then a published version and the `live` alias.

Initiation stays OFF. `CHECKOUT_INITIATION_ENABLED` is deliberately absent from the environment
this script sets, so the deployed function prepares attempts and reserves references but sends no
payable message until someone sets that flag on purpose. Readiness inputs
(`EXPECTED_CONFIGURATION_NAME`, `EXPECTED_PROVIDER_MID`) are also left empty here, so even if
initiation were flipped on, `payment_readiness` blocks until an owner supplies the values from a
live Meta/Razorpay read. There is no path from this script to a live charge.

Usage:
    python scripts/provision_checkout.py --dry-run
    python scripts/provision_checkout.py
    python scripts/provision_checkout.py --verify

After first provision, normal code updates use:
    python scripts/deploy_all_lambdas.py wecare-checkout

Follows .kiro/steering/secret-handling.md: the Wix key is read by reference at runtime via a
SecretId name only; no credential is ever placed on a command line or in a log.
"""

from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "wecare-checkout"
LIVE_ALIAS = "live"
ROLE_NAME = "wecare-checkout-role"

ROOT = Path(__file__).resolve().parents[1]
FUNCTION_DIR = ROOT / "amplify/functions/ecommerce/checkout"
SHARED_DIR = ROOT / "amplify/functions/shared"

PAYMENT_ATTEMPTS_TABLE = "stack-wecare-digital-PaymentAttemptsTable"
COMMERCE_KEYS_TABLE = "stack-wecare-digital-WixOrderIds"
WIX_API_KEY_SECRET = "wecare/wix/headless-api-key"
WIX_SITE_ID = "fcd82f0c-9572-49c7-acfb-88fb05042ece"
SENDER_FUNCTION = "wecare-whatsapp-business-api"
PAYMENT_WABA_ID = "2094615664435155"

_account_id_cache = None


def account_id() -> str:
    global _account_id_cache
    if _account_id_cache is None:
        _account_id_cache = boto3.client(
            "sts", region_name=REGION).get_caller_identity()["Account"]
    return _account_id_cache


def iam():
    return boto3.client("iam")


def lam():
    return boto3.client("lambda", region_name=REGION)


def logs():
    return boto3.client("logs", region_name=REGION)


def _not_found(exc: ClientError, *codes: str) -> bool:
    return exc.response.get("Error", {}).get("Code") in codes


def role_exists() -> bool:
    try:
        iam().get_role(RoleName=ROLE_NAME)
        return True
    except ClientError as exc:
        if _not_found(exc, "NoSuchEntity"):
            return False
        raise


def function_exists() -> bool:
    try:
        lam().get_function(FunctionName=FUNCTION_NAME)
        return True
    except ClientError as exc:
        if _not_found(exc, "ResourceNotFoundException"):
            return False
        raise


def _zip_package() -> bytes:
    """handler.py plus the shared lambda_utils tree it imports (incl. lambda_utils/wix_ecom.py).

    NOT standalone: the handler imports customer_auth, payment_readiness, ecommerce.order_keys,
    ecommerce.payment_attempt, wix_ecom, response and logging — all under lambda_utils, which the
    shared tree carries.
    """
    handler = FUNCTION_DIR / "handler.py"
    if not handler.is_file():
        raise FileNotFoundError(handler)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("handler.py", handler.read_bytes())
        lu = SHARED_DIR / "lambda_utils"
        for path in lu.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            archive.write(path, str(path.relative_to(SHARED_DIR)))
    return buf.getvalue()


def ensure_role(dry_run: bool) -> str:
    if role_exists():
        return "exists"
    if dry_run:
        return "would create"

    assume = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    iam().create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(assume),
        Description="Customer checkout (headless WhatsApp/Razorpay) execution role",
        Tags=[{"Key": "Project", "Value": "WECARE.DIGITAL"},
              {"Key": "Purpose", "Value": "Checkout"}],
    )
    iam().attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    acct = account_id()
    least_privilege = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ReadWixApiKey",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [f"arn:aws:secretsmanager:{REGION}:{acct}:secret:{WIX_API_KEY_SECRET}-*"],
            },
            {
                "Sid": "PaymentAttemptAndCommerceKeys",
                "Effect": "Allow",
                # No DeleteItem: a checkout never deletes a payment attempt or a reservation — a
                # failed attempt is the evidence that no charge became an order.
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:{acct}:table/{PAYMENT_ATTEMPTS_TABLE}",
                    f"arn:aws:dynamodb:{REGION}:{acct}:table/{COMMERCE_KEYS_TABLE}",
                ],
            },
            {
                "Sid": "InvokeWhatsAppSender",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": [
                    f"arn:aws:lambda:{REGION}:{acct}:function:{SENDER_FUNCTION}",
                    f"arn:aws:lambda:{REGION}:{acct}:function:{SENDER_FUNCTION}:{LIVE_ALIAS}",
                ],
            },
        ],
    }
    iam().put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="CheckoutLeastPrivilege",
        PolicyDocument=json.dumps(least_privilege),
    )
    return "created"


def ensure_log_group(dry_run: bool) -> str:
    name = f"/aws/lambda/{FUNCTION_NAME}"
    try:
        groups = logs().describe_log_groups(
            logGroupNamePrefix=name, limit=50).get("logGroups", [])
        exists = any(g.get("logGroupName") == name for g in groups)
    except ClientError:
        exists = False
    if not exists and dry_run:
        return "would create with 30-day retention"
    if not exists:
        logs().create_log_group(logGroupName=name, tags={
            "Project": "WECARE.DIGITAL", "Purpose": "Checkout"})
    if not dry_run:
        logs().put_retention_policy(logGroupName=name, retentionInDays=30)
    return "exists; retention verified" if exists else "created"


def expected_environment() -> dict:
    return {
        "PAYMENT_ATTEMPTS_TABLE": PAYMENT_ATTEMPTS_TABLE,
        "COMMERCE_KEYS_TABLE": COMMERCE_KEYS_TABLE,
        "WIX_API_KEY_SECRET": WIX_API_KEY_SECRET,
        "WIX_SITE_ID": WIX_SITE_ID,
        "SENDER_FUNCTION": f"{SENDER_FUNCTION}:{LIVE_ALIAS}",
        "PAYMENT_WABA_ID": PAYMENT_WABA_ID,
        # Deliberately empty: payment_readiness returns CONFIGURATION_UNVERIFIED until an owner sets
        # these from a live Meta/Razorpay read. No value here can enable a payment.
        "EXPECTED_CONFIGURATION_NAME": "",
        "EXPECTED_PROVIDER_MID": "",
        # CHECKOUT_INITIATION_ENABLED intentionally omitted -> initiation OFF.
    }


def ensure_function(dry_run: bool) -> str:
    if function_exists():
        return "exists"
    if dry_run:
        return "would create"

    role_arn = iam().get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    for attempt in range(8):
        try:
            lam().create_function(
                FunctionName=FUNCTION_NAME,
                Runtime="python3.12",
                Role=role_arn,
                Handler="handler.handler",
                Code={"ZipFile": _zip_package()},
                Description="Customer checkout: authoritative Wix total, readiness gate, "
                            "PaymentAttempt, in-chat handoff. Initiation off by default.",
                Timeout=20,
                MemorySize=256,
                Environment={"Variables": expected_environment()},
                Tags={"Project": "WECARE.DIGITAL", "Purpose": "Checkout"},
            )
            return "created"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != \
                    "InvalidParameterValueException" or attempt == 7:
                raise
            time.sleep(2)
    raise RuntimeError("Lambda create retry exhausted")


def reconcile_environment(dry_run: bool) -> str:
    if not function_exists():
        return "function absent - nothing to reconcile"
    config = lam().get_function_configuration(FunctionName=FUNCTION_NAME)
    current = dict((config.get("Environment") or {}).get("Variables") or {})
    wanted = expected_environment()
    # Only ADD/repair the keys this script owns; never clobber an operator-set
    # CHECKOUT_INITIATION_ENABLED or a live-read EXPECTED_* value.
    drifted = {k: v for k, v in wanted.items()
               if k not in ("EXPECTED_CONFIGURATION_NAME", "EXPECTED_PROVIDER_MID")
               and current.get(k) != v}
    for k in ("EXPECTED_CONFIGURATION_NAME", "EXPECTED_PROVIDER_MID"):
        if k not in current:
            drifted[k] = wanted[k]
    if not drifted:
        return "env already correct"
    if dry_run:
        return f"would set {', '.join(sorted(drifted))}"
    current.update(drifted)
    lam().update_function_configuration(
        FunctionName=FUNCTION_NAME, Environment={"Variables": current})
    lam().get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
    return f"set {', '.join(sorted(drifted))}"


def ensure_live_alias(dry_run: bool) -> str:
    try:
        lam().get_alias(FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS)
        return "exists"
    except ClientError as exc:
        if not _not_found(exc, "ResourceNotFoundException"):
            raise
    if dry_run:
        return "would publish v1 and create live alias"
    published = lam().publish_version(
        FunctionName=FUNCTION_NAME, Description="initial checkout release (initiation off)")
    version = published["Version"]
    lam().get_waiter("function_active_v2").wait(
        FunctionName=FUNCTION_NAME, Qualifier=version)
    lam().create_alias(
        FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS, FunctionVersion=version,
        Description="Production checkout target")
    return f"created -> v{version}"


def verify() -> int:
    problems: list[str] = []
    if not function_exists():
        print("FAIL function missing")
        return 1
    try:
        alias = lam().get_alias(FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS)
    except ClientError:
        print("FAIL live alias missing")
        return 1

    live_config = lam().get_function_configuration(
        FunctionName=FUNCTION_NAME, Qualifier=alias["FunctionVersion"])
    live_env = (live_config.get("Environment") or {}).get("Variables") or {}
    for key in ("PAYMENT_ATTEMPTS_TABLE", "COMMERCE_KEYS_TABLE", "WIX_API_KEY_SECRET",
                "SENDER_FUNCTION", "PAYMENT_WABA_ID"):
        if live_env.get(key) != expected_environment()[key]:
            problems.append(f"env {key} mismatch on live (v{alias['FunctionVersion']})")

    initiation = str(live_env.get("CHECKOUT_INITIATION_ENABLED", "")).strip().lower()
    if initiation in ("1", "true", "yes", "on"):
        problems.append("CHECKOUT_INITIATION_ENABLED is ON — live payment initiation is enabled")

    print(f"function: present (live v{alias['FunctionVersion']})")
    print(f"initiation: {'ON' if initiation in ('1','true','yes','on') else 'OFF (expected)'}")
    print(f"sender: {SENDER_FUNCTION}:{LIVE_ALIAS}; WABA {PAYMENT_WABA_ID}")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\ncheckout provisioning verified (initiation disabled)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    print(f"region: {REGION}")
    print(f"sender: {SENDER_FUNCTION}:{LIVE_ALIAS}; WABA {PAYMENT_WABA_ID}")
    print("initiation: OFF (CHECKOUT_INITIATION_ENABLED not set)")
    print(f"dry run: {args.dry_run}\n")

    print(f"role: {ensure_role(args.dry_run)}")
    print(f"log group: {ensure_log_group(args.dry_run)}")
    print(f"Lambda: {ensure_function(args.dry_run)}")
    print(f"env: {reconcile_environment(args.dry_run)}")
    print(f"live alias: {ensure_live_alias(args.dry_run)}")

    if args.dry_run:
        print("\ndry run: nothing changed")
        return 0

    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
