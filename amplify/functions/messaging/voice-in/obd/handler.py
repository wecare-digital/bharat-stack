"""
Airtel OBD (Outbound Dialer) Campaign Lambda Function

Purpose: Manage bulk voice campaigns via Airtel IQ Telephony API
Features:
- Upload audio prompts (16bits 8000Hz Mono WAV only)
- Upload CSV contact lists with variables
- Create OBD campaigns with default or custom audio (Info-Only)
- Store recordings in S3

API Endpoints (Airtel):
- Upload Audio: POST https://openapi.airtel.in/gateway/airtel-xchange/uploadPrompts?customerId={customerId}
  Headers: requester-id: ironman, Authorization: Basic {upload_auth}
  Body: multipart/form-data with files=@"/path/to/file.wav"
  Response: { audioUrl: "..." } → inject into Create Campaign inputVariables audioURL

- Upload CSV: POST https://openapi.airtel.in/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customerId}&campaignType=OBD_CALL
  Headers: app-id: IRONMAN, Authorization: Basic {upload_auth}
  Body: multipart/form-data with file=@"contacts.csv"
  Response: { fileName, headers, firstRow, totalCount } → use fileName in sheetFileNames,
            headers to build inputCsvMappings

- Create Campaign: POST https://iqtelephony.airtel.in/gateway/airtel-xchange/campaign-manager/v2/createCampaign
  Headers: app-id: IRONMAN, Authorization: Basic {campaign_auth}
  Body: JSON with callFlowConfigV2, inputCsvMappings from upload response

Airtel OBD Requirements:
- Call Flow: Voice (Info-Only)
- Audio: 16bits 8000Hz Mono WAV only
- Campaign Type: TRANSACTIONAL always
- CSV Column: Number (mapped to participantAddress via inputCsvMappings)
- inputCsvMappings: {"participantAddress": "Number"} (built from upload response headers)

Literal Placeholder Rule (Do NOT Substitute):
  The following MUST be treated as fixed literal strings in metaData and must NOT be
  substituted, interpolated, or mapped from any source:
  ${campaignId}, ${campaignName}, ${campaignEndTime}, ${dsrId}, ${participantAddress}

CDR Callback: https://api.wecare.digital/voice-in/obd
  serviceId: We_careCDRDetailsService_obd
  projectId: We_CareCDRDetails_obd

Secrets: wecare/airtel/obd
Expected secret keys:
- customer_id: WECAREDIG_v6J1SyLLI2auy7Lw9JrW
- upload_auth: Base64 token for CSV upload API (campaign-manager-v3/file/s3/upload)
- audio_upload_auth: Base64 token for audio upload API (uploadPrompts)
- campaign_auth: Base64 token for createCampaign API
- app_id: IRONMAN
- call_flow_id: dfbeda76-f641-420f-95e7-b78d562a941f
- caller_id: 8040761117 (Fixed Line · Karnataka · Outbound/Inbound)
- template_id: 69818654d9e8e260e60b16a7
"""

import os
import json
import uuid
import time
import logging
import boto3
import base64
import urllib.request
import urllib.error
from typing import Dict, Any, List
from decimal import Decimal

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

# Environment variables
OBD_CAMPAIGNS_TABLE = os.environ.get('OBD_CAMPAIGNS_TABLE', 'stack-wecare-digital-OBDCampaigns')
VOICE_CDR_TABLE = os.environ.get('VOICE_CDR_TABLE', 'stack-wecare-digital-VoiceCDRTable')
S3_BUCKET = os.environ.get('S3_BUCKET', 'app.wecare.digital')
S3_RECORDING_PREFIX = 'stack/voice/'
S3_OBD_AUDIO_PREFIX = 'stack/voice/obd-audio/'
AIRTEL_OBD_SECRET_NAME = os.environ.get('AIRTEL_OBD_SECRET_NAME', 'wecare/airtel/obd')
TTL_DAYS = 90

# Airtel audio spec
AIRTEL_SAMPLE_RATE = 8000
AIRTEL_CHANNELS = 1
AIRTEL_BITS_PER_SAMPLE = 16

# API Hosts
AIRTEL_OPENAPI_HOST = 'openapi.airtel.in'
AIRTEL_IQTELEPHONY_HOST = 'iqtelephony.airtel.in'
AIRTEL_DEFAULT_AUDIO_URL = 'https://openapi.airtel.in/gateway/airtel-xchange/assets/audios/global/Default_Airtel_Jingle.wav'

# Cached secrets
_secrets_cache = None


