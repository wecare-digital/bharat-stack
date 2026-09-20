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
  Lambda at runtime. Both the aws-cli spelling and the boto3 spelling are
  refused; see "Two routes" below.

Two routes to the same API
--------------------------
Until 2026-09-20 this guard only watched shell commands, and its hook matcher
only listed ``execute_bash|control_bash_process``. That left the AWS MCP server
completely unguarded: ``~/.kiro/settings/mcp.json`` auto-approves
``aws___run_script``, which runs arbitrary Python against live ``wecare-prod``
credentials, and session transcripts showed 46 such calls already made. In that
route the forbidden operation looks like
``call_boto3(service_name="secretsmanager", operation_name="GetSecretValue")``
or ``client.get_secret_value(...)`` - invisible to shell parsing. An inline
``python3 -c`` had the same hole.

``check_api_shaped`` closes both. Its tables are derived from the CLI tables so
the two spellings cannot drift apart.
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

try:
    from unattended_mode import audit as _audit, is_waived as _is_waived
except ImportError:  # guard must never fail closed on a missing helper
    def _is_waived(kind: str = "") -> bool:
        return False

    def _audit(*_a, **_k) -> None:
        return None

HOME = Path.home()

# Derived, not hardcoded, so this guard works unchanged when copied into another
# project. The script lives in <repo>/scripts/, so the repo is its grandparent.
REPO = Path(__file__).resolve().parent.parent

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
# SDK-shaped equivalents of the two tables above
# --------------------------------------------------------------------------- #
# The tables above are spelled the way the *CLI* spells them (`aws
# secretsmanager get-secret-value`). That is only one of the routes an agent has
# to these APIs, and until 2026-09-20 it was the only one this guard could see.
#
# The gap: `~/.kiro/settings/mcp.json` auto-approves `aws___run_script`, which
# executes arbitrary Python against live `wecare-prod` boto3 credentials. This
# hook's matcher listed only `execute_bash|control_bash_process`, so that tool
# was never even evaluated - and had it been, the operation arrives as
# `call_boto3(service_name="secretsmanager", operation_name="GetSecretValue")`
# or `client.get_secret_value(...)`, which no amount of shell parsing will find.
# Measured the same day from session transcripts: 46 `aws___run_script` calls
# already made. An inline `python3 -c` in an ordinary shell command had the same
# hole.
#
# Both spellings are DERIVED from the tables above rather than listed a second
# time, so the CLI tier and the SDK tier cannot drift apart when someone edits
# one of them.

# `aws s3 rb` is a CLI-only convenience with no matching API operation, and its
# underlying DeleteBucket is already covered by ("s3api", "delete-bucket").
# Without this skip the derivation would invent a meaningless `Rb` / `rb` token
# and `.rb(` would match Ruby-ish attribute access in unrelated code.
_CLI_ONLY_VERBS = {("s3", "rb")}


def _api_forms(cli_verb: str) -> tuple[str, str]:
    """`get-secret-value` -> (`GetSecretValue`, `get_secret_value`)."""
    parts = cli_verb.split("-")
    return "".join(p.capitalize() for p in parts), "_".join(parts)


def _build_api_table(cli_table: dict) -> list[tuple[str, str, str, str]]:
    """[(label, PascalOperation, snake_operation, reason)] from a CLI table."""
    out: list[tuple[str, str, str, str]] = []
    for (service, verb), reason in cli_table.items():
        if (service, verb) in _CLI_ONLY_VERBS:
            continue
        pascal, snake = _api_forms(verb)
        out.append((f"{service}:{pascal}", pascal, snake, reason))
    return out


API_FORBIDDEN = _build_api_table(FORBIDDEN_AWS)
API_DESTRUCTIVE = _build_api_table(DESTRUCTIVE_AWS)


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


def all_strings(payload: object) -> str:
    """Every string anywhere in the payload, joined.

    ``find_commands`` is deliberately selective: it prefers values under a
    command-ish key and only falls back to everything. That is right for shell
    parsing and wrong for the SDK check, because `aws___run_script` delivers its
    Python under ``code`` - which is neither a command key nor reached by the
    fallback whenever some other string happens to occupy one.
    """
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            out.append(node)

    walk(payload)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #


