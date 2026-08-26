"""
Create the webhook idempotency guardrail live (boto3), matching the repo convention
where alarms are created via script because ampx can't run in the agent environment.

- Metric filters on the 4 webhook-consumer log groups: emit WECARE.DIGITAL/WebhookDedupErrors
  whenever a "webhook_dedup_error" line is logged (claim_event failing open).
- Alarm wecare-webhook-dedup-errors -> SNS wecare-alarm-notifications.

Idempotent (put_* are upserts). Cost: metric filters free; ~1 alarm (~$0.10/mo).
"""
import boto3

REGION = "us-east-1"
NS = "WECARE.DIGITAL"
METRIC = "WebhookDedupErrors"
SNS_ARN = "arn:aws:sns:us-east-1:775261844268:wecare-alarm-notifications"
CONSUMERS = [
    "wecare-inbound-whatsapp", "wecare-razorpay-webhook",
    "wecare-whatsapp-business-api",
]

logs = boto3.client("logs", region_name=REGION)
cw = boto3.client("cloudwatch", region_name=REGION)

for fn in CONSUMERS:
    lg = f"/aws/lambda/{fn}"
    logs.put_metric_filter(
        logGroupName=lg,
        filterName="webhook-dedup-error",
        filterPattern='"webhook_dedup_error"',
        metricTransformations=[{
            "metricName": METRIC,
            "metricNamespace": NS,
            "metricValue": "1",
            "defaultValue": 0.0,
        }],
    )
    print(f"metric filter set on {lg}")

cw.put_metric_alarm(
    AlarmName="wecare-webhook-dedup-errors",
    AlarmDescription="webhook_dedup_error logged — idempotency failing open (possible missing/broken WebhookDedup table)",
    Namespace=NS,
    MetricName=METRIC,
    Statistic="Sum",
    Period=300,
    EvaluationPeriods=1,
    Threshold=5.0,
    ComparisonOperator="GreaterThanThreshold",
    TreatMissingData="notBreaching",
    AlarmActions=[SNS_ARN],
    OKActions=[],
)
print("alarm wecare-webhook-dedup-errors created")

a = cw.describe_alarms(AlarmNames=["wecare-webhook-dedup-errors"])["MetricAlarms"][0]
print(f"verify: {a['AlarmName']} state={a['StateValue']} alarm_actions={len(a['AlarmActions'])} ok_actions={len(a.get('OKActions', []))}")
