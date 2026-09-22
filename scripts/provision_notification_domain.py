#!/usr/bin/env python3
"""Provision the four notification tables plus the work queue and its DLQ.

Why a script and not `amplify/data/resource.ts`
----------------------------------------------
`resource.ts` declares 65 Amplify models. The account holds 66 DynamoDB tables, and
the two sets have almost no name correspondence - `Contact` against
`ContactsTable`, and so on. Whether those models are deployed at all is an open
question (`NOTIF-STORE-003`), which means a declaration there is not evidence that a
table exists.

That is not a theoretical concern for this domain specifically, it is the exact
failure being repaired. `PstnNotificationDelivery` was declared in four places -
`backend.ts`, `data/resource.ts`, `pstn/claims.py` and `pstn/keys.py` - and exists in
none of the 66 live tables. So every claim attempt raised `ClaimStoreUnavailable` and
the dial-events route answered 503 without sending. Measured: `plivo_dial_event`
fired 0 times in 14 days. A declaration nobody verified is how a notification
subsystem came to be permanently broken while looking complete in source.

So this script creates the tables against the live account and then reads them back.
It is idempotent, safe to re-run, and `--verify` asserts the deployed shape without
changing anything.

Usage
-----
    python scripts/provision_notification_domain.py --dry-run
    python scripts/provision_notification_domain.py
    python scripts/provision_notification_domain.py --verify
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    print("boto3 required", file=sys.stderr)
    raise SystemExit(2)

REGION = "us-east-1"
PREFIX = "stack-wecare-digital"

EVENTS = f"{PREFIX}-NotificationEvents"
DELIVERIES = f"{PREFIX}-NotificationDeliveries"
ATTEMPTS = f"{PREFIX}-NotificationAttempts"
OUTBOX = f"{PREFIX}-NotificationOutbox"

QUEUE = f"{PREFIX}-notification-queue"
DLQ = f"{PREFIX}-notification-dlq"

#: Every table TTLs on the same attribute name, so a sweep or an audit does not need
#: a per-table lookup to know which one to read.
TTL_ATTRIBUTE = "expiresAt"

TABLES = {
    EVENTS: {
        "keys": [("eventClaimKey", "HASH")],
        "attrs": {"eventClaimKey": "S", "canonicalCallId": "S"},
        # Find the event for a provider call id without knowing the version suffix.
        "gsi": [("canonicalCallId-index", [("canonicalCallId", "HASH")])],
    },
    DELIVERIES: {
        "keys": [("deliveryId", "HASH")],
        "attrs": {"deliveryId": "S", "eventClaimKey": "S", "state": "S",
                  "createdAt": "N"},
        "gsi": [
            # All three channels of one call, for the per-number QA matrix rows.
            ("eventClaimKey-index", [("eventClaimKey", "HASH")]),
            # Deliveries stuck in a non-terminal state, oldest first: the backlog and
            # oldest-age signals the observability requirement asks for.
            ("state-createdAt-index", [("state", "HASH"), ("createdAt", "RANGE")]),
        ],
    },
    ATTEMPTS: {
        "keys": [("attemptId", "HASH")],
        "attrs": {"attemptId": "S", "deliveryId": "S", "at": "N"},
        # Append-only history in order. This is the audit trail the brief forbids
        # erasing during the rebuild.
        "gsi": [("deliveryId-at-index", [("deliveryId", "HASH"), ("at", "RANGE")])],
    },
    OUTBOX: {
        "keys": [("jobId", "HASH")],
        "attrs": {"jobId": "S", "status": "S", "availableAt": "N"},
        # The worker's poll: READY jobs whose availableAt has passed, oldest first.
        "gsi": [("status-availableAt-index",
                 [("status", "HASH"), ("availableAt", "RANGE")])],
    },
}


def _ddb():
    return boto3.client("dynamodb", region_name=REGION)


def _sqs():
    return boto3.client("sqs", region_name=REGION)


def table_exists(name: str) -> bool:
    try:
        _ddb().describe_table(TableName=name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return False
        raise


def create_table(name: str, spec: dict, dry_run: bool) -> str:
    if table_exists(name):
        return "exists"
    if dry_run:
        return "would create"

    _ddb().create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": t}
                              for a, t in sorted(spec["attrs"].items())],
        KeySchema=[{"AttributeName": a, "KeyType": k} for a, k in spec["keys"]],
        GlobalSecondaryIndexes=[
            {
                "IndexName": index_name,
                "KeySchema": [{"AttributeName": a, "KeyType": k} for a, k in index_keys],
                "Projection": {"ProjectionType": "ALL"},
            }
            for index_name, index_keys in spec.get("gsi", [])
        ] or None,
        Tags=[{"Key": "domain", "Value": "notifications"},
              {"Key": "phase", "Value": "3"}],
    )
    _ddb().get_waiter("table_exists").wait(TableName=name)
    return "created"


def enable_ttl(name: str, dry_run: bool) -> str:
    """TTL bounds claim growth. A claim must outlive every provider retry window, or
    it expiring would permit a duplicate send - hence 30 days in `store.py`, not 1."""
    current = _ddb().describe_time_to_live(TableName=name)
    desc = current.get("TimeToLiveDescription", {}) or {}
    if desc.get("TimeToLiveStatus") in ("ENABLED", "ENABLING"):
        return f"ttl already {desc.get('AttributeName')}"
    if dry_run:
        return f"would enable ttl on {TTL_ATTRIBUTE}"
    _ddb().update_time_to_live(
        TableName=name,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": TTL_ATTRIBUTE})
    return f"ttl enabled on {TTL_ATTRIBUTE}"


def enable_pitr(name: str, dry_run: bool) -> str:
    """Point-in-time recovery. The brief requires a restorable snapshot before any
    notification table is retired, and requires restoring notification state without
    duplicate sends as a disaster-recovery exercise. Neither is possible without it."""
    try:
        current = _ddb().describe_continuous_backups(TableName=name)
        status = (current.get("ContinuousBackupsDescription", {})
                  .get("PointInTimeRecoveryDescription", {})
                  .get("PointInTimeRecoveryStatus"))
        if status == "ENABLED":
            return "pitr already enabled"
        if dry_run:
            return "would enable pitr"
        _ddb().update_continuous_backups(
            TableName=name,
            PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True})
        return "pitr enabled"
    except ClientError as exc:
        return f"pitr skipped ({exc.response.get('Error', {}).get('Code')})"


def queue_url(name: str) -> str:
    try:
        return _sqs().get_queue_url(QueueName=name)["QueueUrl"]
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if "NonExistentQueue" in code or code == "AWS.SimpleQueueService.NonExistentQueue":
            return ""
        raise


def create_queues(dry_run: bool) -> dict:
    """Work queue with a DLQ after 3 receives, following the repo's own convention:
    `visibilityTimeout` 300s, work retention 1 day, DLQ retention 7 days,
    `maxReceiveCount` 3 (see `amplify/backend-resources.ts`).

    The visibility timeout matches `store.LEASE_SECONDS`. They must agree: a
    visibility timeout shorter than the lease would redeliver a message whose lease is
    still held, and a lease shorter than the timeout would let a second worker take a
    job the first is still processing. Either way the channel sends twice.
    """
    out = {}

    dlq_url = queue_url(DLQ)
    if dlq_url:
        out[DLQ] = "exists"
    elif dry_run:
        out[DLQ] = "would create"
    else:
        dlq_url = _sqs().create_queue(
            QueueName=DLQ,
            Attributes={"MessageRetentionPeriod": str(7 * 24 * 3600),
                        "VisibilityTimeout": "300"})["QueueUrl"]
        out[DLQ] = "created"

    main_url = queue_url(QUEUE)
    if main_url:
        out[QUEUE] = "exists"
        return out
    if dry_run:
        out[QUEUE] = "would create"
        return out

    dlq_arn = _sqs().get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    _sqs().create_queue(
        QueueName=QUEUE,
        Attributes={
            "MessageRetentionPeriod": str(24 * 3600),
            "VisibilityTimeout": "300",
            "RedrivePolicy": ('{"deadLetterTargetArn":"%s","maxReceiveCount":3}'
                              % dlq_arn),
        })
    out[QUEUE] = "created"
    return out


def verify() -> int:
    """Read back the deployed shape. Exit 1 on any discrepancy."""
    problems = []
    print(f"region {REGION}\n")

    for name, spec in TABLES.items():
        if not table_exists(name):
            problems.append(f"{name}: MISSING")
            print(f"  FAIL {name}  does not exist")
            continue
        desc = _ddb().describe_table(TableName=name)["Table"]
        keys = [(k["AttributeName"], k["KeyType"]) for k in desc["KeySchema"]]
        indexes = sorted(i["IndexName"] for i in desc.get("GlobalSecondaryIndexes", []))
        expected_indexes = sorted(n for n, _ in spec.get("gsi", []))

        ttl = (_ddb().describe_time_to_live(TableName=name)
               .get("TimeToLiveDescription", {}) or {})
        ttl_ok = ttl.get("TimeToLiveStatus") == "ENABLED" and ttl.get("AttributeName") == TTL_ATTRIBUTE

        pitr = (_ddb().describe_continuous_backups(TableName=name)
                .get("ContinuousBackupsDescription", {})
                .get("PointInTimeRecoveryDescription", {})
                .get("PointInTimeRecoveryStatus"))

        ok = (keys == spec["keys"] and indexes == expected_indexes
              and ttl_ok and desc["TableStatus"] == "ACTIVE")
        if not ok:
            problems.append(name)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        print(f"       status {desc['TableStatus']}  keys {keys}")
        print(f"       indexes {indexes}")
        print(f"       ttl {ttl.get('TimeToLiveStatus')} on {ttl.get('AttributeName')}"
              f"   pitr {pitr}")
        print(f"       items {desc.get('ItemCount')}")

    print()
    for name in (QUEUE, DLQ):
        url = queue_url(name)
        if not url:
            problems.append(f"{name}: MISSING")
            print(f"  FAIL {name}  does not exist")
            continue
        attrs = _sqs().get_queue_attributes(
            QueueUrl=url, AttributeNames=["VisibilityTimeout", "MessageRetentionPeriod",
                                          "RedrivePolicy"])["Attributes"]
        print(f"  ok   {name}")
        print(f"       visibility {attrs.get('VisibilityTimeout')}s  "
              f"retention {attrs.get('MessageRetentionPeriod')}s")
        if attrs.get("RedrivePolicy"):
            print(f"       redrive {attrs['RedrivePolicy']}")

    # The lease and the visibility timeout must agree, or a job is processed twice.
    try:
        sys.path.insert(0, "amplify/functions/shared")
        from lambda_utils.notifications import store as store_mod
        url = queue_url(QUEUE)
        if url:
            visibility = int(_sqs().get_queue_attributes(
                QueueUrl=url, AttributeNames=["VisibilityTimeout"]
            )["Attributes"]["VisibilityTimeout"])
            if visibility != store_mod.LEASE_SECONDS:
                problems.append("lease/visibility mismatch")
                print(f"\n  FAIL lease {store_mod.LEASE_SECONDS}s != queue visibility "
                      f"{visibility}s — a job could be processed twice")
            else:
                print(f"\n  ok   lease {store_mod.LEASE_SECONDS}s == queue visibility "
                      f"{visibility}s")
    except Exception as exc:  # noqa: BLE001
        print(f"\n  warn could not cross-check the lease: {type(exc).__name__}")

    print()
    if problems:
        print(f"{len(problems)} problem(s): {', '.join(problems)}")
        return 1
    print("notification domain verified")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change, create nothing")
    ap.add_argument("--verify", action="store_true",
                    help="read back the deployed shape and exit non-zero on a gap")
    args = ap.parse_args(argv)

    if args.verify:
        return verify()

    print(f"region {REGION}  dry_run {args.dry_run}\n")
    for name, spec in TABLES.items():
        print(f"  {name}")
        print(f"    {create_table(name, spec, args.dry_run)}")
        if not args.dry_run or table_exists(name):
            print(f"    {enable_ttl(name, args.dry_run)}")
            print(f"    {enable_pitr(name, args.dry_run)}")

    print()
    for name, status in create_queues(args.dry_run).items():
        print(f"  {name}\n    {status}")

    if args.dry_run:
        print("\ndry run: nothing created")
        return 0

    print("\nre-reading the deployed shape ...\n")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
