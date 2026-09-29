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
Corrected 2026-09-25. This defaulted to `https://app.wecare.digital/`, which was a
**different distribution**: CloudFront `ERCXSFDL0VM8X` in front of the S3 bucket
`app.wecare.digital`, serving media. Amplify's `customHeaders` are applied by
Amplify Hosting and never reached it, so the script reported

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

THE ASSETS GAP IS CLOSED, and the target moved (2026-09-29)
-----------------------------------------------------------
Two things changed underneath this script and both had left it reporting noise.

1. `ASSETS_URL` still pointed at the retired `app.wecare.digital` host (written bare
   here on purpose - `check_retired_origins.py` escalates a scheme-qualified retired
   host near the word "origin" to a violation, and it is right to: prose cannot be
   distinguished from an allow-list entry by inspection). That host and its
   distribution are **gone**: `get-distribution ERCXSFDL0VM8X` returns
   NoSuchDistribution, no distribution carries the alias, the name resolves to no
   address, and `head-bucket app.wecare.digital` is 404. So the "report" printed
   only `request failed` - the exact learned-noise failure the section above warns
   about, reintroduced by a dead constant.

2. The premise was obsolete. Media is now served from the **apex** as
   `wecare.digital/get/<key>` through CloudFront `E2GP22R4BIFGQ3`, so it is behind
   the same host whose headers this script gates. Measured 2026-09-29 against
   `/get/o/stream/media/m/wecare-digital.png`:

       HTTP/2 200, content-type image/png
       referrer-policy: strict-origin-when-cross-origin
       permissions-policy: camera=(), microphone=(self), geolocation=()
       strict-transport-security: max-age=31536000
       x-content-type-options: nosniff

   All four are present. The "public distribution serving content with no security
   headers at all" gap that justified reporting it closed when the media moved.

`ASSETS_URL` now points at that media path. It stays **reported and never gated**,
because a media 404 or an S3-side change should not fail a headers check - but it
now reports a live surface rather than a dead name.

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

# Reported, never gated. The media edge: CloudFront E2GP22R4BIFGQ3 over the S3 bucket
# `wecare-digital-get`, reached on the apex as /get/<key>. A concrete object rather than
# `/get/`, because a prefix has no object to serve and would report a 403/404 that says
# nothing about headers. See "THE ASSETS GAP IS CLOSED" above before changing this.
ASSETS_URL = "https://wecare.digital/get/o/stream/media/m/wecare-digital.png"

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
    """Print the media edge's posture. Never affects the exit code.

    Originally included because the media distribution served content with no
    security headers at all and no response-headers policy - a real gap that would
    have stayed unnoticed if unreported. That gap is closed: media moved onto the
    apex host, and all four headers were measured present on 2026-09-29.

    Kept as a report rather than promoted to a gate, because a media 404 or an
    S3-side change is not a headers regression and should not fail this script.
    """
    print(f"\n  MEDIA EDGE (reported, never gated): {url}")
    print("    CloudFront E2GP22R4BIFGQ3 over s3://wecare-digital-get, served on the "
          "apex as /get/<key>.")
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
