# Conversations archive triage

This directory documents the mechanical pre-editorial triage used for the remaining
Conversations archive.

The triage step exists to reduce repeated manual review. It is **not** an editorial
approval system and it must never set a record to `READY_TO_PUBLISH`.

## Inputs

The classifier consumes:

- the formal 1,952-source archive inventory;
- a pending-source CSV containing source file, title, date and archive index;
- the local/private `c4t2(1).zip` archive.

The archive itself is not committed to Git. Only metadata and finished Anew articles may
be committed.

## Mechanical buckets

- `LIKELY_EXISTING_COVERAGE` — strong prior merge/overlap signal. Requires a quick
  distinction-level confirmation against the live corpus before resolution.
- `DEDUPE_REVIEW` — moderate overlap signal. Requires body/distinction comparison.
- `CANDIDATE_NEW_ARTICLE` — title-pass suggests a distinct opportunity and no mechanical
  attribution/fact gate is present. Requires full source reading and human editorial gates.
- `ATTRIBUTION_REVIEW` — the article body depends on named source people/programs or
  explicit source scaffolding.
- `PERSONAL_REFERENCE_REWORK` — first-person/private biography plus named-person
  dependency requires removal, generalisation or justified attribution.
- `FACT_CHECK_REQUIRED` — the source inventory already requires research in a current or
  specialist factual domain.

Bucket precedence deliberately sends strong overlap to dedupe before other review signals;
a source that is already covered should not receive a new article merely because it also
contains attribution or factual risks.

## Guardrail

A machine bucket is only a routing decision.

No triage result may:

- write human gate PASS values;
- change a record to `READY_TO_PUBLISH`;
- publish to Wix;
- convert source wording cosmetically;
- remove required attribution to make copy appear original.

The existing `scripts/conversations_batch.py` remains the only Conversations orchestrator
in front of `scripts/wix_blog_migrate.py`.

## Current 1,212-source triage

Generated 2026-09-30 from pending positions 26–1237:

| Bucket | Count |
|---|---:|
| ATTRIBUTION_REVIEW | 467 |
| FACT_CHECK_REQUIRED | 315 |
| LIKELY_EXISTING_COVERAGE | 153 |
| CANDIDATE_NEW_ARTICLE | 116 |
| DEDUPE_REVIEW | 93 |
| PERSONAL_REFERENCE_REWORK | 68 |
| **Total** | **1,212** |

Recommended review order for speed without lowering standards:

1. confirm `LIKELY_EXISTING_COVERAGE` and close true duplicates;
2. review `CANDIDATE_NEW_ARTICLE` for genuine new Anew articles;
3. resolve `DEDUPE_REVIEW`;
4. process attribution/privacy and factual-review queues with their required specialist
   checks.

The full generated CSV is retained as the persistent control file in the WECARE.DIGITAL
working Library.
