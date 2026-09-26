#!/usr/bin/env python3
"""Make the alarm estate actually able to tell someone, and prove it.

Why this exists
---------------
The account looked healthy: 42 CloudWatch alarms, none in `ALARM`, none in
`INSUFFICIENT_DATA`, none missing an action. Two independent defects hid behind
that, and both produce the same symptom - a green review.

**1. Alarms watching nothing.** `wecare-inbound-dlq-depth` and
`wecare-outbound-dlq-depth` carried a `QueueName` dimension of
`base-wecare-digital-*`, a prefix that no longer exists; the real queues are
`stack-wecare-digital-*`. CloudWatch does not validate a dimension against a live
resource, so both sat permanently `OK` against a metric with **zero datapoints
over 6 hours**. `stack-wecare-digital-notification-dlq` - the DLQ the unified
connected-call notification service depends on - had no alarm at all. Two PayU
alarms named a Lambda deleted with the provider, including a `UrlRequestCount > 0`
tripwire meant to catch anyone calling the retired webhook; a tripwire on an
absent resource never reports.

The statistic was wrong too, and repointing an alarm that is also statistically
wrong just moves the wrongness. `ApproximateNumberOfMessagesVisible` is a gauge,
not a counter: SQS emits it several times per period, so `Sum` over 300s adds
unrelated samples and the threshold stops meaning "messages present". `Maximum`
is the correct reduction, and it is what the one correct alarm in the family
(`wecare-bulk-dlq-depth`) already used.

**2. Alarms nobody receives.** 33 of 41 alarms published only to the SNS topic
`stack-wecare-digital`, whose sole subscriber is the `wecare-inbound-whatsapp`
Lambda - a message handler, not an alarm consumer. It used to crash on those
deliveries (`AttributeError: 'str' object has no attribute 'get'`, nine times in
seven days); that was fixed in `wa_internal_event.py`, which made it **skip**
them instead. So the notifications stopped crashing and started being silently
discarded. Razorpay webhook errors, payments-table throttling, API 5xx, bulk DLQ
depth, EventBridge failed invocations and Lambda throttles all fired into a void.

This does not remove that Lambda subscription - it may be intentional - it adds
`wecare-alarm-notifications`, whose single subscription is a **confirmed** email
to the owner, so every alarm has at least one path to a human. Purely additive.

    python scripts/provision_alarm_coverage.py            # report only, no writes
    python scripts/provision_alarm_coverage.py --apply
    python scripts/provision_alarm_coverage.py --verify

Exit codes: 0 every DLQ is monitored and every alarm can reach a human,
1 drift remains.
"""
from __future__ import annotations

import argparse
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
ALARM_TOPIC = f"arn:aws:sns:{REGION}:775261844268:wecare-alarm-notifications"
METRIC = "ApproximateNumberOfMessagesVisible"

# A DLQ holding anything at all is an incident, so the threshold is "more than
# zero" rather than a depth budget. Period 300s matches the rest of the family.
SPEC = {
    "statistic": "Maximum",
    "comparison": "GreaterThanThreshold",
    "threshold": 0.0,
    "period": 300,
    "evaluation_periods": 1,
    "treat_missing_data": "notBreaching",
}

# alarm name -> (queue name, description)
DESIRED = {
    "wecare-inbound-dlq-depth": (
        "stack-wecare-digital-inbound-dlq",
        "Messages in inbound DLQ (inbound WhatsApp processing failed)",
    ),
    "wecare-outbound-dlq-depth": (
        "stack-wecare-digital-outbound-dlq",
        "Messages in outbound DLQ (outbound send failed)",
    ),
    "wecare-notification-dlq-depth": (
        "stack-wecare-digital-notification-dlq",
        "Messages in notification DLQ (connected-call notification delivery failed)",
    ),
}


# Protocols that put a notification in front of a person. A `lambda` or `sqs`
# subscriber is a program, and a program that discards the message is
# indistinguishable from no subscriber at all.
HUMAN_PROTOCOLS = {"email", "email-json", "sms"}

# Fields DescribeAlarms returns that PutMetricAlarm accepts back unchanged.
# Copied field-by-field rather than with a blanket passthrough, so an unexpected
# response key cannot silently reshape a live alarm.
PUT_FIELDS = (
    "AlarmName",
    "AlarmDescription",
    "ActionsEnabled",
    "OKActions",
    "AlarmActions",
    "InsufficientDataActions",
    "MetricName",
    "Namespace",
    "Statistic",
    "ExtendedStatistic",
    "Dimensions",
    "Period",
    "Unit",
    "EvaluationPeriods",
    "DatapointsToAlarm",
    "Threshold",
    "ComparisonOperator",
    "TreatMissingData",
    "EvaluateLowSampleCountPercentile",
    "Metrics",
    "ThresholdMetricId",
)


