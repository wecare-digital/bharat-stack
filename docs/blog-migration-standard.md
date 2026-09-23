# WECARE.DIGITAL blog migration standard

Wix Blog on the headless site is the content source of truth.

## Editorial reference

The approved **Integrity** article is the master reference for how existing posts
are upgraded. The rule is:

> Preserve the original distinction. Remove looseness. Strengthen rhythm.
> Sharpen wording. Add only the minimum structure needed to make the idea land.

Do not turn a short source post into a new essay. Do not introduce a new analogy,
framework, teaching, personal story, example, or conceptual claim unless the source
post itself supports it.

The approved Integrity flow begins:

> Once balance is distinguished, you do not need to rediscover it every time.

and closes:

> We can always choose it again.

That standard means the upgrade is primarily editing, cadence, paragraph structure,
and selective emphasis.

## Fixed publication rules

- Author: **Anew by WECARE.DIGITAL**
- Default category: **Conversations**
- Tags: **1-3** precise distinctions actually present in the article
- Preserve the original Wix Editor slug wherever practical
- Preserve the original first-published date
- Every post gets a unique, source-faithful SEO title and meta description
- Canonical frontend URL: `https://wecare.digital/post/[slug]/`
- No hero image
- No cover image
- No inline image
- No decorative migrated media
- Frontend typography: Inter; desktop body 20px / 1.4 line-height
- Publisher in structured data: WECARE.DIGITAL
- Visible editorial author: Anew by WECARE.DIGITAL

## Pipeline safety

`scripts/wix_blog_migrate.py` accepts only already-approved manifests.

Its default mode is validation-only. Creating drafts requires
`--mode draft`. Publishing requires the explicit `--mode publish`.

The script rejects media fields and Ricos image/gallery/GIF/video/audio nodes.
Wix bulk creation is chunked at 20 posts per request, matching the API limit.

The migration pipeline does **not** generate editorial copy. Editorial upgrades are
reviewed/generated upstream and passed to the script as an approved manifest. This
keeps "content generation" separate from "content publication" and prevents a batch
publisher from inventing or broadening an article during migration.
