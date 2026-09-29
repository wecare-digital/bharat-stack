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
import time
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
WIX_SITE_ID = "fcd82f0c-9572-49c7-acfb-88fb05042ece"
WIX_ACCOUNT_ID = "15f02319-40ff-4288-b8e6-69c791adae5e"
WIX_CLIENT_ID = "197cd718-e4ec-4e2e-b380-46c297eb18a2"
ROLE_NAME = "wecare-digital-lambda-role"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/{ROLE_NAME}"

#: Where uploaded blog source PDFs land: the existing `wecare-digital-get` bucket, under a
#: new prefix on the PUBLIC root. No bucket is created by this script.
#:
#: `o/` is public - CloudFront E2GP22R4BIFGQ3 serves it at `https://wecare.digital/get/o/...`
#: with no authentication - while `secure/` is denied at the edge. This began as
#: `secure/blog-src/` and moved to `o/` on owner instruction, confirmed a second time on
#: 2026-09-29 to cover derived artefacts as well as sources. The exposure is bounded but
#: real: keys are content hashes or record ids so they cannot be guessed, and listing is not
#: public (all four public-access-block settings are on, and the bucket policy grants
#: s3:GetObject only to the CloudFront service principal) - but every document here,
#: including its extracted text, is readable by anyone holding the URL. These are
#: third-party books and articles, so treat the URL as the secret.
#:
#: Declared above ENV_VARS because ENV_VARS reads it.
SOURCE_BUCKET = "wecare-digital-get"
#: The whole Blog Production tree. Renamed from `o/blog-src/` on 2026-09-29 while the prefix
#: held ZERO objects, which made it a constant change rather than a data migration - and that
#: was the last moment at which it was free. The IAM statement below is scoped to this root,
#: so every sub-prefix (sources/, extracted/, qa/, publish-records/, verification/) is
#: covered without widening to the bucket.
SOURCE_PREFIX = "o/blog-production/"

#: Pure-python wheel, no compiled parts, so it zips straight into the function package -
#: no layer, no Amazon Linux cross-compile. Pinned, and the same version
#: requirements-dev.txt pins, so local extraction and Lambda extraction cannot differ.
PYPDF_VERSION = "6.19.0"

# HTTP API behind wecare.digital/api (stage prod, AutoDeploy on).
# Frontend calls https://wecare.digital/api/seo-tools/{route} (src/api/seo.ts).
API_ID = "zllr9lrg7j"

ENV_VARS = {
    "LOG_LEVEL": "INFO",
    "SEO_TOOLS_TABLE": TABLE_NAME,
    "WEBHOOK_DEDUP_TABLE": DEDUP_TABLE,
    "WIX_SITE_ID": WIX_SITE_ID,
    "WIX_ACCOUNT_ID": WIX_ACCOUNT_ID,
    "WIX_CLIENT_ID": WIX_CLIENT_ID,
    "WIX_BLOG_AUTHOR_NAME": "Anew by WECARE.DIGITAL",
    "BEDROCK_MODEL_ID": "global.anthropic.claude-sonnet-4-6",
    "COGNITO_USER_POOL_ID": "us-east-1_cSx0RHCIR",
    # Blog Production storage, into the existing bucket under o/blog-production/. See
    # SOURCE_PREFIX above for what `o/` being the public root means for these documents.
    "BLOG_SOURCE_BUCKET": SOURCE_BUCKET,
    # AI drafting costs money per call, so it is a cost flag rather than always-on.
    # Enabled here because this function ALREADY invokes Bedrock for ai-seo-audit and
    # already holds the IAM for it - this adds volume to an accepted cost category, not a
    # new one. Turn it off in the SystemConfig cost_flags item without a deploy; the route
    # then answers 409 with the reason instead of silently doing nothing.
    "ENABLE_BEDROCK_ASSIST": "true",
}


