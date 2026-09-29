#!/usr/bin/env python3
"""Bulk ingestion: many PDFs and many URLs to blog source records, in one run.

WHAT THIS DOES, AND THE ONE THING IT WILL NOT DO.

It takes thousands of sources in a single invocation - a directory of PDFs, a file of
URLs, or a work order exported from the admin page - and for each one it:

  1. resolves it against the ledger, so a source already ingested is skipped rather
     than converted a second time (see `blog_ledger` for why that is the whole game),
  2. extracts the text (pypdf for a PDF, lxml for a page),
  3. reflows that text into clean markdown: de-hyphenated, paragraphs rejoined,
     running headers and page numbers dropped, headings recovered,
  4. writes the full extract to disk so a human can actually read the source, which
     section 2 of the standard requires before anything is written,
  5. emits a draft article record pre-filled with every mechanically derivable field -
     slug candidate, canonical, category, author, class, source provenance, source hash.

What it will not do is write the article. Section 31 of the standard is explicit about
the sequence - understand the source, remove the obsolete wrapper, preserve the real
distinction, reconstruct independently in Anew voice - and its closing line forbids the
shortcut: "old essay -> rename -> replace I with we -> lightly paraphrase -> publish".
A generated paraphrase carrying an auto-stamped READY_TO_PUBLISH is exactly that
shortcut wearing a pipeline. So every record lands on SOURCE_REVIEW with
`sourceReviewedFully` unset, and `blog_quality_v2` keeps it there until a person has
done the reading and recorded the human gates.

The mechanical half is what scales to thousands. The editorial half does not, and
pretending it does is how 250-article waves turn into 250 identical articles.

Usage:
    # a whole directory of PDFs plus a list of URLs, one run
    python scripts/blog_ingest.py ingest \\
        --pdf-dir ~/sources/conversations --url-file ~/sources/urls.txt \\
        --category Conversations --article-class ARCHIVE_DERIVED

    # a work order exported from /workspace/seo/blog-studio
    python scripts/blog_ingest.py ingest --work-order ~/Downloads/work-order.json \\
        --pdf-dir ~/sources

    python scripts/blog_ingest.py draft --ledger content/conversations/ledger.json \\
        --out content/conversations/drafts/CONV-001-CONV-025.json --limit 25
    python scripts/blog_ingest.py status --ledger content/conversations/ledger.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
#: The extraction logic is shared with the `wecare-seo-tools` Lambda, so it lives under
#: amplify/functions/shared/ where the deploy packager can reach it. `tests/conftest.py`
#: already puts that directory on sys.path for the Python suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "amplify" / "functions" / "shared"))

import blog_pipeline as bp  # noqa: E402
from blog_ledger import (  # noqa: E402
    Ledger,
    LedgerRow,
    normalize_url,
    now_iso,
    sha256_bytes,
    sha256_text,
    source_identity,
)
import blog_quality_v2 as q  # noqa: E402

DEFAULT_LEDGER = Path("content/conversations/ledger.json")
DEFAULT_EXTRACT_DIR = Path("content/conversations/extracts")
# ── Extraction comes from the shared module, not from here ──────────────────────
#
# This block used to hold ~390 lines of PDF and URL extraction, and it had to move. The
# same extraction now runs in `wecare-seo-tools` for the upload-from-the-browser path, and
# two copies would drift - the same PDF would produce different article text depending on
# which door it came through, which is the kind of difference nobody notices until a
# reviewer compares two extracts of one document.
#
# The shared module is stdlib + pypdf only, because Lambda is the harder of the two
# runtimes: lxml and requests cannot be zipped from a Mac into a Linux Lambda without
# building them there. Using lxml locally and html.parser in Lambda would BE the drift.
#
# Re-exported under the old names so this module's public surface and its tests are
# unchanged.
Extract = bp.Extract
reflow = bp.reflow
extract_pdf = bp.extract_pdf
extract_url = bp.extract_url
extract_html = bp.extract_html
MIN_EXTRACT_CHARS = bp.MIN_EXTRACT_CHARS
USER_AGENT = bp.USER_AGENT
_running_lines = bp.running_lines
_looks_like_heading = bp.looks_like_heading
_join_across_hyphen = bp.join_across_hyphen
_first_heading = bp.first_heading


# ── Source collection ───────────────────────────────────────────────────────────

@dataclass
class SourceSpec:
    source_type: str
    ref: str
    category: str
    article_class: str
    path: Optional[Path] = None


def collect_sources(args: argparse.Namespace) -> List[SourceSpec]:
    """Every source named on the command line or in a work order, de-duplicated by ref."""
    category = args.category
    article_class = args.article_class
    specs: List[SourceSpec] = []
    seen: set = set()

    def add(spec: SourceSpec) -> None:
        key = (spec.source_type, str(spec.path or spec.ref))
        if key in seen:
            return
        seen.add(key)
        specs.append(spec)

    for raw in args.pdf or ():
        path = Path(raw).expanduser()
        add(SourceSpec("pdf", str(path), category, article_class, path))

    for raw in args.pdf_dir or ():
        root = Path(raw).expanduser()
        if not root.is_dir():
            print(f"warning: {root} is not a directory", file=sys.stderr)
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() == ".pdf":
                add(SourceSpec("pdf", str(path), category, article_class, path))

    for raw in args.url or ():
        add(SourceSpec("url", normalize_url(raw), category, article_class))

    for raw in args.url_file or ():
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"warning: {path} is not a file", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                add(SourceSpec("url", normalize_url(line), category, article_class))

    for raw in args.work_order or ():
        specs_from_order, problems = read_work_order(
            Path(raw).expanduser(), category, article_class,
            search_dirs=[Path(p).expanduser() for p in (args.pdf_dir or ())])
        for problem in problems:
            print(f"warning: {problem}", file=sys.stderr)
        for spec in specs_from_order:
            add(spec)

    return specs


def read_work_order(path: Path, default_category: str, default_class: str,
                    search_dirs: Sequence[Path] = ()) -> Tuple[List[SourceSpec], List[str]]:
    """A work order exported from the admin page.

    The page cannot upload bytes anywhere (the site is a static export with no ingest
    backend yet), so it exports the operator's intent: which files, which category, which
    class, and the SHA-256 it computed in the browser. This function relocates each file
    on disk and checks the hash matches.

    THE HASH CHECK IS THE POINT. Browser and script compute the same SHA-256 over the
    same bytes, so a mismatch means the operator selected a different file than the one
    on disk - which is the failure that would otherwise attach the wrong provenance to an
    article, permanently and invisibly.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    items = document.get("sources") if isinstance(document, dict) else document
    order_category = str((document or {}).get("category") or "").strip() \
        if isinstance(document, dict) else ""
    specs: List[SourceSpec] = []
    problems: List[str] = []

    for item in items or []:
        kind = str(item.get("sourceType") or ("url" if item.get("url") else "pdf")).lower()
        category = str(item.get("category") or order_category or default_category).strip()
        article_class = str(item.get("articleClass") or default_class).strip().upper()
        if category not in q.CATEGORIES:
            problems.append(f"{path}: category {category!r} is not one of {list(q.CATEGORIES)}")
            continue
        if kind == "url":
            ref = normalize_url(item.get("url") or item.get("ref") or "")
            if not ref:
                problems.append(f"{path}: a url entry has no url")
                continue
            specs.append(SourceSpec("url", ref, category, article_class))
            continue

        name = str(item.get("fileName") or item.get("ref") or "").strip()
        expected = str(item.get("sha256") or "").strip().lower()
        located: Optional[Path] = None
        candidate = Path(name).expanduser()
        if candidate.is_file():
            located = candidate
        else:
            for directory in search_dirs:
                for found in directory.rglob(Path(name).name):
                    if found.is_file():
                        located = found
                        break
                if located:
                    break
        if located is None:
            problems.append(f"{path}: {name!r} not found on disk; pass --pdf-dir so it can "
                            "be located")
            continue
        if expected:
            actual = sha256_bytes(located.read_bytes())
            if actual != expected:
                problems.append(
                    f"{path}: {located} hashes to {actual[:12]}... but the work order "
                    f"recorded {expected[:12]}...; refusing to attach the wrong source")
                continue
        specs.append(SourceSpec("pdf", str(located), category, article_class, located))

    return specs, problems


