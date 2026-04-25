"""
AI Generate Response Lambda Function

Purpose: Generate AI response using Bedrock for WhatsApp and admin contexts

Architecture:
- INTERNAL: Bedrock Agent (FloatingAgent) for admin tasks - unchanged
  - Agent ID: QIEEHEBTZO / Alias: ASCBD7YPUT / KB: static-faq
- EXTERNAL: Bedrock Converse API (Amazon Nova Lite) for WhatsApp auto-reply
  - Multimodal: text, images, audio, video, documents
  - Conversation history via DynamoDB (per-contact session)
  - Session idle timeout (configurable, default 15 min)
  - Processing lock to prevent duplicate AI calls
  - Bedrock Guardrails integration
  - KB retrieval for grounded answers
  - Intent classification + human escalation
  - Tool use via Converse API toolConfig (KB search, contact lookup, brand info)
  - Message size validation (truncation at configurable limit)

Model: Amazon Nova Pro (amazon.nova-pro-v1:0)
  ~$0.06/1M input tokens, supports multimodal via Converse API

References:
- https://community.aws/content/2m2kHWQAI5z51j706VuZGnJgKEw
- https://aws.amazon.com/blogs/messaging-and-targeting/best-practices-for-building-high-performance-whatsapp-ai-assistant-using-aws/
- https://builder.aws.com/content/2bgPgouKvLhinu8bcE4LZQ1nnwv (intent classification + escalation)
- https://builder.aws.com/content/2cjgSEay78GOI7rfc0gsuMWWHUD (Converse API tool use)
"""

import os
import json
import logging
import boto3
import uuid
import re
import hashlib
import time
from typing import Dict, Any, Tuple, List, Optional
from decimal import Decimal
from botocore.config import Config
from functools import wraps

# Configure logging
from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

logger = get_logger(__name__)

# AWS clients
bedrock_agent_runtime = boto3.client(
    'bedrock-agent-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)
bedrock_runtime = boto3.client(
    'bedrock-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1'),
    config=Config(read_timeout=120, retries={'max_attempts': 2})
)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                             config=Config(read_timeout=60, retries={'max_attempts': 0}))

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
CONVERSATION_TABLE = os.environ.get('CONVERSATION_TABLE', 'stack-wecare-digital-ConversationHistoryTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-WhatsAppInboundTable')

# Internal Agent (FloatingAgent - admin tasks, unchanged)
INTERNAL_AGENT_ID = os.environ.get('INTERNAL_AGENT_ID', '4UUQYFWX64')
INTERNAL_AGENT_ALIAS = os.environ.get('INTERNAL_AGENT_ALIAS', 'TSTALIASID')
INTERNAL_KB_ID = os.environ.get('INTERNAL_KB_ID', 'static-faq')

# External (WhatsApp auto-reply - Converse API)
EXTERNAL_KB_ID = os.environ.get('EXTERNAL_KB_ID', 'static-faq')
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-pro-v1:0')
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', 'DRAFT')

# Conversation limits
MAX_HISTORY_MESSAGES = int(os.environ.get('MAX_HISTORY_MESSAGES', '20'))
MAX_SESSION_MESSAGES = int(os.environ.get('MAX_SESSION_MESSAGES', '50'))
CONVERSATION_TTL_HOURS = int(os.environ.get('CONVERSATION_TTL_HOURS', '24'))
PROCESSING_LOCK_TTL_SECONDS = 90

# Session idle timeout (minutes) - reset conversation if idle too long
SESSION_IDLE_TIMEOUT_MINUTES = int(os.environ.get('SESSION_IDLE_TIMEOUT_MINUTES', '15'))

# Input text size limit - truncate to prevent token abuse
MAX_INPUT_TEXT_LENGTH = int(os.environ.get('MAX_INPUT_TEXT_LENGTH', '2000'))

# Media size limits (bytes) for inline Converse API
MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 4MB
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25MB
MAX_VIDEO_BYTES = 25 * 1024 * 1024  # 25MB
MAX_DOC_BYTES = 5 * 1024 * 1024     # 5MB

# Tool use max iterations to prevent infinite loops
MAX_TOOL_USE_ITERATIONS = 5

# Supported languages for user preference (all regions)
SUPPORTED_LANGUAGES = {
    # Popular (Indian + English + Hinglish)
    'english': 'English', 'en': 'English',
    'hindi': 'Hindi', 'hi': 'Hindi',
    'hinglish': 'Hinglish',
    'bengali': 'Bengali', 'bangla': 'Bengali', 'bn': 'Bengali',
    'tamil': 'Tamil', 'ta': 'Tamil',
    'telugu': 'Telugu', 'te': 'Telugu',
    'gujarati': 'Gujarati', 'gu': 'Gujarati',
    'marathi': 'Marathi', 'mr': 'Marathi',
    'kannada': 'Kannada', 'kn': 'Kannada',
    'malayalam': 'Malayalam', 'ml': 'Malayalam',
    # Asian
    'chinese': 'Chinese', 'zh': 'Chinese', '??': 'Chinese',
    'japanese': 'Japanese', 'ja': 'Japanese', '???': 'Japanese',
    'korean': 'Korean', 'ko': 'Korean', '???': 'Korean',
    'thai': 'Thai', 'th': 'Thai', '???': 'Thai',
    'vietnamese': 'Vietnamese', 'vi': 'Vietnamese',
    'indonesian': 'Indonesian', 'id': 'Indonesian', 'bahasa': 'Indonesian',
    'sinhala': 'Sinhala', 'si': 'Sinhala', 'sinhalese': 'Sinhala',
    # Middle East
    'arabic': 'Arabic', 'ar': 'Arabic', '???????': 'Arabic',
    'turkish': 'Turkish', 'tr': 'Turkish', 'turkce': 'Turkish',
    'russian': 'Russian', 'ru': 'Russian', '???????': 'Russian',
    'urdu': 'Urdu', 'ur': 'Urdu', '????': 'Urdu',
    'punjabi': 'Punjabi', 'pa': 'Punjabi',
    # European
    'french': 'French', 'fr': 'French', 'francais': 'French',
    'spanish': 'Spanish', 'es': 'Spanish', 'espanol': 'Spanish',
    'portuguese': 'Portuguese', 'pt': 'Portuguese', 'portugues': 'Portuguese',
    'italian': 'Italian', 'it': 'Italian', 'italiano': 'Italian',
    'german': 'German', 'de': 'German', 'deutsch': 'German',
    'dutch': 'Dutch', 'nl': 'Dutch', 'nederlands': 'Dutch',
    'polish': 'Polish', 'pl': 'Polish', 'polski': 'Polish',
    'swedish': 'Swedish', 'sv': 'Swedish', 'svenska': 'Swedish',
    'danish': 'Danish', 'da': 'Danish', 'dansk': 'Danish',
    'norwegian': 'Norwegian', 'no': 'Norwegian', 'norsk': 'Norwegian',
    'finnish': 'Finnish', 'fi': 'Finnish', 'suomi': 'Finnish',
    'catalan': 'Catalan', 'ca': 'Catalan', 'catala': 'Catalan',
    'romanian': 'Romanian', 'ro': 'Romanian', 'romana': 'Romanian',
    'malay': 'Malay', 'ms': 'Malay', 'melayu': 'Malay',
    'welsh': 'Welsh', 'cy': 'Welsh', 'cymraeg': 'Welsh',
}

# -- Two-step language picker: Step 1 = Region, Step 2 = Languages --

