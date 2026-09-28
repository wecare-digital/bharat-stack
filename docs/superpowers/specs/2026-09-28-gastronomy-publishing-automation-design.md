# Gastronomy Publishing Automation Design

## Goal

Automate the remaining WECARE.DIGITAL Gastronomy programme from GAST-041 through GAST-340 in fixed 25-post batches while preserving editorial quality, preventing duplicate Wix posts, preventing malformed Ricos content, and causing only one production Amplify refresh per completed batch.

## Current baseline

- GAST-001 through GAST-040 are published in the Wix Headless site.
- The first 40 have been audited through Wix and through the public-blog backend: 40/40 structurally clean, with Gastronomy category, Anew by WECARE.DIGITAL author, 1-3 tags, SEO metadata, Ingredients and Method headings, and ingredient lists.
- Amplify production job 995 completed BUILD, DEPLOY and VERIFY successfully after the Batch 004 formatting repair.
- The Amplify app is connected to the `stack` branch. Work on `gastronomy-publishing` must not update `stack` until a whole batch is ready.

## Batch model

- Batch size: 25 posts.
- Remaining count: 300 posts.
- Remaining batches: 12.
- First automated batch: GAST-041 through GAST-065.
- Final automated batch: GAST-316 through GAST-340.
- Exactly one batch is processed per automation run.

## Git layout

- `content/gastronomy/progress.json` is the durable state machine.
- `content/gastronomy/batches/GAST-XXX-GAST-YYY.json` stores the complete publish package for one batch.
- `scripts/validate_gastronomy_batch.py` validates the committed package before any Wix write.
- `scripts/audit_gastronomy_live.py` validates the published backend representation after Wix write.
- `.github/workflows/gastronomy-content-gate.yml` runs tests and package validation on the working branch and on pull requests.

The source PDF itself is not committed to Git. Batch files contain only original WECARE.DIGITAL article packages and source-page references.

## Post package contract

Each post has:

- sequential `id` such as `GAST-041`
- unique `title`
- unique `slug`
- `author` exactly `Anew by WECARE.DIGITAL`
- `category` exactly `Gastronomy`
- 1-3 precise `tags`
- `seo_title`
- `meta_description`
- `canonical` equal to `https://wecare.digital/post/<slug>/`
- `source_ref` describing the cookbook page/section used
- `body_markdown` with real newline characters, H2 Ingredients and Method headings, a real Markdown ingredient list, and original editorial prose
- `image_status` equal to `none` unless a later explicit instruction changes the text-first policy

Literal escaped newline sequences such as `\\n` are forbidden in `body_markdown`.

## Editorial and source rules

- The source PDF remains the factual/source basis.
- Do not copy long passages from the cookbook.
- Do not fabricate quotes.
- Recipe facts may be preserved, but prose and explanation are original WECARE.DIGITAL language.
- Strong Ayurvedic or medical claims are either framed as traditional/source context or omitted unless independently verified.
- No article image by default.
- Duplicate title/slug checks against Wix occur before publishing.
- A batch is not complete merely because files were generated.

## Batch transaction

A batch completes only in this order:

1. Read the source pages in context.
2. Check all 25 proposed titles and slugs against Wix.
3. Generate all 25 complete post packages.
4. Commit the batch package to `gastronomy-publishing`.
5. Run the static package validator.
6. Publish only missing posts to Wix under Gastronomy.
7. Audit all 25 through the public-blog backend.
8. Update `progress.json` to mark the batch complete.
9. Commit the state update to `gastronomy-publishing`.
10. Update `stack` exactly once for the completed batch.
11. Wait for the resulting Amplify production build and verify BUILD, DEPLOY and VERIFY all succeed.
12. Only then may the next batch begin.

If any gate fails, stop the batch before updating `stack`. On the next run, reconcile Git, Wix and progress state and resume only missing work.

## Public deployment rule

Amplify remains connected to `stack`. The working branch is not an Amplify deployment branch. This is intentional: multiple content commits can accumulate without production builds, then one update to `stack` creates one production refresh.

## Completion

When `completed_through` reaches 340, the automation performs no more writes and reports the programme complete.