#: Blog Production needs one source's batch without reading every source in the system.
#:
#: WHY `INCLUDE` AND NOT `ALL`, unlike the two older indexes. A source item carries
#: `extractPreview` (1,500 characters) and `draftRecord`, and an ALL projection would copy
#: both into the index for data that no listing renders - roughly doubling the storage for the
#: hottest record type. The projected list is exactly what `blog_sources._view` returns plus
#: what `blog_batches.rollup` counts.
#:
#: KEEP THE TWO IN STEP. A field added to `_view` but not projected here reads as EMPTY for
#: batch-scoped queries while working fine for every other query - which is a defect that
#: only shows up on the batches page.
#:
#: AND KEEP IT UNDER 20. DynamoDB refuses an index with more than 20 `NonKeyAttributes`:
#:
#:     ValidationException: Value '[...]' at
#:     'globalSecondaryIndexUpdates.1.member.create.projection.nonKeyAttributes'
#:     failed to satisfy constraint: Member must have length less than or equal to 20
#:
#: The first attempt asked for 24 and was refused at deploy time rather than at test time,
#: which is why `test_the_batch_index_respects_the_twenty_attribute_cap` now asserts it. Both
#: `_view` and this list were trimmed to fit; the six fields that went are on `source_detail`,
#: which reads the whole item and has no projection limit.
MAX_INDEX_NON_KEY_ATTRIBUTES = 20
BATCH_INDEX_NAME = "batchId-createdAt-index"
BATCH_INDEX_DEFINITION = {
    "IndexName": BATCH_INDEX_NAME,
    "KeySchema": [
        {"AttributeName": "batchId", "KeyType": "HASH"},
        {"AttributeName": "createdAt", "KeyType": "RANGE"},
    ],
    "Projection": {
        "ProjectionType": "INCLUDE",
        "NonKeyAttributes": [
            "recordType", "slug", "status", "sourceType", "sourceRef", "s3Key",
            "category", "articleClass", "sourceTitle", "extractedWords", "title",
            "articleStatus", "aiDraftStatus", "gateBlocking", "gateReview", "error",
            "updatedAt",
            #: ONE NAME FOR EVERY DOWNSTREAM STAGE. `blog_sources.PIPELINE_FIELDS` holds
            #: sixteen states - analysis, template, QA, sign-off, publish, verification - and
            #: projecting them individually would need sixteen of the twenty slots. A Map
            #: counts as one attribute, so the cap stops constraining the design.
            #:
            #: Also the reason this landed early: a GSI's projection CANNOT be modified in
            #: place. Widening it means deleting and recreating the index, which is free while
            #: the batch partition holds nothing and a migration once a wave is in flight.
            "pipeline",
            #: Analysis records share this index (same `batchId`), and a batch page reports how
            #: much of the wave has actually been read. `slug` above carries the analysed
            #: source id, so only the version number needs its own slot.
            "version",
        ],
    },
}


def _wait_for_index(ddb, gone: bool = False, attempts: int = 60) -> None:
    for _ in range(attempts):
        indexes = {
            index["IndexName"]: index
            for index in ddb.describe_table(TableName=TABLE_NAME)["Table"].get(
                "GlobalSecondaryIndexes") or []
        }
        found = indexes.get(BATCH_INDEX_NAME)
        if gone and not found:
            return
        if not gone and found and found["IndexStatus"] == "ACTIVE" and not found.get(
                "Backfilling"):
            return
        time.sleep(10)
    raise SystemExit(f"[table] timed out waiting for {BATCH_INDEX_NAME}")


