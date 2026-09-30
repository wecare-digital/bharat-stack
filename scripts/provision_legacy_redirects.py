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

The catch-all's TARGET, changed 2026-09-28 (gap `SEO-404-001`)
-------------------------------------------------------------
The status stays `404-200` for the reason above. What changed is the document: the
catch-all now serves **`/404.html`**, not `/index.html`.

The status code was never the defect. `src/pages/404.tsx` carries
`<meta name="robots" content="noindex, follow">` and a canonical pointing at the home
page, and it is those that a crawler needs on a mistyped URL -- but while the catch-all
served `/index.html`, a mistyped path received the HOME page's head instead, canonical
self-referencing the dead URL and no `noindex` anywhere. The safeguards the 404 page was
written to provide never reached the only requests that needed them.

Serving `/404.html` keeps every behaviour the 404 page documents -- it still
`router.replace`s to the home page, so a visitor still lands on the home page and no
history entry is left behind -- and additionally delivers `noindex` and the correct
canonical. Measured before the change: `/definitely-not-a-page/` returned 404 with
`"page":"/"` and 52,131 bytes of home page. After: 404 with `"page":"/404"`.

It costs nothing in reachability. `/workspace/seo/page/<*>` is the app's only runtime
dynamic route and it was ALREADY not working: a static export emits the literal
directory `out/workspace/seo/page/[id]`, which no URL can address, so
`/workspace/seo/page/test/` was being swallowed by this same catch-all and hydrating as
`"page":"/"` -- the home page, under a 404, with the id discarded. Measured, not assumed.
That route needs the id moved into a query string to work at all; pointing the catch-all
at `/404.html` neither causes nor worsens it.

Order matters
-------------
Amplify evaluates custom rules top-down, and the app already ends with a
`/<*>` -> `/index.html` `404-200` catch-all. These redirects therefore have to be
INSERTED BEFORE it, or the catch-all swallows them. The script rebuilds the list as
[redirects] + [pre-existing non-redirect rules] rather than appending, and refuses to
run if it cannot find the catch-all where it expects it.

Both slash forms are registered because `trailingSlash: true` means the canonical URL is
`/workspace/engage/calls/`, while a hand-typed or older link is usually `/workspace/engage/calls`.

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
import time
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
APP_ID = "d22dm4b0jn71jw"
SITE = "https://wecare.digital"
# Resolved against the repo root, not the cwd. This path carried a stray `workspace/`
# prefix until 2026-09-28 -- collateral from the `/dm/` -> `/workspace/` rename, which
# string-replaced inside a filesystem path that has nothing to do with URL topology. The
# effect was silent: `--apply` created `workspace/docs/execution/snapshots/` in the repo
# root and wrote the rollback artefact there, so the snapshot everyone would reach for
# was not where the script's own docstring implied.
SNAPSHOT = (pathlib.Path(__file__).resolve().parents[1]
            / "docs/execution/snapshots/amplify-custom-rules-before-8.4.json")