LANGUAGE_REGION_PICKER = [
    {'id': 'region_popular', 'title': '\u2b50 Popular', 'description': 'English, Hindi, Bengali, Tamil & more'},
    {'id': 'region_asian', 'title': '\U0001f30f Asian', 'description': '\u4e2d\u6587, \u65e5\u672c\u8a9e, \ud55c\uad6d\uc5b4, \u0e44\u0e17\u0e22 & more'},
    {'id': 'region_middle_east', 'title': '\U0001f30d Middle East', 'description': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629, T\u00fcrk\u00e7e, \u0420\u0443\u0441\u0441\u043a\u0438\u0439, \u0627\u0631\u062f\u0648'},
    {'id': 'region_european', 'title': '\U0001f1ea\U0001f1fa European', 'description': 'Fran\u00e7ais, Espa\u00f1ol, Italiano, Deutsch & more'},
]

LANGUAGE_BY_REGION = {
    'region_popular': [
        {'id': 'lang_english', 'title': 'English'},
        {'id': 'lang_hindi', 'title': '?????? / Hindi'},
        {'id': 'lang_hinglish', 'title': 'Hinglish'},
        {'id': 'lang_bengali', 'title': '????? / Bengali'},
        {'id': 'lang_tamil', 'title': '????? / Tamil'},
        {'id': 'lang_telugu', 'title': '?????? / Telugu'},
        {'id': 'lang_gujarati', 'title': '??????? / Gujarati'},
        {'id': 'lang_marathi', 'title': '????? / Marathi'},
        {'id': 'lang_kannada', 'title': '????? / Kannada'},
        {'id': 'lang_malayalam', 'title': '?????? / Malayalam'},
    ],
    'region_asian': [
        {'id': 'lang_chinese', 'title': '???? / Chinese'},
        {'id': 'lang_japanese', 'title': '??? / Japanese'},
        {'id': 'lang_korean', 'title': '??? / Korean'},
        {'id': 'lang_thai', 'title': '??? / Thai'},
        {'id': 'lang_vietnamese', 'title': 'Ti?ng Vi?t / Vietnamese'},
        {'id': 'lang_indonesian', 'title': 'Indonesia / Indonesian'},
        {'id': 'lang_malay', 'title': 'Melayu / Malay'},
        {'id': 'lang_sinhala', 'title': '????? / Sinhala'},
    ],
    'region_middle_east': [
        {'id': 'lang_arabic', 'title': '??????? / Arabic'},
        {'id': 'lang_turkish', 'title': 'Turkce / Turkish'},
        {'id': 'lang_russian', 'title': '??????? / Russian'},
        {'id': 'lang_urdu', 'title': '???? / Urdu'},
        {'id': 'lang_punjabi', 'title': '?????? / Punjabi'},
    ],
    'region_european': [
        {'id': 'lang_french', 'title': 'Francais / French'},
        {'id': 'lang_spanish', 'title': 'Espanol / Spanish'},
        {'id': 'lang_portuguese', 'title': 'Portugues / Portuguese'},
        {'id': 'lang_italian', 'title': 'Italiano / Italian'},
        {'id': 'lang_german', 'title': 'Deutsch / German'},
        {'id': 'lang_dutch', 'title': 'Nederlands / Dutch'},
        {'id': 'lang_polish', 'title': 'Polski / Polish'},
        {'id': 'lang_swedish', 'title': 'Svenska / Swedish'},
        {'id': 'lang_danish', 'title': 'Dansk / Danish'},
        {'id': 'lang_norwegian', 'title': 'Norsk / Norwegian'},
        {'id': 'lang_finnish', 'title': 'Suomi / Finnish'},
        {'id': 'lang_catalan', 'title': 'Catala / Catalan'},
        {'id': 'lang_romanian', 'title': 'Romana / Romanian'},
        {'id': 'lang_welsh', 'title': 'Cymraeg / Welsh'},
    ],
}

# Flat map: lang ID ? language name (built from all regions)
LANGUAGE_ID_MAP = {}
for _region_langs in LANGUAGE_BY_REGION.values():
    for _opt in _region_langs:
        LANGUAGE_ID_MAP[_opt['id']] = _opt['title'].split(' / ')[-1] if ' / ' in _opt['title'] else _opt['title']

LANGUAGE_CONFIRMATIONS = {
    'English': "Language set to English! ?? How can I help you today?",
    'Hindi': "???? ????? ??? ??? ?? ??! ?? ??? ???? ???? ??? ?? ???? ????",
    'Hinglish': "Language Hinglish mein set ho gayi! ?? Kaise help kar sakta hoon?",
    'Bengali': "???? ??????? ??? ??????! ?? ??? ?????? ??????? ???? ?????",
    'Tamil': "???? ??????? ??????????????! ?? ???? ?????? ??? ?????????",
    'Telugu': "??? ???????? ???? ?????????! ?? ???? ??? ????? ????????",
    'Gujarati': "???? ?????????? ??? ??! ?? ??? ???? ???? ??? ??? ?????",
    'Marathi': "???? ?????? ??? ????! ?? ?? ??? ??? ??? ?????",
    'Kannada': "???? ????????? ????????????! ?? ???? ???? ???? ?????????",
    'Malayalam': "??? ?????????? ????????????! ?? ??? ?????? ???????????",
    'Chinese': "????????!?? ???????",
    'Japanese': "??????????????!?? ????????????",
    'Korean': "??? ???? ???????! ?? ??? ???????",
    'Thai': "??????????????????????????! ?? ????????????????",
    'Vietnamese': "Ngon ngu da duoc dat thanh Tieng Viet! \U0001f1fb\U0001f1f3 Toi co the giup gi?",
    'Indonesian': "Bahasa diatur ke Indonesia! ?? Ada yang bisa saya bantu?",
    'Sinhala': "????? ?????? ???? ??! ?? ?? ??? ???? ?? ?????? ??????",
    'Arabic': "?? ????? ????? ??? ???????! ?? ??? ?????? ????????",
    'Turkish': "Dil Turkce olarak ayarlandi! \U0001f1f9\U0001f1f7 Size nasil yardimci olabilirim?",
    'Russian': "???? ?????????? ?? ???????! ?? ??? ???? ???????",
    'Urdu': "???? ???? ??? ??? ?? ???! ?? ??? ?? ?? ???? ??? ?? ???? ????",
    'Punjabi': "????? ?????? ???? ???? ?? ??! ?? ??? ?????? ????? ??? ?? ???? ????",
    'French': "Langue definie sur le francais ! \U0001f1eb\U0001f1f7 Comment puis-je vous aider ?",
    'Spanish': "Idioma configurado en espanol! \U0001f1ea\U0001f1f8 Como puedo ayudarte?",
    'Portuguese': "Idioma definido para portugues! \U0001f1e7\U0001f1f7 Como posso ajudar?",
    'Italian': "Lingua impostata su italiano! \U0001f1ee\U0001f1f9 Come posso aiutarti?",
    'German': "Sprache auf Deutsch eingestellt! \U0001f1e9\U0001f1ea Wie kann ich Ihnen helfen?",
    'Dutch': "Taal ingesteld op Nederlands! \U0001f1f3\U0001f1f1 Hoe kan ik u helpen?",
    'Polish': "Jezyk ustawiony na polski! \U0001f1f5\U0001f1f1 Jak moge pomoc?",
    'Swedish': "Spraket ar installt pa svenska! \U0001f1f8\U0001f1ea Hur kan jag hjalpa dig?",
    'Danish': "Sproget er sat til dansk! \U0001f1e9\U0001f1f0 Hvordan kan jeg hjaelpe?",
    'Norwegian': "Spraket er satt til norsk! \U0001f1f3\U0001f1f4 Hvordan kan jeg hjelpe?",
    'Finnish': "Kieli asetettu suomeksi! \U0001f1eb\U0001f1ee Miten voin auttaa?",
    'Catalan': "Idioma configurat en catala! \U0001f310 Com puc ajudar-te?",
    'Romanian': "Limba setata pe romana! \U0001f1f7\U0001f1f4 Cum va pot ajuta?",
    'Malay': "Bahasa ditetapkan ke Melayu! \U0001f1f2\U0001f1fe Bagaimana saya boleh membantu?",
    'Welsh': "Iaith wedi'i gosod i Gymraeg! \U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f Sut alla i helpu?",
}


# ============================================================================
# WHATSAPP BOT FLOW CONFIG (loaded from SystemConfigTable, dashboard-manageable)
# ============================================================================

DEFAULT_BOT_FLOW = {
    # -- AI & Language Disclaimer (dashboard-manageable) --
    'disclaimer': "?? _This is an AI assistant. Responses are generated on a best-effort basis and may not always be accurate. Language and voice support is provided on a best-effort basis. Please verify important information independently or contact our team at +91 9330994400._",

    # -- Welcome messages --
    'welcome': {
        'text': "Hi there! ?? Welcome to WECARE.DIGITAL\n\nShop, pay, track requests, or get support \u2014 all right here.\n\n?? _You\u2019re chatting with an AI assistant. Responses may not always be accurate. Please verify important details independently._\n\nTap Menu to get started ??",
    },
    'welcomeBack': {
        'text': "Welcome back! ?? What can we help with today? ??",
    },

    # -- Main Menu (10 rows, 2 sections) --
    'mainMenu': {
        'header': 'WECARE.DIGITAL',
        'body': "Pick what you need ??",
        'footer': 'wecare.digital',
        'buttonText': 'Menu',
        'sections': [
            {
                'title': 'Explore',
                'rows': [
                    {'id': 'menu_store', 'title': '?? Store', 'description': 'Shop our brand marketplaces'},
                    {'id': 'menu_self_service', 'title': '?? Self Service', 'description': 'Submit, track & manage requests'},
                    {'id': 'menu_pay', 'title': '?? Pay', 'description': 'Make a payment via WhatsApp'},
                    {'id': 'menu_subscribe', 'title': '?? Subscribe', 'description': 'Sign up with name, email & phone'},
                ]
            },
            {
                'title': 'More',
                'rows': [
                    {'id': 'menu_app', 'title': '?? Download App', 'description': 'Get the WECARE.DIGITAL app'},
                    {'id': 'menu_about', 'title': '?? About Us', 'description': 'Our mission & brands'},
                    {'id': 'menu_audio', 'title': '?? Audio Response', 'description': 'Get replies as voice messages'},
                    {'id': 'menu_language', 'title': '?? Change Language', 'description': 'Choose your response language'},
                    {'id': 'menu_notifications', 'title': '?? Notifications', 'description': 'Manage your alert preferences'},
                    {'id': 'menu_human', 'title': '?? Talk to Human', 'description': 'Connect with a live agent'},
                ]
            }
        ]
    },

    # -- Sub-Menus --
    'subMenus': {
        'menu_store': {
            'header': 'Our Store',
            'body': "Explore our brands & gifting ??",
            'footer': 'wecare.digital/store',
            'buttonText': 'Browse',
            'sections': [
                {
                    'title': 'Brands',
                    'rows': [
                        {'id': 'store_bnb_club', 'title': '?? BNB Club', 'description': 'Travel, visas, corporate & FIT'},
                        {'id': 'store_no_fault', 'title': '?? No Fault', 'description': 'Faster online dispute resolution'},
                        {'id': 'store_expo_week', 'title': '?? Expo Week', 'description': 'Virtual fairs & digital events'},
                        {'id': 'store_ritual_guru', 'title': '?? Ritual Guru', 'description': 'Puja kits & step-by-step guides'},
                        {'id': 'store_legal_champ', 'title': '?? Legal Champ', 'description': 'Business docs & registrations'},
                        {'id': 'store_swdhya', 'title': '\U0001f9d8 Swdhya', 'description': 'Samvad - self-inquiry chats'},
                    ]
                },
                {
                    'title': 'Gifting',
                    'rows': [
                        {'id': 'store_gift_card', 'title': '?? Gift Card', 'description': 'Send a WECARE.DIGITAL gift card'},
                        {'id': 'menu_back', 'title': '?? Back to Menu', 'description': 'Return to main menu'},
                    ]
                }
            ]
        },
        'menu_self_service': {
            'header': 'Self Service',
            'body': "What do you need help with? ??",
            'footer': 'wecare.digital/selfservice',
            'buttonText': 'Options',
            'sections': [
                {
                    'title': 'Requests',
                    'rows': [
                        {'id': 'menu_submit_request', 'title': '?? Submit a Request', 'description': 'Start a new service request'},
                        {'id': 'menu_amend_request', 'title': '?? Amend a Request', 'description': 'Modify a previous request'},
                        {'id': 'menu_track_request', 'title': '?? Track a Request', 'description': 'Check your request status'},
                    ]
                },
                {
                    'title': 'Services',
                    'rows': [
                        {'id': 'menu_rx_slot', 'title': '??? RX Slot', 'description': 'Schedule a medical appointment'},
                        {'id': 'menu_drop_docs', 'title': '?? Drop Docs', 'description': 'Upload supporting documents'},
                        {'id': 'menu_hours', 'title': '? Business Hours', 'description': 'When we are available'},
                        {'id': 'menu_enterprise', 'title': '?? Enterprise Assist', 'description': 'Business & technical support'},
                        {'id': 'menu_back', 'title': '?? Back to Menu', 'description': 'Return to main menu'},
                    ]
                }
            ]
        },
    },

    # -- Menu Responses --
    'menuResponses': {
        # Sub-menu openers
        'menu_store': {
            'text': '',
            'action': 'show_sub_menu',
        },
        'menu_self_service': {
            'text': '',
            'action': 'show_sub_menu',
        },
        # Conversational flows
        'menu_pay': {
            'text': '',
            'action': 'start_pay_flow',
        },
        'menu_subscribe': {
            'text': '',
            'action': 'start_subscribe_flow',
        },
        # Toggles
        'menu_audio': {
            'text': '',
            'action': 'toggle_audio',
        },
        'menu_notifications': {
            'text': '',
            'action': 'toggle_notifications',
        },
        # Human handoff
        'menu_human': {
            'text': "?? Connecting you with a live agent... A team member will be with you shortly. ??",
            'action': 'human_handoff',
        },
        # Back to main menu (from sub-menus)
        'menu_back': {
            'text': '',
            'action': 'show_main_menu',
        },
        # Language picker
        'menu_language': {
            'text': '',
            'action': 'show_language_picker',
        },
        # Self-service items
        'menu_submit_request': {
            'text': "\U0001f4cb *Submit a Request*\n\nSubmit a request - it\u2019s quick and easy. We\u2019ll review and keep you posted. \U0001f4e8",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_amend_request': {
            'text': "?? *Amend a Request*\n\nNeed to modify a previous request? Update it anytime, subject to terms and approval. ???",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_track_request': {
            'text': "\U0001f50d *Track a Request*\n\nCheck your request status - see when it\u2019s received, reviewed, or completed. \U0001f4cb",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_rx_slot': {
            'text': "??? *RX Slot*\n\nSchedule a medical appointment for your MEd Tour package via BNB Club. ??",
            'cta': {'text': 'Book Slot', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_drop_docs': {
            'text': "?? *Drop Docs*\n\nUpload supporting documents directly to your request. All uploads are secure. ??",
            'cta': {'text': 'Upload Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_enterprise': {
            'text': "?? *Enterprise Support*\n\nFor technical or business inquiries, our enterprise team is here. ??",
            'cta': {'text': 'Get Support', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_hours': {
            'text': "\u23f0 *Business Hours*\n\nMon-Fri, 9 AM - 6 PM (IST). Our 24/7 self-service portal is always open. \U0001f310",
            'cta': {'text': 'Self Service', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_app': {
            'text': "\U0001f4f1 *Download the App*\n\nManage services on the go - iOS and Android. Track, schedule, and more. \U0001f680",
            'cta': {'text': 'GET APP', 'url': 'https://wecare.digital/one'},
        },
        'menu_about': {
            'text': "\U0001f30d *About Us*\n\nWECARE.DIGITAL creates helpful products for everyday life - with you at the heart.\n\nOur brands: BNB Club, Expo Week, Legal Champ, No-Fault, Ritual Guru, and Swdhya.",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital'},
        },
        # Store brand responses
        'store_bnb_club': {
            'text': "\U0001f30d *BNB Club - Travel*\n\nYour travel club for visas, corporate travel, FIT packages, and itinerary planning. \u2708\ufe0f",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/bnbclub'},
        },
        'store_no_fault': {
            'text': "\u2696\ufe0f *No Fault - ODR*\n\nFaster, lower-cost online dispute resolution. Fair, transparent, efficient. \U0001f4bc",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/nofault'},
        },
        'store_expo_week': {
            'text': "\U0001f3aa *Expo Week - Digital Events*\n\nVirtual travel fairs, exclusive offers, and sustainable discovery. \U0001f30d",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/expoweek'},
        },
        'store_ritual_guru': {
            'text': "\U0001f54c *Ritual Guru - Culture*\n\nTemple-grade puja kits with step-by-step guides. Global delivery. \U0001f4e6",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/ritualguru'},
        },
        'store_legal_champ': {
            'text': "\U0001f4dc *Legal Champ - Documentation*\n\nBusiness docs, registrations, and compliance made simple. \u2705",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/legalchamp'},
        },
        'store_swdhya': {
            'text': "\U0001f9d8 *Swdhya - Samvad*\n\nSelf-inquiry conversations for clarity and action. \U0001f4ac",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/swdhya'},
        },
        'store_gift_card': {
            'text': "?? *Gift Card*\n\nGive the gift of choice! Redeemable across all WECARE.DIGITAL brands. ??",
            'cta': {'text': 'Get Gift Card', 'url': 'https://www.wecare.digital/gift-card'},
        },
    },

    # -- Conversational flow prompts --
    'flows': {
        'subscribe': {
            'step_name': "?? Let\u2019s get you signed up! What\u2019s your full name?",
            'step_email': "Nice, {name}! Your email address? ??",
            'step_phone': "Got it! Last one - phone number with country code? \U0001f4f1",
            'done': "You\u2019re all set, {name}! ? Welcome aboard. ??",
            'invalid_email': "Hmm, that doesn\u2019t look like a valid email. Try again? ??",
            'invalid_phone': "That doesn\u2019t look right. Enter phone with country code (e.g. +91 98765 43210) ??",
        },
        'pay': {
            'step_amount': "?? Enter unit price (?) (numbers only)\nExample: 500",
            'step_quantity': "?? Enter quantity / units (type 1 for single)\nExample: 2",
            'invalid_amount': "?? Please enter a valid number between 1 and 100000.",
            'invalid_quantity': "?? Please enter a valid quantity between 1 and 999.",
            'sending': "Processing payment of ?{amount}... ?",
            'default_item_name': 'Services/Goods',
            'default_gst_rate': 18,
            'default_shipping': 49,
            'default_promo': 15,
            'gstin': '19AADFW7431N1ZK',
        },
    },

    # -- Toggle messages --
    'toggles': {
        'audio_on': "?? Audio replies enabled! You\u2019ll now receive voice messages too. ??\n\n_Voice is generated by AI on a best-effort basis. Some languages may use an approximate voice._",
        'audio_off': "?? Audio replies disabled. Text only from now. ??",
        'audio_prompt': "?? Audio replies are {status}. Reply ON to hear responses in your language, or OFF for text only.\n\n_Voice is AI-generated on a best-effort basis._",
        'notifications_on': "?? Notifications enabled! You\u2019ll receive updates and alerts. ??",
        'notifications_off': "?? Notifications turned off. Re-enable anytime from the menu.",
        'notifications_prompt': "?? Notifications are {status}. Reply ON to receive updates, or OFF to stop.",
    },

    # -- Options menu (after any action) --
    'options': {
        'header': "What\u2019s next?",
        'body': "Pick an option below ??",
        'footer': 'wecare.digital',
        'buttonText': 'Next',
        'sections': [
            {
                'title': 'Choose',
                'rows': [
                    {'id': 'opt_do_more', 'title': '?? Do more', 'description': 'Back to the main menu'},
                    {'id': 'opt_done', 'title': '?? Done here', 'description': 'All finished for now'},
                ]
            }
        ]
    },
    'doMore': {
        'text': "Let\u2019s go! ?? Pick what\u2019s next ??",
    },
    'done': {
        'text': "All done? You crushed it. ?? Catch you later! ??",
    },

    # -- Rating --
    'rating': {
        'header': 'Quick feedback',
        'body': "How was your experience? ??",
        'footer': 'wecare.digital',
        'buttonText': 'Rate',
        'sections': [
            {
                'title': 'How was it?',
                'rows': [
                    {'id': 'rate_good', 'title': 'Vibes immaculate ??', 'description': 'Great experience'},
                    {'id': 'rate_ok', 'title': '?? Just okay', 'description': 'It was fine'},
                    {'id': 'rate_mid', 'title': 'Kinda mid ??', 'description': 'Could be better'},
                ]
            }
        ]
    },
    'ratingResponses': {
        'rate_good': "Thanks for vibin\u2019 with us! ??",
        'rate_ok': "Appreciate the honesty! We\u2019ll keep improving. ??",
        'rate_mid': "Bet - glow-up in progress \U0001f4aa",
    },
    'errorMsg': "Whoops! That didn\u2019t register. Try picking from the menu. ??",
}


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are WECARE.DIGITAL's friendly AI assistant on WhatsApp.

IMPORTANT DISCLAIMER:
- You are an AI assistant. Your responses are generated on a best-effort basis and may contain errors.
- Language support is provided on a best-effort basis. Some languages may use approximate translations.
- Voice/audio responses use text-to-speech and may not perfectly match all languages.
- For critical matters (legal, medical, financial), always advise the user to verify with the team directly.
- Never present AI-generated information as guaranteed fact for legal, medical, or financial topics.

RULES:
- If the user has set a preferred language, ALWAYS respond in that language
- Otherwise, detect the user's language from their message and respond in that same language
- If the user asks to change language (e.g. "speak in Hindi", "language bengali"), use the set_language tool
- Keep responses SHORT (2-4 sentences max) - this is WhatsApp, not email
- Use 1-2 emojis for warmth
- If the user sends an image, describe what you see and ask how you can help
- If the user sends a voice note or audio, respond to the transcribed/understood content
- If the user sends a video, describe the key content and respond helpfully
- If the user sends a document, summarize key points and ask what they need
- Always mention the specific brand name when relevant
- End with a clear action (website, phone, or next step) when appropriate
- For pricing, legal terms, or medical info, add: "Please verify this with our team for confirmation."

BRANDS:
- Travel/Hotels/Visa \u2192 BNB Club (bnbclub.in)
- Documents/Registration/GST \u2192 Legal Champ (legalchamp.in)
- Disputes/Complaints \u2192 No Fault (nofault.in)
- Puja/Rituals \u2192 Ritual Guru (ritualguru.in)
- Self-inquiry/Reflection \u2192 Swdhya (swdhya.in)

CONTACT: +91 9330994400 | one@wecare.digital

If you don't know the answer, say so honestly and suggest contacting the team directly.

TOOLS AVAILABLE:
- search_knowledge_base: Use when you need factual info about services, pricing, policies
- lookup_contact: Use to personalize responses with the customer's name/history
- get_brand_info: Use to get detailed brand info (website, services, contact)
- set_language: Use when the user wants to change their response language
Use tools proactively when the customer asks about specific services or brands."""


# ============================================================================
# TOOL DEFINITIONS (Converse API toolConfig for autonomous tool use)
# ============================================================================

TOOL_DEFINITIONS = [
    {
        'toolSpec': {
            'name': 'search_knowledge_base',
            'description': 'Search the WECARE.DIGITAL knowledge base for information about brands, services, pricing, policies, FAQs. Use when the customer asks a question you need factual data to answer.',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'The search query to find relevant information'
                        }
                    },
                    'required': ['query']
                }
            }
        }
    },
    {
        'toolSpec': {
            'name': 'lookup_contact',
            'description': 'Look up a customer contact record by phone number to get their name, previous interactions, and account details. Use when you need to personalize the response or check customer history.',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'phone': {
                            'type': 'string',
                            'description': 'Customer phone number (with country code)'
                        }
                    },
                    'required': ['phone']
                }
            }
        }
    },
    {
        'toolSpec': {
            'name': 'get_brand_info',
            'description': 'Get detailed information about a specific WECARE.DIGITAL brand including services, pricing, contact details, and website. Brands: BNB Club, Legal Champ, No Fault, Ritual Guru, Swdhya.',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'brand_name': {
                            'type': 'string',
                            'description': 'Brand name: BNB Club, Legal Champ, No Fault, Ritual Guru, or Swdhya'
                        }
                    },
                    'required': ['brand_name']
                }
            }
        }
    },
    {
        'toolSpec': {
            'name': 'set_language',
            'description': 'Set the user\'s preferred response language. Use when the user asks to change language, e.g. "speak in Hindi", "reply in Bengali", "change language". Available: English, Hindi, Bengali, Tamil, Telugu, Gujarati, Marathi, Hinglish, Kannada, Malayalam.',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'language': {
                            'type': 'string',
                            'description': 'Language name: English, Hindi, Bengali, Tamil, Telugu, Gujarati, Marathi, Hinglish, Kannada, or Malayalam'
                        }
                    },
                    'required': ['language']
                }
            }
        }
    },
]

# Intent classification prompt (lightweight, used before main Converse call)
INTENT_CLASSIFICATION_PROMPT = """Classify the customer's WhatsApp message intent. Return ONLY a JSON object.

Categories:
- general_inquiry: Questions about services, pricing, brands
- support_request: Need help with an existing service/order
- complaint: Unhappy, frustrated, wants resolution
- urgent: Emergency, legal deadline, time-sensitive
- greeting: Hello, hi, good morning
- media_share: Shared image/video/document without clear question
- out_of_scope: Unrelated to WECARE.DIGITAL services
- escalate: Explicitly asks for human/manager/supervisor

Return JSON: {"intent": "<category>", "escalate": true/false, "confidence": 0.0-1.0}

Rules for escalate=true:
- complaint with strong negative sentiment
- urgent with deadline mention
- explicitly asks for human agent
- you cannot confidently answer (confidence < 0.5)
- repeated question (user seems stuck)"""


# ============================================================================
# MAIN HANDLER
# ============================================================================

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Generate AI response - routes to internal agent or external Converse API."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)

    headers = cors_headers(origin)
    headers['Access-Control-Allow-Methods'] = 'POST,OPTIONS'

    # Handle OPTIONS preflight
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')
    if http_method == 'OPTIONS':
        return options_response(origin)

    # Parse body
    body = event
    if 'body' in event:
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except (json.JSONDecodeError, TypeError):
            body = event

    agent_context = body.get('context', 'external')

    logger.info(json.dumps({
        'event': 'ai_generate_start',
        'sendMode': SEND_MODE,
        'agentContext': agent_context,
        'requestId': request_id
    }))

    if SEND_MODE == 'DRY_RUN':
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': '', 'mode': 'DRY_RUN'})}

    try:
        # -- INTERNAL (admin) path - uses Bedrock Converse API with tool use --
        if agent_context == 'internal-admin':
            return _handle_internal(body, headers, request_id)

        # -- EXTERNAL (WhatsApp) path - DISABLED --
        # WhatsApp AI auto-reply has been removed. Only the FloatingAgent
        # (internal-admin) uses this Lambda. Return empty response.
        logger.info(json.dumps({
            'event': 'external_path_disabled',
            'requestId': request_id
        }))
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'suggestedResponse': '',
                'disabled': True,
                'reason': 'WhatsApp AI auto-reply is disabled'
            })
        }

    except Exception as e:
        logger.error(json.dumps({'event': 'ai_generate_error', 'error': str(e), 'errorType': type(e).__name__, 'requestId': request_id, 'context': agent_context}))
        import traceback
        logger.error(f"TRACEBACK: {traceback.format_exc()}")
        
        fallback_msg = "Sorry, I encountered an error. Please try again or contact support."
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'suggestedResponse': fallback_msg, 'error': str(e)})
        }


# ============================================================================
# INTERNAL PATH (FloatingAgent - Converse API with tool use for admin tasks)
# ============================================================================

def _handle_internal(body: Dict, headers: Dict, request_id: str) -> Dict:
    """
    Internal admin path using Bedrock Converse API with tool use.
    Supports dynamic task execution via function calling.
    """
    message_content = body.get('messageContent', '')
    message_id = body.get('messageId', '')
    contact_id = body.get('contactId', '')
    session_id = body.get('sessionId', f'internal-{request_id}')
    temperature = float(body.get('temperature', 0.7))
    max_tokens = int(body.get('maxTokens', 2048))

    logger.info(json.dumps({
        'event': 'internal_agent_called',
        'messageContent': message_content[:100],
        'sessionId': session_id,
        'requestId': request_id
    }))

    if not message_content:
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': 'How can I help you today?'})}

    # Truncate if too long
    if len(message_content) > MAX_INPUT_TEXT_LENGTH:
        message_content = message_content[:MAX_INPUT_TEXT_LENGTH]

    try:
        # Get or create conversation history for internal agent
        conversation_table = dynamodb.Table(CONVERSATION_TABLE)
        history_key = f'internal-{session_id}'
        
        try:
            # Query by phoneHash (partition key) to get latest conversation
            phone_hash = f'internal-{session_id}'
            history_response = conversation_table.query(
                KeyConditionExpression='phoneHash = :ph',
                ExpressionAttributeValues={':ph': phone_hash},
                ScanIndexForward=False,  # Get latest first
                Limit=1
            )
            items = history_response.get('Items', [])
            history_item = items[0] if items else {}
            conversation_history = history_item.get('messages', [])
            
            # Check session idle timeout
            last_updated = history_item.get('lastUpdated', 0)
            if last_updated and (time.time() - float(last_updated)) > (SESSION_IDLE_TIMEOUT_MINUTES * 60):
                logger.info(json.dumps({'event': 'internal_session_timeout', 'sessionId': session_id}))
                conversation_history = []
        except Exception:
            conversation_history = []

        # Add user message to history
        conversation_history.append({
            'role': 'user',
            'content': [{'text': message_content}]
        })

        # Keep only recent messages
        if len(conversation_history) > MAX_HISTORY_MESSAGES:
            conversation_history = conversation_history[-MAX_HISTORY_MESSAGES:]

        # System prompt for internal admin agent
        system_prompts = [{
            'text': '''You are WECARE.DIGITAL's internal CRM assistant. You execute tasks using your tools.

YOU HAVE THESE TOOLS - USE THEM, never say you can't do something if a tool exists for it:
- search_contacts, create_contact, update_contact, add_contact_email
- send_whatsapp, send_whatsapp_buttons, send_whatsapp_list, send_whatsapp_pay
- send_whatsapp_flow, list_submit_requests
- make_voice_call, send_sms, send_email
- get_messages, get_stats
- schedule_message, list_scheduled_messages
- list_templates, send_template
- delete_contact, delete_messages, delete_media_files, list_media_files, clear_all_contact_data
- get_voice_cdr, get_billing_summary, get_invoice_list, create_invoice
- get_wix_products, get_wix_orders

RULES:
- ALWAYS use your tools to execute tasks. Never explain how to do something manually.
- Keep responses ULTRA SHORT. 1 sentence max. No greetings, no filler, no offers to help further.
- Never include <thinking> tags in responses.
- Be proactive: "send message to Jignesh" -> search first, then send.
- For payment requests, use send_whatsapp_pay tool directly.
- For submit request flows, use send_whatsapp_flow tool.
- Do the task, confirm briefly. Example: "Sent message to Jignesh." or "Found 2 contacts matching 'amen'."
- If user just says hi/hello, reply only: "Ready. What do you need?"
- When a tool returns an error, report it clearly. Do not retry with the same bad input.
- contactId must always be a UUID. If you only have a name, search_contacts first to get the UUID.'''
        }]

        # Define tools for internal agent - COMPREHENSIVE STACK CRM CAPABILITIES
        tools = [
            # ===== CONTACT MANAGEMENT =====
            {
                'toolSpec': {
                    'name': 'search_contacts',
                    'description': 'Search for contacts by name, phone number, or email. Use this when user mentions a contact name or wants to find someone.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'query': {
                                    'type': 'string',
                                    'description': 'Name, phone number, or email to search for'
                                }
                            },
                            'required': ['query']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'create_contact',
                    'description': 'Create a new contact in the CRM.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string', 'description': 'Contact name'},
                                'phone': {'type': 'string', 'description': 'Phone number with country code'},
                                'email': {'type': 'string', 'description': 'Email address'}
                            },
                            'required': ['name']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'update_contact',
                    'description': 'Update an existing contact details.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID to update'},
                                'name': {'type': 'string', 'description': 'New name'},
                                'phone': {'type': 'string', 'description': 'New phone'},
                                'email': {'type': 'string', 'description': 'New email'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            
            # ===== WHATSAPP MESSAGING =====
            {
                'toolSpec': {
                    'name': 'send_whatsapp',
                    'description': 'Send a simple WhatsApp text message to a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'message': {'type': 'string', 'description': 'Message text'}
                            },
                            'required': ['contactId', 'message']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'send_whatsapp_buttons',
                    'description': 'Send WhatsApp message with interactive buttons (up to 3 buttons).',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'bodyText': {'type': 'string', 'description': 'Main message text'},
                                'buttons': {
                                    'type': 'array',
                                    'description': 'Array of button objects with id and title',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'id': {'type': 'string'},
                                            'title': {'type': 'string'}
                                        }
                                    }
                                },
                                'headerText': {'type': 'string', 'description': 'Optional header text'},
                                'footerText': {'type': 'string', 'description': 'Optional footer text'}
                            },
                            'required': ['contactId', 'bodyText', 'buttons']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'send_whatsapp_list',
                    'description': 'Send WhatsApp message with interactive list menu.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'bodyText': {'type': 'string', 'description': 'Main message text'},
                                'buttonText': {'type': 'string', 'description': 'Button text to open list'},
                                'sections': {
                                    'type': 'array',
                                    'description': 'List sections with rows',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'title': {'type': 'string'},
                                            'rows': {'type': 'array'}
                                        }
                                    }
                                }
                            },
                            'required': ['contactId', 'bodyText', 'buttonText', 'sections']
                        }
                    }
                }
            },
            
            # ===== WHATSAPP PAY =====
            {
                'toolSpec': {
                    'name': 'send_whatsapp_pay',
                    'description': 'Send a WhatsApp Pay interactive payment request to a contact. Creates a payment link message.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'amount': {'type': 'number', 'description': 'Payment amount in INR'},
                                'description': {'type': 'string', 'description': 'Payment description (e.g. "Invoice #123")'},
                                'currency': {'type': 'string', 'description': 'Currency code (default: INR)'},
                                'expiryMinutes': {'type': 'number', 'description': 'Payment link expiry in minutes (default: 60)'},
                                'referenceId': {'type': 'string', 'description': 'Optional reference/invoice ID'}
                            },
                            'required': ['contactId', 'amount', 'description']
                        }
                    }
                }
            },
            # ===== VOICE & SMS =====
            {
                'toolSpec': {
                    'name': 'make_voice_call',
                    'description': 'Make a voice call using Airtel C2C with pre-recorded message or TTS.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID to call'},
                                'message': {'type': 'string', 'description': 'Text message for TTS (text-to-speech)'},
                                'audioUrl': {'type': 'string', 'description': 'URL of pre-recorded audio file'},
                                'language': {'type': 'string', 'description': 'Language code for TTS (en, hi, etc)'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'send_sms',
                    'description': 'Send SMS message to a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'message': {'type': 'string', 'description': 'SMS text'}
                            },
                            'required': ['contactId', 'message']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'send_email',
                    'description': 'Send email to a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'subject': {'type': 'string', 'description': 'Email subject'},
                                'message': {'type': 'string', 'description': 'Email body'}
                            },
                            'required': ['contactId', 'subject', 'message']
                        }
                    }
                }
            },
            
            # ===== MESSAGE HISTORY & ANALYTICS =====
            {
                'toolSpec': {
                    'name': 'get_messages',
                    'description': 'Get message history for a contact. Shows recent messages sent to/from the contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'limit': {'type': 'number', 'description': 'Number of messages (default 10)'},
                                'direction': {'type': 'string', 'description': 'Filter by direction: inbound, outbound, or all'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'get_stats',
                    'description': 'Get dashboard statistics including total contacts, messages, and today\'s activity.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'period': {'type': 'string', 'description': 'Time period: today, week, month, all'}
                            }
                        }
                    }
                }
            },
            
            # ===== SCHEDULED MESSAGES =====
            {
                'toolSpec': {
                    'name': 'schedule_message',
                    'description': 'Schedule a message to be sent at a specific time.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'message': {'type': 'string', 'description': 'Message text'},
                                'scheduledTime': {'type': 'string', 'description': 'ISO timestamp when to send'},
                                'channel': {'type': 'string', 'description': 'Channel: whatsapp, sms, email'}
                            },
                            'required': ['contactId', 'message', 'scheduledTime', 'channel']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'list_scheduled_messages',
                    'description': 'List all scheduled messages that haven\'t been sent yet.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Optional: filter by contact ID'}
                            }
                        }
                    }
                }
            },
            
            # ===== TEMPLATES =====
            {
                'toolSpec': {
                    'name': 'list_templates',
                    'description': 'List available WhatsApp message templates.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'status': {'type': 'string', 'description': 'Filter by status: APPROVED, PENDING, REJECTED'}
                            }
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'send_template',
                    'description': 'Send a WhatsApp template message to a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'templateName': {'type': 'string', 'description': 'Template name'},
                                'parameters': {
                                    'type': 'array',
                                    'description': 'Template parameter values',
                                    'items': {'type': 'string'}
                                }
                            },
                            'required': ['contactId', 'templateName']
                        }
                    }
                }
            },
            
            # ===== DATA MANAGEMENT & CLEANUP =====
            {
                'toolSpec': {
                    'name': 'add_contact_email',
                    'description': 'Add or update email address for a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'email': {'type': 'string', 'description': 'Email address to add'}
                            },
                            'required': ['contactId', 'email']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'delete_contact',
                    'description': 'Soft delete a contact (marks as deleted, doesn\'t remove data).',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID to delete'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'delete_messages',
                    'description': 'Delete specific messages or all messages for a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'messageIds': {
                                    'type': 'array',
                                    'description': 'Specific message IDs to delete (optional, if not provided deletes all)',
                                    'items': {'type': 'string'}
                                },
                                'direction': {'type': 'string', 'description': 'Filter by direction: inbound, outbound, or all'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'delete_media_files',
                    'description': 'Delete media files (images, videos, documents) from S3 for a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'fileKeys': {
                                    'type': 'array',
                                    'description': 'Specific S3 keys to delete (optional, if not provided deletes all for contact)',
                                    'items': {'type': 'string'}
                                }
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'clear_all_contact_data',
                    'description': 'DANGEROUS: Completely clear ALL data for a contact including messages, media files, and conversation history. Use with caution!',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'confirm': {'type': 'boolean', 'description': 'Must be true to confirm deletion'}
                            },
                            'required': ['contactId', 'confirm']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'list_media_files',
                    'description': 'List all media files stored in S3 for a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'fileType': {'type': 'string', 'description': 'Filter by type: image, video, audio, document, or all'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            
            # ===== VOICE CDR & ANALYTICS =====
            {
                'toolSpec': {
                    'name': 'get_voice_cdr',
                    'description': 'Get voice call detail records (CDR). Shows call history with duration, status, and caller info.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'callType': {'type': 'string', 'description': 'INBOUND or OUTBOUND'},
                                'status': {'type': 'string', 'description': 'Answered, Missed, Busy, Disconnected'},
                                'limit': {'type': 'number', 'description': 'Number of records (default 20)'},
                                'callerNumber': {'type': 'string', 'description': 'Filter by caller phone'}
                            }
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'get_billing_summary',
                    'description': 'Get AWS billing summary including costs by service, total spend, and comparison with previous month.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'month': {'type': 'number', 'description': '0 for current month, -1 for last month, etc.'}
                            }
                        }
                    }
                }
            },
            
            # ===== INVOICING =====
            {
                'toolSpec': {
                    'name': 'get_invoice_list',
                    'description': 'List invoices. Can filter by contact or status.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Filter by contact ID'},
                                'status': {'type': 'string', 'description': 'Filter by status: draft, sent, paid, overdue'},
                                'limit': {'type': 'number', 'description': 'Number of invoices (default 20)'}
                            }
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'create_invoice',
                    'description': 'Create a new invoice for a contact.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'items': {
                                    'type': 'array',
                                    'description': 'Invoice line items with description and amount',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'description': {'type': 'string'},
                                            'amount': {'type': 'number'},
                                            'quantity': {'type': 'number'}
                                        }
                                    }
                                },
                                'currency': {'type': 'string', 'description': 'Currency code (default: INR)'},
                                'dueDate': {'type': 'string', 'description': 'Due date in ISO format'},
                                'notes': {'type': 'string', 'description': 'Additional notes'}
                            },
                            'required': ['contactId', 'items']
                        }
                    }
                }
            },
            
            # ===== ECOMMERCE (WIX STORE) =====
            {
                'toolSpec': {
                    'name': 'get_wix_products',
                    'description': 'List products from the Wix online store.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string', 'description': 'Search query for product name'},
                                'limit': {'type': 'number', 'description': 'Number of products (default 20)'}
                            }
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'get_wix_orders',
                    'description': 'List orders from the Wix online store.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'status': {'type': 'string', 'description': 'Filter by status: APPROVED, FULFILLED, CANCELLED'},
                                'limit': {'type': 'number', 'description': 'Number of orders (default 20)'}
                            }
                        }
                    }
                }
            },
            
            # ===== WHATSAPP FLOWS =====
            {
                'toolSpec': {
                    'name': 'send_whatsapp_flow',
                    'description': 'Send a WhatsApp Flow (like Submit Request form) to a contact. The flow opens an interactive form in WhatsApp.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Contact ID'},
                                'flowType': {'type': 'string', 'description': 'Flow type: submit_request (default)'}
                            },
                            'required': ['contactId']
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'list_submit_requests',
                    'description': 'List WhatsApp Flow submissions (submit requests). Can filter by contact or status.',
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'contactId': {'type': 'string', 'description': 'Filter by contact ID'},
                                'status': {'type': 'string', 'description': 'Filter by status: pending, approved, rejected, completed'},
                                'limit': {'type': 'number', 'description': 'Number of results (default 20)'}
                            }
                        }
                    }
                }
            }
        ]
        suggestion = _internal_converse_with_tools(
            conversation_history=conversation_history,
            system_prompts=system_prompts,
            tools=tools,
            request_id=request_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Add assistant response to history
        conversation_history.append({
            'role': 'assistant',
            'content': [{'text': suggestion}]
        })

        # Save updated conversation history
        ttl = int(time.time()) + (CONVERSATION_TTL_HOURS * 3600)
        conversation_table.put_item(Item={
            'phoneHash': f'internal-{session_id}',  # Required key for table
            'timestamp': Decimal(str(time.time())),
            'id': history_key,
            'sessionId': session_id,
            'messages': conversation_history,
            'lastUpdated': Decimal(str(time.time())),
            'ttl': ttl,
            'context': 'internal-admin'
        })

        logger.info(json.dumps({
            'event': 'internal_agent_response_generated',
            'sessionId': session_id,
            'responseLength': len(suggestion),
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'suggestedResponse': suggestion,
                'messageId': message_id,
                'contactId': contact_id,
                'sessionId': session_id
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'internal_agent_error',
            'error': str(e),
            'requestId': request_id
        }))
        import traceback
        logger.error(f"TRACEBACK: {traceback.format_exc()}")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'suggestedResponse': 'Sorry, I encountered an error processing your request. Please try again.',
                'errorCode': 'INTERNAL_ERROR',
                'requestId': request_id
            })
        }


def _internal_converse_with_tools(
    conversation_history: List[Dict],
    system_prompts: List[Dict],
    tools: List[Dict],
    request_id: str,
    session_id: str = 'unknown',
    max_iterations: int = MAX_TOOL_USE_ITERATIONS,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> str:
    """
    Internal agent conversation with tool use support.
    Handles multi-turn tool calling until final answer is reached.
    """
    current_messages = conversation_history.copy()
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        
        logger.info(json.dumps({
            'event': 'internal_converse_iteration',
            'iteration': iteration,
            'messageCount': len(current_messages),
            'requestId': request_id
        }))

        try:
            # Call Bedrock Converse API
            converse_params = {
                'modelId': MODEL_ID,
                'messages': current_messages,
                'system': system_prompts,
                'toolConfig': {'tools': tools},
                'inferenceConfig': {
                    'maxTokens': max_tokens,
                    'temperature': temperature,
                    'topP': 0.9
                }
            }

            response = bedrock_runtime.converse(**converse_params)
            
            output = response.get('output', {})
            message = output.get('message', {})
            stop_reason = response.get('stopReason')

            logger.info(json.dumps({
                'event': 'internal_converse_response',
                'stopReason': stop_reason,
                'iteration': iteration,
                'requestId': request_id
            }))

            # Add assistant message to conversation
            current_messages.append(message)

            # If model wants to use tools
            if stop_reason == 'tool_use':
                tool_results = []
                
                for content_block in message.get('content', []):
                    if 'toolUse' in content_block:
                        tool_use = content_block['toolUse']
                        tool_name = tool_use.get('name')
                        tool_input = tool_use.get('input', {})
                        tool_use_id = tool_use.get('toolUseId')

                        logger.info(json.dumps({
                            'event': 'internal_tool_use',
                            'toolName': tool_name,
                            'toolInput': tool_input,
                            'requestId': request_id
                        }))

                        # ===== CRITICAL IMPROVEMENTS =====
                        
                        # 1. Rate Limiting
                        allowed, rate_msg = check_rate_limit(session_id, tool_name, limit=10, window=60)
                        if not allowed:
                            tool_result = {'error': rate_msg}
                            tool_results.append({
                                'toolResult': {
                                    'toolUseId': tool_use_id,
                                    'content': [{'json': tool_result}]
                                }
                            })
                            continue
                        
                        # 2. Execute tool with timing and audit logging
                        start_time = time.time()
                        tool_status = 'success'
                        tool_error = ''
                        
                        try:
                            tool_result = _execute_internal_tool(tool_name, tool_input, request_id)
                            
                            # Check if tool returned an error
                            if isinstance(tool_result, dict) and 'error' in tool_result:
                                tool_status = 'error'
                                tool_error = tool_result['error']
                                
                        except Exception as e:
                            tool_status = 'error'
                            tool_error = str(e)
                            tool_result = {'error': f'Tool execution failed: {str(e)}'}
                            logger.error(json.dumps({
                                'event': 'tool_execution_error',
                                'toolName': tool_name,
                                'error': str(e),
                                'requestId': request_id
                            }))
                        
                        duration = time.time() - start_time
                        
                        # 3. Audit Logging
                        log_tool_execution(
                            tool_name=tool_name,
                            params=tool_input,
                            result=tool_result,
                            duration=duration,
                            session_id=session_id,
                            status=tool_status,
                            error=tool_error
                        )

                        tool_results.append({
                            'toolResult': {
                                'toolUseId': tool_use_id,
                                'content': [{'json': tool_result}]
                            }
                        })

                # Add tool results to conversation
                current_messages.append({
                    'role': 'user',
                    'content': tool_results
                })

                # Continue loop to get final answer
                continue

            # If we have a text response, return it
            for content_block in message.get('content', []):
                if 'text' in content_block:
                    response_text = content_block['text']
                    # Strip <thinking>...</thinking> tags from response
                    import re
                    response_text = re.sub(r'<thinking>.*?</thinking>\s*', '', response_text, flags=re.DOTALL).strip()
                    if response_text:
                        return response_text

            # Fallback
            return "I've processed your request."

        except Exception as e:
            logger.error(json.dumps({
                'event': 'internal_converse_error',
                'error': str(e),
                'iteration': iteration,
                'requestId': request_id
            }))
            if iteration == 1:
                raise
            return "I encountered an error while processing your request."

    # Max iterations reached
    logger.warning(json.dumps({
        'event': 'internal_max_iterations_reached',
        'iterations': iteration,
        'requestId': request_id
    }))
    return "I've completed the available steps for your request."


def _execute_internal_tool(tool_name: str, tool_input: Dict, request_id: str) -> Dict:
    """Execute internal agent tool and return result."""
    try:
        # Contact Management
        if tool_name == 'search_contacts':
            return _tool_search_contacts(tool_input, request_id)
        elif tool_name == 'create_contact':
            return _tool_create_contact(tool_input, request_id)
        elif tool_name == 'update_contact':
            return _tool_update_contact(tool_input, request_id)
        
        # WhatsApp Messaging
        elif tool_name == 'send_whatsapp':
            return _tool_send_whatsapp(tool_input, request_id)
        elif tool_name == 'send_whatsapp_buttons':
            return _tool_send_whatsapp_buttons(tool_input, request_id)
        elif tool_name == 'send_whatsapp_list':
            return _tool_send_whatsapp_list(tool_input, request_id)
        elif tool_name == 'send_whatsapp_pay':
            return _tool_send_whatsapp_pay(tool_input, request_id)
        
        # Voice & SMS
        elif tool_name == 'make_voice_call':
            return _tool_make_voice_call(tool_input, request_id)
        elif tool_name == 'send_sms':
            return _tool_send_sms(tool_input, request_id)
        elif tool_name == 'send_email':
            return _tool_send_email(tool_input, request_id)
        
        # Message History & Analytics
        elif tool_name == 'get_messages':
            return _tool_get_messages(tool_input, request_id)
        elif tool_name == 'get_stats':
            return _tool_get_stats(request_id)
        
        # Scheduled Messages
        elif tool_name == 'schedule_message':
            return _tool_schedule_message(tool_input, request_id)
        elif tool_name == 'list_scheduled_messages':
            return _tool_list_scheduled_messages(tool_input, request_id)
        
        # Templates
        elif tool_name == 'list_templates':
            return _tool_list_templates(tool_input, request_id)
        elif tool_name == 'send_template':
            return _tool_send_template(tool_input, request_id)
        
        # Data Management & Cleanup
        elif tool_name == 'add_contact_email':
            return _tool_add_contact_email(tool_input, request_id)
        elif tool_name == 'delete_contact':
            return _tool_delete_contact(tool_input, request_id)
        elif tool_name == 'delete_messages':
            return _tool_delete_messages(tool_input, request_id)
        elif tool_name == 'delete_media_files':
            return _tool_delete_media_files(tool_input, request_id)
        elif tool_name == 'clear_all_contact_data':
            return _tool_clear_all_contact_data(tool_input, request_id)
        elif tool_name == 'list_media_files':
            return _tool_list_media_files(tool_input, request_id)
        
        # Voice CDR & Analytics
        elif tool_name == 'get_voice_cdr':
            return _tool_get_voice_cdr(tool_input, request_id)
        elif tool_name == 'get_billing_summary':
            return _tool_get_billing_summary(tool_input, request_id)
        
        # Invoicing
        elif tool_name == 'get_invoice_list':
            return _tool_get_invoice_list(tool_input, request_id)
        elif tool_name == 'create_invoice':
            return _tool_create_invoice(tool_input, request_id)
        
        # Ecommerce
        elif tool_name == 'get_wix_products':
            return _tool_get_wix_products(tool_input, request_id)
        elif tool_name == 'get_wix_orders':
            return _tool_get_wix_orders(tool_input, request_id)
        
        # WhatsApp Flows
        elif tool_name == 'send_whatsapp_flow':
            return _tool_send_whatsapp_flow(tool_input, request_id)
        elif tool_name == 'list_submit_requests':
            return _tool_list_submit_requests(tool_input, request_id)
        
        else:
            return {'success': False, 'error': f'Unknown tool: {tool_name}'}
    except Exception as e:
        logger.error(json.dumps({
            'event': 'tool_execution_error',
            'toolName': tool_name,
            'error': str(e),
            'requestId': request_id
        }))
        return {'success': False, 'error': str(e)}


def _tool_search_contacts(params: Dict, request_id: str) -> Dict:
    """Search contacts tool implementation."""
    query = params.get('query', '').lower()
    
    if not query:
        return {'success': False, 'error': 'Search query is required'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        response = contacts_table.scan(
            FilterExpression='(attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':null': None}
        )
        
        contacts = []
        for item in response.get('Items', []):
            name = (item.get('name') or '').lower()
            phone = (item.get('phone') or '').lower()
            email = (item.get('email') or '').lower()
            
            if query in name or query in phone or query in email:
                contacts.append({
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'phone': item.get('phone'),
                    'email': item.get('email')
                })
        
        return {
            'success': True,
            'count': len(contacts),
            'contacts': contacts[:10]
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_whatsapp(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp message tool implementation with validation."""
    contact_id = params.get('contactId')
    message = params.get('message')
    
    # Validate contact ID
    if not contact_id:
        return {'success': False, 'error': format_error('invalid_parameters', 'contactId is required')}
    
    valid_id, id_msg = validate_contact_id(contact_id)
    if not valid_id:
        return {'success': False, 'error': format_error('invalid_parameters', id_msg)}
    
    # Validate message
    if not message:
        return {'success': False, 'error': format_error('invalid_parameters', 'message is required')}
    
    if len(message) > 4096:
        return {'success': False, 'error': format_error('message_too_long', f'Message is {len(message)} characters')}
    
    try:
        # Invoke outbound WhatsApp Lambda with retry
        @retry_on_error(max_retries=3)
        def send_message():
            payload = {
                'body': json.dumps({
                    'contactId': contact_id,
                    'content': message
                })
            }
            
            response = lambda_client.invoke(
                FunctionName='wecare-outbound-whatsapp',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read().decode('utf-8'))
            return json.loads(result.get('body', '{}'))
        
        result_body = send_message()
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': result_body.get('status', 'sent'),
            'message': f'? Message sent successfully to contact {contact_id}'
        }
        
    except Exception as e:
        logger.error(f"Send WhatsApp failed: {e}")
        return {'success': False, 'error': format_error('service_unavailable', str(e))}


def _tool_get_messages(params: Dict, request_id: str) -> Dict:
    """Get messages tool implementation."""
    contact_id = params.get('contactId')
    limit = int(params.get('limit', 10))
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    try:
        messages = []
        
        # Get inbound messages
        inbound_table = dynamodb.Table(MESSAGES_TABLE)
        inbound_response = inbound_table.scan(
            FilterExpression='contactId = :cid',
            ExpressionAttributeValues={':cid': contact_id},
            Limit=limit
        )
        
        for item in inbound_response.get('Items', []):
            messages.append({
                'direction': 'inbound',
                'content': item.get('content'),
                'timestamp': str(item.get('timestamp'))
            })
        
        # Sort by timestamp
        messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            'success': True,
            'count': len(messages),
            'messages': messages[:limit]
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_get_stats(request_id: str) -> Dict:
    """Get stats tool implementation."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        
        contacts_count = contacts_table.scan(
            FilterExpression='attribute_not_exists(deletedAt) OR deletedAt = :null',
            ExpressionAttributeValues={':null': None},
            Select='COUNT'
        ).get('Count', 0)
        
        messages_count = messages_table.scan(Select='COUNT').get('Count', 0)
        
        return {
            'success': True,
            'totalContacts': contacts_count,
            'totalMessages': messages_count
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================================
# EXTERNAL PATH (WhatsApp - Converse API + multimodal + conversation history)
# ============================================================================

def _handle_external(body: Dict, headers: Dict, request_id: str) -> Dict:
    """
    External WhatsApp path using Bedrock Converse API.
    Supports text + multimodal (image, audio, video, document).
    Maintains conversation history per contact in DynamoDB.
    Implements processing lock to prevent duplicate AI calls.
    """
    message_content = body.get('messageContent', '')
    message_id = body.get('messageId', '')
    contact_id = body.get('contactId', '')
    sender_phone = body.get('senderPhone', '')
    message_type = body.get('messageType', 'text')
    s3_key = body.get('s3Key', '')
    media_type = body.get('mediaType', '')
    mime_type = body.get('mimeType', '')
    phone_number_id = body.get('phoneNumberId', '')

    # Hash phone for DynamoDB key (privacy)
    # Include phoneNumberId to separate AI sessions per WABA
    base_phone_hash = _hash_phone(sender_phone) if sender_phone else contact_id
    if phone_number_id:
        phone_hash = _hash_phone(f"{sender_phone}:{phone_number_id}") if sender_phone else f"{contact_id}:{phone_number_id}"
    else:
        phone_hash = base_phone_hash

    logger.info(json.dumps({
        'event': 'external_handler_start',
        'hasSenderPhone': bool(sender_phone),
        'hasMessageContent': bool(message_content),
        'messageType': message_type,
        'phoneHash': phone_hash[:8] if phone_hash else 'NONE',
        'contactId': contact_id,
        'requestId': request_id
    }))

    if not phone_hash:
        return {
            'statusCode': 200, 'headers': headers,
            'body': json.dumps({'suggestedResponse': _get_fallback_response(), 'error': 'No sender identifier'})
        }

    # -- Processing lock: prevent duplicate AI calls --
    lock_acquired = _acquire_processing_lock(phone_hash)
    if not lock_acquired:
        return {
            'statusCode': 200, 'headers': headers,
            'body': json.dumps({
                'suggestedResponse': '',
                'locked': True,
                'messageId': message_id,
                'contactId': contact_id
            })
        }

    try:
        # -- Message size validation: truncate oversized text --
        if message_content and len(message_content) > MAX_INPUT_TEXT_LENGTH:
            logger.warning(json.dumps({
                'event': 'message_truncated',
                'originalLength': len(message_content),
                'maxLength': MAX_INPUT_TEXT_LENGTH,
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
            message_content = message_content[:MAX_INPUT_TEXT_LENGTH] + '...[truncated]'

        # -- Load conversation history --
        logger.info(json.dumps({
            'event': 'loading_history',
            'phoneHash': phone_hash[:8],
            'requestId': request_id
        }))
        history = _load_conversation_history(phone_hash)

        # -- Check if this is a language selection reply --
        lang_selection = _detect_language_selection(message_content, message_type)
        if lang_selection:
            # Region selection (Step 1) ? return languages for that region
            if isinstance(lang_selection, dict) and 'region' in lang_selection:
                region_id = lang_selection['region']
                region_languages = lang_selection['languages']
                lp_config = _get_language_picker_config_from_db()
                # Use DB config if available, fallback to detected
                db_region_langs = lp_config['languagesByRegion'].get(region_id)
                if db_region_langs:
                    region_languages = db_region_langs
                region_title = next(
                    (r['title'] for r in lp_config['regionPicker'] if r['id'] == region_id),
                    'Languages'
                )
                logger.info(json.dumps({
                    'event': 'language_region_selected',
                    'region': region_id,
                    'phoneHash': phone_hash,
                    'requestId': request_id
                }))
                return {
                    'statusCode': 200, 'headers': headers,
                    'body': json.dumps({
                        'suggestedResponse': f'?? Choose your language from {region_title} ??',
                        'showLanguagePicker': True,
                        'languagePickerStep': 'languages',
                        'regionId': region_id,
                        'regionTitle': region_title,
                        'regionLanguages': region_languages,
                    })
                }

            # Language selection (Step 2) ? save preference
            lp_config = _get_language_picker_config_from_db()
            _save_language_preference(phone_hash, lang_selection)
            confirmation = lp_config['languageConfirmations'].get(lang_selection,
                LANGUAGE_CONFIRMATIONS.get(lang_selection,
                    f"Language set to {lang_selection}! \U0001f310 How can I help you?"))
            logger.info(json.dumps({
                'event': 'language_preference_set',
                'language': lang_selection,
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
            return {
                'statusCode': 200, 'headers': headers,
                'body': json.dumps({
                    'suggestedResponse': confirmation,
                    'suggestion': confirmation,
                    'messageId': message_id,
                    'contactId': contact_id,
                    'languageSet': lang_selection,
                    'flowAction': 'showOptions',
                })
            }

        # -- Bot flow: handle menu/options/rating selections --
        flow_config = _get_bot_flow_config()

        # -- Apply welcome page override (welcome.tsx ? SystemConfigTable 'welcome_message') --
        welcome_override = _get_welcome_config()
        if welcome_override:
            if welcome_override.get('textMessage'):
                flow_config.setdefault('welcome', {})['text'] = welcome_override['textMessage']
            if welcome_override.get('welcomeBackMessage'):
                flow_config.setdefault('welcomeBack', {})['text'] = welcome_override['welcomeBackMessage']

        flow_result = _handle_bot_flow(message_content, message_type, flow_config, history, phone_hash, sender_phone, request_id)
        if flow_result:
            return {
                'statusCode': 200, 'headers': headers,
                'body': json.dumps({
                    **flow_result,
                    'messageId': message_id,
                    'contactId': contact_id,
                })
            }

        # -- Check if this is a brand-new session (no history) ? send welcome text only --
        # Menu is NOT auto-sent. User types "menu" to see it.
        is_new_session = not history.get('messages') and not history.get('preferredLanguage')
        is_returning = not history.get('messages') and history.get('preferredLanguage')
        if is_new_session or is_returning:
            welcome_key = 'welcomeBack' if is_returning else 'welcome'
            welcome_text = flow_config.get(welcome_key, flow_config.get('welcome', {})).get('text', '')
            logger.info(json.dumps({
                'event': 'new_session_welcome',
                'welcomeType': welcome_key,
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
            # Save a history marker so welcome doesn't repeat on next message
            _save_conversation_history(
                phone_hash=phone_hash,
                messages=[{'role': 'assistant', 'content': [{'text': welcome_text}]}],
                message_count=0
            )
            # Just send welcome text - no auto menu
            return {
                'statusCode': 200, 'headers': headers,
                'body': json.dumps({
                    'suggestedResponse': welcome_text,
                    'suggestion': welcome_text,
                    'originalMessage': message_content,
                    'messageId': message_id,
                    'contactId': contact_id,
                })
            }

        # -- Build the user content blocks for Converse API --
        content_blocks = _build_content_blocks(
            message_content=message_content,
            message_type=message_type,
            s3_key=s3_key,
            media_type=media_type,
            mime_type=mime_type,
            request_id=request_id
        )

        if not content_blocks:
            return {
                'statusCode': 200, 'headers': headers,
                'body': json.dumps({'suggestedResponse': _get_fallback_response()})
            }

        # -- Session idle timeout: reset if idle too long --
        last_updated = history.get('updatedAt', 0)
        if last_updated:
            idle_seconds = time.time() - float(last_updated)
            idle_minutes = idle_seconds / 60
            if idle_minutes > SESSION_IDLE_TIMEOUT_MINUTES:
                logger.info(json.dumps({
                    'event': 'session_reset_idle',
                    'phoneHash': phone_hash,
                    'idleMinutes': round(idle_minutes, 1),
                    'threshold': SESSION_IDLE_TIMEOUT_MINUTES,
                    'requestId': request_id
                }))
                history = {'messages': [], 'messageCount': 0}

        # -- Check conversation limits --
        session_msg_count = history.get('messageCount', 0)
        if session_msg_count >= MAX_SESSION_MESSAGES:
            logger.info(json.dumps({
                'event': 'session_reset_limit',
                'phoneHash': phone_hash,
                'messageCount': session_msg_count,
                'requestId': request_id
            }))
            history = {'messages': [], 'messageCount': 0}

        # -- Intent classification + human escalation --
        # Skip classification for very short messages (greetings, single words)
        # to avoid unnecessary latency on simple interactions
        if message_content and message_type == 'text' and len(message_content.strip()) > 10:
            intent_result = _classify_intent(message_content, request_id)
            if intent_result.get('escalate'):
                logger.info(json.dumps({
                    'event': 'intent_escalation',
                    'intent': intent_result.get('intent', 'unknown'),
                    'confidence': intent_result.get('confidence', 0),
                    'phoneHash': phone_hash,
                    'requestId': request_id
                }))
                escalation_msg = "I'd like to connect you with our team for the best help on this. ?? A team member will be with you shortly. You can also reach us at +91 9330994400."
                return {
                    'statusCode': 200, 'headers': headers,
                    'body': json.dumps({
                        'suggestedResponse': escalation_msg,
                        'suggestion': escalation_msg,
                        'escalate': True,
                        'intent': intent_result.get('intent', 'unknown'),
                        'confidence': intent_result.get('confidence', 0),
                        'messageId': message_id,
                        'contactId': contact_id
                    })
                }

        # -- Retrieve KB context for grounded answers --
        # Only pre-fetch KB for the first message in a session (no history).
        # For subsequent messages, the model can use the search_knowledge_base tool
        # autonomously when it needs factual data, avoiding redundant KB calls.
        kb_context = ''
        if message_content and not history.get('messages'):
            kb_context = _retrieve_kb_context(message_content, request_id)

        # -- Build system prompt with KB context and language preference --
        system_prompt = SYSTEM_PROMPT
        preferred_lang = history.get('preferredLanguage', '')
        if preferred_lang:
            system_prompt += f"\n\nUSER'S PREFERRED LANGUAGE: {preferred_lang}\nYou MUST respond in {preferred_lang}. This is the user's explicit choice."
        if kb_context:
            system_prompt += f"\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n{kb_context}"

        # -- Prepare messages for Converse API --
        converse_messages = history.get('messages', [])[-MAX_HISTORY_MESSAGES:]
        converse_messages.append({'role': 'user', 'content': content_blocks})

        # -- Call Bedrock Converse API (with tool use loop) --
        suggestion = _call_converse_with_tools(
            system_prompt=system_prompt,
            messages=converse_messages,
            sender_phone=sender_phone,
            phone_hash=phone_hash,
            request_id=request_id
        )

        if not suggestion:
            suggestion = _get_fallback_response()

        # -- Save updated conversation history --
        # Only store text representation in history (not raw media bytes)
        history_user_content = [{'text': message_content or f'[{message_type}]'}]
        history_messages = history.get('messages', [])[-MAX_HISTORY_MESSAGES:]
        history_messages.append({'role': 'user', 'content': history_user_content})
        history_messages.append({'role': 'assistant', 'content': [{'text': suggestion}]})

        _save_conversation_history(
            phone_hash=phone_hash,
            messages=history_messages,
            message_count=session_msg_count + 1
        )

        logger.info(json.dumps({
            'event': 'ai_generate_complete',
            'messageId': message_id,
            'messageType': message_type,
            'hasMedia': bool(s3_key),
            'historyLength': len(history_messages),
            'suggestionLength': len(suggestion),
            'requestId': request_id
        }))

        return {
            'statusCode': 200, 'headers': headers,
            'body': json.dumps({
                'suggestedResponse': suggestion,
                'suggestion': suggestion,
                'messageId': message_id,
                'contactId': contact_id
            })
        }

    finally:
        _release_processing_lock(phone_hash)


# ============================================================================
# MULTIMODAL CONTENT BLOCKS
# ============================================================================

def _build_content_blocks(
    message_content: str,
    message_type: str,
    s3_key: str,
    media_type: str,
    mime_type: str,
    request_id: str
) -> List[Dict]:
    """
    Build Converse API content blocks from the inbound message.
    Supports text, image, audio, video, and document.
    """
    blocks = []

    # Always include text if present
    if message_content and message_content not in ('[Image]', '[Video]', '[Audio]', '[Document]', '[Sticker]'):
        blocks.append({'text': message_content})

    # Add media content block if we have an S3 key
    if s3_key and message_type in ('image', 'video', 'audio', 'document', 'sticker'):
        media_block = _build_media_block(s3_key, message_type, mime_type, request_id)
        if media_block:
            blocks.append(media_block)
            # Add instruction text if no caption was provided (only media block, no text)
            if len(blocks) == 1:
                type_prompts = {
                    'image': 'The user sent this image. Describe what you see and ask how you can help.',
                    'audio': 'The user sent this voice note. Listen and respond to what they said.',
                    'video': 'The user sent this video. Describe the key content and respond helpfully.',
                    'document': 'The user sent this document. Summarize the key points and ask what they need.',
                    'sticker': 'The user sent a sticker. Acknowledge it warmly.',
                }
                blocks.insert(0, {'text': type_prompts.get(message_type, f'The user sent a {message_type}.')})

    # Fallback: at least one text block
    if not blocks:
        if message_content:
            blocks.append({'text': message_content})
        else:
            blocks.append({'text': '[User sent a message]'})

    return blocks


def _build_media_block(s3_key: str, message_type: str, mime_type: str, request_id: str) -> Optional[Dict]:
    """
    Build a single media content block for the Converse API.
    Downloads from S3 and formats per Nova's schema.
    """
    try:
        # Determine format from mime type or file extension
        fmt = _get_converse_format(message_type, mime_type, s3_key)
        if not fmt:
            logger.warning(json.dumps({
                'event': 'unsupported_media_format',
                'messageType': message_type,
                'mimeType': mime_type,
                's3Key': s3_key,
                'requestId': request_id
            }))
            return None

        # Check file size before downloading
        head = s3.head_object(Bucket=MEDIA_BUCKET, Key=s3_key)
        file_size = head.get('ContentLength', 0)

        size_limits = {
            'image': MAX_IMAGE_BYTES,
            'sticker': MAX_IMAGE_BYTES,
            'audio': MAX_AUDIO_BYTES,
            'video': MAX_VIDEO_BYTES,
            'document': MAX_DOC_BYTES,
        }
        max_size = size_limits.get(message_type, MAX_DOC_BYTES)

        if file_size > max_size:
            logger.warning(json.dumps({
                'event': 'media_too_large',
                'messageType': message_type,
                'fileSize': file_size,
                'maxSize': max_size,
                'requestId': request_id
            }))
            return None

        # For video, use S3 URI (Nova supports s3Location for video)
        if message_type == 'video':
            return {
                'video': {
                    'format': fmt,
                    'source': {
                        's3Location': {
                            'uri': f's3://{MEDIA_BUCKET}/{s3_key}'
                        }
                    }
                }
            }

        # For audio, use S3 URI (Nova supports s3Location for audio)
        if message_type == 'audio':
            return {
                'audio': {
                    'format': fmt,
                    'source': {
                        's3Location': {
                            'uri': f's3://{MEDIA_BUCKET}/{s3_key}'
                        }
                    }
                }
            }

        # For image/sticker, download bytes
        if message_type in ('image', 'sticker'):
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            image_bytes = obj['Body'].read()
            return {
                'image': {
                    'format': fmt,
                    'source': {'bytes': image_bytes}
                }
            }

        # For document, download bytes
        if message_type == 'document':
            obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
            doc_bytes = obj['Body'].read()
            doc_name = s3_key.split('/')[-1] if '/' in s3_key else s3_key
            return {
                'document': {
                    'format': fmt,
                    'name': re.sub(r'[^a-zA-Z0-9_\-\.]', '_', doc_name)[:200],
                    'source': {'bytes': doc_bytes}
                }
            }

        return None

    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_block_error',
            'messageType': message_type,
            's3Key': s3_key,
            'error': str(e),
            'requestId': request_id
        }))
        return None


def _get_converse_format(message_type: str, mime_type: str, s3_key: str) -> Optional[str]:
    """Map mime type / message type to Converse API format string."""
    # Image formats
    image_map = {
        'image/jpeg': 'jpeg', 'image/jpg': 'jpeg',
        'image/png': 'png', 'image/gif': 'gif', 'image/webp': 'webp',
    }
    # Audio formats (Nova supports these natively)
    audio_map = {
        'audio/ogg': 'ogg', 'audio/mpeg': 'mp3', 'audio/mp3': 'mp3',
        'audio/mp4': 'mp4', 'audio/aac': 'aac', 'audio/wav': 'wav',
        'audio/flac': 'flac', 'audio/opus': 'opus', 'audio/amr': 'ogg',
    }
    # Video formats
    video_map = {
        'video/mp4': 'mp4', 'video/3gpp': 'three_gp',
        'video/webm': 'webm', 'video/quicktime': 'mov',
        'video/x-matroska': 'mkv',
    }
    # Document formats
    doc_map = {
        'application/pdf': 'pdf',
        'text/plain': 'txt',
        'text/csv': 'csv',
        'text/html': 'html',
        'application/msword': 'doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.ms-excel': 'xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    }

    mime_lower = (mime_type or '').lower()

    if message_type in ('image', 'sticker'):
        if mime_lower in image_map:
            return image_map[mime_lower]
        # Guess from extension
        ext = s3_key.rsplit('.', 1)[-1].lower() if '.' in s3_key else ''
        return {'jpeg': 'jpeg', 'jpg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')

    if message_type == 'audio':
        if mime_lower in audio_map:
            return audio_map[mime_lower]
        ext = s3_key.rsplit('.', 1)[-1].lower() if '.' in s3_key else ''
        return {'ogg': 'ogg', 'mp3': 'mp3', 'aac': 'aac', 'wav': 'wav', 'm4a': 'mp4', 'opus': 'opus'}.get(ext, 'ogg')

    if message_type == 'video':
        if mime_lower in video_map:
            return video_map[mime_lower]
        ext = s3_key.rsplit('.', 1)[-1].lower() if '.' in s3_key else ''
        return {'mp4': 'mp4', '3gp': 'three_gp', 'webm': 'webm', 'mov': 'mov', 'mkv': 'mkv'}.get(ext, 'mp4')

    if message_type == 'document':
        if mime_lower in doc_map:
            return doc_map[mime_lower]
        ext = s3_key.rsplit('.', 1)[-1].lower() if '.' in s3_key else ''
        return {'pdf': 'pdf', 'txt': 'txt', 'csv': 'csv', 'html': 'html',
                'doc': 'doc', 'docx': 'docx', 'xls': 'xls', 'xlsx': 'xlsx'}.get(ext, 'pdf')

    return None


# ============================================================================
# BEDROCK CONVERSE API
# ============================================================================

def _call_converse(system_prompt: str, messages: List[Dict], request_id: str) -> str:
    """
    Call Bedrock Converse API with conversation history and multimodal content.
    Uses Amazon Nova Lite with optional Guardrails.
    """
    try:
        logger.info(json.dumps({
            'event': 'converse_call_start',
            'modelId': MODEL_ID,
            'messagesCount': len(messages),
            'hasGuardrail': bool(GUARDRAIL_ID),
            'requestId': request_id
        }))

        params = {
            'modelId': MODEL_ID,
            'system': [{'text': system_prompt}],
            'messages': messages,
            'inferenceConfig': {
                'maxTokens': 512,
                'temperature': 0.7,
                'topP': 0.9,
            }
        }

        # Add Guardrails if configured
        if GUARDRAIL_ID:
            params['guardrailConfig'] = {
                'guardrailIdentifier': GUARDRAIL_ID,
                'guardrailVersion': GUARDRAIL_VERSION,
            }

        response = bedrock_runtime.converse(**params)

        # Extract response text
        output = response.get('output', {})
        message = output.get('message', {})
        content_blocks = message.get('content', [])

        result_text = ''
        for block in content_blocks:
            if 'text' in block:
                result_text += block['text']

        # Check if guardrail intervened
        stop_reason = response.get('stopReason', '')
        if stop_reason == 'guardrail_intervened':
            logger.warning(json.dumps({
                'event': 'guardrail_intervened',
                'requestId': request_id
            }))
            return _get_fallback_response()

        usage = response.get('usage', {})
        logger.info(json.dumps({
            'event': 'converse_call_success',
            'responseLength': len(result_text),
            'inputTokens': usage.get('inputTokens', 0),
            'outputTokens': usage.get('outputTokens', 0),
            'stopReason': stop_reason,
            'requestId': request_id
        }))

        return result_text.strip() if result_text else ''

    except Exception as e:
        logger.error(json.dumps({
            'event': 'converse_call_error',
            'error': str(e),
            'requestId': request_id
        }))
        return ''


# ============================================================================
# INTENT CLASSIFICATION (lightweight Converse call for escalation detection)
# ============================================================================

def _classify_intent(message_content: str, request_id: str) -> Dict:
    """
    Classify customer intent using a lightweight Converse API call.
    Returns {'intent': str, 'escalate': bool, 'confidence': float}.
    If classification fails, returns non-escalating default.
    """
    try:
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            system=[{'text': INTENT_CLASSIFICATION_PROMPT}],
            messages=[{'role': 'user', 'content': [{'text': message_content}]}],
            inferenceConfig={'maxTokens': 100, 'temperature': 0.1}
        )

        output_text = ''
        for block in response.get('output', {}).get('message', {}).get('content', []):
            if 'text' in block:
                output_text += block['text']

        # Parse JSON from response
        # Handle cases where model wraps JSON in markdown code blocks
        clean = output_text.strip()
        if clean.startswith('```'):
            clean = re.sub(r'^```(?:json)?\s*', '', clean)
            clean = re.sub(r'\s*```$', '', clean)

        result = json.loads(clean)

        logger.info(json.dumps({
            'event': 'intent_classified',
            'intent': result.get('intent', 'unknown'),
            'escalate': result.get('escalate', False),
            'confidence': result.get('confidence', 0),
            'requestId': request_id
        }))

        return {
            'intent': result.get('intent', 'general_inquiry'),
            'escalate': bool(result.get('escalate', False)),
            'confidence': float(result.get('confidence', 0.8))
        }

    except Exception as e:
        logger.warning(json.dumps({
            'event': 'intent_classification_error',
            'error': str(e),
            'requestId': request_id
        }))
        # Fail open - don't escalate on classification error
        return {'intent': 'unknown', 'escalate': False, 'confidence': 0.0}


# ============================================================================
# CONVERSE API WITH TOOL USE LOOP
# ============================================================================

def _call_converse_with_tools(system_prompt: str, messages: List[Dict], sender_phone: str, phone_hash: str, request_id: str) -> str:
    """
    Call Bedrock Converse API with tool definitions.
    Handles tool use loop: if the model requests a tool, execute it locally,
    append the result, and call Converse again until we get a text response.
    """
    working_messages = list(messages)
    iteration = 0

    while iteration < MAX_TOOL_USE_ITERATIONS:
        iteration += 1

        params = {
            'modelId': MODEL_ID,
            'system': [{'text': system_prompt}],
            'messages': working_messages,
            'inferenceConfig': {
                'maxTokens': 512,
                'temperature': 0.7,
                'topP': 0.9,
            },
            'toolConfig': {
                'tools': TOOL_DEFINITIONS
            }
        }

        if GUARDRAIL_ID:
            params['guardrailConfig'] = {
                'guardrailIdentifier': GUARDRAIL_ID,
                'guardrailVersion': GUARDRAIL_VERSION,
            }

        logger.info(json.dumps({
            'event': 'converse_tool_call',
            'iteration': iteration,
            'messagesCount': len(working_messages),
            'requestId': request_id
        }))

        try:
            response = bedrock_runtime.converse(**params)
        except Exception as e:
            logger.error(json.dumps({
                'event': 'converse_tool_call_error',
                'iteration': iteration,
                'error': str(e),
                'requestId': request_id
            }))
            # Fallback: try without tools
            if iteration == 1:
                return _call_converse(system_prompt, messages, request_id)
            return ''

        stop_reason = response.get('stopReason', '')
        output_message = response.get('output', {}).get('message', {})
        content_blocks = output_message.get('content', [])

        # Log usage
        usage = response.get('usage', {})
        logger.info(json.dumps({
            'event': 'converse_tool_response',
            'iteration': iteration,
            'stopReason': stop_reason,
            'inputTokens': usage.get('inputTokens', 0),
            'outputTokens': usage.get('outputTokens', 0),
            'contentBlocks': len(content_blocks),
            'requestId': request_id
        }))

        if stop_reason == 'guardrail_intervened':
            return _get_fallback_response()

        # If model wants to use tools
        if stop_reason == 'tool_use':
            # Append assistant message with tool use request
            working_messages.append({'role': 'assistant', 'content': content_blocks})

            # Execute each tool request and build results
            tool_results = []
            for block in content_blocks:
                if 'toolUse' in block:
                    tool_use = block['toolUse']
                    tool_name = tool_use.get('name', '')
                    tool_input = tool_use.get('input', {})
                    tool_use_id = tool_use.get('toolUseId', '')

                    result = _execute_tool(tool_name, tool_input, sender_phone, phone_hash, request_id)

                    tool_results.append({
                        'toolResult': {
                            'toolUseId': tool_use_id,
                            'content': [{'text': result}]
                        }
                    })

            # Append tool results as user message
            working_messages.append({'role': 'user', 'content': tool_results})
            continue

        # Model returned a final text response (stop_reason = 'end_turn' or 'max_tokens')
        result_text = ''
        for block in content_blocks:
            if 'text' in block:
                result_text += block['text']

        return result_text.strip() if result_text else ''

    # Exhausted iterations - return whatever we have
    logger.warning(json.dumps({
        'event': 'tool_use_max_iterations',
        'iterations': MAX_TOOL_USE_ITERATIONS,
        'requestId': request_id
    }))
    return _get_fallback_response()


def _execute_tool(tool_name: str, tool_input: Dict, sender_phone: str, phone_hash: str, request_id: str) -> str:
    """
    Execute a tool requested by the Converse API model.
    Returns the tool result as a string.
    """
    logger.info(json.dumps({
        'event': 'tool_execute',
        'toolName': tool_name,
        'requestId': request_id
    }))

    try:
        if tool_name == 'search_knowledge_base':
            query = tool_input.get('query', '')
            context = _retrieve_kb_context(query, request_id)
            return context if context else 'No relevant information found in the knowledge base.'

        elif tool_name == 'lookup_contact':
            phone = tool_input.get('phone', sender_phone)
            return _lookup_contact(phone, request_id)

        elif tool_name == 'get_brand_info':
            from static_knowledge_base import get_brand_info
            brand_info = get_brand_info()
            return json.dumps(brand_info, indent=2)

        elif tool_name == 'set_language':
            language = tool_input.get('language', '')
            lang_normalized = SUPPORTED_LANGUAGES.get(language.lower().strip(), language)
            if lang_normalized in LANGUAGE_CONFIRMATIONS:
                _save_language_preference(phone_hash, lang_normalized)
                return f'Language preference saved: {lang_normalized}. Now respond to the user in {lang_normalized}.'
            return f'Unsupported language: {language}. Available: English, Hindi, Bengali, Tamil, Telugu, Gujarati, Marathi, Hinglish, Kannada, Malayalam.'

        else:
            return f'Unknown tool: {tool_name}'

    except Exception as e:
        logger.error(json.dumps({
            'event': 'tool_execute_error',
            'toolName': tool_name,
            'error': str(e),
            'requestId': request_id
        }))
        return f'Error executing {tool_name}: {str(e)}'


def _lookup_contact(phone: str, request_id: str) -> str:
    """Look up contact info from DynamoDB contacts table by phone number."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

        # Query using phone GSI or scan with filter
        # Try GSI first (phone-index), fall back to scan
        try:
            response = contacts_table.query(
                IndexName='phone-index',
                KeyConditionExpression='phone = :phone',
                ExpressionAttributeValues={':phone': clean_phone},
                Limit=1
            )
            items = response.get('Items', [])
        except Exception:
            # GSI may not exist - fall back to scan (less efficient but works)
            response = contacts_table.scan(
                FilterExpression='phone = :phone OR contains(phone, :phone)',
                ExpressionAttributeValues={':phone': clean_phone},
                Limit=1
            )
            items = response.get('Items', [])

        if items:
            item = items[0]
            name = item.get('name', item.get('contactName', 'Unknown'))
            email = item.get('email', '')
            tags = item.get('tags', [])
            return json.dumps({
                'name': name,
                'email': email,
                'tags': tags if isinstance(tags, list) else [],
                'found': True
            })
        return json.dumps({'found': False, 'message': 'Contact not found'})
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'contact_lookup_error',
            'error': str(e),
            'requestId': request_id
        }))
        return json.dumps({'found': False, 'message': 'Could not look up contact'})


def _get_brand_info(brand_name: str) -> str:
    """Return structured brand information."""
    brands = {
        'bnb club': {
            'name': 'BNB Club',
            'domain': 'Travel, Hotels, Visa Services',
            'website': 'https://bnbclub.in',
            'services': 'Hotel bookings, travel packages, visa assistance, flight bookings',
            'contact': '+91 9330994400',
        },
        'legal champ': {
            'name': 'Legal Champ',
            'domain': 'Documents, Registration, GST',
            'website': 'https://legalchamp.in',
            'services': 'Company registration, GST filing, trademark, legal documents',
            'contact': '+91 9330994400',
        },
        'no fault': {
            'name': 'No Fault',
            'domain': 'Disputes, Complaints Resolution',
            'website': 'https://nofault.in',
            'services': 'Consumer complaints, dispute resolution, legal notices',
            'contact': '+91 9330994400',
        },
        'ritual guru': {
            'name': 'Ritual Guru',
            'domain': 'Puja, Rituals, Spiritual Services',
            'website': 'https://ritualguru.in',
            'services': 'Online puja booking, ritual services, pandit booking',
            'contact': '+91 9330994400',
        },
        'swdhya': {
            'name': 'Swdhya',
            'domain': 'Self-inquiry, Reflection, Wellness',
            'website': 'https://swdhya.in',
            'services': 'Self-reflection tools, wellness programs, mindfulness',
            'contact': '+91 9330994400',
        },
    }
    key = brand_name.lower().strip()
    info = brands.get(key)
    if info:
        return json.dumps(info)
    # Fuzzy match
    for k, v in brands.items():
        if key in k or k in key:
            return json.dumps(v)
    return json.dumps({'error': f'Brand "{brand_name}" not found. Available: BNB Club, Legal Champ, No Fault, Ritual Guru, Swdhya'})


# ============================================================================
# KNOWLEDGE BASE RETRIEVAL (for grounding external responses)
# ============================================================================

# Import static knowledge base (FREE - no OpenSearch costs!)
import sys
sys.path.append('/opt/python')
from static_knowledge_base import search_knowledge_base as static_kb_search

def _retrieve_kb_context(query: str, request_id: str) -> str:
    """Retrieve relevant context from static knowledge base (FREE - no OpenSearch!)."""
    if not query:
        return ''
    try:
        # Use static KB instead of OpenSearch
        context = static_kb_search(query, max_results=3)
        logger.info(json.dumps({
            'event': 'static_kb_retrieve_success',
            'contextLength': len(context),
            'requestId': request_id
        }))
        return context
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'static_kb_retrieve_error',
            'error': str(e),
            'requestId': request_id
        }))
        return ''