def _get_secrets() -> Dict[str, str]:
    """Fetch Airtel OBD credentials from Secrets Manager (cached)."""
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    
    try:
        response = secrets_client.get_secret_value(SecretId=AIRTEL_OBD_SECRET_NAME)
        _secrets_cache = json.loads(response['SecretString'])
        logger.info(f"Loaded secrets from {AIRTEL_OBD_SECRET_NAME}")
        return _secrets_cache
    except Exception as e:
        logger.error(f"Failed to load secrets: {str(e)}")
        return {}


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle OBD campaign operations."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    global origin
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    query_params = event.get('queryStringParameters') or {}
    
    try:
        body = {}
        if event.get('body'):
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'})
        
        # Detect Airtel CDR callback (Airtel sends OBD CDR callbacks to this endpoint)
        if http_method == 'POST' and _is_airtel_cdr_callback(body):
            return _handle_cdr_callback(body, request_id)

        if '/tts' in path:
            return _text_to_audio(body, request_id)
        elif '/audio-library' in path:
            if http_method == 'GET':
                return _list_audio_library(query_params, request_id)
            elif http_method == 'POST':
                return _upload_to_audio_library(body, request_id)
            elif http_method == 'DELETE':
                return _delete_audio_library_file(body, query_params, request_id)
        elif '/upload-audio' in path:
            return _upload_audio(body, event, request_id)
        elif '/upload-csv' in path:
            return _upload_csv(body, request_id)
        elif '/create' in path:
            return _create_campaign(body, request_id)
        elif '/status' in path:
            campaign_id = event.get('pathParameters', {}).get('campaignId') or body.get('campaignId')
            return _get_campaign_status(campaign_id, request_id)
        elif '/list' in path or http_method == 'GET':
            return _list_campaigns(query_params, request_id)
        elif '/clear-logs' in path:
            return _clear_logs(body, request_id)
        elif '/delete' in path or http_method == 'DELETE':
            campaign_id = query_params.get('campaignId') or body.get('campaignId')
            hard_delete = query_params.get('hard') == 'true' or body.get('hardDelete', False)
            if body.get('clearAll'):
                return _clear_logs(body, request_id)
            return _delete_campaign(campaign_id, hard_delete, request_id)
        else:
            if http_method == 'POST':
                # Support clear-logs via POST body action
                if body.get('clearAll') or body.get('_action') == 'clear-logs':
                    return _clear_logs(body, request_id)
                return _create_campaign(body, request_id)
            if http_method == 'DELETE':
                campaign_id = query_params.get('campaignId')
                return _delete_campaign(campaign_id, False, request_id)
            return _response(404, {'error': 'Endpoint not found'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"OBD error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _parse_wav_header(data: bytes) -> Dict:
    """Parse WAV file header and return format info."""
    import struct
    if len(data) < 44 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        return {'valid': False, 'error': 'Not a valid WAV file'}
    
    # Find fmt chunk
    pos = 12
    fmt_found = False
    audio_format = channels = sample_rate = bits_per_sample = 0
    data_offset = data_size = 0
    
    while pos < len(data) - 8:
        chunk_id = data[pos:pos+4]
        chunk_size = struct.unpack_from('<I', data, pos+4)[0]
        if chunk_id == b'fmt ':
            if chunk_size < 16:
                return {'valid': False, 'error': 'Invalid fmt chunk'}
            audio_format, channels, sample_rate, _, _, bits_per_sample = struct.unpack_from('<HHIIHH', data, pos+8)
            fmt_found = True
        elif chunk_id == b'data':
            data_offset = pos + 8
            data_size = chunk_size
        pos += 8 + chunk_size
        # Align to even boundary
        if chunk_size % 2:
            pos += 1
    
    if not fmt_found:
        return {'valid': False, 'error': 'No fmt chunk found'}
    
    return {
        'valid': True,
        'audioFormat': audio_format,  # 1 = PCM
        'channels': channels,
        'sampleRate': sample_rate,
        'bitsPerSample': bits_per_sample,
        'dataOffset': data_offset,
        'dataSize': data_size,
        'isPCM': audio_format == 1,
    }


def _convert_wav_to_airtel_spec(audio_bytes: bytes, request_id: str) -> Dict:
    """
    Validate and convert WAV to Airtel spec: 16-bit 8kHz Mono PCM WAV.
    
    Returns: {
        'converted': bool,       # True if conversion was needed
        'compliant': bool,       # True if already compliant (no conversion needed)
        'audioBytes': bytes,     # The compliant WAV bytes
        'originalInfo': dict,    # Original format info
        'error': str or None,    # Error message if failed
        'report': str,           # Human-readable report
    }
    """
    import struct
    
    info = _parse_wav_header(audio_bytes)
    if not info.get('valid'):
        return {'converted': False, 'compliant': False, 'audioBytes': audio_bytes, 'originalInfo': info, 'error': info.get('error', 'Invalid WAV'), 'report': f"Invalid WAV: {info.get('error')}"}
    
    already_compliant = (
        info['isPCM'] and
        info['channels'] == AIRTEL_CHANNELS and
        info['sampleRate'] == AIRTEL_SAMPLE_RATE and
        info['bitsPerSample'] == AIRTEL_BITS_PER_SAMPLE
    )
    
    ch_label = 'Mono' if info['channels'] == 1 else ('Stereo' if info['channels'] == 2 else str(info['channels']) + 'ch')
    fmt_label = 'PCM' if info['isPCM'] else ('fmt=' + str(info['audioFormat']))
    orig_desc = f"{info['sampleRate']}Hz {info['bitsPerSample']}bit {ch_label} {fmt_label}"
    
    if already_compliant:
        return {
            'converted': False, 'compliant': True, 'audioBytes': audio_bytes,
            'originalInfo': info, 'error': None,
            'report': f"Already Airtel-compliant: {orig_desc}"
        }
    
    if not info['isPCM']:
        return {
            'converted': False, 'compliant': False, 'audioBytes': audio_bytes,
            'originalInfo': info, 'error': f'Non-PCM audio (format={info["audioFormat"]}). Only PCM WAV can be auto-converted. Please convert to PCM WAV first.',
            'report': f"Cannot convert non-PCM: {orig_desc}"
        }
    
    if info['dataOffset'] == 0 or info['dataSize'] == 0:
        return {'converted': False, 'compliant': False, 'audioBytes': audio_bytes, 'originalInfo': info, 'error': 'No audio data found in WAV', 'report': 'No data chunk'}
    
    try:
        raw_pcm = audio_bytes[info['dataOffset']:info['dataOffset'] + info['dataSize']]
        src_channels = info['channels']
        src_rate = info['sampleRate']
        src_bits = info['bitsPerSample']
        
        # Step 1: Decode PCM samples to list of float values (mono)
        if src_bits == 16:
            sample_count = len(raw_pcm) // (2 * src_channels)
            samples = list(struct.unpack(f'<{sample_count * src_channels}h', raw_pcm[:sample_count * 2 * src_channels]))
        elif src_bits == 8:
            sample_count = len(raw_pcm) // src_channels
            samples = [((b - 128) * 256) for b in raw_pcm[:sample_count * src_channels]]
        elif src_bits == 24:
            sample_count = len(raw_pcm) // (3 * src_channels)
            samples = []
            for i in range(sample_count * src_channels):
                off = i * 3
                val = raw_pcm[off] | (raw_pcm[off+1] << 8) | (raw_pcm[off+2] << 16)
                if val >= 0x800000:
                    val -= 0x1000000
                samples.append(val >> 8)  # Scale 24-bit to 16-bit
        elif src_bits == 32:
            sample_count = len(raw_pcm) // (4 * src_channels)
            samples = list(struct.unpack(f'<{sample_count * src_channels}i', raw_pcm[:sample_count * 4 * src_channels]))
            samples = [s >> 16 for s in samples]  # Scale 32-bit to 16-bit
        else:
            return {'converted': False, 'compliant': False, 'audioBytes': audio_bytes, 'originalInfo': info, 'error': f'Unsupported bit depth: {src_bits}', 'report': f'Cannot convert {src_bits}-bit'}
        
        # Step 2: Mix to mono if stereo/multi-channel
        if src_channels > 1:
            mono_samples = []
            for i in range(0, len(samples), src_channels):
                chunk = samples[i:i+src_channels]
                mono_samples.append(sum(chunk) // len(chunk))
            samples = mono_samples
        
        # Step 3: Resample to 8000Hz using linear interpolation
        if src_rate != AIRTEL_SAMPLE_RATE:
            src_len = len(samples)
            ratio = src_rate / AIRTEL_SAMPLE_RATE
            dst_len = int(src_len / ratio)
            resampled = []
            for i in range(dst_len):
                src_pos = i * ratio
                idx = int(src_pos)
                frac = src_pos - idx
                if idx + 1 < src_len:
                    val = samples[idx] * (1 - frac) + samples[idx + 1] * frac
                else:
                    val = samples[min(idx, src_len - 1)]
                resampled.append(int(max(-32768, min(32767, val))))
            samples = resampled
        
        # Step 4: Clamp to 16-bit range
        samples = [max(-32768, min(32767, s)) for s in samples]
        
        # Step 5: Build compliant WAV
        pcm_out = struct.pack(f'<{len(samples)}h', *samples)
        byte_rate = AIRTEL_SAMPLE_RATE * AIRTEL_CHANNELS * AIRTEL_BITS_PER_SAMPLE // 8
        block_align = AIRTEL_CHANNELS * AIRTEL_BITS_PER_SAMPLE // 8
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + len(pcm_out), b'WAVE',
            b'fmt ', 16, 1, AIRTEL_CHANNELS, AIRTEL_SAMPLE_RATE, byte_rate, block_align, AIRTEL_BITS_PER_SAMPLE,
            b'data', len(pcm_out)
        )
        converted_wav = wav_header + pcm_out
        
        target_desc = f"{AIRTEL_SAMPLE_RATE}Hz {AIRTEL_BITS_PER_SAMPLE}bit Mono PCM"
        report = f"Converted: {orig_desc} → {target_desc} ({len(audio_bytes)} → {len(converted_wav)} bytes)"
        
        logger.info(json.dumps({
            'event': 'audio_converted_to_airtel_spec',
            'original': orig_desc,
            'target': target_desc,
            'originalSize': len(audio_bytes),
            'convertedSize': len(converted_wav),
            'requestId': request_id
        }))
        
        return {
            'converted': True, 'compliant': True, 'audioBytes': converted_wav,
            'originalInfo': info, 'error': None, 'report': report
        }
    except Exception as e:
        logger.error(f"Audio conversion error: {str(e)}")
        return {'converted': False, 'compliant': False, 'audioBytes': audio_bytes, 'originalInfo': info, 'error': f'Conversion failed: {str(e)}', 'report': f'Conversion error: {str(e)}'}


def _upload_audio(body: Dict, event: Dict, request_id: str) -> Dict[str, Any]:
    """
    Upload audio prompt to Airtel for OBD campaigns.
    
    Airtel API: POST https://openapi.airtel.in/gateway/airtel-xchange/uploadPrompts?customerId={customerId}
    Headers: requester-id: ironman, Authorization: Basic {upload_auth}
    Body: multipart/form-data with files=@"/path/to/file.wav"
    
    Audio Requirements: 16bits 8000Hz Mono WAV only
    
    The audioUrl from the response MUST be injected into the Create Campaign API
    inputVariables as the "audioURL" value.
    
    Request body options:
    - audioData: base64-encoded WAV file content
    - audioS3Key: S3 key to fetch audio from (bucket: app.wecare.digital)
    - fileName: optional custom filename (default: obd_audio_{timestamp}.wav)
    """
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        # Audio upload uses audio_upload_auth with requester-id header
        auth_token = secrets.get('audio_upload_auth', secrets.get('upload_auth', ''))
        
        if not customer_id or not auth_token:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        audio_data = body.get('audioData')  # base64 encoded
        audio_s3_key = body.get('audioS3Key')
        file_name = body.get('fileName', f'obd_audio_{int(time.time())}.wav')
        
        if audio_data:
            audio_bytes = base64.b64decode(audio_data)
        elif audio_s3_key:
            response = s3.get_object(Bucket=S3_BUCKET, Key=audio_s3_key)
            audio_bytes = response['Body'].read()
        else:
            return _response(400, {'error': 'audioData (base64) or audioS3Key is required'})
        
        # Validate and auto-convert to Airtel spec (16-bit 8kHz Mono PCM WAV)
        conv = _convert_wav_to_airtel_spec(audio_bytes, request_id)
        if conv.get('error') and not conv.get('compliant'):
            return _response(400, {'error': conv['error'], 'report': conv['report'], 'originalInfo': conv.get('originalInfo')})
        audio_bytes = conv['audioBytes']
        
        # Store converted file in S3 for download
        converted_s3_key = f'{S3_OBD_AUDIO_PREFIX}{file_name}'
        s3.put_object(Bucket=S3_BUCKET, Key=converted_s3_key, Body=audio_bytes, ContentType='audio/wav')
        download_url = f'https://{S3_BUCKET}/{converted_s3_key}'
        
        # Upload to Airtel uploadPrompts API
        # Endpoint: POST https://openapi.airtel.in/gateway/airtel-xchange/uploadPrompts?customerId={customerId}
        # Headers: requester-id: ironman, Authorization: Basic {audio_upload_auth}
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/uploadPrompts?customerId={customer_id}"
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="files"; filename="{file_name}"'.encode(),
            b'Content-Type: audio/wav',
            b'',
            audio_bytes,
            f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'requester-id': 'ironman'
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'obd_upload_audio',
            'url': url,
            'fileName': file_name,
            'sizeBytes': len(audio_bytes),
            'requestId': request_id
        }))
        
        # Try upload with retry (Airtel uploadPrompts can be slow)
        audio_url = ''
        last_error = ''
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    audio_url = _extract_audio_url(result)
                    
                    logger.info(json.dumps({
                        'event': 'obd_audio_uploaded',
                        'audioUrl': audio_url,
                        'result': result,
                        'attempt': attempt + 1,
                        'requestId': request_id
                    }))
                    break
            except Exception as upload_err:
                last_error = str(upload_err)
                logger.warning(f"Audio upload attempt {attempt + 1} failed: {last_error}")
                if attempt == 0:
                    time.sleep(2)
        
        if not audio_url and last_error:
            logger.error(f"Audio upload failed after retries: {last_error}")
            return _response(500, {
                'error': f'Audio upload to Airtel failed: {last_error}',
                'downloadUrl': download_url,
                'sizeBytes': len(audio_bytes),
                'converted': conv.get('converted', False),
                'conversionReport': conv.get('report', ''),
            })
        
        return _response(200, {
            'success': True,
            'fileName': file_name,
            'audioUrl': audio_url,
            'sizeBytes': len(audio_bytes),
            'downloadUrl': download_url,
            'converted': conv.get('converted', False),
            'conversionReport': conv.get('report', ''),
        })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Audio upload error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"Audio upload error: {str(e)}")
        return _response(500, {'error': str(e)})


