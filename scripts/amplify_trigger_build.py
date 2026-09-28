#!/usr/bin/env python3
"""Trigger an Amplify Hosting build through an *incoming webhook*, not StartJob.

WHY THIS EXISTS. On 2026-09-27 every `aws amplify start-job` on app
`d22dm4b0jn71jw` failed ~1s into BUILD with

    !!! Unable to assume specified IAM Role.

while the last webhook-triggered build (job 960) had succeeded an hour earlier and
its log contains no role step at all. A brand-new service role with the trust
policy AWS documents verbatim failed identically, so the message is not about the
role's trust or permissions -- the two creation paths simply do different things.
This script exercises the path that is known to work.

SECRET HANDLING. An Amplify incoming-webhook URL carries a token in its query
string: anyone holding it can start a production deployment. So the URL is never
printed, never passed as an argument, and never written to disk. It is read from
the Amplify API into memory, POSTed to, and dropped. Per
`.kiro/steering/secret-handling.md`, "a secret value must never appear in a
command, a script argument, an environment assignment on a command line, or a log
line" -- that applies to this URL as much as to an API key.

The webhook is reused when one already exists for the branch, so repeated runs do
not accumulate deployment triggers.

    python scripts/amplify_trigger_build.py                  # create/reuse, fire, wait
    python scripts/amplify_trigger_build.py --no-wait
    python scripts/amplify_trigger_build.py --app-id X --branch Y
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError

APP_ID = "d22dm4b0jn71jw"
BRANCH = "stack"

TERMINAL = {"SUCCEED", "FAILED", "CANCELLED"}


def _client():
    return boto3.client("amplify", region_name="us-east-1")


def _find_or_create_webhook(amp, app_id: str, branch: str) -> str:
    """Return the webhook URL for the branch. Never log or return it elsewhere."""
    paginator_pages = []
    token = None
    while True:
        kwargs = {"appId": app_id, "maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        page = amp.list_webhooks(**kwargs)
        paginator_pages.extend(page.get("webhooks", []))
        token = page.get("nextToken")
        if not token:
            break

    for hook in paginator_pages:
        if hook.get("branchName") == branch:
            return hook["webhookUrl"]

    created = amp.create_webhook(
        appId=app_id,
        branchName=branch,
        description="Build trigger for CI. Created by scripts/amplify_trigger_build.py.",
    )
    return created["webhook"]["webhookUrl"]


def _latest_job_id(amp, app_id: str, branch: str) -> str | None:
    jobs = amp.list_jobs(appId=app_id, branchName=branch, maxResults=1).get("jobSummaries", [])
    return jobs[0]["jobId"] if jobs else None


def trigger(app_id: str, branch: str, wait: bool) -> int:
    amp = _client()

    before = _latest_job_id(amp, app_id, branch)

    url = _find_or_create_webhook(amp, app_id, branch)
    request = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
    except Exception as exc:                                  # noqa: BLE001
        # Deliberately type-only: the exception text can echo the request URL,
        # which carries the webhook token.
        print(f"webhook POST failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    finally:
        del url, request

    print(f"webhook accepted (HTTP {status}); previous job was {before}")

    job_id = None
    for _ in range(15):
        time.sleep(4)
        candidate = _latest_job_id(amp, app_id, branch)
        if candidate and candidate != before:
            job_id = candidate
            break
    if job_id is None:
        print("no new job appeared within 60s -- the webhook did not start a build",
              file=sys.stderr)
        return 1

    print(f"job {job_id} created")
    if not wait:
        return 0

    status = "PENDING"
    for _ in range(60):
        try:
            summary = amp.get_job(appId=app_id, branchName=branch,
                                  jobId=job_id)["job"]["summary"]
        except ClientError as exc:
            print(f"get_job failed: {exc.response['Error']['Code']}", file=sys.stderr)
            return 2
        status = summary["status"]
        print(f"  job {job_id}: {status}")
        if status in TERMINAL:
            break
        time.sleep(20)

    if status != "SUCCEED":
        print(f"job {job_id} finished {status}", file=sys.stderr)
        return 1
    print(f"job {job_id} SUCCEED (commit {summary.get('commitId')})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", default=APP_ID)
    parser.add_argument("--branch", default=BRANCH)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()
    return trigger(args.app_id, args.branch, wait=not args.no_wait)


if __name__ == "__main__":
    raise SystemExit(main())