def check_api_shaped(text: str) -> list[tuple[str, str]]:
    """Find boto3/SDK-shaped calls to the operations in the two AWS tables.

    Narrow on purpose. Matching a bare operation name anywhere in a string would
    fire on this file's own documentation and on any commit message describing
    the guard, so a hit requires call-ish syntax - either a quoted operation
    name, which is how ``call_boto3`` receives it, or an attribute call, which is
    how a boto3 client receives it.
    """
    out: list[tuple[str, str]] = []
    for table, severity in ((API_FORBIDDEN, "block"),
                            (API_DESTRUCTIVE, "ask")):
        for label, pascal, snake, reason in table:
            quoted = re.search(rf"""['"]{re.escape(pascal)}['"]""", text)
            called = re.search(rf"\.{re.escape(snake)}\s*\(", text)
            if not (quoted or called):
                continue
            how = ("operation_name/quoted API name" if quoted
                   else "boto3 client method call")
            out.append((severity, f"`{label}` via {how} - {reason}"))
    return out

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

    # The SDK route: MCP `aws___run_script`, or an inline `python3 -c`. Scanned
    # over the whole payload rather than per shell segment, because the code
    # arrives under `code` and no shell segment will ever contain it.
    for severity, reason in check_api_shaped(all_strings(payload)):
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
        reasons = "; ".join(dict.fromkeys(asks))

        # Unattended mode converts this tier from a prompt into a recorded
        # auto-approval, so a long run does not stall. The hard-block tier above
        # has already returned and is never waived. See scripts/unattended_mode.py.
        if _is_waived("aws_destructive_delete"):
            cmd = next(iter(find_commands(payload)), "")
            _audit("auto_approved_destructive_aws", reasons, cmd)
            return 0, ""

        return 0, json.dumps({
            "hookSpecificOutput": {
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Destructive AWS operation: " + reasons
                    + ". Project steering requires pointwise confirmation for "
                      "deleting a secret, bucket, Lambda, table, queue or topic, "
                      "and for IAM or KMS changes. Account 775261844268, "
                      "us-east-1. To run unattended instead, enable the recorded "
                      "mode: python scripts/unattended_mode.py on --reason '...'"
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

# SDK-shaped cases. These arrive as a `code` payload from
# `mcp_aws_mcp_aws___run_script` rather than as a shell command, so they exercise
# check_api_shaped() and would all have passed silently before 2026-09-20.
# Payloads are given whole, not as bare command strings, because the key the code
# sits under is part of what is being tested.
MCP_BLOCK_PAYLOADS = [
    ("run_script: GetSecretValue via call_boto3",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "r = await call_boto3(service_name='secretsmanager', "
              "operation_name='GetSecretValue', "
              "params={'SecretId': 'wecare/razorpay-webhook'})"}),
    ("run_script: boto3 client method",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "import boto3\n"
              "v = boto3.client('secretsmanager')"
              ".get_secret_value(SecretId='wecare/google-maps')"}),
    ("run_script: batch form",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='secretsmanager', "
              "operation_name='BatchGetSecretValue')"}),
    ("shell python3 -c reaching the same API",
     {"toolName": "execute_bash",
      "command": "python3 -c \"import boto3;print(boto3.client("
                 "'secretsmanager').get_secret_value(SecretId='x'))\""}),
]

MCP_ASK_PAYLOADS = [
    ("run_script: DeleteSecret",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='secretsmanager', "
              "operation_name='DeleteSecret', params={'SecretId': 'x'})"}),
    ("run_script: delete_function",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "boto3.client('lambda')"
              ".delete_function(FunctionName='wecare-contacts')"}),
    ("run_script: DeleteTable",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='dynamodb', "
              "operation_name='DeleteTable')"}),
    ("run_script: ScheduleKeyDeletion",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='kms', "
              "operation_name='ScheduleKeyDeletion', params={'KeyId': 'k'})"}),
]

# Read-only SDK work must stay silent, and the guard must not trip over prose
# describing itself - the same class of false positive that made it block its own
# commit message on 2026-09-20.
MCP_PASS_PAYLOADS = [
    ("run_script: ListFunctions",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='lambda', "
              "operation_name='ListFunctions')"}),
    ("run_script: GetFunctionConfiguration",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='lambda', "
              "operation_name='GetFunctionConfiguration', "
              "params={'FunctionName': 'wecare-contacts'})"}),
    ("run_script: ListSecrets names only, no value read",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='secretsmanager', "
              "operation_name='ListSecrets')"}),
    ("run_script: DescribeSecret metadata is not the value",
     {"toolName": "mcp_aws_mcp_aws___run_script",
      "code": "await call_boto3(service_name='secretsmanager', "
              "operation_name='DescribeSecret', params={'SecretId': 'x'})"}),
    ("commit message describing this guard must not self-trigger",
     {"toolName": "execute_bash",
      "command": "git commit -q -F - <<'MSG'\n"
                 "guard: cover the aws___run_script route\n\n"
                 "block_catastrophic now refuses get-secret-value in boto3 form\n"
                 "as well as the aws-cli spelling, because mcp.json\n"
                 "auto-approves aws___run_script.\n"
                 "MSG"}),
]


