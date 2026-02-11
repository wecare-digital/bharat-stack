"""
AWS EUM Social client wrapper with retries, backoff, throttling, error normalization.
All WhatsApp communication goes through this layer — no direct Meta Graph API calls.
"""
import json
import time
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0
_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client('socialmessaging', region_name='us-east-1')
    return _client


class SocialMessagingError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 500):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"[{code}] {message}")


def send_message(phone_number_id: str, message_payload: dict, meta_api_version: str = 'v20.0') -> Dict[str, Any]:
    """Send WhatsApp message. message_payload is a WhatsApp Message object dict."""
    client = get_client()
    message_bytes = json.dumps(message_payload).encode('utf-8')
    for attempt in range(MAX_RETRIES):
        try:
            response = client.send_whatsapp_message(
                originationPhoneNumberId=phone_number_id,
                message=message_bytes,
                metaApiVersion=meta_api_version
            )
            msg_id = response.get('messageId', '')
            logger.info(f"send_message success: phoneId={phone_number_id} messageId={msg_id}")
            return {'messageId': msg_id}
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(f"Throttled, retry in {delay}s (attempt {attempt + 1})")
                time.sleep(delay)
                continue
            raise SocialMessagingError(
                code=code,
                message=e.response['Error'].get('Message', str(e)),
                http_status=e.response['ResponseMetadata'].get('HTTPStatusCode', 500)
            )


def download_media(media_id: str, phone_number_id: str, s3_bucket: str, s3_key: str) -> Dict[str, Any]:
    """Download media from WhatsApp to S3."""
    client = get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get_whatsapp_message_media(
                mediaId=media_id,
                originationPhoneNumberId=phone_number_id,
                destinationS3File={'bucketName': s3_bucket, 'key': s3_key}
            )
            logger.info(f"download_media success: mediaId={media_id} s3={s3_bucket}/{s3_key}")
            return {'fileSize': response.get('fileSize'), 'mimeType': response.get('mimeType')}
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                time.sleep(min(BASE_DELAY * (2 ** attempt), MAX_DELAY))
                continue
            raise SocialMessagingError(code=code, message=str(e))


def upload_media(phone_number_id: str, s3_bucket: str, s3_key: str) -> str:
    """Upload media from S3 to WhatsApp. Returns mediaId."""
    client = get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.post_whatsapp_message_media(
                originationPhoneNumberId=phone_number_id,
                sourceS3File={'bucketName': s3_bucket, 'key': s3_key}
            )
            media_id = response.get('mediaId', '')
            logger.info(f"upload_media success: phoneId={phone_number_id} mediaId={media_id}")
            return media_id
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                time.sleep(min(BASE_DELAY * (2 ** attempt), MAX_DELAY))
                continue
            raise SocialMessagingError(code=code, message=str(e))


def delete_media(media_id: str, phone_number_id: str) -> bool:
    """Delete media from WhatsApp servers."""
    client = get_client()
    try:
        response = client.delete_whatsapp_message_media(
            mediaId=media_id, originationPhoneNumberId=phone_number_id
        )
        return response.get('success', False)
    except ClientError as e:
        raise SocialMessagingError(code=e.response['Error']['Code'], message=str(e))