# ============================================================================
# LANGUAGE PREFERENCE
# ============================================================================

def _detect_language_selection(message_content: str, message_type: str) -> Optional[Any]:
    """
    Detect if the user's message is a language or region selection.
    Handles:
    - Region picker reply ID (e.g. "region_popular") ? returns dict with region languages
    - Interactive list reply ID (e.g. "lang_hindi") ? returns language name string
    - Interactive list reply title (e.g. "????? / Hindi")
    - Text commands like "language hindi", "lang: bengali"
    Returns:
    - str: normalized language name (for lang_ selections)
    - dict: {'region': region_id, 'languages': [...]} (for region_ selections)
    - None: not a language/region selection
    """
    if not message_content:
        return None

    content_lower = message_content.strip().lower()

    # -- Step 1 reply: Region selection (e.g. "region_popular") --
    if content_lower.startswith('region_'):
        languages = LANGUAGE_BY_REGION.get(content_lower)
        if languages:
            return {'region': content_lower, 'languages': languages}

    # -- Step 2 reply: Language selection (e.g. "lang_hindi") --
    if content_lower.startswith('lang_'):
        lang = LANGUAGE_ID_MAP.get(content_lower)
        if lang:
            return lang

    # Check interactive list reply title (e.g. "????? / Hindi" ? extract "Hindi")
    if message_type == 'interactive':
        if ' / ' in message_content:
            english_part = message_content.split(' / ')[-1].strip().lower()
            if english_part in SUPPORTED_LANGUAGES:
                return SUPPORTED_LANGUAGES[english_part]
        if content_lower in SUPPORTED_LANGUAGES:
            return SUPPORTED_LANGUAGES[content_lower]

    # Text command: "language hindi", "lang bengali", "change language to tamil"
    lang_patterns = [
        r'^(?:language|lang|bhasha|भाषा)[:\s]+(\w+)',
        r'^change\s+language\s+(?:to\s+)?(\w+)',
        r'^switch\s+(?:to\s+)?(\w+)',
        r'^(\w+)\s+(?:mein|me|में)\s+(?:baat|bolo|reply|jawab)',
    ]
    for pattern in lang_patterns:
        match = re.match(pattern, content_lower)
        if match:
            lang_key = match.group(1).strip()
            if lang_key in SUPPORTED_LANGUAGES:
                return SUPPORTED_LANGUAGES[lang_key]

    return None


