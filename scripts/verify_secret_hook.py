#!/usr/bin/env python3
"""Verify the block_inline_secrets hook end to end.

Secret-shaped test values are ASSEMBLED AT RUNTIME from fragments, so this
file itself contains no literal that would trip the very guard it tests
(and no literal that could be recorded anywhere).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = json.loads((ROOT / ".kiro/hooks/block-inline-secrets.json").read_text())
HOOK_CMD = HOOK["hooks"][0]["action"]["command"]

A = "A" * 24
# assembled, never literal
RZP = "rzp" + "_live_" + "ABCDEFGH1234"
OAI = "sk" + "-svcacct-" + A
GK = "AIz" + "a" + "Sy" + "B" * 33
AWSK = "AKI" + "A" + "IOSFODNN7EXAMPLE"
GH = "ghp" + "_" + "c" * 36
PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"

CASES = [
    # (label, payload dict, expected exit)
    ("razorpay live inline",   {"command": f'RZP_ID="{RZP}" python3 -c 1'}, 2),
    ("openai svcacct inline",  {"command": f'OPENAI_ADS_KEY="{OAI}" python3 x.py'}, 2),
    ("google api key inline",  {"command": f'GOOGLE_KEY="{GK}" python3 x.py'}, 2),
    ("aws access key id",      {"command": f"AWS_ACCESS_KEY_ID={AWSK} aws s3 ls"}, 2),
    ("github token in url",    {"command": f"git clone https://{GH}@github.com/x/y"}, 2),
    ("private key pem",        {"command": f'echo "{PEM}" > k.pem'}, 2),
    ("generic SECRET= literal", {"command": f'SOME_API_SECRET="{A}" ./run.sh'}, 2),

    ("plain build",            {"command": "npm run build"}, 0),
    ("pytest",                 {"command": ".venv/bin/python -m pytest -q"}, 0),
    ("git push",               {"command": "git push origin stack"}, 0),
    ("listening port",         {"command": "lsof -nP -iTCP:5476 -sTCP:LISTEN"}, 0),
    ("NODE_ENV",               {"command": "NODE_ENV=production npm run build"}, 0),
    ("secret by NAME boto3",   {"command": "py -c \"c.get_secret_value(SecretId='wecare/razorpay-webhook')\""}, 0),
    ("secret by NAME cli",     {"command": "asm-exec --secret-id wecare/google-maps"}, 0),
    ("cfn resolve ref",        {"command": "deploy --p {{resolve:secretsmanager:wecare/google-maps:SecretString:api_key}}"}, 0),
    ("env var NAME not value", {"command": "RAZORPAY_WEBHOOK_SECRET=wecare/razorpay-webhook python3 app.py"}, 0),
    ("brew install",           {"command": "brew install ffmpeg"}, 0),
    ("empty",                  {}, 0),
]


def run(payload: dict) -> int:
    p = subprocess.run(
        ["sh", "-c", HOOK_CMD],
        input=json.dumps(payload).encode() if payload else b"",
        capture_output=True,
    )
    return p.returncode


def main() -> int:
    ok = bad = 0
    print(f"hook command under test:\n  {HOOK_CMD}\n")
    for label, payload, want in CASES:
        got = run(payload)
        verdict = "PASS" if got == want else "FAIL"
        if got == want:
            ok += 1
        else:
            bad += 1
        kind = "block" if want == 2 else "allow"
        print(f"  {verdict}  expect-{kind:5s} got={got}  {label}")
    print(f"\n{ok} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
