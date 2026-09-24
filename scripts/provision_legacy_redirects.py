#!/usr/bin/env python3
"""Phase 8.4 — every retired route redirects, and a deep link survives a refresh.

Why this is an Amplify rule and not `next.config.js`
---------------------------------------------------
`next.config.js` sets `output: 'export'` in production. A static export has no server,
so Next's own `redirects` array is inert — it is implemented by the Next server, which
is not deployed here. Writing them there would look correct in the repo and do nothing
in production, which is the exact failure mode this project keeps finding.

The other option was a tiny client-side redirect page per route. That works, but it
serves HTTP **200** and then bounces, so a search engine keeps the dead URL indexed and
a person sees a flash of the wrong page. An Amplify custom rule is a real **301**.

Ten routes were retired by the consolidation and all ten currently return **404**,
measured. A 404 is not the same as a redirect: an operator with a bookmark, or a link in
a runbook, hits a dead end instead of the page that replaced it — and for the four
channel-filtered destinations the replacement is a query string they would have to know
to type.

Order matters
-------------
Amplify evaluates custom rules top-down, and the app already ends with a
`/<*>` -> `/index.html` `404-200` catch-all. These redirects therefore have to be
INSERTED BEFORE it, or the catch-all swallows them. The script rebuilds the list as
[redirects] + [pre-existing non-redirect rules] rather than appending, and refuses to
run if it cannot find the catch-all where it expects it.

Both slash forms are registered because `trailingSlash: true` means the canonical URL is
`/dm/calls/`, while a hand-typed or older link is usually `/dm/calls`.

Usage:
    python scripts/provision_legacy_redirects.py            # report
    python scripts/provision_legacy_redirects.py --apply
    python scripts/provision_legacy_redirects.py --verify
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
APP_ID = "d22dm4b0jn71jw"
SITE = "https://wecare.digital"
SNAPSHOT = pathlib.Path("docs/execution/snapshots/amplify-custom-rules-before-8.4.json")

# Retired route -> what replaced it. Every target is a live page, and the four channel
# ones carry the query string the operator would otherwise have to know to type.
RETIRED = {
    "/dm/calls": "/dm/inbox/?channel=voice",
    "/dm/rcs/inbox": "/dm/inbox/?channel=rcs",
    "/dm/ses/inbox": "/dm/inbox/?channel=email",
    "/dm/whatsapp/logs": "/dm/logs/?channel=whatsapp",
    "/dm/rcs/logs": "/dm/logs/?channel=rcs",
    "/dm/ses/logs": "/dm/logs/?channel=email",
    "/dm/rcs/campaign": "/dm/broadcast/",
    "/dm/ses/campaign": "/dm/broadcast/",
    "/forms/logs": "/forms/responses/",
    "/link/logs": "/link/",
}


def amplify():
    return boto3.client("amplify", region_name=REGION)


def desired_redirects() -> list[dict]:
    rules = []
    for source, target in RETIRED.items():
        rules.append({"source": source, "target": target, "status": "301"})
        rules.append({"source": source + "/", "target": target, "status": "301"})
    return rules


def current_rules(client) -> list[dict]:
    app = client.get_app(appId=APP_ID)["app"]
    return [dict(r) for r in app.get("customRules", [])]


def is_ours(rule: dict) -> bool:
    src = rule.get("source", "").rstrip("/")
    return src in RETIRED


def report(client) -> tuple[list[dict], list[dict]]:
    existing = current_rules(client)
    want = desired_redirects()
    have = {(r["source"], r.get("target"), r.get("status")) for r in existing}
    missing = [r for r in want
               if (r["source"], r["target"], r["status"]) not in have]

    print(f"app {APP_ID}: {len(existing)} custom rule(s)")
    for r in existing:
        print(f"    {r.get('status'):>8}  {r.get('source')}  ->  {r.get('target')}")
    print(f"\nretired routes to redirect: {len(RETIRED)}")
    print(f"rules wanted: {len(want)}   missing: {len(missing)}")
    return existing, missing


def apply(client, existing: list[dict]) -> int:
    # Preserve everything that is not one of ours, IN ORDER, and put the redirects
    # first so the catch-all cannot swallow them.
    keep = [r for r in existing if not is_ours(r)]
    catch_all = [r for r in keep if r.get("source") == "/<*>"]
    if not catch_all:
        print("refusing to write: the /<*> catch-all is not in the current rules, so "
              "the ordering assumption this script relies on does not hold",
              file=sys.stderr)
        return 2

    # Domain-level 301s stay at the very top; the catch-all stays at the very bottom.
    domain = [r for r in keep if r.get("source", "").startswith("http")]
    middle = [r for r in keep
              if r not in domain and r.get("source") != "/<*>"]
    new_rules = domain + desired_redirects() + middle + catch_all

    if not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(existing, indent=4) + "\n")
        print(f"  snapshot written to {SNAPSHOT}")

    client.update_app(appId=APP_ID, customRules=new_rules)
    print(f"  wrote {len(new_rules)} rules "
          f"({len(domain)} domain + {len(desired_redirects())} redirects + "
          f"{len(middle)} other + 1 catch-all)")
    return 0


def probe(path: str) -> tuple[str, str]:
    """Status and Location, following nothing."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(SITE + path, timeout=20) as r:
            return str(r.status), r.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        return str(exc.code), exc.headers.get("Location", "") or ""
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, ""


def verify() -> int:
    problems = []
    client = amplify()
    _, missing = report(client)
    for r in missing:
        problems.append(f"rule missing: {r['source']}")

    print("\nlive probes (301 with a Location is the pass):")
    for source, target in RETIRED.items():
        for path in (source, source + "/"):
            code, loc = probe(path)
            print(f"  {path:26} -> {code:4} {loc}")
            if code == "404":
                problems.append(f"{path} still 404s")
            elif code not in ("301", "302", "308"):
                problems.append(f"{path} returned {code}, expected 301")
            elif target.split("?")[0].rstrip("/") not in loc:
                problems.append(f"{path} redirects to {loc}, expected {target}")

    print("\nthe replacement targets must themselves be live:")
    for target in sorted(set(RETIRED.values())):
        code, _ = probe(target)
        print(f"  {target:26} -> {code}")
        if code != "200":
            problems.append(f"redirect target {target} returned {code}, not 200")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nevery retired route 301s to a live replacement")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    client = amplify()
    try:
        existing, missing = report(client)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read the app: {type(exc).__name__}", file=sys.stderr)
        return 2

    if not missing:
        print("\nnothing to do; run --verify to probe")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1
    return apply(client, existing)


if __name__ == "__main__":
    raise SystemExit(main())