def _detect_brand_selection(message_content: str, message_type: str) -> Optional[str]:
    """
    Detect if the user selected a brand from the welcome menu.
    Returns the brand ID (e.g. 'bnbclub') or None.
    """
    if not message_content:
        return None

    content_lower = message_content.strip().lower()

    # Interactive list reply ID (e.g. "brand_bnbclub")
    if content_lower.startswith('brand_'):
        return content_lower.replace('brand_', '')

    return None


# ============================================================================
# BOT FLOW ENGINE (menu ? response ? options ? rating)
# ============================================================================

def _get_bot_flow_config() -> Dict:
    """Load bot flow config from SystemConfigTable. Falls back to DEFAULT_BOT_FLOW."""
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = table.get_item(Key={'id': 'bot_flow_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            merged = DEFAULT_BOT_FLOW.copy()
            merged.update(config)
            return merged
        return DEFAULT_BOT_FLOW.copy()
    except Exception as e:
        logger.warning(f"Failed to get bot flow config: {str(e)}")
        return DEFAULT_BOT_FLOW.copy()


def _get_language_picker_config_from_db() -> Dict:
    """
    Load language picker config from SystemConfigTable (id: 'bot_language_picker_config').
    Returns dict with keys: regionPicker, languagesByRegion, languageConfirmations.
    All are dashboard-manageable. Falls back to hardcoded defaults.
    """
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = table.get_item(Key={'id': 'bot_language_picker_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            return {
                'regionPicker': config.get('regionPicker', LANGUAGE_REGION_PICKER),
                'languagesByRegion': config.get('languagesByRegion', LANGUAGE_BY_REGION),
                'languageConfirmations': config.get('languageConfirmations', LANGUAGE_CONFIRMATIONS),
            }
    except Exception as e:
        logger.warning(f"Failed to get language picker config: {str(e)}")

    return {
        'regionPicker': LANGUAGE_REGION_PICKER,
        'languagesByRegion': LANGUAGE_BY_REGION,
        'languageConfirmations': LANGUAGE_CONFIRMATIONS,
    }

def _get_welcome_config() -> Optional[Dict]:
    """
    Load welcome message config from SystemConfigTable (id: 'welcome_message').
    This is managed by the Welcome page (welcome.tsx).
    Returns the config dict if enabled, None otherwise.
    """
    try:
        table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = table.get_item(Key={'id': 'welcome_message'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            if config.get('enabled', False):
                return config
    except Exception as e:
        logger.warning(f"Failed to get welcome config: {str(e)}")
    return None




def _handle_bot_flow(message_content: str, message_type: str, flow_config: Dict,
                     history: Dict, phone_hash: str, sender_phone: str, request_id: str) -> Optional[Dict]:
    """
    Handle bot flow selections (menu items, options, ratings) and multi-step
    conversational flows (subscribe, pay) via a state machine stored in DynamoDB.
    Returns a response dict if the message is a flow action, or None to fall through to AI.
    """
    if not message_content:
        return None

    content_lower = message_content.strip().lower()

    # -- Fix #3: Escape words - cancel/back/exit during active flows --
    ESCAPE_WORDS = {'cancel', 'menu', 'exit', 'stop', 'quit', 'main menu'}

    # -- Check for active conversational flow (state machine) --
    flow_state = history.get('flowState')
    if flow_state:
        # Check escape words first
        if content_lower in ESCAPE_WORDS:
            _clear_flow_state(phone_hash)
            return {
                'suggestedResponse': "No worries! Back to the main menu ??",
                'suggestion': "No worries! Back to the main menu ??",
                'flowAction': 'showMainMenu',
            }

        flow_name = flow_state.get('flow', '')
        step = flow_state.get('step', '')
        data = flow_state.get('data', {})
        flows = flow_config.get('flows', {})

        # -- Subscribe flow --
        if flow_name == 'subscribe':
            sub_prompts = flows.get('subscribe', {})

            if step == 'awaiting_name':
                name = message_content.strip()
                if len(name) < 2 or len(name) > 100:
                    return {
                        'suggestedResponse': "Please enter a valid name (2-100 characters).",
                        'suggestion': "Please enter a valid name (2-100 characters).",
                    }
                data['name'] = name
                prompt = sub_prompts.get('step_email', 'Your email address?').format(name=name)
                _save_flow_state(phone_hash, 'subscribe', 'awaiting_email', data)
                return {
                    'suggestedResponse': prompt,
                    'suggestion': prompt,
                }

            if step == 'awaiting_email':
                email = message_content.strip()
                if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
                    msg = sub_prompts.get('invalid_email', "Invalid email. Try again?")
                    return {
                        'suggestedResponse': msg,
                        'suggestion': msg,
                    }
                data['email'] = email
                # Skip phone step if sender's WhatsApp phone is available
                if sender_phone:
                    data['phone'] = sender_phone
                    _save_subscriber(data, phone_hash, request_id)
                    _clear_flow_state(phone_hash)
                    done_msg = sub_prompts.get('done', "You're all set! ?").format(name=data.get('name', ''))
                    return {
                        'suggestedResponse': done_msg,
                        'suggestion': done_msg,
                        'flowAction': 'showOptions',
                    }
                prompt = sub_prompts.get('step_phone', 'Phone number with country code?')
                _save_flow_state(phone_hash, 'subscribe', 'awaiting_phone', data)
                return {
                    'suggestedResponse': prompt,
                    'suggestion': prompt,
                }

            if step == 'awaiting_phone':
                phone = message_content.strip()
                if not re.match(r'^\+?\d[\d\s\-]{7,18}$', phone):
                    msg = sub_prompts.get('invalid_phone', "Invalid phone. Try again?")
                    return {
                        'suggestedResponse': msg,
                        'suggestion': msg,
                    }
                data['phone'] = phone
                # Save subscriber to contacts table
                _save_subscriber(data, phone_hash, request_id)
                _clear_flow_state(phone_hash)
                done_msg = sub_prompts.get('done', "You're all set! \u2705").format(name=data.get('name', ''))
                return {
                    'suggestedResponse': done_msg,
                    'suggestion': done_msg,
                    'flowAction': 'showOptions',
                }

        # -- Pay flow (replaced by instant sendPendingPayments flow) --
        if flow_name == 'pay':
            _clear_flow_state(phone_hash)
            return {
                'suggestedResponse': '',
                'suggestion': '',
                'flowAction': 'sendPendingPayments',
                'paymentCustomerPhone': sender_phone,
            }

        # -- Toggle flows (audio/notifications) --
        if flow_name in ('toggle_audio', 'toggle_notifications'):
            toggles = flow_config.get('toggles', {})
            toggle_type = 'audio' if flow_name == 'toggle_audio' else 'notifications'

            if content_lower in ('on', 'yes', '1'):
                _save_toggle_preference(phone_hash, toggle_type, True)
                _clear_flow_state(phone_hash)
                msg = toggles.get(f'{toggle_type}_on', f'{toggle_type} enabled!')
                return {
                    'suggestedResponse': msg,
                    'suggestion': msg,
                    'flowAction': 'showOptions',
                }
            elif content_lower in ('off', 'no', '0'):
                _save_toggle_preference(phone_hash, toggle_type, False)
                _clear_flow_state(phone_hash)
                msg = toggles.get(f'{toggle_type}_off', f'{toggle_type} disabled.')
                return {
                    'suggestedResponse': msg,
                    'suggestion': msg,
                    'flowAction': 'showOptions',
                }
            else:
                # Re-prompt
                status = 'ON' if history.get(f'{toggle_type}Enabled', False) else 'OFF'
                msg = toggles.get(f'{toggle_type}_prompt', f'Reply ON or OFF.').format(status=status)
                return {
                    'suggestedResponse': msg,
                    'suggestion': msg,
                }

    # -- "menu" keyword trigger - show main menu on demand --
    if content_lower in ('menu', 'main menu', 'show menu', 'hi', 'hello'):
        greeting = flow_config.get('welcome', {}).get('text', '') if not history.get('messages') else flow_config.get('welcomeBack', {}).get('text', "Here's the menu ??")
        return {
            'suggestedResponse': greeting or "Here's the menu ??",
            'suggestion': greeting or "Here's the menu ??",
            'flowAction': 'showMainMenu',
        }

    # -- Keyword-based pay flow trigger --
    PAY_KEYWORDS = {
        'pay', 'payment', 'i want to pay', 'make payment', 'make a payment',
        'send payment', 'pay now', 'pay bill', 'bill pay', 'pay due',
        'pay dues', 'pending payment', 'pending due', 'bhugtan', 'paisa',
        'rupees', 'amount pay', 'pay amount', 'invoice', 'pay invoice',
    }
    if content_lower in PAY_KEYWORDS or any(kw in content_lower for kw in ('want to pay', 'make payment', 'pay my', 'pay the', 'pay for')):
        # Instant pay flow - send all pending invoices as WhatsApp Pay orders
        return {
            'suggestedResponse': '',
            'suggestion': '',
            'flowAction': 'sendPendingPayments',
            'paymentCustomerPhone': sender_phone,
        }

    # -- Main menu / store item selected --
    if content_lower.startswith('menu_') or content_lower.startswith('store_'):
        menu_responses = flow_config.get('menuResponses', {})
        item = menu_responses.get(content_lower)
        if item:
            action = item.get('action', '')

            # Show language picker (Step 1: region picker)
            if action == 'show_language_picker':
                lp_config = _get_language_picker_config_from_db()
                return {
                    'suggestedResponse': '?? Choose your region to see available languages ??',
                    'showLanguagePicker': True,
                    'languagePickerStep': 'region',
                    'regionOptions': lp_config['regionPicker'],
                }

            # Show sub-menu
            if action == 'show_sub_menu':
                sub_menus = flow_config.get('subMenus', {})
                sub_menu = sub_menus.get(content_lower)
                if sub_menu:
                    return {
                        'suggestedResponse': sub_menu.get('body', 'Choose an option ??'),
                        'suggestion': sub_menu.get('body', 'Choose an option ??'),
                        'flowAction': 'showSubMenu',
                        'subMenuConfig': sub_menu,
                    }
                return None

            # Back to main menu (from sub-menus)
            if action == 'show_main_menu':
                return {
                    'suggestedResponse': "Here's the menu ??",
                    'suggestion': "Here's the menu ??",
                    'flowAction': 'showMainMenu',
                }

            # Start subscribe flow
            if action == 'start_subscribe_flow':
                flows_config = flow_config.get('flows', {}).get('subscribe', {})
                prompt = flows_config.get('step_name', "What's your full name?")
                _save_flow_state(phone_hash, 'subscribe', 'awaiting_name', {})
                return {
                    'suggestedResponse': prompt,
                    'suggestion': prompt,
                }

            # Start pay flow - check for pending dues first
            if action == 'start_pay_flow':
                # Instant pay flow - send all pending invoices as WhatsApp Pay orders
                return {
                    'suggestedResponse': '',
                    'suggestion': '',
                    'flowAction': 'sendPendingPayments',
                    'paymentCustomerPhone': sender_phone,
                }

            # Toggle audio
            if action == 'toggle_audio':
                toggles = flow_config.get('toggles', {})
                status = 'ON' if history.get('audioEnabled', False) else 'OFF'
                msg = toggles.get('audio_prompt', 'Reply ON or OFF.').format(status=status)
                _save_flow_state(phone_hash, 'toggle_audio', 'awaiting_toggle', {})
                return {
                    'suggestedResponse': msg,
                    'suggestion': msg,
                }

            # Toggle notifications
            if action == 'toggle_notifications':
                toggles = flow_config.get('toggles', {})
                status = 'ON' if history.get('notificationsEnabled', True) else 'OFF'
                msg = toggles.get('notifications_prompt', 'Reply ON or OFF.').format(status=status)
                _save_flow_state(phone_hash, 'toggle_notifications', 'awaiting_toggle', {})
                return {
                    'suggestedResponse': msg,
                    'suggestion': msg,
                }

            # Human handoff
            if action == 'human_handoff':
                _clear_flow_state(phone_hash)
                return {
                    'suggestedResponse': item.get('text', ''),
                    'suggestion': item.get('text', ''),
                    'flowAction': 'humanHandoff',
                    'humanHandoff': True,
                    'intent': 'human_handoff_requested',
                }

            # Default: text response + CTA + show options
            return {
                'suggestedResponse': item.get('text', ''),
                'suggestion': item.get('text', ''),
                'flowAction': 'showOptions',
                'cta': item.get('cta'),
            }
        return None

    # -- Options: Do more --
    if content_lower == 'opt_do_more':
        do_more = flow_config.get('doMore', {})
        return {
            'suggestedResponse': do_more.get('text', ''),
            'suggestion': do_more.get('text', ''),
            'flowAction': 'showMainMenu',
        }

    # -- Options: Done --
    if content_lower == 'opt_done':
        done = flow_config.get('done', {})
        return {
            'suggestedResponse': done.get('text', ''),
            'suggestion': done.get('text', ''),
            'flowAction': 'showRating',
        }

    # -- Rating selection --
    if content_lower.startswith('rate_'):
        rating_responses = flow_config.get('ratingResponses', {})
        response_text = rating_responses.get(content_lower, 'Thanks for your feedback! \U0001f49b')
        _save_rating(phone_hash, content_lower, request_id)
        return {
            'suggestedResponse': response_text,
            'suggestion': response_text,
            'flowAction': 'end',
        }

    return None


# ============================================================================
# CRITICAL IMPROVEMENTS - PRODUCTION READY
# ============================================================================

# -- Retry Logic with Exponential Backoff --
def retry_on_error(max_retries=3, backoff_factor=2):
    """Retry decorator with exponential backoff for transient errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ClientError, ConnectionError) as e:
                    if attempt == max_retries - 1:
                        logger.error(json.dumps({
                            'event': 'retry_exhausted',
                            'function': func.__name__,
                            'error': str(e),
                            'attempts': max_retries
                        }))
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(json.dumps({
                        'event': 'retry_attempt',
                        'function': func.__name__,
                        'attempt': attempt + 1,
                        'wait_time': wait_time,
                        'error': str(e)
                    }))
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator


# -- Parameter Validation --
def validate_phone(phone: str) -> Tuple[bool, str]:
    """Validate phone number (E.164 format)"""
    if not phone:
        return False, "Phone number is required"
    
    clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # Check E.164 format: +[country code][number]
    pattern = r'^\+[1-9]\d{1,14}$'
    if not re.match(pattern, clean):
        return False, f"Invalid phone format. Use: +[country][number] (e.g., +919876543210). Got: {phone}"
    
    return True, clean


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email address"""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, f"Invalid email format: {email}"
    
    return True, email.lower()


def validate_contact_id(contact_id: str) -> Tuple[bool, str]:
    """Validate contact ID (UUID format)"""
    if not contact_id:
        return False, "Contact ID is required"
    
    try:
        uuid.UUID(contact_id)
        return True, contact_id
    except ValueError:
        return False, f"Invalid contact ID format: {contact_id}"


# -- Audit Logging --
def log_tool_execution(tool_name: str, params: Dict, result: Any, duration: float, 
                       session_id: str, status: str = 'success', error: str = ''):
    """Log every tool execution for audit trail and monitoring"""
    try:
        audit_table = dynamodb.Table('stack-wecare-digital-AuditLog')
        
        # Truncate large results
        result_str = json.dumps(result, default=str)
        if len(result_str) > 1000:
            result_str = result_str[:1000] + '... [truncated]'
        
        audit_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'timestamp': Decimal(str(int(time.time()))),
            'toolName': tool_name,
            'parameters': json.dumps(params, default=str)[:500],
            'result': result_str,
            'duration': Decimal(str(round(duration, 3))),
            'sessionId': session_id,
            'status': status,
            'error': error[:500] if error else '',
            'context': 'internal-admin',
            'expiresAt': Decimal(str(int(time.time()) + (90 * 24 * 3600)))  # 90 days TTL
        })
        
        # Send CloudWatch metrics
        try:
            cloudwatch = boto3.client('cloudwatch')
            cloudwatch.put_metric_data(
                Namespace='FloatingAgent',
                MetricData=[
                    {
                        'MetricName': 'ToolExecutionTime',
                        'Value': duration * 1000,
                        'Unit': 'Milliseconds',
                        'Dimensions': [{'Name': 'ToolName', 'Value': tool_name}]
                    },
                    {
                        'MetricName': 'ToolExecutionCount',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'ToolName', 'Value': tool_name},
                            {'Name': 'Status', 'Value': status}
                        ]
                    }
                ]
            )
        except Exception as cw_error:
            logger.warning(f"CloudWatch metric failed: {cw_error}")
            
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'audit_log_failed',
            'error': str(e),
            'toolName': tool_name
        }))