def _text_to_audio(body: Dict, request_id: str) -> Dict[str, Any]:
    """Convert text to speech using AWS Polly, store WAV in S3.

    Generates 16-bit 8kHz Mono WAV (Airtel requirement) via Polly,
    stores in S3, then uploads to Airtel uploadPrompts API.

    Request body:
    - text: The text to convert to speech (required, max 3000 chars)
    - voiceId: Polly voice (default: Kajal for en-IN)
    - languageCode: e.g. hi-IN, en-IN (default: en-IN)
    """
    try:
        text = body.get('text', '').strip()
        if not text:
            return _response(400, {'error': 'text is required'})
        if len(text) > 3000:
            return _response(400, {'error': 'text must be 3000 characters or less'})

        voice_id = body.get('voiceId', 'Kajal')
        language_code = body.get('languageCode', 'en-IN')
        engine = 'neural' if voice_id in ('Kajal',) else 'standard'

        polly = boto3.client('polly', region_name=AWS_REGION)

        # Synthesize speech as PCM 8000Hz (Airtel requires 8kHz)
        polly_resp = polly.synthesize_speech(
            Text=text,
            OutputFormat='pcm',
            SampleRate='8000',
            VoiceId=voice_id,
            LanguageCode=language_code,
            Engine=engine,
        )

        pcm_data = polly_resp['AudioStream'].read()

        # Build WAV header for 16-bit 8kHz Mono PCM
        import struct
        num_channels = 1
        sample_rate = 8000
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_data)

        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_size, b'WAVE',
            b'fmt ', 16, 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
            b'data', data_size
        )
        wav_bytes = wav_header + pcm_data
        file_name = f'tts_audio_{int(time.time())}.wav'
        s3_key = f'{S3_RECORDING_PREFIX}tts/{file_name}'

        # Store in S3
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=wav_bytes, ContentType='audio/wav')

        logger.info(json.dumps({
            'event': 'obd_tts_generated',
            'textLength': len(text),
            'voiceId': voice_id,
            'wavSize': len(wav_bytes),
            's3Key': s3_key,
            'requestId': request_id
        }))

        # Upload to Airtel uploadPrompts
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        # Audio upload uses audio_upload_auth with requester-id header
        auth_token = secrets.get('audio_upload_auth', secrets.get('upload_auth', ''))

        audio_url = ''
        if customer_id and auth_token:
            try:
                url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/uploadPrompts?customerId={customer_id}"
                boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
                body_parts = [
                    f'--{boundary}'.encode(),
                    f'Content-Disposition: form-data; name="files"; filename="{file_name}"'.encode(),
                    b'Content-Type: audio/wav', b'',
                    wav_bytes,
                    f'--{boundary}--'.encode()
                ]
                headers = {
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'Authorization': f'Basic {auth_token}',
                    'requester-id': 'ironman'
                }
                req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    audio_url = _extract_audio_url(result)
            except Exception as upload_err:
                logger.warning(f"Airtel upload failed (will use S3): {str(upload_err)}")

        return _response(200, {
            'success': True,
            'audioUrl': audio_url,
            's3Key': s3_key,
            'fileName': file_name,
            'sizeBytes': len(wav_bytes),
            'voiceId': voice_id,
            'languageCode': language_code,
            'textLength': len(text),
        })

    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return _response(500, {'error': str(e)})



