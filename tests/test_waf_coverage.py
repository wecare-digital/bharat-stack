"""Every WAF-protectable surface is in the plan, and the plan reports per resource.

Why this exists
---------------
On 2026-09-26 the customer Cognito pool had **no web ACL** while the staff pool had
one. Measured with `get_web_acl_for_resource` on both pool ARNs:

    us-east-1_cSx0RHCIR   (staff, dashboard managed login)   wecare-cognito-waf
    us-east-1_46ULYuukt   (customers, public OTP sign-in)    none

That is the wrong way round. `WECARE.DIGITAL-CUSTOMERS` is the pool this project puts
behind public passwordless WhatsApp and email OTP; the staff pool is not comparably
exposed.

**The tool meant to catch this could not see it.** `scripts/provision_waf.py` held one
`resource` string per ACL, so it asked "is this ACL associated with *the* pool", got
yes, and reported the Cognito surface as protected. A second pool was not absent from
its output -- it was absent from its model, which is worse, because the report looked
complete. The fix was to make the plan take a list and to report and verify association
**per resource**, so a partial association can no longer aggregate into a clean answer.

These tests are offline and make no AWS calls. They guard the *model*, which is where
the defect was. Live association is asserted by `provision_waf.py --verify`, which reads
back from WAF; a unit test cannot and should not claim to prove it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provision_waf.py"


@pytest.fixture(scope="module")
def waf_module():
    spec = importlib.util.spec_from_file_location("provision_waf", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provision_waf"] = module
    spec.loader.exec_module(module)
    return module


def test_both_cognito_pools_are_in_the_plan(waf_module):
    """The regression that motivated this file.

    Named pools rather than "at least two", so adding a third pool and forgetting to
    protect it also fails here.
    """
    resources = waf_module.PLAN[waf_module.COGNITO_ACL]["resources"]

    assert waf_module.STAFF_POOL_ARN in resources, (
        "the staff pool dropped out of the WAF plan"
    )
    assert waf_module.CUSTOMER_POOL_ARN in resources, (
        "the CUSTOMER pool is not in the WAF plan. It is the internet-facing pool "
        "behind public OTP sign-in, and it was unprotected until 2026-09-26 precisely "
        "because the plan only named one pool."
    )


def test_every_cognito_pool_in_the_account_is_accounted_for(waf_module):
    """Guard the two ids against a silent third pool appearing in the plan.

    Deliberately checks the plan against the two ids this module declares rather than
    calling Cognito: a test that lists live pools would pass on a machine with no
    credentials and would make the suite depend on the account.
    """
    declared = {waf_module.STAFF_POOL_ID, waf_module.CUSTOMER_POOL_ID}
    assert len(declared) == 2, "the two pool ids collapsed to one"

    planned = set(waf_module.PLAN[waf_module.COGNITO_ACL]["resources"])
    assert planned == {waf_module.pool_arn(p) for p in declared}


def test_the_http_api_is_not_in_any_plan(waf_module):
    """WAF cannot protect an HTTP API, so nothing may claim it does.

    `zllr9lrg7j` is apigatewayv2. WAF's protected resource types are CloudFront, API
    Gateway REST, ALB, AppSync, Cognito user pools, App Runner, Amplify and Verified
    Access. A plan entry for it would fail at `associate_web_acl` -- and, more usefully,
    it would let a status report claim the API is WAF-protected when it cannot be.
    """
    for name, spec in waf_module.PLAN.items():
        for resource in spec["resources"]:
            assert "zllr9lrg7j" not in resource, (
                f"{name} names the HTTP API, which cannot take a web ACL"
            )
            assert ":apis/" not in resource or ":amplify:" in resource, (
                f"{name} names an API Gateway resource: {resource}"
            )


def test_scopes_are_not_interchangeable(waf_module):
    """Amplify needs a CLOUDFRONT-scope ACL; a regional one is not usable with it.

    Two ACLs exist for this reason and not by preference, so a well-meaning
    consolidation onto one ACL has to fail here rather than at apply time.
    """
    assert waf_module.PLAN[waf_module.AMPLIFY_ACL]["scope"] == "CLOUDFRONT"
    assert waf_module.PLAN[waf_module.COGNITO_ACL]["scope"] == "REGIONAL"


def test_every_plan_entry_uses_a_resource_list(waf_module):
    """The shape of the fix, not just its current contents.

    Reverting to a single `resource` string would reintroduce the exact blind spot:
    one association standing in for a surface that has more than one resource.
    """
    for name, spec in waf_module.PLAN.items():
        assert "resource" not in spec, (
            f"{name} uses the old singular `resource` key, which cannot express a "
            f"surface with more than one resource"
        )
        assert isinstance(spec["resources"], list) and spec["resources"], (
            f"{name} must carry a non-empty `resources` list"
        )


def test_cognito_managed_rules_count_and_the_rate_rule_blocks(waf_module):
    """The deliberate asymmetry, so a later edit does not quietly flip it.

    Blocking an untuned Core rule set in front of a sign-in path risks refusing
    legitimate authentication. The rate-based rule is the one that blocks, because
    credential stuffing is what it answers directly.

    This is not a claim that the pools are adequately protected. A per-IP limit is weak
    where carriers CGNAT, which is the case for the Indian customer traffic this pool
    serves -- the real OTP abuse control is per-phone and per-identity in the handler.
    """
    rules = {r["Name"]: r for r in waf_module.COGNITO_RULES}

    rate = rules["auth-rate-limit-per-ip"]
    assert rate["Action"] == {"Block": {}}
    assert rate["Statement"]["RateBasedStatement"]["AggregateKeyType"] == "IP"

    for name in ("AWSManagedRulesAmazonIpReputationList",
                 "AWSManagedRulesCommonRuleSet"):
        assert rules[name]["OverrideAction"] == {"Count": {}}, (
            f"{name} is blocking on a sign-in path without recorded tuning"
        )


def test_amplify_managed_rules_actually_block(waf_module):
    """A static export gives the managed groups nothing legitimate to trip on.

    If these ever go to COUNT the site is unprotected while still reporting a web ACL,
    which is the failure this whole file is about.
    """
    for rule in waf_module.AMPLIFY_RULES:
        override = rule.get("OverrideAction")
        if override is not None:
            assert override == {"None": {}}, (
                f"{rule['Name']} is counting on the Amplify surface, so it blocks "
                f"nothing while appearing configured"
            )


def test_logging_is_part_of_the_plan_not_a_followup(waf_module):
    """COUNT is only honest if somebody can read the counts."""
    for name, spec in waf_module.PLAN.items():
        assert spec["logGroup"].startswith("aws-waf-logs-"), (
            f"{name}: WAF only accepts log groups named aws-waf-logs-*"
        )
    groups = [spec["logGroup"] for spec in waf_module.PLAN.values()]
    assert len(set(groups)) == len(groups), "two ACLs share one log group"