# -- Rate Limiting --
def check_rate_limit(session_id: str, tool_name: str, limit: int = 10, window: int = 60) -> Tuple[bool, str]:
    """Check if rate limit exceeded (10 requests per minute per tool)"""
    try:
        table = dynamodb.Table('stack-wecare-digital-RateLimitTable')
        key = f"{session_id}:{tool_name}"
        now = int(time.time())
        window_start = now - window
        
        # Get current count
        response = table.get_item(Key={'id': key})
        item = response.get('Item', {})
        
        # Clean old timestamps
        timestamps = [int(ts) for ts in item.get('timestamps', []) if int(ts) > window_start]
        
        # Check limit
        if len(timestamps) >= limit:
            return False, f"Rate limit exceeded. Max {limit} requests per {window} seconds. Please wait a moment."
        
        # Add new timestamp
        timestamps.append(now)
        table.put_item(Item={
            'id': key,
            'timestamps': timestamps,
            'expiresAt': Decimal(str(now + window))
        })
        
        return True, ""
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True, ""  # Fail open


# -- Better Error Messages --
ERROR_MESSAGES = {
    'contact_not_found': '\u274c Contact not found.\n\n\U0001f4a1 Try:\n- Search by phone: "find +919876543210"\n- Search by name: "find Jignesh"\n- Create new: "create contact John +919876543210"',
    'invalid_phone': '\u274c Invalid phone number.\n\n\U0001f4a1 Use international format:\n- India: +919876543210\n- USA: +14155552671\n- UK: +447447840003',
    'invalid_email': '? Invalid email address.\n\n?? Use format: name@domain.com',
    'rate_limit': '?? Too many requests.\n\n?? Please wait a moment before trying again.',
    'service_unavailable': '? Service temporarily unavailable.\n\n?? Please try again in a few moments.',
    'invalid_parameters': '? Invalid parameters.\n\n?? Type "help" to see available commands.',
    'permission_denied': '? Permission denied.\n\n?? This action requires admin privileges.',
    'message_too_long': '? Message too long.\n\n?? WhatsApp messages must be under 4096 characters.',
}


