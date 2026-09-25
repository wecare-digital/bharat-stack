#!/usr/bin/env python3
"""Find customers who paid for a file and never received it, and retry.

Why this exists
---------------
A failed WhatsApp send used to be a log line and nothing more, while the customer had
already been charged. Nothing in the system could answer "who is owed a file", so the
only way to notice was for someone to read CloudWatch and recognise what they were
looking at. That is not a control.

``deliver_over_whatsapp`` now writes ``delivered``, ``deliveryDetail``,
``deliveryAttempts`` and ``deliveryAttemptedAt`` onto the grant, which makes the
question answerable as a query.

What counts as owed
-------------------
A grant that is ``paid`` and NOT ``delivered``. Deliberately ignores ``consumed``:
consumed means the customer redeemed on the web, which is a different channel and does
not discharge a WhatsApp delivery they also paid for.

Grants carry a TTL, so this only sees the recent window. That is the right scope for a
retry - anything older needs a human, not an automatic resend, which is why
``--report`` exists separately.

    python scripts/reconcile_file_deliveries.py --report     # list, change nothing
    python scripts/reconcile_file_deliveries.py --retry      # re-attempt delivery
    python scripts/reconcile_file_deliveries.py --retry --max 5

Exit codes: 0 nothing owed, 1 at least one grant still undelivered.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import boto3
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3  (or use .venv/bin/python)")

REGION = "us-east-1"
GRANTS_TABLE = "stack-wecare-digital-DownloadGrantsTable"
FILES_TABLE = "stack-wecare-digital-SecureFilesTable"
SECURE_FILES_FUNCTION = "wecare-secure-files:live"


def table(name: str):
    return boto3.resource("dynamodb", region_name=REGION).Table(name)


def mask(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return ("*" * max(0, len(digits) - 4)) + digits[-4:] if digits else "****"


def owed_grants() -> list[dict]:
    """Paid grants with no successful delivery.

    A Scan is correct here rather than lazy: the question spans every grant and there is
    no access pattern for "paid but not delivered" that an index could serve without
    adding one for a job that runs occasionally over a TTL-bounded table.
    """
    rows, kwargs = [], {}
    while True:
        page = table(GRANTS_TABLE).scan(**kwargs)
        for item in page.get("Items", []):
            # otpprobe# rows share this table as rate-limit counters; they are not grants.
            if str(item.get("grantId", "")).startswith("otpprobe#"):
                continue
            if not item.get("paid"):
                continue
            if item.get("delivered") is True:
                continue
            # Only WhatsApp grants are owed a send; web grants are collected by redeem.
            if item.get("channel") != "whatsapp":
                continue
            rows.append(item)
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return rows


def describe(grant: dict) -> str:
    file_row = table(FILES_TABLE).get_item(
        Key={"fileId": grant.get("fileId", "")}
    ).get("Item") or {}
    age_minutes = int((time.time() - int(grant.get("paidAt") or grant.get("createdAt") or 0)) / 60)
    return (
        f"  grant {str(grant.get('grantId'))[:12]}…  "
        f"{mask(grant.get('ownerPhone', ''))}  "
        f"{str(file_row.get('displayName') or grant.get('fileId'))[:28]:28}  "
        f"paid {age_minutes}m ago  "
        f"attempts={int(grant.get('deliveryAttempts') or 0)}  "
        f"last={str(grant.get('deliveryDetail') or 'never attempted')[:40]}"
    )


def retry(grant: dict) -> tuple[bool, str]:
    """Re-run delivery through the same internal path the webhook uses.

    Synchronous here, unlike the webhook's fire-and-forget, because an operator running
    this wants the answer rather than another thing to go and check.
    """
    response = boto3.client("lambda", region_name=REGION).invoke(
        FunctionName=SECURE_FILES_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {"internalAction": "deliverOverWhatsApp", "grantId": grant["grantId"]}
        ).encode(),
    )
    raw = response["Payload"].read()
    result = json.loads(raw.decode()) if raw else {}
    if response.get("FunctionError"):
        return False, "secure-files raised"
    return bool(result.get("ok")), str(result.get("detail") or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="list only, change nothing")
    ap.add_argument("--retry", action="store_true", help="re-attempt delivery")
    ap.add_argument("--max", type=int, default=25, help="cap retries per run")
    args = ap.parse_args(argv)

    owed = owed_grants()
    print(f"paid but undelivered WhatsApp grants: {len(owed)}")
    for grant in owed:
        print(describe(grant))

    if not owed:
        print("\nnothing owed")
        return 0

    if not args.retry:
        print("\nreport only; pass --retry to re-attempt")
        return 1

    print(f"\nretrying up to {args.max}:")
    recovered = 0
    for grant in owed[: args.max]:
        ok, detail = retry(grant)
        print(f"  {str(grant['grantId'])[:12]}…  {'DELIVERED' if ok else 'FAILED'}  {detail[:60]}")
        recovered += 1 if ok else 0

    still_owed = len(owed) - recovered
    print(f"\nrecovered {recovered}, still owed {still_owed}")
    if still_owed:
        print("Grants that keep failing need a human: check the file is still active,")
        print("that deliverable is set, and that the number is reachable on WhatsApp.")
    return 1 if still_owed else 0


if __name__ == "__main__":
    raise SystemExit(main())
