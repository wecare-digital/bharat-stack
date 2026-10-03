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
    transaction TransactItems of `Update`-with-ConditionExpression entries ONLY, in the
                real low-level AttributeValue shape

Two logs, and the distinction is load-bearing
---------------------------------------------
`calls` is the **attempt** log: it is appended BEFORE the condition is evaluated (`put_item`,
`update_item`, `delete_item`), so a cancelled attempt is still recorded. The existing suite
depends on exactly that meaning and none of its assertions change.

`applied` is the **outcome** log: appended inside the locked body only after every condition
passed and the mutation committed. One says what was tried, the other says what landed, and the
concurrency suite asserts both numbers — "B tried and was refused" is a stronger statement than
"B did not try", and it is unwritable with one log.

Atomicity
---------
One DynamoDB request is one indivisible evaluate-then-apply. CPython releases the GIL at
bytecode boundaries, so without a lock two threads can both pass `settled = :false` and both
apply — which would let the concurrency suite fail against CORRECT production code, or pass
pre-fix for a reason that is the fake rather than the module. `_lock` is held for the entire
body of every operation, condition evaluation included, and it is an `RLock` because subclass
overrides re-enter through `super()`.

A barrier in a subclass override must therefore wait BEFORE delegating to `super()`, never
inside the locked body.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError as _BotoClientError


class UnsupportedFakeOperation(BaseException):
    """An item shape or expression form this fake does not implement.

    Deliberately NOT an `Exception`. `gift_card_store` wraps the balance move in
    `except Exception` -> `GiftCardStoreUnavailable`, so an `AssertionError` here would be
    relabelled as a transient outage and the test author would go hunting for a throttle that
    never happened. A `BaseException` reaches the test with the real reason.

    Only the new transaction path raises this. The rest of the fake keeps its `AssertionError`s,
    because other tests drive paths that do not wrap them.
    """


class FakeClientError(_BotoClientError):
    """A real `botocore.exceptions.ClientError`, so `except ClientError:` code is testable too."""

    def __init__(self, code: str, *, cancellation_reasons: Optional[list] = None) -> None:
        response: Dict[str, Any] = {"Error": {"Code": code, "Message": code}}
        if cancellation_reasons is not None:
            # TOP level, a SIBLING of "Error" - that is where botocore puts it. Reading it from
            # response["Error"] yields [] on every real cancellation.
            response["CancellationReasons"] = cancellation_reasons
        super().__init__(response, "FakeOperation")


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


def _deserialise(value: Any, *, where: str) -> Any:
    """One AttributeValue back to a native value, with `{"N": ...}` forced to `int`.

    `TypeDeserializer` is the faithful inverse of the shape production emits, and importing it
    here is legal: this file lives in `tests/`, where botocore is already a dependency, and the
    gate that forbids `boto3` applies to `gift_card_store.py` rather than to the fake. A
    hand-rolled unmarshaller would be one more thing that can diverge from boto3, and the fake
    should be the reference rather than the side that is pinned.
    """
    from boto3.dynamodb.types import TypeDeserializer

    if not isinstance(value, dict) or len(value) != 1:
        raise UnsupportedFakeOperation(
            f"{where}: expected one AttributeValue-typed map, got {value!r}")
    native = TypeDeserializer().deserialize(value)
    if "N" in value:
        # `{"N": ...}` deserialises to Decimal. Production emits `str(int)` and refuses anything
        # that is not exactly an `int`, so a fractional N means the test built the item by hand.
        if native != native.to_integral_value():
            raise UnsupportedFakeOperation(
                f"{where}: {value!r} is not an integral number; production cannot emit one")
        return int(native)
    return native


def _deserialise_map(mapping: Any, *, where: str) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        raise UnsupportedFakeOperation(f"{where}: expected a map, got {mapping!r}")
    return {str(key): _deserialise(value, where=f"{where}[{key!r}]")
            for key, value in mapping.items()}


