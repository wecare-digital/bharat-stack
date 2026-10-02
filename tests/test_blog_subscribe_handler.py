"""Verified blog subscription writes only to Workspace Contacts, never Cognito."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeDynamo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HANDLER_PATH = ROOT / "amplify/functions/auth/blog-subscribe/handler.py"
PROVISION_PATH = ROOT / "scripts/provision_blog_subscribe.py"

OTP_TABLE = "stack-wecare-digital-DownloadGrantsTable"
CONTACTS_TABLE = "stack-wecare-digital-ContactsTable"
PEPPER = "test-blog-pepper-not-a-secret"
PHONE = "+919330994400"
EMAIL = "asha@example.com"


class _FakePayload:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class _FakeLambda:
    def __init__(self):
        self.invocations = []

    def invoke(self, FunctionName=None, InvocationType=None, Payload=None, **_):
        event = json.loads(Payload.decode("utf-8"))
        self.invocations.append({"FunctionName": FunctionName, "event": event})
        return {"Payload": _FakePayload(json.dumps({"statusCode": 200, "body": "{}"}).encode())}


class _FakeSes:
    def __init__(self):
        self.sent = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "blog-email-1"}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("OTP_TABLE", OTP_TABLE)
    monkeypatch.setenv("CONTACTS_TABLE", CONTACTS_TABLE)
    monkeypatch.setenv("APP_ENV", "development")

    spec = importlib.util.spec_from_file_location("blog_subscribe_under_test", HANDLER_PATH)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)

    fake = FakeDynamo(
        keys={OTP_TABLE: "grantId", CONTACTS_TABLE: "id"},
        indexes={CONTACTS_TABLE: {
            "phone-index": ("phone", None),
            "email-index": ("email", None),
        }},
    )
    lam = _FakeLambda()
    ses = _FakeSes()
    monkeypatch.setattr(h, "_dynamodb", fake)
    monkeypatch.setattr(h, "_pepper", lambda: PEPPER)
    monkeypatch.setattr(h, "_lambda_client", lambda: lam)
    monkeypatch.setattr(h, "_ses_client", lambda: ses)
    return h, fake, lam, ses


def _event(action, ip="203.0.113.5", **body):
    return {
        "requestContext": {"http": {"method": "POST", "sourceIp": ip, "apiId": "zllr9lrg7j"}},
        "headers": {"origin": "http://localhost:3000"},
        "body": json.dumps({"action": action, **body}),
    }


def _wa_code(lam):
    inner = json.loads(lam.invocations[-1]["event"]["body"])
    return inner["components"][0]["parameters"][0]["text"]


def _email_code(ses):
    text = ses.sent[-1]["Content"]["Simple"]["Body"]["Text"]["Data"]
    for token in text.split():
        if token.isdigit() and len(token) == 6:
            return token
    raise AssertionError("email OTP not found")


def _proofs(h, lam, ses):
    assert h.handler(_event("phone_request", phone=PHONE), None)["statusCode"] == 200
    phone_verified = h.handler(
        _event("phone_verify", phone=PHONE, code=_wa_code(lam)), None)
    assert phone_verified["statusCode"] == 200
    phone_proof = json.loads(phone_verified["body"])["proof"]

    assert h.handler(_event(
        "email_request", email=EMAIL, phone=PHONE, firstName="Asha"), None)["statusCode"] == 200
    email_verified = h.handler(
        _event("email_verify", email=EMAIL, code=_email_code(ses)), None)
    assert email_verified["statusCode"] == 200
    email_proof = json.loads(email_verified["body"])["proof"]
    return phone_proof, email_proof


def test_subscribe_requires_both_server_proofs(env):
    h, fake, _lam, _ses = env
    resp = h.handler(_event(
        "subscribe", firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof="made-up", emailProof="made-up",
    ), None)
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"] == "VERIFICATION_REQUIRED"
    assert fake.count(CONTACTS_TABLE) == 0


def test_verified_subscription_creates_workspace_contact_with_forced_tag(env):
    h, fake, lam, ses = env
    phone_proof, email_proof = _proofs(h, lam, ses)
    resp = h.handler(_event(
        "subscribe", firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof=phone_proof, emailProof=email_proof,
        tags=["VIP"], optInSms=True,
    ), None)
    assert resp["statusCode"] == 200
    row = fake.all_rows(CONTACTS_TABLE)[0]
    assert row["id"] == row["contactId"]
    assert row["name"] == "Asha Sen"
    assert row["phone"] == PHONE and row["email"] == EMAIL
    assert row["tags"] == ["blog-subscriber"]
    assert row["phoneVerifiedAt"] and row["emailVerifiedAt"] and row["blogSubscribedAt"]
    assert row["optInWhatsApp"] is True and row["optInEmail"] is True
    assert row["optInSms"] is False and row["allowlistSms"] is False


def test_replay_is_idempotent_and_updates_one_contact(env):
    h, fake, lam, ses = env
    phone_proof, email_proof = _proofs(h, lam, ses)
    body = dict(
        firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof=phone_proof, emailProof=email_proof,
    )
    assert h.handler(_event("subscribe", **body), None)["statusCode"] == 200
    assert h.handler(_event("subscribe", **body), None)["statusCode"] == 200
    assert fake.count(CONTACTS_TABLE) == 1
    assert fake.all_rows(CONTACTS_TABLE)[0]["tags"].count("blog-subscriber") == 1


def test_existing_contact_is_merged_not_duplicated(env):
    h, fake, lam, ses = env
    existing_id = "contact-1"
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": existing_id, "contactId": existing_id, "name": "Asha",
        "phone": PHONE, "email": EMAIL, "tags": ["Customer"], "createdAt": 1,
        "updatedAt": 1, "deletedAt": None,
    })
    phone_proof, email_proof = _proofs(h, lam, ses)
    resp = h.handler(_event(
        "subscribe", firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof=phone_proof, emailProof=email_proof,
    ), None)
    assert resp["statusCode"] == 200
    assert fake.count(CONTACTS_TABLE) == 1
    row = fake.all_rows(CONTACTS_TABLE)[0]
    assert row["id"] == existing_id
    assert set(row["tags"]) == {"Customer", "blog-subscriber"}
    assert row["phoneVerifiedAt"] and row["emailVerifiedAt"]


def test_phone_and_email_on_different_contacts_fail_without_merging(env):
    h, fake, lam, ses = env
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": "phone-row", "contactId": "phone-row", "phone": PHONE,
        "email": "other@example.com", "tags": [], "deletedAt": None,
    })
    fake.Table(CONTACTS_TABLE).put_item(Item={
        "id": "email-row", "contactId": "email-row", "phone": "+919999999999",
        "email": EMAIL, "tags": [], "deletedAt": None,
    })
    phone_proof, email_proof = _proofs(h, lam, ses)
    resp = h.handler(_event(
        "subscribe", firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof=phone_proof, emailProof=email_proof,
    ), None)
    assert resp["statusCode"] == 409
    assert json.loads(resp["body"])["error"] == "SUBSCRIPTION_CONFLICT"
    assert fake.count(CONTACTS_TABLE) == 2


def test_contact_lookup_failure_fails_closed_instead_of_creating_duplicate(env):
    h, fake, lam, ses = env
    phone_proof, email_proof = _proofs(h, lam, ses)
    fake.arm_failure(CONTACTS_TABLE, "query", RuntimeError("dynamo unavailable"))
    resp = h.handler(_event(
        "subscribe", firstName="Asha", lastName="Sen", phone=PHONE, email=EMAIL,
        phoneProof=phone_proof, emailProof=email_proof,
    ), None)
    assert resp["statusCode"] == 500
    assert fake.count(CONTACTS_TABLE) == 0


def test_subscription_path_has_no_cognito_capability():
    handler = HANDLER_PATH.read_text(encoding="utf-8").lower()
    provision = PROVISION_PATH.read_text(encoding="utf-8").lower()
    assert "cognito-idp" not in handler
    assert "admin_create_user" not in handler
    assert "cognito-idp" not in provision
    assert "admincreateuser" not in provision
