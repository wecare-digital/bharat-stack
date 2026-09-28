#!/usr/bin/env python3
"""Deploy the locally built static export straight to Amplify Hosting.

WHY THIS EXISTS. Amplify's own build stopped working on 2026-09-27: every job --
started from `StartJob` or from an incoming webhook, with the app's service role
present, replaced by a brand-new one, and removed entirely -- dies ~0.3s into BUILD
with

    !!! Unable to assume specified IAM Role.

The message is provably not about `iamServiceRoleArn`: job 966 ran with that field
cleared and failed identically, and job 960 succeeded 7 hours earlier with no IAM
or Amplify write event in between (verified against CloudTrail's 90-day history --
1,285 write events in the window, none of them amplify or iam except this
session's). Restoring Amplify's own builder needs `UpdateApp --repository`, which
requires a GitHub token, which is an owner action.

This path does not need one. `CreateDeployment` returns a presigned S3 URL, we PUT
the artifact there, and `StartDeployment` publishes it -- the same DEPLOY and
VERIFY steps a normal build ends with, minus the broken BUILD step. Production
therefore stops serving stale code while the builder is repaired.

SECRET HANDLING. `zipUploadUrl` is a presigned URL: it is write access to the
deployment bucket for anyone who holds it. It stays in memory, is never printed,
never an argument, never written to disk. Exceptions are logged by type, not text,
because a urllib error can echo the URL.

    python scripts/amplify_manual_deploy.py                # build must already exist
    python scripts/amplify_manual_deploy.py --build        # run `npm run build` first
    python scripts/amplify_manual_deploy.py --no-wait
"""

from __future__ import annotations

import argparse
import io
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
import zipfile

import boto3
from botocore.exceptions import ClientError

APP_ID = "d22dm4b0jn71jw"
BRANCH = "stack"
OUT_DIR = "out"

TERMINAL = {"SUCCEED", "FAILED", "CANCELLED"}


def _zip_directory(root: pathlib.Path) -> bytes:
    """Zip `root`'s *contents* (not the directory itself) into memory."""
    buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
                count += 1
    print(f"packaged {count} file(s), {buffer.tell() / 1_048_576:.1f} MiB")
    return buffer.getvalue()


def _run_build() -> None:
    env = dict(os.environ, NODE_ENV="production")
    print("running `npm run build` with NODE_ENV=production ...")
    result = subprocess.run(["npm", "run", "build"], env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f"build failed with exit {result.returncode}")


def deploy(app_id: str, branch: str, out_dir: str, wait: bool) -> int:
    root = pathlib.Path(out_dir)
    if not root.is_dir():
        print(f"{out_dir}/ does not exist -- run with --build first", file=sys.stderr)
        return 2

    payload = _zip_directory(root)

    amp = boto3.client("amplify", region_name="us-east-1")
    try:
        created = amp.create_deployment(appId=app_id, branchName=branch)
    except ClientError as exc:
        print(f"CreateDeployment refused: {exc.response['Error']['Code']}: "
              f"{exc.response['Error']['Message']}", file=sys.stderr)
        return 2

    job_id = created["jobId"]
    upload_url = created["zipUploadUrl"]
    request = urllib.request.Request(upload_url, data=payload, method="PUT",
                                     headers={"Content-Type": "application/zip"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            print(f"artifact uploaded (HTTP {response.status}) for job {job_id}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"artifact upload failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    finally:
        del upload_url, request, payload

    try:
        amp.start_deployment(appId=app_id, branchName=branch, jobId=job_id)
    except ClientError as exc:
        print(f"StartDeployment refused: {exc.response['Error']['Code']}", file=sys.stderr)
        return 2
    print(f"deployment {job_id} started")

    if not wait:
        return 0

    status = "PENDING"
    summary: dict = {}
    for _ in range(60):
        try:
            summary = amp.get_job(appId=app_id, branchName=branch, jobId=job_id)["job"]["summary"]
        except ClientError as exc:
            print(f"get_job failed: {exc.response['Error']['Code']}", file=sys.stderr)
            return 2
        status = summary["status"]
        print(f"  job {job_id}: {status}")
        if status in TERMINAL:
            break
        time.sleep(15)

    if status != "SUCCEED":
        print(f"job {job_id} finished {status}", file=sys.stderr)
        return 1
    print(f"job {job_id} SUCCEED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-id", default=APP_ID)
    parser.add_argument("--branch", default=BRANCH)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--build", action="store_true", help="run `npm run build` first")
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    if args.build:
        _run_build()
    return deploy(args.app_id, args.branch, args.out_dir, wait=not args.no_wait)


if __name__ == "__main__":
    raise SystemExit(main())
