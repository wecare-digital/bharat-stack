"""Contact identity: field provenance, OAuth/PKCE, Google People sync, Truecaller consent.

Measured before building, 2026-09-23: both credentials already exist in Secrets Manager and
nothing reads either of them.

    wecare/seo/google-oauth   client_id, client_secret     created 2026-04-18
    wecare/truecaller         app_key, app_name,
                              app_domain, callback_url     created 2026-09-19

A grep for `people.googleapis`, `truecaller`, `pkce` and `code_verifier` across `amplify/`,
`src/` and `scripts/` found no OAuth flow of any kind, so this is greenfield and no redirect
URI has ever been exercised.

The live consent steps are owner-gated - a Google redirect URI plus a consent-screen scope,
and a Truecaller callback registration - so these tests pin the contracts, the state machines
and the guards against fixtures. What they concentrate on is the handful of places where
getting it wrong is silent:

* a Google sync token that expires and is retried forever, so the sync stops advancing
* `expires_in` stored as if absolute, so a token reads as fresh forever
* a refresh token wiped by a re-authorisation, killing the integration hours later
* a scope the user quietly declined, so the API 403s and the sync "finds nothing"
* a Truecaller callback naming its own profile host, which is an auth bypass
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.identity import (google_people, oauth_pkce,  # noqa: E402
                                  provenance, truecaller)


# ===========================================================================
# Provenance
# ===========================================================================

class TestProvenanceTrust:
    def test_verified_outranks_everything(self):
        for weaker in ("FLOW_SUBMISSION", "DASHBOARD", "GOOGLE_PEOPLE", "DERIVED"):
            assert provenance.trust_of("WHATSAPP_INBOUND") > provenance.trust_of(weaker)

    def test_an_address_book_cannot_overwrite_a_flow_answer(self):
        contact = {"companyName": "Acme Ltd",
                   provenance.PROVENANCE_ATTRIBUTE: {"companyName": "FLOW_SUBMISSION"}}
        allowed, reason = provenance.may_write(contact, "companyName", "GOOGLE_PEOPLE",
                                               incoming_value="Acme Limited")
        assert not allowed
        assert "less trusted" in reason

    def test_a_flow_answer_can_overwrite_an_address_book_value(self):
        contact = {"companyName": "Acme Limited",
                   provenance.PROVENANCE_ATTRIBUTE: {"companyName": "GOOGLE_PEOPLE"}}
        allowed, _ = provenance.may_write(contact, "companyName", "FLOW_SUBMISSION",
                                          incoming_value="Acme Ltd")
        assert allowed

    def test_equal_trust_may_overwrite(self):
        """A second inbound message must be able to refresh a profile name."""
        contact = {"name": "Old",
                   provenance.PROVENANCE_ATTRIBUTE: {"name": "WHATSAPP_INBOUND"}}
        allowed, _ = provenance.may_write(contact, "name", "WHATSAPP_INBOUND",
                                          incoming_value="New")
        assert allowed

    def test_an_unclaimed_field_is_writable(self):
        allowed, reason = provenance.may_write({"name": None}, "name", "GOOGLE_PEOPLE",
                                              incoming_value="Someone")
        assert allowed
        assert "unclaimed" in reason

    def test_a_legacy_row_without_provenance_is_not_frozen(self):
        """Refusing would freeze every pre-existing row; claiming VERIFIED would be a lie."""
        contact = {"companyName": "Acme"}
        allowed, _ = provenance.may_write(contact, "companyName", "GOOGLE_PEOPLE",
                                          incoming_value="Acme Ltd")
        assert allowed

    def test_an_unknown_source_is_refused_not_defaulted(self):
        with pytest.raises(provenance.UnknownSource):
            provenance.trust_of("SOME_NEW_INTEGRATION")


class TestProvenanceLockedFields:
    def test_a_verified_phone_is_never_overwritten_by_an_import(self):
        """phone is the routing key: changing it redirects a conversation to another person."""
        contact = {"phone": "+919903300044",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND"}}
        allowed, reason = provenance.may_write(contact, "phone", "GOOGLE_PEOPLE",
                                               incoming_value="+919900000000")
        assert not allowed
        assert "locked" in reason

    def test_even_another_verified_source_cannot_change_it_silently(self):
        contact = {"phone": "+919903300044",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND"}}
        allowed, _ = provenance.may_write(contact, "phone", "TRUECALLER",
                                          incoming_value="+919900000000")
        assert not allowed
        assert provenance.needs_review(contact, "phone", "TRUECALLER",
                                       incoming_value="+919900000000")

    def test_resyncing_the_same_value_is_not_a_conflict(self):
        """Otherwise a daily incremental sync queues the same review every day."""
        contact = {"phone": "+919903300044",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND"}}
        assert not provenance.needs_review(contact, "phone", "TRUECALLER",
                                           incoming_value="+919903300044")
        allowed, reason = provenance.may_write(contact, "phone", "TRUECALLER",
                                              incoming_value="+919903300044")
        assert not allowed
        assert reason == "value unchanged"

    def test_a_contact_with_no_phone_yet_accepts_one(self):
        allowed, _ = provenance.may_write({}, "phone", "GOOGLE_PEOPLE",
                                          incoming_value="+919903300044")
        assert allowed

    def test_consent_flags_are_never_synced(self):
        """An address book cannot consent to messaging on a customer's behalf."""
        for field in ("optInWhatsApp", "optInSms", "optInEmail",
                      "allowlistWhatsApp", "allowlistSms", "allowlistEmail"):
            allowed, reason = provenance.may_write({}, field, "GOOGLE_PEOPLE",
                                                   incoming_value=True)
            assert not allowed, f"{field} must never be set by a sync"
            assert "never" in reason

    def test_identity_fields_are_never_synced(self):
        for field in ("id", "contactId"):
            allowed, _ = provenance.may_write({}, field, "GOOGLE_PEOPLE",
                                              incoming_value="x")
            assert not allowed