# Retired route -> what replaced it. Every target is a live page, and the four channel
# ones carry the query string the operator would otherwise have to know to type.
RETIRED = {
    "/workspace/engage/calls": "/workspace/engage/inbox/?channel=voice",
    "/workspace/engage/rcs/inbox": "/workspace/engage/inbox/?channel=rcs",
    "/workspace/engage/ses/inbox": "/workspace/engage/inbox/?channel=email",
    "/workspace/engage/whatsapp/logs": "/workspace/engage/logs/?channel=whatsapp",
    "/workspace/engage/rcs/logs": "/workspace/engage/logs/?channel=rcs",
    "/workspace/engage/ses/logs": "/workspace/engage/logs/?channel=email",
    "/workspace/engage/rcs/campaign": "/workspace/engage/broadcast/",
    "/workspace/engage/ses/campaign": "/workspace/engage/broadcast/",
    "/workspace/link/logs": "/workspace/link/",
    # RENAMED 2026-09-28 on owner instruction: the menu row "My Order" became "Orders" and the
    # page moved with it. This is the first PUBLIC, indexable entry in this dict - every other
    # one is behind /workspace/ - which is what makes the 301 matter rather than being tidiness:
    # /my-order/ has been live, is in the sitemap, is advertised in llms.txt and is shipped
    # inside the MCP catalogue, so it is a URL other people and other machines already hold.
    # A 301 moves that equity to /orders/ and takes the old path out of the index; letting it
    # fall through to the catch-all would serve 404.html at HTTP 200 instead, which is the
    # failure mode this whole script exists to avoid.
    "/my-order": "/orders/",
    # ── URLs WITH PROVEN SEARCH EQUITY ON THE OLD www SITE ──────────────────────
    #
    # These are not guesses. Search Console's `https://www.wecare.digital/` property holds
    # 480 days of history that the apex property does not - 313 clicks and 7,411 impressions -
    # because the site moved from the www Wix site to this apex export and Google's index still
    # points at the old map. Measured 2026-09-30 via searchAnalytics, and every number below is
    # that property's own figure for the URL.
    #
    # WHAT MADE THIS INVISIBLE: the apex property reports ZERO impressions, so every earlier
    # reading here concluded the site had no search presence at all. It has presence; it is
    # filed under the other host, against URLs that no longer exist.
    #
    # /swdhya CONTRADICTS A COMMENT IN THIS REPOSITORY, which is why it leads.
    # src/content/products.ts said of the Swdhya -> Open Possibility -> Anew renames: "Neither
    # earlier address was ever published - this page exists only on an unmerged branch - so
    # there is no external link or search equity to keep and no redirect to write. If this page
    # HAD shipped, /swdhya/ and /open-possibility/ would both need 301s." It shipped:
    # 531 impressions, 3 clicks, average position 6.0. So by that comment's own test the
    # redirect is owed, and the comment has been corrected to say so.
    "/swdhya": "/anew/",              # 531 impressions, pos 6.0
    # Same rename chain. No impressions measured for this one, but it is the same page under
    # its second name and the rule costs nothing - and the premise that neither name shipped
    # has now been shown false once already.
    "/open-possibility": "/anew/",
    # 127 impressions, pos 4.4. The FAQ page was deleted on owner instruction; /contact/ is
    # where the self-service routes now live, so it is the honest destination for someone who
    # arrived looking for answers.
    "/faq": "/contact/",
    # ── SECOND PASS, 2026-09-30: ten more, and a MEASUREMENT LESSON ─────────────
    #
    # The entries above came from one reading of the www property. A second reading found ten
    # more URLs with equity, and the reason the first pass missed them is worth writing down
    # because it will recur: the first query used a 90-DAY window. On a site that migrated
    # hosts months ago, a recent window measures the post-migration COLLAPSE, not the equity
    # at stake. Over 90 days the www property reports 412 impressions; over its full 480 days
    # it reports 17,115 across 156 URLs - a 40x difference, all of it equity that still exists
    # in Google's index and still points at URLs that now 404.
    #
    # So: when sizing a migration loss, always query the maximum window Search Console
    # retains. A short window on a migrated property systematically under-reports the damage,
    # and it under-reported it here by enough to change which URLs looked worth a rule.
    #
    # Every figure below is that property's own, measured over 2025-06-07 .. 2026-09-28, and
    # every destination was confirmed to answer 200 before being written here. A redirect to a
    # 404 is worse than no redirect: it converts a clean drop into a soft-404 signal.
    "/no-fault": "/clear-closure/",          # 497 impr, pos 4.5 - online dispute resolution
    "/legal-stuff": "/terms/",               # 379 impr, pos 6.3
    "/expoweek": "/expo-week/",              # 292 impr, pos 5.7 - same page, hyphen added
    "/legal-stuffs": "/terms/",              # 239 impr, pos 5.4 - the plural also ranked
    "/ritual-store": "/ritual-guru/",        # 226 impr, pos 12.9 - temple-grade puja kits
    "/swdhya-store": "/anew/",               # 212 impr, pos 6.9 - same rename chain as /swdhya
    "/request-tracking": "/orders/",         # 201 impr, pos 8.1 - order/request status
    "/rx-slot": "/bharat-rx/",               # 188 impr, pos 6.5 - consults and appointments
    "/bring-friends": "/refer-and-earn/",    # 132 impr, pos 10.4 - the referral programme
    "/home": "/",                            # 8 impr - Wix's index alias
    #
    # DELIBERATELY NOT REDIRECTED, despite carrying more equity than several entries above.
    # Each one has real impressions and NO honest destination on the current site, and an
    # irrelevant redirect is read as a soft 404 - so it damages the target page rather than
    # rescuing the source. Left to 404 so Google drops them cleanly. Listed rather than
    # omitted, so nobody has to re-measure to discover they were considered:
    #
    #     /bnb                    872 impr, pos 6.2    no equivalent service
    #     /bnb-club               622 impr, pos 7.2    no equivalent service
    #     /careers-plus-culture   569 impr, pos 19.1   no careers page exists
    #     /partner-up             413 impr, pos 6.6    "Partner Up" is named in terms.ts s6.3
    #                                                  but has no public page; /refer-and-earn/
    #                                                  is a CUSTOMER referral, not a B2B
    #                                                  partner programme, so it is the wrong
    #                                                  destination rather than an approximate
    #                                                  one
    #     /one                    342 impr, pos 6.5    unidentified
    #     /legal-champ            301 impr, pos 5.2    a legal SERVICE, not the terms page;
    #                                                  /clear-closure/ is dispute resolution
    #                                                  specifically, which may or may not be
    #                                                  what this was
    #     /gift-card              221 impr, pos 9.1    gift cards survive only as terms s21,
    #                                                  not as a purchasable page
    #
    # These need an owner decision, not a guess. If any of those services still exists under a
    # new name, add the rule; the equity is there to reclaim.
    #
    # /_functions/llms (337), /_functions-dev/llms (337), /_functions/aiindex (254),
    # /_functions/smextra (170), /_functions/smtxt (159) are Wix BACKEND function endpoints,
    # 1,257 impressions between them. They are not pages and were never meant to rank. The
    # apex equivalent of the first two is /llms.txt, which is a file rather than a route; a
    # rule for them belongs with the AI-surface work, not here, and is left out on purpose so
    # it gets decided rather than absorbed.
    # /product-page is NOT in this dict - it needs a wildcard, so it is in RETIRED_TREES below.
    # It WAS here briefly and that was measurably not enough: RETIRED emits only the exact path
    # and its slash form, so the rule fixed /product-page and /product-page/ while
    # /product-page/partner - the one actually carrying 665 impressions - kept 404ing.
    #
    # NOT ADDED, because the destination is a guess and a 301 to the wrong page is worse for a
    # reader than a 404:
    #   /bnb-club   644 impressions, pos 7.4 - appears NOWHERE in this repository. Unknown
    #               what the page was, so there is no defensible target. Needs the owner.
    #   /rx-slot    188 impressions, pos 6.5 - probably /bharat-rx/ (consults, appointments,
    #               reminders), and `rx-slots` survives as an authenticated workspace feature
    #               at /workspace/engage/rx-slots. Probably is not good enough to point 188
    #               impressions at. Needs confirming.

    # /llm IS DELIBERATELY ABSENT, AND THIS ENTRY IS NOT COMING BACK.
    #
    # It was `"/llm": "/llms.txt"` from its retirement on 2026-09-30 until the owner removed
    # the redirect the same day: "i dont want any redirect llm must go". So /llm now falls
    # through to the `/<*>` catch-all and answers a real 404.
    #
    # THE ARGUMENT FOR THE 301 IS RECORDED RATHER THAN DELETED, because it was not a bad
    # argument and whoever reads this next deserves to see what was traded away. /llm/ was
    # live at HTTP 200, was named in public/robots.txt and out/llms.txt, and was linked from
    # the MCP server's own User-Agent string - so it is an address other people and other
    # machines already hold, and a 301 would have moved its equity to a document that carries
    # the same content. The owner's call overrides that, and the cost is explicit: anyone
    # holding the old URL now gets a 404 instead of the replacement document.
    #
    # WHAT THE 404 BUYS, so the decision is not only a cost. A 301 keeps a retired URL alive
    # in Google's index as a redirect for as long as the rule exists; a 404 drops it. Given
    # /llm/ was one thin page and its content is fully covered by /llms.txt - which robots.txt
    # advertises directly - there is little equity to preserve and one fewer URL to explain.
    #
    # If it is ever restored, the target must be /llms.txt and NOT /mcp: /mcp answers 405 to a
    # GET because it offers no SSE stream, so pointing a browser URL there turns a retired page
    # into a method error. That reasoning is about the target and survives the removal.
    #
    # ONE 301 ON /llm CANNOT BE REMOVED, AND IT IS NOT A RULE IN THIS FILE. Measured 2026-09-30:
    #
    #     /llm       301 -> /llm/        then 404
    #     /contact   301 -> /contact/    then 200
    #     /zzz-fake  301 -> /zzz-fake/   then 404
    #
    # `trailingSlash: true` in next.config.js makes the canonical form of every URL carry the
    # slash, and Amplify normalises to it for EVERY path - including ones that never existed.
    # So /llm is already treated identically to any other dead address.
    #
    # An explicit `{'source': '/llm', 'target': '/404.html', 'status': '404-200'}` rule was
    # tried, to serve the 404 without the hop. IT IS INERT: Amplify applies the slash
    # normalisation before custom rules, so /llm still answered 301. The rule was removed rather
    # than left in place, on the same principle robots.txt states for a Disallow on a route that
    # does not exist - a rule that does nothing implies something works.
    #
    # The only way to drop the hop is turning trailingSlash off, which rewrites all 1,353
    # canonicals, the sitemap and every internal link to remove one redirect from a dead path.
    # Do not do that.
}

