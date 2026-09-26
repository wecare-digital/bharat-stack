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

Nine, since 2026-09-25 — see the note under RETIRED for the one that was withdrawn.

What the catch-all actually does, because the name misleads
----------------------------------------------------------
`404-200` is NOT "rewrite and return 200". The Amplify CDK enum names it
`NOT_FOUND_REWRITE` and documents it as **"Not found rewrite (404)"**, and that is what
the live app does — measured 2026-09-25: an unknown path returns HTTP **404** with a body
byte-identical to `/index.html`.

So an unknown path already serves the home page's HTML, and because the export's
`index.html` carries `"page":"/"`, it hydrates as the home route and the real home page
renders. What it does not do is return 200 or clean up the address bar.

Do NOT "fix" that by switching the catch-all to plain `200`. A `200` rewrite matches
unconditionally rather than only on a miss, so `/<*>` -> `/index.html` at `200` would
shadow all ~123 exported pages and serve the home page for the entire site. The same
applies to `301`/`302` on `/<*>`. Only the 404-family statuses are evaluated after the
file lookup fails, which is exactly why this rule uses one.

Order matters
-------------
Amplify evaluates custom rules top-down, and the app already ends with a
`/<*>` -> `/index.html` `404-200` catch-all. These redirects therefore have to be
INSERTED BEFORE it, or the catch-all swallows them. The script rebuilds the list as
[redirects] + [pre-existing non-redirect rules] rather than appending, and refuses to
run if it cannot find the catch-all where it expects it.

Both slash forms are registered because `trailingSlash: true` means the canonical URL is
`/workspace/calls/`, while a hand-typed or older link is usually `/workspace/calls`.

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
    "/workspace/calls": "/workspace/inbox/?channel=voice",
    "/workspace/rcs/inbox": "/workspace/inbox/?channel=rcs",
    "/workspace/ses/inbox": "/workspace/inbox/?channel=email",
    "/workspace/whatsapp/logs": "/workspace/logs/?channel=whatsapp",
    "/workspace/rcs/logs": "/workspace/logs/?channel=rcs",
    "/workspace/ses/logs": "/workspace/logs/?channel=email",
    "/workspace/rcs/campaign": "/workspace/broadcast/",
    "/workspace/ses/campaign": "/workspace/broadcast/",
    "/link/logs": "/link/",
}

# Prefix renames: old top-level segment -> new one. `/dm` became `/workspace` on
# 2026-09-26 (63 routes).
#
# This is declared here rather than left as rules someone added in the console,
# because `apply()` rebuilds the list as [redirects] + [everything else] and only
# treats a rule as "ours" if its source is in RETIRED. The `/dm` rules would have
# survived a re-run by landing in `middle` — by luck, not by design. The same class
# of bug is already documented above for `/forms/logs`: a rule the script does not
# model is a rule the next `--apply` can silently drop or resurrect.
#
# Each entry expands to three rules plus a one-hop rule per RETIRED route:
#
#   /dm        -> /workspace/      301   bare form
#   /dm/       -> /workspace/      301   trailing form; a static host treats these
#                                        as different keys
#   /dm/<*>    -> /workspace/<*>   301   everything else. AWS documents exactly this
#                                        shape for a prefix rename, and the wildcard
#                                        must be last in the source and appear once.
#
# The one-hop rules matter: without them `/dm/calls` would take TWO redirects
# (`/dm/calls` -> `/workspace/calls` -> `/workspace/inbox/?channel=voice`). Correct,
# but a wasted round trip on every old bookmark, so the old prefix gets its own
# direct rule to the final destination.
RENAMED_PREFIXES = {
    "/dm": "/workspace",
}

# REMOVED 2026-09-25 on owner instruction: "/forms/logs": "/forms/responses/".
#
# Deleted from the live app too (rules 22 -> 20; snapshot in
# docs/execution/snapshots/amplify-custom-rules-before-forms-logs-removal.json).
# It has to come out of this dict as well, not just out of the app, or the next
# --apply run silently puts it back and the removal looks like it did not stick.
#
# /forms/logs is now covered by the /<*> catch-all like any other unknown path: the
# home page's HTML is served in its place. That is a weaker answer than the 301 was,
# and it was still the owner's call to make.


def amplify():
    return boto3.client("amplify", region_name=REGION)


def desired_redirects() -> list[dict]:
    rules = []
    for source, target in RETIRED.items():
        rules.append({"source": source, "target": target, "status": "301"})
        rules.append({"source": source + "/", "target": target, "status": "301"})

    # Prefix renames. Ordering inside this list is load-bearing: the one-hop rules for
    # specific retired routes must precede the `<*>` wildcard, or the wildcard matches
    # first and sends `/dm/calls` to a `/workspace/calls` page that does not exist.
    for old, new in RENAMED_PREFIXES.items():
        for source, target in RETIRED.items():
            if not source.startswith(new + "/"):
                continue
            old_source = old + source[len(new):]
            rules.append({"source": old_source, "target": target, "status": "301"})
            rules.append({"source": old_source + "/", "target": target, "status": "301"})
        rules.append({"source": old, "target": new + "/", "status": "301"})
        rules.append({"source": old + "/", "target": new + "/", "status": "301"})
        rules.append({"source": f"{old}/<*>", "target": f"{new}/<*>", "status": "301"})
    return rules


def current_rules(client) -> list[dict]:
    app = client.get_app(appId=APP_ID)["app"]
    return [dict(r) for r in app.get("customRules", [])]


def is_ours(rule: dict) -> bool:
    """Rules this script owns and will rewrite from scratch on --apply.

    Must cover the prefix-rename rules too. If it does not, they are treated as
    foreign, preserved in `middle`, AND re-emitted by desired_redirects() — which
    duplicates every one of them on each run.
    """
    src = rule.get("source", "").rstrip("/")
    if src in RETIRED:
        return True
    for old, new in RENAMED_PREFIXES.items():
        if src == old or src == f"{old}/<*>":
            return True
        # A one-hop rule for a retired route under the old prefix.
        if src.startswith(old + "/") and new + src[len(old):] in RETIRED:
            return True
    return False


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