class TestProvenanceApply:
    def test_an_empty_incoming_value_does_not_clear_a_field(self):
        """A Google contact with no company must not wipe a company from a Flow."""
        contact = {"companyName": "Acme",
                   provenance.PROVENANCE_ATTRIBUTE: {"companyName": "FLOW_SUBMISSION"}}
        result = provenance.apply_fields(contact, {"companyName": ""}, "GOOGLE_PEOPLE")
        assert "companyName" not in result["updates"]
        assert result["skipped"]["companyName"] == "empty incoming value"

    def test_a_locked_conflict_is_queued_and_not_applied(self):
        contact = {"phone": "+919903300044",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND"}}
        result = provenance.apply_fields(contact, {"phone": "+919900000000"}, "TRUECALLER")
        assert "phone" not in result["updates"]
        assert result["review"]["phone"]["current"] == "+919903300044"
        assert result["review"]["phone"]["incoming"] == "+919900000000"

    def test_a_mixed_payload_applies_only_what_it_may(self):
        contact = {"phone": "+919903300044", "companyName": "Acme",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND",
                                                     "companyName": "DASHBOARD"}}
        result = provenance.apply_fields(contact, {
            "phone": "+919900000000",     # locked
            "companyName": "Acme Ltd",    # weaker than DASHBOARD
            "designation": "CEO",         # unclaimed
        }, "GOOGLE_PEOPLE")
        assert set(result["updates"]) == {"designation"}
        assert result["sources"]["designation"] == "GOOGLE_PEOPLE"

    def test_provenance_is_merged_not_replaced(self):
        """A partial sync must not demote fields it did not touch to unclaimed."""
        contact = {provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND",
                                                     "name": "FLOW_SUBMISSION"}}
        merged = provenance.merged_provenance(contact, {"designation": "GOOGLE_PEOPLE"})
        assert merged == {"phone": "WHATSAPP_INBOUND", "name": "FLOW_SUBMISSION",
                          "designation": "GOOGLE_PEOPLE"}

    def test_describe_carries_no_field_values(self):
        contact = {"phone": "+919903300044", "name": "Priya",
                   provenance.PROVENANCE_ATTRIBUTE: {"phone": "WHATSAPP_INBOUND"}}
        rendered = repr(provenance.describe(contact))
        assert "919903300044" not in rendered
        assert "Priya" not in rendered


