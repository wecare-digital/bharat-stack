#!/usr/bin/env python3
"""Provision the TWO gift-card execution roles, the pinned cryptography layer, and the two alarms.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
sections 5.1.1 (the layer), 6.5 (the two detectors) and 10.1 (the scoped IAM), plus DECISION 6 of
that task's `plan.md`.

TWO FUNCTIONS, TWO ROLES, AND THE DIFFERENCES ARE THE WHOLE POINT
-----------------------------------------------------------------
|  | `wecare-gift-cards` | `wecare-wix-giftcard-spi` | Why |
|---|---|---|---|
| `dynamodb:DeleteItem` | **yes** | **no** | only the staff/customer function releases a `GCHOLD#` row; the SPI has no reason to delete anything, and a card, transaction or pointer row is never deleted by either |
| `UpdateItem` on PaymentAttemptsTable | **no** | **yes** | the SPI writes `GC_VOIDED` through `advance()`; issuance never touches a payment attempt |
| reachable by Wix | no | **yes**, with no API Gateway authorizer | which is exactly why issuance is not in that function |

NEITHER IS `wecare-digital-lambda-role`
---------------------------------------
That shared fleet role is attached to ~65 functions, so a statement added there would grant every one
of them access to a liability ledger. Nothing in this script touches it.

WHY THE SPI ROLE CANNOT ISSUE A CARD, AND WHY IAM IS NOT WHAT STOPS IT
----------------------------------------------------------------------
`PutItem` on `GiftCardsTable` is identical in both roles, because the SPI MUST write `GCTXN#`,
`GCTXNID#` and `GCORDER#` rows - so a permission boundary cannot distinguish issuance from a
transaction record. The guarantee is STRUCTURAL: issuance lives in `gift_card_store.issue`, which is
called only from `wecare-gift-cards`' handler, and the SPI handler has no code path to it. Stated
here so nobody later reads "both can PutItem" as a finding.

ONE SECRET, BOTH FUNCTIONS
--------------------------
`wecare/wix/giftcard-spi` carries `public_key`, `app_id`, `instance_id` and `code_pepper`. Both
functions need `code_pepper` to derive `codeHash`; only the SPI needs `public_key`. Splitting it was
considered and rejected: the pepper is the field BOTH need, so a split would mean two secrets with
overlapping contents and two rotation procedures. The ARN pattern ends `-*` because Secrets Manager
appends a six-character suffix to every secret ARN, and a pattern without it matches nothing.

Nothing here reads a secret VALUE. The grant is for the FUNCTION at runtime, which is the only place
a secret value is permitted to exist, and `secretsmanager get-secret-value` is never called from a
shell.

DECISION 6 - THE KMS GRANTS
---------------------------
The table is encrypted with the customer-managed key behind `alias/wecare-gift-cards`, so each role
additionally needs `kms:Decrypt` and `kms:GenerateDataKey` - conditioned on
`kms:ViaService = dynamodb.us-east-1.amazonaws.com`, so the grant is "use the key through DynamoDB"
rather than "decrypt anything under this key". Named by ALIAS in the policy's resource is not
possible (a policy resource must be a key ARN), so the ARN is resolved at apply time from the alias
and `--verify` re-resolves it rather than trusting a stored copy.

THE LAYER IS VERSION-PINNED, DELIBERATELY
-----------------------------------------
    arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1

A layer version is immutable, so pinning means the verifier's crypto implementation cannot change
under it without a deliberate edit here. A floating reference would let a layer republish alter
signature verification on a payment route with no code change and no review. The same layer already
serves `wecare-whatsapp-business-api`'s RSA work, so the capability is proven on this runtime in this
account.

Usage:
    python scripts/provision_gift_cards_roles.py              # dry run, the default
    python scripts/provision_gift_cards_roles.py --apply
    python scripts/provision_gift_cards_roles.py --apply --alarms
    python scripts/provision_gift_cards_roles.py --verify
"""

from __future__ import annotations

import argparse
import json

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

#: The one account this project uses. Not a credential - an account id is public in every ARN this
#: repository already commits.
ACCOUNT_ID = "775261844268"

GIFT_CARDS_FUNCTION = "wecare-gift-cards"
SPI_FUNCTION = "wecare-wix-giftcard-spi"

GIFT_CARDS_ROLE = "wecare-gift-cards-role"
SPI_ROLE = "wecare-wix-giftcard-spi-role"

GIFT_CARDS_POLICY = "wecare-gift-cards-table"
SPI_POLICY = "wecare-wix-giftcard-spi-tables"

