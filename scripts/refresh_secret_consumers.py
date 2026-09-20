#!/usr/bin/env python3
"""Make every function that reads a secret pick up its new value, immediately.

Updating a value in Secrets Manager does not change what a running function
serves. Handlers cache the secret on first use so they are not paying an API call
per request, and ten of them cache it for the whole life of the execution
environment. A warm sandbox therefore keeps handing out the old credential for
as long as Lambda keeps it warm - minutes, or hours under steady traffic.

Measured on 2026-09-20: after the Meta verify token was replaced in Secrets
Manager, the live alias still accepted the *old* value and refused the new one.
Nothing was broken; the sandbox was simply still warm.

A published version has no warm execution environments, so moving the alias to a
freshly published version guarantees the next invocation re-reads Secrets
Manager. Publishing needs the version to differ from the last one, so a dated,
non-secret marker is written into the configuration first - otherwise Lambda
deduplicates and hands back the existing version, which is exactly the trap that
made the rotation look like it had failed.

    python scripts/refresh_secret_consumers.py wecare/meta-system-user-token
    python scripts/refresh_secret_consumers.py --list wecare/plivo/api
    python scripts/refresh_secret_consumers.py --all-secrets --dry-run

Consumers are found by reading the source, so a function that names the secret
only at runtime (the per-tenant `wecare/partners/<waba>` prefix) is reported
rather than guessed at.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
ALIAS = "live"


def load_specs():
    """Reuse the deploy script's function-name to source-directory map."""
    path = ROOT / "scripts" / "deploy_all_lambdas.py"
    spec = importlib.util.spec_from_file_location("_deploy_all", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_deploy_all"] = mod
    spec.loader.exec_module(mod)
    return mod.SPECS


SHARED = ROOT / "amplify/functions/shared/lambda_utils"


def names_in_code(text: str, secret_id: str) -> bool:
    """True when the secret id appears as a string the code actually evaluates.

    Prose does not count. `partner-onboarding` has a docstring whose whole point
    is that it reads `wecare/razorpay/api` and *not* `wecare/razorpay-webhook`,
    and a plain text search read that disclaimer as a dependency. Comments are
    absent from the AST, and a docstring is an expression statement, so both drop
    out while a real `SecretId='wecare/...'` argument or an environment default
    stays.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return secret_id in text

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and secret_id in node.value):
            return True
    return False


def _shared_modules_naming(secret_id: str) -> set[str]:
    """Shared lambda_utils modules that reference this secret id in code."""
    out = set()
    for py in SHARED.rglob("*.py"):
        try:
            if names_in_code(py.read_text(errors="replace"), secret_id):
                out.add(py.stem)
        except OSError:
            continue
    return out


def consumers(secret_id: str) -> list[tuple[str, str]]:
    """[(function_name, evidence)] for functions that actually read this secret.

    Packaging a helper is not using it. `lambda_utils/meta_client.py` names the
    Meta secret and is bundled into nearly every function, so matching on file
    contents alone reported 53 consumers for a secret that far fewer functions
    ever read. A function counts when its own source names the secret, or when
    its own source imports a shared module that does.
    """
    shared_mods = _shared_modules_naming(secret_id)
    out = []
    for spec in load_specs():
        if not spec.source.is_dir():
            continue
        own = list(spec.source.rglob("*.py"))
        evidence = None
        for py in own:
            try:
                text = py.read_text(errors="replace")
            except OSError:
                continue
            if names_in_code(text, secret_id):
                evidence = py.relative_to(ROOT).as_posix()
                break
            if spec.standalone:
                continue
            for mod in shared_mods:
                if re.search(rf"(from|import)\s+.*\b{re.escape(mod)}\b", text):
                    evidence = f"{py.relative_to(ROOT).as_posix()} -> lambda_utils.{mod}"
                    break
            if evidence:
                break
        if evidence:
            out.append((spec.name, evidence))
    return out


def refresh(lam, name: str, dry: bool) -> str:
    try:
        cfg = lam.get_function_configuration(FunctionName=name)
    except ClientError as exc:
        return f"SKIP  not deployed ({exc.response['Error']['Code']})"

    try:
        alias_before = lam.get_alias(FunctionName=name, Name=ALIAS)["FunctionVersion"]
        has_alias = True
    except ClientError:
        alias_before, has_alias = None, False

    if dry:
        where = f"alias {ALIAS} -> v{alias_before}" if has_alias else "$LATEST (no alias)"
        return f"would refresh  {where}"

    env = dict((cfg.get("Environment") or {}).get("Variables") or {})
    env["SECRETS_REFRESHED_AT"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lam.update_function_configuration(FunctionName=name, Environment={"Variables": env})
    lam.get_waiter("function_updated_v2").wait(FunctionName=name)

    if not has_alias:
        # No alias means the API invokes $LATEST, and a configuration change has
        # already replaced its execution environments.
        return "refreshed $LATEST (no alias; config change forces new sandboxes)"

    ver = lam.publish_version(FunctionName=name,
                              Description="refresh cached secrets after a rotation")
    v = ver["Version"]
    for _ in range(60):
        st = lam.get_function_configuration(FunctionName=name, Qualifier=v)
        if st.get("State") == "Active":
            break
        time.sleep(1)
    if st.get("State") != "Active":
        return f"FAIL  v{v} never became Active (state={st.get('State')})"
    lam.update_alias(FunctionName=name, Name=ALIAS, FunctionVersion=v)
    return f"{ALIAS}: v{alias_before} -> v{v}   (rollback: --function-version {alias_before})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("secret_id", nargs="?", help="e.g. wecare/meta-system-user-token")
    ap.add_argument("--all-secrets", action="store_true")
    ap.add_argument("--list", action="store_true", help="show consumers, change nothing")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.secret_id and not args.all_secrets:
        ap.error("give a secret id, or --all-secrets")

    sm = boto3.client("secretsmanager", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    if args.all_secrets:
        ids = []
        for page in sm.get_paginator("list_secrets").paginate():
            ids += [s["Name"] for s in page["SecretList"] if s["Name"].startswith("wecare/")]
        targets = sorted(set(ids))
    else:
        targets = [args.secret_id]

    print("=" * 74)
    print("REFRESH SECRET CONSUMERS")
    print("=" * 74)

    all_fns: dict[str, list[str]] = {}
    for sid in targets:
        found = consumers(sid)
        if not found:
            print(f"\n{sid}\n  no function source names this secret")
            continue
        print(f"\n{sid}")
        for fn, src in found:
            print(f"  {fn:38s} {src}")
            all_fns.setdefault(fn, []).append(sid)

    if args.list:
        print(f"\n{len(all_fns)} function(s) would be refreshed")
        return 0

    print(f"\nrefreshing {len(all_fns)} function(s)"
          f"{' (dry run)' if args.dry_run else ''}\n")
    failures = 0
    for fn in sorted(all_fns):
        result = refresh(lam, fn, args.dry_run)
        failures += result.startswith("FAIL")
        print(f"  {fn:38s} {result}")

    print("\n" + "=" * 74)
    print(f"functions refreshed: {len(all_fns) - failures}   failures: {failures}")
    print("Every refreshed function now re-reads Secrets Manager on its next call.")
    print("=" * 74)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
