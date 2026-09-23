"""Google People incremental sync: the sync-token lifecycle and person -> Contact mapping.

Pure. Builds request parameters, interprets responses, and maps a `Person` onto our Contact
fields. No network I/O, so the decisions are testable without credentials.

The sync-token contract, and the one way it always breaks
---------------------------------------------------------
`people.connections.list` supports incremental sync:

1. Full sync with `requestSyncToken=true` -> the last page carries `nextSyncToken`.
2. Later, pass that token as `syncToken` -> only what changed since.

The trap is step 3, which is not optional: **a sync token expires, and Google signals that
with HTTP 410 GONE**. The documented response is to discard the token and run a full sync.
Code that treats 410 as a generic error instead retries forever and the sync silently stops
advancing - the integration looks healthy, no contact has changed for weeks, and nobody
notices because there is no error to see.

`interpret_error` classifies 410 as `EXPIRED_SYNC_TOKEN` with `must_full_sync=True`, and
`next_request_params` refuses to send a token it has been told is expired.

Two further rules that are easy to miss:

* A sync token is only returned on the **last** page. Persisting `nextSyncToken` from a
  middle page, or before pagination completes, produces a token that skips whatever was on
  the remaining pages. `sync_token_from` only yields one when there is no `nextPageToken`.
* `syncToken` and most other parameters are mutually exclusive. Sending `personFields`
  changes between a full sync and an incremental one makes the token invalid, because the
  token encodes the field mask. So the field mask is a module constant, not a caller
  argument - changing it is a deliberate edit that also invalidates stored tokens.

Deletions arrive as tombstones
------------------------------
An incremental page represents a deleted contact as a Person with
``metadata.deleted = true`` and no data. Treating that as an ordinary person writes a
contact with every field blank, wiping a real record. `is_deleted` separates them so a
tombstone becomes an unlink rather than an erasure - and note that we never hard-delete our
Contact from a Google signal: their address book is not authoritative over our own records.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

PEOPLE_CONNECTIONS_ENDPOINT = "https://people.googleapis.com/v1/people/me/connections"

#: The field mask. A module constant on purpose: it is baked into a sync token, so changing
#: it invalidates every stored token. Making it a parameter would let a caller silently
#: invalidate them and see 410s that look like expiry rather than a mask change.
PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations,addresses,metadata"

#: Google's maximum for this endpoint. Fewer, larger pages means fewer round trips and fewer
#: chances to abandon pagination before the sync token appears.
PAGE_SIZE = 1000

#: What we record as the origin of any field this module produces. `provenance.SOURCE_TRUST`
#: maps it to IMPORTED - an address book is somebody's notes, not a verified identifier.
SOURCE = "GOOGLE_PEOPLE"

# Error classifications returned by `interpret_error`.
EXPIRED_SYNC_TOKEN = "EXPIRED_SYNC_TOKEN"
INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
UNAUTHENTICATED = "UNAUTHENTICATED"
RATE_LIMITED = "RATE_LIMITED"
TRANSIENT = "TRANSIENT"
PERMANENT = "PERMANENT"


class SyncTokenExpired(Exception):
    """The stored sync token is no longer valid; a full sync is required.

    A distinct type because the correct response is specific and non-obvious: discard the
    token and start again, rather than retry. Retrying a 410 forever is how a sync stops
    advancing without ever reporting a fault.
    """


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

def next_request_params(*, sync_token: Optional[str] = None,
                        page_token: Optional[str] = None,
                        force_full: bool = False) -> Dict[str, Any]:
    """Query parameters for the next `connections.list` call.

    `force_full` exists so a caller that has just seen a 410 cannot accidentally send the
    dead token again - the flag wins over any token passed alongside it.

    `requestSyncToken=true` is set on a full sync so the run ends with a token to store. It
    is also set on an incremental sync, because Google rotates the token and the response
    carries the next one; omitting it there means the next run has nothing to use and
    silently degrades to a full sync every time.
    """
    params: Dict[str, Any] = {
        "personFields": PERSON_FIELDS,
        "pageSize": PAGE_SIZE,
        "requestSyncToken": "true",
    }
    if page_token:
        # Mid-pagination: the page token carries the cursor, and pairing it with a sync token
        # is rejected.
        params["pageToken"] = page_token
        return params
    if sync_token and not force_full:
        params["syncToken"] = sync_token
    return params


def is_full_sync(params: Mapping[str, Any]) -> bool:
    """Would this request be a full sync? Used for logging and for the audit record."""
    return "syncToken" not in params


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

def sync_token_from(response: Optional[Mapping[str, Any]]) -> Optional[str]:
    """`nextSyncToken`, but only when pagination has finished.

    Google returns the token on the last page only. Storing one while `nextPageToken` is
    still present yields a token that skips everything on the remaining pages - a silent
    partial sync that never self-corrects, because the next incremental run starts from the
    wrong point and reports no changes.
    """
    if not response:
        return None
    if response.get("nextPageToken"):
        return None
    token = response.get("nextSyncToken")
    return str(token) if token else None


def page_token_from(response: Optional[Mapping[str, Any]]) -> Optional[str]:
    token = (response or {}).get("nextPageToken")
    return str(token) if token else None


def interpret_error(status: Optional[int],
                    body: Optional[Mapping[str, Any]] = None) -> Tuple[str, bool]:
    """`(classification, must_full_sync)` for an HTTP error from the People API.

    410 is the one that matters: it means the sync token expired and the documented recovery
    is a full sync. Everything else is a retry-or-stop decision.

    403 is split. Google uses it both for quota exhaustion and for a missing scope, and they
    need opposite responses - back off versus stop and ask the user to consent again. The
    reason string distinguishes them; when it is absent we assume rate limiting, because
    backing off on a scope problem merely delays a clear failure, while treating a quota
    error as a scope problem would tear down a working authorisation.
    """
    if status == 410:
        return EXPIRED_SYNC_TOKEN, True
    if status == 401:
        return UNAUTHENTICATED, False
    if status == 429:
        return RATE_LIMITED, False
    if status == 403:
        reason = _first_reason(body)
        if reason in ("insufficientPermissions", "forbidden", "accessNotConfigured",
                      "insufficientScope"):
            return INSUFFICIENT_SCOPE, False
        return RATE_LIMITED, False
    if status is not None and 500 <= int(status) < 600:
        return TRANSIENT, False
    return PERMANENT, False


def _first_reason(body: Optional[Mapping[str, Any]]) -> str:
    error = (body or {}).get("error")
    if not isinstance(error, Mapping):
        return ""
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], Mapping):
        return str(errors[0].get("reason") or "")
    return str(error.get("status") or "")


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

def is_deleted(person: Optional[Mapping[str, Any]]) -> bool:
    """Is this a tombstone rather than a contact?

    Incremental pages represent a removed contact as a Person with `metadata.deleted` true
    and no field data. Mapping that as an ordinary person produces a contact with every field
    blank, which - without the provenance guard - would wipe a real record.
    """
    metadata = (person or {}).get("metadata")
    if not isinstance(metadata, Mapping):
        return False
    return bool(metadata.get("deleted"))


def resource_name(person: Optional[Mapping[str, Any]]) -> str:
    """Google's stable identifier, e.g. `people/c123`. Our link back to their record."""
    return str((person or {}).get("resourceName") or "")


