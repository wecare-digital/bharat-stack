"""
WECARE.DIGITAL Shared Lambda Utilities
Provides standardized CORS headers, response formatting,
input validation, and structured logging for all Lambda handlers.
"""
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin, error_response
from lambda_utils.validation import validate_required, validate_phone, validate_email, validate_body, sanitize_html, sanitize_dict, sanitize_string
from lambda_utils.logging import get_logger, log_event
from lambda_utils.middleware import require_auth, health_check
from lambda_utils.rate_limit import check_rate_limit
__all__ = [
    'cors_response',
    'cors_headers',
    'options_response',
    'extract_origin',
    'error_response',
    'require_auth',
    'health_check',
    'check_rate_limit',
    'validate_required',
    'validate_phone',
    'validate_email',
    'validate_body',
    'sanitize_html',
    'sanitize_dict',
    'sanitize_string',
    'get_logger',
    'log_event',
]