# Retired SUBTREES: an old path whose every descendant collapses to ONE destination.
#
# Distinct from RENAMED_PREFIXES below, which maps a tree onto a matching tree and PRESERVES the
# tail (`/dm/<*>` -> `/workspace/engage/<*>`). Here the tail is discarded, because the
# destination is a single page - there is no `/contact/partner` to land on.
#
# WHY THIS NEEDED ITS OWN SHAPE rather than one more RETIRED entry: RETIRED emits the exact path
# and its slash form and nothing else. `"/product-page": "/contact/"` was tried there first and
# measured afterwards - /product-page and /product-page/ started working while
# /product-page/partner, the URL actually carrying the impressions, was still 404. The wildcard
# IS the requirement, so encoding it in the data beats a comment asking the next person to
# remember.
RETIRED_TREES = {
    # Wix product URLs from the old www site. src/content/wix-catalog.json still shows the
    # shape - xout.wecare.digital/product-page/<slug> - and /product-page/partner alone carries
    # 665 impressions at position 7.0 on the www Search Console property.
    #
    # tools/browser/seocheck.js already names /contact/ as the intended target and records that
    # the 301 was "expected at the CDN (Amplify Console)" and "is not visible to this harness".
    # It was never actually configured, which is exactly the kind of gap a harness that cannot
    # see the CDN will not catch - so these URLs 404ed for as long as anyone had been assuming
    # they redirected.
    "/product-page": "/contact/",
}

