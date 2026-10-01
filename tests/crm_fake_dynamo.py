"""An in-memory DynamoDB good enough to test conditional writes honestly.

Why not a stub that records calls
---------------------------------
Everything worth testing in `crm.store` *is* the ConditionExpression. A fake that accepts
any condition would let a broken guard pass its tests - which is worse than no test, since
it produces confidence in a race that is still open.

So this evaluates conditions for real, and **raises `AssertionError` on any expression form
it does not understand** rather than assuming success. If the store grows a new condition
shape, the tests fail here until this fake is taught it. That is the intended cost.

Supported, and only this
------------------------
    condition   attribute_exists(X) | attribute_not_exists(X) | X = :v , joined by AND
    update      SET a = :v, b = if_not_exists(b, :v2) [REMOVE c, d] [ADD n :delta]
    query       one index, partition key .eq(value), optional range sort from the
                index name, ScanIndexForward, Limit

`ADD` and `if_not_exists` were added for the OTP throttle, which needs an atomic counter that
initialises its own window on first use. They are the two forms a rate limiter cannot be written
without: a read-then-increment is exactly the race the counter exists to close.

Not a general DynamoDB: no filter expressions, no BETWEEN, no projections, no pagination.
None of those are used by `crm.store`, and adding them unused would be code with no test
behind it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError as _BotoClientError


class FakeClientError(_BotoClientError):
    """A real `botocore.exceptions.ClientError`, not merely shaped like one.

    It used to be a bare `Exception` carrying a `.response` dict, which was enough for code that
    inspects `.response` — `order_keys`, `otp_challenge` and `crm.store` all do — but **not** for
    code written as `except ClientError:`. `webhook_dedup.claim_event` is written that way, and
    against the old fake its conditional branch never matched: every simulated collision fell
    through to the generic handler and took the fail-open path instead.

    So a test asserting "a duplicate is skipped" was quietly asserting "a duplicate is processed",
    and passing, because that is what fail-open returns. Subclassing the real exception is what
    makes both styles of error handling testable.
    """

    def __init__(self, code: str) -> None:
        super().__init__({"Error": {"Code": code, "Message": code}}, "FakeOperation")


_ATTR_EXISTS = re.compile(r"attribute_exists\(\s*([#\w]+)\s*\)")
_ATTR_NOT_EXISTS = re.compile(r"attribute_not_exists\(\s*([#\w]+)\s*\)")
_EQUALITY = re.compile(r"([#\w]+)\s*=\s*(:[\w]+)")
#: `attr <> :v` — matched BEFORE equality so the `=` inside `<>` is not mistaken for one. Used by
#: conditional settlements that must only write a row still in a given state (e.g. not-already-paid).
_INEQUALITY = re.compile(r"([#\w]+)\s*<>\s*(:[\w]+)")
_SET_CLAUSE = re.compile(r"\bSET\b(.*?)(?:\bREMOVE\b|\bADD\b|$)",
                        re.IGNORECASE | re.DOTALL)
_REMOVE_CLAUSE = re.compile(r"\bREMOVE\b(.*?)(?:\bSET\b|\bADD\b|$)",
                           re.IGNORECASE | re.DOTALL)
_ADD_CLAUSE = re.compile(r"\bADD\b(.*?)(?:\bSET\b|\bREMOVE\b|$)",
                        re.IGNORECASE | re.DOTALL)
_IF_NOT_EXISTS = re.compile(
    r"if_not_exists\(\s*([#\w]+)\s*,\s*(:[\w]+)\s*\)", re.IGNORECASE)


def _resolve(token: str, names: Dict[str, str]) -> str:
    """`#s` -> the real attribute name. An unmapped placeholder is a test bug, not a miss."""
    if token.startswith("#"):
        if token not in names:
            raise AssertionError(f"expression uses {token} with no ExpressionAttributeNames "
                                 "entry")
        return names[token]
    return token


def _evaluate_condition(condition: Optional[str], row: Optional[Dict[str, Any]],
                        values: Dict[str, Any], names: Dict[str, str]) -> bool:
    """True when the condition holds. Raises if the expression is not understood."""
    if not condition:
        return True

    text = " ".join(str(condition).split())
    if " OR " in text.upper():
        raise AssertionError("this fake does not implement OR; teach it before using one")

    consumed = text
    result = True

    for match in _ATTR_EXISTS.finditer(text):
        attr = _resolve(match.group(1), names)
        if row is None or attr not in row:
            result = False
        consumed = consumed.replace(match.group(0), "", 1)

    for match in _ATTR_NOT_EXISTS.finditer(text):
        attr = _resolve(match.group(1), names)
        if row is not None and attr in row:
            result = False
        consumed = consumed.replace(match.group(0), "", 1)

    # Inequality first: `<>` contains a `=` only in some writers' spelling, but matching it before
    # equality keeps the two from overlapping and leaves no stray fragment behind.
    for match in _INEQUALITY.finditer(text):
        attr = _resolve(match.group(1), names)
        expected = values[match.group(2)]
        # DynamoDB's `<>` is false when the attribute is absent, so a missing attribute never
        # satisfies "not equal to :v". Mirror that: absence -> condition fails.
        if row is None or attr not in row or row.get(attr) == expected:
            result = False
        consumed = consumed.replace(match.group(0), "", 1)

    for match in _EQUALITY.finditer(text):
        attr = _resolve(match.group(1), names)
        expected = values[match.group(2)]
        if row is None or row.get(attr) != expected:
            result = False
        consumed = consumed.replace(match.group(0), "", 1)

    leftover = consumed.replace("AND", "").replace("(", "").replace(")", "").strip()
    if leftover:
        raise AssertionError(f"unrecognised condition fragment: {leftover!r} "
                             f"(from {text!r})")
    return result


def _split_assignments(clause: str) -> List[str]:
    """Split a SET clause on commas that are NOT inside parentheses.

    A naive `split(",")` breaks `if_not_exists(a, :v)` in half and then fails to parse either
    piece, which surfaces as a confusing "only sets literal placeholders" error.
    """
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
                # `if_not_exists(attr, :v)` — keep what is there, else take the placeholder.
                existing_attr = _resolve(guarded.group(1), names)
                if existing_attr in out:
                    continue
                out[attribute] = values[guarded.group(2)]
                continue

            if not source.startswith(":"):
                raise AssertionError(
                    f"this fake only sets literal placeholders or if_not_exists(), got "
                    f"{assignment!r}")
            out[attribute] = values[source]

    remove_match = _REMOVE_CLAUSE.search(expression)
    if remove_match:
        for target in remove_match.group(1).split(","):
            target = target.strip()
            if target:
                out.pop(_resolve(target, names), None)

    add_match = _ADD_CLAUSE.search(expression)
    if add_match:
        for addition in _split_assignments(add_match.group(1)):
            pieces = addition.split()
            if len(pieces) != 2 or not pieces[1].startswith(":"):
                raise AssertionError(
                    f"this fake only ADDs a numeric placeholder to one attribute, got "
                    f"{addition!r}")
            attribute = _resolve(pieces[0], names)
            delta = values[pieces[1]]
            # DynamoDB's ADD treats a missing attribute as zero, which is precisely what makes
            # it usable as a counter without a separate initialise.
            out[attribute] = out.get(attribute, 0) + delta

    return out


def _key_condition_parts(expression: Any) -> tuple:
    """`(field, value)` out of a boto3 `Key('f').eq(v)`.

    Reads the private `_values`/`_name` attributes deliberately: the alternative is asking
    callers to pass the field separately, which would let a test pass while the store
    queried the wrong attribute.
    """
    values = getattr(expression, "_values", None)
    if not values or len(values) != 2:
        raise AssertionError("only a single-attribute .eq() key condition is supported")
    key, value = values
    name = getattr(key, "name", None) or getattr(key, "_name", None)
    if not name:
        raise AssertionError("could not read the key attribute name")
    return name, value


class FakeTable:
    def __init__(self, parent: "FakeDynamo", name: str, key_attr: str) -> None:
        self.parent = parent
        self.name = name
        self.key_attr = key_attr

    # -- helpers ---------------------------------------------------------
    @property
    def rows(self) -> Dict[Any, Dict[str, Any]]:
        return self.parent.tables.setdefault(self.name, {})

    def _fail_if_armed(self, operation: str) -> None:
        armed = self.parent.fail_on.pop((self.name, operation), None)
        if armed:
            raise armed

    # -- API -------------------------------------------------------------
    def put_item(self, Item=None, ConditionExpression=None,
                 ExpressionAttributeValues=None, ExpressionAttributeNames=None, **_):
        self.parent.calls.append((self.name, "put_item"))
        self._fail_if_armed("put_item")
        item = dict(Item or {})
        if self.key_attr not in item:
            raise AssertionError(f"{self.name} item is missing its key {self.key_attr}")
        existing = self.rows.get(item[self.key_attr])
        if not _evaluate_condition(ConditionExpression, existing,
                                   ExpressionAttributeValues or {},
                                   ExpressionAttributeNames or {}):
            raise FakeClientError("ConditionalCheckFailedException")
        self.rows[item[self.key_attr]] = item
        return {}

    def get_item(self, Key=None, **_):
        self.parent.calls.append((self.name, "get_item"))
        self._fail_if_armed("get_item")
        row = self.rows.get((Key or {})[self.key_attr])
        return {"Item": dict(row)} if row else {}

    def update_item(self, Key=None, UpdateExpression="", ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None,
                    ReturnValues=None, **_):
        self.parent.calls.append((self.name, "update_item"))
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

    def query(self, IndexName=None, KeyConditionExpression=None, Limit=None,
              ScanIndexForward=True, **_):
        self.parent.calls.append((self.name, f"query:{IndexName}"))
        self._fail_if_armed("query")
        if not IndexName:
            raise AssertionError("crm.store never queries the base table; "
                                 "a missing IndexName means a scan crept in")
        declared = self.parent.indexes.get(self.name, {})
        if IndexName not in declared:
            raise AssertionError(
                f"{self.name} has no index {IndexName!r}; declared: "
                f"{sorted(declared)}. An index used in code but absent from "
                "provisioning returns nothing in production.")
        partition, sort = declared[IndexName]

        field, value = _key_condition_parts(KeyConditionExpression)
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


class FakeDynamo:
    """A resource whose `.Table(name)` returns a `FakeTable`.

    `indexes` mirrors what provisioning actually creates, keyed
    ``{table: {index: (partition, sort)}}``. Querying an undeclared index raises, which is
    what catches the most expensive kind of mistake here: code that queries an index the
    provisioning script never created. In production that returns an empty result set, not
    an error, so a board or a queue simply looks empty forever.
    """

    def __init__(self, keys: Dict[str, str],
                 indexes: Optional[Dict[str, Dict[str, tuple]]] = None) -> None:
        self.keys = dict(keys)
        self.indexes = {k: dict(v) for k, v in (indexes or {}).items()}
        self.tables: Dict[str, Dict[Any, Dict[str, Any]]] = {}
        self.calls: List[tuple] = []
        self.fail_on: Dict[tuple, Exception] = {}

    def Table(self, name: str) -> FakeTable:  # noqa: N802 - boto3's spelling
        if name not in self.keys:
            raise AssertionError(f"unknown table {name!r}; declare its key in the fake")
        return FakeTable(self, name, self.keys[name])

    # -- test affordances ------------------------------------------------
    def arm_failure(self, table: str, operation: str, exc: Exception) -> None:
        """Make the next `operation` on `table` raise, once."""
        self.fail_on[(table, operation)] = exc

    def all_rows(self, table: str) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.tables.get(table, {}).values()]

    def count(self, table: str) -> int:
        return len(self.tables.get(table, {}))
