#!/usr/bin/env python3
"""Write a provider credential to a 0600 file OUTSIDE the repo, for your own eyes.

WHY THIS EXISTS
---------------
You need the RCS username and password to verify them against what the service
provider holds. An agent must not print them: chat is persisted into
`~/.kiro/logs` and the session transcript, so a value displayed once has to be
treated as compromised and rotated. On 2026-09-19 four live credentials ended up
in plaintext on disk by exactly that route.

So the value never goes to stdout. It goes to a file only you open.

WHAT IT GUARANTEES
------------------
* stdout carries the destination path, field names, lengths, and an irreversible
  `sha256[:12]` fingerprint per field. Never a value.
* the destination is `~/.provider-verify/`, outside the repo and outside any
  synced folder, created `0700`; the file is written `0600` via an atomic
  `os.open(..., O_CREAT|O_EXCL, 0o600)` so it is never briefly world-readable.
* `--fingerprint-only` writes nothing at all. Use it to confirm a value matches
  the provider's without either side revealing it: ask them for the sha256 of
  the value they hold, compare the first 12 hex characters.
* it refuses to write anywhere inside the repository, into iCloud/Dropbox/
  OneDrive/Google Drive, or to a path that already exists.

It calls `GetSecretValue`, which the project's own rules otherwise forbid. That
is the point of it being a deliberate, human-run, single-purpose script rather
than something an agent invokes: the value goes to a file, not into a model's
context. Do not import this module from anything.

USAGE
-----
    python scripts/export_provider_credentials.py --list
    python scripts/export_provider_credentials.py --secret wecare/sinch/rcs
    python scripts/export_provider_credentials.py --secret wecare/sinch/rcs --fingerprint-only

Afterwards, delete the file:

    shred -u ~/.provider-verify/<name>.txt      # gshred, or `rm -P` on macOS
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

OUT_DIR = Path.home() / ".provider-verify"

#: Provider credentials it is reasonable to verify against a provider. Anything
#: else must be named explicitly with --secret and --i-know-what-i-am-doing, so a
#: careless glob cannot dump the whole vault.
KNOWN = {
    "wecare/sinch/rcs": "Sinch/ACL RCS — username, password, project_id, app_id, bot_id",
    "wecare/plivo/api": "Plivo — auth_id, auth_token (the V3 signing key)",
    "wecare/plivo-answer": "Plivo — diagnostic ?token= bearer",
}

#: Directories a credential must never be written into.
SYNCED = ("Library/Mobile Documents", "iCloud", "Dropbox", "OneDrive",
          "Google Drive", "Creative Cloud Files")


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else "-"


def refuse_unsafe_destination(path: Path) -> None:
    resolved = path.resolve()
    repo = Path(__file__).resolve().parent.parent
    if repo in resolved.parents or resolved == repo:
        sys.exit(f"REFUSED: {resolved} is inside the repository.")
    for marker in SYNCED:
        if marker.lower() in str(resolved).lower():
            sys.exit(f"REFUSED: {resolved} looks like a cloud-synced folder ({marker}).")
    if resolved.exists():
        sys.exit(f"REFUSED: {resolved} already exists. Delete it first, "
                 "so an old value is never silently kept.")


def load(secret_id: str) -> dict:
    try:
        import boto3
    except ImportError:
        sys.exit("boto3 not available. Run with the project venv: "
                 ".venv/bin/python scripts/export_provider_credentials.py ...")
    client = boto3.client(
        "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    raw = client.get_secret_value(SecretId=secret_id)["SecretString"]
    try:
        data = json.loads(raw)
    except ValueError:
        return {"_raw": raw}
    if not isinstance(data, dict):
        return {"_raw": str(data)}
    return data


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Write a provider credential to a 0600 file for manual "
                    "verification. Never prints a value.")
    p.add_argument("--secret", help="Secrets Manager id, e.g. wecare/sinch/rcs")
    p.add_argument("--list", action="store_true",
                   help="show the credentials this tool knows about")
    p.add_argument("--fingerprint-only", action="store_true",
                   help="print field fingerprints and write NOTHING")
    p.add_argument("--i-know-what-i-am-doing", action="store_true",
                   help="allow a secret id outside the known list")
    args = p.parse_args(argv)

    if args.list or not args.secret:
        print("Credentials this tool will export:\n")
        for k, v in KNOWN.items():
            print(f"  {k:24s} {v}")
        print("\nAdd --secret <id> to export one.")
        print("Values are written to a 0600 file under "
              f"{OUT_DIR}; they are never printed.")
        return 0

    if args.secret not in KNOWN and not args.i_know_what_i_am_doing:
        print(f"'{args.secret}' is not in the known list. Re-run with "
              "--i-know-what-i-am-doing if that is deliberate.", file=sys.stderr)
        return 2

    data = load(args.secret)
    fields = sorted(data)

    print(f"secret : {args.secret}")
    print(f"fields : {len(fields)}\n")
    print(f"  {'field':22s} {'present':8s} {'len':>5s}  sha256[:12]")
    print(f"  {'-'*22} {'-'*8} {'-'*5}  {'-'*12}")
    for k in fields:
        v = str(data.get(k) or "")
        print(f"  {k:22s} {'YES' if v else 'no':8s} {len(v):5d}  {fingerprint(v)}")
    print()

    if args.fingerprint_only:
        print("--fingerprint-only: nothing written.")
        print("To verify without disclosure, ask the provider for the sha256 of "
              "the value they hold and compare the first 12 hex characters.")
        return 0

    OUT_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(OUT_DIR, 0o700)
    dest = OUT_DIR / (args.secret.replace("/", "-") + ".txt")
    refuse_unsafe_destination(dest)

    body = [f"# {args.secret}",
            "# Written for manual provider verification. DELETE AFTER USE.",
            f"#   shred -u {dest}", ""]
    for k in fields:
        body.append(f"{k}={data.get(k)}")
    body.append("")

    # O_EXCL so we never overwrite, and mode at creation so the file is never
    # briefly readable by anyone else.
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(body))
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    st = dest.stat()
    print(f"written : {dest}")
    print(f"mode    : {oct(st.st_mode & 0o777)}   bytes: {st.st_size}")
    print()
    print("Open it yourself, verify against the provider, then delete it:")
    print(f"  shred -u {dest}        # gshred, or: rm -P {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
