#!/usr/bin/env python3
"""Move gated objects from secure/<name> into secure/u/<name>, and build secure/d/.

Why the split exists
--------------------
    secure/u/   the original, exactly as the operator uploaded it, any type
    secure/d/   the rendition that can actually be delivered over WhatsApp

Only PDF and images render as something a recipient can open inline. Anything else
has no ``d/`` object and is delivered as a download link instead. Deciding that at
upload time beats discovering it at send time, when a paying customer is waiting.

Both live under ``secure/``, which the CloudFront edge function denies wholesale, so
neither sub-prefix is publicly reachable and no edge change is needed.

Idempotent: objects already under u/ or d/ are left alone. Uses server-side copy, so
the bytes never pass through this script.

    python scripts/migrate_secure_prefixes.py --dry-run
    python scripts/migrate_secure_prefixes.py
    python scripts/migrate_secure_prefixes.py --verify
"""

from __future__ import annotations

import argparse
import sys

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3  (or use .venv/bin/python)")

REGION = "us-east-1"
BUCKET = "wecare-digital-get"
TABLE = "stack-wecare-digital-SecureFilesTable"

SECURE = "secure/"
UPLOAD = SECURE + "u/"
DELIVER = SECURE + "d/"

DELIVERABLE_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_BYTES = 100 * 1024 * 1024


def s3():
    return boto3.client("s3", region_name=REGION)


def table():
    return boto3.resource("dynamodb", region_name=REGION).Table(TABLE)


def classify(content_type: str, size: int) -> str:
    kind = DELIVERABLE_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if kind == "image" and size <= MAX_IMAGE_BYTES:
        return "image"
    if kind == "pdf" and size <= MAX_DOCUMENT_BYTES:
        return "pdf"
    return "link"


def gated_objects() -> list[dict]:
    """Every object under secure/, with the sub-prefix it currently sits in."""
    out, token = [], None
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": SECURE}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3().list_objects_v2(**kwargs)
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            rest = key[len(SECURE):]
            out.append({
                "key": key,
                "basename": key.split("/")[-1],
                "size": obj["Size"],
                "where": "u" if rest.startswith("u/") else "d" if rest.startswith("d/") else "root",
            })
        token = page.get("NextContinuationToken")
        if not token:
            break
    return out


def migrate(dry_run: bool) -> int:
    objects = gated_objects()
    stray = [o for o in objects if o["where"] == "root"]

    print(f"objects under {SECURE}: {len(objects)}")
    print(f"  already in u/: {sum(1 for o in objects if o['where'] == 'u')}")
    print(f"  already in d/: {sum(1 for o in objects if o['where'] == 'd')}")
    print(f"  to move:       {len(stray)}")

    rows = {r["s3Key"]: r for r in table().scan().get("Items", []) if r.get("s3Key")}

    moved = 0
    for obj in stray:
        new_key = UPLOAD + obj["basename"]
        head = s3().head_object(Bucket=BUCKET, Key=obj["key"])
        content_type = head.get("ContentType", "")
        deliverable = classify(content_type, obj["size"])
        deliver_key = DELIVER + obj["basename"] if deliverable in ("pdf", "image") else ""

        if dry_run:
            print(f"  would move {obj['basename'][:34]}… -> u/  deliverable={deliverable}")
            continue

        s3().copy_object(
            Bucket=BUCKET, Key=new_key,
            CopySource={"Bucket": BUCKET, "Key": obj["key"]},
            ContentType=content_type, MetadataDirective="REPLACE",
        )
        if deliver_key:
            s3().copy_object(
                Bucket=BUCKET, Key=deliver_key,
                CopySource={"Bucket": BUCKET, "Key": obj["key"]},
                ContentType=content_type, MetadataDirective="REPLACE",
            )
        s3().delete_object(Bucket=BUCKET, Key=obj["key"])

        # Repoint the catalogue row, or the file becomes unreachable.
        row = rows.get(obj["key"])
        if row:
            table().update_item(
                Key={"fileId": row["fileId"]},
                UpdateExpression=(
                    "SET s3Key = :k, deliverable = :d, deliveryKey = :dk, contentType = :ct"
                ),
                ExpressionAttributeValues={
                    ":k": new_key, ":d": deliverable,
                    ":dk": deliver_key, ":ct": content_type,
                },
            )
            print(f"  moved {obj['basename'][:34]}… -> u/  deliverable={deliverable}  row updated")
        else:
            print(f"  moved {obj['basename'][:34]}… -> u/  deliverable={deliverable}  "
                  f"NO CATALOGUE ROW (orphan object)")
        moved += 1

    if dry_run:
        print("\ndry run: nothing changed")
    return moved


def verify() -> int:
    failures = 0
    objects = gated_objects()

    stray = [o for o in objects if o["where"] == "root"]
    if stray:
        print(f"FAIL {len(stray)} object(s) still directly under {SECURE}")
        failures += 1
    else:
        print(f"PASS no objects left directly under {SECURE}")

    print(f"PASS u/ holds {sum(1 for o in objects if o['where'] == 'u')} object(s)")
    print(f"PASS d/ holds {sum(1 for o in objects if o['where'] == 'd')} object(s)")

    # every active row must point at u/, and claim a d/ object only if it exists
    keys = {o["key"] for o in objects}
    for row in table().scan().get("Items", []):
        key = row.get("s3Key", "")
        name = str(row.get("displayName", ""))[:28]
        if row.get("status") != "active":
            continue
        if not key.startswith(UPLOAD):
            print(f"FAIL row '{name}' s3Key is not under u/: {key[:46]}")
            failures += 1
        elif key not in keys:
            print(f"FAIL row '{name}' points at a missing object")
            failures += 1
        else:
            print(f"PASS row '{name}' -> u/  deliverable={row.get('deliverable', '?')}")

        dk = row.get("deliveryKey") or ""
        if dk and dk not in keys:
            print(f"FAIL row '{name}' claims a d/ object that does not exist")
            failures += 1

    print()
    print("secure prefixes verified" if not failures else f"{failures} check(s) failed")
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)

    if args.verify:
        return verify()

    print(f"bucket: {BUCKET}\n")
    migrate(args.dry_run)
    if args.dry_run:
        return 0
    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