# ===========================================================================
# OAuth / PKCE
# ===========================================================================

class TestPkce:
    def test_verifier_is_within_the_rfc_bounds(self):
        verifier = oauth_pkce.new_code_verifier()
        assert 43 <= len(verifier) <= 128
        assert re.fullmatch(r"[A-Za-z0-9\-._~]+", verifier)

    def test_verifiers_are_unique(self):
        assert len({oauth_pkce.new_code_verifier() for _ in range(50)}) == 50

    def test_challenge_is_unpadded_base64url_sha256(self):
        challenge = oauth_pkce.code_challenge_for("a" * 64)
        assert "=" not in challenge, "Google rejects a padded challenge"
        assert "+" not in challenge and "/" not in challenge
        assert len(challenge) == 43

    def test_challenge_is_deterministic_and_verifier_specific(self):
        a, b = "a" * 64, "b" * 64
        assert oauth_pkce.code_challenge_for(a) == oauth_pkce.code_challenge_for(a)
        assert oauth_pkce.code_challenge_for(a) != oauth_pkce.code_challenge_for(b)

    def test_a_short_verifier_is_refused(self):
        with pytest.raises(oauth_pkce.OAuthError):
            oauth_pkce.code_challenge_for("tooshort")

    def test_state_comparison_is_constant_time_and_rejects_absence(self):
        state = oauth_pkce.new_state()
        assert oauth_pkce.verify_state(state, state)
        assert not oauth_pkce.verify_state(state, state + "x")
        assert not oauth_pkce.verify_state(None, state)
        assert not oauth_pkce.verify_state(state, None)
        assert not oauth_pkce.verify_state("", "")


class TestAuthorizationUrl:
    def _url(self, **overrides):
        kwargs = dict(client_id="cid", redirect_uri="https://api.wecare.digital/cb",
                      scopes=[oauth_pkce.GOOGLE_CONTACTS_SCOPE], state="st",
                      code_challenge="ch")
        kwargs.update(overrides)
        return oauth_pkce.build_authorization_url(**kwargs)

    def test_uses_s256_never_plain(self):
        """`plain` sends the verifier as the challenge, so reading the request is enough."""
        assert "code_challenge_method=S256" in self._url()
        assert "plain" not in self._url()

    def test_requests_offline_access_and_forces_consent(self):
        """Both are needed or a re-auth silently withholds the refresh token."""
        url = self._url()
        assert "access_type=offline" in url
        assert "prompt=consent" in url

    def test_is_incremental(self):
        assert "include_granted_scopes=true" in self._url()

    def test_asks_for_read_only_contacts(self):
        assert "contacts.readonly" in self._url()

    def test_missing_parameters_are_refused(self):
        for missing in ("client_id", "redirect_uri", "state", "code_challenge"):
            with pytest.raises(oauth_pkce.OAuthError):
                self._url(**{missing: ""})
        with pytest.raises(oauth_pkce.OAuthError):
            self._url(scopes=[])

    def test_exchange_body_carries_the_verifier(self):
        body = oauth_pkce.token_exchange_body(
            client_id="cid", client_secret="sec", code="c",
            redirect_uri="https://api.wecare.digital/cb", code_verifier="v" * 43)
        assert body["grant_type"] == "authorization_code"
        assert body["code_verifier"] == "v" * 43

    def test_refresh_body_has_no_verifier(self):
        """PKCE binds the code exchange, not the refresh."""
        body = oauth_pkce.refresh_body(client_id="c", client_secret="s",
                                       refresh_token="r")
        assert body["grant_type"] == "refresh_token"
        assert "code_verifier" not in body