def format_error(error_type: str, details: str = '') -> str:
    """Format user-friendly error message"""
    base_msg = ERROR_MESSAGES.get(error_type, '? An error occurred.\n\n?? Type "help" for assistance.')
    if details:
        return f"{base_msg}\n\nDetails: {details}"
    return base_msg


# -- Pay helpers --

def _r(msg: str) -> Dict:
    """Shorthand: return a simple suggestedResponse/suggestion pair."""
    return {'suggestedResponse': msg, 'suggestion': msg}


PURPOSE_MAP = {
    '1': 'BNB Club - Travel',
    '2': 'No Fault - ODR',
    '3': 'Expo Week - Events',
    '4': 'Ritual Guru - Puja',
    '5': 'Legal Champ - Docs',
    '6': 'Swdhya - Samvad',
    '7': 'Gift Card',
    '8': 'Advance Payment',
    '9': 'Service Fee',
    '10': 'Consultation',
}


# -- Customer profile helpers (for returning customers) --

def _load_customer_profile(phone_hash: str) -> Dict:
    """Load saved customer profile from ConversationHistoryTable."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        resp = table.get_item(Key={'phoneHash': phone_hash}, ProjectionExpression='customerProfile')
        item = resp.get('Item', {})
        profile_str = item.get('customerProfile', '')
        if profile_str:
            return json.loads(profile_str) if isinstance(profile_str, str) else profile_str
    except Exception as e:
        logger.warning(json.dumps({'event': 'customer_profile_load_error', 'error': str(e)}))
    return {}


def _load_contact_as_profile(sender_phone: str) -> Dict:
    """Try to load customer details from contacts table as a profile fallback."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '')
        for variant in [f'+{clean_phone}', clean_phone]:
            try:
                resp = contacts_table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :phone',
                    ExpressionAttributeValues={':phone': variant},
                    Limit=1
                )
                items = resp.get('Items', [])
                if items:
                    c = items[0]
                    name = c.get('customerName', c.get('name', ''))
                    if name:
                        return {
                            'customer_name': name,
                            'customer_phone': sender_phone,
                            'customer_email': c.get('customerEmail', c.get('email', '')),
                            'shipping_address': c.get('shippingAddress', ''),
                            'billing_address': c.get('billingAddress', ''),
                        }
            except Exception:
                pass
    except Exception as e:
        logger.warning(json.dumps({'event': 'contact_profile_load_error', 'error': str(e)}))
    return {}


def _save_customer_profile(phone_hash: str, profile: Dict) -> None:
    """Save customer profile to ConversationHistoryTable for reuse."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET customerProfile = :cp, updatedAt = :now',
            ExpressionAttributeValues={
                ':cp': json.dumps(profile),
                ':now': Decimal(str(int(time.time()))),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({'event': 'customer_profile_save_error', 'error': str(e)}))


def _update_contact_with_customer_info(sender_phone: str, profile: Dict, request_id: str) -> None:
    """Update the contacts table with customer billing/shipping info."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '')
        # Find contact by phone
        existing = None
        for variant in [f'+{clean_phone}', clean_phone]:
            try:
                resp = contacts_table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :phone',
                    ExpressionAttributeValues={':phone': variant},
                    Limit=1
                )
                items = resp.get('Items', [])
                if items:
                    existing = items[0]
                    break
            except Exception:
                pass

        now = Decimal(str(int(time.time())))
        update_parts = []
        attr_names = {}
        attr_values = {':now': now}

        field_map = {
            'customer_name': ('customerName', '#cn'),
            'customer_email': ('customerEmail', '#ce'),
            'billing_address': ('billingAddress', '#ba'),
            'shipping_address': ('shippingAddress', '#sa'),
        }
        for data_key, (db_field, alias) in field_map.items():
            val = profile.get(data_key, '')
            if val:
                update_parts.append(f'{alias} = :{db_field}')
                attr_names[alias] = db_field
                attr_values[f':{db_field}'] = val

        if not update_parts:
            return

        update_parts.append('updatedAt = :now')

        if existing:
            contacts_table.update_item(
                Key={'id': existing['id']},
                UpdateExpression='SET ' + ', '.join(update_parts),
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
            )
        else:
            # Create new contact with customer info
            contact_id = str(uuid.uuid4())
            item = {
                'id': contact_id,
                'phone': clean_phone,
                'channel': 'whatsapp',
                'source': 'payment_flow',
                'createdAt': now,
                'updatedAt': now,
            }
            for data_key, (db_field, _) in field_map.items():
                val = profile.get(data_key, '')
                if val:
                    item[db_field] = val
            if profile.get('customer_name'):
                item['name'] = profile['customer_name']
            contacts_table.put_item(Item=item)

        logger.info(json.dumps({
            'event': 'contact_customer_info_updated',
            'phone': clean_phone,
            'requestId': request_id,
        }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'contact_customer_info_error',
            'error': str(e),
            'requestId': request_id,
        }))


# -- Flow state helpers (DynamoDB) --

def _save_flow_state(phone_hash: str, flow: str, step: str, data: Dict) -> None:
    """Save conversational flow state to DynamoDB."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET flowState = :fs, updatedAt = :now',
            ExpressionAttributeValues={
                ':fs': json.dumps({'flow': flow, 'step': step, 'data': data}),
                ':now': Decimal(str(int(time.time()))),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'flow_state_save_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))


def _clear_flow_state(phone_hash: str) -> None:
    """Clear conversational flow state from DynamoDB."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='REMOVE flowState',
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'flow_state_clear_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))


def _save_subscriber(data: Dict, phone_hash: str, request_id: str) -> None:
    """Save subscribe form data to contacts table."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        now = int(time.time())
        contact_id = str(uuid.uuid4())

        # Check for existing contact by phone
        clean_phone = data.get('phone', '').replace(' ', '').replace('-', '')
        existing = None
        try:
            resp = contacts_table.query(
                IndexName='phone-index',
                KeyConditionExpression='phone = :phone',
                ExpressionAttributeValues={':phone': clean_phone},
                Limit=1
            )
            items = resp.get('Items', [])
            if items:
                existing = items[0]
        except Exception:
            pass

        if existing:
            # Update existing contact
            contacts_table.update_item(
                Key={'id': existing['id']},
                UpdateExpression='SET #n = :name, email = :email, updatedAt = :now, subscribedViaBot = :t',
                ExpressionAttributeNames={'#n': 'name'},
                ExpressionAttributeValues={
                    ':name': data.get('name', ''),
                    ':email': data.get('email', ''),
                    ':now': Decimal(str(now)),
                    ':t': True,
                }
            )
            logger.info(json.dumps({
                'event': 'subscriber_updated',
                'contactId': existing['id'],
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
        else:
            # Create new contact
            contacts_table.put_item(Item={
                'id': contact_id,
                'name': data.get('name', ''),
                'email': data.get('email', ''),
                'phone': clean_phone,
                'channel': 'whatsapp',
                'source': 'bot_subscribe',
                'subscribedViaBot': True,
                'createdAt': Decimal(str(now)),
                'updatedAt': Decimal(str(now)),
            })
            logger.info(json.dumps({
                'event': 'subscriber_created',
                'contactId': contact_id,
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'subscriber_save_error',
            'error': str(e),
            'phoneHash': phone_hash,
            'requestId': request_id
        }))


def _save_toggle_preference(phone_hash: str, toggle_type: str, enabled: bool) -> None:
    """Save audio/notification toggle preference to DynamoDB."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        field = 'audioEnabled' if toggle_type == 'audio' else 'notificationsEnabled'
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression=f'SET {field} = :val, updatedAt = :now',
            ExpressionAttributeValues={
                ':val': enabled,
                ':now': Decimal(str(int(time.time()))),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'toggle_save_error',
            'error': str(e),
            'toggleType': toggle_type,
            'phoneHash': phone_hash
        }))