def _primary(values: Optional[Iterable[Mapping[str, Any]]], field: str) -> str:
    """The primary entry's value, falling back to the first present one.

    Google marks one entry `metadata.primary`, but not always - a contact imported from
    elsewhere often has several phone numbers and no primary flag. Returning nothing in that
    case would drop the data; taking the first is the same choice the Contacts UI makes.
    """
    if not values:
        return ""
    entries = [v for v in values if isinstance(v, Mapping)]
    for entry in entries:
        metadata = entry.get("metadata")
        if isinstance(metadata, Mapping) and metadata.get("primary"):
            value = entry.get(field)
            if value:
                return str(value).strip()
    for entry in entries:
        value = entry.get(field)
        if value:
            return str(value).strip()
    return ""


def to_contact_fields(person: Mapping[str, Any]) -> Dict[str, Any]:
    """Map a Person onto our Contact field names. Only fields Google actually supplied.

    Absent fields are omitted rather than set empty, because `provenance.apply_fields` treats
    an empty incoming value as "no information" - and that distinction is what stops a Google
    contact with no company from clearing a company we learned from a Flow.

    `phone` is included, but note it is a `LOCKED_FIELD` in `provenance`: once recorded at
    VERIFIED it is never overwritten by an import, and a conflict is queued for human review
    instead. An address book must not be able to repoint a conversation.
    """
    if is_deleted(person):
        raise ValueError("refusing to map a tombstone; check is_deleted first")

    fields: Dict[str, Any] = {}

    names = person.get("names")
    display = _primary(names, "displayName")
    if display:
        fields["name"] = display

    phone = _primary(person.get("phoneNumbers"), "value")
    if phone:
        # Kept exactly as Google holds it. Normalisation belongs to
        # `lambda_utils.comms.numbers` at the point of use, and rewriting it here would hide
        # what the source actually said from the provenance audit.
        fields["phone"] = phone

    email = _primary(person.get("emailAddresses"), "value")
    if email:
        fields["email"] = email

    organizations = person.get("organizations")
    company = _primary(organizations, "name")
    if company:
        fields["companyName"] = company
    title = _primary(organizations, "title")
    if title:
        fields["designation"] = title

    addresses = person.get("addresses")
    if addresses:
        for source_field, target in (("streetAddress", "addressLine1"),
                                     ("city", "city"),
                                     ("region", "state"),
                                     ("postalCode", "postalCode"),
                                     ("country", "country")):
            value = _primary(addresses, source_field)
            if value:
                fields[target] = value
        formatted = _primary(addresses, "formattedValue")
        if formatted:
            fields["shippingAddress"] = formatted

    return fields


def contact_link(person: Mapping[str, Any]) -> Dict[str, Any]:
    """The provenance link back to Google's record.

    `etag` is stored so a future write-back path could use optimistic concurrency. There is
    no write-back today - the scope is read-only - but recording it costs nothing and its
    absence would be the thing blocking that work later.
    """
    return {
        "googleResourceName": resource_name(person),
        "googleEtag": str(person.get("etag") or ""),
    }


def summarize_page(response: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Counts for a sync audit record. No contact data, so it is safe in a log."""
    connections = (response or {}).get("connections") or []
    people = [c for c in connections if isinstance(c, Mapping)]
    deleted = [p for p in people if is_deleted(p)]
    return {
        "people": len(people),
        "tombstones": len(deleted),
        "mappable": len(people) - len(deleted),
        "hasNextPage": bool(page_token_from(response)),
        "carriesSyncToken": sync_token_from(response) is not None,
        "totalPeople": (response or {}).get("totalPeople"),
    }
