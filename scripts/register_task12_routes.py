"""Idempotently register verified Task 12 HTTP API routes."""
import json

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT = "775261844268"
API_ID = "zllr9lrg7j"
ROUTES = {
    "wecare-messages-read:live": [
        "GET /messages/{messageId}", "PUT /messages/{messageId}",
    ],
    "wecare-scheduled-messages:live": [
        "PUT /scheduled/{scheduledId}", "DELETE /scheduled/{scheduledId}",
    ],
    "wecare-push-notifications:live": [
        "GET /push/devices", "POST /push/send",
    ],
    "wecare-wix-store:live": [
        "GET /store/order-notifications", "POST /store/order-notifications/retry",
    ],
    "wecare-seo-tools": ["ANY /seo-tools/{proxy+}"],
    "wecare-docs-scraper": [
        "GET /docs/sources", "POST /docs/sources",
        "POST /docs/scrape", "GET /docs/changelog",
    ],
    "wecare-whatsapp-voice:live": [
        "GET /whatsapp-voice/language-config",
        "PUT /whatsapp-voice/language-config",
    ],
    "wecare-waba-management:live": [
        "POST /waba/request-otp", "POST /waba/verify-otp",
        "POST /waba/register-phone", "POST /waba/migrate",
        "GET /waba/{wabaId}/subscribe-sns",
        "POST /waba/{wabaId}/subscribe-sns",
        "DELETE /waba/{wabaId}/subscribe-sns",
    ],
}


def function_arn(function_ref: str) -> str:
    return f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{function_ref}"


def all_items(client, operation_name: str):
    items = []
    for page in client.get_paginator(operation_name).paginate(ApiId=API_ID):
        items.extend(page.get("Items", []))
    return items


def ensure_permission(lam, function_ref: str) -> bool:
    function_name, _, qualifier = function_ref.partition(":")
    statement_id = "Task12HttpApiInvoke" + ("Live" if qualifier else "")
    source_arn = f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/*/*"
    kwargs = {
        "FunctionName": function_name,
        "StatementId": statement_id,
        "Action": "lambda:InvokeFunction",
        "Principal": "apigateway.amazonaws.com",
        "SourceArn": source_arn,
    }
    if qualifier:
        kwargs["Qualifier"] = qualifier
    try:
        lam.add_permission(**kwargs)
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceConflictException":
            raise
    policy_args = {"FunctionName": function_name}
    if qualifier:
        policy_args["Qualifier"] = qualifier
    policy = json.loads(lam.get_policy(**policy_args)["Policy"])
    statement = next(
        (item for item in policy.get("Statement", []) if item.get("Sid") == statement_id),
        None,
    )
    condition = (statement or {}).get("Condition", {})
    configured_source = (
        condition.get("ArnLike", {}).get("AWS:SourceArn")
        or condition.get("ArnEquals", {}).get("AWS:SourceArn")
    )
    principal = (statement or {}).get("Principal", {})
    if not (
        statement
        and statement.get("Action") == "lambda:InvokeFunction"
        and principal.get("Service") == "apigateway.amazonaws.com"
        and configured_source == source_arn
    ):
        raise RuntimeError(
            f"Conflicting Lambda permission {statement_id} on {function_ref}"
        )
    return False


def ensure_integration(apigw, function_ref: str, integrations):
    arn = function_arn(function_ref)
    current = next(
        (item for item in integrations if item.get("IntegrationUri") == arn), None,
    )
    if current:
        return current["IntegrationId"], False
    created = apigw.create_integration(
        ApiId=API_ID,
        IntegrationType="AWS_PROXY",
        IntegrationUri=arn,
        PayloadFormatVersion="2.0",
        TimeoutInMillis=30000,
    )
    integrations.append(created)
    return created["IntegrationId"], True


def rollback(apigw, lam, created_routes, updated_routes, created_integrations, permissions):
    for route_id in reversed(created_routes):
        try:
            apigw.delete_route(ApiId=API_ID, RouteId=route_id)
        except Exception as error:
            print(f"ROLLBACK FAILED deleting route {route_id}: {error}")
    for route in reversed(updated_routes):
        try:
            apigw.update_route(
                ApiId=API_ID,
                RouteId=route["RouteId"],
                Target=route["Target"],
                AuthorizationType=route.get("AuthorizationType", "NONE"),
            )
        except Exception as error:
            print(f"ROLLBACK FAILED restoring route {route['RouteKey']}: {error}")
    for integration_id in reversed(created_integrations):
        try:
            apigw.delete_integration(ApiId=API_ID, IntegrationId=integration_id)
        except Exception as error:
            print(f"ROLLBACK FAILED deleting integration {integration_id}: {error}")
    for function_ref in reversed(permissions):
        function_name, _, qualifier = function_ref.partition(":")
        kwargs = {
            "FunctionName": function_name,
            "StatementId": "Task12HttpApiInvoke" + ("Live" if qualifier else ""),
        }
        if qualifier:
            kwargs["Qualifier"] = qualifier
        try:
            lam.remove_permission(**kwargs)
        except Exception as error:
            print(f"ROLLBACK FAILED removing permission from {function_ref}: {error}")


def main() -> None:
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    existing_routes = {
        item["RouteKey"]: item for item in all_items(apigw, "get_routes")
    }
    integrations = all_items(apigw, "get_integrations")
    created = []
    updated = []
    unchanged = []
    created_route_ids = []
    updated_routes = []
    created_integrations = []
    added_permissions = []
    try:
        for function_ref, route_keys in ROUTES.items():
            function_name, _, qualifier = function_ref.partition(":")
            lookup = {"FunctionName": function_name}
            if qualifier:
                lookup["Qualifier"] = qualifier
            lam.get_function(**lookup)
            if ensure_permission(lam, function_ref):
                added_permissions.append(function_ref)
            integration_id, integration_created = ensure_integration(
                apigw, function_ref, integrations,
            )
            if integration_created:
                created_integrations.append(integration_id)
            target = f"integrations/{integration_id}"
            for route_key in route_keys:
                current = existing_routes.get(route_key)
                if current and current.get("Target") == target:
                    unchanged.append(route_key)
                    continue
                if current:
                    updated_routes.append(current)
                    apigw.update_route(
                        ApiId=API_ID, RouteId=current["RouteId"],
                        Target=target, AuthorizationType="NONE",
                    )
                    updated.append(route_key)
                else:
                    route = apigw.create_route(
                        ApiId=API_ID, RouteKey=route_key, Target=target,
                        AuthorizationType="NONE",
                    )
                    created_route_ids.append(route["RouteId"])
                    created.append(route_key)
    except Exception:
        rollback(
            apigw, lam, created_route_ids, updated_routes,
            created_integrations, added_permissions,
        )
        raise
    print(json.dumps({
        "created": created, "updated": updated, "unchanged": unchanged,
        "totalVerified": len(created) + len(updated) + len(unchanged),
    }, indent=2))


if __name__ == "__main__":
    main()