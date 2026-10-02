"""KMS envelope custody for Wix gift-card bearer codes.

The code is needed twice: once when Cart V2 applies it, and once after Razorpay capture when
Wix Order Billing redeems it against the externally-created order. It must never be logged or
stored in plaintext. Cart custody is rebound to the payment attempt before a gateway order exists.
"""
from __future__ import annotations

import base64
import os
import re
from typing import Optional

import boto3

DEFAULT_KEY_ID = "alias/wecare-checkout-tender"
KEY_ENV = "CHECKOUT_TENDER_KMS_KEY"


class GiftCardCodeUnavailable(RuntimeError):
    pass


def _client(kms=None):
    return kms or boto3.client("kms", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _code(value: str) -> str:
    code = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{8,20}", code):
        raise ValueError("gift card code must be 8-20 letters, digits or hyphens")
    return code


def _seal(code: str, context: dict, *, kms=None, key_id: Optional[str] = None) -> str:
    key = key_id or os.environ.get(KEY_ENV) or DEFAULT_KEY_ID
    try:
        blob = _client(kms).encrypt(
            KeyId=key, Plaintext=_code(code).encode("utf-8"), EncryptionContext=context
        )["CiphertextBlob"]
    except Exception as error:  # noqa: BLE001
        raise GiftCardCodeUnavailable(
            f"gift-card code encryption failed: {type(error).__name__}") from error
    return base64.b64encode(blob).decode("ascii")


def _open(value: str, context: dict, *, kms=None) -> str:
    try:
        blob = base64.b64decode(str(value or ""), validate=True)
        plain = _client(kms).decrypt(
            CiphertextBlob=blob, EncryptionContext=context
        )["Plaintext"].decode("utf-8")
    except Exception as error:  # noqa: BLE001
        raise GiftCardCodeUnavailable(
            f"gift-card code decryption failed: {type(error).__name__}") from error
    return _code(plain)


def seal_for_cart(code: str, *, customer_id: str, cart_id: str, kms=None,
                  key_id: Optional[str] = None) -> str:
    if not customer_id or not cart_id:
        raise ValueError("customer_id and cart_id are required")
    return _seal(code, {"purpose": "checkout-gift-card-cart",
                        "customerId": customer_id, "cartId": cart_id},
                 kms=kms, key_id=key_id)


def open_for_cart(value: str, *, customer_id: str, cart_id: str, kms=None) -> str:
    return _open(value, {"purpose": "checkout-gift-card-cart",
                         "customerId": customer_id, "cartId": cart_id}, kms=kms)


def seal_for_attempt(code: str, *, customer_id: str, payment_attempt_id: str, kms=None,
                     key_id: Optional[str] = None) -> str:
    if not customer_id or not payment_attempt_id:
        raise ValueError("customer_id and payment_attempt_id are required")
    return _seal(code, {"purpose": "checkout-gift-card-attempt",
                        "customerId": customer_id, "paymentAttemptId": payment_attempt_id},
                 kms=kms, key_id=key_id)


def open_for_attempt(value: str, *, customer_id: str, payment_attempt_id: str, kms=None) -> str:
    return _open(value, {"purpose": "checkout-gift-card-attempt",
                         "customerId": customer_id, "paymentAttemptId": payment_attempt_id}, kms=kms)


__all__ = [
    "DEFAULT_KEY_ID", "KEY_ENV", "GiftCardCodeUnavailable",
    "seal_for_cart", "open_for_cart", "seal_for_attempt", "open_for_attempt",
]
