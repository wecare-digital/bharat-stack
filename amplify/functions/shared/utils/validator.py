"""
Message Validator Module

Provides validation for message delivery across all channels.
Implements opt-in validation, allowlist verification, and
24-hour customer service window tracking.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 16.2, 16.3
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum


class ValidationErrorCode(Enum):
    """Validation error codes for message delivery."""
    OPT_IN_REQUIRED = "OPT_IN_REQUIRED"
    ALLOWLIST_VIOLATION = "ALLOWLIST_VIOLATION"
    TEMPLATE_REQUIRED = "TEMPLATE_REQUIRED"
    INVALID_CONTACT = "INVALID_CONTACT"
    MISSING_PHONE = "MISSING_PHONE"
    MISSING_EMAIL = "MISSING_EMAIL"


@dataclass
class ValidationResult:
    """Result of message validation."""
    success: bool
    error_code: Optional[ValidationErrorCode] = None
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @staticmethod
    def ok() -> 'ValidationResult':
        """Create a successful validation result."""
        return ValidationResult(success=True)

    @staticmethod
    def fail(code: ValidationErrorCode, message: str, details: Dict[str, Any] = None) -> 'ValidationResult':
        """Create a failed validation result."""
        return ValidationResult(
            success=False,
            error_code=code,
            error_message=message,
            details=details or {}
        )


class MessageValidator:
    """
    Validates messages before delivery across all channels.
    
    Implements fail-closed validation - any validation failure
    results in message rejection with no fallback delivery.
    
    Requirements:
    - 3.1: WhatsApp opt-in validation
    - 3.2: WhatsApp allowlist validation
    - 3.3: SMS opt-in validation
    - 3.4: Email opt-in validation
    - 3.5: Fail-closed on validation failure
    - 16.2, 16.3: 24-hour customer service window
    """

    # WhatsApp Phone Number Allowlist
    WHATSAPP_ALLOWLIST: List[str] = [
        'phone-number-id-2ff05755631b41f29151c0573b7a4e2a',
        'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6',
    ]

    # Customer service window duration
    SERVICE_WINDOW_HOURS: int = 24

    def __init__(self, allowlist: List[str] = None):
        """
        Initialize MessageValidator.
        
        Args:
            allowlist: Optional custom allowlist (defaults to WHATSAPP_ALLOWLIST)
        """
        self.allowlist = allowlist or self.WHATSAPP_ALLOWLIST

    def validate_whatsapp(
        self,
        contact: Dict[str, Any],
        phone_number_id: str,
        is_template: bool = False
    ) -> ValidationResult:
        """
        Validate WhatsApp message delivery.
        
        Requirement 3.1: Verify optInWhatsApp is True
        Requirement 3.2: Verify phone_number_id is in allowlist
        Requirement 16.3-16.6: Check customer service window for non-template messages
        
        Args:
            contact: Contact record with opt-in preferences
            phone_number_id: WhatsApp phone number ID to send from
            is_template: Whether this is a template message
            
        Returns:
            ValidationResult with success/failure and error details
        """
        if not contact:
            return ValidationResult.fail(
                ValidationErrorCode.INVALID_CONTACT,
                "Contact not found"
            )

        # Requirement 3.1: Check opt-in
        if not contact.get('optInWhatsApp', False):
            return ValidationResult.fail(
                ValidationErrorCode.OPT_IN_REQUIRED,
                "WhatsApp opt-in required",
                {'contactId': contact.get('contactId'), 'channel': 'WHATSAPP'}
            )

        # Requirement 3.2: Check allowlist
        if phone_number_id not in self.allowlist:
            return ValidationResult.fail(
                ValidationErrorCode.ALLOWLIST_VIOLATION,
                f"Phone number ID not in allowlist: {phone_number_id}",
                {'phoneNumberId': phone_number_id, 'allowlist': self.allowlist}
            )

        # Requirement 16.3-16.6: Check customer service window for non-template messages
        if not is_template:
            window_result = self.check_customer_service_window(contact)
            if not window_result.success:
                return window_result

        return ValidationResult.ok()

    def validate_sms(self, contact: Dict[str, Any]) -> ValidationResult:
        """
        Validate SMS message delivery.
        
        Requirement 3.3: Verify optInSms is True
        
        Args:
            contact: Contact record with opt-in preferences
            
        Returns:
            ValidationResult with success/failure and error details
        """
        if not contact:
            return ValidationResult.fail(
                ValidationErrorCode.INVALID_CONTACT,
                "Contact not found"
            )

        # Check phone number exists
        if not contact.get('phone'):
            return ValidationResult.fail(
                ValidationErrorCode.MISSING_PHONE,
                "Contact has no phone number",
                {'contactId': contact.get('contactId')}
            )

        # Requirement 3.3: Check opt-in
        if not contact.get('optInSms', False):
            return ValidationResult.fail(
                ValidationErrorCode.OPT_IN_REQUIRED,
                "SMS opt-in required",
                {'contactId': contact.get('contactId'), 'channel': 'SMS'}
            )

        return ValidationResult.ok()

    def validate_email(self, contact: Dict[str, Any]) -> ValidationResult:
        """
        Validate email message delivery.
        
        Requirement 3.4: Verify optInEmail is True
        
        Args:
            contact: Contact record with opt-in preferences
            
        Returns:
            ValidationResult with success/failure and error details
        """
        if not contact:
            return ValidationResult.fail(
                ValidationErrorCode.INVALID_CONTACT,
                "Contact not found"
            )

        # Check email exists
        if not contact.get('email'):
            return ValidationResult.fail(
                ValidationErrorCode.MISSING_EMAIL,
                "Contact has no email address",
                {'contactId': contact.get('contactId')}
            )

        # Requirement 3.4: Check opt-in
        if not contact.get('optInEmail', False):
            return ValidationResult.fail(
                ValidationErrorCode.OPT_IN_REQUIRED,
                "Email opt-in required",
                {'contactId': contact.get('contactId'), 'channel': 'EMAIL'}
            )

        return ValidationResult.ok()

    def check_customer_service_window(self, contact: Dict[str, Any]) -> ValidationResult:
        """
        Check if contact is within 24-hour customer service window.
        
        Requirement 16.2: Calculate window as 24 hours from lastInboundMessageAt
        Requirement 16.3: Check if current time is within window
        Requirement 16.5: Require template outside window
        Requirement 16.6: Reject free-form messages outside window
        
        Args:
            contact: Contact record with lastInboundMessageAt timestamp
            
        Returns:
            ValidationResult - success if within window, failure if outside
        """
        last_inbound = contact.get('lastInboundMessageAt')
        
        if not last_inbound:
            # No inbound message ever received - template required
            return ValidationResult.fail(
                ValidationErrorCode.TEMPLATE_REQUIRED,
                "No customer service window - template message required",
                {
                    'contactId': contact.get('contactId'),
                    'lastInboundMessageAt': None,
                    'windowExpired': True
                }
            )

        # Parse timestamp
        try:
            if isinstance(last_inbound, str):
                # Handle ISO format string
                last_inbound_dt = datetime.fromisoformat(last_inbound.replace('Z', '+00:00'))
            else:
                last_inbound_dt = last_inbound
        except (ValueError, TypeError):
            return ValidationResult.fail(
                ValidationErrorCode.TEMPLATE_REQUIRED,
                "Invalid lastInboundMessageAt timestamp - template message required",
                {'contactId': contact.get('contactId'), 'lastInboundMessageAt': str(last_inbound)}
            )

        # Requirement 16.2: Calculate window expiration
        window_end = last_inbound_dt + timedelta(hours=self.SERVICE_WINDOW_HOURS)
        now = datetime.utcnow()
        
        # Make timezone-naive for comparison if needed
        if window_end.tzinfo is not None:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)

        # Requirement 16.3: Check if within window
        if now > window_end:
            return ValidationResult.fail(
                ValidationErrorCode.TEMPLATE_REQUIRED,
                "Outside 24-hour customer service window - template message required",
                {
                    'contactId': contact.get('contactId'),
                    'lastInboundMessageAt': str(last_inbound),
                    'windowExpiredAt': window_end.isoformat(),
                    'currentTime': now.isoformat()
                }
            )

        return ValidationResult.ok()

    def is_within_service_window(self, contact: Dict[str, Any]) -> bool:
        """
        Simple boolean check for customer service window.
        
        Args:
            contact: Contact record
            
        Returns:
            True if within 24-hour window, False otherwise
        """
        return self.check_customer_service_window(contact).success

    def get_window_expiration(self, contact: Dict[str, Any]) -> Optional[datetime]:
        """
        Get the customer service window expiration time.
        
        Args:
            contact: Contact record
            
        Returns:
            Window expiration datetime or None if no window
        """
        last_inbound = contact.get('lastInboundMessageAt')
        if not last_inbound:
            return None
            
        try:
            if isinstance(last_inbound, str):
                last_inbound_dt = datetime.fromisoformat(last_inbound.replace('Z', '+00:00'))
            else:
                last_inbound_dt = last_inbound
            return last_inbound_dt + timedelta(hours=self.SERVICE_WINDOW_HOURS)
        except (ValueError, TypeError):
            return None
