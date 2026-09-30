# Gastronomy publishing state

This directory is the durable state for WECARE.DIGITAL Gastronomy publishing.

Current live Wix baseline: **454 published Gastronomy posts**. The historical Git sequence is verified through GAST-340; the 114 newer live posts must be reconciled to source IDs before assigning the next GAST sequence.

## Production model

- Editorial manifests may contain **1-150 posts**.
- 150 is a maximum production-unit size, not a content target.
- Never invent filler to reach 150.
- Wix mutations remain internally chunked to **20 posts per API request**.
- Publication is idempotent by slug: already-published slugs are skipped.
- New publishing/audit runs require **quality_version: 2**.
- Historical v1 manifests remain valid as repository history but cannot be newly published through the v2 gate.
- The working branch is **gastronomy-quality**.
- The GitHub workflow has a concurrency lock so only one Gastronomy Wix publishing run mutates the site at a time.

## Source-specific neutrality and privacy

The quality gate is deliberately **publisher-agnostic**.

Do not hard-code a single source such as Isha into permanent editorial policy.

Each newly supplied PDF, website, cookbook, publisher archive, or source collection must define a private source profile in its manifest:

```json
{
  "quality_version": 2,
  "source_profile": {
    "label": "Internal source label",
    "blocked_public_terms": [
      "Publisher Name",
      "Author Name",
      "Book Title",
      "Institution Name",
      "Private Person Name"
    ],
    "required_public_attribution_terms": []
  }
}
```

`source_profile` is created separately for every new PDF/source. It may include:

- `publisher_names`
- `author_names`
- `publication_titles`
- `institution_names`
- `private_person_names`
- `private_place_names`
- `provenance_phrases`
- additional `blocked_public_terms`
- `allowed_public_terms` for legitimate public culinary terms
- `required_public_attribution_terms` when attribution genuinely must remain

Do not carry one source profile forward blindly to the next PDF.

Normal culinary language is **not** a provenance violation by itself. Phrases such as `cooked with`, `learned from`, `volunteer`, `programme`, family, place, or institution terms should only be blocked when they actually expose the current source's private/provenance context.

`required_public_attribution_terms` is an exception list only for material whose attribution is genuinely necessary.

The final public article should read as independent editorial work by **Anew by WECARE.DIGITAL**, while retaining required attribution and genuine culinary/cultural identity.

## Generic public-language gate

Public title, slug, SEO, meta description and body are rejected when they contain reconstruction scaffolding such as:

- Source note
- Adapted from
- Independently written from
- The source
- Source recipe
- The cookbook
- In the cookbook
- The book says
- The author / author's
- Learned from
- Cooked with
- Market connection
- Unnecessary source institution or programme language

Possessive personal titles such as `Caroline's ...`, `Grandma's ...` or `Aunty ...` require an explicit `public_name_justification`; normally they should be generalized to the culinary identity.

Health-claim terms in titles/SEO such as `cure`, `detox`, `cleanse`, `heal`, `treat`, `prevent`, or `medicinal` require `health_claim_reviewed: true`.

## Article types

Set `article_type` on new records.

`RECIPE` requires semantic **Ingredients** and **Method** structure.

Non-recipe article types may include:

- `TECHNIQUE`
- `INGREDIENT`
- `CULINARY_ARTICLE`
- `CULINARY_DISTINCTION`
- `MENU_PAIRING`
- `CULINARY_CULTURE_HISTORY`

Non-recipe articles are not forced into artificial Ingredients/Method sections.

## Validation and publishing

Validate:

```bash
python scripts/gastronomy_batch.py validate --manifest <v2-manifest>
```

Publishing and live audit remain separate gates:

```bash
python scripts/gastronomy_batch.py publish --manifest <manifest>
python scripts/gastronomy_batch.py audit --manifest <manifest>
```

Publication requires a v2 manifest.

The audit checks live Wix output after publication, including source/privacy leakage and formatting corruption.

## Governing rule

**Keep culinary identity. Remove source scaffolding. Keep necessary attribution. Remove unnecessary personal provenance. Never invent WECARE.DIGITAL biography. Preserve recipe facts.**


## Future PDF workflow

For each newly uploaded or linked PDF:

1. Read and inventory the complete relevant source.
2. Create a new source profile for that PDF only.
3. Record publisher, author, publication title, institutions, personal names/places, and provenance phrases privately.
4. Preserve legitimate culinary geography and established food terminology through `allowed_public_terms`.
5. Prepare independent WECARE.DIGITAL articles.
6. Validate a manifest containing **1-150 articles**.
7. Publish only records that pass the source/privacy, attribution, metadata, structure, and safety gates.
8. Wix writes remain internally chunked at 20.
9. Read every published record back before treating it as verified.
10. Start a fresh source profile when the next PDF/publisher is supplied.

The quality gate targets source leakage, privacy/provenance, attribution, real content corruption, and relevant safety issues. It does **not** attempt to rewrite ordinary cooking prose simply for stylistic preference.