# Prefix renames: old top-level segment -> new one. `/dm` became `/workspace/engage` on
# 2026-09-26 (63 routes).
#
# This is declared here rather than left as rules someone added in the console,
# because `apply()` rebuilds the list as [redirects] + [everything else] and only
# treats a rule as "ours" if its source is in RETIRED. The `/dm` rules would have
# survived a re-run by landing in `middle` — by luck, not by design. The same class
# of bug is already documented above for `/workspace/forms/logs`: a rule the script does not
# model is a rule the next `--apply` can silently drop or resurrect.
#
# Each entry expands to three rules plus a one-hop rule per RETIRED route:
#
#   /dm        -> /engage/      301   bare form
#   /dm/       -> /engage/      301   trailing form; a static host treats these
#                                        as different keys
#   /dm/<*>    -> /engage/<*>   301   everything else. AWS documents exactly this
#                                        shape for a prefix rename, and the wildcard
#                                        must be last in the source and appear once.
#
# The one-hop rules matter: without them `/dm/calls` would take TWO redirects
# (`/dm/calls` -> `/workspace/engage/calls` -> `/workspace/engage/inbox/?channel=voice`). Correct,
# but a wasted round trip on every old bookmark, so the old prefix gets its own
# direct rule to the final destination.
# `/workspace` is listed alongside `/dm` and is NOT dropped as a rounding error. It
# genuinely deployed — Amplify job 937 SUCCEED, and `/workspace/inbox/` served 200 —
# so it is a URL that existed and could have been captured. The realistic number of
# bookmarks is near zero on an admin-only, robots-disallowed route family, but three
# rules is a trivial price against a broken link, and "it was only live briefly" is
# the same argument that would justify dropping any redirect.
# On 2026-09-26 the thirteen authenticated route families were nested under
# `/workspace/`, so every one of them is an old prefix now. `/dm` and `/engage` both
# land on `/workspace/engage` because the section was renamed twice before moving.
#
# `/workspace` itself MUST NOT appear as a key. It was briefly an old prefix during a
# twenty-minute rename, and a bulk edit re-added it here as
# `"/workspace": "/workspace/engage"` — which would have emitted
# `/workspace/<*>` -> `/workspace/engage/<*>`, redirecting `/workspace/dashboard` to
# `/workspace/engage/dashboard` and taking out all thirteen sections at once. The
# wildcard cannot point inside its own source prefix.
#
# The cost of dropping it: a bookmark captured during that twenty-minute window, on a
# robots-disallowed admin family, no longer resolves. That is accepted deliberately;
# the alternative breaks the live tree.
RENAMED_PREFIXES = {
    "/dm": "/workspace/engage",
    "/engage": "/workspace/engage",
    "/dashboard": "/workspace/dashboard",
    "/contacts": "/workspace/contacts",
    "/commerce": "/workspace/commerce",
    "/pay": "/workspace/pay",
    "/forms": "/workspace/forms",
    "/service": "/workspace/service",
    "/docs": "/workspace/docs",
    "/seo": "/workspace/seo",
    "/admin": "/workspace/admin",
    "/access": "/workspace/access",
    "/link": "/workspace/link",
    "/task": "/workspace/task",
    "/settings": "/workspace/settings",
}

