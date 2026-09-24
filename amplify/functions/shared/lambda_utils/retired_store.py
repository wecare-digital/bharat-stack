"""Handling for a data store that was retired and then deleted.

The problem this solves
-----------------------
Retiring a provider happens in two steps that can be months apart: the sender is
switched off, then the table holding its history is deleted. Between those steps
the read paths are correct. After the second step they are not, and nothing says
so - DynamoDB raises `ResourceNotFoundException`, the handler's outer
`except Exception` turns it into a 500, and the operator is told the system is
broken when the truthful answer is "that data was deliberately deleted".

Measured on 2026-09-24, which is what prompted this module:

    stack-wecare-digital-AirtelC2CTable   named by 5 sites in voice-in/c2c,
                                          which took 39 invocations in 30 days
    stack-wecare-digital-AirtelSMSTable   the only table lambda_utils/comms/
                                          legacy_history.py reads

Neither exists. Both were deleted on 2026-09-20 with the Airtel retirement - and
`voice-in/c2c/handler.py` still carried a comment asserting the opposite ("it
holds real historical records that must stay readable"), so reading the code made
the fault invisible too.

A 500 and a 410 are different claims
------------------------------------
`500` says "we failed, try again" - the remedy is to retry or escalate. `410
Gone` says "this existed and was intentionally removed" - the remedy is to stop
asking. Returning the first for the second is how a closed decision gets
reopened as an incident.

This module does not recreate the store and does not pretend the data is
available. It makes the absence explicit, typed and testable.
"""
from __future__ import annotations

from typing import Any, Dict

#: Stable code so a UI can branch without string-matching a message.
ABSENT_ERROR_CODE = "RETIRED_STORE_ABSENT"

#: The right HTTP status for a resource that existed and was deliberately removed.
ABSENT_HTTP_STATUS = 410


def is_absent(exc: BaseException) -> bool:
    """True when `exc` is DynamoDB reporting that the table does not exist.

    Matches on the error code rather than the exception class, because botocore
    synthesises `ResourceNotFoundException` per-client at runtime - there is no
    importable class to catch, and catching `ClientError` broadly would also
    swallow throttling and access-denied, which are real faults that must keep
    surfacing as faults.
    """
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str(response.get("Error", {}).get("Code") or "")
        if code == "ResourceNotFoundException":
            return True
    # Some call paths re-raise with the code only in the message.
    return exc.__class__.__name__ == "ResourceNotFoundException"


def absent_payload(table_name: str, *, what: str, retired: str = "") -> Dict[str, Any]:
    """A body that says the store is gone, and says it the same way every time.

    `what` names the data in human terms ("retired-provider SMS history"), and
    `retired` optionally carries when and why. Neither is a secret and both are
    safe to render.
    """
    note = (
        f"{what} is no longer available: the store was deleted as part of a "
        "provider retirement. This is the intended end state, not an outage - "
        "retrying will not recover it."
    )
    if retired:
        note = f"{note} {retired}"
    return {
        "storeAbsent": True,
        "errorCode": ABSENT_ERROR_CODE,
        "sourceTable": table_name,
        "readOnly": True,
        "note": note,
    }
