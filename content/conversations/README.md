# Conversations — PDF and URL to blog pipeline

Bulk intake of PDFs and URLs, converted into Conversations (or Gastronomy) articles under
the **Conversations Content Quality Standard v2**, with a ledger recording which article
came from which source.

## The shape of it

```
sources (PDF / URL)
  │
  ├─ scripts/blog_ingest.py ingest    extract, reflow, hash, register in the ledger
  │     └─ extracts/<slug>-<id>.md    the readable source, for section 2
  │
  ├─ scripts/blog_ingest.py draft     draft records, every field a machine can fill
  │     └─ drafts/CONV-*.json         status SOURCE_REVIEW, body = source extract
  │
  ├─ EDITORIAL  (human)               read the source, reconstruct in Anew voice,
  │                                   fill centralDistinction / distinctPurpose,
  │                                   record the section 29 human gates
  │
  ├─ scripts/blog_quality_v2.py       the standard, as executable checks
  │     └─ batches/CONV-*.json        only READY_TO_PUBLISH enters the queue
  │
  └─ publish path                     scripts/conversations_batch.py (Conversations)
        │                             scripts/gastronomy_batch.py   (Gastronomy)
        └─ both delegate every Wix write to scripts/wix_blog_migrate.py
```

## What is committed, and what is not

| Path | Committed | Why |
|---|---|---|
| `ledger.json` | **yes** | the source-to-article record; the whole point is that it is durable and diffable |
| `batches/CONV-*.json` | **yes** | the finished Anew articles, which are ours |
| `extracts/` | **no** | verbatim text of third-party PDFs. Committing a book's text is a licensing problem and a repo-size one |
| `drafts/` | **no** | each draft embeds the full `sourceExtract`, so the same reasoning applies |

`extracts/` and `drafts/` are gitignored. They are working files on the machine doing the
ingestion. The ledger keeps the source hash, so provenance survives without the text.

## Running it

```bash
# a directory of PDFs and a list of URLs, one run, thousands of sources
python scripts/blog_ingest.py ingest \
    --pdf-dir ~/sources/conversations \
    --url-file ~/sources/urls.txt \
    --category Conversations --article-class ARCHIVE_DERIVED --workers 8

# re-running is free: a source already in the ledger is skipped, not converted twice
python scripts/blog_ingest.py ingest --pdf-dir ~/sources/conversations

python scripts/blog_ingest.py status
python scripts/blog_ingest.py draft --out content/conversations/drafts/CONV-001-CONV-025.json --limit 25

# after editorial work
python scripts/blog_quality_v2.py validate --manifest content/conversations/batches/CONV-001-CONV-025.json
python scripts/blog_ledger.py verify
```

The admin page at `/workspace/seo/blog-studio` does the intake side: drop PDFs, add URLs,
pick one of the two categories, and export a **work order**. It computes each file's
SHA-256 in the browser, and `--work-order` re-checks that hash against the file on disk —
so selecting the wrong file is caught at ingestion rather than becoming permanent, wrong
provenance on a published article.

## The two categories

`Conversations` and `Gastronomy`. These are the two that exist on the live Wix site, and
`blog_quality_v2.CATEGORIES` is an enum rather than free text on purpose: the older admin
form used a `<datalist>`, where a typo silently creates a third category — and `/blog/`
serves whichever category sorts first alphabetically, so `Conversatons` would have taken
over the blog index.

Gastronomy records additionally carry the recipe structure its own gate enforces
(Ingredients heading, Method heading, an ingredient list, 450+ characters).

## What the pipeline will not do

It does not write the article, and it cannot mark one `READY_TO_PUBLISH`.

Section 29 of the standard asks for a PASS/FAIL on ORIGINAL EXPRESSION ("independently
Anew rather than cosmetically rewritten"), on VOICE, and on SUBSTANCE. Section 30 asks
whether an intelligent reader would feel the article was written because there was
something worth saying. No program can answer those, and one that stamped them would turn
the standard into a rubber stamp while reporting full compliance.

So mechanical checks only ever move a record **down**. A record that passes every
automated check lands on `EDITORIAL_QA`. Reaching `READY_TO_PUBLISH` requires a human to
have recorded the eleven human gates in the record's `gate` object. Section 32's rule that
only `READY_TO_PUBLISH` enters the Wix queue is therefore preserved rather than defeated.

## Publication is still gated, and still two-phase

Nothing in the ingestion pipeline publishes. The publish paths do that, and each requires an
explicit, separately authorised step:

- Conversations — `scripts/conversations_batch.py publish`, or the `publish` input on
  `.github/workflows/conversations-publish.yml`. `validate` and `audit` mutate nothing.
- Gastronomy — the `publish` input on `.github/workflows/gastronomy-content-gate.yml`.

Neither script writes to Wix itself. Both delegate to `scripts/wix_blog_migrate.py`, so
there is one publisher, one credential path and one `WIX_CREDENTIALS_DISABLED` kill switch.

`conversations_batch.py` adds what publishing continuously needs and a one-shot CLI does
not: it is idempotent by slug, so a re-run after a partial failure publishes only what is
missing; it reads every published post back off the live site and checks body, title, slug,
author, category, tags, SEO, public URL, publication freshness, Ricos validity, duplicates
and formatting corruption; and it checkpoints `PUBLISHED` then `VERIFIED` into
`ledger.json` after each chunk, so an interrupted run is resumable.

```bash
python scripts/conversations_batch.py validate --manifest content/conversations/batches/CONV-001.json
python scripts/conversations_batch.py publish  --manifest content/conversations/batches/CONV-001.json
python scripts/conversations_batch.py audit    --manifest content/conversations/batches/CONV-001.json
```

Manifest size is arbitrary. There is no editorial batch count for Conversations — Gastronomy's
contiguous 25 is its own rule — and Wix is fed in chunks of 20 because that is the API's bulk
limit, which is an internal detail rather than an editorial unit.

And because the public site is a static export (`output: 'export'` in `next.config.js`),
a published post is not visible until an Amplify build re-reads Wix. See
`.kiro/steering/lambda-snapstart-deploy.md` for the same two-phase shape on Lambda.
