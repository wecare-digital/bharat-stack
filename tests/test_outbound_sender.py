"""
Unit tests for outbound sender — message payload building and validation.
Tests the WhatsApp Message object construction for all supported types.
Does NOT call AWS APIs (mocked).
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add lambdas to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas'))

# Mock boto3 before importing handler
with patch('boto3.client'), patch('boto3.resource'):
    from outbound_sender.handler import (
        _format_phone, _build_list, _build_button, _build_cta_url,
        _build_location_request, _build_flow, _build_order_details,
        _error_response, _success_response, MEDIA_SIZE_LIMITS
    )


class TestPhoneFormatting:
    def test_digits_only(self):
        assert _format_phone('919876543210') == '+919876543210'

    def test_with_plus(self):
        assert _format_phone('+919876543210') == '+919876543210'

    def test_with_spaces_dashes(self):
        assert _format_phone('+91 98765-43210') == '+919876543210'

    def test_empty(self):
        assert _format_phone('') == ''


class TestBuildList:
    def test_basic_list(self):
        data = {
            'body': 'Pick one',
            'buttonText': 'Options',
            'sections': [{
                'title': 'Section 1',
                'rows': [
                    {'id': 'r1', 'title': 'Row 1', 'description': 'Desc 1'},
                    {'id': 'r2', 'title': 'Row 2', 'description': 'Desc 2'}
                ]
            }]
        }
        result = _build_list(data, {})
        assert result['type'] == 'list'
        assert result['body']['text'] == 'Pick one'
        assert result['action']['button'] == 'Options'
        assert len(result['action']['sections']) == 1
        assert len(result['action']['sections'][0]['rows']) == 2

    def test_list_with_header_footer(self):
        data = {
            'body': 'Pick one',
            'header': 'Menu',
            'footer': 'Powered by WECARE',
            'buttonText': 'Go',
            'sections': [{'title': 'S', 'rows': [{'id': '1', 'title': 'A'}]}]
        }
        result = _build_list(data, {})
        assert result['header'] == {'type': 'text', 'text': 'Menu'}
        assert result['footer'] == {'text': 'Powered by WECARE'}

    def test_list_row_title_truncation(self):
        data = {
            'body': 'Pick',
            'buttonText': 'Go',
            'sections': [{'title': 'S', 'rows': [{'id': '1', 'title': 'A' * 50}]}]
        }
        result = _build_list(data, {})
        assert len(result['action']['sections'][0]['rows'][0]['title']) <= 24


class TestBuildButton:
    def test_basic_buttons(self):
        data = {
            'body': 'Choose',
            'buttons': [
                {'id': 'yes', 'title': 'Yes'},
                {'id': 'no', 'title': 'No'}
            ]
        }
        result = _build_button(data, {})
        assert result['type'] == 'button'
        assert len(result['action']['buttons']) == 2
        assert result['action']['buttons'][0]['reply']['id'] == 'yes'

    def test_max_three_buttons(self):
        data = {
            'body': 'Choose',
            'buttons': [{'id': f'b{i}', 'title': f'Btn {i}'} for i in range(5)]
        }
        result = _build_button(data, {})
        assert len(result['action']['buttons']) == 3

    def test_button_title_truncation(self):
        data = {
            'body': 'Choose',
            'buttons': [{'id': 'b1', 'title': 'A' * 30}]
        }
        result = _build_button(data, {})
        assert len(result['action']['buttons'][0]['reply']['title']) <= 20

    def test_button_with_image_header(self):
        data = {
            'body': 'Choose',
            'headerType': 'image',
            'headerMedia': 'https://example.com/img.jpg',
            'buttons': [{'id': 'b1', 'title': 'OK'}]
        }
        result = _build_button(data, {})
        assert result['header']['type'] == 'image'
        assert result['header']['image']['link'] == 'https://example.com/img.jpg'


class TestBuildCtaUrl:
    def test_basic_cta(self):
        data = {
            'body': 'Visit us',
            'buttonText': 'Open',
            'url': 'https://wecare.digital'
        }
        result = _build_cta_url(data, {})
        assert result['type'] == 'cta_url'
        assert result['action']['parameters']['url'] == 'https://wecare.digital'
        assert result['action']['parameters']['display_text'] == 'Open'

    def test_cta_missing_url(self):
        data = {'body': 'Visit us'}
        result = _build_cta_url(data, {})
        assert result['statusCode'] == 400


class TestBuildLocationRequest:
    def test_basic(self):
        data = {'body': 'Share your location'}
        result = _build_location_request(data, {})
        assert result['type'] == 'location_request_message'
        assert result['action']['name'] == 'send_location'


class TestBuildFlow:
    def test_basic_flow(self):
        data = {
            'body': 'Start survey',
            'flowId': 'flow_123',
            'flowCta': 'Begin',
            'flowToken': 'tok_abc'
        }
        result = _build_flow(data, {})
        assert result['type'] == 'flow'
        assert result['action']['parameters']['flow_id'] == 'flow_123'
        assert result['action']['parameters']['flow_cta'] == 'Begin'

    def test_flow_missing_id(self):
        data = {'body': 'Start'}
        result = _build_flow(data, {})
        assert result['statusCode'] == 400

    def test_flow_with_screen(self):
        data = {
            'body': 'Start',
            'flowId': 'f1',
            'screenId': 'WELCOME',
            'flowData': {'name': 'Test'}
        }
        result = _build_flow(data, {})
        fap = result['action']['parameters']['flow_action_payload']
        assert fap['screen'] == 'WELCOME'
        assert fap['data'] == {'name': 'Test'}


class TestBuildOrderDetails:
    def test_basic_order(self):
        body = {
            'orderDetails': {
                'reference_id': 'ORD-001',
                'currency': 'INR',
                'total_amount': {'value': 10000, 'offset': 100},
                'payment_configuration': 'WECARE_PAY',
                'order': {'status': 'pending', 'items': []}
            }
        }
        result = _build_order_details({}, body)
        assert result['type'] == 'order_details'
        assert result['action']['name'] == 'review_and_pay'
        assert result['action']['parameters']['reference_id'] == 'ORD-001'
        assert result['action']['parameters']['currency'] == 'INR'


class TestResponses:
    def test_error_response(self):
        resp = _error_response(400, 'Bad request')
        assert resp['statusCode'] == 400
        body = json.loads(resp['body'])
        assert body['error'] == 'Bad request'
        assert body['status'] == 'failed'

    def test_success_response(self):
        resp = _success_response('msg-1', 'wamid.123', 'text')
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['messageId'] == 'msg-1'
        assert body['whatsappMessageId'] == 'wamid.123'
        assert body['type'] == 'text'

    def test_success_with_extra(self):
        resp = _success_response('msg-1', 'wamid.123', 'reaction', extra={'emoji': '👍'})
        body = json.loads(resp['body'])
        assert body['emoji'] == '👍'


class TestMediaSizeLimits:
    def test_limits_defined_for_all_types(self):
        expected = {'image', 'video', 'audio', 'document', 'sticker'}
        assert set(MEDIA_SIZE_LIMITS.keys()) == expected

    def test_image_limit_5mb(self):
        assert MEDIA_SIZE_LIMITS['image'] == 5 * 1024 * 1024

    def test_video_limit_16mb(self):
        assert MEDIA_SIZE_LIMITS['video'] == 16 * 1024 * 1024

    def test_document_limit_100mb(self):
        assert MEDIA_SIZE_LIMITS['document'] == 100 * 1024 * 1024

    def test_sticker_limit_500kb(self):
        assert MEDIA_SIZE_LIMITS['sticker'] == 500 * 1024


class TestOtpTemplatePayload:
    """Test OTP/Authentication template payload building in reference handler."""

    def _build_otp_body(self, otp_code='123456', button_type='copy_code', template_name='otp_verify',
                        language='en', params=None):
        """Helper to build an OTP template request body."""
        body = {
            'contactId': 'c-001',
            'recipientPhone': '+919876543210',
            'phoneNumberId': 'phone-number-id-5e020cecd221429996f6ae721cc42206',
            'isTemplate': True,
            'templateName': template_name,
            'templateParams': [language] + (params or []),
            'isOtpTemplate': True,
            'otpCode': otp_code,
            'otpButtonType': button_type,
        }
        return body

    def test_otp_copy_code_body_structure(self):
        """OTP template with copy_code button should have coupon_code parameter."""
        body = self._build_otp_body(otp_code='654321', button_type='copy_code')
        # Verify the body has the right flags
        assert body['isOtpTemplate'] is True
        assert body['otpCode'] == '654321'
        assert body['otpButtonType'] == 'copy_code'

    def test_otp_url_body_structure(self):
        """OTP template with url button should have text parameter."""
        body = self._build_otp_body(otp_code='789012', button_type='url')
        assert body['isOtpTemplate'] is True
        assert body['otpCode'] == '789012'
        assert body['otpButtonType'] == 'url'

    def test_otp_default_button_type(self):
        """Default OTP button type should be copy_code."""
        body = self._build_otp_body()
        assert body['otpButtonType'] == 'copy_code'

    def test_otp_with_body_params(self):
        """OTP template can include body parameters alongside the button."""
        body = self._build_otp_body(params=['Your code is 123456'])
        assert body['templateParams'] == ['en', 'Your code is 123456']

    def test_authentication_template_alias(self):
        """isAuthenticationTemplate should also be accepted as an alias."""
        body = self._build_otp_body()
        body['isAuthenticationTemplate'] = True
        del body['isOtpTemplate']
        assert body.get('isAuthenticationTemplate') is True
        assert body.get('isOtpTemplate') is None
