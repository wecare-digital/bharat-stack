#!/usr/bin/env python3
"""Prove that every short-link form still resolves, on both hosts.

Why this is a live probe and not a unit test
--------------------------------------------
Short-link resolution is not a property of the handler. It is the product of four
independent pieces of live configuration, and the handler is only one of them:

  1. `GET /r/{code}` and `GET /{code}` on HTTP API `zllr9lrg7j`
  2. the `r.wecare.digital` API Gateway custom domain mapped to that API
  3. the Amplify custom rule `/r/<*>` -> `https://wecare.digital/api/r/<*>`,
     which must sit BEFORE the `/<*>` -> `/index.html` SPA catch-all or it can
     never match
  4. the `live` alias of `stack-wecare-url-shortener` pointing at current code

A unit test can assert none of that. Any of the four can be removed by a console
click or a well-meaning cleanup, and three of them fail silently - the SPA
catch-all in particular answers `200` with the app shell, so a broken short link
looks like a working page rather than an error.

What must never break
---------------------
The apex path is what we mint now. The subdomain is what everything already sent
names, and it is NOT scheduled for retirement:

  wecare.digital/r/<code>    canonical since 2026-09-26
  r.wecare.digital/<code>    every link issued before that

`operations/system-cleanup` protects the link tables from factory reset on the
explicit grounds that short links are "printed on materials, embedded in messages,
and shared externally". Printed material cannot be edited and a delivered RCS card
cannot be recalled, so the old host has to answer indefinitely. This script fails
if it stops.

Usage
-----
    python scripts/check_short_link_hosts.py
    python scripts/check_short_link_hosts.py --code wa

Exit 0 means every form resolved to the same target. Non-zero names the mismatch.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request

APEX = "wecare.digital"
LEGACY_HOST = "r.wecare.digital"

# A code that must exist. `wa` is the WhatsApp entry point embedded in the SMS and
# voice auto-replies, so if any single code matters it is this one.
DEFAULT_CODE = "wa"

# A code that must NOT exist, to prove the allow-list is real and that a miss is
# handled rather than 404ing or serving the SPA shell.
ABSENT_CODE = "zz-no-such-code-probe"

FALLBACK = "https://wecare.digital/selfservice"
TIMEOUT = 20


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Capture the redirect instead of following it. Following it would test the
    destination site, which is not what is under test here."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def probe(url: str) -> tuple[int, str | None]:
    try:
        with _opener.open(url, timeout=TIMEOUT) as resp:
            return resp.status, resp.headers.get("Location")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location")
    except Exception as exc:  # noqa: BLE001
        return 0, f"error: {type(exc)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--code", default=DEFAULT_CODE,
                    help=f"short code that must resolve (default: {DEFAULT_CODE})")
    args = ap.parse_args()
    code = args.code

    # Every form that a customer could possibly be holding.
    forms = [
        (f"https://{APEX}/r/{code}", "apex path (canonical, what we mint)"),
        (f"https://{LEGACY_HOST}/{code}", "legacy subdomain (already-sent links)"),
        (f"https://{LEGACY_HOST}/r/{code}", "legacy subdomain, /r/ prefix"),
    ]

    print(f"code under test : {code}\n")
    results = []
    for url, label in forms:
        status, location = probe(url)
        results.append((url, label, status, location))
        print(f"  {status:>3}  {url}")
        print(f"       {label}")
        print(f"       -> {location}")

    targets = {loc for _, _, st, loc in results if st in (301, 302, 307, 308)}
    redirecting = [r for r in results if r[2] in (301, 302, 307, 308)]

    print("\n  absent-code handling (must fall back, not 404 or serve the app shell)")
    miss_ok = True
    for host_url in (f"https://{APEX}/r/{ABSENT_CODE}", f"https://{LEGACY_HOST}/{ABSENT_CODE}"):
        status, location = probe(host_url)
        ok = status in (301, 302) and location == FALLBACK
        miss_ok &= ok
        print(f"  {status:>3}  {host_url}\n       -> {location}  {'ok' if ok else 'UNEXPECTED'}")

    print()
    failures = []
    if len(redirecting) != len(forms):
        broken = [u for u, _, st, _ in results if st not in (301, 302, 307, 308)]
        failures.append("these forms did not redirect: " + ", ".join(broken))
    if len(targets) > 1:
        failures.append(f"forms disagree on the target: {sorted(targets)}")
    if not miss_ok:
        failures.append("an unknown code did not fall back to " + FALLBACK)

    if failures:
        for f in failures:
            print(f"  FAIL  {f}")
        print("\nSHORT LINK HOSTS FAILED - a form that customers may be holding is "
              "broken. Do not 'fix' this by retiring the old host; it is the links "
              "already sent that cannot be changed.")
        return 1

    print(f"  all {len(forms)} forms redirect to the same target: {targets.pop()}")
    print("\nSHORT LINK HOSTS PASSED - apex path and legacy subdomain both resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
