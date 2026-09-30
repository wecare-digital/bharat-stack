#!/usr/bin/env python3
"""Google Search Console: submit the sitemap, and retire the old sitemap feeds.

WHAT THE SEARCH CONSOLE API CAN AND CANNOT DO, stated first, because the obvious
reading of "remove old links from Google" is not a thing this API offers.

The Search Console API v3 exposes exactly four services - Search Analytics, Sitemaps,
Sites and URL Inspection (https://developers.google.com/webmaster-tools/v1/api_reference_index).
There is **no removals endpoint**. The Removals tool is Search Console UI only, its
effect is temporary (roughly six months), and a URL that still returns 200 comes back
when the block lapses. So:

  * Removing an OLD SITEMAP that is still registered  -> DELETE sitemaps/{feedpath}.
    This IS in the API, and it is what this script's --prune does. It matters because
    a registered sitemap Google can no longer fetch shows up permanently as
    "Couldn't fetch", and a registered sitemap listing dead URLs keeps asking Google
    to crawl them.

  * Removing an OLD URL from the index -> not available, and not needed. What actually
    drops a URL is the response the crawler gets when it re-fetches it: 301 consolidates
    onto the replacement, 404/410 drops it. Both are already true for every retired URL
    on this site - verified by scripts/retired_url_probe.py, which fails if any retired
    URL answers 200. The Removals tool only ever hides a URL that is still live, which
    is a different problem from the one we have.

AUTHORIZATION IS THE REAL BLOCKER, and it cannot be solved from here.

Submitting requires the read/WRITE scope https://www.googleapis.com/auth/webmasters
(the .readonly scope cannot submit), and the principal holding it must be a user on the
Search Console property. Measured on this machine:

    gcloud identity  wecare.digital.bw@gmail.com
    token scopes     cloud-platform, compute, appengine.admin, sqlservice.login,
                     userinfo.email, openid, accounts.reauth
    webmasters       ABSENT  ->  sites.list returns 403 PERMISSION_DENIED,
                                 "Request had insufficient authentication scopes"

`wecare/seo/google-oauth` holds a client id and secret but no refresh token, and
src/content/integration-registry.json records it as `access: SCOPE_UNVERIFIED`,
`adapterBuilt: false`, with only `webmasters.readonly` requested. So there is no stored
credential that can submit either.

Both routes out require a human once, and neither has an API:

  1. Re-consent this machine's ADC with the write scope (one browser round trip):

         gcloud auth application-default login \
             --scopes=https://www.googleapis.com/auth/webmasters,\
https://www.googleapis.com/auth/cloud-platform

     The signed-in Google account must already be a user on the property.

  2. Or grant a service account. Create a key, then add its email under
     Search Console > Settings > Users and permissions as Full (Restricted cannot
     submit). scripts/google-language-relay.sh already documents that this step is
     irreducibly manual - there is no API for granting Search Console access - and it
     currently reports 0 properties visible for the relay service account.

Until one of those is done every write here reports BLOCKED rather than pretending.

USAGE

    python scripts/search_console_sitemap.py check          # auth + property state
    python scripts/search_console_sitemap.py list           # registered sitemaps
    python scripts/search_console_sitemap.py submit         # dry run
    python scripts/search_console_sitemap.py submit --apply
    python scripts/search_console_sitemap.py prune          # dry run: stale feeds
    python scripts/search_console_sitemap.py prune --apply
    python scripts/search_console_sitemap.py inspect /anew/

    --property sc-domain:wecare.digital   # override the property to act on
    --sitemap  https://.../sitemap.xml    # override the feed

SECRET DISCIPLINE. The access token is held in memory only. It is never printed, never
written to a file, and never placed on a command line or in an environment assignment -
see .kiro/steering/secret-handling.md, and note that this script deliberately does not
read anything out of Secrets Manager.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://wecare.digital"
DEFAULT_SITEMAP = f"{SITE}/sitemap.xml"

# Both property shapes are tried, because which one exists is a property-creation
# decision nobody can read back without access. A Domain property covers every
# subdomain and both schemes; a URL-prefix property covers exactly one origin.
CANDIDATE_PROPERTIES = [
    "sc-domain:wecare.digital",
    f"{SITE}/",
    "https://www.wecare.digital/",
]

API = "https://searchconsole.googleapis.com/webmasters/v3"
WRITE_SCOPE = "https://www.googleapis.com/auth/webmasters"
READ_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

UNBLOCK = (
    "  Re-consent ADC with the write scope (one browser round trip, as the Google\n"
    "  account that owns the Search Console property):\n\n"
    "    gcloud auth application-default login \\\n"
    f"        --scopes={WRITE_SCOPE},https://www.googleapis.com/auth/cloud-platform\n\n"
    "  Or point GOOGLE_APPLICATION_CREDENTIALS at a service-account key whose email\n"
    "  has been added under Search Console > Settings > Users and permissions as\n"
    "  Full. That grant has no API and must be done in the UI."
)


# --------------------------------------------------------------------------- auth


class Auth:
    """A bearer token plus what is known about its scopes. Never exposes the value."""

    def __init__(self, token: str, source: str, scopes: list[str] | None) -> None:
        self._token = token
        self.source = source
        self.scopes = scopes  # None means "could not be determined"

    @property
    def header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def has_write(self) -> bool | None:
        if self.scopes is None:
            return None
        return any(s == WRITE_SCOPE for s in self.scopes)

    def has_any_console(self) -> bool | None:
        if self.scopes is None:
            return None
        return any(s in (WRITE_SCOPE, READ_SCOPE) for s in self.scopes)


def _tokeninfo(token: str) -> list[str] | None:
    """Ask Google what the token is actually good for. Sends the token, prints nothing."""
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v1/tokeninfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode() or "{}")
    except Exception:  # noqa: BLE001
        return None
    scope = body.get("scope")
    return scope.split() if scope else None


def resolve_auth() -> Auth | None:
    """Service-account key, then ADC, then the gcloud user credential."""
    # 1. An explicit service-account key, scoped to webmasters.
    try:
        import google.auth  # type: ignore
        import google.auth.transport.requests  # type: ignore
        from google.oauth2 import service_account  # type: ignore

        import os

        key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if key and os.path.exists(key):
            creds = service_account.Credentials.from_service_account_file(
                key, scopes=[WRITE_SCOPE])
            creds.refresh(google.auth.transport.requests.Request())
            return Auth(creds.token, f"service account key ({key})", [WRITE_SCOPE])

        # 2. Application Default Credentials.
        creds, _ = google.auth.default(scopes=[WRITE_SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
        return Auth(creds.token, "application default credentials",
                    _tokeninfo(creds.token))
    except Exception:  # noqa: BLE001
        pass

    # 3. The gcloud user credential. Almost certainly lacks the webmasters scope, but
    #    reporting that precisely is more useful than reporting "no credentials".
    for args in (["gcloud", "auth", "application-default", "print-access-token"],
                 ["gcloud", "auth", "print-access-token"]):
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=90)
        except Exception:  # noqa: BLE001
            continue
        if p.returncode == 0 and p.stdout.strip():
            tok = p.stdout.strip()
            return Auth(tok, " ".join(args[:-1]), _tokeninfo(tok))
    return None


# ---------------------------------------------------------------------- transport


def call(auth: Auth, method: str, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(API + path, method=method, headers=auth.header)
    if method in ("PUT", "POST", "DELETE"):
        req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": raw[:400]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": type(e).__name__}


def post_json(auth: Auth, url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={**auth.header,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": raw[:400]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": type(e).__name__}


def enc(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def why(body: dict) -> str:
    err = body.get("error") or {}
    if isinstance(err, str):
        return err
    return f"{err.get('status', '?')}: {err.get('message', body)}"


# ------------------------------------------------------------------------ actions


def properties(auth: Auth) -> tuple[int, list[dict]]:
    st, body = call(auth, "GET", "/sites")
    return st, (body.get("siteEntry") or []) if st == 200 else []


def pick_property(auth: Auth, override: str | None) -> tuple[str | None, list[dict], int]:
    st, entries = properties(auth)
    if override:
        return override, entries, st
    have = {e.get("siteUrl") for e in entries}
    for c in CANDIDATE_PROPERTIES:
        if c in have:
            return c, entries, st
    # Nothing visible. Return the domain-property guess so the error names a target.
    return (entries[0]["siteUrl"] if entries else None), entries, st


def cmd_check(auth: Auth, args) -> int:  # noqa: ANN001
    print(f"credential source : {auth.source}")
    if auth.scopes is None:
        print("token scopes      : could not be determined")
    else:
        print(f"token scopes      : {len(auth.scopes)}")
        for s in sorted(auth.scopes):
            mark = " <-- write" if s == WRITE_SCOPE else (
                " <-- read only" if s == READ_SCOPE else "")
            print(f"                    {s}{mark}")
    print(f"write scope       : {auth.has_write()}")

    st, entries = properties(auth)
    print(f"sites.list        : http {st}")
    if st != 200:
        _, body = call(auth, "GET", "/sites")
        print(f"                    {why(body)}")
        print("\nBLOCKED - no usable Search Console credential.\n")
        print(UNBLOCK)
        return 2
    print(f"properties        : {len(entries)}")
    for e in entries:
        print(f"                    {e.get('siteUrl')}  "
              f"permission={e.get('permissionLevel')}")
    if not entries:
        print("\nBLOCKED - authentication works, but this principal is not a user on")
        print("any Search Console property. There is no API for granting that.\n")
        print(UNBLOCK)
        return 2
    return 0


def cmd_list(auth: Auth, args) -> int:  # noqa: ANN001
    prop, entries, st = pick_property(auth, args.property)
    if st != 200 or prop is None:
        return cmd_check(auth, args)
    print(f"property: {prop}")
    st, body = call(auth, "GET", f"/sites/{enc(prop)}/sitemaps")
    if st != 200:
        print(f"sitemaps.list http {st}  {why(body)}")
        return 2
    feeds = body.get("sitemap") or []
    print(f"registered sitemaps: {len(feeds)}")
    for f in feeds:
        print(f"  {f.get('path')}")
        print(f"    type={f.get('type')} lastSubmitted={f.get('lastSubmitted')} "
              f"lastDownloaded={f.get('lastDownloaded')} "
              f"warnings={f.get('warnings')} errors={f.get('errors')} "
              f"isPending={f.get('isPending')} isSitemapsIndex={f.get('isSitemapsIndex')}")
        for c in f.get("contents") or []:
            print(f"    contents: type={c.get('type')} submitted={c.get('submitted')} "
                  f"indexed={c.get('indexed')}")
    return 0


def cmd_submit(auth: Auth, args) -> int:  # noqa: ANN001
    prop, entries, st = pick_property(auth, args.property)
    if st != 200 or prop is None:
        return cmd_check(auth, args)
    if auth.has_write() is False:
        print("BLOCKED - the token carries no write scope, so submit would 403.\n")
        print(UNBLOCK)
        return 2
    feed = args.sitemap
    print(f"property : {prop}")
    print(f"sitemap  : {feed}")
    if not args.apply:
        print("\nDRY RUN - nothing submitted. Re-run with --apply.")
        print(f"would PUT {API}/sites/{enc(prop)}/sitemaps/{enc(feed)}")
        return 0
    st, body = call(auth, "PUT", f"/sites/{enc(prop)}/sitemaps/{enc(feed)}")
    if st in (200, 204):
        print(f"SUBMITTED (http {st})")
        # Read it straight back. A 200 on the PUT only means Google accepted the
        # registration, not that it could fetch the file.
        st2, b2 = call(auth, "GET", f"/sites/{enc(prop)}/sitemaps/{enc(feed)}")
        if st2 == 200:
            print(f"  lastSubmitted={b2.get('lastSubmitted')} "
                  f"lastDownloaded={b2.get('lastDownloaded')} "
                  f"errors={b2.get('errors')} warnings={b2.get('warnings')} "
                  f"isPending={b2.get('isPending')}")
            print("  NOTE: lastDownloaded stays empty until Google fetches the file.")
        return 0
    print(f"FAILED http {st}  {why(body)}")
    return 2


def cmd_prune(auth: Auth, args) -> int:  # noqa: ANN001
    """Remove registered sitemap feeds this site no longer serves."""
    import urllib.request as ur

    prop, entries, st = pick_property(auth, args.property)
    if st != 200 or prop is None:
        return cmd_check(auth, args)
    st, body = call(auth, "GET", f"/sites/{enc(prop)}/sitemaps")
    if st != 200:
        print(f"sitemaps.list http {st}  {why(body)}")
        return 2
    feeds = body.get("sitemap") or []
    keep, stale = [], []
    for f in feeds:
        path = f.get("path") or ""
        if path == args.sitemap:
            keep.append((f, 200, "the current sitemap"))
            continue
        try:
            with ur.urlopen(ur.Request(
                    path, headers={"User-Agent": "wecare-gsc-prune/1"}),
                    timeout=30) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception:  # noqa: BLE001
            code = 0
        (stale if code != 200 else keep).append(
            (f, code, "not served" if code != 200 else "still served"))

    print(f"property: {prop}")
    print(f"registered: {len(feeds)}   keep: {len(keep)}   stale: {len(stale)}")
    for f, code, note in keep:
        print(f"  KEEP   http {code}  {f.get('path')}  ({note})")
    for f, code, note in stale:
        print(f"  STALE  http {code}  {f.get('path')}  ({note})")
    if not stale:
        print("\nnothing to prune.")
        return 0
    if auth.has_write() is False:
        print("\nBLOCKED - no write scope, so delete would 403.\n")
        print(UNBLOCK)
        return 2
    if not args.apply:
        print("\nDRY RUN - nothing deleted. Re-run with --apply.")
        return 0
    rc = 0
    for f, _code, _note in stale:
        path = f.get("path")
        st, body = call(auth, "DELETE", f"/sites/{enc(prop)}/sitemaps/{enc(path)}")
        if st in (200, 204):
            print(f"  DELETED {path}")
        else:
            print(f"  FAILED  {path}  http {st}  {why(body)}")
            rc = 2
    print("\nReversible: re-register any of these with `submit --sitemap <url>`.")
    return rc


def cmd_inspect(auth: Auth, args) -> int:  # noqa: ANN001
    prop, entries, st = pick_property(auth, args.property)
    if st != 200 or prop is None:
        return cmd_check(auth, args)
    target = args.url
    if target.startswith("/"):
        target = SITE + target
    st, body = post_json(
        auth,
        "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
        {"inspectionUrl": target, "siteUrl": prop, "languageCode": "en-IN"},
    )
    if st != 200:
        print(f"urlInspection http {st}  {why(body)}")
        return 2
    res = (body.get("inspectionResult") or {}).get("indexStatusResult") or {}
    print(f"url        : {target}")
    print(f"verdict    : {res.get('verdict')}")
    print(f"coverage   : {res.get('coverageState')}")
    print(f"robots     : {res.get('robotsTxtState')}")
    print(f"indexing   : {res.get('indexingState')}")
    print(f"canonical  : google={res.get('googleCanonical')} "
          f"user={res.get('userCanonical')}")
    print(f"lastCrawl  : {res.get('lastCrawlTime')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action",
                    choices=["check", "list", "submit", "prune", "inspect"])
    ap.add_argument("url", nargs="?", default="/",
                    help="for `inspect`: the URL or path to inspect")
    ap.add_argument("--property", default=None,
                    help="Search Console property, e.g. sc-domain:wecare.digital")
    ap.add_argument("--sitemap", default=DEFAULT_SITEMAP)
    ap.add_argument("--apply", action="store_true",
                    help="perform writes; without it every write is a dry run")
    args = ap.parse_args()

    auth = resolve_auth()
    if auth is None:
        print("BLOCKED - no Google credential available at all.\n")
        print(UNBLOCK)
        return 2

    return {
        "check": cmd_check, "list": cmd_list, "submit": cmd_submit,
        "prune": cmd_prune, "inspect": cmd_inspect,
    }[args.action](auth, args)


if __name__ == "__main__":
    raise SystemExit(main())
