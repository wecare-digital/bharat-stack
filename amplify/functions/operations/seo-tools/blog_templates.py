"""Content templates, versioned, and immutable once an article has published against one.

WHY A VERSION NUMBER AND NOT JUST A TEMPLATE.

A template is the structural contract an article was written and certified against: which
sections, in what order, which of them are required, and what word band the whole thing sits
in. The quality gate reads it, a QA run records its verdict against it, and a human signs off
having seen that verdict.

If a template could be edited in place, every one of those records would silently start
referring to a document that no longer says what it said. An article certified as "complies
with the Conversations template" would, after one edit, be certified against something nobody
checked it against - and the record would look identical. That is not a theoretical failure
mode; it is the ordinary consequence of someone tightening a word band six months later.

So: an article records `templateId` AND `templateVersion`, and a version that any published
article was written against cannot be modified. Editing it produces the next version.

## What IS allowed to change in place

A version nothing has published against yet. Drafting a template is iterative, and forcing a
new version for every typo would leave a family at v14 before its first real use, which makes
the version number meaningless as an audit trail. `locked()` decides, and it decides by
looking at actual articles rather than at a flag somebody has to remember to set.

That check scans the source partition, which is not cheap. It is on the right path anyway: a
template is edited by a human a handful of times, while a template is READ on every article.
The read is one `get_item`.

## What a template cannot do

It cannot make an article publishable. `decide_status` still requires the section 29 human
gates, and a template compliance failure can only hold a record back. Adding a rule to a
template is therefore always safe in the publishing direction - it can block, never release.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import storage

logger = logging.getLogger(__name__)

RECORD_TYPE = "blogTemplate"

#: A template that applies whatever the category. Spelled explicitly rather than as an empty
#: string, because "" reads as "nobody filled this in".
ANY_CATEGORY = "ANY"

MAX_NAME = 160
MAX_SECTIONS = 20
MAX_GUIDANCE = 2000

#: A version nothing has published against may be edited in place; this is what a caller sees
#: when it may not.
LOCKED_REASON = ("this version has published articles written against it, so editing it would "
                 "change what they were certified against; a new version was created instead")


def family_id(name_or_id: str) -> str:
    """The stable id shared by every version of a template.

    Derived from the name so a human can recognise it in a record, and idempotent so passing
    an existing family id back in returns it unchanged.
    """
    value = str(name_or_id or "").strip()
    if value.startswith("blogtpl_"):
        return re.sub(r"_v\d+$", "", value)
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60]
    if not slug:
        raise ValueError("a template name is required")
    return f"blogtpl_{slug}"


def version_id(template_id: str, version: int) -> str:
    if int(version) < 1:
        raise ValueError("version starts at 1")
    return f"{family_id(template_id)}_v{int(version)}"


# ── Validation ──────────────────────────────────────────────────────────────────

def _clean_sections(raw: Any) -> List[Dict[str, Any]]:
    """The ordered section contract.

    `order` is the list position rather than a field the caller supplies, because two sections
    claiming order 3 is a conflict with no correct resolution, and a list already expresses
    order unambiguously.
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError("sections must be a non-empty array")
    if len(raw) > MAX_SECTIONS:
        raise ValueError(f"at most {MAX_SECTIONS} sections")
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"sections[{index}] must be an object")
        key = str(entry.get("key") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", key or ""):
            raise ValueError(f"sections[{index}].key must be a short lowercase identifier")
        if key in seen:
            raise ValueError(f"sections[{index}].key {key!r} is used twice")
        seen.add(key)
        heading = str(entry.get("heading") or "").strip()
        min_words = int(entry.get("minWords") or 0)
        max_words = int(entry.get("maxWords") or 0)
        if min_words < 0 or max_words < 0:
            raise ValueError(f"sections[{index}] word bounds cannot be negative")
        if max_words and min_words > max_words:
            raise ValueError(f"sections[{index}].minWords exceeds maxWords")
        out.append({
            "key": key,
            "order": index,
            "heading": heading,
            "required": bool(entry.get("required", True)),
            #: A heading is OPTIONAL even for a required section. The standard's shortest
            #: article type is a single unbroken movement of thought, and forcing a `##` onto
            #: it produces the mechanical shape section 13 is trying to prevent.
            "headingRequired": bool(entry.get("headingRequired", False)),
            "minWords": min_words,
            "maxWords": max_words,
            "guidance": str(entry.get("guidance") or "")[:MAX_GUIDANCE],
        })
    return out


def _validate(body: Dict[str, Any], categories: Sequence[str],
              article_classes: Sequence[str]) -> Dict[str, Any]:
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > MAX_NAME:
        raise ValueError(f"name must be at most {MAX_NAME} characters")

    category = str(body.get("category") or ANY_CATEGORY).strip()
    if category != ANY_CATEGORY and category not in categories:
        raise ValueError(
            f"category must be {ANY_CATEGORY} or one of {list(categories)}")

    article_class = str(body.get("articleClass") or "").strip().upper()
    if article_class and article_class not in article_classes:
        raise ValueError(f"articleClass must be empty or one of {list(article_classes)}")

    min_words = int(body.get("minWords") or 0)
    max_words = int(body.get("maxWords") or 0)
    if min_words < 0 or max_words < 0:
        raise ValueError("word bounds cannot be negative")
    if max_words and min_words > max_words:
        raise ValueError("minWords exceeds maxWords")

    sections = _clean_sections(body.get("sections"))
    section_min = sum(section["minWords"] for section in sections)
    if max_words and section_min > max_words:
        #: Refused rather than warned. A template whose required sections cannot fit inside
        #: its own word band makes every article that follows it fail, and the failure would
        #: read as an article defect rather than a template defect.
        raise ValueError(
            f"the sections require at least {section_min} words, which exceeds the "
            f"template's own maximum of {max_words}")

    return {
        "name": name,
        "description": str(body.get("description") or "")[:MAX_GUIDANCE],
        "category": category,
        "articleClass": article_class,
        "minWords": min_words,
        "maxWords": max_words,
        "sections": sections,
        #: Phrases this template forbids ON TOP OF the standard's own list. Additive: a
        #: template can tighten, never loosen, which is what makes adding one safe.
        "forbiddenPhrases": [str(item).strip().lower()
                             for item in (body.get("forbiddenPhrases") or [])
                             if str(item).strip()][:40],
        "requireList": bool(body.get("requireList", False)),
        "notes": str(body.get("notes") or "")[:MAX_GUIDANCE],
    }


# ── Records ─────────────────────────────────────────────────────────────────────

def get(record_id: str) -> Optional[Dict[str, Any]]:
    item = storage.table().get_item(Key={"id": str(record_id)}).get("Item")
    if not item or item.get("recordType") != RECORD_TYPE:
        return None
    return storage._json_safe(item)


def resolve(template_id: str, version: Any = 0) -> Optional[Dict[str, Any]]:
    """A specific version, or the newest when none is named.

    An article resolves the version it RECORDED, always. Resolving "latest" for an existing
    article is what this whole module exists to prevent, so the caller has to pass the number
    it stored and only a new article gets the newest.
    """
    if not str(template_id or "").strip():
        return None
    if int(version or 0) > 0:
        return get(version_id(template_id, int(version)))
    versions = history(template_id)
    return versions[0] if versions else None


def history(template_id: str) -> List[Dict[str, Any]]:
    """Every version of a family, newest first, through the slug index."""
    family = family_id(template_id)
    rows = [row for row in storage.list_slug_records(family)
            if row.get("recordType") == RECORD_TYPE]
    rows.sort(key=lambda row: int(row.get("version") or 0), reverse=True)
    return [storage._json_safe(row) for row in rows]


def list_templates(include_deprecated: bool = False) -> List[Dict[str, Any]]:
    """The newest version of each family."""
    rows = storage.scan_by_record_type(RECORD_TYPE)
    newest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        family = str(row.get("templateId") or "")
        held = newest.get(family)
        if not held or int(row.get("version") or 0) > int(held.get("version") or 0):
            newest[family] = row
    out = [_view(row) for row in newest.values()
           if include_deprecated or not row.get("deprecatedAt")]
    out.sort(key=lambda row: row["name"].lower())
    return out


def _view(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recordId": item.get("id", ""),
        "templateId": item.get("templateId", ""),
        "version": int(item.get("version") or 0),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "category": item.get("category", ""),
        "articleClass": item.get("articleClass", ""),
        "minWords": int(item.get("minWords") or 0),
        "maxWords": int(item.get("maxWords") or 0),
        "sections": item.get("sections", []) or [],
        "forbiddenPhrases": item.get("forbiddenPhrases", []) or [],
        "requireList": bool(item.get("requireList")),
        "notes": item.get("notes", ""),
        "createdBy": item.get("createdBy", ""),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "deprecatedAt": item.get("deprecatedAt", ""),
    }


def view(item: Dict[str, Any]) -> Dict[str, Any]:
    return _view(item)


# ── Locking ─────────────────────────────────────────────────────────────────────

def published_against(template_id: str, version: int) -> List[str]:
    """Source ids of PUBLISHED articles written to this exact version.

    Derived by reading the records rather than from a `useCount` on the template, for the same
    reason every other total in this system is: a counter and the rows it counts disagree at
    exactly the moment they must agree, and a template wrongly believed unused is one whose
    edit rewrites history.
    """
    import blog_sources
    family = family_id(template_id)
    out: List[str] = []
    for row in storage.scan_by_record_type(blog_sources.RECORD_TYPE):
        pipeline = row.get("pipeline") or {}
        if str(pipeline.get("templateId") or "") != family:
            continue
        if int(pipeline.get("templateVersion") or 0) != int(version):
            continue
        if str(pipeline.get("publishStatus") or "").upper() in {"PUBLISHED", "VERIFIED"}:
            out.append(str(row.get("id") or ""))
    return out


def locked(template_id: str, version: int) -> bool:
    return bool(published_against(template_id, version))


# ── Save ────────────────────────────────────────────────────────────────────────

def save(body: Dict[str, Any], actor: str, categories: Sequence[str],
         article_classes: Sequence[str]) -> Dict[str, Any]:
    """Create a template, edit an unlocked version in place, or fork a locked one.

    Three cases, and the caller does not have to know which applies - it says what the
    template should say and this decides whether that is a mutation or a new version. The
    response reports which happened and why, because "I edited v2" and "I created v3" are
    different facts and an operator must not have to guess.
    """
    fields = _validate(body, categories, article_classes)
    family = family_id(str(body.get("templateId") or fields["name"]))
    versions = history(family)
    requested = int(body.get("version") or 0)

    target: Optional[Dict[str, Any]] = None
    if requested:
        target = next((row for row in versions
                       if int(row.get("version") or 0) == requested), None)
        if not target:
            raise LookupError(f"template {family} has no version {requested}")
    elif versions:
        target = versions[0]

    now = storage.now_iso()
    if target is not None and not locked(family, int(target["version"])):
        storage.put_record({**target, **fields, "updatedAt": now, "updatedBy": actor})
        logger.info(json.dumps({
            "event": "blog_template_updated", "templateId": family,
            "version": int(target["version"]), "actor": actor}))
        return {**_view({**target, **fields, "updatedAt": now}),
                "created": False, "reason": "no published article uses this version"}

    version = (int(versions[0]["version"]) + 1) if versions else 1
    record = {
        "id": version_id(family, version),
        "recordType": RECORD_TYPE,
        "createdAt": now,
        "updatedAt": now,
        #: The FAMILY id, so `list_slug_records` returns the whole version history in one
        #: query - the same trick the analysis records use with their source id.
        "slug": family,
        "templateId": family,
        "version": version,
        "createdBy": actor,
        "updatedBy": actor,
        "deprecatedAt": "",
        **fields,
    }
    storage.put_record(record)
    logger.info(json.dumps({
        "event": "blog_template_created", "templateId": family, "version": version,
        "actor": actor, "forkedFrom": int(target["version"]) if target else 0}))
    return {**_view(record), "created": True,
            "reason": LOCKED_REASON if target is not None else "new template"}


def deprecate(record_id: str, actor: str) -> Dict[str, Any]:
    """Stop a version being offered for new articles without deleting it.

    Never a delete. A published article points at the version it was certified against, and
    removing it would leave that certification dangling - which is the same failure as editing
    it, arrived at from the other direction.
    """
    record = get(record_id)
    if not record:
        raise LookupError("Unknown template version")
    now = storage.now_iso()
    storage.table().update_item(
        Key={"id": record_id},
        UpdateExpression="SET deprecatedAt = :d, updatedAt = :u, updatedBy = :by",
        ExpressionAttributeValues={":d": now, ":u": now, ":by": actor},
    )
    return {**_view({**record, "deprecatedAt": now}), "deprecated": True}


# ── Compliance ──────────────────────────────────────────────────────────────────

def _headings(body: str) -> List[str]:
    return [line.lstrip("# ").strip()
            for line in str(body or "").splitlines() if line.strip().startswith("##")]


def check_article(record: Dict[str, Any], template: Dict[str, Any], q) -> List[Any]:
    """Template compliance as `blog_quality_v2.Finding` objects.

    Returns the gate's own type rather than a bespoke shape, so a template failure routes
    through the same status machinery as every other finding and needs no special case in
    `decide_status`. Everything here is REVIEW rather than BLOCK: a template is a house style,
    and a house-style miss is a rewrite instruction, not a reason to declare the article
    structurally invalid.
    """
    if not template:
        return []
    out: List[Any] = []
    body = q.body_of(record)
    words = q.word_count(body)
    headings = [heading.lower() for heading in _headings(body)]

    minimum = int(template.get("minWords") or 0)
    maximum = int(template.get("maxWords") or 0)
    if minimum and words < minimum:
        out.append(q.Finding("7", "TEMPLATE_BELOW_BAND", "REVIEW",
                             f"{words} words is below the {template.get('name')!r} template's "
                             f"minimum of {minimum}", "EDITORIAL_REWRITE"))
    if maximum and words > maximum:
        out.append(q.Finding("7", "TEMPLATE_ABOVE_BAND", "REVIEW",
                             f"{words} words exceeds the {template.get('name')!r} template's "
                             f"maximum of {maximum}", "EDITORIAL_REWRITE"))

    #: Section order is checked on the headings that ARE present, in the order they appear.
    #: A missing optional section must not make the ones after it read as out of order, which
    #: is why this compares a filtered subsequence rather than index positions.
    expected_order: List[str] = []
    for section in sorted(template.get("sections") or [],
                          key=lambda item: int(item.get("order") or 0)):
        heading = str(section.get("heading") or "").strip().lower()
        present = bool(heading) and heading in headings
        if section.get("required") and section.get("headingRequired") and not present:
            out.append(q.Finding("7", "TEMPLATE_SECTION_MISSING", "REVIEW",
                                 f"the template requires a {section.get('heading')!r} section",
                                 "EDITORIAL_REWRITE"))
        if present:
            expected_order.append(heading)
    actual_order = [heading for heading in headings if heading in set(expected_order)]
    if actual_order != expected_order:
        out.append(q.Finding("7", "TEMPLATE_SECTION_ORDER", "REVIEW",
                             f"template sections appear as {actual_order} but the template "
                             f"orders them {expected_order}", "EDITORIAL_REWRITE"))

    lowered = body.lower()
    for phrase in template.get("forbiddenPhrases") or []:
        if phrase and phrase in lowered:
            out.append(q.Finding("7", "TEMPLATE_FORBIDDEN_PHRASE", "REVIEW",
                                 f"the template forbids {phrase!r}", "EDITORIAL_REWRITE"))
    if template.get("requireList") and not q.has_list(body):
        out.append(q.Finding("7", "TEMPLATE_LIST_REQUIRED", "REVIEW",
                             "the template requires at least one list", "EDITORIAL_REWRITE"))
    return out


def compliance(record: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
    """A reportable summary of `check_article`, for a QA run and for the UI."""
    import blog_quality_v2 as q
    findings = check_article(record, template, q)
    return {
        "templateId": str(template.get("templateId") or "") if template else "",
        "templateVersion": int(template.get("version") or 0) if template else 0,
        "templateName": str(template.get("name") or "") if template else "",
        "checked": bool(template),
        "findings": [str(finding) for finding in findings],
        "compliant": bool(template) and not findings,
    }


def assign(source_id: str, template_id: str, version: Any, actor: str) -> Dict[str, Any]:
    """Record which template version an article is being written to.

    The version is RESOLVED AND STORED NOW rather than left as "the latest". An article that
    recorded only a family id would be re-checked against whatever the template later became,
    which is the exact substitution this module exists to prevent.
    """
    import blog_sources
    record = blog_sources.get_source(source_id)
    if not record:
        raise LookupError("Unknown sourceId")
    template = resolve(template_id, version)
    if not template:
        raise LookupError(f"Unknown template {template_id!r}")
    if template.get("deprecatedAt") and not int(version or 0):
        raise ValueError(
            f"the newest version of {template['name']!r} is deprecated; name a version "
            f"explicitly if you intend to use it")

    category = str(record.get("category") or "")
    if template["category"] != ANY_CATEGORY and template["category"] != category:
        raise ValueError(
            f"template {template['name']!r} is for {template['category']} and this source is "
            f"{category or 'uncategorised'}")

    pipeline = blog_sources.update_pipeline(
        source_id, templateId=template["templateId"],
        templateVersion=int(template["version"]))
    logger.info(json.dumps({
        "event": "blog_template_assigned", "sourceId": source_id,
        "templateId": template["templateId"], "version": int(template["version"]),
        "actor": actor}))
    return {"sourceId": source_id, "templateId": template["templateId"],
            "templateVersion": int(template["version"]),
            "templateName": template["name"], "pipeline": pipeline}


def for_source(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The exact template version an article recorded, or None.

    Falls back to the batch default only when the source has none of its own, and stores
    nothing - resolving is a read. A source that has never been assigned a template is
    checked against no template rather than against a guess.
    """
    pipeline = record.get("pipeline") or {}
    template_ref = str(pipeline.get("templateId") or "")
    version = int(pipeline.get("templateVersion") or 0)
    if template_ref and version:
        return resolve(template_ref, version)
    batch_ref = str(record.get("batchId") or "")
    if batch_ref and batch_ref != "unbatched":
        import blog_batches
        batch = blog_batches.get(batch_ref) or {}
        if batch.get("defaultTemplateId"):
            return resolve(str(batch["defaultTemplateId"]),
                           int(batch.get("defaultTemplateVersion") or 0))
    return None


def template_fields() -> Tuple[str, ...]:
    """The view keys, so a test can assert the shape has not quietly shrunk."""
    return ("recordId", "templateId", "version", "name", "description", "category",
            "articleClass", "minWords", "maxWords", "sections", "forbiddenPhrases",
            "requireList", "notes", "createdBy", "createdAt", "updatedAt", "deprecatedAt")