def ensure_batch_index(ddb) -> None:
    """Create the batch index, or replace it when its projection has drifted.

    A GSI is created online: the table stays readable and writable while it backfills, and a
    query against an index still building returns partial results rather than failing. So the
    only ordering requirement is that this runs before anything depends on batch-scoped
    queries returning complete answers, which is why it happens in the deploy rather than
    lazily on first use.

    THE PROJECTION CANNOT BE MODIFIED IN PLACE. DynamoDB offers no "change the projected
    attributes" operation - the only route is delete the index and create it again. That is
    cheap while the partition holds nothing and a real migration once it does, so this refuses
    to do it silently: if the projection has drifted AND the index holds records, it prints
    what is missing and stops rather than dropping an index something is querying.
    """
    indexes = {
        index["IndexName"]: index
        for index in ddb.describe_table(TableName=TABLE_NAME)["Table"].get(
            "GlobalSecondaryIndexes") or []
    }
    found = indexes.get(BATCH_INDEX_NAME)
    if found:
        live = set((found.get("Projection") or {}).get("NonKeyAttributes") or [])
        wanted = set(BATCH_INDEX_DEFINITION["Projection"]["NonKeyAttributes"])
        if live == wanted:
            print(f"[table] GSI {BATCH_INDEX_NAME} already present ({len(live)} attributes)")
            return
        missing = sorted(wanted - live)
        held = int(found.get("ItemCount") or 0)
        print(f"[table] GSI {BATCH_INDEX_NAME} projection drifted; missing={missing} "
              f"extra={sorted(live - wanted)} itemCount={held}")
        if held:
            raise SystemExit(
                f"[table] {BATCH_INDEX_NAME} holds {held} items and its projection cannot be "
                f"changed in place. Recreating it would leave batch-scoped queries returning "
                f"partial results while it backfills. Do it deliberately: delete the index, "
                f"wait, and re-run this script.")
        print(f"[table] recreating {BATCH_INDEX_NAME} (it projects nothing anybody is reading)")
        ddb.update_table(TableName=TABLE_NAME,
                         GlobalSecondaryIndexUpdates=[
                             {"Delete": {"IndexName": BATCH_INDEX_NAME}}])
        _wait_for_index(ddb, gone=True)

    print(f"[table] adding GSI {BATCH_INDEX_NAME} (online, backfills in the background)")
    ddb.update_table(
        TableName=TABLE_NAME,
        AttributeDefinitions=[
            {"AttributeName": "batchId", "AttributeType": "S"},
            {"AttributeName": "createdAt", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexUpdates=[{"Create": BATCH_INDEX_DEFINITION}],
    )
    print(f"[table] GSI {BATCH_INDEX_NAME} creation requested")


def ensure_table() -> None:
    ddb = boto3.client("dynamodb", region_name=REGION)
    try:
        ddb.describe_table(TableName=TABLE_NAME)
        print(f"[table] {TABLE_NAME} already exists — skipping create")
        ensure_batch_index(ddb)
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
            BATCH_INDEX_DEFINITION,
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


def _vendor_pypdf(z: zipfile.ZipFile) -> int:
    """Put pypdf in the package, from the local install rather than a fresh download.

    Resolved from the interpreter running this script, which is the same version
    requirements-dev.txt pins and the same one the local CLI extracts with. That equality
    is the point: if the Lambda extracted with a different pypdf, the same PDF could
    produce different article text depending on which door it came through, and nobody
    would notice until somebody compared two extracts of one document.

    Safe to zip from a Mac because pypdf is pure python - `pypdf-6.19.0-py3-none-any.whl`
    has no compiled parts and no platform tag. Do NOT use this helper for anything with a
    C extension; lxml would need building on Amazon Linux, which is exactly why
    `shared/blog_pipeline.py` parses HTML with the stdlib instead.
    """
    try:
        import pypdf
    except ImportError:
        raise SystemExit(
            f"pypdf is not installed locally. Run:\n"
            f"    python -m pip install pypdf=={PYPDF_VERSION}\n"
            "It is pinned in requirements-dev.txt and is vendored into this package."
        )
    version = getattr(pypdf, "__version__", "?")
    if version != PYPDF_VERSION:
        raise SystemExit(
            f"pypdf {version} is installed but this deploy pins {PYPDF_VERSION}. "
            "Matching versions is what keeps local and Lambda extraction identical."
        )
    root = Path(pypdf.__file__).resolve().parent
    count = 0
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        z.write(path, f"pypdf/{path.relative_to(root).as_posix()}")
        count += 1
    # pypdf ships a py.typed marker; harmless to include and keeps the tree faithful.
    marker = root / "py.typed"
    if marker.exists():
        z.write(marker, "pypdf/py.typed")
    print(f"[package] vendored pypdf {version}: {count} modules")
    return count


def ensure_blog_source_perms() -> None:
    """Additive inline policy for the blog source intake: S3 on one prefix, self-invoke.

    Scoped as narrowly as the two capabilities allow, because this role is SHARED by the
    whole fleet - a wildcard here would widen every other function too.

    - S3 is limited to `o/blog-production/*` in one bucket, and to the three actions the
      pipeline uses. No DeleteObject: nothing here deletes a source, and a source is the
      provenance record for a published article. Note this grants WRITE on a prefix of the
      public root, so the blast radius of a bug in key construction is "publishes a file
      publicly" rather than "overwrites something" - which is why every key is derived from a
      content hash or a record id and cannot collide with the 273 existing objects under `o/`.
    - lambda:InvokeFunction is limited to THIS function, which is all the async worker
      hand-off needs. The worker is reached only through IAM, so this statement is also the
      thing that makes the `blogWorker` branch in the handler unreachable from the internet.
    """
    iam = boto3.client("iam")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BlogSourceObjects",
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:GetObject", "s3:HeadObject"],
                "Resource": f"arn:aws:s3:::{SOURCE_BUCKET}/{SOURCE_PREFIX}*",
            },
            {
                "Sid": "BlogWorkerSelfInvoke",
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{FUNCTION_NAME}",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="seo-blog-source-intake",
        PolicyDocument=json.dumps(policy),
    )
    print(f"[iam] ensured inline policy seo-blog-source-intake on {ROLE_NAME}")


def package() -> bytes:
    """Zip: shim + operations/seo-tools + shared/lambda_utils + blog pipeline + pypdf."""
    shim = FUNCTIONS_DIR / "seo_tools_handler.py"
    seo_dir = FUNCTIONS_DIR / "operations" / "seo-tools"
    lambda_utils = FUNCTIONS_DIR / "shared" / "lambda_utils"
    pipeline = FUNCTIONS_DIR / "shared" / "blog_pipeline.py"
    # The quality gate is SHARED WITH THE CLI rather than reimplemented, which is the only
    # way the browser path and the bulk path can agree on what passes. It is dependency-free
    # by design so it can be dropped into a Lambda package unchanged.
    gate = ROOT / "scripts" / "blog_quality_v2.py"
    for required in (shim, seo_dir, lambda_utils, pipeline, gate):
        assert required.exists(), f"missing {required}"

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
        # Flat at the root, because the shim puts operations/seo-tools on sys.path and
        # these are imported as bare module names (`import blog_pipeline`,
        # `import blog_quality_v2`) from handler-local code.
        z.write(pipeline, "blog_pipeline.py")
        z.write(gate, "blog_quality_v2.py")
        _vendor_pypdf(z)
    data = buf.getvalue()
    print(f"[package] built zip: {len(data)} bytes")
    if len(data) > 50 * 1024 * 1024:
        raise SystemExit("package exceeds the 50MB direct-upload limit; use S3 instead")
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
        current = lam.get_function_configuration(FunctionName=FUNCTION_NAME)
        current_env = (current.get("Environment") or {}).get("Variables") or {}
        config["Environment"] = {"Variables": {**current_env, **ENV_VARS}}
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
    """Wire https://wecare.digital/api/seo-tools/* -> wecare-seo-tools (idempotent)."""
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
    ensure_blog_source_perms()
    zip_bytes = package()
    deploy_lambda(zip_bytes)
    ensure_api_route()
    print("=== done ===")
    print(f"Endpoint: https://wecare.digital/api/seo-tools/  (stage prod, auto-deploy)")


if __name__ == "__main__":
    main()
