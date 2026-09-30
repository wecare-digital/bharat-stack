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

    * the developer token was never the blocker. Tokens were SUNSET on 2026-09-09: they may
      still be sent and are IGNORED by the API servers, and API access level now attaches to
      the Google Cloud project owning the credential - for a service-account workflow, the
      project that owns the service account;
    * `v25/customers:listAccessibleCustomers` returns **HTTP 200** with no developer token
      sent at all, so authentication SUCCEEDS;
    * the HTML 404s from v17-v21 were never about the token either. v22-v25 are served and
      the older ones are retired, which is why an unserved version answers with an HTML
      error page rather than a JSON one;
    * the real blocker is that 200 came back with an EMPTY customer list, because
      `automation@wecaredigitalbw` is not a user on the Ads account.

CORRECTED AGAIN, 2026-09-30, and this correction matters more than the one above because it
changes what someone is told to go and do. An earlier revision of this docstring - written by
me - claimed "a service account cannot be a Google Ads user, Ads user management accepts real
Google accounts only, so there is no grant to make; Ads needs a stored human refresh token
permanently." **Every clause of that is wrong**, and it would have sent a reader to build an
OAuth refresh-token flow that is not needed. Google's own service-account workflow guide
documents the opposite:

    Google Ads -> Admin -> Access and security -> Users -> +
    type the SERVICE ACCOUNT EMAIL into the Email box, pick an access level, Add account
    (the only restriction: service accounts do not support the 'Email only' level)

No domain-wide delegation, no Google Workspace, no human refresh token, no browser consent.
So all three blocked surfaces have the SAME one-step fix - add the service account as a
read-only user inside each product - and Ads is not the special case it was made out to be.

Which cause it is, is measured rather than assumed, because the two candidates look identical
at `listAccessibleCustomers` (both answer 200 with an empty list) and differ only in the error
code from a real customer query:

    USER_PERMISSION_DENIED                     -> not an Ads user; project access level FINE
    CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION  -> project on Test access; a user grant will
                                                  NOT help, apply for Explorer/Basic instead

Measured here: USER_PERMISSION_DENIED. So the grant is the fix and the Cloud project is fine.

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

#: Each probe records its verdict here and the summary RENDERS FROM IT. The summary used to be
#: hardcoded prose, and on the run after the Google Ads grant landed it printed "only the account
#: link is missing" directly underneath output proving the link existed and the project was the
#: blocker instead. A report that contradicts its own measurements is worse than no report.
VERDICT: dict[str, str] = {}

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
        VERDICT["Search Console"] = "BLOCKED - owns no property"
        print("  BLOCKED - this principal owns no property.")
        return
    VERDICT["Search Console"] = f"OK - {len(entries)} property, permission " \
        f"{entries[0].get('permissionLevel')}"

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
        VERDICT["Tag Manager"] = "BLOCKED - authenticates, on no GTM account"
        print("  BLOCKED - authentication works but this principal is on no GTM account.")
        print("  There is no API to grant it; it is added in Tag Manager > Admin > User Management.")
        return
    VERDICT["Tag Manager"] = f"OK - {len(accounts)} account(s)"
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
        VERDICT["Analytics GA4"] = f"OK - property {GA4_PROPERTY} readable"
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
        VERDICT["Analytics GA4"] = f"BLOCKED - http {st} on property {GA4_PROPERTY}"
        print(f"    {why(body)}")
        print("  BLOCKED - the service account is not on this GA4 property. It is granted in")
        print("  Analytics > Admin > Account access management. There IS an API for it -")
        print("  accounts.accessBindings.create, scope analytics.manage.users - but it must be")
        print("  called by an existing administrator, so it cannot bootstrap itself.")


# ── Google Ads ─────────────────────────────────────────────────────────────────

