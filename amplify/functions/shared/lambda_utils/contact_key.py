"""The Contact identifier contract. One physical key, one enforced alias.

Measured, not assumed
---------------------
`stack-wecare-digital-ContactsTable`, read live on 2026-09-22:

    KeySchema            id (HASH)      single partition key, no sort key
    AttributeDefinitions bsuid, email, id, phone
    GSIs                 bsuid-index, email-index, phone-index
    Items                13
    id == contactId      13 of 13       zero divergence, zero missing, zero empty

And in source: **20 files** access the table, every one of them with
`Key={'id': ...}`. There is not a single `Key={'contactId': ...}` anywhere.

So the brief's framing - that runtime wrongly uses `id` while the contract is
`contactId` - is the wrong way round. `id` **is** the deployed key and the runtime is
correct. What is actually wrong is subtler and worth naming precisely.

The real defect
---------------
Every row stores the identifier **twice**, as `id` and as `contactId`, and nothing
enforces that they agree. They agree today by habit, not by constraint.

That matters because readers mix the two. `rcs-dlr._lookup_contact_by_phone` and
`rcs-send._lookup_contact_by_phone` both query `phone-index` and then return
``items[0].get('contactId', '')``. That value flows into `put_message(contact_id=...)`
and onward into code that uses it as a **key**. The moment one writer sets `contactId`
to something other than `id` - a migration, a bulk import, a hand edit in the console -
those readers start producing a key that resolves to nothing, and the failure is silent:
a message stored against a contact that cannot be looked up.

The Amplify model in `amplify/data/resource.ts` declares `contactId` as the identifier,
which is a third version of the truth and matches neither the table nor the code.

The decision
------------
**`id` is the canonical physical key.** It is what the live table uses, what all 20
callers use, and what 3 GSIs are defined against. Repointing a live table's partition
key would mean recreating the table and its indexes to gain nothing.

`contactId` stays, because 13 rows carry it and readers depend on it, but it is demoted
to an **alias that this module guarantees** rather than a duplicate that happens to
match. Writers go through `contact_item_keys`, readers through `resolve`, and
`assert_consistent` is the invariant a test can assert against real rows.

Why not simply delete the `contactId` attribute
-----------------------------------------------
Because deleting it silently breaks the two `_lookup_contact_by_phone` readers, and
because the API and the frontend both speak `contactId` outward. Removing it is a
separate, wider change; making it trustworthy is this one.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

#: The DynamoDB partition key. Confirmed against the deployed table.
PHYSICAL_KEY = "id"

#: The alias every row also carries, and which the outward API speaks.
ALIAS_KEY = "contactId"


class ContactKeyMismatch(ValueError):
    """A row carries `id` and `contactId` with different values.

    A distinct type because the correct response is not "pick one": it means a writer
    has broken the invariant and any key derived from that row is untrustworthy.
    """


def resolve(source: Optional[Mapping[str, Any]] = None, *,
            contact_id: Optional[str] = None) -> str:
    """The contact's canonical id, from a row or from a loose value.

    Accepts either spelling and prefers `id`, because `id` is the physical key: if the
    two disagree, the one that can actually be used for a `get_item` is the right answer.
    Returns `''` when there is nothing usable, so callers can test falsiness rather than
    catching.
    """
    if contact_id:
        value = str(contact_id).strip()
        if value:
            return value

    if not source:
        return ""

    for field in (PHYSICAL_KEY, ALIAS_KEY):
        value = source.get(field)
        if value:
            text = str(value).strip()
            if text:
                return text
    return ""


def assert_consistent(item: Mapping[str, Any]) -> None:
    """Raise `ContactKeyMismatch` when a row's two identifiers disagree.

    Absence is tolerated - a row may legitimately carry only `id`, and a projection may
    return only one field. Only a genuine *conflict* is an error, because that is the
    state no reader can resolve safely.
    """
    primary = item.get(PHYSICAL_KEY)
    alias = item.get(ALIAS_KEY)
    if not primary or not alias:
        return
    if str(primary).strip() != str(alias).strip():
        # Deliberately does not echo either value: this message reaches logs, and a
        # contact id is a customer reference.
        raise ContactKeyMismatch(
            f"contact row has {PHYSICAL_KEY} and {ALIAS_KEY} set to different values "
            f"(lengths {len(str(primary))} and {len(str(alias))}); "
            "any key derived from this row is untrustworthy")


def key(contact_id: str) -> Dict[str, str]:
    """The DynamoDB `Key=` argument for a contact.

    Exists so no new call site has to know which spelling is the physical key, and so
    that a future change of key is one edit rather than twenty.
    """
    value = str(contact_id or "").strip()
    if not value:
        raise ValueError("contact id is required to build a key")
    return {PHYSICAL_KEY: value}


def contact_item_keys(contact_id: str) -> Dict[str, str]:
    """Both identifier fields for a row being written, guaranteed equal.

    Every writer should spread this into its item rather than setting either field by
    hand. That is what turns the alias from a coincidence into an invariant.
    """
    value = str(contact_id or "").strip()
    if not value:
        raise ValueError("contact id is required")
    return {PHYSICAL_KEY: value, ALIAS_KEY: value}


def normalize_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the row with both identifiers present and equal.

    Repairs a row that carries only one spelling, which is what lets a reader treat any
    row uniformly. Raises on a genuine conflict rather than silently choosing.
    """
    assert_consistent(item)
    out = dict(item)
    resolved = resolve(out)
    if resolved:
        out[PHYSICAL_KEY] = resolved
        out[ALIAS_KEY] = resolved
    return out


def describe(item: Mapping[str, Any]) -> Tuple[bool, str]:
    """`(consistent, reason)` for diagnostics. Never includes an id value."""
    primary, alias = item.get(PHYSICAL_KEY), item.get(ALIAS_KEY)
    if not primary and not alias:
        return False, "no identifier on the row"
    if primary and not alias:
        return True, f"{PHYSICAL_KEY} only"
    if alias and not primary:
        return True, f"{ALIAS_KEY} only (not usable as a key without resolution)"
    if str(primary).strip() == str(alias).strip():
        return True, "both present and equal"
    return False, f"{PHYSICAL_KEY} and {ALIAS_KEY} disagree"
