#!/usr/bin/env python3
"""Deny the handful of actions that cannot be undone. Kiro PreToolUse hook.

Why this exists
---------------
This workspace runs with blanket ``allow`` permissions so long agent runs are not
interrupted (see ``scripts/apply_unattended_permissions.py``). That trade is only
defensible if the genuinely irreversible actions are stopped by something that
does **not** need a human in the loop.

Prompting is the wrong control for an unattended fleet. It blocks the 999 safe
commands and depends on a tired human to catch the one bad one. So this hook
inverts it: allow everything, and refuse a short, explicit list of operations
whose blast radius cannot be walked back.

Two tiers
---------
**BLOCK (exit 2)** - no legitimate agent-initiated use, or a safe alternative
always exists:

* ``rm``/``shred``/``truncate`` targeting ``/``, ``$HOME``, ``~/.aws``,
  ``~/.ssh``, ``~/.kiro``, ``~/.gnupg`` or the repository root
* any destruction, truncation, move or overwrite of
  ``~/aws-new-keys-SAVE-THEN-DELETE.txt`` - the steering file
  ``plaintext-source-policy`` marks it **RETAIN UNTIL PROJECT COMPLETE** and
  supersedes its own filename, with deletion gated behind an explicit
  ``YES PROJECT-CLOSE-001``
* truncation or overwrite of ``~/.aws/credentials`` (the only thing granting this
  account non-interactively) or ``~/.ssh`` private keys
* ``chmod`` widening on those files - steering says never widen past ``0600``
* ``aws secretsmanager get-secret-value`` / ``batch-get-secret-value`` - the
  ``aws-agent-rules`` steering forbids it outright, because it pulls the value
  into the transcript. Use
  ``{{resolve:secretsmanager:<name>:SecretString:<key>}}`` or read it inside the
  Lambda at runtime.
* disk-level writes: ``diskutil eraseDisk``, ``dd of=/dev/disk*``, ``mkfs``
* ``sudo rm -rf``

**ASK (exit 0 + permissionDecision)** - AWS resource deletion. The
``maintenance-reporting`` steering already requires pointwise confirmation for
deleting a secret, bucket, Lambda, database, queue or topic, and for IAM and KMS
changes. Stalling for a human is the *correct* behaviour here, so these are
surfaced rather than silently blocked.

Ordinary cleanup is untouched: ``rm -rf node_modules``, ``rm -rf .next``,
``rm build/artifact.zip`` all pass.

Self-test
---------
    python scripts/block_catastrophic.py --self-test
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_shell_parse import (  # noqa: E402
    program_and_args,
    redirect_targets,
    segments as shell_segments,
)

HOME = Path.home()
REPO = Path("/Users/wecaredigital/wecare-store")

# Deleting any of these breaks the machine, the account, or the project.
PROTECTED_DIRS = [
    Path("/"),
    HOME,
    HOME / ".aws",
    HOME / ".ssh",
    HOME / ".kiro",
    HOME / ".gnupg",
    HOME / ".secure-backups",
    REPO,
]

# Retained by explicit user decision despite the filename. See the
# plaintext-source-policy steering file.
RETAINED_PLAINTEXT = HOME / "aws-new-keys-SAVE-THEN-DELETE.txt"

# Overwriting these locks you out or destroys recovery material.
PROTECTED_FILES = [
    RETAINED_PLAINTEXT,
    HOME / ".aws/credentials",
    HOME / ".aws/config",
    HOME / ".secure-backups/wecare-secrets-backup.txt.enc",
]

DESTRUCTIVE_AWS = {
    ("secretsmanager", "delete-secret"): "deletes a secret consumed by live Lambdas",
    ("s3api", "delete-bucket"): "deletes an S3 bucket",
    ("s3", "rb"): "removes an S3 bucket",
    ("lambda", "delete-function"): "deletes a Lambda function",
    ("lambda", "delete-alias"): "deletes a Lambda alias the HTTP API routes to",
    ("dynamodb", "delete-table"): "deletes a DynamoDB table and its data",
    ("cloudformation", "delete-stack"): "deletes a CloudFormation stack",
    ("kms", "schedule-key-deletion"): "schedules deletion of a KMS key",
    ("iam", "delete-role"): "deletes an IAM role",
    ("iam", "delete-user"): "deletes an IAM user",
    ("iam", "delete-policy"): "deletes an IAM policy",
    ("iam", "detach-role-policy"): "detaches an IAM policy from a role",
    ("sqs", "delete-queue"): "deletes an SQS queue",
    ("sns", "delete-topic"): "deletes an SNS topic",
    ("rds", "delete-db-instance"): "deletes an RDS instance",
    ("route53", "delete-hosted-zone"): "deletes a Route 53 hosted zone",
}

# Steering aws-agent-rules: never pull a secret value into context.
FORBIDDEN_AWS = {
    ("secretsmanager", "get-secret-value"):
        "pulls a raw secret value into the transcript; use "
        "{{resolve:secretsmanager:<name>:SecretString:<key>}} or read it inside "
        "the function at runtime",
    ("secretsmanager", "batch-get-secret-value"):
        "pulls raw secret values into the transcript",
}


# --------------------------------------------------------------------------- #
# path handling
# --------------------------------------------------------------------------- #

def resolve_target(raw: str) -> Path | None:
    """Expand a shell word to an absolute path, best effort, no filesystem I/O."""
    t = raw.strip().strip("'\"")
    if not t or t.startswith("-"):
        return None
    t = t.replace("$HOME", str(HOME)).replace("${HOME}", str(HOME))
    t = os.path.expanduser(t)
    # Strip a trailing glob so "rm -rf ~/*" is judged against the home directory.
    t = re.sub(r"/\*+$", "", t)
    if not t:
        t = str(HOME)
    try:
        p = Path(t)
        return p if p.is_absolute() else (REPO / p)
    except (OSError, ValueError):
        return None


def same_or_inside(target: Path, protected: Path) -> bool:
    """True when target IS protected (not merely nested inside it)."""
    try:
        return target.resolve(strict=False) == protected.resolve(strict=False)
    except (OSError, RuntimeError):
        return str(target).rstrip("/") == str(protected).rstrip("/")


# --------------------------------------------------------------------------- #
# payload
# --------------------------------------------------------------------------- #

def find_commands(payload: object) -> list[str]:
    found: list[str] = []
    fallback: list[str] = []

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, str(k))
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str):
            if key.lower() in ("command", "cmd", "commandline", "command_line",
                               "script", "shellcommand"):
                found.append(node)
            else:
                fallback.append(node)

    walk(payload)
    return found or fallback


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #

def check_segment(segment: str) -> list[tuple[str, str]]:
    """Return [(severity, reason)] for one shell segment.

    Only the program in *command position* is inspected. Scanning every token, as
    an earlier version did, meant the word ``truncate`` inside a commit message
    looked like an invocation with ``/`` and ``$HOME`` as its arguments.
    """
    out: list[tuple[str, str]] = []

    # Redirection is checked against the raw segment: `>` is unambiguous and
    # cannot be mistaken for prose the way a program name can.
    for raw in redirect_targets(segment):
        tgt = resolve_target(raw)
        if tgt and any(same_or_inside(tgt, p) for p in PROTECTED_FILES):
            out.append(("block", f"redirection would overwrite {tgt}"))

    prog, args, sudo = program_and_args(segment)
    if not prog:
        return out

    if prog in ("rm", "shred", "truncate", "srm"):
        recursive = any(
            a.startswith("-") and not a.startswith("--") and
            ("r" in a[1:] or "R" in a[1:]) for a in args
        ) or "--recursive" in args
        for a in args:
            tgt = resolve_target(a)
            if not tgt:
                continue
            if any(same_or_inside(tgt, p) for p in PROTECTED_FILES):
                label = ("the RETAINED plaintext credential source "
                         "(steering: retain until PROJECT COMPLETE, gated "
                         "behind YES PROJECT-CLOSE-001)"
                         if same_or_inside(tgt, RETAINED_PLAINTEXT)
                         else "a protected credential file")
                out.append(("block", f"`{prog}` would destroy {tgt} - {label}"))
            for p in PROTECTED_DIRS:
                if same_or_inside(tgt, p):
                    out.append((
                        "block",
                        f"`{prog}` targets {tgt}"
                        + (" recursively" if recursive else "")
                        + " - protected location"))
        # Any privileged recursive delete is refused regardless of target. An
        # agent has no legitimate need for it, and the blast radius of getting
        # the path wrong under sudo is the whole machine.
        if sudo and recursive:
            out.append(("block",
                        "`sudo rm -r` is a privileged recursive delete; refused "
                        "regardless of target"))
        return out

    if prog == "mv":
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            src = resolve_target(positional[0])
            if src and any(same_or_inside(src, p) for p in PROTECTED_FILES):
                out.append(("block", f"`mv` would relocate {src}, a protected "
                                     f"credential file"))
        return out

    if prog == "chmod":
        mode = next((a for a in args
                     if re.fullmatch(r"[0-7]{3,4}|[ugoa]*[+=][rwx]+", a)), None)
        widens = bool(mode and (
            (re.fullmatch(r"[0-7]?[0-7][0-7][0-7]", mode) and mode[-2:] != "00")
            or ("+" in mode and any(c in mode for c in "oga"))
        ))
        if widens:
            for a in args:
                tgt = resolve_target(a)
                if tgt and any(same_or_inside(tgt, p) for p in PROTECTED_FILES):
                    out.append(("block", f"`chmod {mode}` would widen permissions "
                                         f"on {tgt}; steering requires 0600"))
        return out

    if prog == "diskutil" and "eraseDisk" in args:
        out.append(("block", "`diskutil eraseDisk` erases a volume"))
        return out

    if prog == "dd":
        for a in args:
            if a.startswith("of=") and "/dev/" in a:
                out.append(("block", f"`dd {a}` writes directly to a device"))
        return out

    if prog.startswith("mkfs") or prog == "newfs":
        out.append(("block", f"`{prog}` formats a filesystem"))
        return out

    if prog == "aws":
        positional = [a for a in args if not a.startswith("-")]
        if len(positional) >= 2:
            pair = (positional[0], positional[1])
            if pair in FORBIDDEN_AWS:
                out.append(("block", f"`aws {pair[0]} {pair[1]}` "
                                     f"{FORBIDDEN_AWS[pair]}"))
            elif pair in DESTRUCTIVE_AWS:
                out.append(("ask", f"`aws {pair[0]} {pair[1]}` "
                                   f"{DESTRUCTIVE_AWS[pair]}"))
        return out

    return out


def decide(raw: str) -> tuple[int, str]:
    if not raw.strip():
        return 0, ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw

    blocks: list[str] = []
    asks: list[str] = []
    for command in find_commands(payload):
        for seg in shell_segments(command):
            for severity, reason in check_segment(seg):
                (blocks if severity == "block" else asks).append(reason)

    if blocks:
        return 2, (
            "BLOCKED: irreversible action.\n"
            + "\n".join(f"  - {r}" for r in dict.fromkeys(blocks)) + "\n"
            "This workspace runs with blanket allow permissions so long runs are "
            "not interrupted. That is only safe because this short list is "
            "refused outright. If you genuinely need this, a human must do it "
            "deliberately outside the agent."
        )

    if asks:
        return 0, json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Destructive AWS operation: "
                    + "; ".join(dict.fromkeys(asks))
                    + ". Project steering requires pointwise confirmation for "
                      "deleting a secret, bucket, Lambda, table, queue or topic, "
                      "and for IAM or KMS changes. Account 775261844268, "
                      "us-east-1."
                ),
            }
        })

    return 0, ""


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #

BLOCK_CASES = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf $HOME",
    "rm -rf ~/*",
    "rm -rf ~/.aws",
    "rm -rf ~/.ssh",
    "rm -rf ~/.kiro",
    "rm -rf /Users/wecaredigital/wecare-store",
    "rm ~/aws-new-keys-SAVE-THEN-DELETE.txt",
    "shred -u ~/aws-new-keys-SAVE-THEN-DELETE.txt",
    "truncate -s 0 ~/aws-new-keys-SAVE-THEN-DELETE.txt",
    "mv ~/aws-new-keys-SAVE-THEN-DELETE.txt /tmp/x",
    "echo x > ~/.aws/credentials",
    "chmod 644 ~/aws-new-keys-SAVE-THEN-DELETE.txt",
    "sudo rm -rf /var",
    "dd if=/dev/zero of=/dev/disk0",
    "diskutil eraseDisk JHFS+ Blank disk2",
    "aws secretsmanager get-secret-value --secret-id wecare/razorpay-webhook",
    "aws secretsmanager batch-get-secret-value --secret-id-list a b",
]

ASK_CASES = [
    "aws secretsmanager delete-secret --secret-id wecare/razorpay-webhook",
    "aws lambda delete-function --function-name wecare-contacts",
    "aws dynamodb delete-table --table-name wecare-contacts",
    "aws s3 rb s3://wecare-credential-backups-775261844268",
    "aws kms schedule-key-deletion --key-id abc",
    "aws iam delete-role --role-name wecare-lambda-role",
    "aws cloudformation delete-stack --stack-name wecare",
]

# Regression cases. Each of these was a real false positive, or is one token away
# from being one. On 2026-09-20 this guard blocked its own documentation.
PASS_CASES_REGRESSION = [
    # The actual failure: a commit message documenting this very guard.
    "git commit -q -F - <<'MSG'\n"
    "guard docs\n\n"
    "block-catastrophic refuses rm/shred/truncate on / $HOME ~/.aws ~/.ssh\n"
    "~/.kiro and the repo root, and `aws secretsmanager get-secret-value`.\n"
    "MSG",
    # Heredoc carrying a python script that merely mentions the words.
    "/usr/bin/python3 - <<'PY'\n"
    "print('never rm -rf / here')\n"
    "print('truncate ~/.aws/credentials is only a string')\n"
    "PY",
    # Dangerous names as arguments or filenames rather than programs.
    "grep -rn 'rm -rf /' docs/",
    "echo 'do not run rm -rf $HOME'",
    "ls -la scripts/block_catastrophic.py",
    "git log --grep='truncate'",
    "python scripts/block_catastrophic.py --self-test",
    # Paths that merely live under a protected directory are fine to remove.
    "rm -rf ~/.kiro/sessions/cli/stale.lock",
    "rm ~/.aws/cli/cache/tmp.json",
    # Wrapper forms that must still resolve to a harmless program.
    "env -u AWS_PROFILE python3 probe.py",
    "sudo -u nobody ls /tmp",
    "timeout 30 npm run build",
]

PASS_CASES = [
    "rm -rf node_modules",
    "rm -rf .next",
    "rm -rf .pytest_cache",
    "rm build/artifact.zip",
    "rm -f /tmp/scratch.txt",
    "ls -la ~/.aws",
    "cat ~/.aws/config",
    "chmod 600 ~/aws-new-keys-SAVE-THEN-DELETE.txt",
    "chmod +x scripts/session_map.py",
    "aws lambda list-functions",
    "aws lambda update-function-code --function-name wecare-contacts --zip-file x",
    "aws secretsmanager list-secrets",
    "python scripts/session_map.py",
    "git status --short",
    "echo hello > /tmp/out.txt",
]


def self_test() -> int:
    failures = 0
    for cmd in BLOCK_CASES:
        code, _ = decide(json.dumps({"command": cmd}))
        ok = code == 2
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  block  {cmd}")
    for cmd in ASK_CASES:
        code, msg = decide(json.dumps({"command": cmd}))
        ok = code == 0 and "permissionDecision" in msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  ask    {cmd}")
    for cmd in PASS_CASES:
        code, msg = decide(json.dumps({"command": cmd}))
        ok = code == 0 and not msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  pass   {cmd}")
    for cmd in PASS_CASES_REGRESSION:
        code, msg = decide(json.dumps({"command": cmd}))
        ok = code == 0 and not msg
        failures += not ok
        label = cmd.split("\n")[0][:64] + ("..." if "\n" in cmd else "")
        print(f"  {'ok  ' if ok else 'FAIL'}  regr   {label}")
    total = (len(BLOCK_CASES) + len(ASK_CASES) + len(PASS_CASES)
             + len(PASS_CASES_REGRESSION))
    print(f"\n{total - failures}/{total} cases passed")
    return 1 if failures else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    code, msg = decide(sys.stdin.read())
    if code == 2:
        print(msg, file=sys.stderr)
    elif msg:
        print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
