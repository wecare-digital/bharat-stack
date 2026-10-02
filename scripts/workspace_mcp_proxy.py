#!/usr/bin/env python3
"""Kiro/Codex stdio bridge to the cloud router using existing AWS SigV4 auth.

No static API keys or provider credentials are accepted. Stdout is MCP JSON only.
The AWS SDK loads the existing named profile inside this process.
"""
import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

ENDPOINT = "https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/workspace/mcp-iam"


def relay(message):
    session = boto3.Session(profile_name="wecare-prod", region_name="us-east-1")
    data = json.dumps(message).encode()
    request = AWSRequest(method="POST", url=ENDPOINT, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json", "MCP-Protocol-Version": "2025-11-25"})
    credentials = session.get_credentials().get_frozen_credentials()
    SigV4Auth(credentials, "execute-api", "us-east-1").add_auth(request)
    prepared = request.prepare()
    with urllib.request.urlopen(urllib.request.Request(ENDPOINT, data=data, headers=dict(prepared.headers)), timeout=29) as response:
        result = response.read(600000)
        if "id" not in message:
            return None
        return json.loads(result)


def main():
    for line in sys.stdin:
        message = {}
        try:
            if len(line.encode()) > 65536: raise ValueError("Message too large")
            message = json.loads(line)
            if not isinstance(message, dict): raise ValueError("Expected an object")
            result = relay(message)
            if result is not None:
                print(json.dumps(result), flush=True)
        except Exception:
            if isinstance(message, dict) and "id" in message:
                print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32603, "message": "Cloud MCP request failed; verify AWS profile and endpoint status"}}), flush=True)


if __name__ == "__main__":
    main()
