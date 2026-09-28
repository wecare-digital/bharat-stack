#!/usr/bin/env python3
"""Set one Lambda environment variable without discarding the other twenty.

SAME HAZARD AS `UpdateUserPool`, AND IT BITES HARDER HERE.
`update-function-configuration --environment Variables={...}` **replaces** the entire
map. A function in this account carries up to 17 variables -- table names, secret
pointers, phone-number ids, feature flags -- and writing one key the obvious way deletes
the rest, which does not fail, it just makes the function start resolving defaults. On
2026-09-28 the Cognito equivalent silently wiped three CUSTOM_AUTH triggers and opened
self-signup; this is the same shape on a bigger surface.

So: read, merge, write, verify, and snapshot the before state to disk first. Also
publishes a version and moves the `live` alias, because `lambda-snapstart-deploy.md` is
explicit that the HTTP API invokes `:live` and a configuration change on `$LATEST` does
not reach production for the 58 functions that have an alias.

    python scripts/set_lambda_env_flag.py --list ADMIN_MFA_REQUIRED
    python scripts/set_lambda_env_flag.py --set ADMIN_MFA_REQUIRED=true \
        --functions wecare-invoice-engine wecare-messages-read --apply
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import time

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
SNAPSHOT_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs/execution/snapshots"


def _lam():
    return boto3.client("lambda", region_name=REGION)


def read_env(lam, name: str) -> dict:
    config = lam.get_function_configuration(FunctionName=name)
    return dict((config.get("Environment") or {}).get("Variables") or {})


def live_version(lam, name: str) -> str | None:
    try:
        return lam.get_alias(FunctionName=name, Name="live")["FunctionVersion"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            return None
        raise


def wait_active(lam, name: str, timeout: int = 90) -> bool:
    for _ in range(timeout // 3):
        config = lam.get_function_configuration(FunctionName=name)
        if config.get("LastUpdateStatus") != "InProgress" and config.get("State") == "Active":
            return True
        time.sleep(3)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", metavar="KEY=VALUE")
    parser.add_argument("--list", metavar="KEY")
    parser.add_argument("--functions", nargs="*", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()

    lam = _lam()

    if args.list:
        names = args.functions or [
            f["FunctionName"] for page in lam.get_paginator("list_functions").paginate()
            for f in page["Functions"]]
        present = []
        for name in sorted(names):
            env = read_env(lam, name)
            if args.list in env:
                present.append((name, env[args.list]))
        print(f"{args.list}: set on {len(present)} of {len(names)} function(s)")
        for name, value in present:
            print(f"  {name} = {value}")
        return 0

    if not args.set or "=" not in args.set:
        print("--set expects KEY=VALUE", file=sys.stderr)
        return 2
    key, value = args.set.split("=", 1)
    if not args.functions:
        print("--functions is required with --set", file=sys.stderr)
        return 2

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    before: dict[str, dict] = {}
    for name in args.functions:
        try:
            before[name] = {"env": read_env(lam, name), "live": live_version(lam, name)}
        except ClientError as exc:
            print(f"  {name}: {exc.response['Error']['Code']}", file=sys.stderr)
            return 2

    print(f"{key} -> {value!r} on {len(args.functions)} function(s)")
    for name, state in before.items():
        current = state["env"].get(key, "<absent>")
        print(f"  {name:34s} {key}={current}  "
              f"(preserving {len(state['env'])} var(s), live={state['live']})")

    if not args.apply:
        print("\n(dry run; pass --apply)")
        return 0

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = SNAPSHOT_DIR / f"lambda-env-before-{key.lower()}-{stamp}.json"
    snapshot.write_text(json.dumps(before, indent=2, default=str) + "\n")
    print(f"\nsnapshot: {snapshot.relative_to(SNAPSHOT_DIR.parents[2])}")

    failures = 0
    for name in args.functions:
        merged = dict(before[name]["env"])
        merged[key] = value
        try:
            lam.update_function_configuration(
                FunctionName=name, Environment={"Variables": merged})
            if not wait_active(lam, name):
                print(f"  {name}: did not return to Active in time", file=sys.stderr)
                failures += 1
                continue
            after = read_env(lam, name)
            lost = sorted(set(before[name]["env"]) - set(after))
            if lost:
                print(f"  {name}: LOST {lost}", file=sys.stderr)
                failures += 1
                continue
            if after.get(key) != value:
                print(f"  {name}: did not take ({after.get(key)!r})", file=sys.stderr)
                failures += 1
                continue

            published = None
            if before[name]["live"] and not args.no_publish:
                published = lam.publish_version(FunctionName=name)["Version"]
                lam.update_alias(FunctionName=name, Name="live",
                                 FunctionVersion=published)
            print(f"  OK  {name:34s} {len(after)} var(s) kept"
                  + (f", live {before[name]['live']} -> {published}" if published
                     else ", no live alias (env applies to $LATEST)"))
        except ClientError as exc:
            print(f"  {name}: {exc.response['Error']['Code']}: "
                  f"{exc.response['Error']['Message'][:120]}", file=sys.stderr)
            failures += 1

    print(f"\nupdated={len(args.functions) - failures} failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
