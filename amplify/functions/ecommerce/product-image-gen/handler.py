"""
Product Image Generator — WECARE.DIGITAL

Auto-generates branded product card images for the Wix Store.
Uses SVG → PNG conversion via Pillow + cairosvg (or pure SVG for Wix).

Wix product image specs:
  - 1:1 square ratio (1000×1000px minimum, 3000×3000 ideal)
  - JPG or PNG
  - Max 8MB

Design approach:
  - Dark gradient background (brand colors)
  - Country flag from flagcdn.com (free, no API key)
  - Country name + visa type
  - WECARE.DIGITAL branding + BNB CLUB ribbon
  - Tagline: "We optimize for approval, not just submission"
  - Price display

Routes:
  POST /generate-product-image   — Generate + upload to S3
  GET  /preview-product-image    — Return SVG preview (no S3 upload)
"""

import os
import json
import logging
import urllib.request
import urllib.error
import base64
from typing import Dict, Any

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

S3_BUCKET = 'app.wecare.digital'
S3_PREFIX = 'store/products'

# Country code → name mapping (ISO 3166-1 alpha-2)
COUNTRIES = {
    'fr': 'France', 'de': 'Germany', 'it': 'Italy', 'es': 'Spain',
    'gb': 'United Kingdom', 'us': 'United States', 'ca': 'Canada',
    'au': 'Australia', 'jp': 'Japan', 'sg': 'Singapore', 'ae': 'UAE',
    'th': 'Thailand', 'my': 'Malaysia', 'tr': 'Turkey', 'gr': 'Greece',
    'pt': 'Portugal', 'nl': 'Netherlands', 'be': 'Belgium', 'at': 'Austria',
    'ch': 'Switzerland', 'se': 'Sweden', 'no': 'Norway', 'dk': 'Denmark',
    'fi': 'Finland', 'ie': 'Ireland', 'nz': 'New Zealand', 'za': 'South Africa',
    'kr': 'South Korea', 'cn': 'China', 'vn': 'Vietnam', 'id': 'Indonesia',
    'ph': 'Philippines', 'lk': 'Sri Lanka', 'np': 'Nepal', 'mm': 'Myanmar',
    'kh': 'Cambodia', 'cz': 'Czech Republic', 'pl': 'Poland', 'hu': 'Hungary',
    'hr': 'Croatia', 'bg': 'Bulgaria', 'ro': 'Romania', 'ee': 'Estonia',
    'lv': 'Latvia', 'lt': 'Lithuania', 'si': 'Slovenia', 'sk': 'Slovakia',
    'mt': 'Malta', 'cy': 'Cyprus', 'is': 'Iceland', 'lu': 'Luxembourg',
    'schengen': 'Schengen Zone',
}