# Paths that are frozen OUTSIDE this repository and cannot be edited to follow a
# rename. Added 2026-09-28.
#
# WHY THIS IS A SEPARATE DICT AND NOT MORE RETIRED ENTRIES. Everything in RETIRED is a
# route this project itself retired, where the redirect is a courtesy to a bookmark. The
# two below are different in kind: the URL is printed inside an **approved, immutable**
# provider artefact, so the redirect is the only repair available at all.
#
#   /selfservice  appears in DLT-approved SMS template `ivr-default`
#                 (1007277993798259629) as "Submit your request here:
#                 https://wecare.digital/selfservice". A DLT body must match the
#                 registration character for character, and the registry table
#                 `stack-wecare-digital-DLTTemplates` holds no other approved content,
#                 so the sentence CANNOT be changed. It is also in the body of nine
#                 approved Sinch RCS templates, including `rcsmenu` — the one template
#                 every post-call RCS actually sends — and an approved RCS body cannot
#                 be edited in place either, only superseded by a new template.
#   /track        appears in approved RCS template `wecare_order_update`.
#
# Measured 2026-09-28: `/selfservice` and `/track` both 404, and 0 of the app's 104
# custom rules mentioned either. PR #47 (`6bc44a35`) removed the in-repo `/selfservice`
# stub and nothing replaced it, so the primary call to action in the SMS had been dead.
#
# WHY THESE TARGETS. Not `/contact/`, which was the obvious guess and is weaker. The
# frozen sentence is literally "**Submit your request** here", and since 2026-09-28 there
# is a real public page for exactly that — `/submit-request/`, one of the five Selfservice
# rows given their own pages. `/track` maps to `/orders/`, whose own badge reads "Order
# tracking". Both were probed live at 200 before being named here. A redirect to a page
# that answers the sentence beats one to a generic contact form.
#
# WHY A REDIRECT RATHER THAN RESTORING A `/selfservice` PAGE. `faa956e8` deliberately
# removed "Selfservice" from everywhere customer-visible. Re-creating the page would
# reintroduce the retired word as a live public URL; a 301 keeps the frozen links working
# without putting it back in front of anyone.
# `/track` REPOINTED 2026-09-28 from `/my-order/` to `/orders/` with the page rename. This is the
# entry that made the rename more than a find-and-replace: the sentence containing /track is
# printed inside a DLT-approved template that cannot be edited, so the redirect is the only thing
# standing between an unchangeable SMS and a dead link. Left at /my-order/ it would have chained
# /track -> /my-order/ -> /orders/ at best, and pointed at nothing at worst.
FROZEN_EXTERNAL = {
    "/selfservice": "/submit-request/",
    "/track": "/orders/",
}