# ── Ingestion ───────────────────────────────────────────────────────────────────

def _extract_one(spec: SourceSpec) -> Tuple[SourceSpec, Optional[bytes], Extract]:
    if spec.source_type == "pdf":
        path = spec.path or Path(spec.ref)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            return spec, None, Extract(False, error=f"unreadable file: {type(exc).__name__}")
        return spec, payload, extract_pdf(payload, ref=str(path))
    return spec, None, extract_url(spec.ref)


def ingest(specs: Sequence[SourceSpec], ledger: Ledger, extract_dir: Path,
           workers: int = 8, dry_run: bool = False,
           progress: bool = True) -> Dict[str, Any]:
    """Extract every source that is not already in the ledger.

    Resolution happens BEFORE extraction, not after: on a re-run over 2,000 PDFs the
    skip must be free, and a design that extracts first and then discovers the row
    already exists pays the full cost every time.
    """
    pending: List[SourceSpec] = []
    skipped: List[str] = []

    for spec in specs:
        payload: Optional[bytes] = None
        if spec.source_type == "pdf":
            path = spec.path or Path(spec.ref)
            try:
                payload = path.read_bytes()
            except OSError as exc:
                if not dry_run:
                    row, _ = ledger.register(
                        "text", str(path), category=spec.category,
                        articleClass=spec.article_class, status="EXTRACTION_FAILED",
                        error=f"unreadable file: {type(exc).__name__}")
                continue
        existing = ledger.resolve_source(spec.source_type, spec.ref, payload)
        if existing is not None and existing.status != "EXTRACTION_FAILED":
            skipped.append(existing.sourceRef)
            continue
        pending.append(spec)

    results = {"requested": len(specs), "skipped": len(skipped), "ingested": 0,
               "failed": 0, "failures": [], "rows": []}
    if dry_run:
        results["wouldIngest"] = [spec.ref for spec in pending]
        return results

    extract_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for spec, payload, extract in pool.map(_extract_one, pending):
            done += 1
            if progress and (done % 25 == 0 or done == len(pending)):
                print(f"  extracted {done}/{len(pending)}", file=sys.stderr)

            row, created = ledger.register(
                spec.source_type, spec.ref, payload,
                category=spec.category, articleClass=spec.article_class)

            if not extract.ok:
                ledger.update(row.sourceId, status="EXTRACTION_FAILED",
                              error=extract.error, sourcePages=extract.pages)
                results["failed"] += 1
                results["failures"].append({"ref": spec.ref, "error": extract.error})
                continue

            stem = (q.slugify(extract.title) or row.sourceId[:16])[:80]
            extract_path = extract_dir / f"{stem}-{row.sourceId[:8]}.md"
            extract_path.write_text(extract.text + "\n", encoding="utf-8")

            ledger.update(
                row.sourceId,
                status="INGESTED",
                error="",
                sourceTitle=extract.title,
                sourceDate=extract.date,
                sourcePages=extract.pages,
                extractedChars=len(extract.text),
                extractedWords=q.word_count(extract.text),
                extractPath=str(extract_path),
                contentSha256=extract.content_sha256,
                fetchedAt=now_iso() if spec.source_type == "url" else "",
            )
            results["ingested"] += 1
            results["rows"].append(row.sourceId)

    return results


