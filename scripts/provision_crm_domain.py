#!/usr/bin/env python3
"""Provision the CRM domain: Lead, Pipeline, Stage, Opportunity, Activity.

    python scripts/provision_crm_domain.py --dry-run
    python scripts/provision_crm_domain.py
    python scripts/provision_crm_domain.py --verify

Measured before writing this: the live account holds **70 DynamoDB tables and no CRM
entity**. Nothing here migrates or replaces an existing table, so there is no cutover and
no rollback beyond deleting five empty tables.

Why no TTL on any of these
--------------------------
Every other table in this account that holds transport detail expires it - Messages at 30
days, FlowDraft at 7. These five hold the *business* record: which enquiry came from which
campaign, what it was worth, whether it was won. Expiring that deletes the only evidence
of what marketing spend produced, and it cannot be reconstructed from the message log
because the message log has already expired.

PITR is on for the same reason: these are the rows whose accidental deletion has no other
copy. It is a continuous backup, not a snapshot, so it covers a bad bulk update as well as
a dropped table.

The index map is duplicated in tests/test_crm_service.py on purpose
------------------------------------------------------------------
`TABLE_INDEXES` there mirrors `TABLES` here, and the fake raises on a query against an
index it does not know. That pairing catches the most expensive mistake available in this
design: code querying an index provisioning never created. DynamoDB answers that with an
empty result set, not an error - so a board or a lead queue looks permanently empty and
nothing anywhere reports a fault.
"""

from __future__ import annotations

import argparse
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    print("boto3 required", file=sys.stderr)
    raise SystemExit(2)

REGION = "us-east-1"
PREFIX = "stack-wecare-digital"

PIPELINES = f"{PREFIX}-CrmPipelines"
STAGES = f"{PREFIX}-CrmStages"
LEADS = f"{PREFIX}-CrmLeads"
OPPORTUNITIES = f"{PREFIX}-CrmOpportunities"
ACTIVITIES = f"{PREFIX}-CrmActivities"

#: `attrs` lists only attributes used in a key or an index. DynamoDB requires exactly that
#: - declaring an unindexed attribute is rejected, and omitting an indexed one is too.
TABLES = {
    PIPELINES: {
        "keys": [("pipelineId", "HASH")],
        "attrs": {"pipelineId": "S", "isDefault": "S"},
        # `isDefault` is a string, not a boolean: DynamoDB cannot index a boolean, so the
        # alternative is scanning every pipeline to find the default on every request.
        "gsi": [("isDefault-index", [("isDefault", "HASH")])],
    },
    STAGES: {
        "keys": [("stageId", "HASH")],
        "attrs": {"stageId": "S", "pipelineId": "S", "displayOrder": "N"},
        # The board renders from this one query, already ordered. No client-side sort.
        "gsi": [("pipelineId-displayOrder-index",
                 [("pipelineId", "HASH"), ("displayOrder", "RANGE")])],
    },
    LEADS: {
        "keys": [("leadId", "HASH")],
        "attrs": {"leadId": "S", "contactId": "S", "state": "S",
                  "contactPipelineKey": "S", "createdAt": "N"},
        "gsi": [
            # Contact 360: this contact's leads, newest first.
            ("contactId-createdAt-index",
             [("contactId", "HASH"), ("createdAt", "RANGE")]),
            # The work queue: everything NEW, oldest first when read ascending.
            ("state-createdAt-index", [("state", "HASH"), ("createdAt", "RANGE")]),
            # "does this contact already have an open lead in this pipeline?" - the
            # business-duplicate question, answered at read time as a policy rather than
            # enforced as a uniqueness constraint. See lambda_utils.crm.keys.
            ("contactPipelineKey-index", [("contactPipelineKey", "HASH")]),
        ],
    },
    OPPORTUNITIES: {
        "keys": [("opportunityId", "HASH")],
        "attrs": {"opportunityId": "S", "contactId": "S", "stageId": "S",
                  "createdAt": "N"},
        "gsi": [
            ("contactId-createdAt-index",
             [("contactId", "HASH"), ("createdAt", "RANGE")]),
            # One board column.
            ("stageId-createdAt-index",
             [("stageId", "HASH"), ("createdAt", "RANGE")]),
        ],
    },
    ACTIVITIES: {
        "keys": [("activityId", "HASH")],
        "attrs": {"activityId": "S", "contactId": "S", "leadId": "S",
                  "opportunityId": "S", "at": "N"},
        # Three timelines, three sparse indexes. Sparse is the point: an activity attached
        # only to a contact does not appear in the lead or opportunity index at all, so
        # those indexes stay small and cheap.
        "gsi": [
            ("contactId-at-index", [("contactId", "HASH"), ("at", "RANGE")]),
            ("leadId-at-index", [("leadId", "HASH"), ("at", "RANGE")]),
            ("opportunityId-at-index",
             [("opportunityId", "HASH"), ("at", "RANGE")]),
        ],
    },
}