# Tool names this guard must actually be wired to, verified against the `toolName`
# field in session transcripts rather than guessed. Checked because every case
# below invokes decide() directly, so they would all keep passing even if the
# hook's matcher stopped firing - and a silent no-op guard is worse than a known
# gap, because nothing reports it.
MUST_MATCH_TOOLS = [
    "execute_bash",
    "control_bash_process",
    "mcp_aws_mcp_aws___run_script",
]


def check_matcher() -> int:
    """Confirm the hook matcher fires on every tool this guard must cover."""
    hook = Path(__file__).resolve().parents[1] / ".kiro/hooks/block-catastrophic.json"
    failures = 0
    try:
        matcher = json.loads(hook.read_text())["hooks"][0].get("matcher", "")
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  FAIL  cannot read matcher from {hook}: {e}")
        return 1
    print(f"  matcher: {matcher!r}")
    for tool in MUST_MATCH_TOOLS:
        hit = bool(re.search(matcher, tool)) if matcher else False
        failures += not hit
        print(f"  {'ok  ' if hit else 'FAIL'}  matcher fires on {tool}")
    return failures


def self_test() -> int:
    # Isolate from the machine's real unattended flag. Without this the ask-tier
    # cases fail whenever unattended mode happens to be on, which tests the
    # operator's current state rather than this guard's logic.
    global _is_waived, _audit
    real_is_waived = _is_waived
    _is_waived = lambda kind="": False          # noqa: E731
    _audit = lambda *a, **k: None               # noqa: E731

    failures = check_matcher()
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

    # The SDK route, still with the mode off.
    for label, payload in MCP_BLOCK_PAYLOADS:
        code, _ = decide(json.dumps(payload))
        ok = code == 2
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  sdk-block  {label}")
    for label, payload in MCP_ASK_PAYLOADS:
        code, msg = decide(json.dumps(payload))
        ok = code == 0 and "permissionDecision" in msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  sdk-ask    {label}")

    # With the mode ON, the ask tier must auto-approve and the block tier must not.
    _is_waived = lambda kind="": kind == "aws_destructive_delete"   # noqa: E731
    for cmd in ASK_CASES:
        code, msg = decide(json.dumps({"command": cmd}))
        ok = code == 0 and not msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  unatt-allow  {cmd}")
    for cmd in BLOCK_CASES[:6]:
        code, _ = decide(json.dumps({"command": cmd}))
        ok = code == 2
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  unatt-block  {cmd}")

    # This is the behaviour that is live right now: unattended mode is ON, so an
    # SDK-shaped destructive delete proceeds with an audit record, while an
    # SDK-shaped secret read stays refused. The waiver must not leak across tiers.
    for label, payload in MCP_ASK_PAYLOADS:
        code, msg = decide(json.dumps(payload))
        ok = code == 0 and not msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  unatt-sdk-allow  {label}")
    for label, payload in MCP_BLOCK_PAYLOADS:
        code, _ = decide(json.dumps(payload))
        ok = code == 2
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  unatt-sdk-block  {label}")
    _is_waived = real_is_waived
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

    # Forced off for these. With the mode on, "code 0 and no message" is
    # ambiguous - it cannot distinguish "correctly silent" from "asked, then
    # auto-approved", so a false positive would pass unnoticed.
    _is_waived = lambda kind="": False          # noqa: E731
    for label, payload in MCP_PASS_PAYLOADS:
        code, msg = decide(json.dumps(payload))
        ok = code == 0 and not msg
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  sdk-pass   {label}")
    _is_waived = real_is_waived

    total = (len(BLOCK_CASES) + len(ASK_CASES) * 2 + len(PASS_CASES)
             + len(PASS_CASES_REGRESSION) + 6
             + len(MCP_BLOCK_PAYLOADS) * 2 + len(MCP_ASK_PAYLOADS) * 2
             + len(MCP_PASS_PAYLOADS) + len(MUST_MATCH_TOOLS))
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
