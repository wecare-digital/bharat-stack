"""Validation utilities for phone numbers and required fields."""
import re

E164_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
PHONE_NUMBER_ID_PATTERN = re.compile(r'^phone-number-id-[0-9a-f]{32}$')
WABA_ID_PATTERN = re.compile(r'^waba-[0-9a-f]{32}$')
MAX_TEXT_LENGTH = 4096


def validate_e164(phone: str) -> bool:
    return bool(E164_PATTERN.match(phone.replace(' ', '').replace('-', '')))


def normalize_phone(phone: str) -> str:
    return re.sub(r'[^\d]', '', phone)


def validate_phone_number_id(phone_id: str) -> bool:
    return bool(PHONE_NUMBER_ID_PATTERN.match(phone_id))


def validate_waba_id(waba_id: str) -> bool:
    return bool(WABA_ID_PATTERN.match(waba_id))


def validate_text_content(content: str) -> tuple:
    if not content:
        return True, None
    if len(content) > MAX_TEXT_LENGTH:
        return False, f'Content exceeds {MAX_TEXT_LENGTH} characters'
    return True, None
