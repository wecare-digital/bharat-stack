#!/usr/bin/env python3
"""One-time provisioning for wecare-elevenlabs-webhook.

scripts/deploy_all_lambdas.py deliberately refuses to create functions - it only
moves $LATEST on functions that already exist, so a typo in the function map
cannot silently conjure a new Lambda. That makes it the wrong tool for the first
deploy of a new function, which is what this script is for. After this runs once,
deploy_all_lambdas.py owns the function like any other.

What it creates, all idempotent - re-running is safe and reports "exists":

  1. Lambda wecare-elevenlabs-webhook   python3.12 / x86_64 / 256MB / 15s
                                        role wecare-digital-lambda-role
  2. a published version + the `live` alias, because every HTTP API integration
     in this fleet invokes the alias, not $LATEST
  3. HTTP API integration (AWS_PROXY, payload 2.0) pointing at the alias
  4. route  POST /elevenlabs/webhook  on api zllr9lrg7j
  5. the lambda:InvokeFunction permission API Gateway needs, scoped to this
     route rather than the whole API

The route is AuthorizationType=NONE because ElevenLabs cannot present a SigV4
signature or a JWT. Authentication is the HMAC signature the handler verifies;
see the module docstring in the handler for why it fails closed when the signing
secret is absent. That combination - public route, in-handler HMAC - is the same
shape as POST /plivo/answer.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_all_lambdas import Spec, build_zip  # noqa: E402

REGION = "us-east-1"
ACCOUNT = "775261844268"
API_ID = "zllr9lrg7j"
FUNCTION = "wecare-elevenlabs-webhook"
ROUTE_KEY = "POST /elevenlabs/webhook"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/wecare-digital-lambda-role"
SPEC = Spec(FUNCTION, "messaging/elevenlabs-webhook")

ENV = {
    "VOICE_CDR_TABLE": "stack-wecare-digital-VoiceCDRTable",
    "ELEVENLABS_SECRET_ID": "wecare/elevenlabs",
    "ELEVENLABS_SIGNING_FIELD": "webhook_secret",
    "ELEVENLABS_MAX_SKEW": "1800",
    "LOG_LEVEL": "INFO",
}


def main() -> int:
    lam = boto3.client("lambda", region_name=REGION)
    api = boto3.client("apigatewayv2", region_name=REGION)

    zip_bytes, members = build_zip(SPEC)
    print(f"package: {len(zip_bytes)} bytes, {len(members)} members")

    # ---- 1. function ------------------------------------------------------
    try:
        lam.get_function(FunctionName=FUNCTION)
        print(f"  function {FUNCTION} exists -> updating code")
        lam.update_function_code(FunctionName=FUNCTION, ZipFile=zip_bytes, Publish=False)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        lam.create_function(
            FunctionName=FUNCTION,
            Runtime="python3.12",
            Role=ROLE,
            Handler="handler.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=15,
            MemorySize=256,
            Architectures=["x86_64"],
            Environment={"Variables": ENV},
            Description="ElevenLabs post-call webhook receiver. HMAC-verified, "
                        "fails closed without a signing secret.",
        )
        print(f"  function {FUNCTION} CREATED")

    for _ in range(60):
        cfg = lam.get_function_configuration(FunctionName=FUNCTION)
        if cfg["State"] == "Active" and cfg.get("LastUpdateStatus") != "InProgress":
            break
        time.sleep(2)
    else:
        sys.exit("function did not reach Active")
    print(f"  state={cfg['State']}  lastUpdate={cfg.get('LastUpdateStatus')}")

    # env may drift on an existing function; make it match
    if (cfg.get("Environment") or {}).get("Variables") != ENV:
        lam.update_function_configuration(FunctionName=FUNCTION,
                                          Environment={"Variables": ENV})
        print("  environment updated")
        time.sleep(3)

    # ---- 2. version + live alias ------------------------------------------
    version = lam.publish_version(FunctionName=FUNCTION)["Version"]
    print(f"  published version {version}")
    try:
        lam.update_alias(FunctionName=FUNCTION, Name="live", FunctionVersion=version)
        print(f"  alias live -> {version} (updated)")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        lam.create_alias(FunctionName=FUNCTION, Name="live", FunctionVersion=version)
        print(f"  alias live -> {version} (created)")

    alias_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{FUNCTION}:live"

    # ---- 3. integration ---------------------------------------------------
    existing = [i for i in api.get_integrations(ApiId=API_ID, MaxResults="500")["Items"]
                if i.get("IntegrationUri") == alias_arn]
    if existing:
        integration_id = existing[0]["IntegrationId"]
        print(f"  integration exists: {integration_id}")
    else:
        integration_id = api.create_integration(
            ApiId=API_ID, IntegrationType="AWS_PROXY", IntegrationMethod="POST",
            IntegrationUri=alias_arn, PayloadFormatVersion="2.0",
            TimeoutInMillis=30000, ConnectionType="INTERNET",
        )["IntegrationId"]
        print(f"  integration CREATED: {integration_id}")

    # ---- 4. route ---------------------------------------------------------
    routes = {r["RouteKey"]: r for r in api.get_routes(ApiId=API_ID, MaxResults="500")["Items"]}
    if ROUTE_KEY in routes:
        route = routes[ROUTE_KEY]
        if route.get("Target") != f"integrations/{integration_id}":
            api.update_route(ApiId=API_ID, RouteId=route["RouteId"],
                             Target=f"integrations/{integration_id}")
            print(f"  route {ROUTE_KEY} retargeted")
        else:
            print(f"  route {ROUTE_KEY} exists")
    else:
        api.create_route(ApiId=API_ID, RouteKey=ROUTE_KEY,
                         Target=f"integrations/{integration_id}",
                         AuthorizationType="NONE")
        print(f"  route {ROUTE_KEY} CREATED (AuthorizationType=NONE; HMAC is the gate)")

    # ---- 5. invoke permission --------------------------------------------
    method, path = ROUTE_KEY.split(" ", 1)
    source_arn = f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/{method}{path}"
    try:
        lam.add_permission(
            FunctionName=FUNCTION, Qualifier="live",
            StatementId="apigw-elevenlabs-webhook",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn,
        )
        print(f"  invoke permission added for {source_arn}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print("  invoke permission already present")

    print(f"\nDONE. https://api.wecare.digital{path}")
    print("  next: register the webhook in ElevenLabs and store the returned")
    print("        signing secret at wecare/elevenlabs.webhook_secret")
    return 0


if __name__ == "__main__":
    sys.exit(main())
