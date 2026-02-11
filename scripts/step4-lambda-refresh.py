import boto3, sys
lam = boto3.client("lambda", region_name="us-east-1")
print("Updating Lambda config to force cold start...")
sys.stdout.flush()
r = lam.update_function_configuration(
    FunctionName="wecare-whatsapp-calling",
    Environment={"Variables": {
        "VERIFY_TOKEN": "wecare_calling_verify_2026",
        "CALL_LOG_TABLE": "base-wecare-digital-WhatsAppCallingTable",
        "META_TOKEN_SECRET": "wecare/meta-system-user-token",
        "META_API_VERSION": "v20.0",
        "LOG_LEVEL": "INFO",
        "AUTO_PICKUP_ENABLED": "true",
        "AUTO_PICKUP_IVR_URL": "https://app.wecare.digital/stream/media/ivr/ivr-greeting.mp3",
        "SYSTEM_CONFIG_TABLE": "base-wecare-digital-SystemConfigTable",
        "TOKEN_REFRESH": "v4",
    }},
)
print(f"Done. State: {r['State']}, LastModified: {r['LastModified']}")