VISA_TYPES = {
    'tourist': {'label': 'TOURIST VISA', 'color': '#00C9A7'},
    'schengen': {'label': 'SCHENGEN VISA', 'color': '#4A90D9'},
    'business': {'label': 'BUSINESS VISA', 'color': '#F5A623'},
    'conference': {'label': 'CONFERENCE VISA', 'color': '#F5A623'},
    'transit': {'label': 'TRANSIT VISA', 'color': '#9B59B6'},
    'student': {'label': 'STUDENT VISA', 'color': '#E74C3C'},
    'work': {'label': 'WORK VISA', 'color': '#E67E22'},
    'medical': {'label': 'MEDICAL VISA', 'color': '#1ABC9C'},
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler."""
    request_id = context.aws_request_id if context else 'local'
    try:
        http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
        path = event.get('path', event.get('rawPath', '/'))
        params = event.get('queryStringParameters', {}) or {}

        if http_method == 'POST' and '/generate-product-image' in path:
            body = json.loads(event.get('body', '{}') or '{}')
            return _generate_and_upload(body, request_id)

        if '/preview-product-image' in path:
            return _preview_svg(params, request_id)

        return _response(404, {'error': 'Not found', 'path': path})
    except Exception as e:
        logger.error(json.dumps({'action': 'image_gen_error', 'error': str(e), 'requestId': request_id}))
        return _response(500, {'error': str(e), 'requestId': request_id})


def _generate_svg(country_code: str, visa_type: str, price: str = '',
                  custom_tagline: str = '', country_name: str = '') -> str:
    """
    Generate a 1000x1000 SVG product card.

    Design:
    - Dark gradient background (#0A1628 → #1A2744)
    - Country flag (circular, centered)
    - Visa type badge with accent color
    - Country name (large)
    - WECARE.DIGITAL branding
    - BNB CLUB ribbon
    - Tagline + price
    """
    cc = country_code.lower()
    vt = visa_type.lower()

    c_name = country_name or COUNTRIES.get(cc, cc.upper())
    v_info = VISA_TYPES.get(vt, {'label': f'{vt.upper()} VISA', 'color': '#00C9A7'})
    v_label = v_info['label']
    v_color = v_info['color']
    tagline = custom_tagline or 'We optimize for approval, not just submission'
    flag_url = f'https://flagcdn.com/w320/{cc}.png' if cc != 'schengen' else ''

    # For Schengen, use EU flag
    if cc == 'schengen':
        flag_url = 'https://flagcdn.com/w320/eu.png'

    price_text = f'From {price}' if price else ''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">
  <defs>
    <!-- Background gradient -->
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0A1628"/>
      <stop offset="50%" style="stop-color:#12203A"/>
      <stop offset="100%" style="stop-color:#1A2744"/>
    </linearGradient>
    <!-- Accent glow -->
    <radialGradient id="glow" cx="50%" cy="45%" r="40%">
      <stop offset="0%" style="stop-color:{v_color};stop-opacity:0.15"/>
      <stop offset="100%" style="stop-color:{v_color};stop-opacity:0"/>
    </radialGradient>
    <!-- Flag circle clip -->
    <clipPath id="flagClip">
      <circle cx="500" cy="380" r="120"/>
    </clipPath>
    <!-- Subtle pattern overlay -->
    <pattern id="dots" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
      <circle cx="15" cy="15" r="0.8" fill="white" opacity="0.05"/>
    </pattern>
  </defs>

  <!-- Background -->
  <rect width="1000" height="1000" fill="url(#bg)"/>
  <rect width="1000" height="1000" fill="url(#dots)"/>
  <rect width="1000" height="1000" fill="url(#glow)"/>

  <!-- Top decorative line -->
  <rect x="0" y="0" width="1000" height="4" fill="{v_color}" opacity="0.8"/>

  <!-- BNB CLUB ribbon (top-right) -->
  <rect x="740" y="40" width="220" height="44" rx="22" fill="{v_color}" opacity="0.9"/>
  <text x="850" y="68" font-family="Arial, Helvetica, sans-serif" font-size="18"
        font-weight="700" fill="white" text-anchor="middle" letter-spacing="2">BNB CLUB</text>

  <!-- WECARE.DIGITAL logo (top-left) -->
  <text x="50" y="70" font-family="Arial, Helvetica, sans-serif" font-size="20"
        font-weight="700" fill="white" opacity="0.9" letter-spacing="1.5">WECARE.DIGITAL</text>

  <!-- Subtle divider -->
  <line x1="50" y1="100" x2="950" y2="100" stroke="white" stroke-opacity="0.08" stroke-width="1"/>

  <!-- Flag circle background -->
  <circle cx="500" cy="380" r="125" fill="white" opacity="0.08"/>
  <circle cx="500" cy="380" r="122" fill="none" stroke="{v_color}" stroke-width="2" opacity="0.4"/>

  <!-- Country flag (circular) -->
  <image href="{flag_url}" x="380" y="310" width="240" height="140"
         clip-path="url(#flagClip)" preserveAspectRatio="xMidYMid slice"/>

  <!-- Visa type badge -->
  <rect x="350" y="530" width="300" height="46" rx="23" fill="{v_color}" opacity="0.2"/>
  <rect x="350" y="530" width="300" height="46" rx="23" fill="none" stroke="{v_color}"
        stroke-width="1.5" opacity="0.6"/>
  <text x="500" y="560" font-family="Arial, Helvetica, sans-serif" font-size="20"
        font-weight="700" fill="{v_color}" text-anchor="middle" letter-spacing="3">{v_label}</text>

  <!-- Country name -->
  <text x="500" y="640" font-family="Arial, Helvetica, sans-serif" font-size="52"
        font-weight="800" fill="white" text-anchor="middle" letter-spacing="2">{c_name.upper()}</text>

  <!-- Tagline -->
  <text x="500" y="710" font-family="Arial, Helvetica, sans-serif" font-size="16"
        fill="white" opacity="0.6" text-anchor="middle" font-style="italic">"{tagline}"</text>

  <!-- Price -->
  <text x="500" y="780" font-family="Arial, Helvetica, sans-serif" font-size="28"
        font-weight="700" fill="{v_color}" text-anchor="middle">{price_text}</text>

  <!-- Bottom bar -->
  <rect x="0" y="920" width="1000" height="80" fill="white" opacity="0.03"/>
  <line x1="0" y1="920" x2="1000" y2="920" stroke="white" stroke-opacity="0.08" stroke-width="1"/>

  <!-- Bottom: WhatsApp + contact -->
  <text x="500" y="958" font-family="Arial, Helvetica, sans-serif" font-size="14"
        fill="white" opacity="0.4" text-anchor="middle">WhatsApp: +91 93309 94400  ·  visa@wecare.digital</text>

  <!-- Bottom accent line -->
  <rect x="0" y="996" width="1000" height="4" fill="{v_color}" opacity="0.8"/>
</svg>'''

    return svg


def _preview_svg(params: dict, request_id: str) -> Dict[str, Any]:
    """Return SVG directly for browser preview."""
    country = params.get('country', 'fr')
    visa_type = params.get('visaType', 'tourist')
    price = params.get('price', '₹2,999')
    tagline = params.get('tagline', '')
    country_name = params.get('countryName', '')

    svg = _generate_svg(country, visa_type, price, tagline, country_name)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'image/svg+xml',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'public, max-age=3600',
        },
        'body': svg,
    }


def _generate_and_upload(body: dict, request_id: str) -> Dict[str, Any]:
    """
    Generate product image and upload to S3.

    Body:
      country: 'fr' (ISO code, required)
      visaType: 'tourist' (required)
      price: '₹2,999' (optional)
      tagline: custom tagline (optional)
      countryName: override country name (optional)
      category: S3 subfolder (default: 'bnb-club')
      productId: if provided, also attaches image to Wix product
    """
    country = body.get('country', '')
    visa_type = body.get('visaType', '')
    if not country or not visa_type:
        return _response(400, {'error': 'Missing country or visaType', 'requestId': request_id})

    price = body.get('price', '')
    tagline = body.get('tagline', '')
    country_name = body.get('countryName', '')
    category = body.get('category', 'bnb-club').strip('/')

    svg = _generate_svg(country, visa_type, price, tagline, country_name)

    # Upload SVG to S3
    file_name = f'{country}-{visa_type}.svg'
    s3_key = f'{S3_PREFIX}/{category}/{file_name}'

    try:
        s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=svg.encode('utf-8'),
            ContentType='image/svg+xml',
            CacheControl='public, max-age=31536000',
        )

        public_url = f'https://{S3_BUCKET}/{s3_key}'

        result = {
            's3Key': s3_key,
            'publicUrl': public_url,
            'fileName': file_name,
            'country': country,
            'visaType': visa_type,
            'uploaded': True,
            'requestId': request_id,
        }

        # Optionally attach to Wix product
        pid = body.get('productId', '')
        if pid:
            try:
                WIX_API_KEY = os.environ.get('WIX_API_KEY', '')
                WIX_SITE_ID = os.environ.get('WIX_SITE_ID', '')
                headers = {
                    'Authorization': WIX_API_KEY,
                    'Content-Type': 'application/json',
                    'wix-site-id': WIX_SITE_ID,
                }
                patch_body = json.dumps({
                    'product': {'media': {'items': [{'image': {'url': public_url}}]}}
                }).encode('utf-8')
                req = urllib.request.Request(
                    f'https://www.wixapis.com/stores/v1/products/{pid}',
                    data=patch_body, headers=headers, method='PATCH'
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    wix_result = json.loads(resp.read().decode('utf-8'))
                result['productAttached'] = True
                result['productId'] = pid
            except Exception as e:
                result['productAttachError'] = str(e)

        return _response(200, result)
    except Exception as e:
        return _response(500, {'error': str(e), 'requestId': request_id})


def _response(status_code: int, body: dict) -> Dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        },
        'body': json.dumps(body, default=str),
    }