class FakeTable:
    """One table. `calls` records `(operation, kwargs)` in order, so ordering is assertable."""

    def __init__(self, key_attr: str = "couponKey",
                 indexes: Optional[Dict[str, Tuple[str, Optional[str]]]] = None,
                 name: str = "stack-wecare-digital-FakeTable") -> None:
        self.key_attr = key_attr
        self.indexes = dict(indexes or {})
        self.rows: Dict[Any, Dict[str, Any]] = {}
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        #: The OUTCOME log. Appended only after every condition passed and the mutation landed.
        self.applied: List[Tuple[str, Dict[str, Any]]] = []
        self.fail_on: Dict[str, Tuple[BaseException, int]] = {}
        #: The logical table name, so production can use only the real boto3 shape
        #: (`TableName=table.name`). A placeholder, not a claim about the live table.
        self.name = name
        #: One DynamoDB request = one indivisible evaluate+apply. `RLock`, not `Lock`, because
        #: subclass overrides re-enter through `super()`.
        self._lock = threading.RLock()

    # -- the real boto3 shape ---------------------------------------------
    @property
    def meta(self) -> "FakeTable":
        """`table.meta.client` resolves back to this fake.

        `TransactWriteItems` is a CLIENT operation, not a `Table` resource one, so production
        reaches it as `table.meta.client.transact_write_items(...)`. The adaptation belongs here
        rather than as a fake-shaped branch in the store.
        """
        return self

    @property
    def client(self) -> "FakeTable":
        return self

    # -- test affordances -------------------------------------------------
    def arm_failure(self, operation: str, exc: BaseException, *, times: int = 1) -> None:
        """Make the next `times` calls to `operation` raise `exc`.

        `times` exists because a one-shot arm cannot express "fail the same op twice":
        `_fail_if_armed` CONSUMES the arm with `self.fail_on.pop(operation, None)`, so two
        `arm_failure` calls before the two operations produce ONE failure and the second
        `pytest.raises` then fails against correct code. A decrementing counter keeps the
        arming visible at the arming site instead of hiding a re-arm in the middle of a test
        body, and it makes a test whose narrative says "armed twice" literally true.

        Defaulted to `1`, so every existing call site is unaffected.
        """
        if type(times) is not int or times < 1:
            raise AssertionError("times must be a positive int")
        self.fail_on[operation] = (exc, times)

    def operations(self) -> List[str]:
        return [name for name, _ in self.calls]

    def seed(self, item: Dict[str, Any]) -> None:
        self.rows[item[self.key_attr]] = dict(item)

    def _fail_if_armed(self, operation: str) -> None:
        armed = self.fail_on.get(operation)
        if not armed:
            return
        exc, remaining = armed
        if remaining <= 1:
            self.fail_on.pop(operation, None)
        else:
            self.fail_on[operation] = (exc, remaining - 1)
        raise exc

    # -- API --------------------------------------------------------------
    def put_item(self, Item=None, ConditionExpression=None,
                 ExpressionAttributeValues=None, ExpressionAttributeNames=None, **_):
        with self._lock:
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
            self.applied.append(("put_item", {"Item": dict(item)}))
            return {}

    def get_item(self, Key=None, **kwargs):
        with self._lock:
            self.calls.append(("get_item", {"Key": dict(Key or {}), **kwargs}))
            self._fail_if_armed("get_item")
            row = self.rows.get((Key or {})[self.key_attr])
            return {"Item": dict(row)} if row else {}

    def update_item(self, Key=None, UpdateExpression="", ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None,
                    ReturnValues=None, **_):
        with self._lock:
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
            self.applied.append(("update_item", {
                "Key": dict(Key or {}), "UpdateExpression": UpdateExpression}))
            return {"Attributes": dict(updated)} if ReturnValues else {}

    def transact_write_items(self, TransactItems=None, **_):
        """`TransactWriteItems` over `Update`-with-`ConditionExpression` items only.

        All or nothing: every condition is evaluated against current state FIRST, and nothing
        mutates unless all of them hold. On any failure it raises
        `FakeClientError("TransactionCanceledException", cancellation_reasons=[...])` carrying
        `{"Code": "ConditionalCheckFailed"}` for the items that failed and `{"Code": "None"}`
        for those that did not - the shape the store's reason-code branch reads.

        `calls` records the item list AS RECEIVED, so an assertion can be made on the wire form
        (every `"N"` must match `^-?[0-9]+$`).
        """
        with self._lock:
            items = list(TransactItems or [])
            self.calls.append(("transact_write_items", {"TransactItems": items}))
            self._fail_if_armed("transact_write_items")
            if not items:
                raise UnsupportedFakeOperation("a transaction needs at least one item")

            parsed: List[Tuple[Any, str, Dict[str, Any], Dict[str, str], Optional[str]]] = []
            outcomes: List[bool] = []
            for index, entry in enumerate(items):
                where = f"TransactItems[{index}]"
                if not isinstance(entry, dict) or set(entry) != {"Update"}:
                    raise UnsupportedFakeOperation(
                        f"{where}: this fake implements only `Update` items, got "
                        f"{sorted(entry) if isinstance(entry, dict) else entry!r}")
                update = entry["Update"]
                if not isinstance(update, dict):
                    raise UnsupportedFakeOperation(f"{where}: Update must be a map")
                if not update.get("TableName"):
                    raise UnsupportedFakeOperation(f"{where}: Update needs a TableName")
                condition = update.get("ConditionExpression")
                if not condition:
                    raise UnsupportedFakeOperation(
                        f"{where}: this fake implements only Update WITH a ConditionExpression; "
                        f"an unconditioned transaction item is not a shape this design uses")
                key_map = _deserialise_map(update.get("Key"), where=f"{where}.Key")
                if self.key_attr not in key_map:
                    raise UnsupportedFakeOperation(
                        f"{where}: Key is missing {self.key_attr}")
                values = _deserialise_map(update.get("ExpressionAttributeValues") or {},
                                          where=f"{where}.ExpressionAttributeValues")
                names = {str(k): str(v) for k, v in
                         (update.get("ExpressionAttributeNames") or {}).items()}
                expression = str(update.get("UpdateExpression") or "")
                key = key_map[self.key_attr]
                parsed.append((key, expression, values, names, str(condition)))
                outcomes.append(_evaluate_condition(condition, self.rows.get(key), values, names))

            if not all(outcomes):
                raise FakeClientError(
                    "TransactionCanceledException",
                    cancellation_reasons=[
                        {"Code": "None"} if held else {"Code": "ConditionalCheckFailed"}
                        for held in outcomes])

            for key, expression, values, names, _condition in parsed:
                base = dict(self.rows[key]) if key in self.rows else {self.key_attr: key}
                self.rows[key] = _apply_update(expression, base, values, names)
            self.applied.append(("transact_write_items", {"TransactItems": items}))
            return {}

    def delete_item(self, Key=None, ConditionExpression=None,
                    ExpressionAttributeValues=None, ExpressionAttributeNames=None, **_):
        with self._lock:
            self.calls.append(("delete_item", {"Key": dict(Key or {}),
                                               "ConditionExpression": ConditionExpression}))
            self._fail_if_armed("delete_item")
            key = (Key or {})[self.key_attr]
            if not _evaluate_condition(ConditionExpression, self.rows.get(key),
                                       ExpressionAttributeValues or {},
                                       ExpressionAttributeNames or {}):
                raise FakeClientError("ConditionalCheckFailedException")
            self.rows.pop(key, None)
            self.applied.append(("delete_item", {"Key": dict(Key or {})}))
            return {}

    def query(self, IndexName=None, KeyConditionExpression=None,
              ExpressionAttributeValues=None, ExpressionAttributeNames=None,
              Limit=None, ScanIndexForward=True, ExclusiveStartKey=None, **_):
        with self._lock:
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