def _ddb():
    return boto3.client("dynamodb", region_name=REGION)


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
                "KeySchema": [{"AttributeName": a, "KeyType": k}
                              for a, k in index_keys],
                "Projection": {"ProjectionType": "ALL"},
            }
            for index_name, index_keys in spec.get("gsi", [])
        ] or None,
        Tags=[{"Key": "domain", "Value": "crm"}, {"Key": "phase", "Value": "4"}],
    )
    _ddb().get_waiter("table_exists").wait(TableName=name)
    return "created"


def enable_pitr(name: str, dry_run: bool) -> str:
    """Continuous backup. These rows have no other copy."""
    if dry_run:
        return "would enable"
    try:
        current = _ddb().describe_continuous_backups(TableName=name)
        status = (current.get("ContinuousBackupsDescription", {})
                  .get("PointInTimeRecoveryDescription", {})
                  .get("PointInTimeRecoveryStatus"))
        if status == "ENABLED":
            return "already on"
        _ddb().update_continuous_backups(
            TableName=name,
            PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True},
        )
        return "enabled"
    except ClientError as exc:
        return f"failed: {exc.response.get('Error', {}).get('Code')}"


def verify() -> int:
    """Read back what is deployed and compare it to `TABLES`. Exit 1 on any mismatch.

    Checks the index *key schema*, not just the index name. An index that exists with the
    wrong partition key is worse than a missing one: the query succeeds and returns
    nothing, which reads as "no leads" rather than as a fault.
    """
    problems = []
    print(f"{'table':<44} {'status':<10} {'items':>7}  indexes")
    for name, spec in TABLES.items():
        try:
            described = _ddb().describe_table(TableName=name)["Table"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"{name:<44} {'MISSING':<10} {'-':>7}")
                problems.append(f"{name} does not exist")
                continue
            raise

        live_keys = [(k["AttributeName"], k["KeyType"]) for k in described["KeySchema"]]
        if live_keys != spec["keys"]:
            problems.append(f"{name} key schema is {live_keys}, expected {spec['keys']}")

        live_indexes = {
            gsi["IndexName"]: [(k["AttributeName"], k["KeyType"])
                               for k in gsi["KeySchema"]]
            for gsi in described.get("GlobalSecondaryIndexes", [])
        }
        for index_name, index_keys in spec.get("gsi", []):
            if index_name not in live_indexes:
                problems.append(f"{name} is missing index {index_name}")
            elif live_indexes[index_name] != index_keys:
                problems.append(
                    f"{name}.{index_name} keys are {live_indexes[index_name]}, "
                    f"expected {index_keys}")

        backups = _ddb().describe_continuous_backups(TableName=name)
        pitr = (backups.get("ContinuousBackupsDescription", {})
                .get("PointInTimeRecoveryDescription", {})
                .get("PointInTimeRecoveryStatus"))
        if pitr != "ENABLED":
            problems.append(f"{name} has PITR {pitr}")

        # A TTL here would silently delete business history.
        ttl = _ddb().describe_time_to_live(TableName=name)
        ttl_status = ttl.get("TimeToLiveDescription", {}).get("TimeToLiveStatus")
        if ttl_status not in ("DISABLED", None):
            problems.append(f"{name} has TTL {ttl_status}; CRM rows must not expire")

        print(f"{name:<44} {described['TableStatus']:<10} "
              f"{described.get('ItemCount', 0):>7}  {len(live_indexes)} gsi, PITR {pitr}")

    if problems:
        print("\nPROBLEMS")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nCRM domain verified: 5 tables, key schemas and indexes match, PITR on, "
          "no TTL.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                       help="report what would change, write nothing")
    parser.add_argument("--verify", action="store_true",
                       help="read back and compare against the declared shape")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    print(f"region={REGION} tables={len(TABLES)} dry_run={args.dry_run}")
    for name, spec in TABLES.items():
        created = create_table(name, spec, args.dry_run)
        pitr = enable_pitr(name, args.dry_run) if created != "exists" or \
            not args.dry_run else "skipped"
        index_count = len(spec.get("gsi", []))
        print(f"  {name:<44} {created:<12} pitr={pitr:<12} gsi={index_count}")

    if args.dry_run:
        print("\ndry run: nothing created")
        return 0
    print("\nNow seed the default pipeline from a Lambda or a shell with the shared "
          "path on sys.path:\n"
          "  from lambda_utils.crm import service; service.ensure_default_pipeline()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
