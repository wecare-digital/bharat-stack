import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "amplify/functions/ai/workspace-mcp"


@pytest.fixture
def module(monkeypatch):
    # Import needs only the static policy. No AWS clients are created at import.
    monkeypatch.syspath_prepend(str(DIRECTORY))
    policy_path = DIRECTORY / "workspace-mcp.json"
    original = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda p, *a, **kw: (ROOT / "config/workspace-mcp.json").read_bytes().decode() if p == policy_path else original(p, *a, **kw))
    spec = importlib.util.spec_from_file_location("workspace_mcp_test", DIRECTORY / "handler.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def event(message=None, auth=True):
    return {"body": json.dumps(message or {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
        "headers": {}, "requestContext": {"apiId": "zllr9lrg7j", "routeKey": "POST /workspace/mcp-iam",
        "http": {"method": "POST", "path": "/workspace/mcp-iam"},
        "authorizer": {"iam": {"userArn": "arn:aws:iam::775261844268:user/wecare-admin"}} if auth else {}}}


class MemoryTable:
    def __init__(self): self.rows = {}
    def get_item(self, Key, **kwargs): return {"Item": self.rows.get(Key["pk"], {})}
    def put_item(self, Item, **kwargs): self.rows[Item["pk"]] = Item
    def delete_item(self, Key, **kwargs):
        item = self.rows.get(Key["pk"])
        values = kwargs.get("ExpressionAttributeValues", {})
        if not item or (values and (item["stateHash"] != values[":s"] or item["expiresAt"] <= values[":n"])):
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "DeleteItem")
        del self.rows[Key["pk"]]
    def update_item(self, **kwargs): pass


@pytest.fixture
def memory(module, monkeypatch):
    table = MemoryTable()
    monkeypatch.setattr(module, "table", lambda: table)
    monkeypatch.setattr(module, "encrypt", lambda value, owner, provider: json.dumps(value).encode())
    monkeypatch.setattr(module, "decrypt", lambda value, owner, provider: json.loads(value))
    return table


def test_unauthenticated_never_reaches_tools(module, monkeypatch):
    monkeypatch.setattr(module, "run_tool", lambda *a: pytest.fail("must not call a tool"))
    assert module.handler(event(auth=False), None)["statusCode"] == 401


@pytest.mark.parametrize("change", ["api", "arn", "origin"])
def test_identity_binding(module, change):
    request = event()
    if change == "api": request["requestContext"]["apiId"] = "other"
    if change == "arn": request["requestContext"]["authorizer"]["iam"]["userArn"] = "arn:aws:iam::010526260063:user/wecare-admin"
    if change == "origin": request["headers"]["Origin"] = "https://evil.invalid"
    assert module.handler(request, None)["statusCode"] in (401, 403)


@pytest.mark.parametrize("bad", ["issuer", "audience", "id_token", "viewer", "expired"])
def test_staff_jwt_claims_fail_closed(module, bad):
    claims = {"iss": module.ISSUER, "client_id": module.STAFF_CLIENT, "token_use": "access", "cognito:groups": "[Admin]", "sub": "staff", "exp": str(int(time.time()) + 3600)}
    if bad == "issuer": claims["iss"] = "https://customer.invalid"
    if bad == "audience": claims["client_id"] = "customer-app"
    if bad == "id_token": claims["token_use"] = "id"
    if bad == "viewer": claims["cognito:groups"] = "[Viewer]"
    if bad == "expired": claims["exp"] = "1"
    request = event()
    request["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
    assert module.handler(request, None)["statusCode"] == 401


def test_staff_access_token_authorized(module, monkeypatch):
    class Cognito:
        def get_user(self, **kwargs): return {"Username": "staff", "UserAttributes": [{"Name": "sub", "Value": "staff"}]}
        def admin_list_groups_for_user(self, **kwargs): return {"Groups": [{"GroupName": "Admin"}]}
    monkeypatch.setattr(module, "client", lambda *a: Cognito())
    request = event()
    request["headers"]["authorization"] = "Bearer fixture"
    request["requestContext"]["authorizer"] = {"jwt": {"claims": {"iss": module.ISSUER, "client_id": module.STAFF_CLIENT, "token_use": "access", "cognito:groups": "[Admin]", "sub": "staff", "exp": str(int(time.time()) + 3600)}}}
    assert module.handler(request, None)["statusCode"] == 200


def test_tool_inventory_has_no_mutating_provider_tools(module):
    result = json.loads(module.handler(event(), None)["body"])["result"]
    assert {x["name"] for x in result["tools"]} == {"connections_list", "connection_authorize", "connection_verify", "provider_read", "aws_status", "github_status", "code_job_submit", "code_job_status"}
    assert module.POLICY["connections"]["whatsapp"]["tools"] == {"whatsapp_biz_businesses": ["list"]}


@pytest.mark.parametrize("name,args", [
    ("whatsapp_biz_send_message", {"action": "send"}),
    ("devtools_webhook_manage", {"action": "create"}),
    ("devtools_app", {"action": "advanced_settings", "app_id": "other-app"}),
    ("devtools_app_list", {"action": "list", "endpoint": "http://169.254.169.254"}),
    ("devtools_app_list", {"action": "delete"}),
    ("devtools_app_list", {"action": "list", "limit": True}),
])
def test_provider_policy_refuses_before_network(module, name, args):
    with pytest.raises(module.Refusal): module.safe_provider_args("meta-social", name, args)


def test_callback_one_use_and_pkce(module, memory, monkeypatch):
    import urllib.parse
    begin = module.oauth_begin("owner", "meta-social")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(begin["authorizationUrl"]).query)
    assert query["redirect_uri"] == [module.CALLBACK]
    assert query["code_challenge_method"] == ["S256"]
    assert "developer_tools_mcp_app_management" not in query["scope"][0]
    seen = []
    def exchange(url, payload=None, **kw):
        seen.append(payload)
        return {"access_token": "fixture-access", "refresh_token": "fixture-refresh", "expires_in": 3600}, None
    monkeypatch.setattr(module, "http", exchange)
    callback = {"state": query["state"][0], "code": "fixture-code"}
    assert module.oauth_callback(callback)["status"] == "authorized_unverified"
    assert "code_verifier" in seen[0] and seen[0]["resource"] == "https://mcp.facebook.com/devtools"
    connection = memory.rows["connection:owner:meta-social"]
    # TTL must not delete the refresh credential at access-token expiry.
    assert "ttl" not in connection
    with pytest.raises(module.Refusal): module.oauth_callback(callback)
    assert len(seen) == 1


def test_superseded_oauth_flow_cannot_authorize(module, memory, monkeypatch):
    import urllib.parse
    a = module.oauth_begin("owner", "whatsapp")
    module.oauth_begin("owner", "whatsapp")
    state = urllib.parse.parse_qs(urllib.parse.urlparse(a["authorizationUrl"]).query)["state"][0]
    monkeypatch.setattr(module, "http", lambda *a, **kw: pytest.fail("superseded flow must not exchange"))
    with pytest.raises(module.Refusal): module.oauth_callback({"state": state, "code": "fixture"})


def test_callback_does_not_bypass_auth_on_similar_path(module):
    request = event(auth=False)
    request["requestContext"]["http"]["path"] = "/workspace/mcp/oauth/callback-evil"
    assert module.handler(request, None)["statusCode"] == 401


def test_registry_never_returns_ciphertext(module, memory):
    memory.rows["connection:owner:whatsapp"] = {"status": "verified", "expiresAt": int(time.time()) + 3600, "cipher": b"fixture-sensitive"}
    result = json.dumps(module.registry("owner"))
    assert "fixture-sensitive" not in result and "cipher" not in result
    assert "pending-adapter" in result and "documentation-only" in result


def test_notification_does_not_execute_tool(module, monkeypatch):
    monkeypatch.setattr(module, "run_tool", lambda *a: pytest.fail("notification must not call tool"))
    request = event({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "code_job_submit"}})
    assert module.handler(request, None)["statusCode"] == 400


def test_provider_result_redacts_nested_credentials(module):
    value = {"content": [{"type": "text", "text": json.dumps({"app_secret": "fixture-sensitive", "name": "WECARE"})}]}
    result = json.dumps(module.redact(value))
    assert "fixture-sensitive" not in result and "WECARE" in result


def test_iac_roles_cannot_mutate_providers_or_lambda():
    template = json.loads((ROOT / "amplify/infra/workspace-mcp.json").read_text())
    resources = template["Resources"]
    assert resources["StaffRoute"]["Properties"]["AuthorizationType"] == "JWT"
    assert resources["IamRoute"]["Properties"]["AuthorizationType"] == "AWS_IAM"
    assert resources["CallbackRoute"]["Properties"]["RouteKey"] == "GET /workspace/mcp/oauth/callback"
    statements = resources["Role"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    actions = {a for s in statements for a in s["Action"]}
    assert "lambda:UpdateFunctionCode" not in actions and "iam:PassRole" not in actions
    assert resources["Function"]["Properties"]["Environment"]["Variables"]["CODE_JOBS_ENABLED"] == "false"


@pytest.mark.parametrize("path", [".github/workflows/build-test.yml", ".kiro/steering/secret-handling.md", "amplify/functions/ecommerce/checkout/handler.py", "src/components/../lib/auth.ts", "src/components/Header.tsx\"", "/etc/passwd"])
def test_patch_path_policy_denies_sensitive_paths(path):
    sys.path.insert(0, str(DIRECTORY))
    from patch_policy import validate_patch
    patch = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-a\n+b\n"
    with pytest.raises(ValueError): validate_patch(patch)


def test_patch_alternate_header_attack_denied():
    sys.path.insert(0, str(DIRECTORY))
    from patch_policy import validate_patch
    patch = "diff --git a/src/components/Header.tsx b/src/components/Header.tsx\n--- a/.kiro/steering/secret-handling.md\n+++ b/.kiro/steering/secret-handling.md\n@@ -1 +1 @@\n-a\n+b\n"
    with pytest.raises(ValueError): validate_patch(patch)


def test_patch_existing_public_component_allowed():
    sys.path.insert(0, str(DIRECTORY))
    from patch_policy import validate_patch
    patch = "diff --git a/src/components/Header.tsx b/src/components/Header.tsx\n--- a/src/components/Header.tsx\n+++ b/src/components/Header.tsx\n@@ -1 +1 @@\n-a\n+b\n"
    assert validate_patch(patch) == ["src/components/Header.tsx"]


def test_expired_state_never_exchanges_token(module, memory, monkeypatch):
    import urllib.parse
    begin = module.oauth_begin("owner", "whatsapp")
    state = urllib.parse.parse_qs(urllib.parse.urlparse(begin["authorizationUrl"]).query)["state"][0]
    for item in memory.rows.values(): item["expiresAt"] = 1
    monkeypatch.setattr(module, "http", lambda *a, **kw: pytest.fail("expired state must not exchange"))
    with pytest.raises(module.Refusal): module.oauth_callback({"state": state, "code": "fixture"})


def test_removed_admin_membership_refused(module, monkeypatch):
    class Cognito:
        def get_user(self, **kwargs): return {"Username": "staff", "UserAttributes": [{"Name": "sub", "Value": "staff"}]}
        def admin_list_groups_for_user(self, **kwargs): return {"Groups": [{"GroupName": "Viewer"}]}
    monkeypatch.setattr(module, "client", lambda *a: Cognito())
    request = event()
    request["headers"]["authorization"] = "Bearer fixture"
    request["requestContext"]["authorizer"] = {"jwt": {"claims": {"iss": module.ISSUER, "client_id": module.STAFF_CLIENT, "token_use": "access", "cognito:groups": "[Admin]", "sub": "staff", "exp": str(int(time.time()) + 3600)}}}
    assert module.handler(request, None)["statusCode"] == 401


def test_provider_call_initializes_and_uses_negotiated_session(module, monkeypatch):
    monkeypatch.setattr(module, "token", lambda *a: "fixture-access")
    calls = []
    def remote(url, payload=None, headers=None, **kw):
        calls.append((url, payload, dict(headers)))
        if payload["method"] == "initialize": return {"result": {"protocolVersion": "2025-06-18"}}, "fixture-session"
        if payload["method"] == "notifications/initialized": return {}, None
        return {"result": {"content": [{"type": "text", "text": '{"app_secret":"fixture-sensitive","name":"WECARE"}'}]}}, None
    monkeypatch.setattr(module, "http", remote)
    result = module.provider_call("owner", "meta-social", "devtools_app_list", {"action": "list"})
    assert [call[1]["method"] for call in calls] == ["initialize", "notifications/initialized", "tools/call"]
    assert calls[-1][2]["MCP-Protocol-Version"] == "2025-06-18"
    assert calls[-1][2]["Mcp-Session-Id"] == "fixture-session"
    assert "fixture-sensitive" not in json.dumps(result)


def test_sse_returns_without_waiting_for_eof(module, monkeypatch):
    import io
    class Response:
        headers = {"Content-Type": "text/event-stream"}
        def __init__(self): self.stream = io.BytesIO(b'data: {"jsonrpc":"2.0","id":9,"result":{"ok":true}}\n\n')
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def readline(self, size):
            line = self.stream.readline(size)
            if not line: pytest.fail("must not wait for persistent stream EOF")
            return line
    class Opener:
        def open(self, *a, **kw): return Response()
    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *a: Opener())
    result, _ = module.http("https://mcp.facebook.com/devtools", {"jsonrpc": "2.0", "id": 9, "method": "ping"})
    assert result["result"] == {"ok": True}


def test_disabled_code_jobs_are_persisted_once_without_dispatch(module, memory, monkeypatch):
    monkeypatch.setenv("PATCH_BUCKET", "fixture-bucket")
    monkeypatch.setenv("CODE_JOBS_ENABLED", "false")
    puts = []
    class S3:
        def put_object(self, **kwargs): puts.append(kwargs)
    monkeypatch.setattr(module, "client", lambda *a: S3())
    monkeypatch.setattr(module, "http", lambda *a, **kw: pytest.fail("disabled job must not dispatch"))
    patch = "diff --git a/src/components/Header.tsx b/src/components/Header.tsx\n--- a/src/components/Header.tsx\n+++ b/src/components/Header.tsx\n@@ -1 +1 @@\n-a\n+b\n"
    args = {"expectedBase": "a" * 40, "patch": patch}
    one = module.code_submit("owner", args)
    two = module.code_submit("owner", args)
    assert one["jobId"] == two["jobId"] and two["status"] == "dispatch_pending"
    assert len(puts) == 1 and puts[0]["Key"].startswith("workspace-mcp/patches/owner/")


def test_audit_log_does_not_include_arguments(module, memory, caplog):
    request = event({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "connections_list", "arguments": {"unrecognized": "fixture-sensitive"}}})
    module.handler(request, None)
    assert "fixture-sensitive" not in caplog.text
    assert "workspace_mcp_tool" in caplog.text


def test_route_audit_only_exempts_nonce_callback():
    spec = importlib.util.spec_from_file_location("workspace_route_audit", ROOT / "scripts/audit_route_auth.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert "GET /workspace/mcp/oauth/callback" in audit.EXPECTED_PUBLIC_ROUTES
    assert "ANY /workspace/mcp" not in audit.EXPECTED_PUBLIC_ROUTES
    assert "POST /workspace/mcp-iam" not in audit.EXPECTED_PUBLIC_ROUTES


def test_generic_deployer_delegates_workspace_bundle():
    source = (ROOT / "scripts/deploy_all_lambdas.py").read_text()
    assert '"wecare-workspace-mcp": "scripts/build_workspace_mcp.py + scripts/deploy_workspace_mcp.py' in source