# REMOVED 2026-09-25 on owner instruction: "/workspace/forms/logs": "/workspace/forms/responses/".
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
    # Frozen external links first. No wildcard overlaps any of them, so position among
    # the specific rules is not load-bearing; what matters is that they precede the
    # `/<*>` catch-all, which apply() guarantees for everything in this list.
    for source, target in FROZEN_EXTERNAL.items():
        rules.append({"source": source, "target": target, "status": "301"})
        rules.append({"source": source + "/", "target": target, "status": "301"})

    for source, target in RETIRED.items():
        rules.append({"source": source, "target": target, "status": "301"})
        rules.append({"source": source + "/", "target": target, "status": "301"})

    # Retired subtrees. The `<*>` form goes AFTER the two exact forms, for the same reason the
    # prefix renames order theirs that way: a wildcard placed before a specific rule matches
    # first and the specific rule becomes unreachable.
    for source, target in RETIRED_TREES.items():
        rules.append({"source": source, "target": target, "status": "301"})
        rules.append({"source": source + "/", "target": target, "status": "301"})
        rules.append({"source": f"{source}/<*>", "target": target, "status": "301"})

    # Prefix renames. Ordering inside this list is load-bearing: the one-hop rules for
    # specific retired routes must precede the `<*>` wildcard, or the wildcard matches
    # first and sends `/dm/calls` to a `/workspace/engage/calls` page that does not exist.
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


# Sources this script once emitted and must now actively REMOVE rather than merely
# stop emitting. `apply()` preserves anything `is_ours()` does not claim, so dropping a
# prefix from RENAMED_PREFIXES is not enough on its own — the old rules survive in
# `middle` and keep redirecting. That is how `/workspace/<*>` -> `/engage/<*>` outlived
# the rename that made it wrong, and an assertion caught it pointing the live
# `/workspace` tree at a path that no longer exists.
OBSOLETE_SOURCES = {
    "/workspace", "/workspace/", "/workspace/<*>",
}

# Every internal path a redirect may legitimately land on. Anything else is a target
# left behind by an earlier topology.
#
# The public entries were added 2026-09-28 with FROZEN_EXTERNAL and are NOT cosmetic.
# `_targets_dead_prefix()` treats any internal target outside this tuple as residue and
# `is_ours()` then claims it for deletion — so without them the two new rules would be
# judged dead on sight, and, worse, so would any future rule pointing at a public page.
# Listed individually rather than relaxed to "/" so the check keeps its teeth: a target
# that is genuinely stale still has to be named here to survive.
# `/orders/` replaced `/my-order/` on 2026-09-28. `/my-order/` is NOT kept here: nothing targets
# it any more, and leaving a retired page in the list of legitimate destinations is how the
# residue check loses its teeth - the point of naming each one is that a stale target has to be
# re-justified to survive.
LIVE_TARGET_PREFIXES = (
    "/workspace/", "/index.html", "/404.html", "/get/",
    "/submit-request/", "/orders/", "/contact/",
)

#: The document the `/<*>` catch-all serves on a miss. See the docstring section
#: "The catch-all's TARGET" for why this is the 404 export and not `/index.html`.
#: `apply()` normalises the live rule onto this value, because the catch-all is
#: otherwise preserved verbatim and would silently keep whatever it already had.
CATCH_ALL_SOURCE = "/<*>"
CATCH_ALL_TARGET = "/404.html"
CATCH_ALL_STATUS = "404-200"


def _targets_dead_prefix(rule: dict) -> bool:
    """True when a rule points at a path that no longer exists.

    Enumerating obsolete SOURCES is not sufficient. The `/workspace/{calls,rcs/inbox,…}`
    rules had valid-looking sources and stale TARGETS (`/engage/inbox/?channel=voice`),
    so they passed a source check and still pointed sixteen routes at a deleted prefix.
    Deriving it from the target instead means the next topology change cannot leave the
    same residue behind.
    """
    t = rule.get("target", "")
    if not t.startswith("/"):
        return False  # absolute URL: an external rewrite, not ours to judge
    return not t.startswith(LIVE_TARGET_PREFIXES)


def is_ours(rule: dict) -> bool:
    """Rules this script owns and will rewrite from scratch on --apply.

    Must cover the prefix-rename rules too. If it does not, they are treated as
    foreign, preserved in `middle`, AND re-emitted by desired_redirects() — which
    duplicates every one of them on each run.
    """
    src = rule.get("source", "").rstrip("/")
    if rule.get("source") in OBSOLETE_SOURCES or src in {s.rstrip("/") for s in OBSOLETE_SOURCES}:
        return True
    if _targets_dead_prefix(rule):
        return True
    if src in RETIRED:
        return True
    if src in {s.rstrip("/") for s in FROZEN_EXTERNAL}:
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
    print(f"frozen external links to repair: {len(FROZEN_EXTERNAL)} "
          f"({', '.join(FROZEN_EXTERNAL)})")
    print(f"rules wanted: {len(want)}   missing: {len(missing)}")
    return existing, missing