LOG_RETENTION_DAYS = 30

GIFT_CARDS_TABLE = "stack-wecare-digital-GiftCardsTable"
PAYMENT_ATTEMPTS_TABLE = "stack-wecare-digital-PaymentAttemptsTable"
STATUS_INDEX = "status-index"
SPI_SECRET = "wecare/wix/giftcard-spi"

KMS_ALIAS = "alias/wecare-gift-cards"

#: VERSION PINNED. See the module docstring.
CRYPTOGRAPHY_LAYER_ARN = (
    f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:layer:cryptography-python312:1")

#: The two section 6.5 detectors. A single occurrence of either is actionable, which is why the
#: threshold is 1 rather than a rate.
METRIC_NAMESPACE = "WecareGiftCards"
ALARMS = (
    {
        "name": "wecare-gift-card-wix-spi-redemption",
        "metric": "WixSpiRedemption",
        "description": ("Wix called our /v1/redeem. Section 1.3 predicts this never happens, so a "
                        "single occurrence means that prediction is wrong and the two-namespace "
                        "double-spend analysis needs revisiting."),
    },
    {
        "name": "wecare-gift-card-charge-mismatch",
        "metric": "ChargedVsCapturedMismatch",
        "description": ("razorpayChargedPaise disagrees with verifiedCapturedPaise on a payment "
                        "attempt: either a gateway anomaly or a tampered split."),
    },
)

#: The SNS topic the account's existing alarms route to, resolved by name so this script does not
#: carry a dated ARN.
ALARM_TOPIC_NAME = "wecare-alerts"


def iam():
    return boto3.client("iam")


def logs():
    return boto3.client("logs", region_name=REGION)


def lam():
    return boto3.client("lambda", region_name=REGION)


def kms():
    return boto3.client("kms", region_name=REGION)


def cloudwatch():
    return boto3.client("cloudwatch", region_name=REGION)


def sns():
    return boto3.client("sns", region_name=REGION)


def table_arn(name: str) -> str:
    return f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{name}"


def index_arn(name: str, index: str = STATUS_INDEX) -> str:
    return f"{table_arn(name)}/index/{index}"


def secret_arn() -> str:
    """The secret ARN pattern. A NAME, never a value.

    The trailing `-*` is Secrets Manager's six-character suffix, which is part of the ARN and is not
    known until the secret is created - so the wildcard is the documented way to name ONE secret,
    not a widening to all of them.
    """
    return f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:{SPI_SECRET}-*"


def log_group(function: str) -> str:
    return f"/aws/lambda/{function}"


def kms_key_arn() -> str:
    """Resolve `alias/wecare-gift-cards` to a key ARN, or `""`.

    Resolved rather than stored. A policy resource must be a key ARN, and the ARN does not exist
    until the key is created - which is exactly why the table, the policies and this script all
    agree on the ALIAS and derive the ARN from it.
    """
    try:
        return kms().describe_key(KeyId=KMS_ALIAS)["KeyMetadata"]["Arn"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NotFoundException",
                                                         "AccessDeniedException"):
            return ""
        raise


def trust_policy() -> dict:
    """Lambda may assume the role, but only on behalf of THIS account.

    Without `aws:SourceAccount` the Lambda service principal is a confused-deputy opening: any
    account's function could, in principle, be used to assume it.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT_ID}},
        }],
    }


def kms_statement(key_arn: str) -> dict:
    """DECISION 6. Use the key THROUGH DynamoDB, and in no other way.

    Without `kms:ViaService` the grant would let the function decrypt arbitrary ciphertext under this
    key, which is a strictly wider capability than reading the table it exists to encrypt.
    """
    return {
        "Sid": "UseGiftCardTableKeyThroughDynamoDBOnly",
        "Effect": "Allow",
        "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
        "Resource": [key_arn or f"arn:aws:kms:{REGION}:{ACCOUNT_ID}:key/*"],
        "Condition": {"StringEquals": {
            "kms:ViaService": f"dynamodb.{REGION}.amazonaws.com"}},
    }


def gift_cards_policy(key_arn: str = "") -> dict:
    """`wecare-gift-cards-role`'s inline policy, built with no AWS call.

    A pure function on purpose: `tests/test_gift_cards_iam_and_table.py` asserts over this exact
    document offline, so the policy that is TESTED is the policy that is WRITTEN rather than a
    transcription of it.

    `DeleteItem` is here for exactly one reason: releasing a `GCHOLD#` row. An IAM policy cannot be
    narrowed below item granularity, so the restriction that actually holds is in code -
    `gift_card_store` has exactly one `delete_item` call site, it is `_delete_hold`, and
    `tests/test_gift_card_store.py` enumerates the delete sites to keep it that way.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "GiftCardLedger",
                "Effect": "Allow",
                # No Scan: every access in `gift_card_store` is an exact-key operation or the
                # status-index Query.
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                           "dynamodb:DeleteItem", "dynamodb:Query"],
                "Resource": [table_arn(GIFT_CARDS_TABLE), index_arn(GIFT_CARDS_TABLE)],
            },
            kms_statement(key_arn),
            {
                "Sid": "ReadGiftCardSpiSecret",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [secret_arn()],
            },
            {
                "Sid": "OwnLogGroup",
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:"
                    f"{log_group(GIFT_CARDS_FUNCTION)}",
                    f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:"
                    f"{log_group(GIFT_CARDS_FUNCTION)}:*",
                ],
            },
        ],
    }


