# Conversations deep audit — 2026-10-02

## Scope
Audit of the 332 PASS_TO_RECONSTRUCTION population, the 7-batch assignment of the remaining 324 sources, current Wix Conversations integrity, and Git/Wix publication-state consistency.

## Source-assignment reconciliation
Authoritative 478-source QA CSV:
- total exception rows: 478
- PASS_TO_RECONSTRUCTION: 332
- already handled before the 7-batch plan: 8
- expected remaining: 324

Seven batch checkpoints:
- Batch 001: 50
- Batch 002: 50
- Batch 003: 50
- Batch 004: 50
- Batch 005: 50
- Batch 006: 50
- Batch 007: 24
- total assigned: 324
- unique assigned: 324
- missing: 0
- duplicates: 0
- extras: 0

QA route reconciliation for the 324:
- ATTRIBUTION_AWARE_RECONSTRUCTION: 232
- PRIVACY_SAFE_RECONSTRUCTION: 72
- FACT_SAFE_RECONSTRUCTION: 20

These totals match the authoritative QA CSV exactly after subtracting the 8 previously handled sources.

## Current Wix integrity
Fresh read-back:
- live Conversations posts: 869
- duplicate slugs: 0
- duplicate titles: 0
- blank rich-content bodies: 0

The two directly published approved posts are live exactly once:
- `what-is-true-and-what-we-believe-about-it-are-different`
- `hear-the-story-without-turning-the-person-into-the-story`

Their titles, slugs, category, author member, and rich-content bodies match the approved records.

## Audit defects / follow-up required

### 1. Git publication state is stale for the two direct-Wix publishes
`content/conversations/batches/CONV-332-001.json` still marks both posts `READY_TO_PUBLISH`.
`content/conversations/ledger.json` still has count 42 and does not include these two October 2 live posts.

This is a state-reconciliation defect, not a Wix publication failure.

### 2. Wix tag representation differs from the batch manifest
The two new posts have the requested values in Wix `hashtags`, but `tagIds` is empty.
If repository/publication policy requires Wix Blog tags rather than hashtags, tag creation/assignment remains to be reconciled.

### 3. SEO read-back is unresolved
The current posts-query read-back returns `seoData: null` and no public URL field for the two direct-Wix posts.
This query result is insufficient to certify that the requested custom SEO title/meta/canonical persisted. A method-specific SEO/get-post verification is still required before claiming SEO read-back PASS.

### 4. Batch 007 checkpoint contains one cross-batch note contamination
`CONV-324-BATCH-007-20261002.md` mentions `wouldyou.html` / “Would You Rather Be Right Or Happy?” as an exact title collision, but that source belongs to Batch 006.
The Batch 007 source assignment itself is correct; only the note is contaminated.

### 5. The 7 batches are scoped/screened, not completed
All 324 sources have been assigned and fresh title-collision screened, but the following are not yet complete for the 324:
- full body-level dedupe against live article bodies
- source clustering/combination decisions
- independent draft reconstruction for surviving article opportunities
- article-level Model QA
- human/editorial gates
- publication and live read-back

Therefore 324/324 assignment coverage must not be described as 324/324 final editorial completion.

## Verdict
No source record was missed in the 324-source batch assignment.
The remaining issues are state/metadata reconciliation and unfinished body-level editorial work, not source coverage loss.
