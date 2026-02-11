"""
Normalized internal event model — canonical schema for all WhatsApp events.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class NormalizedEvent:
    eventType: str  # INBOUND_MESSAGE, STATUS_UPDATE, PAYMENT_STATUS, TEMPLATE_STATUS, PHONE_QUALITY, ACCOUNT_UPDATE
    eventId: str
    whatsappMessageId: str = ''
    messageType: str = ''
    content: str = ''
    senderPhone: str = ''
    senderName: str = ''
    receivingPhone: str = ''
    awsPhoneNumberId: str = ''
    wabaId: str = ''
    mediaId: str = ''
    mimeType: str = ''
    s3Key: str = ''
    fileSize: int = 0
    interactiveType: str = ''
    interactiveData: Dict[str, Any] = field(default_factory=dict)
    latitude: float = 0.0
    longitude: float = 0.0
    locationName: str = ''
    reactionMessageId: str = ''
    reactionEmoji: str = ''
    status: str = ''
    recipientPhone: str = ''
    errorCode: str = ''
    paymentStatus: str = ''
    referenceId: str = ''
    amount: str = ''
    currency: str = ''
    templateName: str = ''
    newStatus: str = ''
    timestamp: int = 0
    rawPayload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v and v != 0 and v != 0.0}
