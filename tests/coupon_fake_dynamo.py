"""An in-memory DynamoDB that evaluates `OR` conditions, for the coupon and hold stores.

Why this is not `tests/crm_fake_dynamo.py`
-----------------------------------------
That fake is excellent and is deliberately narrow: it raises `AssertionError` on `OR` and it
reads a boto3 `Key('f').eq(v)` object for a query. `coupon_store` needs both of the forms it
refuses, and for load-bearing reasons rather than stylistic ones:

* DECISION 5's hold gate is one conditional `UpdateItem` whose whole point is a three-way `OR`
  (`nobody holds it` OR `I already hold it` OR `the hold lapsed`). Testing it against a fake
  that cannot parse `OR` would mean not testing it.
* `coupon_store` holds no boto3 client at all - that is what makes it offline-testable - so its
  `KeyConditionExpression` is a STRING with `ExpressionAttributeNames`, not a `Key` object.

Teaching the shared fake both forms would mean editing a helper that eleven other test files
depend on, from a session that owns none of them. So this is a sibling, with the same discipline:
**any expression form it does not understand raises `AssertionError` rather than being assumed to
succeed.** A fake that accepts any condition would let a broken guard pass, which is worse than
no test at all, because it produces confidence in a race that is still open.

Supported, and only this
------------------------
    condition   attribute_exists(X) | attribute_not_exists(X) | X <op> :v
                joined by AND / OR, with parentheses. <op> is = <> < <= > >=
    update      SET a = :v [, ...]  REMOVE c, d  ADD #n :delta   in any order
    query       a string `#p = :v` key condition against one declared index, with
                ScanIndexForward and Limit
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError as _BotoClientError


class FakeClientError(_BotoClientError):
    """A real `botocore.exceptions.ClientError`, so `except ClientError:` code is testable too."""

    def __init__(self, code: str) -> None:
        super().__init__({"Error": {"Code": code, "Message": code}}, "FakeOperation")


_TOKEN = re.compile(r"""
      (?P<lparen>\()
    | (?P<rparen>\))
    | (?P<and>\bAND\b)
    | (?P<or>\bOR\b)
    | (?P<exists>attribute_exists\(\s*[#\w]+\s*\))
    | (?P<not_exists>attribute_not_exists\(\s*[#\w]+\s*\))
    | (?P<compare>[#\w]+\s*(?:<>|<=|>=|=|<|>)\s*:[\w]+)
    | (?P<space>\s+)
""", re.VERBOSE | re.IGNORECASE)

_SET_CLAUSE = re.compile(r"\bSET\b(.*?)(?:\bREMOVE\b|\bADD\b|\bDELETE\b|$)",
                         re.IGNORECASE | re.DOTALL)
_REMOVE_CLAUSE = re.compile(r"\bREMOVE\b(.*?)(?:\bSET\b|\bADD\b|\bDELETE\b|$)",
                            re.IGNORECASE | re.DOTALL)
_ADD_CLAUSE = re.compile(r"\bADD\b(.*?)(?:\bSET\b|\bREMOVE\b|\bDELETE\b|$)",
                         re.IGNORECASE | re.DOTALL)
_IF_NOT_EXISTS = re.compile(r"if_not_exists\(\s*([#\w]+)\s*,\s*(:[\w]+)\s*\)", re.IGNORECASE)
_KEY_CONDITION = re.compile(r"^\s*([#\w]+)\s*=\s*(:[\w]+)\s*$")


def _resolve(token: str, names: Dict[str, str]) -> str:
    token = token.strip()
    if token.startswith("#"):
        if token not in names:
            raise AssertionError(f"expression uses {token} with no ExpressionAttributeNames entry")
        return names[token]
    return token


def _tokenise(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if not match:
            raise AssertionError(f"unrecognised condition fragment at {text[position:]!r} "
                                 f"(from {text!r})")
        position = match.end()
        kind = match.lastgroup
        if kind != "space":
            tokens.append((kind, match.group()))
    return tokens


def _predicate(text: str, row: Optional[Dict[str, Any]], values: Dict[str, Any],
               names: Dict[str, str], kind: str) -> bool:
    if kind in ("exists", "not_exists"):
        attribute = _resolve(text[text.index("(") + 1:text.rindex(")")], names)
        present = row is not None and attribute in row
        return present if kind == "exists" else not present

    for operator in ("<>", "<=", ">=", "=", "<", ">"):
        left, found, right = text.partition(operator)
        if not found:
            continue
        attribute = _resolve(left, names)
        expected = values[right.strip()]
        if row is None or attribute not in row:
            # DynamoDB's comparators are all false against a missing attribute.
            return False
        actual = row[attribute]
        if operator == "=":
            return actual == expected
        if operator == "<>":
            return actual != expected
        if operator == "<":
            return actual < expected
        if operator == "<=":
            return actual <= expected
        if operator == ">":
            return actual > expected
        return actual >= expected
    raise AssertionError(f"unrecognised comparison {text!r}")


def _evaluate_condition(condition: Optional[str], row: Optional[Dict[str, Any]],
                        values: Dict[str, Any], names: Dict[str, str]) -> bool:
    """True when the condition holds. Raises on any form this fake does not implement."""
    if not condition:
        return True
    tokens = _tokenise(" ".join(str(condition).split()))
    index = 0

    def parse_or() -> bool:
        nonlocal index
        result = parse_and()
        while index < len(tokens) and tokens[index][0] == "or":
            index += 1
            right = parse_and()
            result = result or right
        return result

    def parse_and() -> bool:
        nonlocal index
        result = parse_factor()
        while index < len(tokens) and tokens[index][0] == "and":
            index += 1
            right = parse_factor()
            result = result and right
        return result

    def parse_factor() -> bool:
        nonlocal index
        if index >= len(tokens):
            raise AssertionError(f"truncated condition {condition!r}")
        kind, text = tokens[index]
        index += 1
        if kind == "lparen":
            inner = parse_or()
            if index >= len(tokens) or tokens[index][0] != "rparen":
                raise AssertionError(f"unbalanced parentheses in {condition!r}")
            index += 1
            return inner
        if kind in ("exists", "not_exists", "compare"):
            return _predicate(text, row, values, names, kind)
        raise AssertionError(f"unexpected token {text!r} in {condition!r}")

    outcome = parse_or()
    if index != len(tokens):
        raise AssertionError(f"trailing tokens in {condition!r}")
    return outcome


def _split_assignments(clause: str) -> List[str]:
    parts, depth, current = [], 0, []
    for character in clause:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _apply_update(expression: str, row: Dict[str, Any], values: Dict[str, Any],
                  names: Dict[str, str]) -> Dict[str, Any]:
    out = dict(row)

    set_match = _SET_CLAUSE.search(expression)
    if set_match:
        for assignment in _split_assignments(set_match.group(1)):
            target, _, source = (part.strip() for part in assignment.partition("="))
            attribute = _resolve(target, names)
            guarded = _IF_NOT_EXISTS.fullmatch(source)
            if guarded:
                if _resolve(guarded.group(1), names) in out:
                    continue
                out[attribute] = values[guarded.group(2)]
                continue
            if not source.startswith(":"):
                raise AssertionError(f"this fake only sets placeholders, got {assignment!r}")
            out[attribute] = values[source]

    remove_match = _REMOVE_CLAUSE.search(expression)
    if remove_match:
        for target in remove_match.group(1).split(","):
            if target.strip():
                out.pop(_resolve(target, names), None)

    add_match = _ADD_CLAUSE.search(expression)
    if add_match:
        for addition in _split_assignments(add_match.group(1)):
            pieces = addition.split()
            if len(pieces) != 2 or not pieces[1].startswith(":"):
                raise AssertionError(f"this fake ADDs one numeric placeholder, got {addition!r}")
            attribute = _resolve(pieces[0], names)
            # DynamoDB's ADD treats a missing attribute as zero, which is what makes it a
            # counter with no separate initialise.
            out[attribute] = out.get(attribute, 0) + values[pieces[1]]
    return out


class FakeTable:
    """One table. `calls` records `(operation, kwargs)` in order, so ordering is assertable."""

    def __init__(self, key_attr: str = "couponKey",
                 indexes: Optional[Dict[str, Tuple[str, Optional[str]]]] = None) -> None:
        self.key_attr = key_attr
        self.indexes = dict(indexes or {})
        self.rows: Dict[Any, Dict[str, Any]] = {}
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self.fail_on: Dict[str, Exception] = {}

    # -- test affordances -------------------------------------------------
    def arm_failure(self, operation: str, exc: Exception) -> None:
        """Make the next `operation` raise, once."""
        self.fail_on[operation] = exc

    def operations(self) -> List[str]:
        return [name for name, _ in self.calls]

    def seed(self, item: Dict[str, Any]) -> None:
        self.rows[item[self.key_attr]] = dict(item)

    def _fail_if_armed(self, operation: str) -> None:
        armed = self.fail_on.pop(operation, None)
        if armed:
            raise armed

    # -- API --------------------------------------------------------------
    def put_item(self, Item=None, ConditionExpression=None,
                 ExpressionAttributeValues=None, ExpressionAttributeNames=None, **_):
        self.calls.append(("put_item", {"Item": dict(Item or {}),
                                        "ConditionExpression": ConditionExpression}))
        self._fail_if_armed("put_item")
        item = dict(Item or {})
        if self.key_attr not in item:
            raise AssertionError(f"item is missing its key {self.key_attr}")
        if not _evaluate_condition(ConditionExpression, self.rows.get(item[self.key_attr]),
                                   ExpressionAttributeValues or {},
                                   ExpressionAttributeNames or {}):
            raise FakeClientError("ConditionalCheckFailedException")
        self.rows[item[self.key_attr]] = item
        return {}

    def get_item(self, Key=None, **kwargs):
        self.calls.append(("get_item", {"Key": dict(Key or {}), **kwargs}))
        self._fail_if_armed("get_item")
        row = self.rows.get((Key or {})[self.key_attr])
        return {"Item": dict(row)} if row else {}

    def update_item(self, Key=None, UpdateExpression="", ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None,
                    ReturnValues=None, **_):
        self.calls.append(("update_item", {
            "Key": dict(Key or {}), "UpdateExpression": UpdateExpression,
            "ConditionExpression": ConditionExpression,
            "ExpressionAttributeValues": dict(ExpressionAttributeValues or {}),
            "ExpressionAttributeNames": dict(ExpressionAttributeNames or {})}))
        self._fail_if_armed("update_item")
        key = (Key or {})[self.key_attr]
        existing = self.rows.get(key)
        values = ExpressionAttributeValues or {}
        names = ExpressionAttributeNames or {}
        if not _evaluate_condition(ConditionExpression, existing, values, names):
            raise FakeClientError("ConditionalCheckFailedException")
        base = dict(existing) if existing else {self.key_attr: key}
        updated = _apply_update(UpdateExpression, base, values, names)
        self.rows[key] = updated
        return {"Attributes": dict(updated)} if ReturnValues else {}

    def delete_item(self, Key=None, ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None, **_):
        self.calls.append(("delete_item", {"Key": dict(Key or {}),
                                           "ConditionExpression": ConditionExpression}))
        self._fail_if_armed("delete_item")
        key = (Key or {})[self.key_attr]
        if not _evaluate_condition(ConditionExpression, self.rows.get(key),
                                   ExpressionAttributeValues or {},
                                   ExpressionAttributeNames or {}):
            raise FakeClientError("ConditionalCheckFailedException")
        self.rows.pop(key, None)
        return {}

    def query(self, IndexName=None, KeyConditionExpression=None,
              ExpressionAttributeValues=None, ExpressionAttributeNames=None,
              Limit=None, ScanIndexForward=True, ExclusiveStartKey=None, **_):
        self.calls.append(("query", {"IndexName": IndexName,
                                     "KeyConditionExpression": KeyConditionExpression}))
        self._fail_if_armed("query")
        if not IndexName:
            raise AssertionError("a query with no IndexName is a base-table read; the coupon "
                                 "store must only ever query status-index")
        if IndexName not in self.indexes:
            raise AssertionError(
                f"no index {IndexName!r} is declared; an index used in code but absent from "
                f"provisioning returns nothing in production rather than an error")
        partition, sort = self.indexes[IndexName]
        match = _KEY_CONDITION.match(str(KeyConditionExpression or ""))
        if not match:
            raise AssertionError(
                f"only a single-attribute `#p = :v` key condition is supported, got "
                f"{KeyConditionExpression!r}")
        field = _resolve(match.group(1), ExpressionAttributeNames or {})
        value = (ExpressionAttributeValues or {})[match.group(2)]
        if field != partition:
            raise AssertionError(f"{IndexName} is partitioned on {partition!r}, "
                                 f"queried on {field!r}")
        items = [dict(row) for row in self.rows.values() if row.get(field) == value]
        if sort:
            items.sort(key=lambda r: (r.get(sort) is None, r.get(sort)),
                       reverse=not ScanIndexForward)
        if Limit:
            items = items[:Limit]
        return {"Items": items, "Count": len(items)}

    def scan(self, **_):  # pragma: no cover - present only so a scan FAILS LOUDLY
        raise AssertionError("the coupon store must never scan; every access is an exact-key "
                             "operation or the status-index query")