def _upload_csv(body: Dict, request_id: str) -> Dict[str, Any]:
    """Upload CSV contact list to Airtel with variable support.
    
    Airtel API: POST https://openapi.airtel.in/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload
    Query params: customerId={customerId}&campaignType=OBD_CALL
    Headers: app-id: IRONMAN, Authorization: Basic {upload_auth}
    Body: multipart/form-data with file=@"contacts.csv"
    
    CSV column must be 'Number' (not 'participantNumber').
    The inputCsvMappings in createCampaign maps: {"participantAddress": "Number"}
    
    Response includes fileName, headers, firstRow, totalCount which should be used
    when creating the campaign:
    - fileName → sheetFileNames array
    - headers → build inputCsvMappings (e.g. {"participantAddress": "Number"})
    - firstRow → sample values for validation
    - totalCount → validate > 0 before creating campaign
    """
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        # CSV upload uses upload_auth with app-id header
        auth_token = secrets.get('upload_auth', '')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        if not customer_id or not auth_token:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        contacts = body.get('contacts', [])
        variables = body.get('variables', {})  # {phone: {var1: val1, var2: val2}}
        csv_url = body.get('csvUrl')
        csv_data = body.get('csvData')
        
        if contacts:
            # Build CSV with 'Number' column (Airtel requirement per actual API)
            var_names = []
            if variables:
                for phone, vars_dict in variables.items():
                    var_names.extend(vars_dict.keys())
                var_names = list(set(var_names))
            
            if var_names:
                header = "Number," + ",".join(var_names)
                rows = []
                for contact in contacts:
                    clean_phone = _clean_phone(contact)
                    if not clean_phone:
                        continue
                    phone_vars = variables.get(contact, variables.get(clean_phone, {}))
                    var_values = [str(phone_vars.get(v, '')) for v in var_names]
                    rows.append(f"{clean_phone},{','.join(var_values)}")
                csv_content = header + "\n" + "\n".join(rows)
            else:
                csv_content = "Number\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
            csv_bytes = csv_content.encode('utf-8')
        elif csv_url and csv_url.startswith('s3://'):
            parts = csv_url.replace('s3://', '').split('/', 1)
            response = s3.get_object(Bucket=parts[0], Key=parts[1] if len(parts) > 1 else '')
            csv_bytes = response['Body'].read()
        elif csv_data:
            csv_bytes = base64.b64decode(csv_data)
        else:
            return _response(400, {'error': 'contacts, csvUrl, or csvData is required'})
        
        file_name = f'obd_contacts_{int(time.time())}.csv'
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customer_id}&campaignType=OBD_CALL"
        
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode(),
            b'Content-Type: text/csv', b'',
            csv_bytes,
            f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'app-id': app_id
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            uploaded_name = result.get('fileName') or result.get('sheetFileName') or file_name
            resp_headers = result.get('headers', [])
            first_row = result.get('firstRow', {})
            total_count = result.get('totalCount', len(contacts) if contacts else 0)
            return _response(200, {
                'success': True,
                'fileName': uploaded_name,
                'headers': resp_headers,
                'firstRow': first_row,
                'totalCount': total_count,
                'contactCount': len(contacts) if contacts else None,
                'variableColumns': var_names if var_names else None,
                'result': result
            })
            
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        return _response(500, {'error': str(e)})



