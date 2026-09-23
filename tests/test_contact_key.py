"""The Contact identifier contract (CRM-KEY-001).

Measured against the live table on 2026-09-22, which is what settles the question the
brief poses:

    KeySchema        id (HASH)
    GSIs             bsuid-index, email-index, phone-index
    Items            13
    id == contactId  13 of 13, zero divergence

And in source: 20 files access `ContactsTable`, every one with `Key={'id': ...}`, and
**zero** with `Key={'contactId': ...}`.

So `id` is the physical key and the runtime is correct. The brief's framing - runtime
wrongly uses `id` while the contract says `contactId` - is inverted. The actual defect is
that every row stores the identifier twice with nothing enforcing agreement, and readers
mix the two: both `_lookup_contact_by_phone` implementations return `item['contactId']`,
which then flows into code that uses it as a key.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import contact_key  # noqa: E402

CID = "c-0001"


class TestThePhysicalKeyIsId:
    def test_the_key_helper_uses_id(self):
        """Confirmed against the deployed table: KeySchema is id (HASH)."""
        assert contact_key.PHYSICAL_KEY == "id"
        assert contact_key.key(CID) == {"id": CID}

    def test_the_key_helper_refuses_an_empty_id(self):
        """A `get_item` with an empty key silently returns nothing, which reads as
        'contact not found' rather than 'the caller had no id'."""
        for empty in ("", "   ", None):
            with pytest.raises(ValueError):
                contact_key.key(empty)

    def test_no_call_site_needs_to_know_the_spelling(self):
        """The point of the helper: a future key change is one edit, not twenty."""
        assert list(contact_key.key(CID)) == [contact_key.PHYSICAL_KEY]


class TestResolveAcceptsEitherSpelling:
    def test_an_id_only_row_resolves(self):
        assert contact_key.resolve({"id": CID}) == CID

    def test_a_contact_id_only_row_resolves(self):
        """This is the shape a projection or an older row can produce."""
        assert contact_key.resolve({"contactId": CID}) == CID

    def test_a_row_with_both_resolves(self):
        assert contact_key.resolve({"id": CID, "contactId": CID}) == CID

    def test_id_wins_when_the_two_disagree(self):
        """If they disagree, the one that can actually be used for a get_item is the
        right answer."""
        assert contact_key.resolve({"id": CID, "contactId": "other"}) == CID

    def test_an_explicit_argument_beats_the_row(self):
        assert contact_key.resolve({"id": "from-row"}, contact_id="explicit") == "explicit"

    @pytest.mark.parametrize("empty", [None, {}, {"id": ""}, {"contactId": "  "},
                                       {"id": None, "contactId": None}])
    def test_nothing_usable_returns_empty_rather_than_raising(self, empty):
        """Callers test falsiness; making this raise would push a try/except into twenty
        call sites."""
        assert contact_key.resolve(empty) == ""

    def test_whitespace_is_stripped(self):
        assert contact_key.resolve({"id": f"  {CID}  "}) == CID


class TestTheInvariant:
    def test_matching_identifiers_pass(self):
        contact_key.assert_consistent({"id": CID, "contactId": CID})

    def test_a_diverged_row_is_rejected(self):
        """The hazard this module exists for. Today 13 of 13 rows agree, by habit rather
        than constraint - a migration, a bulk import or a console edit breaks it."""
        with pytest.raises(contact_key.ContactKeyMismatch):
            contact_key.assert_consistent({"id": CID, "contactId": "different"})

    def test_the_error_does_not_echo_the_identifiers(self):
        """This message reaches logs, and a contact id is a customer reference."""
        try:
            contact_key.assert_consistent({"id": "cust-abc-123", "contactId": "cust-xyz-789"})
        except contact_key.ContactKeyMismatch as exc:
            text = str(exc)
            assert "cust-abc-123" not in text
            assert "cust-xyz-789" not in text
            assert "untrustworthy" in text
        else:
            pytest.fail("expected ContactKeyMismatch")

    @pytest.mark.parametrize("partial", [{"id": CID}, {"contactId": CID}, {}])
    def test_absence_is_tolerated_only_conflict_is_an_error(self, partial):
        """A projection legitimately returns one field. Only a genuine conflict is
        unresolvable."""
        contact_key.assert_consistent(partial)


class TestWritersCannotDivergeThem:
    def test_both_fields_are_produced_together(self):
        """What turns the alias from a coincidence into an invariant: a writer cannot set
        one without the other."""
        assert contact_key.contact_item_keys(CID) == {"id": CID, "contactId": CID}

    def test_an_empty_id_is_refused(self):
        for empty in ("", "  ", None):
            with pytest.raises(ValueError):
                contact_key.contact_item_keys(empty)

    def test_the_produced_pair_always_satisfies_the_invariant(self):
        for value in ("a", "c-1", "uuid-like-0000-1111", "x" * 64):
            contact_key.assert_consistent(contact_key.contact_item_keys(value))


class TestNormalizeRepairsAPartialRow:
    def test_an_id_only_row_gains_the_alias(self):
        out = contact_key.normalize_item({"id": CID, "name": "n"})
        assert out["contactId"] == CID
        assert out["name"] == "n", "unrelated fields must survive"

    def test_a_contact_id_only_row_gains_the_physical_key(self):
        """This is the repair that makes a reader able to treat any row uniformly."""
        out = contact_key.normalize_item({"contactId": CID})
        assert out["id"] == CID

    def test_it_does_not_mutate_the_input(self):
        original = {"id": CID}
        contact_key.normalize_item(original)
        assert "contactId" not in original

    def test_a_conflict_raises_rather_than_silently_choosing(self):
        with pytest.raises(contact_key.ContactKeyMismatch):
            contact_key.normalize_item({"id": CID, "contactId": "other"})


class TestTheSilentFailurePath:
    """The reason this module exists, stated as a test.

    `rcs-dlr._lookup_contact_by_phone` queries `phone-index` and returns
    ``items[0].get('contactId', '')``. That value flows into `put_message(contact_id=...)`
    and onward into code that uses it as a **key**. If a writer ever diverges the two
    fields, the returned value resolves to nothing and a message is stored against a
    contact that cannot be looked up - with no error anywhere.
    """

    def _legacy_lookup(self, row):
        """The pattern as it exists today in two handlers."""
        return row.get("contactId", "")

    def _guarded_lookup(self, row):
        """The same lookup through this module."""
        contact_key.assert_consistent(row)
        return contact_key.resolve(row)

    def test_today_both_approaches_agree(self):
        """13 of 13 live rows are consistent, so the legacy pattern works right now. That
        is exactly why the hazard is invisible."""
        row = {"id": CID, "contactId": CID, "phone": "+919876543210"}
        assert self._legacy_lookup(row) == self._guarded_lookup(row) == CID

    def test_a_diverged_row_makes_the_legacy_pattern_return_an_unusable_key(self):
        row = {"id": CID, "contactId": "stale-id", "phone": "+919876543210"}
        assert self._legacy_lookup(row) == "stale-id"
        # Which is not the key, so a get_item with it finds nothing.
        assert contact_key.key(self._legacy_lookup(row)) != contact_key.key(CID)

    def test_the_guarded_lookup_refuses_instead_of_returning_a_bad_key(self):
        """Failing loudly beats storing a message against an unresolvable contact."""
        row = {"id": CID, "contactId": "stale-id"}
        with pytest.raises(contact_key.ContactKeyMismatch):
            self._guarded_lookup(row)

    def test_a_row_carrying_only_the_alias_still_yields_a_usable_key(self):
        """The legacy pattern happens to work here; the guarded one also repairs it."""
        row = {"contactId": CID}
        assert contact_key.key(self._guarded_lookup(row)) == {"id": CID}


class TestDescribeForDiagnostics:
    @pytest.mark.parametrize("row,consistent", [
        ({"id": CID, "contactId": CID}, True),
        ({"id": CID}, True),
        ({"contactId": CID}, True),
        ({"id": CID, "contactId": "x"}, False),
        ({}, False),
    ])
    def test_it_classifies_without_raising(self, row, consistent):
        assert contact_key.describe(row)[0] is consistent

    def test_it_never_includes_an_identifier(self):
        for row in ({"id": "secret-id-1", "contactId": "secret-id-2"},
                    {"id": "secret-id-1"}):
            _, reason = contact_key.describe(row)
            assert "secret-id-1" not in reason
            assert "secret-id-2" not in reason
