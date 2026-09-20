#!/usr/bin/env python3
"""Did the deploy break anything? Compare the fleet before and after it.

A deploy that exits 0 proves the upload worked, nothing more. What matters is
whether invocations still succeed afterwards, and the honest way to answer that is
to put the error rate in the window *before* the change next to the window after
it. A function that was already failing should not be blamed on the deploy, and a
function that only started failing afterwards must not be missed.

Reads CloudWatch metrics for every function, plus the HTTP API's 5xx count, plus
the recent error lines from the log group of whichever functions look unhealthy.

    python scripts/post_deploy_health.py                    # 3h window, split now-90m
    python scripts/post_deploy_health.py --since 08:00      # split at a UTC time today
    python scripts/post_deploy_health.py --function wecare-whatsapp-calling

Exit status: 1 when any function has errors after the split point that it did not
have before.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
API_ID = "zllr9lrg7j"


def total(cw, namespace, metric, dims, start, end, stat="Sum") -> float:
    try:
        r = cw.get_metric_statistics(Namespace=namespace, MetricName=metric,
                                     Dimensions=dims, StartTime=start, EndTime=end,
                                     Period=3600, Statistics=[stat])
    except ClientError:
        return 0.0
    return sum(p[stat] for p in r.get("Datapoints", []))


def recent_errors(logs, fn: str, start: dt.datetime, limit: int = 4) -> list[str]:
    try:
        r = logs.filter_log_events(
            logGroupName=f"/aws/lambda/{fn}",
            startTime=int(start.timestamp() * 1000),
            filterPattern='?ERROR ?Error ?Task timed out ?Unable ?AccessDenied',
            limit=limit)
    except ClientError:
        return []
    out = []
    for e in r.get("events", []):
        msg = " ".join(e["message"].split())[:150]
        if msg not in out:
            out.append(msg)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="UTC HH:MM today to use as the before/after split")
    ap.add_argument("--hours", type=float, default=3.0, help="total window (default 3)")
    ap.add_argument("--function", action="append", help="limit to these functions")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(hours=args.hours)
    if args.since:
        h, _, m = args.since.partition(":")
        split = now.replace(hour=int(h), minute=int(m or 0), second=0, microsecond=0)
    else:
        split = now - dt.timedelta(minutes=90)

    lam = boto3.client("lambda", region_name=REGION)
    cw = boto3.client("cloudwatch", region_name=REGION)
    logs = boto3.client("logs", region_name=REGION)

    print("=" * 78)
    print("POST-DEPLOY HEALTH")
    print("=" * 78)
    print(f"window {start:%H:%M} -> {now:%H:%M} UTC, split at {split:%H:%M} UTC")

    names = args.function or []
    if not names:
        for page in lam.get_paginator("list_functions").paginate():
            names += [f["FunctionName"] for f in page["Functions"]]
    names.sort()

    regressed, noisy, idle, healthy = [], [], 0, 0
    for fn in names:
        d = [{"Name": "FunctionName", "Value": fn}]
        inv_b = total(cw, "AWS/Lambda", "Invocations", d, start, split)
        err_b = total(cw, "AWS/Lambda", "Errors", d, start, split)
        inv_a = total(cw, "AWS/Lambda", "Invocations", d, split, now)
        err_a = total(cw, "AWS/Lambda", "Errors", d, split, now)
        thr_a = total(cw, "AWS/Lambda", "Throttles", d, split, now)
        if inv_b == 0 and inv_a == 0:
            idle += 1
            continue
        if err_a > 0 and err_b == 0:
            regressed.append((fn, inv_b, err_b, inv_a, err_a, thr_a))
        elif err_a > 0:
            noisy.append((fn, inv_b, err_b, inv_a, err_a, thr_a))
        else:
            healthy += 1

    def show(rows, title):
        print(f"\n{title}")
        if not rows:
            print("  none")
            return
        for fn, ib, eb, ia, ea, th in rows:
            print(f"  {fn:38s} before {int(ib):5d} inv / {int(eb):3d} err   "
                  f"after {int(ia):5d} inv / {int(ea):3d} err"
                  + (f"   throttles {int(th)}" if th else ""))
            for line in recent_errors(logs, fn, split):
                print(f"        {line}")

    show(regressed, "NEW errors after the split (blame the deploy)")
    show(noisy, "errors both before and after (pre-existing)")
    print(f"\nhealthy with traffic: {healthy}    idle in this window: {idle}")

    print("\nHTTP API")
    for metric in ("5xx", "4xx", "Count"):
        b = total(cw, "AWS/ApiGateway", metric,
                  [{"Name": "ApiId", "Value": API_ID}], start, split)
        a = total(cw, "AWS/ApiGateway", metric,
                  [{"Name": "ApiId", "Value": API_ID}], split, now)
        print(f"  {metric:6s} before {int(b):6d}   after {int(a):6d}")

    print("\n" + "=" * 78)
    verdict = "FAIL - new errors after the deploy" if regressed else "PASS"
    print(f"RESULT: {verdict}")
    print("=" * 78)
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
