"""Tests for the WABA Management Lambda handler (Part 3 / Module 1).

Verifies the migration onto the shared MetaGraphClient: normalized error
envelopes, per-WABA token context, and audit logging on writes.
"""
import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'waba-management'))


def _import_handler():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'waba-management'))
    with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
        with patch('boto3.resource'), patch('boto3.client'):
            import handler
            return handler


def _meta_error(message='boom', http_status=400, code=100):
    """A normalized error envelope shaped like MetaGraphClient.normalize_error."""
    return {'error': {'message': message, 'type': 'GraphAPIError', 'code': code,
                      'http_status': http_status, 'retryable': False, 'is_transient': False}}


class TestListWabas:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_lists_successful_wabas(self):
        with patch.object(self.h._meta, 'get', return_value={'id': '2094615664435155', 'name': 'WECARE'}):
            result = self.h._list_wabas('req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['count'] == len(self.h.AWS_TO_META_WABA)
        assert body['wabas'][0]['wabaName'] == 'WECARE'

    def test_skips_wabas_that_error(self):
        with patch.object(self.h._meta, 'get', return_value=_meta_error()):
            result = self.h._list_wabas('req-2')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['count'] == 0

    def test_uses_waba_token_context(self):
        with patch.object(self.h._meta, 'get', return_value={'id': 'x'}) as mock_get:
            self.h._list_wabas('req-3')
        # Every call should carry a waba_id token context
        for call in mock_get.call_args_list:
            assert 'token_context' in call.kwargs
            assert 'waba_id' in call.kwargs['token_context']


class TestGetWabaDetails:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_success_includes_phone_numbers(self):
        account = {'id': '2094615664435155', 'name': 'WECARE', 'currency': 'INR'}
        phones = {'data': [{'id': '1016149501586345', 'display_phone_number': '+91 93309 94400',
                            'quality_rating': 'GREEN'}]}
        with patch.object(self.h._meta, 'get', side_effect=[account, phones]):
            result = self.h._get_waba_details('2094615664435155', 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['wabaName'] == 'WECARE'
        assert len(body['phoneNumbers']) == 1
        assert body['phoneNumbers'][0]['qualityRating'] == 'GREEN'

    def test_account_error_propagates_status(self):
        with patch.object(self.h._meta, 'get', return_value=_meta_error(http_status=404)):
            result = self.h._get_waba_details('2094615664435155', 'req-2')
        assert result['statusCode'] == 404
        assert 'error' in json.loads(result['body'])

    def test_phone_error_propagates(self):
        account = {'id': '2094615664435155', 'name': 'WECARE'}
        with patch.object(self.h._meta, 'get', side_effect=[account, _meta_error(http_status=500)]):
            result = self.h._get_waba_details('2094615664435155', 'req-3')
        assert result['statusCode'] == 500


class TestPhoneDetails:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_success(self):
        with patch.object(self.h._meta, 'get', return_value={'id': '1016149501586345',
                                                             'display_phone_number': '+91 93309 94400',
                                                             'quality_rating': 'GREEN'}):
            result = self.h._get_phone_number_details('1016149501586345', 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['qualityRating'] == 'GREEN'

    def test_error(self):
        with patch.object(self.h._meta, 'get', return_value=_meta_error(http_status=404)):
            result = self.h._get_phone_number_details('1016149501586345', 'req-2')
        assert result['statusCode'] == 404


class TestMedia:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_delete_requires_media_id(self):
        assert self.h._delete_media('', 'phone-1', 'req-1')['statusCode'] == 400

    def test_delete_requires_phone(self):
        assert self.h._delete_media('media-1', '', 'req-1')['statusCode'] == 400

    def test_delete_success_audits(self):
        with patch.object(self.h._meta, 'delete', return_value={'success': True}), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._delete_media('media-1', '1016149501586345', 'req-1')
        assert result['statusCode'] == 200
        assert json.loads(result['body'])['success'] is True
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs['action'] == 'media.delete'

    def test_delete_error(self):
        with patch.object(self.h._meta, 'delete', return_value=_meta_error(http_status=404)):
            result = self.h._delete_media('media-1', '1016149501586345', 'req-1')
        assert result['statusCode'] == 404

    def test_get_media_metadata_only(self):
        with patch.object(self.h._meta, 'get', return_value={'mime_type': 'image/png', 'file_size': 10}):
            result = self.h._get_media('media-1', '1016149501586345', {'metadataOnly': 'true'}, 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['mimeType'] == 'image/png'
        assert 's3Key' not in body

    def test_get_media_downloads_binary_to_s3(self):
        with patch.object(self.h._meta, 'get', return_value={'mime_type': 'image/png', 'url': 'https://lookaside/x'}), \
             patch.object(self.h._meta, 'download_file', return_value=b'bytes'), \
             patch.object(self.h.s3, 'put_object'), \
             patch.object(self.h.s3, 'generate_presigned_url', return_value='https://signed'):
            result = self.h._get_media('media-1', '1016149501586345', {}, 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['s3Key'].endswith('media-1')
        assert body['downloadUrl'] == 'https://signed'

    def test_post_media_requires_fields(self):
        assert self.h._post_media({'phoneNumberId': 'p'}, 'req-1')['statusCode'] == 400
        assert self.h._post_media({'s3Key': 'k'}, 'req-1')['statusCode'] == 400

    def test_post_media_success_audits(self):
        s3_obj = {'Body': MagicMock(read=MagicMock(return_value=b'data')), 'ContentType': 'image/png'}
        with patch.object(self.h.s3, 'get_object', return_value=s3_obj), \
             patch.object(self.h._meta, 'upload_multipart', return_value={'id': 'media-99'}), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._post_media({'phoneNumberId': '1016149501586345', 's3Key': 'k/file.png'}, 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['mediaId'] == 'media-99'
        assert mock_audit.call_args.kwargs['action'] == 'media.upload'


class TestEventDestinations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_requires_waba(self):
        assert self.h._put_event_destinations('', {}, 'req-1')['statusCode'] == 400

    def test_subscribe_path_audits(self):
        with patch.object(self.h._meta, 'post', return_value={'success': True}) as mock_post, \
             patch.object(self.h._meta, 'delete') as mock_delete, \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._put_event_destinations(
                '2094615664435155', {'eventDestinations': [{'eventDestinationArn': 'arn'}]}, 'req-1')
        assert result['statusCode'] == 200
        mock_post.assert_called_once()
        mock_delete.assert_not_called()
        assert mock_audit.call_args.kwargs['action'] == 'event_destination.update'

    def test_empty_destinations_unsubscribes(self):
        with patch.object(self.h._meta, 'delete', return_value={'success': True}) as mock_delete, \
             patch.object(self.h, 'record_audit'):
            result = self.h._put_event_destinations('2094615664435155', {'eventDestinations': []}, 'req-1')
        assert result['statusCode'] == 200
        mock_delete.assert_called_once()

    def test_meta_error_propagates(self):
        with patch.object(self.h._meta, 'post', return_value=_meta_error(http_status=403)):
            result = self.h._put_event_destinations(
                '2094615664435155', {'eventDestinations': [{'x': 1}]}, 'req-1')
        assert result['statusCode'] == 403


class TestSnsSubscription:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_subscribe_requires_waba(self):
        assert self.h._subscribe_waba_to_sns('', {}, 'req-1')['statusCode'] == 400

    def test_subscribe_success_audits(self):
        table = MagicMock()
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h.dynamodb, 'Table', return_value=table), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._subscribe_waba_to_sns('2094615664435155', {}, 'req-1')
        assert result['statusCode'] == 200
        table.put_item.assert_called_once()
        assert mock_audit.call_args.kwargs['action'] == 'webhook.subscribe'

    def test_subscribe_meta_error_no_db_write(self):
        table = MagicMock()
        with patch.object(self.h._meta, 'post', return_value=_meta_error(http_status=400)), \
             patch.object(self.h.dynamodb, 'Table', return_value=table):
            result = self.h._subscribe_waba_to_sns('2094615664435155', {}, 'req-1')
        assert result['statusCode'] == 400
        table.put_item.assert_not_called()

    def test_unsubscribe_success_audits(self):
        table = MagicMock()
        with patch.object(self.h._meta, 'delete', return_value={'success': True}), \
             patch.object(self.h.dynamodb, 'Table', return_value=table), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._unsubscribe_waba_from_sns('2094615664435155', {}, 'req-1')
        assert result['statusCode'] == 200
        assert mock_audit.call_args.kwargs['action'] == 'webhook.unsubscribe'

    def test_status_handles_meta_error_gracefully(self):
        table = MagicMock()
        table.get_item.return_value = {}
        with patch.object(self.h.dynamodb, 'Table', return_value=table), \
             patch.object(self.h._meta, 'get', return_value=_meta_error(http_status=500)):
            result = self.h._get_sns_subscription_status('2094615664435155', 'req-1')
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['isSubscribed'] is False


class TestPhoneRegistrationMigration:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_request_otp_requires_phone(self):
        assert self.h._request_otp({}, 'req-1')['statusCode'] == 400

    def test_request_otp_success_audits(self):
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._request_otp({'phoneNumberId': '1016149501586345'}, 'req-1')
        assert result['statusCode'] == 200
        assert mock_audit.call_args.kwargs['action'] == 'phone.request_otp'

    def test_verify_otp_requires_code(self):
        assert self.h._verify_otp({'phoneNumberId': 'p'}, 'req-1')['statusCode'] == 400

    def test_verify_otp_success(self):
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h, 'record_audit'):
            result = self.h._verify_otp({'phoneNumberId': '1016149501586345', 'code': '123456'}, 'req-1')
        assert json.loads(result['body'])['verified'] is True

    def test_register_phone_success_audits(self):
        table = MagicMock()
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h.dynamodb, 'Table', return_value=table), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._register_phone({'phoneNumberId': '1016149501586345', 'pin': '000000'}, 'req-1')
        assert result['statusCode'] == 200
        assert mock_audit.call_args.kwargs['action'] == 'phone.register'

    def test_migrate_requires_target(self):
        assert self.h._migrate_phone({'phoneNumberId': 'p'}, 'req-1')['statusCode'] == 400

    def test_migrate_success_audits(self):
        table = MagicMock()
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h.dynamodb, 'Table', return_value=table), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._migrate_phone(
                {'phoneNumberId': '1055232054343117', 'targetWabaId': '2094615664435155'}, 'req-1')
        assert result['statusCode'] == 200
        assert mock_audit.call_args.kwargs['action'] == 'phone.migrate'

    def test_migrate_pin_send_error_propagates(self):
        with patch.object(self.h._meta, 'post', return_value=_meta_error(http_status=400)):
            result = self.h._migrate_phone(
                {'phoneNumberId': '1055232054343117', 'targetWabaId': '2094615664435155', 'sendPin': True},
                'req-1')
        assert result['statusCode'] == 400


class TestConversationalComponents:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = _import_handler()
        self.h.origin = ''

    def test_requires_prompts_or_commands(self):
        assert self.h._push_conversational_components({}, 'req-1')['statusCode'] == 400

    def test_all_success(self):
        with patch.object(self.h._meta, 'post', return_value={'success': True}), \
             patch.object(self.h, 'record_audit') as mock_audit:
            result = self.h._push_conversational_components({'prompts': ['Hi']}, 'req-1')
        assert result['statusCode'] == 200
        assert json.loads(result['body'])['success'] is True
        assert mock_audit.call_args.kwargs['action'] == 'conversational.update'

    def test_partial_failure_returns_207(self):
        with patch.object(self.h._meta, 'post', side_effect=[{'success': True}, _meta_error(http_status=400)]), \
             patch.object(self.h, 'record_audit'):
            result = self.h._push_conversational_components({'commands': [{'command_name': 'menu'}]}, 'req-1')
        assert result['statusCode'] == 207
        body = json.loads(result['body'])
        assert body['success'] is False