class TestTokenLifecycle:
    RESPONSE = {"access_token": "at", "refresh_token": "rt", "expires_in": 3599,
                "token_type": "Bearer",
                "scope": oauth_pkce.GOOGLE_CONTACTS_SCOPE}

    def test_expires_in_becomes_absolute(self):
        """Storing 3599 raw makes the token read as fresh forever."""
        record = oauth_pkce.token_record(self.RESPONSE, at=1_000_000)
        assert record["expiresAt"] == 1_000_000 + 3599
        assert "expires_in" not in record

    def test_a_response_without_an_access_token_is_refused(self):
        with pytest.raises(oauth_pkce.OAuthError):
            oauth_pkce.token_record({"expires_in": 3599})

    def test_a_missing_lifetime_is_treated_as_expired_not_unlimited(self):
        record = oauth_pkce.token_record({"access_token": "at"}, at=1_000)
        assert record["expiresAt"] == 1_000
        assert oauth_pkce.needs_refresh(record, at=1_000)

    def test_refresh_happens_before_the_cliff(self):
        record = oauth_pkce.token_record(self.RESPONSE, at=0)
        assert not oauth_pkce.needs_refresh(record, at=3000)
        # Inside the skew window.
        assert oauth_pkce.needs_refresh(record, at=3599 - 10)
        assert oauth_pkce.needs_refresh(record, at=3599)

    def test_a_reauthorisation_must_not_wipe_the_refresh_token(self):
        """Google omits refresh_token on re-consent and on every refresh response."""
        stored = oauth_pkce.token_record(self.RESPONSE, at=0)
        assert stored["refreshToken"] == "rt"
        fresh = oauth_pkce.token_record(
            {"access_token": "at2", "expires_in": 3599,
             "scope": oauth_pkce.GOOGLE_CONTACTS_SCOPE}, at=4000)
        merged = oauth_pkce.merge_token_record(stored, fresh)
        assert merged["accessToken"] == "at2"
        assert merged["refreshToken"] == "rt", (
            "losing this turns a working integration into one that dies at next expiry")

    def test_a_rotated_refresh_token_wins(self):
        stored = oauth_pkce.token_record(self.RESPONSE, at=0)
        fresh = oauth_pkce.token_record(
            {"access_token": "at2", "refresh_token": "rt2", "expires_in": 3599}, at=4000)
        assert oauth_pkce.merge_token_record(stored, fresh)["refreshToken"] == "rt2"

    def test_no_token_needs_a_refresh(self):
        assert oauth_pkce.needs_refresh(None)
        assert oauth_pkce.needs_refresh({})
        assert oauth_pkce.needs_refresh({"accessToken": "", "expiresAt": 9_999_999_999})

    def test_can_refresh_reports_whether_consent_is_needed_again(self):
        assert oauth_pkce.can_refresh({"refreshToken": "rt"})
        assert not oauth_pkce.can_refresh({"accessToken": "at"})
        assert not oauth_pkce.can_refresh(None)

    def test_describe_leaks_no_token_material(self):
        """Distinctive values, because `at`/`rt` are too short to prove anything.

        This output is designed to be safe in a CloudWatch line and an admin screen, so the
        assertion has to be able to actually fail.
        """
        record = oauth_pkce.token_record({
            "access_token": "ACCESS-b7f3c1d9e4a2-SENTINEL",
            "refresh_token": "REFRESH-4c8e2a1f6b90-SENTINEL",
            "expires_in": 3599,
            "scope": oauth_pkce.GOOGLE_CONTACTS_SCOPE,
        }, at=int(time.time()))
        rendered = repr(oauth_pkce.describe(record))
        assert "ACCESS-b7f3c1d9e4a2-SENTINEL" not in rendered
        assert "REFRESH-4c8e2a1f6b90-SENTINEL" not in rendered
        assert "SENTINEL" not in rendered
        # But it must still be useful.
        assert oauth_pkce.describe(record)["accessTokenLength"] == \
            len("ACCESS-b7f3c1d9e4a2-SENTINEL")
        assert oauth_pkce.describe(record)["canRefresh"] is True


