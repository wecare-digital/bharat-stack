#!/usr/bin/env python3
"""List captured payments the webhook parked for reconciliation, and acknowledge them.

Why this exists
---------------
A `payment.captured` that the webhook could not authoritatively clear used to be a log line
and nothing more: an alert that money may have moved with no order, no invoice and no wallet
credit to show for it. The moment CloudWatch retention lapsed - and certainly once Razorpay
stopped retrying the event - that alert was gone, and nothing in the system could answer
"which captures still need a human".

`razorpay-webhook._quarantine_unverified_capture` now writes a DURABLE intake row
(`CAPTUREQUARANTINE#<paymentId>`) onto the commerce-keys table via the same conditional-write
pattern order creation uses. That makes the question answerable as a scan, and it survives
after the provider stops retrying - which is the whole point.

What acknowledgement means
--------------------------
Acknowledging a row records that a human has SEEN it. It does NOT resolve it, credit anything,
mark any invoice paid or delete the row. The row is retained precisely so an acknowledged
capture stays recoverable - a staff member can still come back to it, decide what the money
was for, and act. Nothing in this script writes financial state.

    python scripts/reconcile_captures.py --report              # list, change nothing
    python scripts/reconcile_captures.py --ack pay_LIVExxxx    # acknowledge one capture
    python scripts/reconcile_captures.py --ack-all             # acknowledge every unresolved row

Exit codes: 0 nothing unresolved, 1 at least one capture still unacknowledged.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "amplify", "functions", "shared"))

try:
    import boto3  # noqa: F401 - imported for parity with the other reconcile scripts
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: pip install boto3  (or use .venv/bin/python)")

from lambda_utils.ecommerce import order_keys  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")


def _table():
    import boto3 as _boto3
    return _boto3.resource("dynamodb", region_name=REGION).Table(
        order_keys.commerce_keys_table_name())


def parked_captures() -> list[dict]:
    """Durable capture-quarantine rows.

    A Scan is correct here rather than lazy: the question spans every parked capture, this job
    runs occasionally, and the commerce-keys table holds few rows. Only the
    `CAPTUREQUARANTINE#` namespace is a parked capture; everything else on this table is a
    payment reference or order-identity marker.
    """
    rows, kwargs = [], {}
    table = _table()
    while True:
        page = table.scan(**kwargs)
        for item in page.get("Items", []):
            if str(item.get("orderId", "")).startswith(order_keys.QUARANTINE_PREFIX):
                rows.append(item)
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return rows


def describe(row: dict) -> str:
    age_minutes = int((time.time() - int(row.get("createdAt") or 0)) / 60)
    return (
        f"  payment {str(row.get('paymentId'))[:20]:20}  "
        f"ref {str(row.get('referenceId') or '-')[:24]:24}  "
        f"outcome={str(row.get('outcome') or '-')[:22]:22}  "
        f"parked {age_minutes}m ago  "
        f"{'ACK' if row.get('acknowledged') else 'UNRESOLVED'}"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="list only, change nothing")
    ap.add_argument("--ack", metavar="PAYMENT_ID", help="acknowledge one capture by payment id")
    ap.add_argument("--ack-all", action="store_true", help="acknowledge every unresolved row")
    ap.add_argument("--actor", default="staff", help="who is acknowledging (audit field)")
    args = ap.parse_args(argv)

    if args.ack:
        updated = order_keys.acknowledge_capture_quarantine(
            _table(), payment_id=args.ack, actor=args.actor)
        if not updated:
            print(f"no parked capture found for {args.ack}")
            return 1
        print(f"acknowledged {args.ack} (row retained; still recoverable)")
        return 0

    parked = parked_captures()
    unresolved = [r for r in parked if not r.get("acknowledged")]
    print(f"parked captures: {len(parked)} ({len(unresolved)} unacknowledged)")
    for row in parked:
        print(describe(row))

    if not parked:
        print("\nnothing parked")
        return 0

    if args.ack_all:
        print(f"\nacknowledging {len(unresolved)}:")
        for row in unresolved:
            order_keys.acknowledge_capture_quarantine(
                _table(), payment_id=row["paymentId"], actor=args.actor)
            print(f"  {str(row['paymentId'])[:20]}  ACK")
        print("\nrows retained; acknowledgement does not resolve or discharge them")
        return 0

    if unresolved:
        print("\nreport only; pass --ack <paymentId> or --ack-all to acknowledge")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
