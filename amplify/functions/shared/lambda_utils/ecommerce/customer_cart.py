"""Phone-keyed backend cart using the existing WixOrderIds table (D4).

Keys have a namespace; immutable order keys must never acquire DynamoDB TTL.
Cart expiry is enforced by this application. A lock with an uncertain Wix outcome
is never stolen on expiry: readback/reconciliation is required before reuse.
"""
import hashlib
import json
import re
import time
from decimal import Decimal
from uuid import uuid4

from lambda_utils.customer_auth import authorize_resource
from .cart_v2 import catalog_item, identifier

CART_LIFETIME = 30 * 24 * 3600
QUOTE_LIFETIME = 300


class CartBusy(RuntimeError):
    pass


class CartMissing(ValueError):
    pass


def _conditional(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _public_numbers(value):
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            raise ValueError("nonintegral public cart number")
        return int(value)
    if isinstance(value, dict):
        return {key: _public_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_numbers(item) for item in value]
    return value


def _key(identity):
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", identity.phone or ""):
        raise ValueError("verified E.164 phone required")
    return "CUSTOMERCART#" + identity.phone


class CustomerCart:
    def __init__(self, table, adapter, now=None):
        self.table, self.adapter = table, adapter
        self.now = int(time.time()) if now is None else now

    def execute(self, identity, command):
        """Identity comes from customer_auth or a verified WhatsApp webhook adapter.

        A browser cannot supply phone, customerId, Wix cart id or money. Duplicate
        writes need the same requestId and same command, and return the saved result.
        """
        if not isinstance(command, dict):
            raise ValueError("cart command must be an object")
        action = command.get("action")
        allowed = {"get": {"action"}, "create": {"action", "requestId", "items"},
                   "add": {"action", "requestId", "item"},
                   "quantity": {"action", "requestId", "lineItemId", "quantity"},
                   "remove": {"action", "requestId", "lineItemId"},
                   "calculate": {"action", "requestId"}}
        if action not in allowed or set(command) != allowed[action]:
            raise ValueError("unsupported cart command fields")
        request_id = identifier(command["requestId"]) if action != "get" else str(uuid4())
        if action == "create":
            if not isinstance(command["items"], list) or not 1 <= len(command["items"]) <= 100:
                raise ValueError("1 to 100 items required")
            for item in command["items"]:
                catalog_item(item)
        if action == "add":
            catalog_item(command["item"])
        if action in ("quantity", "remove"):
            identifier(command["lineItemId"])
        if action == "quantity" and (type(command["quantity"]) is not int or
                                      not 1 <= command["quantity"] <= 100000):
            raise ValueError("positive integer quantity required")
        fingerprint = hashlib.sha256(json.dumps(command, sort_keys=True).encode()).hexdigest()
        key = {"orderId": _key(identity)}
        op_key = {"orderId": "CARTOP#" + hashlib.sha256(identity.phone.encode()).hexdigest()
                  + "#" + request_id}
        operation = (self.table.get_item(Key=op_key, ConsistentRead=True).get("Item")
                     if action != "get" else None)
        if operation:
            authorize_resource(identity, operation)
            if operation.get("fingerprint") != fingerprint:
                raise ValueError("requestId was used for another command")
            if operation.get("state") != "DONE":
                raise CartBusy("operation requires reconciliation")
            if operation.get("failed"):
                raise ValueError("calculation validation failed")
            result = operation["result"]
            if result.get("expiresAt", self.now + 1) <= self.now:
                raise ValueError("calculation expired; request a fresh quote")
            if action == "calculate":
                current = self.table.get_item(Key=key, ConsistentRead=True).get("Item") or {}
                if (current.get("busy") or
                        (current.get("snapshot") or {}).get("calculationId") != operation.get("calculationId")):
                    raise ValueError("calculation was invalidated; request a fresh quote")
            return _public_numbers(result)
        row = self.table.get_item(Key=key, ConsistentRead=True).get("Item")
        if row:
            authorize_resource(identity, row)
            if row.get("busy"):
                raise CartBusy("cart operation requires reconciliation")
        active = row and int(row.get("expiresAt", 0)) > self.now
        if action == "create" and active:
            raise ValueError("an active cart already exists")
        if action != "create" and not active:
            raise CartMissing("no active cart")
        lock = str(uuid4())
        version = int(row.get("version", 0)) if row else 0
        pending = {**key, "customerId": identity.customer_id, "version": version + 1,
                   "busy": lock, "expiresAt": self.now + CART_LIFETIME}
        if active:
            pending["wixCartId"] = row["wixCartId"]
        try:
            args = {"Item": pending, "ConditionExpression": "attribute_not_exists(orderId)"}
            if row:
                args.update(ConditionExpression="version = :version AND attribute_not_exists(busy)",
                            ExpressionAttributeValues={":version": version})
            self.table.put_item(**args)
        except Exception as error:
            if _conditional(error):
                raise CartBusy("another cart operation won") from error
            raise
        operation = {**op_key, "customerId": identity.customer_id,
                     "fingerprint": fingerprint, "state": "PENDING"}
        if action != "get":
            self.table.put_item(Item=operation, ConditionExpression="attribute_not_exists(orderId)")
        # Any exception after the claim retains the lock. Never replay a remote
        # mutation after a timeout, including create/add and auto-refreshing GET.
        cart_id = pending.get("wixCartId")
        snapshot = None
        if action == "create":
            cart = self.adapter.create(command["items"])
        elif action == "get":
            cart = self.adapter.get(cart_id)
        elif action == "add":
            cart = self.adapter.add(cart_id, command["item"])
        elif action == "quantity":
            cart = self.adapter.set_quantity(cart_id, command["lineItemId"], command["quantity"])
        elif action == "remove":
            cart = self.adapter.remove(cart_id, command["lineItemId"])
        else:
            try:
                snapshot = self.adapter.calculate(cart_id)
            except ValueError:
                # A received calculation with a known validation failure did not
                # place an order. Let the customer fix their cart; discard quotes.
                self.table.update_item(Key=key, UpdateExpression="REMOVE busy",
                                       ConditionExpression="busy = :lock",
                                       ExpressionAttributeValues={":lock": lock})
                self.table.put_item(Item={**operation, "state": "DONE", "failed": True},
                                    ConditionExpression="#state = :pending",
                                    ExpressionAttributeNames={"#state": "state"},
                                    ExpressionAttributeValues={":pending": "PENDING"})
                raise
            snapshot["expiresAt"] = self.now + QUOTE_LIFETIME
            cart = snapshot["cart"]
        # Internal identifiers and verification tokens never leave the backend.
        result = {"items": [{"lineItemId": item["id"],
                              "quantity": (item.get("quantityInfo") or {}).get("confirmedQuantity")}
                             for item in cart.get("lineItems", [])]}
        if snapshot:
            result.update(amountPaise=snapshot["amountPaise"], currency="INR",
                          expiresAt=snapshot["expiresAt"],
                          componentsPaise=snapshot["componentsPaise"])
        finished = {**pending, "wixCartId": cart["id"], "cartRevision": cart["revision"],
                    "lastRequestId": request_id, "fingerprint": fingerprint, "result": result}
        del finished["busy"]
        if snapshot:
            # Wix non-money fields can contain fractional weights/coordinates.
            # boto3 resources require Decimal; monetary amounts remain integers.
            finished["snapshot"] = json.loads(json.dumps(snapshot), parse_float=Decimal)
        self.table.put_item(Item=finished, ConditionExpression="busy = :lock",
                            ExpressionAttributeValues={":lock": lock})
        if action != "get":
            completed = {**operation, "state": "DONE", "result": result}
            if snapshot:
                completed["calculationId"] = snapshot["calculationId"]
            self.table.put_item(Item=completed,
                                ConditionExpression="#state = :pending",
                                ExpressionAttributeNames={"#state": "state"},
                                ExpressionAttributeValues={":pending": "PENDING"})
        return result