# ── Draft records ───────────────────────────────────────────────────────────────

def draft_record(row: LedgerRow, extract_text: str) -> Dict[str, Any]:
    """A draft article record with every mechanical field filled and no editorial claim.

    Read what is NOT set here. `sourceReviewedFully` is absent, the section 5 uniqueness
    booleans are absent, and `gate` is absent. Those are the fields a human fills after
    doing the reading, and `blog_quality_v2.decide_status` will hold this record on
    SOURCE_REVIEW until they are. Pre-filling them with YES would produce a record that
    validates and means nothing.
    """
    title = row.sourceTitle or Path(row.extractPath or row.sourceRef).stem
    slug = q.slugify(title)
    words = q.word_count(extract_text)
    if words <= 420:
        article_type = "DISTINCTION"
    elif words <= 820:
        article_type = "REFLECTION"
    elif words <= 1500:
        article_type = "ARTICLE"
    else:
        article_type = "DEEP_ARTICLE"

    record: Dict[str, Any] = {
        "sourceId": row.sourceId,
        "articleClass": row.articleClass or "ARCHIVE_DERIVED",
        "status": "SOURCE_REVIEW",

        # Section 2 - provenance, machine-derived and therefore trustworthy.
        "sourceFile": row.sourceRef,
        "originalSourceTitle": row.sourceTitle,
        "originalSourceDate": row.sourceDate,
        "sourceType": row.sourceType,
        "sourceHash": row.sourceSha256,

        # Sections 21-25 - candidates, to be replaced by editorial decisions.
        "title": title,
        "slug": slug,
        "category": row.category or q.DEFAULT_CATEGORY,
        "author": q.AUTHOR,
        "canonical": q.expected_canonical(slug),
        "tags": [],
        "seoTitle": f"{title} | {q.PUBLISHER}" if title else "",
        "metaDescription": "",

        # Sections 10-11 - a suggestion from the source's own length.
        "articleType": article_type,

        # Section 27.
        "imageStatus": "none",

        # The body starts as the FAITHFUL EXTRACT, not as a rewrite. Section 3: understand
        # the source before editing it. This field is what the editor works from.
        "sourceExtract": extract_text,
        "contentMarkdown": "",

        # Sections 4 and 5 - left empty on purpose. See the docstring.
        "centralDistinction": "",
        "distinctPurpose": "",
    }
    return record


