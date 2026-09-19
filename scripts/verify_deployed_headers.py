#!/usr/bin/env python3
"""Assert the DEPLOYED security headers, not the ones in config.

Why this exists
---------------
The app is a static export. `next.config.js` declares a `headers()` block, but
Next.js only serves those when it runs as a server (`next start`); with
`output: export` the artifacts are plain files and the response headers come from
`amplify.yml` `customHeaders`.

On 2026-09-19 the two disagreed: `next.config.js` allowed `microphone=(self)`
while the deployed header sent `microphone=()`. Reading the Next config - the
file that looks like it configures this - gave the wrong answer, and the Plivo
Browser SDK would have been denied the microphone with no visible cause.

So this check reads the live response. A config assertion cannot catch that class
of bug, because the config was already correct.

Usage
-----
    python scripts/verify_deployed_headers.py
    python scripts/verify_deployed_headers.py --url https://app.wecare.digital
    python scripts/verify_deployed_headers.py --local   # parse amplify.yml only

Exit codes
    0  every required header matches
    1  a header is missing or wrong
    2  the request failed (network, DNS, TLS) - NOT a header failure
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://app.wecare.digital/"

# Directive -> required allowlist. The microphone is same-origin because the
# softphone needs it; camera and geolocation are denied outright.
REQUIRED_PERMISSIONS = {
    "camera": "()",
    "microphone": "(self)",
    "geolocation": "()",
}

OTHER_REQUIRED = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}

ROOT = Path(__file__).resolve().parent.parent


def parse_permissions_policy(value: str) -> dict:
    """'camera=(), microphone=(self)' -> {'camera': '()', 'microphone': '(self)'}"""
    found = {}
    for part in value.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, allowlist = part.partition("=")
        found[name.strip().lower()] = allowlist.strip()
    return found


def check_permissions(value: str) -> list:
    """Returns a list of failure strings; empty means compliant."""
    failures = []
    found = parse_permissions_policy(value)
    for directive, expected in REQUIRED_PERMISSIONS.items():
        actual = found.get(directive)
        if actual is None:
            failures.append(f"{directive} missing (expected {expected})")
        elif actual != expected:
            failures.append(f"{directive}={actual}, expected {expected}")
    return failures


def amplify_yml_header() -> str:
    """The Permissions-Policy from amplify.yml, which is what actually deploys.

    Deliberately a narrow regex rather than a YAML parse: this script must run
    with no third-party dependency, since it is also useful in a bare CI shell.
    """
    text = (ROOT / "amplify.yml").read_text()
    match = re.search(
        r"key:\s*Permissions-Policy\s*\n\s*value:\s*[\"']?([^\"'\n]+)[\"']?",
        text)
    return match.group(1).strip() if match else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--local", action="store_true",
                        help="check amplify.yml only; do not make a request")
    args = parser.parse_args()

    print("DEPLOYED SECURITY HEADER CHECK")

    # Always report the configured value, so a mismatch between config and live
    # is visible rather than inferred.
    configured = amplify_yml_header()
    print(f"  amplify.yml Permissions-Policy: {configured or '(not found)'}")
    config_failures = check_permissions(configured) if configured else ["not found in amplify.yml"]
    for failure in config_failures:
        print(f"    FAIL  {failure}")
    if not config_failures:
        print("    ok    camera=(), microphone=(self), geolocation=()")

    # next.config.js is inert under static export. Report it so the discrepancy
    # that caused the original bug stays visible.
    next_config = (ROOT / "next.config.js").read_text()
    next_match = re.search(r"'Permissions-Policy',\s*value:\s*'([^']+)'", next_config)
    if next_match:
        next_value = next_match.group(1)
        print(f"  next.config.js (INERT under static export): {next_value}")
        if next_value != configured:
            print("    WARN  next.config.js and amplify.yml disagree. amplify.yml wins.")

    if args.local:
        return 1 if config_failures else 0

    print(f"  requesting {args.url}")
    request = urllib.request.Request(args.url, method="GET",
                                     headers={"User-Agent": "wecare-header-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            headers = {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        # A 4xx/5xx still carries headers, so this is checkable.
        status = exc.code
        headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
    except Exception as exc:  # noqa: BLE001
        print(f"  REQUEST FAILED: {type(exc).__name__}: {exc}")
        print("  Cannot verify the deployed header. This is not a pass.")
        return 2

    print(f"  HTTP {status}")
    live = headers.get("permissions-policy", "")
    print(f"  live Permissions-Policy: {live or '(absent)'}")

    failures = check_permissions(live) if live else ["header absent from the response"]
    for failure in failures:
        print(f"    FAIL  {failure}")
    if not failures:
        print("    ok    camera=(), microphone=(self), geolocation=()")

    for name, expected in OTHER_REQUIRED.items():
        actual = headers.get(name, "")
        if actual.lower() != expected.lower():
            print(f"    FAIL  {name}={actual or '(absent)'}, expected {expected}")
            failures.append(name)
        else:
            print(f"    ok    {name}={actual}")

    if failures or config_failures:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS - deployed headers permit same-origin microphone "
          "and deny camera/geolocation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
