#!/usr/bin/env python3
"""Deploy WECARE.DIGITAL site-language Lambda and API routes.

Idempotent direct-AWS deployment, following the repository's existing model for
Python Lambdas that are not owned by Amplify Gen 2.
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import boto3

REGION = "us-east-1"
ACCOUNT = "775261844268"
API_ID = "zllr9lrg7j"  # HTTP API behind api.wecare.digital
FUNCTION_NAME = "wecare-site-language"
ROLE_NAME = "wecare-digital-lambda-role"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE_NAME}"
TABLE_NAME = "stack-wecare-digital-SiteLanguageCache"
HANDLER = Path("amplify/functions/core/site-language/handler.py")

# Browser origins allowed to call the service. stack.wecare.digital is included
# because the Cloud Run language relay refuses it with a 403, which is why this
# AWS service exists.
ALLOWED_ORIGINS = [
    "https://www.wecare.digital",
    "https://wecare.digital",
    "https://stack.wecare.digital",
]

# Throttle applied to the site-language routes ONLY.
SITE_LANGUAGE_RATE_LIMIT = 15.0
SITE_LANGUAGE_BURST_LIMIT = 30


def ensure_table() -> None:
    ddb = boto3.client("dynamodb", region_name=REGION)
    try:
        ddb.describe_table(TableName=TABLE_NAME)
        print(f"[ddb] table exists: {TABLE_NAME}")
    except ddb.exceptions.ResourceNotFoundException:
        ddb.create_table(
            TableName=TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": "cacheKey", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "cacheKey", "KeyType": "HASH"}],
        )
        ddb.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        print(f"[ddb] created: {TABLE_NAME}")

    ttl = ddb.describe_time_to_live(TableName=TABLE_NAME).get("TimeToLiveDescription", {})
    if ttl.get("TimeToLiveStatus") not in ("ENABLED", "ENABLING"):
        ddb.update_time_to_live(
            TableName=TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "expiresAt"},
        )
        print("[ddb] enabled TTL on expiresAt")


def ensure_role_policy() -> None:
    iam = boto3.client("iam", region_name=REGION)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["translate:ListLanguages", "translate:TranslateText"],
                "Resource": "*",
            },
            {
                # Amazon Translate implements SourceLanguageCode="auto" by
                # calling Comprehend on the caller's behalf, so auto-detect
                # fails with AccessDenied without this. Deep testing caught it:
                # every request that omitted sourceLanguage returned 500.
                "Effect": "Allow",
                "Action": ["comprehend:DetectDominantLanguage"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": ["polly:DescribeVoices", "polly:SynthesizeSpeech"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem"],
                "Resource": f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{TABLE_NAME}",
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{FUNCTION_NAME}:*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="wecare-site-language",
        PolicyDocument=json.dumps(policy),
    )
    print(f"[iam] ensured inline policy on {ROLE_NAME}")


def package() -> bytes:
    if not HANDLER.exists():
        raise SystemExit(f"missing {HANDLER}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(HANDLER, "handler.py")
    return buffer.getvalue()


def deploy_lambda(zip_bytes: bytes) -> str:
    lam = boto3.client("lambda", region_name=REGION)
    # AWS_REGION is deliberately absent: Lambda reserves it and rejects any
    # attempt to set it. The runtime provides it, and the handler defaults to
    # us-east-1 regardless.
    env = {
        "SITE_LANGUAGE_CACHE_TABLE": TABLE_NAME,
        "SITE_LANGUAGE_ALLOWED_ORIGINS": ",".join(ALLOWED_ORIGINS),
        "SITE_LANGUAGE_CACHE_TTL_SECONDS": str(90 * 24 * 3600),
        "SITE_LANGUAGE_MAX_TEXTS": "40",
        "SITE_LANGUAGE_MAX_TEXT_BYTES": "9000",
        "SITE_LANGUAGE_MAX_TOTAL_BYTES": "30000",
        "SITE_LANGUAGE_MAX_TTS_CHARS": "2800",
    }

    try:
        current = lam.get_function(FunctionName=FUNCTION_NAME)
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes, Publish=False)
        waiter = lam.get_waiter("function_updated_v2")
        waiter.wait(FunctionName=FUNCTION_NAME)
        lam.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Role=ROLE_ARN,
            Handler="handler.handler",
            Runtime="python3.12",
            Timeout=30,
            MemorySize=512,
            Environment={"Variables": env},
        )
        waiter.wait(FunctionName=FUNCTION_NAME)
        arn = current["Configuration"]["FunctionArn"]
        print(f"[lambda] updated {FUNCTION_NAME}")
        return arn
    except lam.exceptions.ResourceNotFoundException:
        created = lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=ROLE_ARN,
            Handler="handler.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=512,
            Environment={"Variables": env},
            Description="WECARE.DIGITAL dynamic site translation and Polly TTS",
            Publish=False,
        )
        lam.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)
        print(f"[lambda] created {FUNCTION_NAME}")
        return created["FunctionArn"]


def ensure_api_routes(function_arn: str) -> None:
    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    integration_id = None
    for item in api.get_integrations(ApiId=API_ID, MaxResults="500").get("Items", []):
        if FUNCTION_NAME in (item.get("IntegrationUri") or ""):
            integration_id = item["IntegrationId"]
            break
    if not integration_id:
        integration_id = api.create_integration(
            ApiId=API_ID,
            IntegrationType="AWS_PROXY",
            IntegrationUri=function_arn,
            IntegrationMethod="POST",
            PayloadFormatVersion="2.0",
            TimeoutInMillis=29000,
        )["IntegrationId"]
        print(f"[api] created integration {integration_id}")
    else:
        print(f"[api] reusing integration {integration_id}")

    target = f"integrations/{integration_id}"
    existing = {
        row["RouteKey"]: row
        for row in api.get_routes(ApiId=API_ID, MaxResults="1000").get("Items", [])
    }
    route_keys = [
        "GET /site-language/languages",
        "POST /site-language/translate",
        "GET /site-language/voices",
        "POST /site-language/tts",
        "OPTIONS /site-language/{proxy+}",
    ]
    for route_key in route_keys:
        if route_key not in existing:
            api.create_route(ApiId=API_ID, RouteKey=route_key, Target=target, AuthorizationType="NONE")
            print(f"[api] created route: {route_key}")
        else:
            print(f"[api] route exists: {route_key}")

    # Limit public spend at the API layer as a second guard behind the request
    # size caps in the handler.
    #
    # This MUST be per-route. DefaultRouteSettings is the fallback for every
    # route on the stage, and prod currently serves 100 rps / burst 200 across
    # WhatsApp inbound, Razorpay webhooks, SMS and voice. Lowering the default
    # to protect one new endpoint would throttle all of production by 85%.
    stage = api.get_stage(ApiId=API_ID, StageName="prod")
    existing_settings = dict(stage.get("RouteSettings") or {})
    desired = dict(existing_settings)
    for route_key in route_keys:
        desired[route_key] = {
            **(existing_settings.get(route_key) or {}),
            "ThrottlingBurstLimit": SITE_LANGUAGE_BURST_LIMIT,
            "ThrottlingRateLimit": SITE_LANGUAGE_RATE_LIMIT,
        }

    if desired != existing_settings:
        api.update_stage(ApiId=API_ID, StageName="prod", RouteSettings=desired)
        print(
            f"[api] throttled the {len(route_keys)} site-language routes to "
            f"{SITE_LANGUAGE_RATE_LIMIT:g} rps / burst {SITE_LANGUAGE_BURST_LIMIT}"
        )
    else:
        print("[api] per-route throttling already in place")

    default_settings = stage.get("DefaultRouteSettings") or {}
    print(
        "[api] stage default left untouched at "
        f"{default_settings.get('ThrottlingRateLimit')} rps / "
        f"burst {default_settings.get('ThrottlingBurstLimit')}"
    )

    source_arn = f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/*/site-language/*"
    try:
        lam.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="apigw-site-language",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn,
        )
        print("[lambda] added API Gateway invoke permission")
    except lam.exceptions.ResourceConflictException:
        print("[lambda] API Gateway invoke permission already exists")


def main() -> None:
    print("=== deploy WECARE site language ===")
    ensure_table()
    ensure_role_policy()
    # IAM policy propagation can be briefly eventual after first creation/update.
    time.sleep(2)
    arn = deploy_lambda(package())
    ensure_api_routes(arn)
    print("=== done ===")
    print("Endpoints: https://api.wecare.digital/site-language/*")


if __name__ == "__main__":
    main()