def _disambiguate_slugs(records: List[Dict[str, Any]]) -> None:
    """Make candidate slugs unique within a batch, and refuse to invent one.

    Two PDFs exported from the same template share a `/Title`, so both produced the slug
    `fixture-source-document` and the second would have collided the moment it was
    published. Section 22 forbids appending an arbitrary number to force uniqueness, so
    the fallback order is: the document's own filename stem, then NOTHING.

    An empty slug is the correct last resort. The gate blocks on SLUG_MISSING, which puts
    the decision in front of the editor who is reading the source anyway - whereas a
    machine-invented `-2` suffix is a URL nobody chose, and section 22 names it.
    """
    seen: Dict[str, int] = {}
    for record in records:
        slug = str(record.get("slug") or "")
        if slug and slug not in seen:
            seen[slug] = 1
            continue
        fallback = q.slugify(Path(str(record.get("sourceFile") or "")).stem)
        if fallback and fallback not in seen:
            record["slug"] = fallback
            record["canonical"] = q.expected_canonical(fallback)
            record.setdefault("ingestNotes", []).append(
                f"slug candidate {slug!r} collided; used the filename stem instead")
            seen[fallback] = 1
            continue
        record["slug"] = ""
        record["canonical"] = ""
        record.setdefault("ingestNotes", []).append(
            f"slug candidate {slug!r} collided and no distinct fallback existed; an editor "
            "must name this one (section 22 forbids appending a number to force uniqueness)")


