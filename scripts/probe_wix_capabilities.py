#!/usr/bin/env python3
"""Establish Wix site capability using ONLY the public headless client id.

Why this exists
---------------
Phase 0 discovery recorded catalog version, installed apps and Invoices
availability as ``BLOCKED`` on the grounds that they need the admin API key,
which does not exist yet (`wecare/wix/headless-api-key` holds 0 versions). That
is true for *admin* reads. It is not true for capability.

``WIX_CLIENT_ID`` is the public half of the headless OAuth client. It is designed
to ship in a browser bundle, and Wix will exchange it for an anonymous *visitor*
token with no secret involved -- exactly what a page load does. A visitor token
is enough to settle:

  * which catalog version the site runs, from Wix's own error code
  * whether Stores, Blog and eCommerce are installed
  * whether the Invoices API is available
  * whether the checkout redirect handoff is reachable
  * that the headless client and the committed site id belong to each other

so those rows do not have to stay blocked while the owner mints a credential.

Safety
------
No secret is read, sent or printed. The visitor token is held in memory and
never logged -- only its expiry is reported. Every call is a read; the one
endpoint that would create state (``redirect-session``) is probed with a
deliberately invalid payload so Wix rejects it before creating anything, which
still proves reachability and returns the list of valid session types.

    python scripts/probe_wix_capabilities.py
    python scripts/probe_wix_capabilities.py --json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
CONFIG = REPO / "src/config/wix.ts"
BASE = "https://www.wixapis.com"


def committed_ids() -> tuple[str, str]:
    """Read the public client id and site id from the committed config.

    Read from source rather than hardcoded, so the probe cannot drift away from
    what the application actually uses.
    """
    text = CONFIG.read_text()

    def const(name: str) -> str:
        m = re.search(rf"export const {name} = '([^']+)'", text)
        if not m:
            raise SystemExit(f"{name} not found in {CONFIG.relative_to(REPO)}")
        return m.group(1)

    return const("WIX_CLIENT_ID"), const("WIX_SITE_ID")


def call(url: str, token: str | None = None, body: dict | None = None,
         method: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, headers=headers,
        method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode() or "{}")
        except (ValueError, OSError):
            return exc.code, {}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"transport": type(exc).__name__}


def app_error(resp: dict) -> str:
    return ((resp.get("details") or {}).get("applicationError") or {}).get("code", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    client_id, site_id = committed_ids()
    out: dict[str, object] = {"clientId": client_id, "siteId": site_id}

    status, tok = call(f"{BASE}/oauth2/token",
                       body={"clientId": client_id, "grantType": "anonymous"})
    if status != 200 or "access_token" not in tok:
        out["headlessClient"] = {"live": False, "status": status}
        print(json.dumps(out, indent=2) if args.json else
              f"headless client NOT live (HTTP {status})", file=sys.stderr)
        return 1
    token = tok["access_token"]
    out["headlessClient"] = {"live": True, "expiresIn": tok.get("expires_in"),
                             "tokenType": tok.get("token_type")}

    # --- catalog version, decided by Wix rather than by us ---
    st_v1, r_v1 = call(f"{BASE}/stores/v1/products/query", token,
                       {"query": {"paging": {"limit": 1}}})
    st_v3, r_v3 = call(f"{BASE}/stores/v3/products/search", token,
                       {"search": {"cursorPaging": {"limit": 1}}})
    if app_error(r_v1) == "CATALOG_V3_CALLING_CATALOG_V1_API":
        version = "CATALOG_V3"
    elif st_v1 == 200 and st_v3 != 200:
        version = "CATALOG_V1"
    elif st_v3 == 200:
        version = "CATALOG_V3 (inferred: V3 responds)"
    else:
        version = f"UNDETERMINED (v1={st_v1} v3={st_v3})"
    out["catalogVersion"] = version
    out["catalogVersionEvidence"] = {
        "storesV1Status": st_v1, "storesV1Error": app_error(r_v1),
        "storesV3Status": st_v3,
    }

    # --- counts, by paging to the end rather than trusting one page ---
    def count_all(path: str, key: str, body_for) -> int | None:
        total, cursor, guard = 0, None, 0
        while guard < 60:
            guard += 1
            st, r = call(f"{BASE}{path}", token, body_for(cursor))
            if st != 200:
                return None if total == 0 else total
            items = r.get(key) or []
            total += len(items)
            cursor = ((r.get("pagingMetadata") or {}).get("cursors") or {}).get("next")
            if not cursor or not items:
                break
        return total

    out["productCount"] = count_all(
        "/stores/v3/products/search", "products",
        lambda c: {"search": {"cursorPaging":
                              {"limit": 100, **({"cursor": c} if c else {})}}})

    st, r = call(f"{BASE}/blog/v3/posts/query", token, {"paging": {"limit": 1}})
    out["blogPostTotal"] = (r.get("metaData") or {}).get("total") if st == 200 else None

    # --- installed apps and API availability ---
    probes = {
        "storesInventoryV3": ("POST", "/stores/v3/inventory-items/query",
                              {"query": {"cursorPaging": {"limit": 1}}}),
        "storesCategoriesV3": ("POST", "/categories/v1/categories/query",
                               {"query": {"cursorPaging": {"limit": 1}},
                                "treeReference": {"appNamespace": "@wix/stores"}}),
        "storesCustomizationsV3": ("POST", "/stores/v3/customizations/query",
                                   {"query": {"cursorPaging": {"limit": 1}}}),
        "storesBrandsV3": ("POST", "/stores/v3/brands/query",
                           {"query": {"cursorPaging": {"limit": 1}}}),
        "blogV3": ("GET", "/blog/v3/categories?paging.limit=1", None),
        "ecomCart": ("GET", "/ecom/v1/carts/current", None),
        "ecomOrders": ("POST", "/ecom/v1/orders/search",
                       {"search": {"cursorPaging": {"limit": 1}}}),
        "invoicesV2": ("GET", "/invoices/v2/invoices?paging.limit=1", None),
        "members": ("GET", "/members/v1/members/my", None),
        "siteProperties": ("GET", "/site-properties/v4/properties", None),
        # Deliberately invalid payload: proves reachability and returns the valid
        # session types without creating a redirect session.
        "redirectSession": ("POST", "/_api/redirects-api/v1/redirect-session",
                            {"callbacks": {}}),
    }
    results = {}
    for name, (method, path, body) in probes.items():
        st, r = call(f"{BASE}{path}", token, body, method)
        results[name] = {"status": st, "applicationError": app_error(r) or None}
    out["probes"] = results

    # An app that is NOT installed answers differently from one that is installed
    # but needs a wider scope. 403/permission-denied means present-and-scoped;
    # 404 on the collection route means unavailable.
    def verdict(name: str, present_codes=(200, 400, 403, 428)) -> str:
        st = results[name]["status"]
        if st in (200,):
            return "INSTALLED"
        if st in present_codes:
            return "INSTALLED (admin scope required)"
        if st == 404:
            return "NOT AVAILABLE"
        return f"UNKNOWN ({st})"

    out["verdicts"] = {
        "wixStores": verdict("storesInventoryV3"),
        "wixBlog": verdict("blogV3"),
        "wixEcommerce": ("INSTALLED (admin scope required)"
                         if results["ecomOrders"]["status"] == 403
                         or results["ecomCart"]["applicationError"]
                         == "OWNED_CART_NOT_FOUND"
                         else verdict("ecomCart")),
        "wixInvoices": verdict("invoicesV2"),
        "checkoutRedirect": ("REACHABLE"
                             if results["redirectSession"]["status"] in (200, 400)
                             else f"UNREACHABLE ({results['redirectSession']['status']})"),
    }

    # The site-scoped error messages name the site id, which ties the public
    # client to the committed site id without any admin call.
    st, r = call(f"{BASE}/site-properties/v4/properties", token)
    msg = json.dumps(r)
    out["clientResolvesToCommittedSite"] = site_id in msg
    out["siteIdSeenInResponse"] = site_id if site_id in msg else None

    # Which host Wix believes this site is published at.
    #
    # This is the one fact that identifies the site in human terms without the admin
    # credential. `POST /site-list/v2/sites/query` is the direct answer and needs admin
    # scope, so the site's published/draft status was recorded as BLOCKED. But every
    # product carries `url.url`, which Wix builds from the site's own primary domain -
    # so asking for one product with the URL field projection names the host.
    #
    # Does NOT establish published-vs-draft on its own. It establishes *which* site the
    # committed id refers to, which is the part that was indistinguishable from a
    # self-consistent-but-wrong id.
    st, r = call(f"{BASE}/stores/v3/products/search", token,
                 {"search": {"cursorPaging": {"limit": 1}}, "fields": ["URL"]})
    host = None
    products = r.get("products") or []
    if st == 200 and products:
        raw = (products[0].get("url") or {}).get("url", "")
        m = re.match(r"https?://([^/]+)", raw)
        host = m.group(1) if m else None
    out["wixReportedSiteHost"] = host
    out["wixReportedProductUrlSample"] = (
        (products[0].get("url") or {}).get("url") if products else None)

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    print(f"headless client {client_id}")
    print(f"  visitor token: LIVE, expires_in={out['headlessClient']['expiresIn']}s")
    print(f"  resolves to committed site id: "
          f"{'YES' if out['clientResolvesToCommittedSite'] else 'NOT CONFIRMED'}")
    print(f"  Wix reports this site at     : {out['wixReportedSiteHost'] or 'unknown'}")
    print()
    print(f"catalog version : {out['catalogVersion']}")
    print(f"  evidence      : stores/v1 -> {st_v1} {app_error(r_v1)}")
    print(f"products        : {out['productCount']}")
    print(f"blog posts      : {out['blogPostTotal']}")
    print()
    for k, v in out["verdicts"].items():
        print(f"  {k:<18} {v}")
    print()
    for name, res in results.items():
        code = f" {res['applicationError']}" if res["applicationError"] else ""
        print(f"  {res['status']:>4}  {name}{code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
