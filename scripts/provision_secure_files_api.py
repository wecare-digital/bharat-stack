#!/usr/bin/env python3
"""Provision the wecare-secure-files Lambda, its role, and its HTTP API routes.

Creates or updates, idempotently:

* IAM role ``wecare-secure-files-role`` with a least-privilege inline policy
* Lambda ``wecare-secure-files`` (python3.12) + published version + ``live`` alias
* Seven routes on HTTP API ``zllr9lrg7j``, all pointing at the alias
* The ``DOWNLOAD_GRANTS_TABLE`` env var and grants-table permission on
  ``wecare-razorpay-webhook``, so the webhook can mark a grant paid

Two policy choices worth stating, because a wildcard here would be invisible and
wrong:

* S3 is scoped to ``secure/*`` on the one bucket. The function has no reason to
  read the open ``o/`` tier and must not be able to rewrite it.
* Cognito admin actions are scoped to the **customer** pool ARN only. This role
  must never be able to create or modify a user in the admin pool.

Run after ``provision_secure_file_sharing.py`` (which makes the tables) and
``provision_customer_whatsapp_auth.py`` (which makes the customer pool).

Usage
-----
    python scripts/provision_secure_files_api.py --dry-run
    python scripts/provision_secure_files_api.py
    python scripts/provision_secure_files_api.py --verify
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3  (or use .venv/bin/python)")

REGION = "us-east-1"
ACCOUNT = "775261844268"
API_ID = "zllr9lrg7j"

FUNCTION_NAME = "wecare-secure-files"
ROLE_NAME = "wecare-secure-files-role"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE_NAME}"
LIVE_ALIAS = "live"

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "amplify" / "functions" / "core" / "secure-files"
LAMBDA_UTILS = ROOT / "amplify" / "functions" / "shared" / "lambda_utils"

BUCKET = "wecare-digital-get"
SECURE_PREFIX = "secure/"
FILES_TABLE = "stack-wecare-digital-SecureFilesTable"
GRANTS_TABLE = "stack-wecare-digital-DownloadGrantsTable"
CUSTOMER_POOL_ID = "us-east-1_46ULYuukt"
ADMIN_POOL_ID = "us-east-1_cSx0RHCIR"
META_WABA_ID = "2094615664435155"
RAZORPAY_SECRET_NAME = "wecare/razorpay-webhook"

WEBHOOK_FUNCTION = "wecare-razorpay-webhook"

ROUTES = [
    # admin surface (authorised inside the handler via require_auth Operator)
    ("GET", "/secure-files"),
    ("POST", "/secure-files/upload-init"),
    ("POST", "/secure-files/{fileId}/confirm"),
    ("POST", "/secure-files/{fileId}/revoke"),
    # customer surface (customer-pool token, checked inside the handler)
    ("GET", "/secure-files/mine"),
    ("POST", "/secure-files/{fileId}/order"),
    ("GET", "/secure-files/{fileId}/download"),
]

EXCLUDE_DIRS = {"__pycache__", "tests", ".pytest_cache"}


def iam():
    return boto3.client("iam", region_name=REGION)


def lam():
    return boto3.client("lambda", region_name=REGION)


def api():
    return boto3.client("apigatewayv2", region_name=REGION)


# ── IAM ───────────────────────────────────────────────────────────────────────

def policy_document() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "SecurePrefixOnly",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:HeadObject"],
                # deliberately NOT the whole bucket: the open o/ tier is out of scope
                "Resource": f"arn:aws:s3:::{BUCKET}/{SECURE_PREFIX}*",
            },
            {
                "Sid": "Catalogue",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{FILES_TABLE}",
                    f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{FILES_TABLE}/index/*",
                    f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{GRANTS_TABLE}",
                    f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{GRANTS_TABLE}/index/*",
                ],
            },
            {
                "Sid": "CustomerPoolOnly",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminUpdateUserAttributes",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminGetUser",
                ],
                # scoped to the customer pool: this role must never be able to
                # touch a user in the admin pool
                "Resource": f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/{CUSTOMER_POOL_ID}",
            },
            {
                "Sid": "ValidateCallerToken",
                "Effect": "Allow",
                # GetUser acts on the token's own user, so it takes no resource
                "Action": ["cognito-idp:GetUser"],
                "Resource": "*",
            },
            {
                "Sid": "AdminRoleLookup",
                "Effect": "Allow",
                # require_auth resolves the admin's groups in the admin pool. Read
                # only - no admin-pool mutation.
                "Action": ["cognito-idp:AdminListGroupsForUser", "cognito-idp:AdminGetUser"],
                "Resource": f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/{ADMIN_POOL_ID}",
            },
            {
                "Sid": "RazorpayKeyByArn",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                # one secret by ARN. The -* suffix matches the six random
                # characters Secrets Manager appends.
                "Resource": (
                    f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:{RAZORPAY_SECRET_NAME}-*"
                ),
            },
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{FUNCTION_NAME}:*",
            },
        ],
    }


def ensure_role(dry_run: bool) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        iam().get_role(RoleName=ROLE_NAME)
        exists = True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchEntity":
            raise
        exists = False

    if dry_run:
        return "exists (would refresh policy)" if exists else "would create"

    if not exists:
        iam().create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Execution role for wecare-secure-files",
        )
        time.sleep(12)  # IAM propagation before Lambda validates the role

    iam().put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="wecare-secure-files",
        PolicyDocument=json.dumps(policy_document()),
    )
    return "created" if not exists else "policy refreshed"


# ── packaging ─────────────────────────────────────────────────────────────────

def package() -> bytes:
    """handler.py + razorpay_orders.py + lambda_utils/, deterministically."""
    if not (SOURCE_DIR / "handler.py").exists():
        raise SystemExit(f"missing {SOURCE_DIR / 'handler.py'}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("handler.py", "razorpay_orders.py"):
            archive.write(SOURCE_DIR / name, name)
        for path in sorted(LAMBDA_UTILS.rglob("*")):
            if not path.is_file() or path.suffix == ".pyc":
                continue
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            archive.write(path, str(Path("lambda_utils") / path.relative_to(LAMBDA_UTILS)))
    return buffer.getvalue()


def environment() -> dict:
    # AWS_REGION is deliberately absent: Lambda reserves it and rejects it.
    return {
        "SECURE_FILES_BUCKET": BUCKET,
        "SECURE_FILES_TABLE": FILES_TABLE,
        "DOWNLOAD_GRANTS_TABLE": GRANTS_TABLE,
        "CUSTOMER_USER_POOL_ID": CUSTOMER_POOL_ID,
        "COGNITO_USER_POOL_ID": ADMIN_POOL_ID,  # require_auth resolves admins here
        "META_WABA_ID": META_WABA_ID,
        "PARTNER_GROUP": "Partner",
        "SECURE_FILE_PRICE_PAISE": "4900",
        "DOWNLOAD_URL_TTL_SECONDS": "60",
        "UPLOAD_URL_TTL_SECONDS": "900",
        "GRANT_TTL_SECONDS": "1800",
        # A secret NAME, never a value. See .kiro/steering/secret-handling.md.
        "RAZORPAY_SECRET_ID": RAZORPAY_SECRET_NAME,
        # OFF. Enabling paid downloads is an owner action; while this is off the
        # order route refuses and Razorpay is never contacted.
        "SECURE_FILES_PAYMENT_ENABLED": "false",
    }


def ensure_function(zip_bytes: bytes, dry_run: bool) -> str:
    client = lam()
    try:
        client.get_function(FunctionName=FUNCTION_NAME)
        exists = True
    except client.exceptions.ResourceNotFoundException:
        exists = False

    if dry_run:
        return "exists (would update)" if exists else "would create"

    if exists:
        client.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
        client.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
        client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Role=ROLE_ARN,
            Handler="handler.handler",
            Runtime="python3.12",
            Timeout=30,
            MemorySize=512,
            Environment={"Variables": environment()},
        )
        client.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
        return "updated"

    client.create_function(
        FunctionName=FUNCTION_NAME,
        Runtime="python3.12",
        Role=ROLE_ARN,
        Handler="handler.handler",
        Code={"ZipFile": zip_bytes},
        Timeout=30,
        MemorySize=512,
        Architectures=["x86_64"],
        Environment={"Variables": environment()},
        Description="Secure file sharing for wecare.digital/get/secure",
    )
    client.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)
    return "created"


def ensure_alias(dry_run: bool) -> str:
    """Publish a version and point ``live`` at it.

    The HTTP API integrates with the alias, not ``$LATEST``, so nothing reaches
    production until this runs. See .kiro/steering/lambda-snapstart-deploy.md.
    """
    if dry_run:
        return "would publish and move alias"
    client = lam()
    version = client.publish_version(FunctionName=FUNCTION_NAME)["Version"]
    try:
        client.update_alias(
            FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS, FunctionVersion=version
        )
        return f"alias moved -> v{version}"
    except client.exceptions.ResourceNotFoundException:
        client.create_alias(
            FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS, FunctionVersion=version
        )
        return f"alias created -> v{version}"


# ── API Gateway ───────────────────────────────────────────────────────────────

def ensure_routes(dry_run: bool) -> list:
    client = api()
    alias_arn = (
        f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{FUNCTION_NAME}:{LIVE_ALIAS}"
    )
    results = []

    existing_routes = {}
    token = None
    while True:
        kwargs = {"ApiId": API_ID, "MaxResults": "100"}
        if token:
            kwargs["NextToken"] = token
        page = client.get_routes(**kwargs)
        for route in page.get("Items", []):
            existing_routes[route["RouteKey"]] = route
        token = page.get("NextToken")
        if not token:
            break

    if dry_run:
        for method, path in ROUTES:
            key = f"{method} {path}"
            results.append(f"{key}: {'exists' if key in existing_routes else 'would create'}")
        return results

    integration_id = client.create_integration(
        ApiId=API_ID,
        IntegrationType="AWS_PROXY",
        IntegrationUri=alias_arn,
        PayloadFormatVersion="2.0",
        IntegrationMethod="POST",
    )["IntegrationId"]
    target = f"integrations/{integration_id}"

    # one permission for the whole API, so every route can invoke the alias
    try:
        lam().add_permission(
            FunctionName=f"{FUNCTION_NAME}:{LIVE_ALIAS}",
            StatementId="apigw-secure-files",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/*",
        )
    except lam().exceptions.ResourceConflictException:
        pass

    for method, path in ROUTES:
        key = f"{method} {path}"
        if key in existing_routes:
            client.update_route(
                ApiId=API_ID, RouteId=existing_routes[key]["RouteId"], Target=target
            )
            results.append(f"{key}: retargeted")
        else:
            client.create_route(ApiId=API_ID, RouteKey=key, Target=target)
            results.append(f"{key}: created")
    return results


# ── webhook needs the grants table ────────────────────────────────────────────

def ensure_webhook_access(dry_run: bool) -> str:
    """Give wecare-razorpay-webhook the env var and permission to mark grants paid."""
    client = lam()
    try:
        config = client.get_function_configuration(FunctionName=WEBHOOK_FUNCTION)
    except client.exceptions.ResourceNotFoundException:
        return f"{WEBHOOK_FUNCTION} not found - skipped"

    variables = dict((config.get("Environment") or {}).get("Variables") or {})
    role_name = config["Role"].rsplit("/", 1)[-1]

    if variables.get("DOWNLOAD_GRANTS_TABLE") == GRANTS_TABLE:
        env_state = "env already set"
    elif dry_run:
        env_state = "would set env"
    else:
        variables["DOWNLOAD_GRANTS_TABLE"] = GRANTS_TABLE
        client.update_function_configuration(
            FunctionName=WEBHOOK_FUNCTION, Environment={"Variables": variables}
        )
        client.get_waiter("function_updated_v2").wait(FunctionName=WEBHOOK_FUNCTION)
        env_state = "env set"

    if dry_run:
        return f"{env_state}; would add grants-table policy to {role_name}"

    iam().put_role_policy(
        RoleName=role_name,
        PolicyName="wecare-download-grants",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:Query", "dynamodb:UpdateItem"],
                        "Resource": [
                            f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{GRANTS_TABLE}",
                            f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{GRANTS_TABLE}/index/*",
                        ],
                    }
                ],
            }
        ),
    )
    return f"{env_state}; grants policy on {role_name}"


# ── verify ────────────────────────────────────────────────────────────────────

def verify() -> int:
    failures = 0
    client = lam()

    try:
        config = client.get_function_configuration(
            FunctionName=f"{FUNCTION_NAME}:{LIVE_ALIAS}"
        )
        print(f"PASS {FUNCTION_NAME}:{LIVE_ALIAS} {config['Runtime']} {config['State']}")
        variables = (config.get("Environment") or {}).get("Variables") or {}

        if variables.get("SECURE_FILES_PAYMENT_ENABLED", "").lower() in ("1", "true", "yes", "on"):
            print("FAIL payment flag is ON - paid downloads were not meant to be enabled")
            failures += 1
        else:
            print("PASS payment flag off")

        for key in ("SECURE_FILES_BUCKET", "SECURE_FILES_TABLE", "DOWNLOAD_GRANTS_TABLE",
                    "CUSTOMER_USER_POOL_ID", "RAZORPAY_SECRET_ID"):
            if variables.get(key):
                print(f"PASS env {key}")
            else:
                print(f"FAIL env {key} missing")
                failures += 1

        # a credential must never be an env var, only a secret NAME
        for key, value in variables.items():
            if value.startswith("rzp_") or value.startswith("sk_"):
                print(f"FAIL env {key} looks like a credential value")
                failures += 1
    except client.exceptions.ResourceNotFoundException:
        print(f"FAIL {FUNCTION_NAME}:{LIVE_ALIAS} missing")
        failures += 1

    routes = set()
    token = None
    while True:
        kwargs = {"ApiId": API_ID, "MaxResults": "100"}
        if token:
            kwargs["NextToken"] = token
        page = api().get_routes(**kwargs)
        routes.update(r["RouteKey"] for r in page.get("Items", []))
        token = page.get("NextToken")
        if not token:
            break

    for method, path in ROUTES:
        key = f"{method} {path}"
        if key in routes:
            print(f"PASS route {key}")
        else:
            print(f"FAIL route {key} missing")
            failures += 1

    try:
        webhook = client.get_function_configuration(FunctionName=WEBHOOK_FUNCTION)
        variables = (webhook.get("Environment") or {}).get("Variables") or {}
        if variables.get("DOWNLOAD_GRANTS_TABLE") == GRANTS_TABLE:
            print("PASS webhook knows the grants table")
        else:
            print("FAIL webhook DOWNLOAD_GRANTS_TABLE not set")
            failures += 1
    except client.exceptions.ResourceNotFoundException:
        print(f"FAIL {WEBHOOK_FUNCTION} missing")
        failures += 1

    print()
    print("secure files API verified" if not failures else f"{failures} check(s) failed")
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)

    if args.verify:
        return verify()

    print(f"region: {REGION}  api: {API_ID}")
    print(f"dry run: {args.dry_run}\n")
    print(f"role: {ensure_role(args.dry_run)}")
    zip_bytes = package()
    print(f"package: {len(zip_bytes)} bytes")
    print(f"function: {ensure_function(zip_bytes, args.dry_run)}")
    print(f"alias: {ensure_alias(args.dry_run)}")
    for line in ensure_routes(args.dry_run):
        print(f"route {line}")
    print(f"webhook: {ensure_webhook_access(args.dry_run)}")

    if args.dry_run:
        print("\ndry run: nothing changed")
        return 0

    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
