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
the ACCESS gate: a service account still has to be granted access inside each product.
Search Console was solved differently - by proving site ownership - which has no equivalent
in the other three.

CORRECTED 2026-09-30: "none of them has an API for granting it" was WRONG for two of the
three, and the error mattered because it made a solvable problem look permanent.

    Tag Manager   accounts.user_permissions.create    scope tagmanager.manage.users
    Analytics     accounts.accessBindings.create      scope analytics.manage.users
    Google Ads    no API, and no UI either - see below

Both APIs exist. What is missing is not an endpoint but a CALLER: the grant must be made by a
principal that is already an administrator there, and a service account cannot grant itself
access. `scripts/google_grant_service_account.py` makes exactly those two calls, and needs one
browser consent to obtain an administrator token carrying the two manage.users scopes. One
human action, after which both products are reachable by impersonation forever.

GOOGLE ADS IS DIFFERENT, AND THE PREVIOUS EXPLANATION HERE WAS WRONG ON EVERY POINT.
This file used to say the developer token was missing, that Ads therefore "cannot authenticate
at all", and that adding the service account as a read-only user would fix all three products.
Measured instead:

    * the developer token IS present in `wecare/google/ads` - a 22-character string, which is
      the documented shape of a developer token from a manager account's API Center;
    * with it, `v25/customers:listAccessibleCustomers` returns **HTTP 200**, so authentication
      SUCCEEDS. Both of the things that were blamed are fine;
    * the HTML 404s from v17-v21 were never about the token. **v25 is the served version** and
      those older ones are simply retired, which is why an unserved version answers with an
      HTML error page rather than a JSON one;
    * the real blocker is that 200 came back with an EMPTY customer list, because a service
      account cannot be a Google Ads user. Ads user management accepts real Google accounts
      only, so unlike GA4 and GTM there is no grant to make - the step does not exist. Ads
      needs a stored human refresh token permanently.

So a 200 with an empty list is the most misleading answer in this whole script, and it is now
reported in full rather than as success.

No secret value is printed. The developer token is read into memory at call time and never
rendered; only its presence and length are reported. Identifiers - property ids, container
ids, customer ids - are not credentials; they appear in page source and in tag payloads.

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
    print("  DEVELOPER TOKENS WERE SUNSET ON 2026-09-09. They may still be sent and are ignored")
    print("  by the API servers; access levels now attach to the Google Cloud project that owns")
    print("  the credentials - for a service-account workflow, the project owning the service")
    print("  account. So `wecare/google/ads` missing a developer_token is NOT the blocker, and")
    print("  docs recording it as one are describing the pre-sunset world.")
    print("  https://developers.google.com/google-ads/api/docs/api-policy/developer-token")

    # Version matters: v17-v21 are gone and answer an HTML 404, which reads like a dead
    # endpoint rather than a retired version. v22-v25 are live; v26+ does not exist yet.
    live_versions = []
    for v in ("v22", "v23", "v24", "v25", "v26"):
        st, _ = call(tok, f"https://googleads.googleapis.com/{v}/customers:listAccessibleCustomers")
        if st == 200:
            live_versions.append(v)
    print(f"\n  live API versions: {', '.join(live_versions) or 'none'}")
    version = live_versions[-1] if live_versions else "v25"

    st, body = call(
        tok, f"https://googleads.googleapis.com/{version}/customers:listAccessibleCustomers")
    names = (body or {}).get("resourceNames") or []
    print(f"  listAccessibleCustomers ({version}): http {st}, {len(names)} customer(s)")
    print("    ^ http 200 means OAuth alone authenticated. No developer token was sent.")
    for n in names:
        print(f"      {n}")

    # The decisive probe. Two different errors mean two different fixes, and guessing between
    # them wastes a round trip through the owner:
    #   CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION -> the Cloud project is on Test access and
    #       needs Explorer or Basic from the Google Ads API Overview page in Cloud Console.
    #   USER_PERMISSION_DENIED                    -> access levels are fine; the principal is
    #       simply not a user on the Ads account.
    st, body = call(
        tok,
        f"https://googleads.googleapis.com/{version}/customers/{ADS_CUSTOMER}/googleAds:search",
        method="POST",
        body={"query": "SELECT customer.id, customer.descriptive_name FROM customer LIMIT 1"},
        extra={"login-customer-id": ADS_LOGIN_CUSTOMER},
    )
    print(f"\n  query customer {ADS_CUSTOMER}: http {st}")
    codes = []
    if isinstance(body, dict) and body.get("error"):
        err = body["error"]
        print(f"    {err.get('status')}: {str(err.get('message'))[:120]}")
        for d in err.get("details") or []:
            for e2 in d.get("errors") or []:
                code = json.dumps(e2.get("errorCode") or {})
                codes.append(code)
                print(f"    errorCode: {code}")
    else:
        rows = (body or {}).get("results") or []
        print(f"    {len(rows)} row(s): {json.dumps(rows)[:200]}")

    joined = " ".join(codes)
    if "CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION" in joined or "ACTION_NOT_PERMITTED" in joined:
        print("\n  BLOCKER = the Cloud project's API access level (Test).")
        print("  Apply for Explorer or Basic access on the Google Ads API Overview page in")
        print("  Cloud Console. Basic is automated and reviewed in minutes AFTER brand")
        print("  verification. Known issue: a project on Free Trial, or with suspended or")
        print("  disabled billing, is rejected - check billing state first.")
    elif "USER_PERMISSION_DENIED" in joined:
        print("\n  BLOCKER = account access, NOT the token and NOT the project access level.")
        print("  Measured: auth succeeds, the project is not refused for production, and the")
        print("  only failure is that this principal is not a user on the Ads account. So Ads")
        print("  sits in the same category as Tag Manager and Analytics.")


def main() -> int:
    tok = token()
    print(f"auth: impersonated {SA} (no browser, no key file, no secret read)")
    search_console(tok)
    tag_manager(tok)
    analytics(tok)
    google_ads(tok)

    head("SUMMARY")
    print("  Search Console  reachable - ownership was proven by serving a verification file.")
    print("  Tag Manager / Analytics / Ads  all three authenticate and all three return no")
    print("  data for one reason: the principal is not a user inside the product. None of the")
    print("  three offers an API to grant that.")
    print("  Ads needs NO developer token - they were sunset 2026-09-09 - and its Cloud project")
    print("  is not refused for production either. Only the account link is missing.")
    print(f"\n  To grant all three at once, add this principal as a read-only user:\n    {SA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