class TestScopeVerification:
    def test_a_declined_scope_is_reported(self):
        """The token is valid, so the only other symptom is a 403 and an empty sync."""
        response = {"access_token": "at", "scope": "https://www.googleapis.com/auth/userinfo.email"}
        missing = oauth_pkce.missing_scopes(response, [oauth_pkce.GOOGLE_CONTACTS_SCOPE])
        assert missing == [oauth_pkce.GOOGLE_CONTACTS_SCOPE]

    def test_a_granted_scope_is_not_reported(self):
        response = {"access_token": "at", "scope": oauth_pkce.GOOGLE_CONTACTS_SCOPE}
        assert oauth_pkce.missing_scopes(response, [oauth_pkce.GOOGLE_CONTACTS_SCOPE]) == []

    def test_an_absent_scope_means_nothing_granted_not_everything(self):
        assert oauth_pkce.missing_scopes({"access_token": "at"},
                                        [oauth_pkce.GOOGLE_CONTACTS_SCOPE]) == \
            [oauth_pkce.GOOGLE_CONTACTS_SCOPE]


# ===========================================================================
# Google People
# ===========================================================================

class TestSyncTokenLifecycle:
    def test_410_demands_a_full_sync(self):
        """Retrying it forever is how a sync silently stops advancing."""
        classification, must_full = google_people.interpret_error(410)
        assert classification == google_people.EXPIRED_SYNC_TOKEN
        assert must_full is True

    def test_force_full_beats_a_stale_token(self):
        params = google_people.next_request_params(sync_token="dead", force_full=True)
        assert "syncToken" not in params
        assert google_people.is_full_sync(params)

    def test_an_incremental_request_sends_the_token(self):
        params = google_people.next_request_params(sync_token="tok")
        assert params["syncToken"] == "tok"
        assert not google_people.is_full_sync(params)

    def test_an_incremental_request_still_asks_for_a_new_token(self):
        """Google rotates it; omitting this degrades every run to a full sync."""
        params = google_people.next_request_params(sync_token="tok")
        assert params["requestSyncToken"] == "true"

    def test_a_page_token_is_not_paired_with_a_sync_token(self):
        params = google_people.next_request_params(sync_token="tok", page_token="pg")
        assert params["pageToken"] == "pg"
        assert "syncToken" not in params

    def test_a_sync_token_is_only_taken_from_the_last_page(self):
        """Storing one mid-pagination yields a token that skips the remaining pages."""
        assert google_people.sync_token_from(
            {"nextSyncToken": "t", "nextPageToken": "more"}) is None
        assert google_people.sync_token_from({"nextSyncToken": "t"}) == "t"

    def test_the_field_mask_is_not_caller_controlled(self):
        """It is baked into the sync token, so a caller changing it invalidates them all."""
        import inspect

        signature = inspect.signature(google_people.next_request_params)
        assert "person_fields" not in signature.parameters
        assert "personFields" not in signature.parameters
        assert google_people.next_request_params()["personFields"] == \
            google_people.PERSON_FIELDS

    @pytest.mark.parametrize("status,expected", [
        (401, google_people.UNAUTHENTICATED),
        (429, google_people.RATE_LIMITED),
        (500, google_people.TRANSIENT),
        (503, google_people.TRANSIENT),
        (400, google_people.PERMANENT),
    ])
    def test_other_statuses(self, status, expected):
        assert google_people.interpret_error(status)[0] == expected

    def test_403_distinguishes_a_missing_scope_from_a_quota(self):
        scope_body = {"error": {"errors": [{"reason": "insufficientPermissions"}]}}
        assert google_people.interpret_error(403, scope_body)[0] == \
            google_people.INSUFFICIENT_SCOPE
        # Unlabelled 403 assumes quota: backing off on a scope problem only delays a clear
        # failure, whereas treating a quota error as a scope problem tears down a working auth.
        assert google_people.interpret_error(403, {})[0] == google_people.RATE_LIMITED


