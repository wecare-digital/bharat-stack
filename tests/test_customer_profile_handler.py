"""Authenticated checkout profile safely converges into Workspace Contacts."""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeDynamo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HANDLER_PATH = ROOT / "amplify/functions/auth/customer-profile/handler.py"

OTP_TABLE = "stack-wecare-digital-DownloadGrantsTable"
CONTACTS_TABLE = "stack-wecare-digital-ContactsTable"
CUSTOMER = "CUS_01J0000000000000000000000"
PHONE = "+919330994400"
EMAIL = "asha@example.com"
PEPPER = "profile-test-pepper"


class Identity:
    def __init__(self, customer_id=CUSTOMER, phone=PHONE):
        self.customer_id = customer_id
        self.phone = phone
        self.subject = "sub-1"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("OTP_TABLE", OTP_TABLE)
    monkeypatch.setenv("CONTACTS_TABLE", CONTACTS_TABLE)
    monkeypatch.setenv("APP_ENV", "development")

    spec = importlib.util.spec_from_file_location("customer_profile_under_test", HANDLER_PATH)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)

    fake = FakeDynamo(
        keys={OTP_TABLE: "grantId", CONTACTS_TABLE: "id"},
        indexes={CONTACTS_TABLE: {
            "phone-index": ("phone", None),
            "email-index": ("email", None),
        }},
    )
    monkeypatch.setattr(h, "_dynamodb", fake)
    monkeypatch.setattr(h, "_pepper", lambda: PEPPER)
    monkeypatch.setattr(h.customer_auth, "require_customer",
                        lambda event: (Identity(), None))
    return h, fake, monkeypatch


def event(**body):
    return {
        "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.7"}},
        "headers": {"origin": "http://localhost:3000", "authorization": "Bearer test"},
        "body": json.dumps(body),
    }


def proof(h, fake, email=EMAIL):
    token = "proof-fixture"
    now = int(time.time())
    fake.Table(OTP_TABLE).put_item(Item={
        "grantId": h.PROOF_PREFIX + token,
        "purpose": h.PROOF_PURPOSE,
        "subjectDigest": h._proof_digest(email),
        "createdAt": now,
        "expiresAt": now + 600,
    })
    return token


def test_requires_authenticated_customer(env):
    h, _fake, monkeypatch = env
    denied = {"statusCode": 401, "headers": {}, "body": "{}"}
    monkeypatch.setattr(h.customer_auth, "require_customer",
                        lambda event: (None, denied))
    resp = h.handler(event(firstName="Asha", lastName="Sen", email=EMAIL,
                           emailProof="x"), None)
    assert resp["statusCode"] == 401


def test_rejects_unexpected_browser_fields(env):
    h, fake, _ = env
    token = proof(h, fake)
    resp = h.handler(event(
        firstName="Asha", lastName="Sen", email=EMAIL, emailProof=token,
        phone="+919999999999", tags=["VIP"], optInEmail=True,
    ), None)
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "UNEXPECTED_FIELD"
    assert fake.count(CONTACTS_TABLE) == 0


def test_email_proof_is_bound_to_exact_email(env):
    h, fake, _ = env
    token = proof(h, fake, EMAIL)
    resp = h.handler(event(
        firstName="Asha", lastName="Sen", email="other@example.com", emailProof=token,
    ), None)
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "EMAIL_VERIFICATION_REQUIRED"
    assert fake.count(CONTACTS_TABLE) == 0


def test_creates_workspace_contact_from_session_phone_without_marketing_consent(env):
    h, fake, _ = env
    token = proof(h, fake)
    resp = h.handler(event(
        firstName="Asha", lastName="Sen", email=EMAIL, emailProof=token,
    ), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "PROFILE_READY"
    assert body["phone"] == PHONE

    rows = fake.all_rows(CONTACTS_TABLE)
    assert len(rows) == 1
    row = rows[0]
    assert row["phone"] == PHONE
    assert row["email"] == EMAIL
    assert row["name"] == "Asha Sen"
    assert row["checkoutCustomerId"] == CUSTOMER
    assert row["tags"] == ["Customer"]
    assert row["phoneVerifiedAt"] and row["emailVerifiedAt"]
    assert row["optInWhatsApp"] is False
    assert row["optInEmail"] is False
    assert row["optInSms"] is False
    assert row["allowlistWhatsApp"] is False
    assert row["allowlistEmail"] is False
    assert row["allowlistSms"] is False


def test_merges_existing_phone_contact_and_preserves_explicit_consent(env):
    h, fake, _ = env
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": "contact-1", "contactId": "contact-1",
        "phone": PHONE, "email": "old@example.com", "name": "Asha",
        "tags": ["VIP"], "optInEmail": True, "allowlistEmail": True,
        "createdAt": 1, "updatedAt": 1, "deletedAt": None,
    })
    token = proof(h, fake)
    resp = h.handler(event(
        firstName="Asha", lastName="Sen", email=EMAIL, emailProof=token,
    ), None)
    assert resp["statusCode"] == 200
    assert fake.count(CONTACTS_TABLE) == 1
    row = fake.all_rows(CONTACTS_TABLE)[0]
    assert row["id"] == "contact-1"
    assert set(row["tags"]) == {"VIP", "Customer"}
    assert row["optInEmail"] is True
    assert row["allowlistEmail"] is True


def test_refuses_to_merge_phone_and_email_that_belong_to_two_contacts(env):
    h, fake, _ = env
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": "phone-contact", "contactId": "phone-contact",
        "phone": PHONE, "email": "old@example.com", "tags": [], "deletedAt": None,
    })
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": "email-contact", "contactId": "email-contact",
        "phone": "+919999999999", "email": EMAIL, "tags": [], "deletedAt": None,
    })
    token = proof(h, fake)
    resp = h.handler(event(
        firstName="Asha", lastName="Sen", email=EMAIL, emailProof=token,
    ), None)
    assert resp["statusCode"] == 409
    assert json.loads(resp["body"])["error"] == "CONTACT_IDENTITY_CONFLICT"
    assert fake.count(CONTACTS_TABLE) == 2