def build_drafts(ledger: Ledger, out: Path, limit: Optional[int] = None,
                 category: Optional[str] = None) -> Dict[str, Any]:
    rows = [row for row in ledger.pending() if row.status == "INGESTED"]
    if category:
        rows = [row for row in rows if row.category == category]
    if limit:
        rows = rows[:limit]

    records: List[Dict[str, Any]] = []
    missing: List[str] = []
    for row in rows:
        path = Path(row.extractPath) if row.extractPath else None
        if path is None or not path.is_file():
            missing.append(row.sourceRef)
            continue
        records.append(draft_record(row, path.read_text(encoding="utf-8")))
    _disambiguate_slugs(records)

    document = {
        "generatedAt": now_iso(),
        "standard": "WECARE.DIGITAL Conversations Content Quality Standard v2",
        "note": ("Draft records. Every body is the faithful source extract, not an "
                 "article. Editorial reconstruction, the section 4/5 fields and the "
                 "section 29 human gates are all outstanding."),
        "posts": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"drafted": len(records), "missingExtract": missing, "out": str(out)}


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _add_source_args(node: argparse.ArgumentParser) -> None:
    node.add_argument("--pdf", nargs="*", default=[], help="one or more PDF paths")
    node.add_argument("--pdf-dir", nargs="*", default=[],
                     help="directories searched recursively for *.pdf")
    node.add_argument("--url", nargs="*", default=[], help="one or more URLs")
    node.add_argument("--url-file", nargs="*", default=[],
                     help="text files of URLs, one per line, # comments allowed")
    node.add_argument("--work-order", nargs="*", default=[],
                     help="work orders exported from /workspace/seo/blog-studio")
    node.add_argument("--category", default=q.DEFAULT_CATEGORY, choices=list(q.CATEGORIES))
    node.add_argument("--article-class", default="ARCHIVE_DERIVED",
                     choices=list(q.ARTICLE_CLASSES))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk PDF and URL blog ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_cmd = sub.add_parser("ingest")
    _add_source_args(ingest_cmd)
    ingest_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ingest_cmd.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_DIR)
    ingest_cmd.add_argument("--workers", type=int, default=8)
    ingest_cmd.add_argument("--limit", type=int, default=0)
    ingest_cmd.add_argument("--dry-run", action="store_true")
    ingest_cmd.add_argument("--json", action="store_true")

    draft_cmd = sub.add_parser("draft")
    draft_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    draft_cmd.add_argument("--out", required=True, type=Path)
    draft_cmd.add_argument("--limit", type=int, default=0)
    draft_cmd.add_argument("--category", default=None, choices=list(q.CATEGORIES))
    draft_cmd.add_argument("--json", action="store_true")

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    status_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    ledger = Ledger.load(args.ledger)

    if args.command == "status":
        report = ledger.rollup()
        print(json.dumps(report, indent=2) if args.json else
              "\n".join(f"{k:<18} {v}" for k, v in report.items()))
        return 0

    if args.command == "draft":
        result = build_drafts(ledger, args.out, args.limit or None, args.category)
        ledger.save()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"wrote {result['drafted']} draft record(s) to {result['out']}")
            for ref in result["missingExtract"]:
                print(f"  warning: no extract on disk for {ref}")
            print("\nEvery record is SOURCE_REVIEW. Next: read each extract, reconstruct the "
                  "article in Anew voice, fill centralDistinction and distinctPurpose, then "
                  "run scripts/blog_quality_v2.py validate.")
        return 0

    specs = collect_sources(args)
    if args.limit:
        specs = specs[:args.limit]
    if not specs:
        print("no sources given; pass --pdf, --pdf-dir, --url, --url-file or --work-order",
              file=sys.stderr)
        return 2

    print(f"{len(specs)} source(s) collected", file=sys.stderr)
    result = ingest(specs, ledger, args.extract_dir, workers=args.workers,
                    dry_run=args.dry_run)
    if not args.dry_run:
        ledger.save()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"requested {result['requested']}  "
              f"already known {result['skipped']}  "
              f"ingested {result['ingested']}  failed {result['failed']}")
        for failure in result["failures"]:
            print(f"  FAILED {failure['ref']}: {failure['error']}")
        if args.dry_run:
            for ref in result.get("wouldIngest", []):
                print(f"  would ingest {ref}")
        else:
            print(f"\nledger: {args.ledger}")
    #: A failed extraction is reportable, not fatal: on a 2,000-source run a handful of
    #: scans is expected, and exiting non-zero would make the whole run look failed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
