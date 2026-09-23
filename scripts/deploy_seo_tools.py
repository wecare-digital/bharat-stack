"""Deploy the wecare-seo-tools Lambda + SeoToolsTable via boto3 (Docker-free).

Mirrors amplify/seo-resources.ts but deploys directly — like scripts/deploy_task12.py —
because CI builds frontend only and does NOT run `ampx pipeline-deploy`. The Gen2
backend + 42+ Lambdas are all managed this way and already exist in AWS.

Idempotent: safe to re-run. Creates on first run, updates code+config afterward.

What it does:
  1. Create DynamoDB `stack-wecare-digital-SeoToolsTable` (PK id, 2 GSIs, PAY_PER_REQUEST, PITR).
  2. Add an additive Bedrock inference-profile inline policy to the shared lambda role
     (ai.py uses cross-region `global.anthropic.*` profiles the role didn't cover).
  3. Package the Lambda (shim + operations/seo-tools + shared/lambda_utils) and
     create/update `wecare-seo-tools` (python3.12, handler seo_tools_handler.handler).

Usage:  python scripts/deploy_seo_tools.py
"""
import io
import json
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT = "775261844268"
ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS_DIR = ROOT / "amplify" / "functions"

FUNCTION_NAME = "wecare-seo-tools"
TABLE_NAME = "stack-wecare-digital-SeoToolsTable"
DEDUP_TABLE = "stack-wecare-digital-WebhookDedup"
WIX_SECRET_NAME = "wecare/wix/headless-api-key"
WIX_SITE_ID = "fcd82f0c-9572-49c7-acfb-88fb05042ece"
WIX_ACCOUNT_ID = "15f02319-40ff-4288-b8e6-69c791adae5e"
ROLE_NAME = "wecare-digital-lambda-role"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE_NAME}"

# HTTP API behind api.wecare.digital (stage prod, AutoDeploy on).
# Frontend calls https://api.wecare.digital/seo-tools/{route} (src/api/seo.ts).
API_ID = "zllr9lrg7j"

ENV_VARS = {
    "LOG_LEVEL": "INFO",
    "SEO_TOOLS_TABLE": TABLE_NAME,
    "WEBHOOK_DEDUP_TABLE": DEDUP_TABLE,
    "WIX_API_KEY_SECRET": WIX_SECRET_NAME,
    "WIX_SITE_ID": WIX_SITE_ID,
    "WIX_ACCOUNT_ID": WIX_ACCOUNT_ID,
    "WIX_BLOG_AUTHOR_NAME": "Anew by WECARE.DIGITAL",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-4-6",
    "COGNITO_USER_POOL_ID": "us-east-1_cSx0RHCIR",
}


def ensure_table() -> None:
    ddb = boto3.client("dynamodb", region_name=REGION)
    try:
        ddb.describe_table(TableName=TABLE_NAME)
        print(f"[table] {TABLE_NAME} already exists — skipping create")
        return
    except ddb.exceptions.ResourceNotFoundException:
        pass

    print(f"[table] creating {TABLE_NAME} ...")
    ddb.create_table(
        TableName=TABLE_NAME,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "recordType", "AttributeType": "S"},
            {"AttributeName": "createdAt", "AttributeType": "S"},
            {"AttributeName": "slug", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "recordType-createdAt-index",
                "KeySchema": [
                    {"AttributeName": "recordType", "KeyType": "HASH"},
                    {"AttributeName": "createdAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "slug-createdAt-index",
                "KeySchema": [
                    {"AttributeName": "slug", "KeyType": "HASH"},
                    {"AttributeName": "createdAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )
    ddb.get_waiter("table_exists").wait(TableName=TABLE_NAME)
    ddb.update_continuous_backups(
        TableName=TABLE_NAME,
        PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True},
    )
    print(f"[table] {TABLE_NAME} ACTIVE with PITR enabled")


def ensure_bedrock_inference_profile_perms() -> None:
    """Additive inline policy so ai.py's cross-region `global.*` profiles can invoke."""
    iam = boto3.client("iam")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockInferenceProfiles",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                "Resource": [
                    f"arn:aws:bedrock:*:{ACCOUNT}:inference-profile/*",
                    f"arn:aws:bedrock:*:{ACCOUNT}:application-inference-profile/*",
                    "arn:aws:bedrock:*::foundation-model/*",
                ],
            }
        ],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="seo-bedrock-inference-profiles",
        PolicyDocument=json.dumps(policy),
    )
    print(f"[iam] ensured inline policy seo-bedrock-inference-profiles on {ROLE_NAME}")


def ensure_wix_secret_perms() -> None:
    """Grant this Lambda read access only to the Wix Headless API-key secret."""
    iam = boto3.client("iam")
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "ReadWixHeadlessApiKey",
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:{WIX_SECRET_NAME}*",
        }],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="seo-wix-headless-secret-read",
        PolicyDocument=json.dumps(policy),
    )
    print(f"[iam] ensured Wix secret read policy on {ROLE_NAME}")


