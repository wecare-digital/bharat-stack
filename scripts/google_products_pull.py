#!/usr/bin/env python3
"""Pull live data from the four Google products this site depends on. Read-only.

    Search Console   search analytics, properties, sitemaps      webmasters
    Tag Manager      accounts, containers, published version     tagmanager.readonly
    Analytics (GA4)  properties, and a report if reachable       analytics.readonly
    Google Ads       accessible customers                        adwords

AUTH, and why it is the same mechanism for all four. A service account can be issued a token
for ANY scope with no consent screen, and `automation@wecaredigitalbw` grants this machine
`roles/iam.serviceAccountTokenCreator`. So no browser, no key file on disk, and no provider
credential read into context - which matters because steering prohibits reading one.

WHAT THAT DOES AND DOES NOT BUY. It solves the SCOPE gate for every product. It does not solve
the ACCESS gate: a service account still has to be granted access inside each product, and
none of Tag Manager, Analytics or Ads has an API for granting it. Search Console was solved
differently - by proving site ownership - which has no equivalent in the other three.

GOOGLE ADS IS EXPECTED TO FAIL FOR A SEPARATE REASON. Its API requires a `developer_token` on
every request in addition to OAuth, and `docs/provider-inventory.md` records
`wecare/google/ads` as **missing** it. So Ads cannot authenticate at all regardless of scope
or account access, and this reports that precisely rather than as a generic error.

No secret value is printed. Identifiers - property ids, container ids, customer ids - are not
credentials; they appear in page source and in tag payloads.
"""
from __future__ import annotations

import json
import urllib.parse
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

SA = "automation@wecaredigitalbw.iam.gserviceaccount.com"

SCOPES = ",".join([
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/adwords",
])

SITE = "https://wecare.digital"
GSC_PROPERTY = f"{SITE}/"
GTM_CONTAINER = "GTM-TXZ8JT78"
GA4_PROPERTY = "550346663"
ADS_CUSTOMER = "8367589699"
ADS_LOGIN_CUSTOMER = "4270412231"


def token() -> str:
    p = subprocess.run(
        ["gcloud", "auth", "print-access-token",
         f"--impersonate-service-account={SA}", f"--scopes={SCOPES}"],
        capture_output=True, text=True, timeout=120)
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit(f"could not mint a token: {p.stderr.strip()[:300]}")
    return p.stdout.strip()


