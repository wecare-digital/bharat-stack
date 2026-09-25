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

WHICH HOST, AND WHY IT IS NOT `app.`
------------------------------------
Corrected 2026-09-25. This defaulted to `https://app.wecare.digital/`, which is a
**different distribution**: CloudFront `ERCXSFDL0VM8X` in front of the S3 bucket
`app.wecare.digital`, serving media. Amplify's `customHeaders` are applied by
Amplify Hosting and never reach it, so the script reported

    live Permissions-Policy: (absent)
    FAIL x-content-type-options=(absent)
    FAIL referrer-policy=(absent)
    RESULT: FAIL

against a host that was never meant to carry them - while `wecare.digital`, the
Amplify-hosted app, served all three correctly. A check that fails for a reason
unrelated to the thing it guards is worse than no check, because its red gets
learned as noise and then the real regression is invisible.

The Amplify app is served from the **apex**. That is also the origin the Plivo
softphone runs on, so it is the origin whose `microphone=(self)` actually matters.

The assets distribution is still *reported* - it genuinely has no security headers
and no CloudFront response-headers policy - but it cannot be a gate here, because
fixing it means attaching a policy to that distribution, not editing `amplify.yml`.

Usage
-----
    python scripts/verify_deployed_headers.py
    python scripts/verify_deployed_headers.py --url https://wecare.digital
    python scripts/verify_deployed_headers.py --no-assets  # skip the report
    python scripts/verify_deployed_headers.py --local      # parse amplify.yml only

Exit codes
    0  every required header matches on the Amplify origin
    1  a header is missing or wrong on the Amplify origin
    2  the request failed (network, DNS, TLS) - NOT a header failure

The assets-distribution report never changes the exit code.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# The Amplify-hosted app, which is what `amplify.yml` customHeaders apply to.
# NOT app.wecare.digital - see "WHICH HOST" above before changing this.
DEFAULT_URL = "https://wecare.digital/"

# Reported, never gated. A separate CloudFront distribution (ERCXSFDL0VM8X) over the
# S3 bucket `app.wecare.digital`; Amplify customHeaders cannot reach it.
ASSETS_URL = "https://app.wecare.digital/"

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


def fetch_headers(url: str) -> tuple[int, dict]:
    """(status, lowercased headers). Raises on a transport failure.

    A 4xx/5xx still carries response headers, so it is checkable and is not
    treated as a transport failure.
    """
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "wecare-header-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}


def report_assets_distribution(url: str) -> None:
    """Print the assets distribution's posture. Never affects the exit code.

    Included because silently ignoring it is how it stayed unnoticed: it is a
    public distribution serving `text/html` and `image/svg+xml` with no security
    headers at all and no CloudFront response-headers policy attached. That is a
    real gap, but it is a CloudFront change rather than an `amplify.yml` one, so
    gating this script on it would block a deploy on an unrelated fix.
    """
    print(f"\n  ASSETS DISTRIBUTION (reported, never gated): {url}")
    print("    Amplify customHeaders do not apply here - separate CloudFront "
          "distribution ERCXSFDL0VM8X over S3.")
    try:
        status, headers = fetch_headers(url)
    except Exception as exc:  # noqa: BLE001
        print(f"    request failed: {type(exc).__name__} - not a gate, continuing")
        return

    present = [h for h in ("permissions-policy", "x-content-type-options",
                           "referrer-policy", "x-frame-options",
                           "strict-transport-security", "content-security-policy")
               if headers.get(h)]
    print(f"    HTTP {status}, content-type {headers.get('content-type', '(none)')}")
    if present:
        for h in present:
            print(f"    present  {h}={headers[h]}")
    else:
        print("    none of Permissions-Policy, X-Content-Type-Options, Referrer-Policy,")
        print("    X-Frame-Options, HSTS or CSP is present.")
        print("    Worth noting rather than alarming: this origin serves image/svg+xml")
        print("    (the BIMI logo), and SVG can carry script, so a document opened here")
        print("    executes in this origin. It is a distinct origin from wecare.digital,")
        print("    which limits the blast radius. Fix is a CloudFront response-headers")
        print("    policy on ERCXSFDL0VM8X - tracked separately, not by this script.")


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
    parser.add_argument("--url", default=DEFAULT_URL,
                        help=f"origin to gate on (default: {DEFAULT_URL})")
    parser.add_argument("--assets-url", default=ASSETS_URL,
                        help="assets distribution to report on, never gated")
    parser.add_argument("--no-assets", action="store_true",
                        help="skip the assets-distribution report")
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

    print(f"  requesting {args.url}  (the Amplify-hosted app)")
    try:
        status, headers = fetch_headers(args.url)
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

    if not args.no_assets:
        report_assets_distribution(args.assets_url)

    if failures or config_failures:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS - deployed headers on the Amplify origin permit "
          "same-origin microphone and deny camera/geolocation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
