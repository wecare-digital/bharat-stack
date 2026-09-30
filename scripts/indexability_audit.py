#!/usr/bin/env python3
"""Why is the corpus not indexed? Answered from the built export, with no credentials.

    python scripts/indexability_audit.py            # summary
    python scripts/indexability_audit.py --json
    python scripts/indexability_audit.py --list-thin 20

Read-only. Needs `out/` from `npm run build` and nothing else - no AWS, no Google, no OAuth.

WHY THIS EXISTS ALONGSIDE search_console_index_audit.py
------------------------------------------------------
That script asks Google, per URL, why it is or is not indexed. It is the authoritative answer
and it needs the Search Console OAuth credential, so it cannot run in CI and cannot run at all
while the Cloud project is on Test access. This one asks the complementary question - "is there
anything in what we PUBLISHED that would stop it being indexed" - and it can run on any
checkout, which means the answer is available to anybody at any time rather than to whoever
holds the credential.

THE FINDING THIS WAS WRITTEN TO ESTABLISH, measured 2026-09-30 on 1279 posts
---------------------------------------------------------------------------
Google reported 1352 of 1353 URLs not indexed, and the obvious suspects are all clean:

    noindex                0
    missing canonical      0
    canonical mismatch     0
    duplicate titles       0
    missing datePublished  0
    missing author         0
    robots.txt             deliberate, and audited - see the file's own header

What is not clean is LENGTH. The median post carries 232 words of body text, 86% are under
300, and the longest in the entire corpus is 545. No page exceeds 600 words.

That is the signature of "Crawled - currently not indexed", which is the verdict Google gives
a page it fetched and judged not worth a place in the index. It is a content judgement, not a
configuration fault, and no amount of sitemap, schema or canonical work moves it. Recording it
as a measured number is the point: the technical surface being clean is exactly what makes
thinness the remaining explanation, and that conclusion is only trustworthy while the zeros
above stay zero. Hence a script rather than a note.

`scripts/blog_quality_v2.py` sets ABSOLUTE_MIN_WORDS to 120, so a 150-word post passes it by
design - the threshold permits what was published rather than the gate having been evaded.

WHAT THIS SCRIPT CANNOT TELL YOU, stated so the number below is not over-read. It counts words
RENDERED inside <main>; blog_quality_v2.py counts words in the MARKDOWN SOURCE. The two totals
differ per post, so when this reports N posts under the gate's floor that is NOT N posts that
evaded the gate - it is a prompt to run the gate, which counts the thing its floor is defined
against. An earlier draft of this file asserted the stronger claim and was wrong to.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SITE = "https://wecare.digital"

#: The floor scripts/blog_quality_v2.py enforces. Read from that file rather than restated, so
#: the two cannot drift - the whole point of the note above is that the gate is NOT being
#: bypassed, and that claim has to stay true on its own.
def gate_floor() -> int:
    source = (ROOT / "scripts" / "blog_quality_v2.py").read_text(encoding="utf-8")
    match = re.search(r"^ABSOLUTE_MIN_WORDS\s*=\s*(\d+)", source, re.M)
    return int(match.group(1)) if match else 0


#: Where Google's own guidance puts "thin". There is no published number, so this is a working
#: threshold for reporting rather than a rule being cited - hence it is named as an opinion.
REPORTING_THRESHOLD = 300

TAG = re.compile(r"<[^>]+>")


def body_words(html: str) -> int:
    """Words inside <main>, which is the text a reader actually gets.

    Counted from <main> and not the whole document on purpose: the header, the footer and the
    support widget are identical on all 1279 posts, so counting them would add the same few
    hundred words to every page and make a thin corpus look adequate.
    """
    main = re.search(r"<main.*?</main>", html, re.S)
    if not main:
        return 0
    return len(TAG.sub(" ", main.group(0)).split())


def audit() -> dict:
    posts = sorted(OUT.glob("post/*/index.html"))
    if not posts:
        print("no posts under out/post/ - run `npm run build` first", file=sys.stderr)
        raise SystemExit(2)

    counts: list[int] = []
    noindex: list[str] = []
    missing_canonical: list[str] = []
    canonical_mismatch: list[tuple[str, str]] = []
    no_date: list[str] = []
    no_author: list[str] = []
    thin: list[tuple[str, int]] = []
    below_gate: list[tuple[str, int]] = []
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)

    for path in posts:
        slug = path.parent.name
        html = path.read_text(encoding="utf-8")

        robots = re.search(r'<meta name="robots" content="([^"]*)"', html)
        if robots and "noindex" in robots.group(1):
            noindex.append(slug)

        canonical = re.search(r'<link rel="canonical" href="([^"]*)"', html)
        if not canonical:
            missing_canonical.append(slug)
        elif canonical.group(1) != f"{SITE}/post/{slug}/":
            canonical_mismatch.append((slug, canonical.group(1)))

        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        if title:
            titles[title.group(1).strip()].append(slug)
        description = re.search(r'<meta name="description" content="([^"]*)"', html)
        if description:
            descriptions[description.group(1)].append(slug)

        if "datePublished" not in html:
            no_date.append(slug)
        if '"author"' not in html:
            no_author.append(slug)

        words = body_words(html)
        counts.append(words)
        if words < REPORTING_THRESHOLD:
            thin.append((slug, words))
        if words < gate_floor():
            below_gate.append((slug, words))

    counts.sort()
    buckets = Counter()
    for words in counts:
        buckets[
            "0-149" if words < 150 else "150-299" if words < 300
            else "300-599" if words < 600 else "600-999" if words < 1000 else "1000+"
        ] += 1

    return {
        "posts": len(posts),
        "words": {
            "median": statistics.median(counts),
            "mean": round(statistics.mean(counts), 1),
            "p10": counts[len(counts) // 10],
            "p90": counts[9 * len(counts) // 10],
            "min": counts[0],
            "max": counts[-1],
            "buckets": dict(buckets),
        },
        "gateFloor": gate_floor(),
        "reportingThreshold": REPORTING_THRESHOLD,
        "clean": {
            "noindex": len(noindex),
            "missingCanonical": len(missing_canonical),
            "canonicalMismatch": len(canonical_mismatch),
            "duplicateTitles": sum(1 for s in titles.values() if len(s) > 1),
            "missingDatePublished": len(no_date),
            "missingAuthor": len(no_author),
        },
        "duplicateTitles": {t: s for t, s in titles.items() if len(s) > 1},
        "duplicateDescriptions": {d: s for d, s in descriptions.items() if len(s) > 1},
        "thinCount": len(thin),
        "belowGateCount": len(below_gate),
        "thin": sorted(thin, key=lambda pair: pair[1]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-thin", type=int, default=0,
                        help="print the N shortest posts")
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    words = report["words"]
    print("=" * 74)
    print(f"indexability audit - {report['posts']} posts in out/post/")
    print("=" * 74)

    print("\nTHE TECHNICAL SURFACE (every one of these should be 0)")
    for name, value in report["clean"].items():
        flag = "ok " if value == 0 else "!! "
        print(f"  {flag}{name:<22} {value}")

    print(f"\nBODY LENGTH inside <main>  median {words['median']}  mean {words['mean']}"
          f"  p10 {words['p10']}  p90 {words['p90']}  range {words['min']}-{words['max']}")
    for bucket in ("0-149", "150-299", "300-599", "600-999", "1000+"):
        n = words["buckets"].get(bucket, 0)
        bar = "#" * max(0, round(n / max(1, report["posts"]) * 50))
        print(f"  {bucket:>9} words  {n:5}  {bar}")

    pct = report["thinCount"] * 100 // report["posts"]
    print(f"\n  under {report['reportingThreshold']} words : {report['thinCount']} ({pct}%)")
    # NOT COMPARABLE, AND SAYING SO IS THE POINT. An earlier version of this line printed "the
    # gate is not being bypassed" next to this number, which it cannot establish: this script
    # counts words RENDERED inside <main>, while blog_quality_v2.py counts words in the MARKDOWN
    # SOURCE before it becomes HTML. Those two totals differ per post, so a count below the floor
    # here is not evidence of a post that evaded the gate. It is a prompt to check with
    # `python scripts/blog_quality_v2.py`, which counts the thing the floor is defined against.
    print(f"  rendered body under the blog_quality_v2 floor of {report['gateFloor']} : "
          f"{report['belowGateCount']}")
    print("    NB different metric from the gate's - it counts markdown source, this counts")
    print("    rendered <main> - so this is a prompt to run blog_quality_v2.py, not a verdict.")

    dupes = report["duplicateDescriptions"]
    if dupes:
        print(f"\nDUPLICATE META DESCRIPTIONS ({len(dupes)}) - two URLs describing themselves "
              "identically is a de-duplication signal:")
        for description, slugs in dupes.items():
            print(f"  {slugs}")
            print(f"    {description[:100]}")
        print("  These live in the blog corpus, not in this repository, so they are reported "
              "here rather than fixed here.")

    if args.list_thin:
        print(f"\nTHE {args.list_thin} SHORTEST:")
        for slug, n in report["thin"][:args.list_thin]:
            print(f"  {n:4} words  /post/{slug}/")

    print("\nVERDICT")
    if any(report["clean"].values()):
        print("  Something in the published markup would stop indexing - see the !! lines above.")
    else:
        print("  Nothing in the published markup blocks indexing: no noindex, no canonical")
        print("  problem, no duplicate titles, dates and authors present on every post.")
        print(f"  What remains is length. A median of {words['median']} words with nothing above")
        print(f"  {words['max']} is the signature of \"Crawled - currently not indexed\", which is")
        print("  a content judgement and not something sitemap, schema or canonical work moves.")
        print("  Ask Google directly with scripts/search_console_index_audit.py when the")
        print("  credential is available; this script is the half that needs no credential.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
