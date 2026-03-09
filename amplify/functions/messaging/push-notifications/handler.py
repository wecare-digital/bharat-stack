"""
Push Notifications Lambda - WECARE.DIGITAL

Registers device tokens with SNS Platform Applications,
stores token-to-user mappings in DynamoDB,
and sends push notifications via SNS.

AWS Resources:
- SNS Platform Application (FCM): for Android push via Firebase
- SNS Platform Application (APNs): for iOS push via Apple
- DynamoDB PushTokensTable: deviceToken (PK), userId (SK)
"""

import json
import os
import boto3
import time
from datetime import datetime

sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")

PUSH_TOKENS_TABLE = os.environ.get("PUSH_TOKENS_TABLE", "PushTokensTable")
SNS_ANDROID_ARN = os.environ.get("SNS_PLATFORM_APP_ARN_ANDROID", "")
SNS_IOS_ARN = os.environ.get("SNS_PLATFORM_APP_ARN_IOS", "")

table = dynamodb.Table(PUSH_TOKENS_TABLE)


def handler(event, context):
    """Main Lambda handler."""
    method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "GET"))
    path = event.get("path", event.get("rawPath", ""))
    body = json.loads(event.get("body", "{}") or "{}")

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
    }

    try:
        if method == "OPTIONS":
            return {"statusCode": 200, "headers": headers, "body": ""}

        if "register" in path:
            if method == "POST":
                return register_token(body, headers)
            elif method == "DELETE":
                return unregister_token(body, headers)

        if "send" in path and method == "POST":
            return send_push(body, headers)

        return {
            "statusCode": 404,
            "headers": headers,
            "body": json.dumps({"error": "Not found"}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }


def register_token(body, headers):
    """Register a device push token with SNS and store mapping."""
    device_token = body.get("deviceToken")
    platform = body.get("platform", "android")  # 'android' or 'ios'
    user_id = body.get("userId", "anonymous")

    if not device_token:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "deviceToken required"}),
        }

    # Choose SNS Platform Application ARN
    platform_arn = SNS_ANDROID_ARN if platform == "android" else SNS_IOS_ARN
    if not platform_arn:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": f"SNS Platform ARN not configured for {platform}"}),
        }

    # Create SNS Platform Endpoint
    response = sns.create_platform_endpoint(
        PlatformApplicationArn=platform_arn,
        Token=device_token,
        CustomUserData=user_id,
    )
    endpoint_arn = response["EndpointArn"]

    # Store in DynamoDB
    table.put_item(
        Item={
            "deviceToken": device_token,
            "userId": user_id,
            "platform": platform,
            "endpointArn": endpoint_arn,
            "registeredAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }
    )

    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({
            "success": True,
            "endpointArn": endpoint_arn,
        }),
    }


def unregister_token(body, headers):
    """Remove device token from SNS and DynamoDB."""
    device_token = body.get("deviceToken")
    user_id = body.get("userId", "anonymous")

    if not device_token:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "deviceToken required"}),
        }

    # Look up endpoint ARN
    try:
        item = table.get_item(Key={"deviceToken": device_token, "userId": user_id}).get("Item")
        if item and item.get("endpointArn"):
            sns.delete_endpoint(EndpointArn=item["endpointArn"])
    except Exception:
        pass

    # Remove from DynamoDB
    table.delete_item(Key={"deviceToken": device_token, "userId": user_id})

    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({"success": True}),
    }


def send_push(body, headers):
    """Send push notification to a specific device or all devices of a user."""
    target_user = body.get("userId")
    target_token = body.get("deviceToken")
    title = body.get("title", "Stack CRM")
    message_body = body.get("body", "")
    data = body.get("data", {})

    endpoints = []

    if target_token:
        # Send to specific device
        item = table.get_item(Key={"deviceToken": target_token, "userId": target_user or "anonymous"}).get("Item")
        if item:
            endpoints.append(item)
    elif target_user:
        # Send to all devices of a user
        result = table.scan(
            FilterExpression="userId = :uid",
            ExpressionAttributeValues={":uid": target_user},
        )
        endpoints = result.get("Items", [])

    if not endpoints:
        return {
            "statusCode": 404,
            "headers": headers,
            "body": json.dumps({"error": "No registered devices found"}),
        }

    sent = 0
    failed = 0

    for ep in endpoints:
        endpoint_arn = ep.get("endpointArn")
        platform = ep.get("platform", "android")

        try:
            if platform == "ios":
                # APNs payload
                payload = json.dumps({
                    "APNS": json.dumps({
                        "aps": {
                            "alert": {"title": title, "body": message_body},
                            "sound": "default",
                            "badge": 1,
                        },
                        "data": data,
                    })
                })
            else:
                # FCM payload
                payload = json.dumps({
                    "GCM": json.dumps({
                        "notification": {"title": title, "body": message_body, "sound": "default"},
                        "data": data,
                    })
                })

            sns.publish(
                TargetArn=endpoint_arn,
                Message=payload,
                MessageStructure="json",
            )
            sent += 1
        except Exception as e:
            print(f"Failed to send to {endpoint_arn}: {e}")
            failed += 1

    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({"sent": sent, "failed": failed}),
    }
