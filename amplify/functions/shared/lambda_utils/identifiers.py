"""UUIDv7 and ULID, implemented here because nothing in the fleet mints either.

Why not a dependency
--------------------
`ulid` appears in `package-lock.json` as a transitive npm dependency and is imported by
nothing; there is no Python ULID or UUIDv7 package in the Lambda layer, and `uuid.uuid7`
does not exist in CPython 3.12. Adding a PyPI dependency to 66 functions to obtain sixty
lines of bit-packing is the wrong trade, especially for identifiers that sit on the payment
path where the supply chain matters.

Both formats are specified, so this is an implementation of a spec rather than an invention:
UUIDv7 is RFC 9562 §5.7, ULID is the canonical ULID spec.

Why time-ordered identifiers at all
-----------------------------------
A payment attempt and an order are both written once and then read back by id, often in
creation order. A random UUIDv4 scatters those writes across the keyspace; a time-prefixed id
keeps them adjacent, which is what makes a range scan over "attempts created today" possible
without a GSI on a timestamp. The cost is that the creation time is *visible* in the id -
deliberate for an internal identifier, and the reason neither of these may ever be used as a
public order number (see `order_keys.mint_public_order_number`, which is unordered on purpose).

Randomness
----------
`secrets`, never `random`. `random` is seeded per execution environment and a SnapStart
snapshot freezes that seed, so every restored sandbox would replay the same sequence. SnapStart
is off across the fleet today, but an identifier that must never collide is the last place to
depend on that staying true.
"""

from __future__ import annotations

import secrets
import time
import uuid

#: Crockford base32, the ULID alphabet. Excludes I, L, O and U so a human reading an id aloud
#: or off a screen cannot produce a second valid id by mistake.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

#: ULID is 26 Crockford symbols: 10 encoding a 48-bit millisecond timestamp, 16 encoding
#: 80 bits of randomness.
_ULID_TIME_SYMBOLS = 10
_ULID_RANDOM_SYMBOLS = 16
ULID_LENGTH = _ULID_TIME_SYMBOLS + _ULID_RANDOM_SYMBOLS

#: 2 ** 48 milliseconds from the epoch, i.e. the year 10889. A timestamp at or past this
#: cannot be encoded in 10 symbols.
_ULID_MAX_TIME_MS = (1 << 48) - 1


def _encode_crockford(value: int, symbols: int) -> str:
    """Big-endian base32 of `value`, left-padded to exactly `symbols` characters."""
    out = []
    for _ in range(symbols):
        value, remainder = divmod(value, 32)
        out.append(_CROCKFORD[remainder])
    if value:
        raise ValueError(f"value does not fit in {symbols} base32 symbols")
    return "".join(reversed(out))


def new_ulid(*, now_ms: int | None = None) -> str:
    """A canonical 26-character ULID.

    Monotonic only to the millisecond. Two ULIDs minted in the same millisecond sort
    arbitrarily relative to each other, which is fine for every use here - nothing depends
    on ordering two identifiers created within the same millisecond, and the 80 random bits
    are what make them distinct.
    """
    timestamp = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if timestamp < 0 or timestamp > _ULID_MAX_TIME_MS:
        raise ValueError("ULID timestamp out of range")
    return (
        _encode_crockford(timestamp, _ULID_TIME_SYMBOLS)
        + _encode_crockford(secrets.randbits(80), _ULID_RANDOM_SYMBOLS)
    )


def new_uuid7(*, now_ms: int | None = None) -> str:
    """A UUIDv7 in canonical hyphenated form, per RFC 9562 section 5.7.

    Layout: 48 bits of Unix time in milliseconds, 4 bits of version (7), 12 bits of random
    (`rand_a`), 2 bits of variant (0b10), 62 bits of random (`rand_b`). 74 random bits in
    total.

    Returned as a string rather than a `uuid.UUID` because every consumer here writes it to
    DynamoDB or JSON, and a `UUID` object serialises only after an explicit `str()` that is
    easy to forget.
    """
    timestamp = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if timestamp < 0 or timestamp > _ULID_MAX_TIME_MS:
        raise ValueError("UUIDv7 timestamp out of range")

    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)

    value = timestamp << 80            # bits 127..80  unix_ts_ms
    value |= 0x7 << 76                 # bits 79..76   version
    value |= rand_a << 64              # bits 75..64   rand_a
    value |= 0b10 << 62                # bits 63..62   variant
    value |= rand_b                    # bits 61..0    rand_b
    return str(uuid.UUID(int=value))


def uuid7_timestamp_ms(value: str) -> int:
    """The millisecond timestamp encoded in a UUIDv7.

    Exists so a test can assert ordering, and so an operator can date an identifier without a
    database lookup. Raises for anything that is not a version-7 UUID rather than returning a
    meaningless number from a v4.
    """
    parsed = uuid.UUID(str(value))
    if parsed.version != 7:
        raise ValueError(f"not a UUIDv7 (version {parsed.version})")
    return parsed.int >> 80


def ulid_timestamp_ms(value: str) -> int:
    """The millisecond timestamp encoded in a ULID."""
    text = str(value).strip().upper()
    if len(text) != ULID_LENGTH:
        raise ValueError(f"ULID must be {ULID_LENGTH} characters, got {len(text)}")
    total = 0
    for symbol in text[:_ULID_TIME_SYMBOLS]:
        index = _CROCKFORD.find(symbol)
        if index < 0:
            raise ValueError("ULID contains a character outside the Crockford alphabet")
        total = total * 32 + index
    return total


def is_ulid(value: object) -> bool:
    """True for a syntactically valid canonical ULID."""
    if not isinstance(value, str) or len(value) != ULID_LENGTH:
        return False
    return all(character in _CROCKFORD for character in value)


def is_uuid7(value: object) -> bool:
    """True for a canonical UUID string whose version field is 7."""
    if not isinstance(value, str):
        return False
    try:
        return uuid.UUID(value).version == 7
    except (ValueError, AttributeError, TypeError):
        return False


__all__ = [
    "ULID_LENGTH",
    "new_ulid",
    "new_uuid7",
    "ulid_timestamp_ms",
    "uuid7_timestamp_ms",
    "is_ulid",
    "is_uuid7",
]