class TestPersonMapping:
    PERSON = {
        "resourceName": "people/c123",
        "etag": "%EgUBAj0",
        "names": [{"displayName": "Priya Sharma",
                   "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": "+91 99033 00044", "metadata": {"primary": True}},
                         {"value": "+919900000001"}],
        "emailAddresses": [{"value": "priya@example.com", "metadata": {"primary": True}}],
        "organizations": [{"name": "Acme Ltd", "title": "CEO",
                           "metadata": {"primary": True}}],
        "addresses": [{"streetAddress": "12 MG Road", "city": "Bengaluru",
                       "region": "KA", "postalCode": "560001", "country": "India",
                       "formattedValue": "12 MG Road, Bengaluru, KA 560001",
                       "metadata": {"primary": True}}],
    }

    def test_maps_the_primary_values(self):
        fields = google_people.to_contact_fields(self.PERSON)
        assert fields["name"] == "Priya Sharma"
        assert fields["phone"] == "+91 99033 00044"
        assert fields["email"] == "priya@example.com"
        assert fields["companyName"] == "Acme Ltd"
        assert fields["designation"] == "CEO"
        assert fields["city"] == "Bengaluru"
        assert fields["postalCode"] == "560001"

    def test_falls_back_to_the_first_entry_when_nothing_is_primary(self):
        """Imported contacts often carry several numbers and no primary flag."""
        person = {"phoneNumbers": [{"value": "+919900000002"}]}
        assert google_people.to_contact_fields(person)["phone"] == "+919900000002"

    def test_absent_fields_are_omitted_not_blanked(self):
        fields = google_people.to_contact_fields({"names": [{"displayName": "Solo"}]})
        assert fields == {"name": "Solo"}

    def test_the_number_is_not_rewritten_here(self):
        """Normalisation belongs to comms.numbers at the point of use.

        Rewriting it here would hide from the provenance audit what the source actually said.
        """
        fields = google_people.to_contact_fields(self.PERSON)
        assert fields["phone"] == "+91 99033 00044"

    def test_a_tombstone_is_detected_and_refused_for_mapping(self):
        """Mapping one would write a contact with every field blank."""
        tombstone = {"resourceName": "people/c999", "metadata": {"deleted": True}}
        assert google_people.is_deleted(tombstone)
        with pytest.raises(ValueError):
            google_people.to_contact_fields(tombstone)

    def test_a_live_person_is_not_a_tombstone(self):
        assert not google_people.is_deleted(self.PERSON)
        assert not google_people.is_deleted({})

    def test_the_link_back_records_the_etag(self):
        link = google_people.contact_link(self.PERSON)
        assert link["googleResourceName"] == "people/c123"
        assert link["googleEtag"] == "%EgUBAj0"

    def test_mapped_fields_are_imported_trust(self):
        """An address book is somebody's notes, not a verified identifier."""
        assert provenance.SOURCE_TRUST[google_people.SOURCE] == provenance.IMPORTED

    def test_page_summary_carries_no_contact_data(self):
        response = {"connections": [self.PERSON,
                                    {"metadata": {"deleted": True}}],
                    "nextSyncToken": "t"}
        summary = google_people.summarize_page(response)
        assert summary == {"people": 2, "tombstones": 1, "mappable": 1,
                           "hasNextPage": False, "carriesSyncToken": True,
                           "totalPeople": None}
        assert "Priya" not in repr(summary)


# ===========================================================================
# Truecaller
# ===========================================================================

class TestTruecallerEndpointAllowlist:
    """The security boundary. The callback is public, so `endpoint` is attacker input."""

    def test_an_allowed_host_passes(self):
        for host in sorted(truecaller.ALLOWED_PROFILE_HOSTS):
            url = f"https://{host}/v1/default"
            assert truecaller.resolve_profile_endpoint(url) == url

    def test_an_arbitrary_host_is_refused(self):
        """Otherwise it returns any phone number and we record it as verified."""
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint("https://evil.example/v1/default")

    def test_a_suffix_lookalike_is_refused(self):
        """A suffix test on truecaller.com would accept this."""
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint(
                "https://profile4-noneu.truecaller.com.evil.example/v1/default")

    def test_a_substring_lookalike_is_refused(self):
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint(
                "https://evil.example/profile4-noneu.truecaller.com/v1/default")

    def test_userinfo_smuggling_is_refused(self):
        """The real host is after the '@'; reading left to right suggests otherwise."""
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint(
                "https://profile4-noneu.truecaller.com@evil.example/v1/default")

    def test_plain_http_is_refused(self):
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint(
                "http://profile4-noneu.truecaller.com/v1/default")

    def test_an_explicit_port_is_refused(self):
        with pytest.raises(truecaller.UntrustedEndpoint):
            truecaller.resolve_profile_endpoint(
                "https://profile4-noneu.truecaller.com:8443/v1/default")

    def test_a_query_or_fragment_is_refused(self):
        for suffix in ("?next=https://evil.example", "#https://evil.example"):
            with pytest.raises(truecaller.UntrustedEndpoint):
                truecaller.resolve_profile_endpoint(
                    f"https://profile4-noneu.truecaller.com/v1/default{suffix}")

    def test_metadata_service_is_refused(self):
        """The same primitive is an SSRF; 169.254.169.254 is the reason it matters."""
        for url in ("https://169.254.169.254/latest/meta-data/",
                    "https://localhost/v1/default",
                    "https://10.0.0.1/v1/default"):
            with pytest.raises(truecaller.UntrustedEndpoint):
                truecaller.resolve_profile_endpoint(url)

    def test_an_absent_endpoint_is_refused_not_defaulted(self):
        """Substituting a known host would make the whole check decorative."""
        for value in ("", None, "   "):
            with pytest.raises(truecaller.UntrustedEndpoint):
                truecaller.resolve_profile_endpoint(value)