def _save_rating(phone_hash: str, rating: str, request_id: str) -> None:
    """Save user rating to conversation history."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET lastRating = :r, lastRatingAt = :t',
            ExpressionAttributeValues={
                ':r': rating,
                ':t': Decimal(str(int(time.time()))),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'rating_save_error',
            'error': str(e),
            'phoneHash': phone_hash,
            'requestId': request_id
        }))


def _check_pending_payments(phone_hash: str, request_id: str, sender_phone: str = '') -> Optional[List[Dict]]:
    """
    Check if user has any pending payment requests by querying the Messages table.
    Returns a list of pending payments [{ref, amount, item, createdAt}] or None.
    Queries by senderPhone (contactId GSI or scan) for messageType=payment_request, status=pending.
    """
    try:
        # First try the Messages table for full payment history
        if sender_phone:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '')

            # Query GSI senderPhone-status-index (falls back to scan if GSI missing)
            try:
                try:
                    resp = messages_table.query(
                        IndexName='senderPhone-status-index',
                        KeyConditionExpression='senderPhone = :phone AND #s = :pending',
                        FilterExpression='messageType = :mt',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':phone': clean_phone,
                            ':mt': 'payment_request',
                            ':pending': 'pending',
                        },
                        Limit=10,
                        ScanIndexForward=False,
                    )
                except Exception:
                    # Fallback to scan if GSI not yet active
                    resp = messages_table.scan(
                        FilterExpression='senderPhone = :phone AND messageType = :mt AND #s = :pending',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':phone': clean_phone,
                            ':mt': 'payment_request',
                            ':pending': 'pending',
                        },
                        Limit=10,
                    )
                items = resp.get('Items', [])
                if items:
                    dues = []
                    for item in items:
                        total_paise = float(item.get('paymentTotal', item.get('paymentAmount', 0)))
                        total_rs = total_paise / 100 if total_paise > 500 else total_paise  # handle paise vs rupees
                        dues.append({
                            'ref': item.get('paymentReferenceId', item.get('messageId', 'N/A')),
                            'amount': total_rs,
                            'item': item.get('paymentItemName', 'Services/Goods'),
                            'createdAt': int(float(item.get('createdAt', 0))),
                        })
                    # Sort by most recent first
                    dues.sort(key=lambda x: x['createdAt'], reverse=True)
                    return dues
            except Exception as scan_err:
                logger.warning(json.dumps({
                    'event': 'pending_payment_scan_error',
                    'error': str(scan_err),
                    'requestId': request_id
                }))

        # Fallback: check ConversationHistoryTable for last payment ref
        table = dynamodb.Table(CONVERSATION_TABLE)
        resp = table.get_item(Key={'phoneHash': phone_hash})
        item = resp.get('Item', {})
        last_payment_ref = item.get('lastPaymentRef', '')
        last_payment_amount = float(item.get('lastPaymentAmount', 0))
        last_payment_status = item.get('lastPaymentStatus', '')
        if last_payment_ref and last_payment_status == 'pending':
            return [{
                'ref': last_payment_ref,
                'amount': last_payment_amount,
                'item': 'Previous Payment',
                'createdAt': int(float(item.get('lastPaymentAt', 0))),
            }]
        return None
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'pending_payment_check_error',
            'error': str(e),
            'phoneHash': phone_hash,
            'requestId': request_id
        }))
        return None


def _save_language_preference(phone_hash: str, language: str) -> None:
    """Save the user's preferred language to their conversation history record."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        now = int(time.time())
        ttl = now + (CONVERSATION_TTL_HOURS * 3600)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET preferredLanguage = :lang, updatedAt = :now, expiresAt = :ttl',
            ExpressionAttributeValues={
                ':lang': language,
                ':now': Decimal(str(now)),
                ':ttl': Decimal(str(ttl)),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'language_preference_save_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))


# ============================================================================
# CONVERSATION HISTORY (DynamoDB)
# ============================================================================

def _hash_phone(phone: str) -> str:
    """Hash phone number for privacy-safe DynamoDB key."""
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    return hashlib.sha256(clean.encode()).hexdigest()[:32]


def _load_conversation_history(phone_hash: str) -> Dict:
    """Load conversation history from DynamoDB."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        response = table.get_item(Key={'phoneHash': phone_hash})
        item = response.get('Item')
        if not item:
            return {'messages': [], 'messageCount': 0}

        messages_json = item.get('messages', '[]')
        messages = json.loads(messages_json) if isinstance(messages_json, str) else messages_json
        message_count = int(item.get('messageCount', 0))
        updated_at = float(item.get('updatedAt', 0))
        preferred_language = item.get('preferredLanguage', '')

        # Load flow state for multi-step conversations
        flow_state_json = item.get('flowState', '')
        flow_state = json.loads(flow_state_json) if flow_state_json else None

        # Load toggle preferences
        audio_enabled = item.get('audioEnabled', False)
        notifications_enabled = item.get('notificationsEnabled', True)

        return {
            'messages': messages,
            'messageCount': message_count,
            'updatedAt': updated_at,
            'preferredLanguage': preferred_language,
            'flowState': flow_state,
            'audioEnabled': audio_enabled,
            'notificationsEnabled': notifications_enabled,
        }
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'history_load_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))
        return {'messages': [], 'messageCount': 0}


def _save_conversation_history(phone_hash: str, messages: List[Dict], message_count: int) -> None:
    """Save conversation history to DynamoDB with TTL. Uses update_item to preserve flowState, audioEnabled, etc."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        now = int(time.time())
        ttl = now + (CONVERSATION_TTL_HOURS * 3600)

        # Trim to max history size
        trimmed = messages[-(MAX_HISTORY_MESSAGES * 2):]

        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET messages = :msgs, messageCount = :cnt, updatedAt = :now, expiresAt = :ttl',
            ExpressionAttributeValues={
                ':msgs': json.dumps(trimmed, default=str),
                ':cnt': message_count,
                ':now': Decimal(str(now)),
                ':ttl': Decimal(str(ttl)),
            }
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'history_save_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))


# ============================================================================
# PROCESSING LOCK (prevents duplicate AI calls per contact)
# ============================================================================

def _acquire_processing_lock(phone_hash: str) -> bool:
    """
    Acquire processing lock for a contact.
    Returns True if lock acquired, False if already locked.
    Uses DynamoDB conditional put with TTL for auto-expiry.
    """
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        now = int(time.time())
        lock_expiry = now + PROCESSING_LOCK_TTL_SECONDS

        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET processingLock = :lock, lockExpiresAt = :exp',
            ConditionExpression='attribute_not_exists(processingLock) OR processingLock = :false OR lockExpiresAt < :now',
            ExpressionAttributeValues={
                ':lock': True,
                ':false': False,
                ':exp': Decimal(str(lock_expiry)),
                ':now': Decimal(str(now)),
            }
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.info(json.dumps({
            'event': 'processing_lock_busy',
            'phoneHash': phone_hash
        }))
        return False
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'processing_lock_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))
        # On error, allow processing (fail open)
        return True


def _release_processing_lock(phone_hash: str) -> None:
    """Release processing lock for a contact."""
    try:
        table = dynamodb.Table(CONVERSATION_TABLE)
        table.update_item(
            Key={'phoneHash': phone_hash},
            UpdateExpression='SET processingLock = :false',
            ExpressionAttributeValues={':false': False}
        )
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'processing_lock_release_error',
            'error': str(e),
            'phoneHash': phone_hash
        }))


# ============================================================================
# INTERNAL AGENT (unchanged from original)
# ============================================================================

def _invoke_bedrock_agent(user_message: str, agent_id: str, agent_alias: str, kb_id: str, request_id: str) -> str:
    """Invoke Bedrock Agent for internal admin response generation."""
    try:
        session_id = str(uuid.uuid4())
        detected_lang, lang_name = _detect_language(user_message)

        language_instruction = f"[RESPOND IN {lang_name.upper()} ONLY] "
        enhanced_message = language_instruction + user_message

        logger.info(json.dumps({
            'event': 'bedrock_agent_invoke',
            'agentId': agent_id,
            'sessionId': session_id,
            'messageLength': len(user_message),
            'detectedLanguage': lang_name,
            'requestId': request_id
        }))

        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias,
            sessionId=session_id,
            inputText=enhanced_message,
            enableTrace=False
        )

        completion = ""
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk_data = event['chunk']
                if 'bytes' in chunk_data:
                    completion += chunk_data['bytes'].decode('utf-8')

        if completion:
            logger.info(json.dumps({
                'event': 'bedrock_agent_success',
                'responseLength': len(completion),
                'detectedLanguage': lang_name,
                'requestId': request_id
            }))
            return completion.strip()

        # Fallback to KB only if kb_id is provided (external path)
        if kb_id:
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)

        # For internal agent (no KB), return empty to let caller handle
        return ""

    except Exception as e:
        logger.error(json.dumps({
            'event': 'bedrock_agent_error',
            'error': str(e),
            'requestId': request_id
        }))
        # Only use KB fallback if kb_id provided (external path)
        if kb_id:
            detected_lang, lang_name = _detect_language(user_message)
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)
        # For internal agent, return empty
        return ""


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================

def _detect_language(text: str) -> Tuple[str, str]:
    """Detect language from text using character patterns."""
    if not text:
        return ('en', 'English')

    if re.search(r'[\u0900-\u097F]', text):
        marathi_words = ['???', '???', '???', '??????', '?????']
        if any(word in text for word in marathi_words):
            return ('mr', 'Marathi')
        return ('hi', 'Hindi')

    if re.search(r'[\u0980-\u09FF]', text):
        return ('bn', 'Bengali')
    if re.search(r'[\u0B80-\u0BFF]', text):
        return ('ta', 'Tamil')
    if re.search(r'[\u0C00-\u0C7F]', text):
        return ('te', 'Telugu')
    if re.search(r'[\u0A80-\u0AFF]', text):
        return ('gu', 'Gujarati')

    hinglish_words = ['kya', 'hai', 'kaise', 'mujhe', 'aap', 'hum', 'tum', 'kab', 'kahan', 'kyun', 'nahi', 'haan', 'theek', 'accha', 'bahut']
    if sum(1 for word in hinglish_words if word in text.lower()) >= 2:
        return ('hi-Latn', 'Hinglish')

    return ('en', 'English')


# ============================================================================
# KB QUERY (for internal fallback - unchanged)
# ============================================================================

def _query_knowledge_base(user_message: str, kb_id: str, detected_lang: str, lang_name: str, request_id: str) -> str:
    """Direct Knowledge Base query with Nova Lite (internal fallback)."""
    try:
        prompt_template = f"""You are WECARE.DIGITAL's friendly AI assistant.

CRITICAL: You MUST respond ONLY in {lang_name}. Do not mix languages.

INSTRUCTIONS:
- Respond ONLY in {lang_name} language
- Keep responses SHORT (2-3 sentences max)
- Use 1-2 emojis for warmth
- Always mention the specific brand name
- End with a clear action (website, phone, or next step)

BRANDS:
- Travel/Hotels/Visa ? BNB Club (bnbclub.in)
- Documents/Registration/GST ? Legal Champ (legalchamp.in)
- Disputes/Complaints ? No Fault (nofault.in)
- Puja/Rituals ? Ritual Guru (ritualguru.in)
- Self-inquiry/Reflection ? Swdhya (swdhya.in)

CONTACT: +91 9330994400 | one@wecare.digital

CONTEXT FROM KNOWLEDGE BASE:
$search_results$

USER QUESTION ({lang_name}): $query$

Respond helpfully in {lang_name} and end with a specific action."""

        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': user_message},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': f'arn:aws:bedrock:us-east-1::foundation-model/{MODEL_ID}',
                    'generationConfiguration': {
                        'promptTemplate': {'textPromptTemplate': prompt_template}
                    }
                }
            }
        )

        output = response.get('output', {}).get('text', '')
        if output:
            return output.strip()
        return _get_fallback_response(lang_name)

    except Exception as e:
        logger.error(json.dumps({'event': 'kb_query_error', 'error': str(e), 'requestId': request_id}))
        return _get_fallback_response(lang_name)


# ============================================================================
# FALLBACK RESPONSES
# ============================================================================

def _get_fallback_response(lang_name: str = 'English') -> str:
    """Return a friendly fallback response in the detected language."""
    fallback_responses = {
        'Hindi': "??????! ?? WECARE.DIGITAL ?? ?????? ???? ?? ??? ???????? ?????? ?????? ?? ??? +91 9330994400 ?? ??? ???? ?? one@wecare.digital ?? ???? ????? ??",
        'Bengali': "???????! ?? WECARE.DIGITAL-? ??????? ???? ???? ???????? ????? ????????? ???? +91 9330994400-? ?? ???? ?? one@wecare.digital-? ???? ????? ??",
        'Hinglish': "Hi! ?? WECARE.DIGITAL se contact karne ke liye thanks. Quick help ke liye +91 9330994400 pe call karein ya one@wecare.digital pe email karein. ??",
        'Tamil': "???????! ?? WECARE.DIGITAL-? ??????? ?????????? ?????? ??????? ???????? +91 9330994400 ?????????? ?????? one@wecare.digital ?????????? ??????????. ??",
        'Telugu': "????????! ?? WECARE.DIGITAL ?? ???????????????? ??????????? ?????? ????? ???? +91 9330994400 ?? ???? ?????? ???? one@wecare.digital ?? ??????? ??????. ??",
        'Gujarati': "??????! ?? WECARE.DIGITAL ?? ?????? ???? ??? ????. ???? ??? ???? +91 9330994400 ?? ??? ??? ???? one@wecare.digital ?? ????? ???. ??",
        'Marathi': "???????! ?? WECARE.DIGITAL ?? ?????? ???????????? ???????? ??? ???????? +91 9330994400 ?? ??? ??? ????? one@wecare.digital ?? ???? ???. ??",
    }
    return fallback_responses.get(lang_name, "Hi! ?? Thanks for reaching out to WECARE.DIGITAL. For quick help, call us at +91 9330994400 or email one@wecare.digital. We're here to help! ??")



# ============================================================================
# ADDITIONAL TOOL IMPLEMENTATIONS FOR INTERNAL AGENT
# ============================================================================