def apply(client, existing: list[dict]) -> int:
    # Preserve everything that is not one of ours, IN ORDER, and put the redirects
    # first so the catch-all cannot swallow them.
    keep = [r for r in existing if not is_ours(r)]
    catch_all = [r for r in keep if r.get("source") == CATCH_ALL_SOURCE]
    if not catch_all:
        print("refusing to write: the /<*> catch-all is not in the current rules, so "
              "the ordering assumption this script relies on does not hold",
              file=sys.stderr)
        return 2

    # Normalise the catch-all rather than preserving it verbatim. It is the one rule
    # whose target this script asserts, and leaving it untouched is how it kept
    # pointing at /index.html after 404.tsx was written to handle this case.
    for rule in catch_all:
        if rule.get("target") != CATCH_ALL_TARGET or rule.get("status") != CATCH_ALL_STATUS:
            print(f"  catch-all normalised: {rule.get('status')} {rule.get('target')}"
                  f"  ->  {CATCH_ALL_STATUS} {CATCH_ALL_TARGET}")
        rule["target"] = CATCH_ALL_TARGET
        rule["status"] = CATCH_ALL_STATUS

    # Domain-level 301s stay at the very top; the catch-all stays at the very bottom.
    domain = [r for r in keep if r.get("source", "").startswith("http")]
    middle = [r for r in keep
              if r not in domain and r.get("source") != CATCH_ALL_SOURCE]
    new_rules = domain + desired_redirects() + middle + catch_all

    # THE HISTORICAL SNAPSHOT IS NOT A ROLLBACK ARTEFACT, and treating it as one would be
    # worse than having none. It is written once and then kept forever, so it holds the THREE
    # rules this app had on 2026-09-24. Production is past a hundred. Restoring it to undo a
    # run would delete every rule added since - the /mcp rewrite, the /get/<*> CDN
    # passthrough, the whole /workspace tree - which is a far larger outage than whatever it
    # was reverting. It stays because it records where this started, not because it is a
    # recovery path, and `public-surface-deploy.yml` used to point operators at it by name.
    if not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(existing, indent=4) + "\n")
        print(f"  first-run historical snapshot written to {SNAPSHOT}")

    # The actual rollback artefact: what was live a moment ago, timestamped, one file per run.
    # In CI this is inside the runner and vanishes with it, which is why the workflow uploads
    # it as a run artefact - a production write whose previous state exists only in a
    # discarded filesystem is a write with no way back.
    rollback = (pathlib.Path(__file__).resolve().parents[1] / ".scratch" /
                f"amplify-custom-rules-before-{time.strftime('%Y%m%d-%H%M%S')}.json")
    rollback.parent.mkdir(parents=True, exist_ok=True)
    rollback.write_text(json.dumps(existing, indent=4) + "\n")
    print(f"  rollback snapshot ({len(existing)} rules as live now) -> {rollback}")

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
    for source, target in {**FROZEN_EXTERNAL, **RETIRED}.items():
        for path in (source, source + "/"):
            code, loc = probe(path)
            frozen = " [frozen external link]" if source in FROZEN_EXTERNAL else ""
            print(f"  {path:26} -> {code:4} {loc}{frozen}")
            if code == "404":
                problems.append(f"{path} still 404s")
            elif code not in ("301", "302", "308"):
                problems.append(f"{path} returned {code}, expected 301")
            elif target.split("?")[0].rstrip("/") not in loc:
                problems.append(f"{path} redirects to {loc}, expected {target}")

    print("\nthe replacement targets must themselves be live:")
    for target in sorted(set(RETIRED.values()) | set(FROZEN_EXTERNAL.values())):
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

    # Two independent kinds of divergence, and keying "nothing to do" on the first
    # alone is what let the catch-all keep pointing at /index.html indefinitely: the
    # redirect set was complete, so the script returned 0 and never looked at it.
    drifted = [r for r in existing
               if r.get("source") == CATCH_ALL_SOURCE
               and (r.get("target") != CATCH_ALL_TARGET
                    or r.get("status") != CATCH_ALL_STATUS)]
    for rule in drifted:
        print(f"\ncatch-all drift: {rule.get('status')} {rule.get('target')}"
              f"  should be  {CATCH_ALL_STATUS} {CATCH_ALL_TARGET}")

    if not missing and not drifted:
        print("\nnothing to do; run --verify to probe")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1
    return apply(client, existing)


if __name__ == "__main__":
    raise SystemExit(main())
