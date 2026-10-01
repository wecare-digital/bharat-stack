#!/usr/bin/env python3
"""Validate an immutable supplied patch against an exact stack base; no execution."""
import argparse
import hashlib
import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("patch_policy", ROOT / "amplify/functions/ai/workspace-mcp/patch_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.base): raise SystemExit("Invalid base SHA")
    match = re.fullmatch(r"workspace-mcp/patches/([a-f0-9]{64})/([a-f0-9]{64})\.patch", args.key)
    if not match or args.job != match[2]: raise SystemExit("Invalid artifact identity")
    patch_path = Path(args.patch).resolve(strict=True)
    if not patch_path.is_relative_to(ROOT) or patch_path.stat().st_size > 32768:
        raise SystemExit("Patch must be a bounded file inside this checkout")
    patch = patch_path.read_text()
    if hashlib.sha256((match[1] + args.base + patch).encode()).hexdigest() != args.job:
        raise SystemExit("Artifact checksum does not match the submitted job")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != args.base:
        raise SystemExit("Stack moved; resubmit on its new base")
    paths = policy.validate_patch(patch)
    subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=ROOT, check=True)
    subprocess.run(["git", "apply", str(patch_path)], cwd=ROOT, check=True)
    actual = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines()
    if sorted(actual) != paths: raise SystemExit("Applied paths differ from allowlist")
    print("Validated paths: " + ", ".join(paths))


if __name__ == "__main__": main()