def _create_campaign(body: Dict, request_id: str) -> Dict[str, Any]:
    """Create OBD campaign via Airtel API.
    
    Airtel API: POST https://iqtelephony.airtel.in/gateway/airtel-xchange/campaign-manager/v2/createCampaign
    Headers: app-id: IRONMAN, Authorization: Basic {campaign_auth}, Content-Type: application/json
    
    Airtel OBD Requirements:
    - Call Flow: Voice (Info-Only) - plays audio and disconnects
    - Audio: 16bits 8000Hz Mono WAV only
    - Campaign Type: TRANSACTIONAL always
    - CSV Column: Number (mapped to participantAddress via inputCsvMappings)
    
    Uses upload response data:
    - response.fileName → sheetFileNames array
    - response.headers → build inputCsvMappings (e.g. {"participantAddress": "Number"})
    - Validate response.totalCount > 0 before creating
    
    Literal Placeholder Rule (Do NOT Substitute):
    ${campaignId}, ${campaignName}, ${campaignEndTime}, ${dsrId}, ${participantAddress}
    These are fixed literal strings resolved by Airtel at runtime.
    """
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        # Create campaign uses campaign_auth with app-id header
        campaign_auth = secrets.get('campaign_auth', '')
        app_id = secrets.get('app_id', 'IRONMAN')
        call_flow_id = secrets.get('call_flow_id', 'dfbeda76-f641-420f-95e7-b78d562a941f')
        caller_id = secrets.get('caller_id', '8040761117')
        template_id = secrets.get('template_id', '69818654d9e8e260e60b16a7')
        
        if not customer_id or not campaign_auth:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        campaign_name = body.get('campaignName', f'OBD_Campaign_{int(time.time())}')
        contacts = body.get('contacts', [])
        variables = body.get('variables', {})  # {phone: {var1: val1, var2: val2}}
        sheet_file_names = body.get('sheetFileNames', [])
        input_csv_mappings = body.get('inputCsvMappings', {})
        caller_id = body.get('callerId', caller_id)
        retry_count = body.get('retryCount', 2)
        
        # Use custom audio URL if provided, otherwise default Airtel jingle
        audio_url = body.get('audioUrl', AIRTEL_DEFAULT_AUDIO_URL)
        
        # Start/end time (epoch ms UTC) — 5 min from now to allow Airtel scheduling, end in 24 hours
        start_time = body.get('startTime', int(time.time() * 1000) + (5 * 60 * 1000))  # 5 min from now
        end_time = body.get('endTime', start_time + (24 * 3600 * 1000))  # 24 hours
        
        # Upload CSV if contacts provided and no sheetFileNames already uploaded
        if contacts and not sheet_file_names:
            csv_result = _upload_csv_internal(contacts, variables, secrets, request_id)
            if not csv_result.get('success'):
                return _response(500, {'error': csv_result.get('error', 'Failed to upload contacts')})
            sheet_file_names = [csv_result.get('fileName')]
            # Build inputCsvMappings from upload response headers if not provided
            if not input_csv_mappings:
                upload_headers = csv_result.get('headers', [])
                if 'Number' in upload_headers:
                    input_csv_mappings = {"participantAddress": "Number"}
                else:
                    input_csv_mappings = {"participantAddress": "Number"}
            # Validate totalCount > 0
            total_count = csv_result.get('totalCount', 0)
            if total_count == 0 and contacts:
                logger.warning(f"Upload returned totalCount=0 but {len(contacts)} contacts were sent")
        
        # Store contact count from body if provided (when CSV was uploaded separately)
        contact_count = body.get('contactCount', len(contacts) if contacts else 0)
        
        if not sheet_file_names:
            return _response(400, {'error': 'contacts or sheetFileNames is required'})
        
        # Default inputCsvMappings if not set
        if not input_csv_mappings:
            input_csv_mappings = {"participantAddress": "Number"}
        
        campaign_id = str(uuid.uuid4())
        
        # Build input variables for call flow
        # participantAddress: use first contact number as default — CSV mapping overrides at runtime
        first_contact = body.get('firstContact', '')
        if not first_contact and contacts:
            first_contact = _clean_phone(contacts[0])
        if not first_contact:
            first_contact = caller_id  # fallback to caller_id
        
        input_variables = [
            {"name": "participantAddress", "value": first_contact, "type": "phoneNumber"},
            {"name": "callerId", "value": caller_id, "type": "phoneNumber"},
            {"name": "audioURL", "value": audio_url, "type": "string"}
        ]
        
        # IMPORTANT: metaData placeholders are LITERAL strings resolved by Airtel at runtime.
        # Do NOT substitute, interpolate, or map these from any source.
        payload = {
            "customerId": customer_id,
            "templateId": template_id,
            "campaignName": campaign_name,
            "startTime": start_time,
            "endTime": end_time,
            "sheetFileNames": sheet_file_names,
            "campaignData": {
                "customerId": customer_id,
                "messageType": "TRANSACTIONAL",
                "callBackQueueActive": True,
                "callType": "OUTBOUND",
                "additionalObjectsForRequestBody": {
                    "metaData": {
                        "Channel": "OBD",
                        "campaignId": "${campaignId}",
                        "campaignName": "${campaignName}",
                        "campaignEndTime": "${campaignEndTime}",
                        "dsrId": "${dsrId}",
                        "isV2": True
                    },
                    "callFlowConfigV2": {
                        "callFlowId": call_flow_id,
                        "inputVariables": input_variables,
                        "callBackURLs": [
                            {"notifyURL": "queue", "eventType": "CALL"},
                            {
                                "eventType": "CDR",
                                "notifyURL": "https://api.wecare.digital/voice-in/obd",
                                "method": "POST",
                                "serviceId": "We_careCDRDetailsService_obd",
                                "projectId": "We_CareCDRDetails_obd",
                                "headers": {"a": "b"}
                            }
                        ]
                    }
                }
            },
            "inputCsvMappings": input_csv_mappings,
            "campaignType": "OBD_CALL",
            "retryDetail": {
                "maxRetryCount": retry_count,
                "retryConfig": {"retryType": "FIXED_INTERVAL", "retryIntervalList": [100, 200]},
                "retryCountToEventMap": {"1": ["default"], "2": ["busy"]}
            }
        }
        
        url = f"https://{AIRTEL_IQTELEPHONY_HOST}/gateway/airtel-xchange/campaign-manager/v2/createCampaign"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {campaign_auth}',
            'app-id': app_id
        }
        
        logger.info(json.dumps({
            'event': 'obd_create_campaign',
            'campaignName': campaign_name,
            'contactCount': len(contacts),
            'sheetFileNames': sheet_file_names,
            'requestId': request_id
        }))
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            airtel_campaign_id = result.get('campaignId') or result.get('id')
            
            _store_campaign(campaign_id, campaign_name, airtel_campaign_id, sheet_file_names, audio_url, contact_count)
            
            return _response(200, {
                'success': True,
                'campaignId': campaign_id,
                'airtelCampaignId': airtel_campaign_id,
                'campaignName': campaign_name,
                'contactCount': contact_count,
                'status': 'created'
            })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Campaign create error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"Campaign create error: {str(e)}")
        return _response(500, {'error': str(e)})


def _upload_csv_internal(contacts: List[str], variables: Dict, secrets: Dict, request_id: str) -> Dict[str, Any]:
    """Internal CSV upload helper with variable support. CSV column: Number.
    
    Returns: {success, fileName, headers, firstRow, totalCount}
    """
    try:
        customer_id = secrets.get('customer_id')
        # CSV upload uses upload_auth with app-id header
        auth_token = secrets.get('upload_auth', '')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        # Get variable names
        var_names = []
        if variables:
            for phone_vars in variables.values():
                var_names.extend(phone_vars.keys())
            var_names = list(set(var_names))
        
        # Build CSV with 'Number' column (Airtel requirement per actual API)
        if var_names:
            header = "Number," + ",".join(var_names)
            rows = []
            for contact in contacts:
                clean_phone = _clean_phone(contact)
                if not clean_phone:
                    continue
                phone_vars = variables.get(contact, variables.get(clean_phone, {}))
                var_values = [str(phone_vars.get(v, '')) for v in var_names]
                rows.append(f"{clean_phone},{','.join(var_values)}")
            csv_content = header + "\n" + "\n".join(rows)
        else:
            csv_content = "Number\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
        
        csv_bytes = csv_content.encode('utf-8')
        file_name = f'obd_contacts_{int(time.time())}.csv'
        
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customer_id}&campaignType=OBD_CALL"
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode(),
            b'Content-Type: text/csv', b'', csv_bytes, f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'app-id': app_id
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                'success': True,
                'fileName': result.get('fileName') or result.get('sheetFileName') or file_name,
                'headers': result.get('headers', []),
                'firstRow': result.get('firstRow', {}),
                'totalCount': result.get('totalCount', len(contacts))
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _get_campaign_status(campaign_id: str, request_id: str) -> Dict[str, Any]:
    """Get campaign status."""
    try:
        if not campaign_id:
            return _response(400, {'error': 'campaignId is required'})
        
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        result = table.get_item(Key={'id': campaign_id})
        campaign = result.get('Item')
        
        if campaign:
            return _response(200, {'campaign': _normalize_campaign(campaign)})
        return _response(404, {'error': 'Campaign not found'})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _list_campaigns(params: Dict, request_id: str) -> Dict[str, Any]:
    """List OBD campaigns."""
    try:
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        result = table.scan(Limit=int(params.get('limit', 50)))
        campaigns = result.get('Items', [])
        campaigns.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {'campaigns': [_normalize_campaign(c) for c in campaigns], 'count': len(campaigns)})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _store_campaign(campaign_id: str, name: str, airtel_id: str, sheets: List[str], audio_url: str, contact_count: int = 0) -> None:
    """Store campaign record."""
    try:
        now = int(time.time())
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        table.put_item(Item={
            'id': campaign_id,
            'campaignId': campaign_id,
            'airtelCampaignId': airtel_id or '',
            'campaignName': name,
            'sheetFileNames': sheets,
            'audioUrl': audio_url,
            'contactCount': contact_count,
            'status': 'created',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + (TTL_DAYS * 24 * 60 * 60)))
        })
    except Exception as e:
        logger.error(f"Store campaign error: {str(e)}")


