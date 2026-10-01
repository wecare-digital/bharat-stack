#!/usr/bin/env python3
"""Probe the URL/host matrix and fail on any row that does not match its expectation.

WHAT THIS IS FOR. `scripts/retired_url_probe.py` answers one question - "did a retired URL
start answering 200 again" - and answers it well. This answers a different one: does the
WHOLE host-and-path surface still behave the way it was measured to behave, including the
rows that are supposed to be boring. Hosts, the 404 fallback, the provider passthroughs, the
staff entry, and the aliases the owner retired, all in one pass with one exit code.

ONLY THE LAST STATUS IN A CHAIN MEANS ANYTHING, and that is the lesson this file is built
around rather than a detail of it. `next.config.js` sets `trailingSlash: true`, so an
extensionless path ALWAYS 301s to add the slash before any page lookup happens. A probe that
records the first status reads `/admin` as "301, fine" when the chain actually terminates on
a 404 - and reads it as "301, fine" equally when the chain terminates on a staff login at
200, which is the exact defect this matrix was built to catch. So every row follows the chain
to a terminal response and judges THAT, while still recording the hops so a new hop is
visible.

LOOPS ARE CHECKED, NOT ASSUMED. A redirect whose target redirects back is the one failure a
status-code assertion cannot see: both codes look correct in isolation. Every chain is walked
with a seen-set and a hop budget, and a repeat is a hard failure.

READ-ONLY. HTTP GET and POST against the public site, nothing else. No AWS call, no secret
read, no write of any kind. The POST rows exist because the provider webhooks are delivered
by POST and a rewrite can behave differently per method - `GET /mcp` is 405 while
`POST /mcp` is 400, which is only visible if both are probed.

MEASURED STATE THIS ENCODES (2026-10-01). The live Amplify rule array went from 146 rules to
8 when the owner instructed "delete all url redirects now"
(docs/execution/url-redirect-removal-20261001.md), then to 9 when the host-canonicalisation
301 was restored (docs/execution/url-host-matrix-20261001.md). So the ~150 legacy aliases
that used to 301 now terminate at 404 on the `/<*>` -> `/404.html` catch-all, and that 404 is
the EXPECTED value here, not a regression. The 15 former top-level workspace prefixes are the
rows that matter most: every one of them used to end on the staff Authenticator shell at
HTTP 200, and this file fails if any of them ever does again.

Usage:
    .venv/bin/python scripts/probe_url_host_matrix.py            # human table
    .venv/bin/python scripts/probe_url_host_matrix.py --json     # machine readable
    .venv/bin/python scripts/probe_url_host_matrix.py --only api # filter rows by group
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://wecare.digital"
WWW = "https://www.wecare.digital"
UA = "wecare-url-host-matrix-probe/1"
MAX_HOPS = 5

# The 15 top-level prefixes that used to redirect into the staff tree. Until 2026-10-01 every
# one of these terminated on the Authenticator shell at 200 - /contacts sits right next to the
# genuine public /contact/, so a mistyped customer path handed back a staff login. /settings
# was worse for staff: it 301d to a /workspace/settings/ page that 404s.
LEGACY_WORKSPACE_PREFIXES = (
    "/dm", "/engage", "/dashboard", "/contacts", "/commerce", "/pay", "/forms",
    "/service", "/docs", "/seo", "/admin", "/access", "/link", "/task", "/settings",
)

# The legacy content/SEO aliases. Owner-retired 2026-10-01; 404 is the intended answer and a
# 301 reappearing here would mean the removal was reverted.
RETIRED_CONTENT = (
    "/swdhya/", "/no-fault/", "/legal-stuff/", "/legal-stuffs/", "/faq/", "/my-order/",
    "/expoweek/", "/ritual-store/", "/swdhya-store/", "/request-tracking/", "/rx-slot/",
    "/bring-friends/", "/home/", "/open-possibility/", "/product-page/partner/",
    "/selfservice/", "/track/",
)

PUBLIC_PAGES = (
    "/", "/shop/", "/cart/", "/orders/", "/blog/", "/contact/", "/checkout/status/",
    "/grahak-os/", "/vayulok/", "/terms/", "/anew/", "/clear-closure/",
)


def _row(group: str, url: str, expect: int, why: str, *, method: str = "GET",
         terminal_url: str | None = None, body_contains: tuple[str, ...] = ()) -> dict:
    return {
        "group": group, "method": method, "url": url, "expect_status": expect,
        "expect_terminal_url": terminal_url, "expect_body_contains": body_contains,
        "why": why,
    }


def matrix() -> list[dict]:
    rows: list[dict] = []

    # ── hosts ────────────────────────────────────────────────────────────────────────
    rows.append(_row("host", f"{SITE}/", 200, "the canonical home"))
    rows.append(_row("host", f"{WWW}/", 200, "www must canonicalise to the apex",
                     terminal_url=f"{SITE}/"))
    # The row the whole host rule exists for. Restored 2026-10-01 after the redirect removal
    # left www serving the entire site at 200 under a second hostname - duplicate content, not
    # a redirect cleanup. The source is a bare origin, which is what preserves the path; a
    # source with a path would collapse every www URL onto the apex home page.
    rows.append(_row("host", f"{WWW}/shop/", 200, "www must preserve the PATH, not land on home",
                     terminal_url=f"{SITE}/shop/"))
    rows.append(_row("host", f"{WWW}/blog/", 200, "path preservation, second sample",
                     terminal_url=f"{SITE}/blog/"))
    rows.append(_row("host", f"http://{SITE.split('://')[1]}/", 200,
                     "http apex reaches https apex", terminal_url=f"{SITE}/"))

    # ── the 404 fallback ─────────────────────────────────────────────────────────────
    # 404 is load-bearing and must never become 200: a non-404 status on /<*> matches
    # unconditionally and would shadow all ~123 exported pages with one rule.
    rows.append(_row("fallback", f"{SITE}/definitely-not-a-page", 404,
                     "trailing-slash 301 then a real 404, judged on the terminal hop"))
    rows.append(_row("fallback", f"{SITE}/definitely-not-a-page/", 404,
                     "must serve 404.html with noindex and the apex canonical",
                     body_contains=('"page":"/404"', 'name="robots"', 'noindex')))
    rows.append(_row("fallback", f"{SITE}/404/", 200, "the exported page itself"))

    # ── the 15 legacy workspace prefixes ────────────────────────────────────────────
    for prefix in LEGACY_WORKSPACE_PREFIXES:
        rows.append(_row("legacy-workspace", f"{SITE}{prefix}/", 404,
                         "must NOT reach the staff Authenticator shell"))
        rows.append(_row("legacy-workspace", f"{SITE}{prefix}", 404,
                         "bare form: 301 to add the slash, then 404"))
    rows.append(_row("legacy-workspace", f"{SITE}/dm/calls", 404,
                     "the one-hop channel alias is gone with its prefix"))
    rows.append(_row("legacy-workspace", f"{SITE}/admin/anything/deep", 404,
                     "a deep path under a retired prefix"))

    # ── retired content aliases ─────────────────────────────────────────────────────
    for path in RETIRED_CONTENT:
        rows.append(_row("retired-content", f"{SITE}{path}", 404,
                         "owner-retired 2026-10-01; a 301 here means the removal reverted"))

    # ── the staff entry, untouched ──────────────────────────────────────────────────
    # Not hidden and not opened. This task does not touch authorization, and a 200 here is
    # the Authenticator shell doing its job - it is only a defect when a CUSTOMER path
    # resolves to it, which the legacy-workspace rows above are what guard.
    rows.append(_row("staff", f"{SITE}/workspace/", 200, "the real staff entry, unchanged"))
    rows.append(_row("staff", f"{SITE}/workspace/access/", 200, "staff sign-in, unchanged"))

    # ── customer auth and public pages ──────────────────────────────────────────────
    rows.append(_row("public", f"{SITE}/account/sign-in/", 200, "the CUSTOMER auth flow"))
    for path in PUBLIC_PAGES:
        rows.append(_row("public", f"{SITE}{path}", 200, "a live public page"))

    # ── passthrough rewrites: the payment-critical rows ─────────────────────────────
    # These statuses ARE the contract. 401 is a signature rejection travelling back from the
    # Lambda - a meaningful answer. If one of these ever returns a PAGE status (200 HTML, or a
    # 302 to a page) the rewrite has been shadowed by a redirect and provider delivery is
    # broken, which is why they are probed by their real method.
    rows.append(_row("api", f"{SITE}/api/razorpay-webhook", 401,
                     "payment webhook: signature rejection, not a page", method="POST"))
    rows.append(_row("api", f"{SITE}/api/auth/validate", 401, "auth route reachable",
                     method="POST"))
    rows.append(_row("api", f"{SITE}/api/payments/webhook", 404, "no such route, from the API",
                     method="POST"))
    rows.append(_row("api", f"{SITE}/api/wa-business/webhooks", 401,
                     "WhatsApp webhook delivery address", method="POST"))
    rows.append(_row("api", f"{SITE}/api/webhook/sinch-rcs", 200, "RCS webhook verification GET"))
    rows.append(_row("api", f"{SITE}/mcp", 405, "MCP rejects GET"))
    rows.append(_row("api", f"{SITE}/mcp", 400, "MCP accepts POST and rejects an empty body",
                     method="POST"))
    rows.append(_row("api", f"{SITE}/get/o/stream/media/m/wecare-digital.png", 200,
                     "media CDN passthrough"))
    # A short-link miss answers with a 302 to /contact/ from inside the Lambda. Terminal is
    # therefore /contact/ at 200, one hop, no loop.
    rows.append(_row("api", f"{SITE}/r/zzznotacode", 200, "short-link miss lands on /contact/",
                     terminal_url=f"{SITE}/contact/"))
    # KNOWN FINDING, owned by the amplify/functions workstream, NOT a regression of this task:
    # the HTTP API's single-segment catch-all GET /{code} answers an unknown API path with a
    # 302 to /contact/ rather than JSON. Recorded so it is visible, asserted at its measured
    # value so a change to it is also visible.
    rows.append(_row("api-finding", f"{SITE}/api/definitely-no-route", 200,
                     "unknown single-segment API path -> /contact/ (another workstream owns it)",
                     terminal_url=f"{SITE}/contact/"))

    # ── subdomains: documented gaps, asserted so they cannot change silently ────────
    # 0 means no TCP connection at all: the name has no address in Route 53 and CloudFront
    # refuses the TLS handshake for an unregistered host (alert 40). Closing this needs an
    # Amplify update-domain-association AND a Route 53 wildcard - outside this task's
    # authority, recorded as an owner-decision item in the matrix document.
    rows.append(_row("subdomain", "https://shop.wecare.digital/", 0,
                     "no address; documented coverage gap, NOT fixed here"))
    rows.append(_row("subdomain", "https://xout.wecare.digital/", 404,
                     "legacy Wix host, second-label, out of scope"))
    # mta-sts is the MTA-STS policy endpoint under mode: enforce. Probed at / ONLY, read-only,
    # to confirm nothing about it moved. Its policy path is not touched by this or any probe.
    rows.append(_row("subdomain", "https://mta-sts.wecare.digital/", 403,
                     "email auth is fail-closed - this must not change"))

    return rows


def _open(url: str, method: str):
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):  # noqa: ANN002, ANN003
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    data = b"" if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": UA})
    return opener.open(req, timeout=30)


def _one_hop(url: str, method: str) -> tuple[int, str, str]:
    """Return (status, location, body-prefix) without following the redirect."""
    try:
        with _open(url, method) as response:
            body = ""
            if response.status == 200:
                body = response.read(65536).decode("utf-8", "replace")
            return response.status, response.headers.get("Location", "") or "", body
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(65536).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - a bodyless error response is normal
            pass
        location = exc.headers.get("Location", "") if exc.headers else ""
        return exc.code, location or "", body
    except Exception as exc:  # noqa: BLE001 - DNS/TLS failure is a measurable outcome
        return 0, "", type(exc).__name__


def follow(row: dict) -> dict:
    """Walk the chain to a terminal response. A repeated URL is a loop and a hard failure."""
    url, method = row["url"], row["method"]
    hops: list[dict] = []
    seen: list[str] = []
    loop = False

    while True:
        if url in seen:
            loop = True
            break
        seen.append(url)
        status, location, body = _one_hop(url, method)
        hops.append({"url": url, "status": status, "location": location})
        if status in (301, 302, 303, 307, 308) and location:
            url = urllib.parse.urljoin(url, location)
            # A 303, or a 301/302 on a POST, is followed as GET by every real client.
            if status == 303 or (status in (301, 302) and method == "POST"):
                method = "GET"
            if len(hops) >= MAX_HOPS:
                break
            continue
        break

    terminal = hops[-1]
    failures: list[str] = []
    if loop:
        failures.append(f"REDIRECT LOOP: {' -> '.join(seen)}")
    if len(hops) >= MAX_HOPS and terminal["status"] in (301, 302, 307, 308):
        failures.append(f"chain did not terminate within {MAX_HOPS} hops")
    if terminal["status"] != row["expect_status"]:
        failures.append(f"terminal status {terminal['status']}, expected {row['expect_status']}")
    if row["expect_terminal_url"] and terminal["url"] != row["expect_terminal_url"]:
        failures.append(f"terminal url {terminal['url']}, expected {row['expect_terminal_url']}")
    for needle in row["expect_body_contains"]:
        if needle not in body:
            failures.append(f"body missing {needle!r}")

    return {
        "group": row["group"], "method": row["method"], "url": row["url"],
        "expect_status": row["expect_status"], "status": terminal["status"],
        "terminal_url": terminal["url"], "hops": hops, "hop_count": len(hops),
        "why": row["why"], "ok": not failures, "failures": failures,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Probe the URL/host matrix.")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--only", help="probe one group only (host, fallback, legacy-workspace, "
                                       "retired-content, staff, public, api, api-finding, subdomain)")
    args = parser.parse_args(argv)

    rows = matrix()
    if args.only:
        rows = [r for r in rows if r["group"] == args.only]
        if not rows:
            print(f"no rows in group {args.only!r}", file=sys.stderr)
            return 2

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(follow, rows))

    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({
            "probed": len(results), "failed": len(failed),
            "results": results,
        }, indent=2))
    else:
        width = max(len(r["url"]) for r in results)
        current = None
        for result in results:
            if result["group"] != current:
                current = result["group"]
                print(f"\n── {current} ──")
            mark = "ok  " if result["ok"] else "FAIL"
            chain = " -> ".join(str(h["status"]) for h in result["hops"])
            print(f"  {mark} {result['method']:<4} {result['url']:<{width}} "
                  f"[{chain}] expect {result['expect_status']}")
            for failure in result["failures"]:
                print(f"       !! {failure}")
        print(f"\nprobed {len(results)} row(s); {len(failed)} failed")

    for result in failed:
        print(f"FAIL {result['method']} {result['url']}: {'; '.join(result['failures'])} "
              f"({result['why']})", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