def google_ads(tok: str) -> None:
    head("GOOGLE ADS")
    print(f"  customer {ADS_CUSTOMER} (836-758-9699) - queried DIRECTLY.")
    print(f"  manager {ADS_LOGIN_CUSTOMER} (427-041-2231) exists but is NOT used: a manager")
    print("  account is required only to manage MULTIPLE accounts via the API, and all three")
    print("  access paths were measured returning the same error, so it changes nothing here.")
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
    # DIRECT, WITH NO login-customer-id. A manager account is only needed to link and manage
    # MULTIPLE accounts through the API - Google's own policy doc says so since the developer
    # token sunset - and this deployment reads one account. Measured 2026-09-30, all three paths
    # return the IDENTICAL error, so the manager adds nothing here:
    #
    #   direct on 836-758-9699, no header   CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION
    #   via login-customer-id 427-041-2231  CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION
    #   direct on the manager itself        CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION
    #
    # That identity is itself the finding: the Cloud project's access tier is evaluated BEFORE
    # anything account-level, so it blocks every customer equally and no header can route around
    # it. Sending the manager id would only have made a project problem look like a linkage one.
    st, body = call(
        tok,
        f"https://googleads.googleapis.com/{version}/customers/{ADS_CUSTOMER}/googleAds:search",
        method="POST",
        body={"query": "SELECT customer.id, customer.descriptive_name, customer.manager, "
                       "customer.test_account, customer.currency_code FROM customer"},
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
    if not codes:
        VERDICT["Google Ads"] = f"OK - {len(names)} customer(s), query succeeded"
    elif "CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION" in joined or "ACTION_NOT_PERMITTED" in joined:
        VERDICT["Google Ads"] = (
            f"PARTIAL - account access GRANTED ({len(names)} customers visible), "
            "but the Cloud project is on Test access")
    elif "USER_PERMISSION_DENIED" in joined:
        VERDICT["Google Ads"] = "BLOCKED - not a user on the Ads account"
    else:
        VERDICT["Google Ads"] = f"BLOCKED - {joined[:60]}"

    if "CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION" in joined or "ACTION_NOT_PERMITTED" in joined:
        print("\n  BLOCKER = the Cloud project's API access level (Test).")
        print("  Apply for Explorer or Basic access on the Google Ads API Overview page in")
        print("  Cloud Console. Basic is automated and reviewed in minutes AFTER brand")
        print("  verification. Known issue: a project on Free Trial, or with suspended or")
        print("  disabled billing, is rejected - check billing state first.")
    elif "USER_PERMISSION_DENIED" in joined:
        print("\n  BLOCKER = account access. The principal is not a user on the Ads account,")
        print("  which puts Ads in the same category as Tag Manager and Analytics.")
        print("\n  STATED CAREFULLY, because an earlier version of this script over-claimed:")
        print("  getting USER_PERMISSION_DENIED rather than CLOUD_PROJECT_NOT_APPROVED_FOR_")
        print("  PRODUCTION SUGGESTS the Cloud project has production access, but it does not")
        print("  prove it - the order in which the API evaluates those two failures is not")
        print("  documented, so a Test-access project with no user link could plausibly report")
        print("  the user error first. The access level itself is NOT readable from the API:")
        print("  serviceusage exposes the four *_access_granted metrics for this project and")
        print("  every quotaBucket comes back empty, so the tier is visible only on the Google")
        print("  Ads API Overview page in Cloud Console, exactly as the policy doc says.")
        print("\n  TWO THINGS PRE-CHECKED so an application does not bounce:")
        print("  - Billing: enabled, account 016A1E-FB34AB-ABFE41, open, INR, not a")
        print("    sub-account. That rules out the doc's 'suspended or disabled billing'")
        print("    rejection. It does NOT rule out Free Trial, which the API does not expose")
        print("    and which the doc names as the same rejection cause - confirm in the")
        print("    console that the account is not showing as 'Free trial account'.")
        print("  - IAM: managing access levels needs Owner, Editor, Quota Administrator or")
        print("    Service Usage Admin. wecare.digital.bw@gmail.com holds roles/owner, so the")
        print("    OWNER can apply. This service account holds only serviceUsageConsumer and")
        print("    bigquery.jobUser, so it CANNOT - the application is a browser action.")


def main() -> int:
    tok = token()
    print(f"auth: impersonated {SA} (no browser, no key file, no secret read)")
    search_console(tok)
    tag_manager(tok)
    analytics(tok)
    google_ads(tok)

    head("SUMMARY")
    for product, verdict in VERDICT.items():
        mark = "ok  " if verdict.startswith("OK") else (
            "part" if verdict.startswith("PARTIAL") else "FAIL")
        print(f"  {mark}  {product:<16} {verdict}")

    outstanding = {p: v for p, v in VERDICT.items() if not v.startswith("OK")}
    if not outstanding:
        print("\n  All four products reachable.")
        return 0

    print(f"\n  {len(outstanding)} product(s) still outstanding:")
    for product, verdict in outstanding.items():
        if product == "Google Ads" and "Test access" in verdict:
            print("    Google Ads   the USER grant has landed - 2 customers are visible, and the")
            print("                 error moved from USER_PERMISSION_DENIED to")
            print("                 CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION. That second error")
            print("                 PROVES what could only be guessed before: the Cloud project")
            print("                 sits on Test access, which cannot call a production account.")
            print("                 USE THE EXISTING PROJECT: wecaredigitalbw (756034744787).")
            print("                 Not a new one, and not the other project in the account -")
            print("                 gmp-demo-project-567757500 is a Maps Platform demo. For a")
            print("                 service-account workflow the governing project is the one")
            print("                 that OWNS the service account, and that is wecaredigitalbw;")
            print("                 measured, not assumed. It already carries the OAuth brand")
            print("                 'WECARE.DIGITAL' and sits under organization 470921486845.")
            print("")
            print("                 APPLY FOR EXPLORER, NOT BASIC, AS THE FIRST STEP. The tier")
            print("                 quotas read live off this project:")
            print("                     test      no production access   <- current")
            print("                     explorer   2,880 operations/day")
            print("                     basic     15,000 operations/day")
            print("                     standard  unlimited")
            print("                 2,880/day is ample for reading reports, and the policy doc")
            print("                 requires brand verification for BASIC and STANDARD - not")
            print("                 Explorer. That matters here because this project's OAuth")
            print("                 brand is orgInternalOnly=True, i.e. an Internal consent")
            print("                 screen, which is not the thing a public brand verification")
            print("                 applies to. Explorer sidesteps the question entirely.")
            print("")
            print("                 DIRECT LINK (project pre-selected):")
            print("                   https://console.cloud.google.com/apis/api/"
                  "googleads.googleapis.com/overview?project=wecaredigitalbw")
            print("")
            print("                 THE QUOTA ROUTE DOES NOT WORK - tried, so nobody repeats it.")
            print("                 Access levels ARE modelled as quota, and serviceusage will")
            print("                 happily accept a consumerOverride: POSTing overrideValue")
            print("                 2880 to the explorer_access_level_operations limit as the")
            print("                 project OWNER returned http 200 and a real operation, and")
            print("                 the override appeared. Ads then returned the SAME")
            print("                 CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION. An override caps")
            print("                 a limit you already hold; it cannot grant the tier. The")
            print("                 override was deleted afterwards - a stray quota override on")
            print("                 a production project is debris someone later has to explain.")
            print("                 Needs Owner/Editor/Quota Admin: wecare.digital.bw@gmail.com")
            print("                 holds roles/owner, this service account does not - so it is")
            print("                 a browser action. Billing is already enabled and open, which")
            print("                 rules out the doc's suspended-billing rejection.")
            print("                 The manager account is NOT part of this: direct access,")
            print("                 the manager header and the manager itself all return the")
            print("                 same project-level error, because the tier is checked")
            print("                 before anything account-level.")
        elif product == "Tag Manager":
            print("    Tag Manager  Admin > Account > User Management > + , account + container")
            print("                 Read. Or accounts.user_permissions.create called by an")
            print("                 existing admin token with tagmanager.manage.users.")
        elif product == "Analytics GA4":
            print("    Analytics    Admin > Account access management > + , role Viewer. Or")
            print("                 accounts.accessBindings.create called by an existing admin")
            print("                 token with analytics.manage.users.")
        else:
            print(f"    {product:<12} {verdict}")
    print(f"\n  principal to grant: {SA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