def clients():
    cfg = Config(retries={"max_attempts": 10, "mode": "adaptive"})
    return (
        boto3.client("cloudwatch", region_name=REGION, config=cfg),
        boto3.client("sqs", region_name=REGION, config=cfg),
        boto3.client("sns", region_name=REGION, config=cfg),
    )


def human_topics(sns) -> set[str]:
    """Topic ARNs with at least one CONFIRMED human subscription.

    A pending email subscription is not coverage - SNS will not deliver to it
    until the recipient clicks confirm, so counting it would recreate exactly the
    kind of false green this script exists to remove.
    """
    out: set[str] = set()
    for page in sns.get_paginator("list_topics").paginate():
        for t in page.get("Topics", []):
            arn = t["TopicArn"]
            for sub_page in sns.get_paginator("list_subscriptions_by_topic").paginate(
                TopicArn=arn
            ):
                for s in sub_page.get("Subscriptions", []):
                    if s["Protocol"] in HUMAN_PROTOCOLS and not s[
                        "SubscriptionArn"
                    ].endswith("Pending"):
                        out.add(arn)
    return out


def put_kwargs(alarm: dict) -> dict:
    """Rebuild a faithful PutMetricAlarm call from a DescribeAlarms result."""
    kw = {k: alarm[k] for k in PUT_FIELDS if alarm.get(k) not in (None, [], "")}
    # A metric-math alarm carries `Metrics` and must not also send the
    # single-metric fields, or CloudWatch rejects the call.
    if "Metrics" in kw:
        for k in ("MetricName", "Namespace", "Statistic", "ExtendedStatistic",
                  "Dimensions", "Period", "Unit"):
            kw.pop(k, None)
    return kw


def live_queues(sqs) -> set[str]:
    out: set[str] = set()
    for page in sqs.get_paginator("list_queues").paginate():
        out.update(u.rsplit("/", 1)[-1] for u in page.get("QueueUrls", []) or [])
    return out


def existing_alarms(cw) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for page in cw.get_paginator("describe_alarms").paginate():
        for a in page.get("MetricAlarms", []):
            out[a["AlarmName"]] = a
    return out


def describe(alarm: dict) -> dict:
    dims = {d["Name"]: d["Value"] for d in alarm.get("Dimensions", [])}
    return {
        "queue": dims.get("QueueName"),
        "metric": alarm.get("MetricName"),
        "statistic": alarm.get("Statistic"),
        "comparison": alarm.get("ComparisonOperator"),
        "threshold": alarm.get("Threshold"),
        "period": alarm.get("Period"),
        "actions": alarm.get("AlarmActions") or [],
    }


def drift(alarm: dict | None, queue: str) -> list[str]:
    """Every way the live alarm differs from what it must be."""
    if alarm is None:
        return ["absent"]
    got = describe(alarm)
    problems = []
    if got["queue"] != queue:
        problems.append(f"dimension QueueName={got['queue']!r} should be {queue!r}")
    if got["metric"] != METRIC:
        problems.append(f"metric {got['metric']} should be {METRIC}")
    if got["statistic"] != SPEC["statistic"]:
        problems.append(
            f"statistic {got['statistic']} should be {SPEC['statistic']} "
            "(gauge metric, Sum double-counts samples)"
        )
    if got["comparison"] != SPEC["comparison"] or got["threshold"] != SPEC["threshold"]:
        problems.append(
            f"condition {got['comparison']} {got['threshold']} should be "
            f"{SPEC['comparison']} {SPEC['threshold']}"
        )
    if ALARM_TOPIC not in got["actions"]:
        problems.append("alarm action does not include wecare-alarm-notifications")
    return problems


def report(cw, sqs, sns) -> dict:
    queues = live_queues(sqs)
    alarms = existing_alarms(cw)
    reachable = human_topics(sns)

    state: dict = {
        "targets": {},
        "orphans": {},
        "unmonitored": [],
        "human_topics": sorted(reachable),
        "unreachable_alarms": sorted(
            name
            for name, a in alarms.items()
            if not (set(a.get("AlarmActions") or []) & reachable)
        ),
    }

    for name, (queue, _desc) in DESIRED.items():
        state["targets"][name] = {
            "queue": queue,
            "queue_exists": queue in queues,
            "drift": drift(alarms.get(name), queue),
        }

    # Any alarm anywhere whose QueueName names a queue that is not there.
    watched: dict[str, list[str]] = {}
    for a in alarms.values():
        dims = {d["Name"]: d["Value"] for d in a.get("Dimensions", [])}
        q = dims.get("QueueName")
        if q:
            watched.setdefault(q, []).append(a["AlarmName"])
    state["orphans"] = {q: n for q, n in watched.items() if q not in queues}

    dlqs = {q for q in queues if "dlq" in q.lower() or "dead-letter" in q.lower()}
    state["unmonitored"] = sorted(dlqs - set(watched))
    return state