class TestTruecallerNonce:
    def test_a_nonce_is_within_the_documented_bounds(self):
        nonce = truecaller.new_nonce()
        assert truecaller.NONCE_MIN_LENGTH <= len(nonce) <= truecaller.NONCE_MAX_LENGTH
        assert truecaller.nonce_is_wellformed(nonce)

    def test_nonces_are_unguessable_and_unique(self):
        assert len({truecaller.new_nonce() for _ in range(50)}) == 50

    def test_a_nonce_must_bind_to_a_session(self):
        """Without it a verified number lands on whoever polls next."""
        with pytest.raises(ValueError):
            truecaller.nonce_record(truecaller.new_nonce(), session_id="")

    def test_a_matching_pending_nonce_is_claimable(self):
        nonce = truecaller.new_nonce()
        record = truecaller.nonce_record(nonce, session_id="s1", at=1000)
        ok, reason = truecaller.claim_nonce(record, nonce, at=1100)
        assert ok, reason

    def test_a_mismatched_nonce_is_refused(self):
        record = truecaller.nonce_record(truecaller.new_nonce(), session_id="s1", at=1000)
        ok, reason = truecaller.claim_nonce(record, truecaller.new_nonce(), at=1100)
        assert not ok
        assert "mismatch" in reason

    def test_a_replayed_callback_is_refused(self):
        nonce = truecaller.new_nonce()
        record = truecaller.nonce_record(nonce, session_id="s1", at=1000)
        record["status"] = truecaller.STATUS_VERIFIED
        ok, reason = truecaller.claim_nonce(record, nonce, at=1100)
        assert not ok
        assert truecaller.STATUS_PENDING in reason

    def test_an_expired_nonce_is_refused(self):
        nonce = truecaller.new_nonce()
        record = truecaller.nonce_record(nonce, session_id="s1", at=1000,
                                        ttl_seconds=60)
        ok, reason = truecaller.claim_nonce(record, nonce, at=2000)
        assert not ok
        assert "expired" in reason

    def test_an_unknown_nonce_is_refused(self):
        ok, reason = truecaller.claim_nonce(None, truecaller.new_nonce())
        assert not ok
        assert "no such nonce" in reason


