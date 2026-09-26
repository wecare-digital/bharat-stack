"""`provision_log_retention.py` must be able to see Lambda@Edge log groups.

The gap this guards
-------------------
The script scanned `/aws/lambda/wecare-` in `us-east-1` only, and reported

    69 log groups ... never expires: 0
    every /aws/lambda/wecare-* log group has a retention period

while **four** log groups never expired. Lambda@Edge defeats both halves of that
scan at once:

* the group is named `/aws/lambda/us-east-1.<function>`, so the region sits inside
  the name and the old prefix could never match it;
* CloudFront writes the logs in the region nearest the viewer, so the groups exist in
  several regions and no single-region scan can find them all.

Measured across all 34 enabled regions on 2026-09-25: `wecare-get-miss-redirect` and
`/aws/cloudfront/LambdaEdge/E2GP22R4BIFGQ3` each had a never-expiring group in
`us-east-1` **and** `ap-south-1`.

These tests pin the two properties that made the miss possible, so a future
simplification back to one prefix in one region fails here instead of in production
silence. They are offline: no AWS call is made.
"""

import ast
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parent.parent
          / "scripts" / "provision_log_retention.py")


@pytest.fixture(scope="module")
def source() -> str:
    return SCRIPT.read_text()


@pytest.fixture(scope="module")
def tree(source: str) -> ast.Module:
    return ast.parse(source)


def _assigned(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned in {SCRIPT.name}")


class TestEdgePrefixes:
    def test_edge_prefixes_exist(self, tree):
        prefixes = _assigned(tree, "EDGE_PREFIXES")
        assert prefixes, "EDGE_PREFIXES must not be empty"

    def test_covers_the_edge_replica_group_name(self, tree):
        """`/aws/lambda/us-east-1.<fn>` cannot match the plain `/aws/lambda/wecare-`."""
        prefixes = _assigned(tree, "EDGE_PREFIXES")
        observed = "/aws/lambda/us-east-1.wecare-get-miss-redirect"
        assert any(observed.startswith(p) for p in prefixes), (
            f"no EDGE_PREFIXES entry matches {observed!r}, the real group name "
            f"measured in us-east-1 and ap-south-1"
        )

    def test_covers_the_cloudfront_execution_error_group(self, tree):
        prefixes = _assigned(tree, "EDGE_PREFIXES")
        observed = "/aws/cloudfront/LambdaEdge/E2GP22R4BIFGQ3"
        assert any(observed.startswith(p) for p in prefixes), (
            f"no EDGE_PREFIXES entry matches {observed!r}"
        )

    def test_the_plain_prefix_still_cannot_match_edge(self, tree):
        """Guards the reasoning, not just the constant.

        If someone 'simplifies' by deleting EDGE_PREFIXES on the belief that PREFIX
        already covers Edge, this states plainly that it does not.
        """
        prefix = _assigned(tree, "PREFIX")
        assert not "/aws/lambda/us-east-1.wecare-get-miss-redirect".startswith(prefix)
        assert not "/aws/cloudfront/LambdaEdge/E2GP22R4BIFGQ3".startswith(prefix)


class TestMultiRegionScan:
    def test_edge_scan_is_region_plural(self, source):
        """The scan must derive regions rather than assume one."""
        assert "def enabled_regions" in source
        assert "describe_regions" in source

    def test_edge_groups_returns_region_with_each_group(self, source):
        """Retention must be set in the region holding the group.

        The same group NAME exists in several regions, so a (region, group) pair is
        required - a bare name would send put_retention_policy to the wrong region.
        """
        assert "found.append((region, group))" in source or \
               "hits.append((region, group))" in source, (
            "edge_groups must carry the region alongside each group"
        )

    def test_unreachable_regions_are_not_reported_as_clean(self, source):
        """An unread region is unproven, never clean.

        This is the distinction that makes the gate honest: it fails on a group with
        no retention, and separately reports regions it could not read.
        """
        assert "unreachable" in source
        assert "UNPROVEN" in source, (
            "an unreadable region must be reported as unproven coverage"
        )

    def test_strict_mode_exists_for_a_runner_with_full_egress(self, source):
        assert "--strict" in source


class TestApplyTargetsTheRightRegion:
    def test_apply_builds_a_client_per_region(self, source):
        """`logs(region).put_retention_policy(...)` - not the default client."""
        assert "logs(region).put_retention_policy" in source, (
            "Edge retention must be applied through a client for that group's region"
        )