def add_human_action(cw, alarms: dict, names: list[str]) -> int:
    """Append the human topic to alarms that cannot reach anyone.

    Existing actions are preserved. The Lambda subscription on
    `stack-wecare-digital` may well be intentional, and removing it is a separate
    decision from making sure a person also finds out.
    """
    changed = 0
    for name in names:
        alarm = alarms.get(name)
        if alarm is None:
            continue
        kw = put_kwargs(alarm)
        for key in ("AlarmActions", "OKActions"):
            actions = list(kw.get(key) or [])
            if ALARM_TOPIC not in actions:
                actions.append(ALARM_TOPIC)
            kw[key] = actions
        cw.put_metric_alarm(**kw)
        changed += 1
        print(f"  ROUTED {name} -> + wecare-alarm-notifications")
    return changed


def apply(cw, sqs, state) -> int:
    changed = 0
    for name, (queue, desc) in DESIRED.items():
        target = state["targets"][name]
        if not target["queue_exists"]:
            print(f"  SKIP {name}: queue {queue} does not exist", file=sys.stderr)
            continue
        if not target["drift"]:
            print(f"  ok   {name}")
            continue
        # PutMetricAlarm is an upsert, so this both repoints and creates.
        cw.put_metric_alarm(
            AlarmName=name,
            AlarmDescription=desc,
            Namespace="AWS/SQS",
            MetricName=METRIC,
            Dimensions=[{"Name": "QueueName", "Value": queue}],
            Statistic=SPEC["statistic"],
            ComparisonOperator=SPEC["comparison"],
            Threshold=SPEC["threshold"],
            Period=SPEC["period"],
            EvaluationPeriods=SPEC["evaluation_periods"],
            TreatMissingData=SPEC["treat_missing_data"],
            ActionsEnabled=True,
            AlarmActions=[ALARM_TOPIC],
            OKActions=[ALARM_TOPIC],
        )
        changed += 1
        print(f"  WROTE {name} -> {queue}  ({'; '.join(target['drift'])})")
    return changed


def verify(cw, sqs, sns) -> int:
    state = report(cw, sqs, sns)
    bad = 0
    for name, t in sorted(state["targets"].items()):
        if t["drift"]:
            bad += 1
            print(f"DRIFT  {name}: {'; '.join(t['drift'])}")
        else:
            print(f"OK     {name} -> {t['queue']}")
    if state["orphans"]:
        bad += 1
        print(f"ORPHAN alarms watching a nonexistent queue: {state['orphans']}")
    if state["unmonitored"]:
        bad += 1
        print(f"UNMONITORED DLQs: {state['unmonitored']}")
    if state["unreachable_alarms"]:
        bad += 1
        print(
            f"UNREACHABLE ({len(state['unreachable_alarms'])}) — no action topic has a "
            f"confirmed human subscriber: {state['unreachable_alarms']}"
        )
    if not bad:
        print(
            "\nEvery DLQ has an alarm, every alarm names a real queue, and every "
            "alarm can reach a human."
        )
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Provision DLQ depth alarms.")
    p.add_argument("--apply", action="store_true", help="write the alarms")
    p.add_argument("--verify", action="store_true", help="read back and exit nonzero on drift")
    args = p.parse_args(argv)

    try:
        cw, sqs, sns = clients()
        if args.verify:
            return verify(cw, sqs, sns)

        state = report(cw, sqs, sns)
        print("Desired DLQ alarms:")
        for name, t in sorted(state["targets"].items()):
            status = "ok" if not t["drift"] else "; ".join(t["drift"])
            print(f"  {name:32} -> {t['queue']:40} {status}")
        print(f"\nAlarms watching a queue that does not exist: {state['orphans'] or 'none'}")
        print(f"DLQs with no alarm at all: {state['unmonitored'] or 'none'}")
        print(
            f"\nTopics with a confirmed human subscriber: "
            f"{[t.rsplit(':', 1)[-1] for t in state['human_topics']] or 'NONE'}"
        )
        print(
            f"Alarms that cannot reach a human "
            f"({len(state['unreachable_alarms'])}): {state['unreachable_alarms'] or 'none'}"
        )

        if not args.apply:
            print("\nRead-only. Re-run with --apply to write.")
            return 0

        print("\nApplying:")
        n = apply(cw, sqs, state)
        # Re-read: the DLQ writes above changed action lists, so routing must be
        # decided from current state rather than the pre-apply snapshot.
        n += add_human_action(
            cw, existing_alarms(cw), report(cw, sqs, sns)["unreachable_alarms"]
        )
        print(f"\n{n} alarm(s) written. Verifying:")
        return verify(cw, sqs, sns)
    except (ClientError, BotoCoreError) as exc:
        print(f"AWS call failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
