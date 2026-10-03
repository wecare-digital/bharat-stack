"""Gift-card IAM, the CMK, the pinned layer and the two alarms - as OFFLINE contract tests.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
sections 5.1.1, 6, 6.5 and 10.1, plus DECISION 6 of that task's `plan.md`, and the test list in
section 9.1 (tests 101-115).

Modelled on `tests/test_provision_checkout_contract.py`: load the provisioner, read its policy
documents and its constants, and assert over those. No provisioner is run with `--apply` and no AWS
call is made.

THREE xfail(strict=True) MARKS, AND FOUR THE BRIEF NAMED THAT ARE DELIBERATELY NOT MARKED
-----------------------------------------------------------------------------------------
Marked, because their subject is a file another workstream owns and the fact they assert is ABSENT
today: 112 (SEAM-G14, `website_checkout.py`), 114 (SEAM-G7a, `finalization.py`) and 115 (SEAM-G7b,
`side_effect_guard.py`). DECISION 8: marked, never weakened, so each converts from pending to
passing the moment its producer lands and fails loudly if somebody satisfies it by lowering the bar.

**107 was the fourth and is no longer marked: SEAM-G9 has landed.** DECISION 7 assigned
`scripts/provision_checkout.py` to this task, and the shared-gate step made the whole HIGH-5 edit in
one visit, covering the coupon and gift-card tables together so there is no ordering hazard between
the two seams. `strict=True` is what made removing the mark safe to do by deletion: had the grant
not actually landed, the test would fail rather than pass quietly.

NOT marked, and each for the same reason the coupon suite left its test 52a unmarked - the property
holds TODAY and a strict mark would xpass immediately, which is a failure here AND would switch off
the one assertion that catches the hazard:

* **107a** is the half-done-seam detector. The coupon suite already owns the general subset relation
  (`tests/test_coupons_iam_and_table.py::test_the_iam_simulation_covers_every_action_the_checkout_policy_grants`,
  unmarked and passing), and the design says whichever document lands second should EXTEND that
  assertion rather than duplicate it. So this file carries the gift-card-specific IMPLICATION
  instead: if `provision_checkout.py`'s policy names the GiftCardsTable, then that ARN is in the
  simulated table list and `DeleteItem` is in `_SIMULATED_ACTIONS`. Vacuously true today, and it
  fires the moment SEAM-G9 adds the grant without extending the two hard-coded lists - which is
  exactly the half-done seam MEDIUM-18 exists to catch.
* **113** asserts `initiation.reserve` writes NO gift-card attribute. That is true today and must
  stay true: section 8.3 declares that producer out of scope, and the test exists so the omission
  stays deliberate and VISIBLE rather than becoming a silent gap. There is nothing pending about it.
* **113b** is the same gate for the FOURTH attempt producer, `blog_contribution.prepare_contribution`
  (MEDIUM-3, section 8.5). Unmarked for the identical reason: the property holds today, so a strict
  mark would xpass immediately, and the mark would switch off the only detector for a gift card
  reaching a flow that has no `wixCollectionPaise` to cap a redemption against.
* **103 / 105 / 106**-style refusals are likewise unmarked: a refusal that holds today is a gate, not
  a pending change.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

TABLE_SCRIPT = ROOT / "scripts" / "provision_gift_cards_table.py"
ROLES_SCRIPT = ROOT / "scripts" / "provision_gift_cards_roles.py"
ROUTES_SCRIPT = ROOT / "scripts" / "provision_gift_card_routes.py"
CHECKOUT_SCRIPT = ROOT / "scripts" / "provision_checkout.py"
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_all_lambdas.py"

SPI_HANDLER = ROOT / "amplify/functions/ecommerce/wix-giftcard-spi/handler.py"
GIFT_CARDS_HANDLER = ROOT / "amplify/functions/ecommerce/gift-cards/handler.py"
SPI_AUTH = ROOT / "amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py"
SHARED = ROOT / "amplify/functions/shared"

ACCOUNT = "775261844268"
GIFT_CARDS_TABLE_ARN = (f"arn:aws:dynamodb:us-east-1:{ACCOUNT}:table/"
                        "stack-wecare-digital-GiftCardsTable")
PAYMENT_ATTEMPTS_TABLE_ARN = (f"arn:aws:dynamodb:us-east-1:{ACCOUNT}:table/"
                              "stack-wecare-digital-PaymentAttemptsTable")
SHARED_FLEET_ROLE = "wecare-digital-lambda-role"
PINNED_LAYER = f"arn:aws:lambda:us-east-1:{ACCOUNT}:layer:cryptography-python312:1"

#: What the cryptography layer provides at the top level, as `deploy_all_lambdas.layer_modules`
#: would read it off the layer zip. Declared here because test 110 is the OFFLINE reproduction of
#: that gate - the point of it is that a missing layer is caught before a deploy, and reading the
#: real zip needs AWS and a function that already exists.
DECLARED_LAYER_CONTENTS = frozenset({"cryptography", "cffi", "_cffi_backend", "pycparser"})

SEAM_G14 = ("SEAM-G14: website_checkout.py is owned by the website-checkout workstream and is on "
            "this task's do-not-touch list. Marked rather than weakened per DECISION 8.")
SEAM_G7A = ("SEAM-G7(a): finalization.py passes int(attempt['amountPaise']) to "
            "record_external_payment today, which OVERSTATES the provider payment once a gift "
            "card funds part of the total. finalization.py is owned elsewhere.")
SEAM_G7B = ("SEAM-G7(b): side_effect_guard.KNOWN_EFFECTS is a 5-member frozenset validated in "
            "claim(), and side_effect_guard.py is on the do-not-touch list.")


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def roles():
    module = _load(ROLES_SCRIPT, "provision_gift_cards_roles")
    yield module
    sys.modules.pop("provision_gift_cards_roles", None)


@pytest.fixture(scope="module")
def table():
    module = _load(TABLE_SCRIPT, "provision_gift_cards_table")
    yield module
    sys.modules.pop("provision_gift_cards_table", None)


@pytest.fixture(scope="module")
def routes():
    module = _load(ROUTES_SCRIPT, "provision_gift_card_routes")
    yield module
    sys.modules.pop("provision_gift_card_routes", None)


def _docstring_ids(tree: ast.Module) -> set:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = (node.body or [None])[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _checkout_policy() -> dict:
    """`provision_checkout.py`'s inline policy document, evaluated without calling AWS.

    The same idiom `tests/test_provision_checkout_contract.py` uses: the literal interpolates the
    region, the account and a handful of constants, so it is evaluated against a namespace holding
    exactly those - plus the two table constants the two seams would add, defaulted so this works
    before and after either lands.
    """
    source = CHECKOUT_SCRIPT.read_text(encoding="utf-8")
    body = source.split("least_privilege = ")[1].split("\n    iam().put_role_policy")[0]
    checkout = _load(CHECKOUT_SCRIPT, "provision_checkout")
    namespace = {
        "REGION": checkout.REGION, "acct": ACCOUNT,
        "WIX_API_KEY_SECRET": checkout.WIX_API_KEY_SECRET,
        "PAYMENT_ATTEMPTS_TABLE": checkout.PAYMENT_ATTEMPTS_TABLE,
        "COMMERCE_KEYS_TABLE": checkout.COMMERCE_KEYS_TABLE,
        "SENDER_FUNCTION": checkout.SENDER_FUNCTION,
        "LIVE_ALIAS": checkout.LIVE_ALIAS,
        "COUPONS_TABLE": getattr(checkout, "COUPONS_TABLE",
                                 "stack-wecare-digital-CouponsTable"),
        "GIFT_CARDS_TABLE": getattr(checkout, "GIFT_CARDS_TABLE",
                                    "stack-wecare-digital-GiftCardsTable"),
        "RAZORPAY_API_SECRET": getattr(checkout, "RAZORPAY_API_SECRET",
                                       "wecare/razorpay/api"),
        "ORDERS_TABLE": getattr(checkout, "ORDERS_TABLE",
                                "stack-wecare-digital-OrderTable"),
        "CONTACTS_TABLE": getattr(checkout, "CONTACTS_TABLE",
                                  "stack-wecare-digital-ContactsTable"),
    }
    try:
        return eval(body, {"__builtins__": {}}, namespace)  # noqa: S307 - our own source
    finally:
        sys.modules.pop("provision_checkout", None)


def _checkout_simulated_tables() -> list:
    source = CHECKOUT_SCRIPT.read_text(encoding="utf-8")
    body = source.split("    tables = [", 1)[1].split("]", 1)[0]
    checkout = _load(CHECKOUT_SCRIPT, "provision_checkout")
    namespace = {
        "REGION": checkout.REGION, "acct": ACCOUNT,
        "PAYMENT_ATTEMPTS_TABLE": checkout.PAYMENT_ATTEMPTS_TABLE,
        "COMMERCE_KEYS_TABLE": checkout.COMMERCE_KEYS_TABLE,
        "COUPONS_TABLE": getattr(checkout, "COUPONS_TABLE",
                                 "stack-wecare-digital-CouponsTable"),
        "GIFT_CARDS_TABLE": getattr(checkout, "GIFT_CARDS_TABLE",
                                    "stack-wecare-digital-GiftCardsTable"),
        "RAZORPAY_API_SECRET": getattr(checkout, "RAZORPAY_API_SECRET",
                                       "wecare/razorpay/api"),
        "ORDERS_TABLE": getattr(checkout, "ORDERS_TABLE",
                                "stack-wecare-digital-OrderTable"),
        "CONTACTS_TABLE": getattr(checkout, "CONTACTS_TABLE",
                                  "stack-wecare-digital-ContactsTable"),
    }
    try:
        return eval("[" + body + "]", {"__builtins__": {}}, namespace)  # noqa: S307
    finally:
        sys.modules.pop("provision_checkout", None)


# ── 101 / 102 / 103: two roles, their own tables, no wildcards ─────────────────

def test_the_spi_function_has_its_own_role(roles):
    """Not the shared fleet role, and not shared with the issuance function either.

    Two roles rather than one because the two functions have different callers, different auth and
    different blast radius: one is internet-facing with no API Gateway authorizer, and the other
    issues liabilities.
    """
    assert roles.SPI_ROLE == "wecare-wix-giftcard-spi-role"
    assert roles.GIFT_CARDS_ROLE == "wecare-gift-cards-role"
    assert roles.SPI_ROLE != roles.GIFT_CARDS_ROLE
    assert roles.SPI_POLICY != roles.GIFT_CARDS_POLICY
    assert {name for name, *_ in roles.ROLES} == {roles.SPI_ROLE, roles.GIFT_CARDS_ROLE}


def test_each_policy_names_only_the_two_expected_table_arns(roles):
    """HIGH-5's permission half. The gift-cards role sees ONE table; the SPI role sees that table
    plus `PaymentAttemptsTable`, and nothing else."""
    own = roles.gift_cards_policy()
    spi = roles.spi_policy()

    own_tables = sorted({r for s in own["Statement"] for r in s["Resource"]
                         if ":table/" in r})
    assert own_tables == sorted([GIFT_CARDS_TABLE_ARN,
                                 GIFT_CARDS_TABLE_ARN + "/index/status-index"])

    spi_tables = sorted({r for s in spi["Statement"] for r in s["Resource"]
                         if ":table/" in r})
    assert spi_tables == sorted([GIFT_CARDS_TABLE_ARN,
                                 GIFT_CARDS_TABLE_ARN + "/index/status-index",
                                 PAYMENT_ATTEMPTS_TABLE_ARN])

    # The gift-cards role must NOT reach a payment attempt: issuance never touches one.
    assert PAYMENT_ATTEMPTS_TABLE_ARN not in own_tables


def test_no_policy_has_scan_or_a_wildcard_action(roles):
    """A grant nobody exercises is a grant nobody notices has gone wrong. Every access in
    `gift_card_store` is an exact-key operation or the `status-index` Query."""
    for document in (roles.gift_cards_policy(), roles.spi_policy()):
        actions = {a for s in document["Statement"] for a in s["Action"]}
        for forbidden in ("dynamodb:Scan", "dynamodb:*", "*", "kms:*", "secretsmanager:*",
                          "dynamodb:DeleteTable", "dynamodb:BatchWriteItem", "iam:*",
                          "lambda:*"):
            assert forbidden not in actions, f"the policy grants {forbidden}"
        for resource in (r for s in document["Statement"] for r in s["Resource"]):
            assert resource != "*", "a wildcard resource"
            assert not resource.endswith(":table/*")

        rendered = json.dumps(document)
        for shape in ("rzp_live_", "rzp_test_", "sk-", "AIza", "ghp_", "xoxb-", "AKIA", "ASIA",
                      "sk_live_", "-----BEGIN"):
            assert shape not in rendered, "the policy document carries an issuer-shaped value"


def test_the_only_secret_either_role_reads_is_the_spi_secret_and_by_name(roles):
    """One secret, both functions - because the PEPPER is the field both need, and splitting it
    would mean two secrets with overlapping contents and two rotation procedures."""
    for document in (roles.gift_cards_policy(), roles.spi_policy()):
        secrets = [r for s in document["Statement"]
                   if "secretsmanager:GetSecretValue" in s["Action"] for r in s["Resource"]]
        assert secrets == [f"arn:aws:secretsmanager:us-east-1:{ACCOUNT}:"
                           "secret:wecare/wix/giftcard-spi-*"]
    # A NAME, never a value, and the trailing `-*` is Secrets Manager's own six-character suffix.
    assert roles.SPI_SECRET == "wecare/wix/giftcard-spi"


def test_the_trust_policies_pin_the_source_account(roles):
    """Without `aws:SourceAccount` the Lambda service principal is a confused-deputy opening."""
    trust = roles.trust_policy()
    assert [((s.get("Condition") or {}).get("StringEquals") or {}).get("aws:SourceAccount")
            for s in trust["Statement"]] == [ACCOUNT]
    assert all(s["Principal"] == {"Service": "lambda.amazonaws.com"}
               for s in trust["Statement"])


# ── 104 / 105: the two asymmetries ────────────────────────────────────────────

def test_the_spi_role_cannot_issue_a_card():
    """And IAM is NOT what stops it, which is why this is an AST test rather than a policy test.

    `PutItem` on `GiftCardsTable` is identical in both roles, because the SPI must write `GCTXN#`,
    `GCTXNID#` and `GCORDER#` rows - so a permission boundary cannot distinguish issuance from a
    transaction record. The guarantee is structural: `issue` is never reached from that handler.
    """
    tree = ast.parse(SPI_HANDLER.read_text(encoding="utf-8"), filename=str(SPI_HANDLER))
    reached = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for forbidden in ("issue", "generate_code", "pin_hash", "disable", "credit"):
        assert forbidden not in reached, f"the SPI handler reaches store.{forbidden}"

    # And the issuance function DOES reach it, so the separation is a split rather than an absence.
    own = ast.parse(GIFT_CARDS_HANDLER.read_text(encoding="utf-8"),
                    filename=str(GIFT_CARDS_HANDLER))
    own_reached = {node.attr for node in ast.walk(own) if isinstance(node, ast.Attribute)}
    assert "issue" in own_reached


def test_the_spi_role_has_no_delete_item(roles):
    """Only the staff/customer function releases a `GCHOLD#` row. The SPI has no reason to delete
    anything, and a card, transaction, claim or pointer row is never deleted by either."""
    spi_actions = {a for s in roles.spi_policy()["Statement"] for a in s["Action"]}
    assert "dynamodb:DeleteItem" not in spi_actions

    own_actions = {a for s in roles.gift_cards_policy()["Statement"] for a in s["Action"]}
    assert "dynamodb:DeleteItem" in own_actions, (
        "the issuance role needs DeleteItem for GCHOLD# rows; the narrowing below item "
        "granularity is in code, not in IAM")

    # The reverse asymmetry: only the SPI may touch a payment attempt.
    spi_attempt = [s for s in roles.spi_policy()["Statement"]
                   if PAYMENT_ATTEMPTS_TABLE_ARN in s.get("Resource", [])]
    assert len(spi_attempt) == 1
    assert spi_attempt[0]["Action"] == ["dynamodb:UpdateItem"]
    assert "dynamodb:Query" not in spi_attempt[0]["Action"], (
        "both functions reach an attempt only by its exact paymentAttemptId")


def test_no_wildcard_was_added_to_the_shared_lambda_role(roles):
    """`wecare-digital-lambda-role` is attached to ~65 functions. A statement added there would
    grant every one of them access to a liability ledger.

    Over the AST rather than the text, for the same reason the vocabulary gate walks the AST: the
    paragraph explaining why the shared role must not be touched necessarily contains its name.
    """
    for script in (ROLES_SCRIPT, TABLE_SCRIPT, ROUTES_SCRIPT):
        tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        docstrings = _docstring_ids(tree)
        offenders = [f"{script.name}:{node.lineno} names the shared fleet role"
                     for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)
                     and id(node) not in docstrings and SHARED_FLEET_ROLE in node.value]
        assert not offenders, "\n  ".join(offenders)


# ── 107 / 107a: SEAM-G9, landed ───────────────────────────────────────────────

def test_the_checkout_role_gains_only_the_gift_cards_table():
    """`wecare-checkout-role` is a PER-FUNCTION role, not the shared fleet role, which is why
    extending it additively is compatible with section 10.1's objection to widening a shared role.

    The hold is taken and the redemption performed inside the checkout and finalization paths, not
    inside `wecare-gift-cards`, so without this statement neither can write at all.
    """
    policy = _checkout_policy()
    statements = [s for s in policy["Statement"]
                  if any(GIFT_CARDS_TABLE_ARN in r for r in s.get("Resource", []))]
    assert statements, "no statement names the gift-cards table"
    for statement in statements:
        actions = set(statement["Action"])
        assert actions == {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                           "dynamodb:DeleteItem"}
        assert "dynamodb:Scan" not in actions
        for resource in statement["Resource"]:
            assert not resource.endswith("*"), f"{resource} is a wildcard over the tables"


def test_the_gift_card_grant_and_its_simulation_cannot_drift_apart():
    """107a, re-pointed. See the module docstring for why it is not `xfail`.

    `provision_checkout.py --verify` is the only thing that MEASURES that role, and both of its
    lists are hard-coded - so a grant it does not simulate is granted and never measured, while the
    simulation keeps reporting a clean verdict. This is the gift-card-specific implication:
    """
    policy = _checkout_policy()
    names_gift_cards = any(GIFT_CARDS_TABLE_ARN in r
                           for s in policy["Statement"] for r in s.get("Resource", []))
    checkout = _load(CHECKOUT_SCRIPT, "provision_checkout")
    try:
        simulated_actions = set(checkout._SIMULATED_ACTIONS)
    finally:
        sys.modules.pop("provision_checkout", None)
    simulated_tables = set(_checkout_simulated_tables())

    if names_gift_cards:
        assert GIFT_CARDS_TABLE_ARN in simulated_tables, (
            "SEAM-G9 granted the GiftCardsTable without adding it to the simulated table list, "
            "so --verify now measures a role it does not cover")
        granted = {a for s in policy["Statement"] for a in s["Action"]
                   if a.startswith("dynamodb:")}
        assert granted <= simulated_actions, (
            f"granted but never simulated: {sorted(granted - simulated_actions)}")
    else:
        # Vacuous today, and deliberately asserted anyway so the implication has a live subject.
        assert GIFT_CARDS_TABLE_ARN not in simulated_tables, (
            "the table is simulated but not granted, which is the other half-done shape")


# ── 108: the table ────────────────────────────────────────────────────────────

def test_the_provisioner_asserts_ttl_disabled_and_pitr_enabled(table):
    """TTL disabled is load-bearing here in a way it is not for most tables: a gift-card row is a
    LIABILITY, and an expiring row is a disappearing debt. Asserted in `--verify` rather than merely
    left unset, so enabling it later trips a gate instead of being discovered from a gap."""
    body = TABLE_SCRIPT.read_text(encoding="utf-8").split("def verify(")[1].split("\ndef ")[0]
    assert "describe_time_to_live" in body
    assert "DISABLED" in body
    assert "PointInTimeRecoveryDescription" in body
    assert "ENABLED" in body

    create_body = (TABLE_SCRIPT.read_text(encoding="utf-8")
                   .split("def create(")[1].split("\ndef ")[0])
    assert "update_continuous_backups" in create_body
    assert "PointInTimeRecoveryEnabled" in create_body

    tree = ast.parse(TABLE_SCRIPT.read_text(encoding="utf-8"), filename=str(TABLE_SCRIPT))
    for forbidden in ("update_time_to_live", "delete_table", "delete_item", "put_item"):
        assert not [node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == forbidden], f"the provisioner calls {forbidden}"


def test_the_table_shape_is_the_documented_one(table):
    assert table.TABLE == "stack-wecare-digital-GiftCardsTable"
    assert table.KEY_ATTRIBUTE == "giftCardKey"
    assert table.INDEXES == [("status-index", [("status", "HASH"), ("createdAt", "RANGE")])]
    # Only key-participating attributes may be declared; DynamoDB rejects the rest.
    assert set(table.ATTRIBUTES) == {"giftCardKey", "status", "createdAt"}


def test_the_table_is_encrypted_with_a_customer_managed_key_named_by_alias(table):
    """DECISION 6, and the alias indirection is the part worth pinning.

    A key ARN does not exist until the key is created, so the table, the two role policies and this
    provisioner all agree on a NAME. A dated ARN in any of the four would be wrong the first time
    the key was rotated out or recreated.
    """
    assert table.KMS_ALIAS == "alias/wecare-gift-cards"
    create_body = (TABLE_SCRIPT.read_text(encoding="utf-8")
                   .split("def create(")[1].split("\ndef ")[0])
    assert "SSESpecification" in create_body
    assert '"SSEType": "KMS"' in create_body
    assert "KMSMasterKeyId" in create_body
    assert "KMS_ALIAS" in create_body

    # And it refuses to create the table before the key exists, because the fallback would be an
    # AWS-owned key and nothing would report that as a failure.
    assert "refusing to create" in create_body
    assert "find_alias()" in create_body

    # Key rotation on, and creation behind --apply as an owner-confirmation item.
    source = TABLE_SCRIPT.read_text(encoding="utf-8")
    assert "enable_key_rotation" in source
    assert "OWNER CONFIRMATION REQUIRED" in source
    assert '"--apply", action="store_true"' in source
    assert '"--verify", action="store_true"' in source


def test_the_key_policy_restricts_the_two_roles_to_dynamodb(table):
    """`kms:ViaService = dynamodb.us-east-1.amazonaws.com`.

    Without it the grant would let either function decrypt ARBITRARY ciphertext under this key,
    which is strictly wider than reading the table the key exists to encrypt. The account root keeps
    administrative control, because a key policy that locks out the account is unrecoverable.
    """
    policy = table.key_policy()
    by_sid = {s["Sid"]: s for s in policy["Statement"]}
    assert set(by_sid) == {"AccountRootAdministration", "GiftCardRolesViaDynamoDBOnly"}

    consumers = by_sid["GiftCardRolesViaDynamoDBOnly"]
    assert consumers["Condition"] == {"StringEquals": {
        "kms:ViaService": "dynamodb.us-east-1.amazonaws.com"}}
    assert set(consumers["Action"]) == {"kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"}
    assert consumers["Principal"]["AWS"] == [
        f"arn:aws:iam::{ACCOUNT}:role/wecare-gift-cards-role",
        f"arn:aws:iam::{ACCOUNT}:role/wecare-wix-giftcard-spi-role"]
    assert SHARED_FLEET_ROLE not in json.dumps(policy)
    assert table.CONSUMER_ROLES == ("wecare-gift-cards-role", "wecare-wix-giftcard-spi-role")


def test_both_role_policies_carry_the_same_kms_condition(roles):
    """The key policy and the identity policies have to agree, or the grant is unusable in one
    direction and over-broad in the other."""
    for document in (roles.gift_cards_policy("arn:aws:kms:us-east-1:x:key/abc"),
                     roles.spi_policy("arn:aws:kms:us-east-1:x:key/abc")):
        kms_statements = [s for s in document["Statement"]
                          if any(a.startswith("kms:") for a in s["Action"])]
        assert len(kms_statements) == 1
        statement = kms_statements[0]
        assert statement["Condition"] == {"StringEquals": {
            "kms:ViaService": "dynamodb.us-east-1.amazonaws.com"}}
        assert set(statement["Action"]) == {"kms:Decrypt", "kms:GenerateDataKey",
                                           "kms:DescribeKey"}
        assert statement["Resource"] == ["arn:aws:kms:us-east-1:x:key/abc"]
    assert roles.KMS_ALIAS == "alias/wecare-gift-cards"


# ── 109 / 109a: the two detectors ─────────────────────────────────────────────

def test_the_wix_spi_redemption_alarm_exists_with_a_threshold_of_one(roles):
    """Section 1.3 predicts Wix never calls our `/v1/redeem`, so a single occurrence means that
    prediction is wrong - which is why the threshold is 1 rather than a rate."""
    alarm = next(a for a in roles.ALARMS
                 if a["name"] == "wecare-gift-card-wix-spi-redemption")
    assert alarm["metric"] == "WixSpiRedemption"
    assert roles.METRIC_NAMESPACE == "WecareGiftCards"
    assert alarm["description"]

    body = ROLES_SCRIPT.read_text(encoding="utf-8").split(
        "def ensure_alarms(")[1].split("\ndef ")[0]
    assert "Threshold=1" in body
    assert 'Statistic="Sum"' in body
    assert "Period=300" in body
    assert "EvaluationPeriods=1" in body
    assert 'ComparisonOperator="GreaterThanOrEqualToThreshold"' in body

    # And the handler emits that metric, so the alarm has something to fire on.
    spi = SPI_HANDLER.read_text(encoding="utf-8")
    assert "WixSpiRedemption" in spi
    assert "gift_card_wix_spi_redemption" in spi


def test_the_charge_mismatch_alarm_exists_with_a_threshold_of_one(roles):
    """It only exists because BOTH figures are now on the attempt row: `razorpayChargedPaise` is
    what we asked the gateway for and `verifiedCapturedPaise` is what it gave. A disagreement is a
    gateway anomaly or a tampered split, and before SEAM-G13 it was unobservable."""
    alarm = next(a for a in roles.ALARMS if a["name"] == "wecare-gift-card-charge-mismatch")
    assert alarm["metric"] == "ChargedVsCapturedMismatch"
    assert len(roles.ALARMS) == 2

    from lambda_utils.ecommerce import gift_card_settlement as gcs
    assert gcs.CHECKOUT_INTENDED_PAISE_ATTR == "razorpayChargedPaise"
    assert gcs.RAZORPAY_VERIFIED_PAISE_ATTR == "verifiedCapturedPaise"
    assert gcs.CHECKOUT_INTENDED_PAISE_ATTR not in gcs.EVIDENCE_KEYS
    assert gcs.RAZORPAY_VERIFIED_PAISE_ATTR not in gcs.EVIDENCE_KEYS


# ── 110 / 111: the layer ──────────────────────────────────────────────────────

def test_the_spi_handlers_top_level_imports_are_covered_by_its_layers():
    """HIGH-6's failure mode, caught OFFLINE.

    `scripts/deploy_all_lambdas.py` resolves every top-level import against the package plus the
    function's LIVE layer list and fails with
    `"{arcname}:{lineno} imports '{root}', not in package or layers"`. A new function has NO layers
    attached until a provisioner attaches them, because the gate reads `current.get("Layers")` off
    the live function - so without this test the deploy gate would be the first place a missing
    `cryptography` layer was discovered, and `--dry-run` cannot pass for a function that does not
    exist yet.

    Reproduced here against a DECLARED layer set, using the same resolution rule: the package's own
    modules, the runtime-provided set, the standard library, and the layer.
    """
    deploy = _load(DEPLOY_SCRIPT, "deploy_all_lambdas")
    try:
        runtime_provided = set(deploy.RUNTIME_PROVIDED)
    finally:
        sys.modules.pop("deploy_all_lambdas", None)

    # What the packaged function would carry: handler.py plus the shared package's top level.
    packaged = {"handler"} | {path.stem for path in SHARED.glob("*.py")} \
        | {path.name for path in SHARED.iterdir() if path.is_dir()}
    known = (packaged | runtime_provided | set(sys.stdlib_module_names)
             | DECLARED_LAYER_CONTENTS)

    unresolved = []
    for path in (SPI_HANDLER, SPI_AUTH, GIFT_CARDS_HANDLER):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [(alias.name.split(".")[0], node.lineno) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                roots = [((node.module or "").split(".")[0], node.lineno)]
            else:
                continue
            for root, lineno in roots:
                if root and root not in known:
                    unresolved.append(f"{path.name}:{lineno} imports '{root}', "
                                      f"not in package or layers")
    assert not unresolved, "\n  ".join(unresolved)

    # And the thing that makes the layer necessary rather than incidental: the verifier imports
    # `cryptography`, which the standard library cannot replace - Python cannot verify an RSA
    # signature without it.
    auth_source = SPI_AUTH.read_text(encoding="utf-8")
    assert "from cryptography" in auth_source
    assert "cryptography" not in set(sys.stdlib_module_names)
    assert "cryptography" in DECLARED_LAYER_CONTENTS


def test_the_provisioner_attaches_the_pinned_cryptography_layer(roles):
    """Version PINNED to `:1`.

    A layer version is immutable, so pinning means the verifier's crypto implementation cannot change
    under it without a deliberate edit. A floating reference would let a layer republish alter
    signature verification on a payment route with no code change and no review.
    """
    assert roles.CRYPTOGRAPHY_LAYER_ARN == PINNED_LAYER
    assert roles.CRYPTOGRAPHY_LAYER_ARN.endswith(":1")
    assert not roles.CRYPTOGRAPHY_LAYER_ARN.endswith(("$LATEST", ":*"))

    body = ROLES_SCRIPT.read_text(encoding="utf-8").split(
        "def ensure_layer(")[1].split("\ndef ")[0]
    assert "update_function_configuration" in body
    assert "CRYPTOGRAPHY_LAYER_ARN" in body
    # Additive: `update-function-configuration` REPLACES the layer list, so the existing ones are
    # preserved rather than dropped.
    assert "set(attached)" in body
    assert roles.SPI_FUNCTION == "wecare-wix-giftcard-spi"


def test_the_route_provisioner_creates_eight_routes_across_two_integrations(routes):
    """Three SPI paths plus five of our own, and the file is named for all eight (NIT-3)."""
    assert len(routes.SPI_ROUTE_KEYS) == 3
    assert len(routes.OWN_ROUTE_KEYS) == 5
    assert ROUTES_SCRIPT.name == "provision_gift_card_routes.py"
    assert not (ROOT / "scripts" / "provision_gift_card_spi_routes.py").exists()

    for key in routes.OWN_ROUTE_KEYS + routes.SPI_ROUTE_KEYS:
        assert "{code}" not in key, "a route template carries a gift-card code"
        assert not key.startswith("DELETE ")
    for forbidden in ("POST /gift-cards/hold", "POST /gift-cards/release"):
        assert forbidden not in routes.OWN_ROUTE_KEYS

    # Both integrations target the alias, never `$LATEST`.
    for function, *_ in routes.PLAN:
        assert routes.function_arn(function).endswith(":live")
    # Over the AST: the paragraph explaining why the alias and not `$LATEST` necessarily names it.
    route_tree = ast.parse(ROUTES_SCRIPT.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(route_tree)
    assert not [node.lineno for node in ast.walk(route_tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and "$LATEST" in node.value]
    assert routes.LIVE_ALIAS == "live"

    # Additive only: 361 pre-existing routes belong to other functions.
    tree = ast.parse(ROUTES_SCRIPT.read_text(encoding="utf-8"), filename=str(ROUTES_SCRIPT))
    for forbidden in ("delete_route", "delete_integration", "update_route",
                      "update_integration"):
        assert not [node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == forbidden], f"the provisioner calls {forbidden}"


def test_every_provisioner_defaults_to_a_dry_run_and_verifies_what_it_wrote():
    """A provisioner that writes and does not read back has measured nothing, and a run that
    measured nothing must not be indistinguishable from a clean one."""
    for script in (TABLE_SCRIPT, ROLES_SCRIPT, ROUTES_SCRIPT):
        source = script.read_text(encoding="utf-8")
        assert '"--apply", action="store_true"' in source, script.name
        assert '"--verify", action="store_true"' in source, script.name
        assert "dry run: nothing changed" in source, script.name
        verify_body = source.split("def verify(")[1].split("\ndef ")[0]
        assert "problems" in verify_body, script.name
        assert "return 1" in verify_body, script.name


# ── 112 / 113: the two attempt producers ──────────────────────────────────────

@pytest.mark.xfail(strict=True, reason=SEAM_G14)
def test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately():
    """HIGH-1, and the test that catches BOTH obvious wrong resolutions of it.

    `binding["amountPaise"] == payNowPaise` (or line 434 refuses every capture as a
    `BINDING_MISMATCH`), `attempt["amountPaise"] == quote.total_payable_paise` (or
    `is_fully_settled`'s closure has nothing to close against and a gift-card order reads as settled
    on the Razorpay leg alone), and `attempt["razorpayChargedPaise"] == payNowPaise` for the audit
    record.

    The fourth clause is MEDIUM-2's, and it is the one the split table added three rows for:
    `options["amountPaise"] == payNowPaise`. `_browser_options` builds that field from its
    `amount_paise` keyword, so the figure Razorpay Standard Checkout PRESENTS to the browser is
    whatever that call site passes. Today `payment_attempt.build` and `_browser_options` are handed
    the SAME `amount_paise` local, and section 8 mandates `build` keep the full payable - so the two
    arguments must diverge or the customer is shown a price nobody is charging. Asserted as that
    divergence rather than as a string, because the string `payNowPaise` could be satisfied by
    naming the variable without routing it to the browser.
    """
    source = (ROOT / "amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py"
              ).read_text(encoding="utf-8")
    assert "razorpayChargedPaise" in source, (
        "the website producer does not record the gateway figure, so nothing distinguishes the "
        "charged amount from the payable")
    assert "giftCard" in source
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "pay_now_paise" in names or "payNowPaise" in source

    # MEDIUM-2: the browser figure and the attempt figure cannot be the same expression.
    #
    # Scoped to the function that calls `payment_attempt.build`, because `_browser_options` has TWO
    # call sites and only this one is in scope. The other is `_ready_from_binding`, which reads the
    # amount back off the binding - MEDIUM-2 lists it as NEEDS NO CHANGE, and asserting pay-now there
    # would either double-apply the split or make this mark unclearable. Its no-change state is
    # asserted below, so "no edit" stays the deliberate answer rather than reading as an oversight.
    def _amount_args(scope, predicate):
        found = []
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call) or not predicate(node.func):
                continue
            found += [ast.unparse(keyword.value) for keyword in node.keywords
                      if keyword.arg == "amount_paise"]
        return found

    is_build = lambda func: isinstance(func, ast.Attribute) and func.attr == "build"
    is_browser = lambda func: isinstance(func, ast.Name) and func.id == "_browser_options"

    producers = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and _amount_args(node, is_build)]
    assert producers, "no function passes amount_paise to payment_attempt.build"
    for producer in producers:
        built = set(_amount_args(producer, is_build))
        browser = set(_amount_args(producer, is_browser))
        assert browser, f"{producer.name} builds an attempt but no browser options"
        assert not (browser & built), (
            f"in {producer.name}, _browser_options and payment_attempt.build are handed the same "
            f"amount expression {sorted(browser & built)}, so options['amountPaise'] is the payable "
            f"and the browser is shown a price that is not being charged")
        assert all("pay_now" in argument for argument in browser), (
            f"in {producer.name} the browser amount comes from {sorted(browser)} rather than from "
            f"the pay-now figure")

    resume = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
              and node.name == "_ready_from_binding"]
    assert resume, "_ready_from_binding is gone, so MEDIUM-2's NEEDS NO CHANGE row is stale"
    assert all("binding" in argument for argument in _amount_args(resume[0], is_browser)), (
        "the resume path no longer reads its amount off the binding, so the split is either "
        "double-applied or the payable is back on the resumed browser options")


def test_the_initiation_reserve_path_writes_no_gift_card_attribute():
    """113, and deliberately NOT `xfail` - see the module docstring.

    Section 8.3 declares `initiation.reserve` out of scope on three grounds: it is untracked with no
    caller in `amplify/`, it consumes a pre-computed `snapshot['amountPaise']` rather than a
    `CheckoutQuote` so it has no fee to split against, and it is gated on
    `CHECKOUT_INITIATION_ENABLED` which this change does not enable.

    The consequence is named rather than left implicit: if `reserve` ever becomes a live producer, a
    gift card applied through it will behave as revision 2's design did on the website path - the
    gateway amount unreduced. This test is what keeps that omission deliberate and VISIBLE.
    """
    initiation = ROOT / "amplify/functions/shared/lambda_utils/ecommerce/initiation.py"
    if not initiation.exists():          # pragma: no cover - the module is untracked in git
        pytest.skip("initiation.py is not present in this tree")
    source = initiation.read_text(encoding="utf-8")
    for attribute in ("giftCardStageRank", "giftCardRequiredPaise", "giftCardCodeHash",
                      "giftCardRedeemedPaise", "giftCardTransactionId",
                      "razorpayChargedPaise"):
        assert attribute not in source, (
            f"initiation.reserve writes {attribute}, so section 8.3's out-of-scope decision is no "
            f"longer true and the split table must be applied there too")


def test_the_blog_contribution_path_writes_no_gift_card_attribute():
    """113b, MEDIUM-3's fourth attempt producer, and deliberately NOT `xfail`.

    Revision 3 enumerated THREE `payment_attempt.build` call sites and called the enumeration
    measured; there are four. The fourth is `blog_contribution.prepare_contribution`, whose own
    docstring calls itself a sibling of `website_checkout` - which is the strongest available hint
    that an enumeration stopping at three was not one.

    Section 8.5 declares it out of scope, and the ground is arithmetic rather than effort: a
    contribution flow has NO Wix cart, so there is no `wixCollectionPaise` for
    `gift_card_store.redeem_cap` to cap against. HIGH-4 exists precisely to stop that cap being taken
    against anything else, and a gift card is a liability - an undefined cap spends real money on a
    path nobody designed. Section 4.2's six reconciliation identities are likewise all stated against
    a Wix cart summary, so with no summary the refusal that protects every other path would not run.

    Unmarked, exactly like 113: the property holds today, so `xfail(strict=True)` would xpass
    immediately AND would switch off the only thing that notices when it stops holding. This is the
    gate that keeps "a gift card cannot reach producer #4" true rather than merely stated.
    """
    contribution = (ROOT
                    / "amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py")
    source = contribution.read_text(encoding="utf-8")
    for attribute in ("giftCardStageRank", "giftCardRequiredPaise", "giftCardCodeHash",
                      "giftCardRedeemedPaise", "giftCardTransactionId",
                      "razorpayChargedPaise"):
        assert attribute not in source, (
            f"blog_contribution.prepare_contribution writes {attribute}, so section 8.5's "
            f"out-of-scope decision is no longer true: a gift card now reaches a producer with no "
            f"wixCollectionPaise to cap the redemption against")


# ── 114 / 115: SEAM-G7 ────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason=SEAM_G7A)
def test_no_recorded_payment_exceeds_the_verified_capture_for_its_transaction_id():
    """MEDIUM-15, with the direction corrected.

    Revision 2 said the risk was a SHORT payment. Measured, it runs the other way:
    `finalization.py` passes `int(attempt['amountPaise'])` - which section 8 MANDATES stay the full
    payable - so the Wix order would record a payment of the full payable attributed to a Razorpay
    transaction that captured only `payNowPaise`. That is an OVERSTATED provider payment: a record
    claiming Razorpay collected money it did not.
    """
    finalization = ROOT / "amplify/functions/shared/lambda_utils/ecommerce/finalization.py"
    if not finalization.exists():        # pragma: no cover - the module is untracked in git
        pytest.skip("finalization.py is not present in this tree")
    source = finalization.read_text(encoding="utf-8")
    tree = ast.parse(source)
    call = next(node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "record_external_payment")
    amount = next(keyword.value for keyword in call.keywords
                  if keyword.arg == "amount_paise")
    rendered = ast.unparse(amount)
    assert "verifiedCapturedPaise" in rendered or "RAZORPAY_VERIFIED_PAISE_ATTR" in rendered, (
        f"record_external_payment is given {rendered}, which overstates the provider payment "
        f"whenever a gift card funds part of the total")


@pytest.mark.xfail(strict=True, reason=SEAM_G7B)
def test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment():
    """SEAM-G7(b). A second tender record cannot ride on the existing claim.

    `side_effect_guard` allows ONE `WIX_PAYMENT` claim per `order_id`, bound to four fields, and
    `wix_writeback` RAISES when a later call presents a different binding - so a gift-card tender
    offered under `WIX_PAYMENT` would be read as a contradicting retry of the Razorpay payment and
    would refuse. `KNOWN_EFFECTS` is a `frozenset` validated in `claim()`, so the new constant has to
    be added there or the claim is refused outright.
    """
    from lambda_utils.ecommerce import side_effect_guard

    assert hasattr(side_effect_guard, "WIX_GIFT_CARD_TENDER")
    assert side_effect_guard.WIX_GIFT_CARD_TENDER in side_effect_guard.KNOWN_EFFECTS
    assert side_effect_guard.WIX_GIFT_CARD_TENDER != side_effect_guard.WIX_PAYMENT


def test_the_existing_five_known_effects_are_unchanged():
    """114/115's unconditional companion: the seam must ADD an effect, never repurpose one.

    `WIX_CART_COMPLETED`'s own comment sets the precedent - "Its own effect rather than folded into
    `WIX_ORDER` because it is a separate remote call" - which is exactly the gift-card tender's
    situation: a second `add-payment` call with a different tender.
    """
    from lambda_utils.ecommerce import side_effect_guard

    for effect in (side_effect_guard.WIX_ORDER, side_effect_guard.WIX_PAYMENT,
                   side_effect_guard.WIX_CART_COMPLETED, side_effect_guard.RECEIPT,
                   side_effect_guard.CONFIRMATION):
        assert effect in side_effect_guard.KNOWN_EFFECTS
    assert isinstance(side_effect_guard.KNOWN_EFFECTS, frozenset)


# ── the drift allowance is DEPENDED ON, not duplicated ─────────────────────────

def test_the_gift_cards_table_name_follows_the_drift_script_default_rule():
    """`GiftCard -> GiftCardsTable` under `check_data_model_drift`'s pluralise-and-append rule, so no
    `EXPLICIT_TABLE` entry is needed. A name that needs an exception recorded is a name that will be
    got wrong later.

    The `UNDECLARED_ALLOWED` entry itself is asserted by the coupon suite's test 57, because that
    document owns the single edit adding BOTH entries - one file, edited once, by one session.
    """
    drift = _load(ROOT / "scripts" / "check_data_model_drift.py", "check_data_model_drift")
    try:
        assert drift.expected_table("GiftCard") == "GiftCardsTable"
        assert "GiftCard" not in drift.EXPLICIT_TABLE
    finally:
        sys.modules.pop("check_data_model_drift", None)


def test_the_three_scripts_and_the_store_module_agree_on_the_table_and_the_index(roles, table):
    """Four files name the same table and the same index. A disagreement means a function is granted
    access to a table it does not use, or queries an index that was never created - and the second
    returns an empty result set in production rather than an error."""
    from lambda_utils.ecommerce import gift_card_store as gc

    assert gc.DEFAULT_TABLE_NAME == table.TABLE == roles.GIFT_CARDS_TABLE
    assert gc.STATUS_INDEX == table.INDEXES[0][0] == roles.STATUS_INDEX
    assert gc.KEY_ATTRIBUTE == table.KEY_ATTRIBUTE
    assert gc.SECRET_ID == roles.SPI_SECRET
    assert table.KMS_ALIAS == roles.KMS_ALIAS