def package() -> bytes:
    """Zip: shim at root + operations/seo-tools + shared/lambda_utils (+ static KB)."""
    shim = FUNCTIONS_DIR / "seo_tools_handler.py"
    seo_dir = FUNCTIONS_DIR / "operations" / "seo-tools"
    lambda_utils = FUNCTIONS_DIR / "shared" / "lambda_utils"
    assert shim.exists(), f"missing {shim}"
    assert seo_dir.exists(), f"missing {seo_dir}"
    assert lambda_utils.exists(), f"missing {lambda_utils}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(shim, "seo_tools_handler.py")
        for f in sorted(seo_dir.glob("*.py")):
            z.write(f, f"operations/seo-tools/{f.name}")
        for f in sorted(lambda_utils.glob("*.py")):
            z.write(f, f"shared/lambda_utils/{f.name}")
        skb = FUNCTIONS_DIR / "shared" / "static_knowledge_base.py"
        if skb.exists():
            z.write(skb, "shared/static_knowledge_base.py")
    data = buf.getvalue()
    print(f"[package] built zip: {len(data)} bytes")
    return data


def deploy_lambda(zip_bytes: bytes) -> None:
    lam = boto3.client("lambda", region_name=REGION)
    config = dict(
        Runtime="python3.12",
        Role=ROLE_ARN,
        Handler="seo_tools_handler.handler",
        Timeout=120,
        MemorySize=512,
        Environment={"Variables": ENV_VARS},
    )
    try:
        lam.get_function(FunctionName=FUNCTION_NAME)
        exists = True
    except lam.exceptions.ResourceNotFoundException:
        exists = False

    if exists:
        print(f"[lambda] {FUNCTION_NAME} exists — updating code + config")
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
        lam.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
        lam.update_function_configuration(FunctionName=FUNCTION_NAME, **config)
        lam.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION_NAME)
    else:
        print(f"[lambda] creating {FUNCTION_NAME}")
        lam.create_function(
            FunctionName=FUNCTION_NAME,
            Code={"ZipFile": zip_bytes},
            Architectures=["x86_64"],
            Publish=False,
            **config,
        )
        lam.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)

    cfg = lam.get_function_configuration(FunctionName=FUNCTION_NAME)
    print(f"[lambda] {FUNCTION_NAME} {cfg['State']} / {cfg.get('LastUpdateStatus')} "
          f"(runtime={cfg['Runtime']}, mem={cfg['MemorySize']}, timeout={cfg['Timeout']})")


def ensure_api_route() -> None:
    """Wire https://api.wecare.digital/seo-tools/* -> wecare-seo-tools (idempotent)."""
    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    fn_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{FUNCTION_NAME}"

    # 1) Integration (reuse if one already targets this function)
    integ_id = None
    for it in api.get_integrations(ApiId=API_ID, MaxResults="500").get("Items", []):
        if FUNCTION_NAME in (it.get("IntegrationUri") or ""):
            integ_id = it["IntegrationId"]
            break
    if integ_id:
        print(f"[api] reusing integration {integ_id}")
    else:
        integ_id = api.create_integration(
            ApiId=API_ID,
            IntegrationType="AWS_PROXY",
            IntegrationUri=fn_arn,
            IntegrationMethod="POST",
            PayloadFormatVersion="2.0",
        )["IntegrationId"]
        print(f"[api] created integration {integ_id}")

    # 2) Routes (ANY covers GET/POST/PUT/DELETE/OPTIONS; handler does its own auth)
    target = f"integrations/{integ_id}"
    existing = {r["RouteKey"] for r in api.get_routes(ApiId=API_ID, MaxResults="1000").get("Items", [])}
    for rk in ["ANY /seo-tools", "ANY /seo-tools/{proxy+}"]:
        if rk in existing:
            print(f"[api] route exists: {rk}")
        else:
            api.create_route(ApiId=API_ID, RouteKey=rk, Target=target, AuthorizationType="NONE")
            print(f"[api] created route: {rk}")

    # 3) Allow API Gateway to invoke the Lambda
    for sid, res in [
        ("apigw-seo-tools-base", "seo-tools"),
        ("apigw-seo-tools-proxy", "seo-tools/*"),
    ]:
        try:
            lam.add_permission(
                FunctionName=FUNCTION_NAME,
                StatementId=sid,
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/*/{res}",
            )
            print(f"[api] added invoke permission {sid}")
        except lam.exceptions.ResourceConflictException:
            print(f"[api] invoke permission {sid} already present")


def main() -> None:
    print("=== deploy wecare-seo-tools ===")
    ensure_table()
    ensure_bedrock_inference_profile_perms()
    ensure_wix_secret_perms()
    zip_bytes = package()
    deploy_lambda(zip_bytes)
    ensure_api_route()
    print("=== done ===")
    print(f"Endpoint: https://api.wecare.digital/seo-tools/  (stage prod, auto-deploy)")


if __name__ == "__main__":
    main()
