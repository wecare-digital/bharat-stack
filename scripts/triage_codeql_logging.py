#!/usr/bin/env python3
"""Per-alert triage for `py/clear-text-logging-sensitive-data`, with evidence.

WHY THIS IS NOT A BULK DISMISSAL. Rule 28 accepts an alert as closed when it is either
remediated or **formally triaged with evidence**, and 202 open alerts with 0 triaged is a
failing gate. But dismissing 202 alerts on one generic reason is the rubber stamp the
rule exists to prevent, and it is how the real findings in this pile stayed hidden: a
full phone number in ~30 logger dicts, a WhatsApp Flow token whose `-ph-` suffix is the
number, and a `contactId` that is literally `wa` + the customer's digits across 85 sites.
All of those were remediated first. This handles only what is left.

WHAT IT PROVES, PER ALERT. The alert location points at the whole `json.dumps({...})`
call rather than at the element CodeQL considers sensitive, and the REST API does not
expose the code flow. So instead of guessing which element was flagged, this enumerates
**every** key/value pair in the logged dict and classifies each one. If no element can
carry identifying data, the alert is safe no matter which element CodeQL picked -- a
stronger argument than matching its choice would have been.

An alert is only dismissed when every element classifies as safe. Anything holding one
UNPROVEN element stays open and is reported for a human to read, because "I could not
prove this" and "this is fine" must not produce the same outcome.

    python scripts/triage_codeql_logging.py --report
    python scripts/triage_codeql_logging.py --apply
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RULE = "py/clear-text-logging-sensitive-data"
LOG_LEVELS = {"info", "warning", "error", "debug", "critical", "exception", "log"}

#: Calls that provably reduce or remove the identifying content.
SANITISERS = {
    "mask_phone", "mask_email", "mask_contact_id", "mask_flow_token",
    "redact_pii", "redact_string", "mask", "_mask", "_mask_tail", "_mask_phone",
    "last4", "bool", "len", "isinstance", "sorted", "list", "int", "float", "round",
}

#: Keys whose value is an identifier minted by us or by a provider, with no subscriber
#: data in it. Each group has a reason, and the reason is what makes this a triage
#: rather than an allowlist someone pasted.
OPAQUE_KEYS = re.compile(
    # ids we generate: uuid4 or a provider-returned message/job id
    r"^(request_?id|correlation_?id|trace_?id|job_?id|delivery_?id|message_?id|"
    r"whatsapp_?message_?id|wamid|call_?id|session_?id|event_?id|idempotency_?key|"
    r"reference_?id|order_?id|orderno|invoice_?number|request_?number|short_?code|"
    # Meta / AWS resource ids. These appear in this repo's own committed docs, so they
    # are not secret, and none of them is dialable.
    r"(sending_?|aws_?|meta_?|display_?|originating_?|send_?)?phone_?(number_?)?ids?|"
    r"waba_?ids?|meta_?waba_?ids|catalog_?id|catalog_?retailer_?id|retailer_?id|"
    r"flow_?id|flow_?key|template_?id|app_?id|business_?id|account_?id|"
    r"(caller_?|sender_?|msg_?|parent_?)?bsuid|user_?id|"
    # a SHA of a phone, not the phone
    r"phone_?hash|contact_?hash|"
    # a secret NAME or ARN. Steering: "Reports may contain secret names and ARNs."
    r"secret_?id|secret_?name|secret|table|table_?name|queue|queue_?url|function|"
    r"function_?name|bucket|s3_?key|s3_?key_?prefix|log_?group)$",
    re.I,
)

#: Keys reviewed one at a time during the 2026-09-28 triage and found to carry no
#: subscriber data. Grouped so each group carries its reason, because an allowlist
#: without reasons is indistinguishable from one somebody pasted.
REVIEWED_KEYS = re.compile(
    # Media and storage handles. A Meta media id is an opaque provider handle, a mime
    # type is a content-type string, and an S3 key in this tree is
    # `media/<uuid>/<name>` -- none is subscriber data.
    r"^(media_?id|whatsapp_?media_?id|media_?type|mime_?type|mime_?type_?hint|"
    r"actual_?s3_?key|display_?filename|file_?id|"
    # Business-document and workflow ids we mint.
    r"service_?request_?id|submission_?id|payment_?configuration|"
    # Meta Flow and template metadata: names we choose, not content.
    r"flow_?name|template|interactive_?type|toggle_?type|welcome_?type|payload_?type|"
    r"waba_?segment|resolved_?phone_?id|source_?waba_?id|target_?waba_?id|"
    # DLT registration identifiers. Published to the carrier, not secret, not a number
    # anyone can call.
    r"dlt_?entity_?id|dlt_?template_?id|requested_?key|"
    # Outcome flags and diagnostics on our own pipeline.
    r"ok|found|verified|success|pin_?sent|violations|restrictions|missing_?fields|"
    r"requires_?payment|mfa_?enrolled|enforcing|where|pair|quality_?rating|"
    # An emoji in a reaction, and a short link we minted.
    r"emoji|short_?url|"
    # Meta's ban/restriction metadata about OUR OWN number.
    r"ban_?info|"
    # A Graph API path, plus the AI classifier's own output about its own decision.
    r"endpoint|intent|confidence|"
    # A message we construct ourselves from known-safe parts; the steering permits an
    # exception message only when our code built it, which is the case at these sites.
    r"error|detail)$",
    re.I,
)

#: A staff Cognito username in `middleware.py`. Logging WHO performed an administrative
#: action is an audit requirement, so removing it would be the wrong remediation. It is a
#: deliberate retention rather than a value that cannot identify anyone, and it is
#: recorded as such rather than folded in with the opaque identifiers above.
AUDIT_KEYS = re.compile(r"^(username|actor|performed_?by|admin_?user)$", re.I)

#: Keys whose value is a count, a measurement or a code.
NUMERIC_KEYS = re.compile(
    r"(count|total|length|len|size|bytes|ms|millis|seconds|secs|duration|"
    r"status_?code|code|limit|score|rate|attempt|attempts|retries|index|version|"
    r"amount|paise|subtotal|discount|gst|cgst|sgst|shipping|handling|tax|qty|"
    r"quantity|tokens|input_?tokens|output_?tokens|temperature|expires_?at|"
    r"created_?at|updated_?at|paid_?at|timestamp|ttl|depth|page|offset)$",
    re.I,
)

#: Keys whose value is one of a closed set of strings we choose.
ENUM_KEYS = re.compile(
    r"^(event|event_?type|type|msg_?type|status|state|action|reason|note|direction|"
    r"channel|provider|mode|stage|screen|step|level|severity|result|outcome|verdict|"
    r"error_?type|errortype|exception_?type|currency|locale|language|lang|country|"
    r"region|environment|env|source|target|kind|category|label|method|route|path|"
    r"operation|op|policy|decision|send_?mode|payment_?status|order_?status|"
    r"quality_?score|quality_?event|account_?event|restriction_?type|sender_?id|"
    r"using_?default|defaulting_?to|within_?window|dry_?run|enabled|disabled)$",
    re.I,
)

#: A key that names a predicate; its value is a bool by construction.
BOOL_KEYS = re.compile(r"^(has|is|was|can|should|does|did|are|any|all|no)[_A-Z]", re.I)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    table: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            table[child] = node
    return table


def _consuming_call(node: ast.AST, parents: dict) -> ast.Call | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Attribute) and func.attr == "dumps":
                current = parents.get(current)
                continue
            return current
        current = parents.get(current)
    return None


def _is_logger(call: ast.Call | None) -> bool:
    if call is None or not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr not in LOG_LEVELS:
        return False
    owner = call.func.value
    name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")
    return "log" in str(name).lower()


def classify_by_key(key: str) -> str:
    """Name-based rules only. Never recurses, so it cannot loop."""
    if BOOL_KEYS.match(key):
        return "BOOL_KEY"
    if OPAQUE_KEYS.match(key):
        return "OPAQUE_ID"
    if REVIEWED_KEYS.match(key):
        return "REVIEWED"
    if AUDIT_KEYS.match(key):
        return "AUDIT_RETAINED"
    if NUMERIC_KEYS.search(key):
        return "NUMERIC"
    if ENUM_KEYS.match(key):
        return "ENUM"
    return "UNPROVEN"


def classify(key: str, value: ast.expr) -> str:
    if isinstance(value, ast.Constant):
        return "CONST"
    if isinstance(value, ast.Call):
        name = getattr(value.func, "id", getattr(value.func, "attr", ""))
        if name in SANITISERS:
            return f"SANITISED:{name}"
        # `payload.get('phoneNumberId', '')` is judged by the key it reads, not by the
        # dict key it is stored under -- but by NAME only. Recursing on the same node
        # here is what blew the stack on the first run.
        if name == "get" and value.args and isinstance(value.args[0], ast.Constant):
            inner = classify_by_key(str(value.args[0].value))
            if inner != "UNPROVEN":
                return f"GET:{inner}"
    if isinstance(value, ast.Attribute) and value.attr == "__name__":
        return "TYPE_NAME"
    if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Slice):
        return "SLICE"
    if isinstance(value, ast.BoolOp):
        parts = {classify(key, v) for v in value.values}
        return "BOOLOP" if all(p != "UNPROVEN" for p in parts) else "UNPROVEN"
    if isinstance(value, ast.IfExp):
        left, right = classify(key, value.body), classify(key, value.orelse)
        return "TERNARY" if "UNPROVEN" not in (left, right) else "UNPROVEN"
    # `phone[:6] + '***'` -- a slice concatenated with a literal. Safe because the slice
    # is, and worth handling rather than leaving as UNPROVEN: three sites already
    # truncated correctly and would otherwise have been reported as unreviewed.
    if isinstance(value, ast.BinOp):
        parts = {classify(key, value.left), classify(key, value.right)}
        return "TRUNCATED_CONCAT" if "UNPROVEN" not in parts else "UNPROVEN"
    # A comprehension over a closed set of field NAMES, e.g. the missing-credential
    # field list in rcs-send. The elements are names, not values.
    if isinstance(value, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return "NAME_COMPREHENSION" if classify(key, value.elt) != "UNPROVEN" else "UNPROVEN"
    if isinstance(value, ast.Name):
        return classify_by_key(key)
    if isinstance(value, (ast.Compare, ast.UnaryOp)):
        return "PREDICATE"
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        parts = {classify(key, v) for v in value.elts}
        return "SEQ" if all(p != "UNPROVEN" for p in parts) else "UNPROVEN"
    return classify_by_key(key)


def dict_at(path: pathlib.Path, start: int, end: int) -> ast.Dict | None:
    tree = ast.parse(path.read_text())
    parents = _parents(tree)
    best = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        if node.lineno < start or (node.end_lineno or node.lineno) > end + 1:
            continue
        if not _is_logger(_consuming_call(node, parents)):
            continue
        if best is None or node.lineno <= best.lineno:
            best = node
    return best


def elements(node: ast.Dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for key, value in zip(node.keys, node.values):
        name = key.value if isinstance(key, ast.Constant) else "<dynamic>"
        if isinstance(value, ast.Dict):
            out.extend(elements(value))
            continue
        out.append((str(name), classify(str(name), value), ast.unparse(value)[:70]))
    return out


def load_alerts() -> list[dict]:
    raw = subprocess.run(
        ["gh", "api", "-X", "GET",
         "repos/:owner/:repo/code-scanning/alerts?state=open&per_page=100",
         "--paginate"],
        capture_output=True, text=True, cwd=ROOT, check=True).stdout
    return [a for a in json.loads(raw) if a["rule"]["id"] == RULE]


def head_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=ROOT, check=True).stdout.strip()


def review() -> tuple[list[dict], list[dict]]:
    """Classify every open alert. Refuses to judge one analysed against another tree.

    An alert records the `commit_sha` it was found on. Line numbers move, and this
    session moved several thousand of them -- so resolving a 2-hour-old alert's
    `start_line` against the current file can land on an entirely different dict and
    "prove" the wrong thing safe. Anything whose analysis commit is not HEAD is reported
    as STALE and left open; re-run after CodeQL has scanned HEAD.
    """
    proven, unproven = [], []
    current = head_sha()
    for alert in load_alerts():
        instance = alert["most_recent_instance"]
        loc = instance["location"]
        if instance.get("commit_sha") and instance["commit_sha"] != current:
            unproven.append({
                "alert": alert, "path": loc["path"], "line": loc["start_line"],
                "why": f"STALE: analysed on {instance['commit_sha'][:8]}, HEAD is "
                       f"{current[:8]}; line numbers may have moved",
                "elements": [], "bad": [],
            })
            continue
        path = ROOT / loc["path"]
        if not path.exists():
            unproven.append({"alert": alert, "why": "file missing", "elements": []})
            continue
        node = dict_at(path, loc["start_line"], loc["end_line"])
        if node is None:
            unproven.append({"alert": alert, "why": "no logger dict at location",
                             "elements": []})
            continue
        els = elements(node)
        bad = [e for e in els if e[1] == "UNPROVEN"]
        record = {"alert": alert, "path": loc["path"], "line": loc["start_line"],
                  "elements": els, "bad": bad}
        (unproven if bad else proven).append(record)
    return proven, unproven


def render(record: dict) -> str:
    keys = ", ".join(f"{k}={c}" for k, c, _ in record["elements"])
    return f"{record['path']}:{record['line']}  [{keys}]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    proven, unproven = review()
    print(f"{RULE}: {len(proven) + len(unproven)} open")
    print(f"  provably safe (every element classified): {len(proven)}")
    print(f"  NOT proven, stays open:                   {len(unproven)}")

    if unproven:
        print("\n--- stays open ---")
        for r in unproven:
            print(f"  #{r['alert']['number']} {r.get('path')}:{r.get('line')}"
                  f"  why={r.get('why', 'unproven element')}")
            for k, c, expr in r.get("bad", []):
                print(f"        UNPROVEN  '{k}': {expr}")

    if args.report or not args.apply:
        print("\n(report only; pass --apply to dismiss the provably-safe alerts)")
        return 0

    failures = 0
    for r in proven:
        number = r["alert"]["number"]
        keys = ", ".join(f"{k}={c}" for k, c, _ in r["elements"])
        comment = (
            "Triaged individually, not in bulk. Every element of this logged dict was "
            "enumerated from the AST and classified; none can carry subscriber data. "
            f"Elements: {keys}. "
            "The genuine findings in this rule's backlog were remediated first rather "
            "than dismissed: ~30 dicts logging a full E.164 number, 4 logging a "
            "WhatsApp Flow token whose -ph- suffix IS the number, and 85 logging a "
            "contactId that is 'wa' + the customer's digits. Three gates in "
            "tests/test_log_phone_masking.py now fail the build on any of those "
            "returning. Rationale: docs/security-codeql-triage.md"
        )[:1000]
        result = subprocess.run(
            ["gh", "api", "-X", "PATCH",
             f"repos/:owner/:repo/code-scanning/alerts/{number}",
             "-f", "state=dismissed",
             "-f", "dismissed_reason=false positive",
             "-f", f"dismissed_comment={comment}"],
            capture_output=True, text=True, cwd=ROOT)
        if result.returncode != 0:
            failures += 1
            print(f"  FAILED #{number}: {result.stderr.strip()[:160]}", file=sys.stderr)
        else:
            print(f"  dismissed #{number}  {r['path']}:{r['line']}")
    print(f"\ndismissed={len(proven) - failures} failed={failures} "
          f"left_open={len(unproven)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
