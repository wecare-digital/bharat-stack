#!/usr/bin/env python3
"""Provision the authenticated checkout customer-profile Lambda and API route."""

from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "wecare-customer-profile"
LIVE_ALIAS = "live"
ROLE_NAME = "wecare-customer-profile-role"
API_ID = "zllr9lrg7j"
STAGE = "prod"
ROUTE_KEYS = ("POST /customer/profile", "OPTIONS /customer/profile")

ROOT = Path(__file__).resolve().parents[1]
FUNCTION_DIR = ROOT / "amplify/functions/auth/customer-profile"
SHARED_DIR = ROOT / "amplify/functions/shared"

OTP_TABLE = "stack-wecare-digital-DownloadGrantsTable"
CONTACTS_TABLE = "stack-wecare-digital-ContactsTable"
OTP_PEPPER_SECRET_ID = "wecare/otp/pepper"

_account = None


def account_id():
    global _account
    if _account is None:
        _account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    return _account


def iam(): return boto3.client("iam")
def lam(): return boto3.client("lambda", region_name=REGION)
def api(): return boto3.client("apigatewayv2", region_name=REGION)


def _zip_package():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("handler.py", (FUNCTION_DIR / "handler.py").read_bytes())
        for item in sorted((SHARED_DIR / "lambda_utils").rglob("*.py")):
            if "__pycache__" not in item.parts:
                archive.write(item, str(item.relative_to(SHARED_DIR)))
    return buf.getvalue()


def _exists(client, method, **kwargs):
    try:
        return getattr(client, method)(**kwargs)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchEntity", "ResourceNotFoundException"):
            return None
        raise


def ensure_role(dry_run):
    existing = _exists(iam(), "get_role", RoleName=ROLE_NAME)
    if existing:
        return "exists"
    if dry_run:
        return "would create"
    assume = {"Version":"2012-10-17","Statement":[{
        "Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
    iam().create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(assume),
        Description="Authenticated checkout profile -> Workspace Contacts",
        Tags=[{"Key":"Project","Value":"WECARE.DIGITAL"},{"Key":"Purpose","Value":"CustomerProfile"}],
    )
    iam().attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    acct = account_id()
    policy = {"Version":"2012-10-17","Statement":[
        {"Sid":"ReadOtpPepper","Effect":"Allow","Action":["secretsmanager:GetSecretValue"],
         "Resource":[f"arn:aws:secretsmanager:{REGION}:{acct}:secret:{OTP_PEPPER_SECRET_ID}-*"]},
        {"Sid":"ReadEmailProof","Effect":"Allow","Action":["dynamodb:GetItem"],
         "Resource":[f"arn:aws:dynamodb:{REGION}:{acct}:table/{OTP_TABLE}"]},
        {"Sid":"ContactsUpsert","Effect":"Allow",
         "Action":["dynamodb:GetItem","dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:Query"],
         "Resource":[
             f"arn:aws:dynamodb:{REGION}:{acct}:table/{CONTACTS_TABLE}",
             f"arn:aws:dynamodb:{REGION}:{acct}:table/{CONTACTS_TABLE}/index/*",
         ]},
        # customer_auth.GetUser validates the caller's own access token.
        {"Sid":"ValidateCustomerToken","Effect":"Allow","Action":["cognito-idp:GetUser"],"Resource":["*"]},
    ]}
    iam().put_role_policy(
        RoleName=ROLE_NAME, PolicyName="CustomerProfileLeastPrivilege",
        PolicyDocument=json.dumps(policy))
    return "created"


def ensure_function(dry_run):
    if _exists(lam(), "get_function", FunctionName=FUNCTION_NAME):
        return "exists"
    if dry_run:
        return "would create"
    role_arn = iam().get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    for attempt in range(8):
        try:
            lam().create_function(
                FunctionName=FUNCTION_NAME, Runtime="python3.12", Role=role_arn,
                Handler="handler.handler", Code={"ZipFile":_zip_package()},
                Timeout=15, MemorySize=256,
                Environment={"Variables":{
                    "OTP_TABLE":OTP_TABLE,
                    "CONTACTS_TABLE":CONTACTS_TABLE,
                    "OTP_PEPPER_SECRET_ID":OTP_PEPPER_SECRET_ID,
                }},
                Description="Authenticated checkout identity -> Workspace Contacts",
                Tags={"Project":"WECARE.DIGITAL","Purpose":"CustomerProfile"},
            )
            return "created"
        except ClientError as exc:
            if exc.response.get("Error",{}).get("Code") != "InvalidParameterValueException" or attempt == 7:
                raise
            time.sleep(2)


def ensure_alias(dry_run):
    if not _exists(lam(), "get_function", FunctionName=FUNCTION_NAME):
        return "function absent"
    if _exists(lam(), "get_alias", FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS):
        return "exists"
    if dry_run:
        return "would publish and alias"
    version = lam().publish_version(FunctionName=FUNCTION_NAME)["Version"]
    lam().create_alias(FunctionName=FUNCTION_NAME, Name=LIVE_ALIAS, FunctionVersion=version)
    return f"created -> v{version}"


def _all(method):
    out, token = [], None
    while True:
        kwargs={"ApiId":API_ID,"MaxResults":"100"}
        if token: kwargs["NextToken"]=token
        result=getattr(api(), method)(**kwargs)
        out.extend(result.get("Items",[]))
        token=result.get("NextToken")
        if not token: return out


def ensure_integration(dry_run):
    wanted=f"arn:aws:lambda:{REGION}:{account_id()}:function:{FUNCTION_NAME}:{LIVE_ALIAS}"
    for item in _all("get_integrations"):
        if wanted in str(item.get("IntegrationUri") or ""):
            return item["IntegrationId"], "exists"
    if dry_run:
        return "DRY_RUN","would create"
    item=api().create_integration(
        ApiId=API_ID, IntegrationType="AWS_PROXY", IntegrationUri=wanted,
        PayloadFormatVersion="2.0", TimeoutInMillis=15000)
    return item["IntegrationId"],"created"


def ensure_routes(integration_id, dry_run):
    existing={r["RouteKey"] for r in _all("get_routes")}
    states=[]
    for route in ROUTE_KEYS:
        if route in existing:
            states.append(route+"=exists")
        elif dry_run:
            states.append(route+"=would create")
        else:
            api().create_route(ApiId=API_ID, RouteKey=route, Target=f"integrations/{integration_id}")
            states.append(route+"=created")
    return ", ".join(states)


def ensure_permissions(dry_run):
    states=[]
    for route in ROUTE_KEYS:
        method,path=route.split(" ",1)
        sid="apigw-customer-profile-"+method.lower()+path.replace("/","-")
        if dry_run:
            states.append(route+"=would ensure")
            continue
        try:
            lam().add_permission(
                FunctionName=FUNCTION_NAME, Qualifier=LIVE_ALIAS, StatementId=sid,
                Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:{REGION}:{account_id()}:{API_ID}/{STAGE}/{method}{path}")
            states.append(route+"=created")
        except ClientError as exc:
            if exc.response.get("Error",{}).get("Code")=="ResourceConflictException":
                states.append(route+"=exists")
            else: raise
    return ", ".join(states)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args(argv)
    print("role:",ensure_role(args.dry_run))
    print("function:",ensure_function(args.dry_run))
    print("alias:",ensure_alias(args.dry_run))
    iid,state=ensure_integration(args.dry_run)
    print("integration:",state)
    print("routes:",ensure_routes(iid,args.dry_run))
    print("permissions:",ensure_permissions(args.dry_run))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