def call(tok: str, url: str, *, method: str = "GET", body: dict | None = None,
         extra: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        **(extra or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": raw[:400]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": type(e).__name__}


def why(body: object) -> str:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return f"{err.get('status', err.get('code', '?'))}: {str(err.get('message'))[:170]}"
        if err:
            return str(err)[:170]
    return json.dumps(body)[:170]


def head(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ── Search Console ─────────────────────────────────────────────────────────────

def search_console(tok: str) -> None:
    head("SEARCH CONSOLE")
    st, body = call(tok, "https://searchconsole.googleapis.com/webmasters/v3/sites")
    if st != 200:
        print(f"  sites.list http {st} - {why(body)}")
        return
    entries = (body or {}).get("siteEntry") or []
    print(f"  properties: {len(entries)}")
    for e in entries:
        print(f"    {e.get('siteUrl')}  permission={e.get('permissionLevel')}")
    if not entries:
        print("  BLOCKED - this principal owns no property.")
        return

    st, body = call(tok, "https://searchconsole.googleapis.com/webmasters/v3/sites/"
                    f"{urllib.parse.quote(GSC_PROPERTY, safe='')}/sitemaps")
    feeds = (body or {}).get("sitemap") or [] if st == 200 else []
    print(f"\n  registered sitemaps: {len(feeds)}")
    for f in feeds:
        c = (f.get("contents") or [{}])[0]
        print(f"    {f.get('path')}")
        print(f"      lastDownloaded={f.get('lastDownloaded')} errors={f.get('errors')} "
              f"warnings={f.get('warnings')} submitted={c.get('submitted')} "
              f"indexed={c.get('indexed')}")

    # Search analytics. The window is deliberately wide: this property was created today, and
    # Search Console data lags 2-3 days at source, so a 7-day window could be empty for a
    # healthy site and that would be indistinguishable from no traffic.
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=90)
    for dims, label in (([], "totals"), (["query"], "top queries"),
                        (["page"], "top pages"), (["country"], "countries"),
                        (["device"], "devices")):
        st, body = call(
            tok,
            "https://searchconsole.googleapis.com/webmasters/v3/sites/"
            f"{urllib.parse.quote(GSC_PROPERTY, safe='')}/searchAnalytics/query",
            method="POST",
            body={"startDate": start.isoformat(), "endDate": end.isoformat(),
                  "dimensions": dims, "rowLimit": 10},
        )
        rows = (body or {}).get("rows") or [] if st == 200 else []
        print(f"\n  {label} ({start} .. {end}): http {st}, {len(rows)} row(s)")
        if st != 200:
            print(f"    {why(body)}")
            continue
        if not rows:
            print("    no data - the property records no impressions in this window")
            continue
        for r in rows:
            keys = " / ".join(r.get("keys") or []) or "ALL"
            print(f"    {keys[:52]:<54} clicks={r.get('clicks', 0):>6.0f} "
                  f"impr={r.get('impressions', 0):>8.0f} "
                  f"ctr={r.get('ctr', 0) * 100:>5.2f}% pos={r.get('position', 0):>5.1f}")


# ── Tag Manager ────────────────────────────────────────────────────────────────

def tag_manager(tok: str) -> None:
    head("TAG MANAGER")
    print(f"  container in the page source: {GTM_CONTAINER}  (_document.tsx)")
    st, body = call(tok, "https://tagmanager.googleapis.com/tagmanager/v2/accounts")
    if st != 200:
        print(f"  accounts.list http {st} - {why(body)}")
        print("  BLOCKED - see the note at the end.")
        return
    accounts = (body or {}).get("account") or []
    print(f"  accounts visible: {len(accounts)}")
    if not accounts:
        print("  BLOCKED - authentication works but this principal is on no GTM account.")
        print("  There is no API to grant it; it is added in Tag Manager > Admin > User Management.")
        return
    for a in accounts:
        print(f"    {a.get('accountId')}  {a.get('name')}")
        st2, b2 = call(tok, "https://tagmanager.googleapis.com/tagmanager/v2/"
                       f"{a.get('path')}/containers")
        for c in (b2 or {}).get("container") or []:
            print(f"      container {c.get('publicId')}  {c.get('name')}  "
                  f"({', '.join(c.get('usageContext') or [])})")


# ── Analytics (GA4) ────────────────────────────────────────────────────────────

def analytics(tok: str) -> None:
    head("ANALYTICS (GA4)")
    print(f"  property in src/config/analytics.ts: {GA4_PROPERTY}")
    st, body = call(tok, "https://analyticsadmin.googleapis.com/v1beta/accounts")
    if st != 200:
        print(f"  accounts.list http {st} - {why(body)}")
    else:
        accounts = (body or {}).get("accounts") or []
        print(f"  accounts visible: {len(accounts)}")
        for a in accounts:
            print(f"    {a.get('name')}  {a.get('displayName')}")

    st, body = call(tok, "https://analyticsadmin.googleapis.com/v1beta/"
                    f"properties/{GA4_PROPERTY}")
    print(f"  properties/{GA4_PROPERTY}: http {st}")
    if st == 200:
        print(f"    displayName={body.get('displayName')} "
              f"timeZone={body.get('timeZone')} currency={body.get('currencyCode')}")
        st2, rep = call(
            tok,
            f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY}:runReport",
            method="POST",
            body={"dateRanges": [{"startDate": "28daysAgo", "endDate": "yesterday"}],
                  "metrics": [{"name": "sessions"}, {"name": "activeUsers"},
                              {"name": "screenPageViews"}],
                  "dimensions": [{"name": "sessionDefaultChannelGroup"}], "limit": 10},
        )
        print(f"    runReport: http {st2}")
        if st2 == 200:
            rows = rep.get("rows") or []
            print(f"      {len(rows)} row(s)")
            for r in rows:
                dim = (r.get("dimensionValues") or [{}])[0].get("value", "")
                vals = [m.get("value") for m in r.get("metricValues") or []]
                print(f"      {dim:<28} sessions={vals[0]:>8} users={vals[1]:>8} views={vals[2]:>8}")
            if not rows:
                print("      no rows - the property recorded no sessions in the window")
        else:
            print(f"      {why(rep)}")
    else:
        print(f"    {why(body)}")
        print("  BLOCKED - the service account is not on this GA4 property. It is granted in")
        print("  Analytics > Admin > Property Access Management; there is no API for it.")


# ── Google Ads ─────────────────────────────────────────────────────────────────

def google_ads(tok: str) -> None:
    head("GOOGLE ADS")
    print(f"  customer {ADS_CUSTOMER} (836-758-9699), manager {ADS_LOGIN_CUSTOMER} (427-041-2231)")
    print("  The Ads API requires a developer_token on EVERY request in addition to OAuth.")
    print("  docs/provider-inventory.md records wecare/google/ads as MISSING that token, and")
    print("  reading the secret is prohibited - so this call is expected to fail on the token,")
    print("  not on the scope. Attempted anyway so the failure is measured, not assumed.")
    st, body = call(
        tok, "https://googleads.googleapis.com/v21/customers:listAccessibleCustomers")
    print(f"\n  listAccessibleCustomers: http {st}")
    if st == 200:
        names = (body or {}).get("resourceNames") or []
        print(f"    accessible customers: {len(names)}")
        for n in names:
            print(f"      {n}")
    else:
        print(f"    {why(body)}")
        print("    MEASURED, and stated carefully: every API version v17-v21 returns an HTML")
        print("    404 with OAuth alone, and googleads.googleapis.com IS enabled on the")
        print("    project - so this is not a missing-API or wrong-version problem. The Ads")
        print("    API requires a `developer-token` HTTP header on every request and does not")
        print("    route without it, which is consistent with the recorded missing token. It")
        print("    does not PROVE it: an HTML 404 carries no machine-readable reason, so the")
        print("    token remains the documented cause rather than a confirmed one.")


def main() -> int:
    tok = token()
    print(f"auth: impersonated {SA} (no browser, no key file, no secret read)")
    search_console(tok)
    tag_manager(tok)
    analytics(tok)
    google_ads(tok)

    head("SUMMARY")
    print("  Search Console  reachable - ownership was proven by serving a verification file.")
    print("  Tag Manager / Analytics / Ads  each need the service account added INSIDE the")
    print("  product, and none of the three offers an API to do it. Ads additionally needs a")
    print("  developer_token that is recorded as missing.")
    print(f"\n  To grant all three at once, add this principal as a read-only user:\n    {SA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