def spi_policy(key_arn: str = "") -> dict:
    """`wecare-wix-giftcard-spi-role`'s inline policy, built with no AWS call.

    Two asymmetries against the other role, both deliberate: NO `DeleteItem` anywhere, and
    `UpdateItem` on `PaymentAttemptsTable` for the `GC_VOIDED` write. That second grant is for a
    call that can actually be composed, which is what DECISION 9 bought by putting
    `paymentAttemptId` on the `GCTXNID#` pointer row - without it the grant would be privilege for
    an unreachable code path.

    No `Query` on `PaymentAttemptsTable`: the SPI reaches an attempt only by its exact
    `paymentAttemptId`.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "GiftCardLedgerNoDelete",
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                           "dynamodb:Query"],
                "Resource": [table_arn(GIFT_CARDS_TABLE), index_arn(GIFT_CARDS_TABLE)],
            },
            {
                "Sid": "AdvanceGiftCardStageOnAPaymentAttempt",
                "Effect": "Allow",
                "Action": ["dynamodb:UpdateItem"],
                "Resource": [table_arn(PAYMENT_ATTEMPTS_TABLE)],
            },
            kms_statement(key_arn),
            {
                "Sid": "ReadGiftCardSpiSecret",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [secret_arn()],
            },
            {
                "Sid": "OwnLogGroup",
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{log_group(SPI_FUNCTION)}",
                    f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{log_group(SPI_FUNCTION)}:*",
                ],
            },
        ],
    }


ROLES = (
    (GIFT_CARDS_ROLE, GIFT_CARDS_POLICY, gift_cards_policy, GIFT_CARDS_FUNCTION),
    (SPI_ROLE, SPI_POLICY, spi_policy, SPI_FUNCTION),
)


def role_exists(name: str) -> bool:
    try:
        iam().get_role(RoleName=name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchEntity", "NoSuchEntityException"):
            return False
        raise


def ensure_role(name: str, policy_name: str, document, apply: bool, key_arn: str) -> str:
    existed = role_exists(name)
    if not apply:
        return "exists; would reconcile the inline policy" if existed else "would create"
    if not existed:
        iam().create_role(
            RoleName=name,
            AssumeRolePolicyDocument=json.dumps(trust_policy()),
            Description="Gift-card execution role (least privilege, own table only)",
            Tags=[{"Key": "Project", "Value": "WECARE.DIGITAL"},
                  {"Key": "Purpose", "Value": "GiftCards"}],
        )
    else:
        iam().update_assume_role_policy(RoleName=name,
                                        PolicyDocument=json.dumps(trust_policy()))
    iam().put_role_policy(RoleName=name, PolicyName=policy_name,
                          PolicyDocument=json.dumps(document(key_arn)))
    return "reconciled" if existed else "created"


def ensure_log_group(function: str, apply: bool) -> str:
    """The function's own log group, with retention.

    Created here rather than left to Lambda's first invocation, because a group Lambda creates has no
    retention policy and keeps logs forever.
    """
    name = log_group(function)
    try:
        groups = logs().describe_log_groups(logGroupNamePrefix=name,
                                            limit=50).get("logGroups", [])
        exists = any(g.get("logGroupName") == name for g in groups)
    except ClientError:
        exists = False
    if not apply:
        return ("exists; would verify retention" if exists
                else f"would create with {LOG_RETENTION_DAYS}-day retention")
    if not exists:
        logs().create_log_group(logGroupName=name, tags={
            "Project": "WECARE.DIGITAL", "Purpose": "GiftCards"})
    logs().put_retention_policy(logGroupName=name, retentionInDays=LOG_RETENTION_DAYS)
    return "exists; retention verified" if exists else "created"


def ensure_layer(apply: bool) -> str:
    """Attach the version-pinned cryptography layer to the SPI function.

    `scripts/deploy_all_lambdas.py` validates every top-level import against the package PLUS the
    function's LIVE layer list, so a new function with no layers attached fails that gate before it
    ever deploys. Attaching here is what makes the SPI function deployable at all, and test 110
    reproduces the same check offline so the gate is not the first place it is discovered.
    """
    try:
        current = lam().get_function_configuration(FunctionName=SPI_FUNCTION)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return (f"{SPI_FUNCTION} does not exist yet; attach "
                    f"{CRYPTOGRAPHY_LAYER_ARN} after the first deploy")
        raise
    attached = [layer.get("Arn") for layer in current.get("Layers") or []]
    if CRYPTOGRAPHY_LAYER_ARN in attached:
        return f"already attached ({CRYPTOGRAPHY_LAYER_ARN})"
    if not apply:
        return f"would attach {CRYPTOGRAPHY_LAYER_ARN}"
    # Additive: keep whatever else is attached. `update-function-configuration` REPLACES the layer
    # list, so dropping the existing ones would be a silent regression.
    lam().update_function_configuration(
        FunctionName=SPI_FUNCTION,
        Layers=sorted(set(attached) | {CRYPTOGRAPHY_LAYER_ARN}))
    return f"attached {CRYPTOGRAPHY_LAYER_ARN}"


def alarm_topic_arn() -> str:
    for page in sns().get_paginator("list_topics").paginate():
        for topic in page.get("Topics", []):
            if str(topic.get("TopicArn", "")).endswith(":" + ALARM_TOPIC_NAME):
                return topic["TopicArn"]
    return ""


def ensure_alarms(apply: bool) -> str:
    """The two section 6.5 alarms, at `Sum >= 1` over five minutes, one datapoint.

    A threshold of one rather than a rate, because a single occurrence of either is actionable: the
    first means Wix called an endpoint section 1.3 predicts it never calls, and the second means a
    recorded charge disagrees with what the gateway confirmed.
    """
    topic = alarm_topic_arn()
    notes = []
    for alarm in ALARMS:
        if not apply:
            notes.append(f"would create {alarm['name']} on "
                         f"{METRIC_NAMESPACE}/{alarm['metric']} Sum >= 1")
            continue
        cloudwatch().put_metric_alarm(
            AlarmName=alarm["name"],
            AlarmDescription=alarm["description"],
            Namespace=METRIC_NAMESPACE,
            MetricName=alarm["metric"],
            Statistic="Sum",
            Period=300,
            EvaluationPeriods=1,
            DatapointsToAlarm=1,
            Threshold=1,
            ComparisonOperator="GreaterThanOrEqualToThreshold",
            TreatMissingData="notBreaching",
            ActionsEnabled=bool(topic),
            AlarmActions=[topic] if topic else [],
            Tags=[{"Key": "Project", "Value": "WECARE.DIGITAL"},
                  {"Key": "Purpose", "Value": "GiftCards"}],
        )
        notes.append(f"created {alarm['name']}"
                     + ("" if topic else " (NO SNS ACTION: wecare-alerts not found)"))
    return "; ".join(notes)


def verify() -> int:
    """Read every fact back off the account. Non-zero on any problem."""
    problems: list[str] = []
    key_arn = kms_key_arn()
    if not key_arn:
        problems.append(f"{KMS_ALIAS} does not resolve to a key, so the KMS grants name nothing")

    for name, policy_name, document, function in ROLES:
        if not role_exists(name):
            problems.append(f"role {name} does not exist")
            continue
        role = iam().get_role(RoleName=name)["Role"]
        trust = role.get("AssumeRolePolicyDocument") or {}
        if isinstance(trust, str):
            trust = json.loads(trust)
        conditions = [((s.get("Condition") or {}).get("StringEquals") or {})
                      .get("aws:SourceAccount") for s in trust.get("Statement") or []]
        if conditions != [ACCOUNT_ID]:
            problems.append(f"{name} trust SourceAccount is {conditions}, "
                            f"expected [{ACCOUNT_ID}]")

        try:
            live = iam().get_role_policy(RoleName=name, PolicyName=policy_name)
            live_document = live["PolicyDocument"]
            if isinstance(live_document, str):
                live_document = json.loads(live_document)
        except ClientError:
            problems.append(f"inline policy {policy_name} is missing from {name}")
            continue

        if live_document != document(key_arn):
            problems.append(f"the live inline policy on {name} differs from this script's "
                            f"document")

        actions = {a for s in live_document.get("Statement", []) for a in s.get("Action", [])}
        for forbidden in ("dynamodb:Scan", "dynamodb:*", "*", "kms:*", "secretsmanager:*",
                          "dynamodb:DeleteTable", "iam:*"):
            if forbidden in actions:
                problems.append(f"{name} grants {forbidden}")
        for resource in (r for s in live_document.get("Statement", [])
                         for r in s.get("Resource", [])):
            if resource == "*":
                problems.append(f"{name} carries a wildcard resource")

        # The asymmetries. These are what make two roles worth having.
        if name == SPI_ROLE and "dynamodb:DeleteItem" in actions:
            problems.append("the SPI role must not hold DeleteItem")
        if name == GIFT_CARDS_ROLE and any(
                table_arn(PAYMENT_ATTEMPTS_TABLE) in s.get("Resource", [])
                for s in live_document.get("Statement", [])):
            problems.append("the gift-cards role must not reach PaymentAttemptsTable")

        # The KMS condition, re-read rather than assumed.
        via = [((s.get("Condition") or {}).get("StringEquals") or {}).get("kms:ViaService")
               for s in live_document.get("Statement", [])
               if any(a.startswith("kms:") for a in s.get("Action", []))]
        if via != [f"dynamodb.{REGION}.amazonaws.com"]:
            problems.append(f"{name}'s kms:ViaService condition is {via}")

        attached = iam().list_attached_role_policies(RoleName=name).get("AttachedPolicies", [])
        if attached:
            problems.append(f"{name} has managed policies attached: "
                            f"{[p['PolicyArn'] for p in attached]}")

        try:
            retention = next(
                g.get("retentionInDays")
                for g in logs().describe_log_groups(logGroupNamePrefix=log_group(function),
                                                    limit=50).get("logGroups", [])
                if g.get("logGroupName") == log_group(function))
        except StopIteration:
            retention = None
            problems.append(f"log group {log_group(function)} does not exist")

        print(f"role: {name}")
        print(f"  trust SourceAccount: {conditions}")
        print(f"  actions: {sorted(actions)}")
        print(f"  log retention: {retention}")

    # The layer, on the live function.
    try:
        configuration = lam().get_function_configuration(FunctionName=SPI_FUNCTION)
        layers = [layer.get("Arn") for layer in configuration.get("Layers") or []]
        print(f"layers on {SPI_FUNCTION}: {layers}")
        if CRYPTOGRAPHY_LAYER_ARN not in layers:
            problems.append(f"{SPI_FUNCTION} is missing {CRYPTOGRAPHY_LAYER_ARN}; its top-level "
                            f"imports will fail the deploy gate")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        print(f"layers on {SPI_FUNCTION}: function not created yet")

    live_alarms = {a["AlarmName"] for a in cloudwatch().describe_alarms(
        AlarmNames=[alarm["name"] for alarm in ALARMS]).get("MetricAlarms", [])}
    for alarm in ALARMS:
        if alarm["name"] not in live_alarms:
            problems.append(f"alarm {alarm['name']} does not exist (run with --alarms)")
    print(f"alarms: {sorted(live_alarms)}")
    print(f"kms alias: {KMS_ALIAS} -> {key_arn or 'MISSING'}")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\ngift-card roles verified")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="create or reconcile; without it this is a dry run")
    parser.add_argument("--alarms", action="store_true",
                        help="also create the two section 6.5 alarms")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    key_arn = kms_key_arn()
    print(f"region: {REGION}\napply: {args.apply}\nkms alias: {KMS_ALIAS} -> "
          f"{key_arn or 'MISSING (run provision_gift_cards_table.py first)'}\n")
    for name, policy_name, document, function in ROLES:
        print(f"role {name}: {ensure_role(name, policy_name, document, args.apply, key_arn)}")
        print(f"log group {log_group(function)}: {ensure_log_group(function, args.apply)}")
    print(f"layer: {ensure_layer(args.apply)}")
    if args.alarms:
        print(f"alarms: {ensure_alarms(args.apply)}")
    if not args.apply:
        print("\ndry run: nothing changed")
        print(json.dumps({GIFT_CARDS_ROLE: gift_cards_policy(key_arn),
                          SPI_ROLE: spi_policy(key_arn)}, indent=2))
        return 0
    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