class TestTruecallerCallbackAndProfile:
    def test_a_rejection_is_a_normal_outcome(self):
        parsed = truecaller.read_callback({"requestId": "r", "status": "user_rejected"})
        assert parsed["rejected"] is True
        assert parsed["accessToken"] == ""

    def test_a_success_callback_is_parsed(self):
        parsed = truecaller.read_callback({
            "requestId": "r", "accessToken": "tok",
            "endpoint": "https://profile4-noneu.truecaller.com/v1/default"})
        assert parsed["rejected"] is False
        assert parsed["accessToken"] == "tok"

    def test_only_one_number_is_treated_as_verified(self):
        """One consent vouches for the handset used, not for every listed number."""
        profile = {"phoneNumbers": ["919903300044", "919900000001"]}
        assert truecaller.verified_phone(profile) == "919903300044"
        assert truecaller.to_contact_fields(profile) == {"phone": "919903300044"}

    def test_self_reported_profile_data_is_kept_separate_from_the_verified_number(self):
        """The consent proves possession of a number, not the name on the profile."""
        profile = {"phoneNumbers": ["919903300044"],
                   "name": {"first": "Priya", "last": "Sharma"},
                   "onlineIdentities": {"email": "priya@example.com"},
                   "companyName": "Acme", "jobTitle": "CEO"}
        assert truecaller.to_contact_fields(profile) == {"phone": "919903300044"}
        declared = truecaller.declared_fields(profile)
        assert declared["name"] == "Priya Sharma"
        assert declared["email"] == "priya@example.com"
        assert "phone" not in declared

    def test_a_profile_with_no_number_verifies_nothing(self):
        assert truecaller.verified_phone({"phoneNumbers": []}) == ""
        assert truecaller.to_contact_fields({"phoneNumbers": []}) == {}

    def test_the_verified_number_is_verified_trust(self):
        assert provenance.SOURCE_TRUST[truecaller.SOURCE] == provenance.VERIFIED

    def test_the_profile_summary_leaks_no_pii(self):
        profile = {"phoneNumbers": ["919903300044"],
                   "name": {"first": "Priya", "last": "Sharma"},
                   "onlineIdentities": {"email": "priya@example.com"}}
        rendered = repr(truecaller.summarize_profile(profile))
        assert "919903300044" not in rendered
        assert "Priya" not in rendered
        assert "priya@example.com" not in rendered
        assert "0044" in rendered, "the masked suffix is useful and not a disclosure"


class TestTruecallerDeepLink:
    def test_carries_the_nonce_and_partner_key(self):
        nonce = truecaller.new_nonce()
        link = truecaller.build_deep_link(nonce=nonce, app_key="ak", app_name="WECARE")
        assert link.startswith(truecaller.DEEP_LINK_SCHEME)
        assert f"requestNonce={nonce}" in link
        assert "partnerKey=ak" in link
        assert "partnerName=WECARE" in link

    def test_a_malformed_nonce_is_refused(self):
        with pytest.raises(ValueError):
            truecaller.build_deep_link(nonce="short", app_key="ak", app_name="W")

    def test_missing_partner_details_are_refused(self):
        with pytest.raises(ValueError):
            truecaller.build_deep_link(nonce=truecaller.new_nonce(), app_key="",
                                       app_name="W")

    def test_ttl_is_clamped_to_the_documented_minimum(self):
        """Truecaller floors it at 8000ms, so sending less makes the link lie."""
        link = truecaller.build_deep_link(nonce=truecaller.new_nonce(), app_key="k",
                                          app_name="W", ttl_ms=1000)
        assert "ttl=8000" in link


class TestNoBulkLookup:
    """Consent-based verification of the current user only. No number-to-identity lookup."""

    def test_no_module_function_takes_a_phone_number_to_look_up(self):
        import inspect

        for name, fn in inspect.getmembers(truecaller, inspect.isfunction):
            if fn.__module__ != truecaller.__name__:
                continue
            params = set(inspect.signature(fn).parameters)
            assert not ({"phone", "phone_number", "msisdn"} & params), (
                f"truecaller.{name} accepts a phone number to resolve; that is a bulk "
                "lookup, which is prohibited")

    def test_nothing_in_the_tree_calls_a_truecaller_search_api(self):
        functions = ROOT / "amplify" / "functions"
        offenders = []
        for path in functions.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in (r"search[45]?\.truecaller\.com",
                            r"/v1/search", r"truecaller.*\bsearch\b"):
                if re.search(pattern, text, re.IGNORECASE):
                    offenders.append(f"{path.relative_to(functions)}: {pattern}")
        assert not offenders, f"bulk lookup surface found: {offenders}"

    def test_only_the_profile_hosts_are_reachable(self):
        assert truecaller.ALLOWED_PROFILE_HOSTS == {
            "profile4-noneu.truecaller.com", "profile4-eu.truecaller.com"}