def _delete_campaign(campaign_id: str, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete a campaign (soft or hard delete)."""
    if not campaign_id:
        return _response(400, {'error': 'campaignId is required'})
    
    try:
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        
        if hard_delete:
            # Hard delete - remove from DynamoDB
            table.delete_item(Key={'id': campaign_id})
            return _response(200, {'success': True, 'deleted': campaign_id, 'type': 'hard'})
        else:
            # Soft delete - mark as deleted
            now = int(time.time())
            table.update_item(
                Key={'id': campaign_id},
                UpdateExpression='SET #status = :status, deletedAt = :deletedAt, updatedAt = :updatedAt',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'DELETED',
                    ':deletedAt': Decimal(str(now)),
                    ':updatedAt': Decimal(str(now))
                }
            )
            return _response(200, {'success': True, 'deleted': campaign_id, 'type': 'soft'})
    except Exception as e:
        logger.error(f"Delete campaign error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(body: Dict, request_id: str) -> Dict[str, Any]:
    """Clear campaign logs (hard delete multiple campaigns)."""
    try:
        campaign_ids = body.get('campaignIds', [])
        clear_all = body.get('clearAll', False)
        
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        deleted_count = 0
        
        if clear_all:
            # Scan and delete all campaigns with pagination
            scan_kwargs = {'ProjectionExpression': 'id'}
            while True:
                result = table.scan(**scan_kwargs)
                for item in result.get('Items', []):
                    table.delete_item(Key={'id': item['id']})
                    deleted_count += 1
                if 'LastEvaluatedKey' not in result:
                    break
                scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
        elif campaign_ids:
            # Delete specific campaigns
            for cid in campaign_ids:
                try:
                    table.delete_item(Key={'id': cid})
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f'Campaign delete failed for {cid}: {e}')
        else:
            return _response(400, {'error': 'campaignIds or clearAll is required'})
        
        return _response(200, {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Cleared {deleted_count} campaign logs'
        })
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _normalize_campaign(item: Dict) -> Dict:
    """Normalize campaign for response."""
    return {
        'id': item.get('id', ''),
        'campaignId': item.get('campaignId', ''),
        'airtelCampaignId': item.get('airtelCampaignId', ''),
        'campaignName': item.get('campaignName', ''),
        'status': item.get('status', ''),
        'audioUrl': item.get('audioUrl', ''),
        'sheetFileNames': item.get('sheetFileNames', []),
        'contactCount': int(float(item.get('contactCount', 0))),
        'createdAt': int(float(item.get('createdAt', 0))),
        'updatedAt': int(float(item.get('updatedAt', 0))),
    }


def _list_audio_library(params: Dict, request_id: str) -> Dict[str, Any]:
    """List audio files from S3 obd-audio library folder.
    
    Returns all WAV files stored in s3://app.wecare.digital/stack/voice/obd-audio/
    Each file includes: key, name, size, lastModified, publicUrl, downloadUrl, format info
    """
    try:
        files = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_OBD_AUDIO_PREFIX):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key == S3_OBD_AUDIO_PREFIX:
                    continue  # skip folder marker
                name = key.replace(S3_OBD_AUDIO_PREFIX, '')
                if not name:
                    continue
                
                # Read first 44 bytes to parse WAV header for format info
                format_info = {}
                try:
                    head_resp = s3.get_object(Bucket=S3_BUCKET, Key=key, Range='bytes=0-255')
                    head_bytes = head_resp['Body'].read()
                    parsed = _parse_wav_header(head_bytes)
                    if parsed.get('valid'):
                        sr = parsed['sampleRate']
                        ch = parsed['channels']
                        bits = parsed['bitsPerSample']
                        compliant = (parsed['isPCM'] and sr == AIRTEL_SAMPLE_RATE and ch == AIRTEL_CHANNELS and bits == AIRTEL_BITS_PER_SAMPLE)
                        format_info = {
                            'sampleRate': sr,
                            'channels': ch,
                            'bitsPerSample': bits,
                            'isPCM': parsed['isPCM'],
                            'airtelCompliant': compliant,
                            'formatLabel': f"{sr}Hz {bits}bit {'Mono' if ch == 1 else 'Stereo'}",
                        }
                except Exception:
                    pass
                
                public_url = f'https://{S3_BUCKET}/{key}'
                files.append({
                    'key': key,
                    'name': name,
                    'size': obj['Size'],
                    'lastModified': obj['LastModified'].isoformat() if hasattr(obj['LastModified'], 'isoformat') else str(obj['LastModified']),
                    'publicUrl': public_url,
                    'downloadUrl': public_url,
                    **format_info,
                })
        files.sort(key=lambda x: x.get('lastModified', ''), reverse=True)
        return _response(200, {'success': True, 'files': files, 'count': len(files), 'prefix': S3_OBD_AUDIO_PREFIX})
    except Exception as e:
        logger.error(f"List audio library error: {str(e)}")
        return _response(500, {'error': str(e)})


def _upload_to_audio_library(body: Dict, request_id: str) -> Dict[str, Any]:
    """Upload audio file to S3 obd-audio library.
    
    Stores in s3://app.wecare.digital/stack/voice/obd-audio/{fileName}
    Also optionally uploads to Airtel uploadPrompts API.
    
    Request body:
    - audioData: base64-encoded WAV file content (required)
    - fileName: custom filename (optional, default: obd_lib_{timestamp}.wav)
    - uploadToAirtel: whether to also upload to Airtel (default: true)
    """
    try:
        audio_data = body.get('audioData')
        if not audio_data:
            return _response(400, {'error': 'audioData (base64) is required'})
        
        audio_bytes = base64.b64decode(audio_data)
        file_name = body.get('fileName', f'obd_lib_{int(time.time())}.wav')
        # Sanitize filename
        file_name = file_name.replace('/', '_').replace('\\', '_')
        
        # Validate and auto-convert to Airtel spec (16-bit 8kHz Mono PCM WAV)
        conv = _convert_wav_to_airtel_spec(audio_bytes, request_id)
        conversion_report = conv.get('report', '')
        was_converted = conv.get('converted', False)
        if conv.get('error') and not conv.get('compliant'):
            return _response(400, {'error': conv['error'], 'report': conversion_report, 'originalInfo': conv.get('originalInfo')})
        audio_bytes = conv['audioBytes']
        
        s3_key = f'{S3_OBD_AUDIO_PREFIX}{file_name}'
        
        # Store in S3
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=audio_bytes, ContentType='audio/wav')
        
        logger.info(json.dumps({
            'event': 'obd_audio_library_upload',
            'fileName': file_name,
            's3Key': s3_key,
            'sizeBytes': len(audio_bytes),
            'requestId': request_id
        }))
        
        # Optionally upload to Airtel
        airtel_audio_url = ''
        upload_to_airtel = body.get('uploadToAirtel', True)
        if upload_to_airtel:
            secrets = _get_secrets()
            customer_id = secrets.get('customer_id')
            auth_token = secrets.get('audio_upload_auth', secrets.get('upload_auth', ''))
            if customer_id and auth_token:
                try:
                    url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/uploadPrompts?customerId={customer_id}"
                    boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
                    body_parts = [
                        f'--{boundary}'.encode(),
                        f'Content-Disposition: form-data; name="files"; filename="{file_name}"'.encode(),
                        b'Content-Type: audio/wav', b'',
                        audio_bytes,
                        f'--{boundary}--'.encode()
                    ]
                    headers = {
                        'Content-Type': f'multipart/form-data; boundary={boundary}',
                        'Authorization': f'Basic {auth_token}',
                        'requester-id': 'ironman'
                    }
                    req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        result = json.loads(resp.read().decode('utf-8'))
                        airtel_audio_url = _extract_audio_url(result)
                except Exception as upload_err:
                    logger.warning(f"Airtel upload failed (S3 copy saved): {str(upload_err)}")
        
        return _response(200, {
            'success': True,
            'fileName': file_name,
            's3Key': s3_key,
            'publicUrl': f'https://{S3_BUCKET}/{s3_key}',
            'downloadUrl': f'https://{S3_BUCKET}/{s3_key}',
            'airtelAudioUrl': airtel_audio_url,
            'sizeBytes': len(audio_bytes),
            'converted': was_converted,
            'conversionReport': conversion_report,
        })
    except Exception as e:
        logger.error(f"Audio library upload error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_audio_library_file(body: Dict, params: Dict, request_id: str) -> Dict[str, Any]:
    """Delete audio file from S3 obd-audio library."""
    try:
        s3_key = body.get('s3Key') or params.get('s3Key', '')
        if not s3_key or not s3_key.startswith(S3_OBD_AUDIO_PREFIX):
            return _response(400, {'error': 's3Key is required and must be in obd-audio folder'})
        s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        return _response(200, {'success': True, 'deleted': s3_key})
    except Exception as e:
        logger.error(f"Delete audio library file error: {str(e)}")
        return _response(500, {'error': str(e)})


def _store_recording_to_s3(recording_url: str, cdr_id: str, request_id: str) -> str:
    """Download recording from Airtel and store in S3. Returns S3 key or empty string."""
    try:
        if not recording_url:
            return ''
        req = urllib.request.Request(recording_url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
        timestamp = int(time.time())
        s3_key = f"{S3_RECORDING_PREFIX}obd-rec-{timestamp}_{cdr_id}.wav"
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=audio_data, ContentType='audio/wav')
        logger.info(json.dumps({'event': 'obd_recording_stored_s3', 'cdrId': cdr_id, 's3Key': s3_key, 'requestId': request_id}))
        return s3_key
    except Exception as e:
        logger.error(f"Store OBD recording error: {str(e)}")
        return ''


def _is_airtel_cdr_callback(body: Dict) -> bool:
    """
    Detect if a POST payload is an Airtel CDR callback (vs a user OBD API request).

    Airtel OBD CDR callbacks contain fields like Session_ID, Overall_Call_Status,
    participants array, etc. that user campaign creation requests never have.
    """
    # Format B (OBD display format)
    if body.get('Session_ID') or body.get('Client_Correlation_Id'):
        return True
    # Format A (standard camelCase)
    if body.get('vmSessionId') or body.get('clientCorrelationId'):
        return True
    # Either format
    if body.get('overallCallStatus') or body.get('Overall_Call_Status'):
        return True
    if body.get('participants') and isinstance(body.get('participants'), list):
        for p in body['participants']:
            if isinstance(p, dict) and p.get('participantType'):
                return True
    return False


def _handle_cdr_callback(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Handle Airtel CDR callback that was sent to the OBD endpoint.

    Normalizes the payload from Format B (Display_Format) to camelCase,
    then stores it in the VoiceCDR table (same table as /voice-cdr-webhook).
    """
    try:
        # Normalize Format B → Format A
        normalized = _normalize_cdr_payload(body)

        vm_session_id = normalized.get('vmSessionId', '')
        client_correlation_id = normalized.get('clientCorrelationId', '')

        logger.info(json.dumps({
            'event': 'obd_cdr_callback_received',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'callType': normalized.get('callType', ''),
            'overallCallStatus': normalized.get('overallCallStatus', ''),
            'campaignId': normalized.get('campaignId', body.get('Campaign_Id', '')),
            'requestId': request_id
        }))

        current_time = int(time.time())
        ttl_expiry = current_time + (90 * 24 * 60 * 60)

        duration = _safe_ms(normalized.get('duration', 0))
        from_waiting_time = _safe_ms(normalized.get('fromWaitingTime', 0))
        conversation_duration = _safe_ms(normalized.get('conversationDuration', 0))

        # Parse participants
        participants = normalized.get('participants', [])
        caller_name = ''
        destination_name = ''
        caller_status = normalized.get('callerNumberStatus', '')
        dest_status = normalized.get('destinationNumberStatus', '')
        participants_json = ''

        for p in participants:
            p_type = p.get('participantType', '')
            if p_type == 'From':
                caller_name = p.get('participantName', '') or normalized.get('callerName', '')
                if not caller_status:
                    caller_status = p.get('status', '')
            elif p_type == 'To':
                destination_name = p.get('participantName', '') or normalized.get('destinationName', '')
                if not dest_status:
                    dest_status = p.get('status', '')

        try:
            if participants:
                participants_json = json.dumps(participants)
        except (TypeError, ValueError):
            pass

        # Clean up quoted empty strings
        for key in ['callerName', 'destinationName', 'hangupCause']:
            val = normalized.get(key, '')
            if isinstance(val, str) and val.strip() in ('""', "''"):
                normalized[key] = ''

        cdr_record = {
            'id': str(uuid.uuid4()),
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'customerId': normalized.get('customerId', ''),
            'startTime': normalized.get('startTime', 0),
            'endTime': normalized.get('endTime', 0),
            'callAnswerTime': normalized.get('callAnswerTime', 0),
            'timestamp': normalized.get('timestamp', ''),
            'createdAt': current_time,
            'expiresAt': ttl_expiry,
            'durationMs': duration,
            'durationSec': round(duration / 1000, 2) if duration else 0,
            'fromWaitingTimeMs': from_waiting_time,
            'fromWaitingTimeSec': round(from_waiting_time / 1000, 2) if from_waiting_time else 0,
            'conversationDurationMs': conversation_duration,
            'conversationDurationSec': round(conversation_duration / 1000, 2) if conversation_duration else 0,
            'callType': normalized.get('callType', 'OUTBOUND'),
            'overallCallStatus': normalized.get('overallCallStatus', ''),
            'hangupStatus': normalized.get('hangUpStatus', ''),
            'hangupCause': normalized.get('hangupCause', ''),
            'callerId': normalized.get('callerId', ''),
            'callerNumber': normalized.get('callerNumber', ''),
            'destinationNumber': normalized.get('destinationNumber', ''),
            'callerName': caller_name or normalized.get('callerName', ''),
            'destinationName': destination_name or normalized.get('destinationName', ''),
            'callerNumberStatus': caller_status,
            'destinationNumberStatus': dest_status,
            'circleNameCaller': normalized.get('circleNameCaller', ''),
            'circleNameDestination': normalized.get('circleNameDestination', ''),
            'operatorNameCaller': normalized.get('operatorNameCaller', ''),
            'operatorNameDestination': normalized.get('operatorNameDestination', ''),
            'recordingURL': normalized.get('recordingURL', ''),
            'retryCountCaller': _safe_ms(normalized.get('retryCountCaller', 0)),
            'retryCountDestination': _safe_ms(normalized.get('retryCountDestination', 0)),
            'participantsJson': participants_json,
            'participantsCount': len(participants),
            'campaignId': normalized.get('campaignId', body.get('Campaign_Id', '')),
            'campaignName': normalized.get('campaignName', body.get('Campaign_Name', '')),
            'source': 'airtel_obd_cdr_callback',
        }

        # Download and store recording in S3 if available
        recording_url = cdr_record.get('recordingURL', '')
        if recording_url:
            s3_key = _store_recording_to_s3(recording_url, cdr_record['id'], request_id)
            if s3_key:
                cdr_record['s3RecordingKey'] = s3_key
                cdr_record['s3RecordingUrl'] = f"https://{S3_BUCKET}/{s3_key}"

        # Store in VoiceCDR table
        item = {}
        for key, value in cdr_record.items():
            if value is None or value == '':
                continue
            if isinstance(value, (float, int)):
                item[key] = Decimal(str(value))
            else:
                item[key] = value

        table = dynamodb.Table(VOICE_CDR_TABLE)
        table.put_item(Item=item)

        logger.info(json.dumps({
            'event': 'obd_cdr_stored',
            'id': cdr_record['id'],
            'vmSessionId': vm_session_id,
            'requestId': request_id
        }))

        return _response(200, {
            'status': 'ok',
            'vmSessionId': vm_session_id,
            'clientCorrelationId': client_correlation_id,
            'message': 'OBD CDR callback received and stored'
        })

    except Exception as e:
        logger.error(f"OBD CDR callback error: {str(e)}")
        return _response(500, {'error': f'CDR processing error: {str(e)}'})


def _normalize_cdr_payload(payload: Dict) -> Dict:
    """Normalize Airtel CDR from Format B (Display_Format) to camelCase."""
    normalized = dict(payload)
    field_map = {
        'Session_ID': 'vmSessionId',
        'Client_Correlation_Id': 'clientCorrelationId',
        'Overall_Call_Status': 'overallCallStatus',
        'Caller_Number': 'callerNumber',
        'Destination_Number': 'destinationNumber',
        'Caller_ID': 'callerId',
        'Call_Type': 'callType',
        'Caller_Status': 'callerNumberStatus',
        'Destination_Status': 'destinationNumberStatus',
        'Caller_Circle_Name': 'circleNameCaller',
        'Destination_Circle_Name': 'circleNameDestination',
        'Caller_Operator_Name': 'operatorNameCaller',
        'Destination_Operator_Name': 'operatorNameDestination',
        'Hangup_Cause': 'hangupCause',
        'Caller_Retry_Count': 'retryCountCaller',
        'Destination_Retry_Count': 'retryCountDestination',
        'Caller_Name': 'callerName',
        'Destination_Name': 'destinationName',
        'Campaign_Id': 'campaignId',
        'Campaign_Name': 'campaignName',
        'Recording': 'recordingURL',
        'Customer_Name': 'customerId',
        'Destination_CLI': 'displayCliDestination',
    }
    for display_key, camel_key in field_map.items():
        if payload.get(display_key) is not None and not normalized.get(camel_key):
            val = payload[display_key]
            if isinstance(val, str) and val.strip() in ('""', "''", ''):
                val = ''
            normalized[camel_key] = val
    if not normalized.get('callType'):
        normalized['callType'] = payload.get('Call_Type', 'OUTBOUND')
    if not normalized.get('customerId'):
        normalized['customerId'] = payload.get('Customer_Name', payload.get('customerId', ''))
    return normalized


def _safe_ms(val) -> int:
    """Safely convert a value to int. Handles None, strings, and numeric types."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    return 0


def _extract_audio_url(result: Dict) -> str:
    """Extract audio URL from Airtel uploadPrompts response.

    Airtel returns: {"promptResponseList": [{"audioURL": "https://...", "fileName": "...", "fileDisplayName": "..."}]}
    On duplicate: {"errorPromptResponseList": [{"fileName": "...", "message": "File with same name exists"}]}
    Also handles flat response formats as fallback.
    """
    # Primary: promptResponseList[0].audioURL
    prompt_list = result.get('promptResponseList', [])
    if prompt_list and isinstance(prompt_list, list):
        first = prompt_list[0] if prompt_list else {}
        url = first.get('audioURL') or first.get('audioUrl') or first.get('url', '')
        if url:
            return url
    # Handle "File with same name exists" — construct URL from known pattern
    error_list = result.get('errorPromptResponseList', [])
    if error_list and isinstance(error_list, list):
        first = error_list[0] if error_list else {}
        if 'same name exists' in first.get('message', '').lower():
            file_name = first.get('fileName', '')
            if file_name:
                secrets = _get_secrets()
                cid = secrets.get('customer_id', '')
                return f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/assets/audios/{cid}/{file_name}"
    # Fallback: flat response
    return result.get('audioUrl') or result.get('audioURL') or result.get('url') or result.get('promptUrl', '')



def _clean_phone(phone: str) -> str:
    """Clean phone number to 10 digits."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 else ''


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str)
    }
