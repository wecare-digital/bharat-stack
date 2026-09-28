# Gastronomy Publishing Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable 25-post Gastronomy batch pipeline that validates prepared article packages, publishes only missing Wix posts, audits the live backend representation, records progress in Git, and updates `stack` only after a whole batch is complete.

**Architecture:** Keep editorial generation outside CI and store only approved original article packages in Git. A dedicated Python batch tool validates the package, compiles Markdown to Ricos, performs idempotent Wix publication, and audits the live backend through `wecare-seo-tools`; GitHub Actions runs validation on the working branch and allows an explicitly approved publish run. The `gastronomy-publishing` branch accumulates batch state without triggering Amplify; `stack` is updated once per completed batch so Amplify builds once.

**Tech Stack:** Python 3.12, Wix REST API, AWS Secrets Manager/Lambda, GitHub Actions, AWS Amplify Hosting.

**Spec:** `docs/superpowers/specs/2026-09-28-gastronomy-publishing-automation-design.md`

## Global Constraints

- Batch size is exactly 25 posts.
- Author is exactly `Anew by WECARE.DIGITAL`.
- Category is exactly `Gastronomy`.
- Each post has 1-3 tags.
- Literal `\\n`, literal Markdown headings inside Ricos text, and malformed list serialization are blocking errors.
- Publication is idempotent: existing target slugs are skipped, never duplicated.
- No article image by default.
- A batch does not update `stack` until package validation, Wix publication, and live backend audit all pass.
- The source PDF is not committed.

## Review Focus

- A JSON string containing literal `\\n` instead of real line breaks must fail before a Wix mutation.
- Duplicate IDs, slugs, titles, or non-contiguous batch IDs must fail validation.
- A partially published batch must resume by publishing only missing slugs.
- A published post whose backend Ricos lacks Ingredients/Method/list structure must fail the live audit.
- The final progress state must never advance beyond the highest fully audited batch.

---

### Task 1: Batch package validator and Ricos compiler

**Files:**
- Create: `scripts/gastronomy_batch.py`
- Create: `tests/test_gastronomy_batch.py`

**Interfaces:**
- Produces: `validate_batch_document(document: dict) -> list[str]`
- Produces: `markdown_to_rich_content(markdown: str) -> dict`
- Produces: CLI `python scripts/gastronomy_batch.py validate --manifest <path>`

- [ ] Write failing tests for a valid 25-post batch, literal escaped newlines, duplicate slugs, non-contiguous IDs, missing Ingredients/Method, wrong category/author, tag count, canonical mismatch, and Ricos headings/list output.
- [ ] Run focused tests and verify they fail because `scripts/gastronomy_batch.py` does not exist.
- [ ] Implement the minimal validator/compiler.
- [ ] Run focused tests and verify all pass.
- [ ] Commit.

### Task 2: Idempotent Wix publication and live audit

**Files:**
- Modify: `scripts/gastronomy_batch.py`
- Modify: `tests/test_gastronomy_batch.py`

**Interfaces:**
- Produces: `pending_posts(document, existing_slugs) -> list[dict]`
- Produces: `audit_public_post(post: dict, expected: dict) -> list[str]`
- Produces: CLI `publish --manifest <path>` and `audit --manifest <path>`

- [ ] Add failing tests proving existing slugs are skipped and malformed live Ricos fails audit.
- [ ] Run focused tests and verify red.
- [ ] Implement Wix request/auth, category/tag resolution, publish in chunks of <=20, and Lambda-backed live audit.
- [ ] Run focused tests and full existing `tests/test_wix_blog_migrate.py`.
- [ ] Commit.

### Task 3: Durable progress state and CI gate

**Files:**
- Create: `content/gastronomy/progress.json`
- Create: `content/gastronomy/README.md`
- Create: `.github/workflows/gastronomy-content-gate.yml`
- Modify: `tests/test_gastronomy_batch.py`

**Interfaces:**
- Progress schema: `completed_through`, `next_id`, `batch_size`, `total`, `last_batch`.
- Workflow validates every committed batch manifest on PR/push to `gastronomy-publishing`; explicit workflow dispatch may publish one manifest after AWS credential setup.

- [ ] Add failing tests for the initial 40/340 progress state and invalid progress advances.
- [ ] Run focused tests and verify red.
- [ ] Implement progress validation and initial state.
- [ ] Add CI workflow using the existing GitHub AWS OIDC pattern and a dedicated publish gate.
- [ ] Run focused tests.
- [ ] Commit.

### Task 4: First automated batch handoff

**Files:**
- Create: `content/gastronomy/batches/GAST-041-GAST-065.json` after the source/editorial work is complete.
- Modify: `content/gastronomy/progress.json` only after publish + audit pass.

**Interfaces:**
- Consumes Task 1-3 CLI and progress state.
- Produces one completed 25-post transaction and one production `stack` refresh.

- [ ] Read source pages for GAST-041-GAST-065 and run duplicate checks against Wix.
- [ ] Generate and commit 25 complete article packages.
- [ ] Validate package.
- [ ] Publish only missing posts.
- [ ] Audit all 25 through the public-blog backend.
- [ ] Advance progress to 65 and commit.
- [ ] Update `stack` once and verify Amplify BUILD/DEPLOY/VERIFY succeed.