def _tool_create_contact(params: Dict, request_id: str) -> Dict:
    """Create contact tool implementation."""
    name = params.get('name')
    phone = params.get('phone', '').strip()
    email = params.get('email', '').strip()
    
    if not name:
        return {'success': False, 'error': 'Name is required'}
    
    if not phone and not email:
        return {'success': False, 'error': 'At least phone or email is required'}
    
    # Validate email format if provided
    if email:
        valid_email, email_msg = validate_email(email)
        if not valid_email:
            return {'success': False, 'error': email_msg}
        email = email_msg  # normalized lowercase
    
    # Validate phone format if provided
    if phone:
        valid_phone, phone_msg = validate_phone(phone)
        if not valid_phone:
            return {'success': False, 'error': phone_msg}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        # Duplicate detection - scan for matching phone or email
        if phone:
            scan_result = contacts_table.scan(
                FilterExpression='phone = :p AND attribute_not_exists(deletedAt)',
                ExpressionAttributeValues={':p': phone},
                Limit=5
            )
            if scan_result.get('Items'):
                existing = scan_result['Items'][0]
                return {
                    'success': False,
                    'error': f'Contact with phone {phone} already exists: {existing.get("name")} (ID: {existing.get("id")})'
                }
        
        if email:
            scan_result = contacts_table.scan(
                FilterExpression='email = :e AND attribute_not_exists(deletedAt)',
                ExpressionAttributeValues={':e': email},
                Limit=5
            )
            if scan_result.get('Items'):
                existing = scan_result['Items'][0]
                return {
                    'success': False,
                    'error': f'Contact with email {email} already exists: {existing.get("name")} (ID: {existing.get("id")})'
                }
        
        contact_id = str(uuid.uuid4())
        now = int(time.time())
        
        contact = {
            'id': contact_id,
            'contactId': contact_id,
            'name': name,
            'phone': phone,
            'email': email,
            'optInWhatsApp': True,
            'optInSms': True,
            'optInEmail': True,
            'createdAt': now,
            'updatedAt': now
        }
        
        contacts_table.put_item(Item=contact)
        
        return {
            'success': True,
            'contactId': contact_id,
            'message': f'Contact "{name}" created successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_update_contact(params: Dict, request_id: str) -> Dict:
    """Update contact tool implementation."""
    contact_id = params.get('contactId')
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    # Validate contactId looks like a UUID (not a name)
    if len(contact_id) < 30 or '-' not in contact_id:
        return {'success': False, 'error': f'Invalid contactId format: "{contact_id}". Use search_contacts first to get the correct ID.'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        # First verify the contact exists
        existing = contacts_table.get_item(Key={'id': contact_id})
        if 'Item' not in existing:
            return {'success': False, 'error': f'Contact not found with ID: {contact_id}'}
        
        update_expr_parts = ['updatedAt = :now']
        expr_values = {':now': int(time.time())}
        expr_names = {}
        
        if params.get('name'):
            update_expr_parts.append('#n = :name')
            expr_values[':name'] = params['name']
            expr_names['#n'] = 'name'
        if params.get('phone'):
            update_expr_parts.append('phone = :phone')
            expr_values[':phone'] = params['phone']
        if params.get('email'):
            update_expr_parts.append('email = :email')
            expr_values[':email'] = params['email'].strip().lower()
        
        update_kwargs = {
            'Key': {'id': contact_id},
            'UpdateExpression': 'SET ' + ', '.join(update_expr_parts),
            'ExpressionAttributeValues': expr_values,
            'ReturnValues': 'ALL_NEW'
        }
        if expr_names:
            update_kwargs['ExpressionAttributeNames'] = expr_names
        
        result = contacts_table.update_item(**update_kwargs)
        updated = result.get('Attributes', {})
        
        return {
            'success': True,
            'contactId': contact_id,
            'name': updated.get('name'),
            'email': updated.get('email'),
            'phone': updated.get('phone'),
            'message': 'Contact updated successfully'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_whatsapp_buttons(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp interactive buttons message."""
    contact_id = params.get('contactId')
    body_text = params.get('bodyText')
    buttons = params.get('buttons', [])
    
    if not contact_id or not body_text or not buttons:
        return {'success': False, 'error': 'contactId, bodyText, and buttons are required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    # Button count validation (WhatsApp max 3)
    if len(buttons) > 3:
        return {'success': False, 'error': f'Maximum 3 buttons allowed, got {len(buttons)}. Remove some buttons.'}
    
    if len(buttons) == 0:
        return {'success': False, 'error': 'At least 1 button is required'}
    
    # Validate button structure
    for i, btn in enumerate(buttons):
        if not isinstance(btn, dict) or not btn.get('id') or not btn.get('title'):
            return {'success': False, 'error': f'Button {i+1} must have "id" and "title" fields'}
        if len(btn['title']) > 20:
            return {'success': False, 'error': f'Button {i+1} title exceeds 20 char limit: "{btn["title"]}"'}
    
    try:
        # Build interactive message payload
        interactive_payload = {
            'type': 'button',
            'body': {'text': body_text},
            'action': {
                'buttons': [{'type': 'reply', 'reply': btn} for btn in buttons[:3]]  # Max 3 buttons
            }
        }
        
        if params.get('headerText'):
            interactive_payload['header'] = {'type': 'text', 'text': params['headerText']}
        if params.get('footerText'):
            interactive_payload['footer'] = {'text': params['footerText']}
        
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'interactive': interactive_payload
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'message': 'Interactive button message sent'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_whatsapp_list(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp interactive list message."""
    contact_id = params.get('contactId')
    body_text = params.get('bodyText')
    button_text = params.get('buttonText')
    sections = params.get('sections', [])
    
    if not all([contact_id, body_text, button_text, sections]):
        return {'success': False, 'error': 'contactId, bodyText, buttonText, and sections are required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    # Button text max 20 chars
    if len(button_text) > 20:
        return {'success': False, 'error': f'buttonText exceeds 20 char limit: "{button_text}"'}
    
    # Section validation (max 10 sections, each with max 10 rows)
    if len(sections) > 10:
        return {'success': False, 'error': f'Maximum 10 sections allowed, got {len(sections)}'}
    
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            return {'success': False, 'error': f'Section {i+1} must be an object with title and rows'}
        rows = section.get('rows', [])
        if not rows:
            return {'success': False, 'error': f'Section {i+1} must have at least 1 row'}
        if len(rows) > 10:
            return {'success': False, 'error': f'Section {i+1} exceeds 10 row limit'}
    
    try:
        interactive_payload = {
            'type': 'list',
            'body': {'text': body_text},
            'action': {
                'button': button_text,
                'sections': sections
            }
        }
        
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'interactive': interactive_payload
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'message': 'Interactive list message sent'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_whatsapp_pay(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp Pay interactive payment request."""
    contact_id = params.get('contactId')
    amount = params.get('amount')
    description = params.get('description')
    currency = params.get('currency', 'INR')
    expiry_minutes = params.get('expiryMinutes', 60)
    reference_id = params.get('referenceId', f'PAY-{int(time.time())}')

    if not all([contact_id, amount, description]):
        return {'success': False, 'error': 'contactId, amount, and description are required'}

    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}

    if not isinstance(amount, (int, float)) or amount <= 0:
        return {'success': False, 'error': 'amount must be a positive number'}

    try:
        # Build WhatsApp interactive payment message
        interactive_payload = {
            'type': 'button',
            'body': {'text': f'Payment Request: {description}\nAmount: {currency} {amount}\nRef: {reference_id}'},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': f'pay_{reference_id}', 'title': f'Pay {currency} {amount}'}},
                    {'type': 'reply', 'reply': {'id': f'decline_{reference_id}', 'title': 'Decline'}}
                ]
            }
        }

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'interactive': interactive_payload
            })
        }

        response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))

        logger.info(json.dumps({
            'event': 'whatsapp_pay_sent',
            'contactId': contact_id,
            'amount': amount,
            'currency': currency,
            'referenceId': reference_id,
            'requestId': request_id
        }))

        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'referenceId': reference_id,
            'message': f'Payment request sent: {currency} {amount} for {description}'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_make_voice_call(params: Dict, request_id: str) -> Dict:
    """Make voice call with TTS or pre-recorded audio."""
    contact_id = params.get('contactId')
    message = params.get('message')
    audio_url = params.get('audioUrl')
    language = params.get('language', 'en')
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    if not message and not audio_url:
        return {'success': False, 'error': 'Either message (for TTS) or audioUrl is required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'message': message,
                'audioUrl': audio_url,
                'language': language
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-voice-aws',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'callId': result_body.get('callId'),
            'message': 'Voice call initiated'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_sms(params: Dict, request_id: str) -> Dict:
    """Send SMS tool implementation."""
    contact_id = params.get('contactId')
    message = params.get('message')
    
    if not contact_id or not message:
        return {'success': False, 'error': 'contactId and message are required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': message
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-sms',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': 'sent'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_email(params: Dict, request_id: str) -> Dict:
    """Send email tool implementation."""
    contact_id = params.get('contactId')
    subject = params.get('subject')
    message = params.get('message')
    
    if not all([contact_id, subject, message]):
        return {'success': False, 'error': 'contactId, subject, and message are required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'subject': subject,
                'content': message
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-email',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'status': 'sent'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_schedule_message(params: Dict, request_id: str) -> Dict:
    """Schedule message tool implementation."""
    contact_id = params.get('contactId')
    message = params.get('message')
    scheduled_time = params.get('scheduledTime')
    channel = params.get('channel', 'whatsapp')
    
    if not all([contact_id, message, scheduled_time, channel]):
        return {'success': False, 'error': 'contactId, message, scheduledTime, and channel are required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': message,
                'scheduledTime': scheduled_time,
                'channel': channel
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-scheduled-messages',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'scheduleId': result_body.get('scheduleId'),
            'message': f'Message scheduled for {scheduled_time}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_list_scheduled_messages(params: Dict, request_id: str) -> Dict:
    """List scheduled messages for a contact or all pending."""
    try:
        dynamodb_res = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        table = dynamodb_res.Table(os.environ.get('SCHEDULED_MESSAGES_TABLE', 'stack-wecare-digital-ScheduledMessagesTable'))
        contact_id = params.get('contactId', '')
        status_filter = params.get('status', 'PENDING')

        if contact_id:
            # contactId-index doesn't exist yet — fall back to scan with filter
            response = table.scan(
                FilterExpression='contactId = :cid AND #s = :st',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':cid': contact_id, ':st': status_filter},
                Limit=50,
            )
        else:
            response = table.query(
                IndexName='status-scheduledAt-index',
                KeyConditionExpression='#s = :st',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':st': status_filter},
                Limit=50,
            )

        items = response.get('Items', [])
        messages = []
        for item in items:
            messages.append({
                'scheduledId': item.get('scheduledId', item.get('id', '')),
                'contactId': item.get('contactId', ''),
                'contactName': item.get('contactName', ''),
                'templateName': item.get('templateName', ''),
                'scheduledAt': item.get('scheduledAt', ''),
                'status': item.get('status', ''),
            })

        return {
            'success': True,
            'scheduledMessages': messages,
            'count': len(messages),
        }
    except Exception as e:
        logger.warning(f'[{request_id}] list_scheduled_messages error: {e}')
        return {'success': True, 'scheduledMessages': [], 'message': f'Could not query: {e}'}


def _tool_list_templates(params: Dict, request_id: str) -> Dict:
    """List WhatsApp message templates from Meta Graph API."""
    try:
        waba_id = params.get('wabaId', os.environ.get('WABA1_ID', '2094615664435155'))
        status_filter = params.get('status', '')  # APPROVED, PENDING, REJECTED
        limit = int(params.get('limit', 50))

        secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        meta_secret = os.environ.get('META_TOKEN_SECRET', 'wecare/meta-system-user-token')
        resp = secrets_client.get_secret_value(SecretId=meta_secret)
        secret_data = json.loads(resp['SecretString'])
        token = (secret_data.get('access_token') or '').strip()
        app_secret = (secret_data.get('app_secret') or '').strip()

        api_version = os.environ.get('META_API_VERSION', 'v25.0')
        url = f'https://graph.facebook.com/{api_version}/{waba_id}/message_templates?limit={limit}'
        if status_filter:
            url += f'&status={status_filter}'
        url += '&fields=name,status,category,language,components'

        if app_secret:
            import hmac as _hmac, hashlib as _hashlib
            proof = _hmac.new(app_secret.encode(), token.encode(), _hashlib.sha256).hexdigest()
            url += f'&appsecret_proof={proof}'

        import urllib.request
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read().decode('utf-8'))

        templates = []
        for t in result.get('data', []):
            templates.append({
                'name': t.get('name', ''),
                'status': t.get('status', ''),
                'category': t.get('category', ''),
                'language': t.get('language', ''),
            })

        return {
            'success': True,
            'templates': templates,
            'count': len(templates),
        }
    except Exception as e:
        logger.warning(f'[{request_id}] list_templates error: {e}')
        return {'success': True, 'templates': [], 'message': f'Could not query: {e}'}


def _tool_send_template(params: Dict, request_id: str) -> Dict:
    """Send WhatsApp template message tool implementation."""
    contact_id = params.get('contactId')
    template_name = params.get('templateName')
    parameters = params.get('parameters', [])
    
    if not contact_id or not template_name:
        return {'success': False, 'error': 'contactId and templateName are required'}
    
    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'templateName': template_name,
                'parameters': parameters
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'message': f'Template "{template_name}" sent'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}



# ============================================================================
# DATA MANAGEMENT & CLEANUP TOOLS
# ============================================================================

def _tool_add_contact_email(params: Dict, request_id: str) -> Dict:
    """Add or update email for a contact."""
    contact_id = params.get('contactId')
    email = params.get('email', '').strip().lower()
    
    if not contact_id or not email:
        return {'success': False, 'error': 'contactId and email are required'}
    
    # Validate contactId looks like a UUID
    if len(contact_id) < 30 or '-' not in contact_id:
        return {'success': False, 'error': f'Invalid contactId format: "{contact_id}". Use search_contacts first to get the correct ID.'}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        # Verify contact exists
        existing = contacts_table.get_item(Key={'id': contact_id})
        if 'Item' not in existing:
            return {'success': False, 'error': f'Contact not found with ID: {contact_id}'}
        
        result = contacts_table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET email = :email, updatedAt = :now',
            ExpressionAttributeValues={
                ':email': email,
                ':now': int(time.time())
            },
            ReturnValues='ALL_NEW'
        )
        
        updated = result.get('Attributes', {})
        
        return {
            'success': True,
            'contactId': contact_id,
            'name': updated.get('name'),
            'email': updated.get('email'),
            'message': f'Email updated to {email}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_delete_contact(params: Dict, request_id: str) -> Dict:
    """Soft delete a contact."""
    contact_id = params.get('contactId')

    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}

    # UUID validation - prevent name-as-ID bug
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}

    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)

        # Existence check
        existing = contacts_table.get_item(Key={'id': contact_id}).get('Item')
        if not existing:
            return {'success': False, 'error': f'Contact {contact_id} not found'}

        if existing.get('deletedAt'):
            return {'success': False, 'error': 'Contact is already deleted'}

        contacts_table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET deletedAt = :now, updatedAt = :now',
            ExpressionAttributeValues={
                ':now': int(time.time())
            },
            ReturnValues='ALL_NEW'
        )

        contact_name = existing.get('name', 'Unknown')

        logger.info(json.dumps({
            'event': 'contact_deleted',
            'contactId': contact_id,
            'contactName': contact_name,
            'requestId': request_id
        }))

        return {
            'success': True,
            'contactId': contact_id,
            'message': f'Contact "{contact_name}" marked as deleted'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}



def _tool_delete_messages(params: Dict, request_id: str) -> Dict:
    """Delete messages for a contact."""
    contact_id = params.get('contactId')
    message_ids = params.get('messageIds', [])
    direction = params.get('direction', 'all')
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        deleted_count = 0
        
        if message_ids:
            # Delete specific messages
            for msg_id in message_ids:
                try:
                    messages_table.delete_item(Key={'id': msg_id})
                    deleted_count += 1
                except Exception:
                    pass
        else:
            # Delete all messages for contact
            response = messages_table.scan(
                FilterExpression='contactId = :cid',
                ExpressionAttributeValues={':cid': contact_id}
            )
            
            for item in response.get('Items', []):
                if direction == 'all' or item.get('direction', '').lower() == direction.lower():
                    try:
                        messages_table.delete_item(Key={'id': item['id']})
                        deleted_count += 1
                    except Exception:
                        pass
        
        logger.info(json.dumps({
            'event': 'messages_deleted',
            'contactId': contact_id,
            'count': deleted_count,
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Deleted {deleted_count} messages'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_delete_media_files(params: Dict, request_id: str) -> Dict:
    """Delete media files from S3 for a contact."""
    contact_id = params.get('contactId')
    file_keys = params.get('fileKeys', [])
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    try:
        deleted_count = 0
        
        if file_keys:
            # Delete specific files
            for key in file_keys:
                try:
                    s3.delete_object(Bucket=MEDIA_BUCKET, Key=key)
                    deleted_count += 1
                except Exception:
                    pass
        else:
            # Delete all files for contact
            prefix = f'media/{contact_id}/'
            response = s3.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix)
            
            for obj in response.get('Contents', []):
                try:
                    s3.delete_object(Bucket=MEDIA_BUCKET, Key=obj['Key'])
                    deleted_count += 1
                except Exception:
                    pass
        
        logger.info(json.dumps({
            'event': 'media_files_deleted',
            'contactId': contact_id,
            'count': deleted_count,
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Deleted {deleted_count} media files from S3'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_clear_all_contact_data(params: Dict, request_id: str) -> Dict:
    """DANGEROUS: Clear ALL data for a contact."""
    contact_id = params.get('contactId')
    confirm = params.get('confirm', False)
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    if not confirm:
        return {
            'success': False,
            'error': 'Confirmation required. This will delete ALL data including messages, media, and conversation history. Set confirm=true to proceed.'
        }
    
    try:
        results = {
            'messages_deleted': 0,
            'media_files_deleted': 0,
            'conversation_cleared': False,
            'contact_deleted': False
        }
        
        # Delete messages
        messages_result = _tool_delete_messages({'contactId': contact_id}, request_id)
        if messages_result.get('success'):
            results['messages_deleted'] = messages_result.get('deletedCount', 0)
        
        # Delete media files
        media_result = _tool_delete_media_files({'contactId': contact_id}, request_id)
        if media_result.get('success'):
            results['media_files_deleted'] = media_result.get('deletedCount', 0)
        
        # Clear conversation history
        try:
            conversation_table = dynamodb.Table(CONVERSATION_TABLE)
            phone_hash = f'contact-{contact_id}'
            
            # Query and delete all conversation records
            response = conversation_table.query(
                KeyConditionExpression='phoneHash = :ph',
                ExpressionAttributeValues={':ph': phone_hash}
            )
            
            for item in response.get('Items', []):
                conversation_table.delete_item(
                    Key={
                        'phoneHash': item['phoneHash'],
                        'timestamp': item['timestamp']
                    }
                )
            
            results['conversation_cleared'] = True
        except Exception:
            pass
        
        # Soft delete contact
        contact_result = _tool_delete_contact({'contactId': contact_id}, request_id)
        if contact_result.get('success'):
            results['contact_deleted'] = True
        
        logger.warning(json.dumps({
            'event': 'all_contact_data_cleared',
            'contactId': contact_id,
            'results': results,
            'requestId': request_id
        }))
        
        return {
            'success': True,
            'results': results,
            'message': f'Cleared all data for contact: {results["messages_deleted"]} messages, {results["media_files_deleted"]} media files, conversation history, and contact record'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_list_media_files(params: Dict, request_id: str) -> Dict:
    """List media files for a contact."""
    contact_id = params.get('contactId')
    file_type = params.get('fileType', 'all').lower()
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    try:
        prefix = f'media/{contact_id}/'
        response = s3.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix)
        
        files = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            size = obj['Size']
            last_modified = obj['LastModified'].isoformat()
            
            # Determine file type from extension
            ext = key.split('.')[-1].lower() if '.' in key else ''
            detected_type = 'unknown'
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                detected_type = 'image'
            elif ext in ['mp4', 'mov', 'avi', 'webm']:
                detected_type = 'video'
            elif ext in ['mp3', 'wav', 'ogg', 'opus']:
                detected_type = 'audio'
            elif ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx']:
                detected_type = 'document'
            
            # Filter by type if specified
            if file_type == 'all' or detected_type == file_type:
                files.append({
                    'key': key,
                    'type': detected_type,
                    'size': size,
                    'lastModified': last_modified
                })
        
        return {
            'success': True,
            'count': len(files),
            'files': files[:50],  # Limit to 50 files
            'message': f'Found {len(files)} media files'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ===== NEW TOOLS: Voice CDR, Billing, Invoicing, Ecommerce =====

def _tool_get_voice_cdr(params: Dict, request_id: str) -> Dict:
    """Get voice call detail records."""
    try:
        query_params = {}
        if params.get('callType'):
            query_params['callType'] = params['callType']
        if params.get('status'):
            query_params['status'] = params['status']
        if params.get('limit'):
            query_params['limit'] = str(params['limit'])
        if params.get('callerNumber'):
            query_params['callerNumber'] = params['callerNumber']
        
        payload = {
            'httpMethod': 'GET',
            'queryStringParameters': query_params,
            'headers': {'origin': 'https://app.wecare.digital'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-voice-cdr-read',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        records = body.get('records', [])
        stats = body.get('stats', {})
        
        summary = []
        for r in records[:10]:
            summary.append({
                'caller': r.get('callerNumber', 'N/A'),
                'destination': r.get('destinationNumber', 'N/A'),
                'status': r.get('status', 'N/A'),
                'duration': r.get('conversationDuration', '00:00'),
                'time': r.get('startTime', 'N/A')
            })
        
        return {
            'success': True,
            'totalRecords': body.get('count', 0),
            'records': summary,
            'stats': {
                'totalCalls': stats.get('totalCalls', 0),
                'answered': stats.get('answered', 0),
                'missed': stats.get('missed', 0),
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_get_billing_summary(params: Dict, request_id: str) -> Dict:
    """Get AWS billing summary."""
    try:
        month = params.get('month', 0)
        payload = {
            'httpMethod': 'GET',
            'queryStringParameters': {'month': str(month)},
            'headers': {'origin': 'https://app.wecare.digital'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-billing',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'totalCost': body.get('totalCost', '0.00'),
            'currency': body.get('currency', 'USD'),
            'period': body.get('period', ''),
            'topServices': body.get('serviceBreakdown', [])[:5],
            'previousMonthTotal': body.get('previousMonthTotal', '0.00'),
            'freeAlerts': body.get('freeTierAlerts', [])
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_get_invoice_list(params: Dict, request_id: str) -> Dict:
    """List invoices."""
    try:
        query_params = {}
        if params.get('contactId'):
            query_params['contactId'] = params['contactId']
        if params.get('status'):
            query_params['status'] = params['status']
        query_params['limit'] = str(params.get('limit', 20))
        
        payload = {
            'httpMethod': 'GET',
            'path': '/invoices',
            'queryStringParameters': query_params,
            'headers': {'origin': 'https://app.wecare.digital'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-invoice-engine',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        invoices = body.get('invoices', [])
        summary = []
        for inv in invoices[:20]:
            summary.append({
                'invoiceId': inv.get('invoiceId'),
                'contactId': inv.get('contactId'),
                'amount': inv.get('totalAmount'),
                'status': inv.get('status'),
                'date': inv.get('createdAt', '')[:10]
            })
        
        return {
            'success': True,
            'count': len(invoices),
            'invoices': summary
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_create_invoice(params: Dict, request_id: str) -> Dict:
    """Create a new invoice."""
    contact_id = params.get('contactId')
    items = params.get('items', [])
    
    if not contact_id or not items:
        return {'success': False, 'error': 'contactId and items are required'}
    
    try:
        invoice_data = {
            'contactId': contact_id,
            'items': items,
            'currency': params.get('currency', 'INR'),
            'notes': params.get('notes', ''),
        }
        if params.get('dueDate'):
            invoice_data['dueDate'] = params['dueDate']
        
        payload = {
            'httpMethod': 'POST',
            'path': '/invoices',
            'body': json.dumps(invoice_data),
            'headers': {'origin': 'https://app.wecare.digital', 'Content-Type': 'application/json'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-invoice-engine',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'invoiceId': body.get('invoiceId'),
            'invoiceNumber': body.get('invoiceNumber'),
            'totalAmount': body.get('totalAmount'),
            'message': f'Invoice created: {body.get("invoiceNumber", "N/A")}'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_get_wix_products(params: Dict, request_id: str) -> Dict:
    """List Wix store products."""
    try:
        query_params = {}
        if params.get('query'):
            query_params['search'] = params['query']
        query_params['limit'] = str(params.get('limit', 20))
        
        payload = {
            'httpMethod': 'GET',
            'path': '/products',
            'queryStringParameters': query_params,
            'headers': {'origin': 'https://app.wecare.digital'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-wix-store',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        products = body.get('products', [])
        summary = []
        for p in products[:20]:
            summary.append({
                'name': p.get('name'),
                'price': p.get('price', {}).get('formatted', 'N/A'),
                'status': p.get('status', 'N/A'),
                'id': p.get('id')
            })
        
        return {
            'success': True,
            'count': len(products),
            'products': summary
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_get_wix_orders(params: Dict, request_id: str) -> Dict:
    """List Wix store orders."""
    try:
        query_params = {}
        if params.get('status'):
            query_params['status'] = params['status']
        query_params['limit'] = str(params.get('limit', 20))
        
        payload = {
            'httpMethod': 'GET',
            'path': '/orders',
            'queryStringParameters': query_params,
            'headers': {'origin': 'https://app.wecare.digital'}
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-wix-store',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        body = json.loads(result.get('body', '{}'))
        
        orders = body.get('orders', [])
        summary = []
        for o in orders[:20]:
            summary.append({
                'orderId': o.get('number') or o.get('id'),
                'status': o.get('status', 'N/A'),
                'total': o.get('totals', {}).get('total', 'N/A'),
                'date': o.get('dateCreated', '')[:10],
                'buyer': o.get('buyerInfo', {}).get('firstName', 'N/A')
            })
        
        return {
            'success': True,
            'count': len(orders),
            'orders': summary
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_send_whatsapp_flow(params: Dict, request_id: str) -> Dict:
    """Send a WhatsApp Flow (e.g. Submit Request) to a contact."""
    contact_id = params.get('contactId')
    flow_type = params.get('flowType', 'submit_request')
    
    if not contact_id:
        return {'success': False, 'error': 'contactId is required'}
    
    # UUID validation
    valid, msg = validate_contact_id(contact_id)
    if not valid:
        return {'success': False, 'error': msg}
    
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        existing = contacts_table.get_item(Key={'id': contact_id}).get('Item')
        if not existing:
            return {'success': False, 'error': f'Contact {contact_id} not found'}
        
        phone = existing.get('phone', '')
        if not phone:
            return {'success': False, 'error': 'Contact has no phone number'}
        
        # Get flow config from SystemConfig
        flow_config = {}
        try:
            config_table = dynamodb.Table(os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable'))
            config_resp = config_table.get_item(Key={'id': 'botFlowConfig'})
            bot_config = config_resp.get('Item', {}).get('configValue', {})
            if isinstance(bot_config, str):
                bot_config = json.loads(bot_config)
            triggers = bot_config.get('flowTriggers', {})
            flow_config = triggers.get(flow_type, {})
        except Exception:
            pass
        
        # Default flow IDs
        flow_ids = {
            'submit_request': '1235100738173254',
        }
        
        flow_id = flow_config.get('flowId', '') or flow_ids.get(flow_type, '')
        if not flow_id:
            return {'success': False, 'error': f'Unknown flow type: {flow_type}'}
        
        flow_msg = flow_config.get('message', {})
        flow_token = f'flow-{contact_id}-{int(time.time())}'
        
        # Invoke outbound-whatsapp with flow payload
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'interactive': {
                    'type': 'flow',
                    'body': {'text': flow_msg.get('body', 'Please use the self-service option below.')},
                    'footer': {'text': flow_msg.get('footer', 'WECARE.DIGITAL')},
                    'action': {
                        'name': 'flow',
                        'parameters': {
                            'flow_message_version': '3',
                            'flow_id': flow_id,
                            'flow_cta': flow_msg.get('flowCta', 'Submit Request'),
                            'flow_action': 'data_exchange',
                            'flow_token': flow_token,
                            'flow_action_payload': {
                                'screen': 'INIT',
                                'data': {'senderPhone': phone}
                            }
                        }
                    }
                }
            })
        }
        
        response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        result_body = json.loads(result.get('body', '{}'))
        
        return {
            'success': True,
            'messageId': result_body.get('messageId'),
            'flowType': flow_type,
            'message': f'WhatsApp Flow "{flow_type}" sent to {existing.get("name", phone)}'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _tool_list_submit_requests(params: Dict, request_id: str) -> Dict:
    """List submit request flow submissions from DynamoDB."""
    contact_id = params.get('contactId')
    status_filter = params.get('status')
    limit = min(params.get('limit', 20), 50)
    
    try:
        table = dynamodb.Table(os.environ.get('SUBMIT_REQUESTS_TABLE', 'stack-wecare-digital-SubmitRequestsTable'))
        
        scan_kwargs = {'Limit': limit}
        filter_parts = []
        expr_values = {}
        
        if contact_id:
            valid, msg = validate_contact_id(contact_id)
            if not valid:
                return {'success': False, 'error': msg}
            filter_parts.append('contactId = :cid')
            expr_values[':cid'] = contact_id
        
        if status_filter:
            filter_parts.append('#st = :status')
            expr_values[':status'] = status_filter
            scan_kwargs['ExpressionAttributeNames'] = {'#st': 'status'}
        
        if filter_parts:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_parts)
            scan_kwargs['ExpressionAttributeValues'] = expr_values
        
        result = table.scan(**scan_kwargs)
        items = result.get('Items', [])
        
        # Sort by createdAt descending
        items.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        
        summary = []
        for item in items[:limit]:
            summary.append({
                'submissionId': item.get('id') or item.get('submissionId'),
                'contactId': item.get('contactId'),
                'phone': item.get('senderPhone', ''),
                'status': item.get('status', 'pending'),
                'requestType': item.get('requestType', ''),
                'description': (item.get('description', '') or '')[:100],
                'createdAt': item.get('createdAt', ''),
                'paymentStatus': item.get('paymentStatus', ''),
            })
        
        return {
            'success': True,
            'count': len(summary),
            'submissions': summary
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
