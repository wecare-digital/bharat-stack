"""
AI Generate Response Lambda Function

Purpose: Generate AI response using Bedrock for WhatsApp and admin contexts

Architecture:
- INTERNAL: Bedrock Agent (FloatingAgent) for admin tasks — unchanged
  - Agent ID: QIEEHEBTZO / Alias: ASCBD7YPUT / KB: D0JU8Q7IQS
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

Model: Amazon Nova Lite (amazon.nova-lite-v1:0)
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

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

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

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
CONVERSATION_TABLE = os.environ.get('CONVERSATION_TABLE', 'base-wecare-digital-ConversationHistoryTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'base-wecare-digital-SystemConfigTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')

# Internal Agent (FloatingAgent — admin tasks, unchanged)
INTERNAL_AGENT_ID = os.environ.get('INTERNAL_AGENT_ID', 'QIEEHEBTZO')
INTERNAL_AGENT_ALIAS = os.environ.get('INTERNAL_AGENT_ALIAS', 'ASCBD7YPUT')
INTERNAL_KB_ID = os.environ.get('INTERNAL_KB_ID', 'D0JU8Q7IQS')

# External (WhatsApp auto-reply — Converse API)
EXTERNAL_KB_ID = os.environ.get('EXTERNAL_KB_ID', 'LYMQLKZNY7')
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-lite-v1:0')
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID', '')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', 'DRAFT')

# Conversation limits
MAX_HISTORY_MESSAGES = int(os.environ.get('MAX_HISTORY_MESSAGES', '20'))
MAX_SESSION_MESSAGES = int(os.environ.get('MAX_SESSION_MESSAGES', '50'))
CONVERSATION_TTL_HOURS = int(os.environ.get('CONVERSATION_TTL_HOURS', '24'))
PROCESSING_LOCK_TTL_SECONDS = 90

# Session idle timeout (minutes) — reset conversation if idle too long
SESSION_IDLE_TIMEOUT_MINUTES = int(os.environ.get('SESSION_IDLE_TIMEOUT_MINUTES', '15'))

# Input text size limit — truncate to prevent token abuse
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
    'chinese': 'Chinese', 'zh': 'Chinese', '中文': 'Chinese',
    'japanese': 'Japanese', 'ja': 'Japanese', '日本語': 'Japanese',
    'korean': 'Korean', 'ko': 'Korean', '한국어': 'Korean',
    'thai': 'Thai', 'th': 'Thai', 'ไทย': 'Thai',
    'vietnamese': 'Vietnamese', 'vi': 'Vietnamese',
    'indonesian': 'Indonesian', 'id': 'Indonesian', 'bahasa': 'Indonesian',
    'sinhala': 'Sinhala', 'si': 'Sinhala', 'sinhalese': 'Sinhala',
    # Middle East
    'arabic': 'Arabic', 'ar': 'Arabic', 'العربية': 'Arabic',
    'turkish': 'Turkish', 'tr': 'Turkish', 'türkçe': 'Turkish',
    'russian': 'Russian', 'ru': 'Russian', 'русский': 'Russian',
    'urdu': 'Urdu', 'ur': 'Urdu', 'اردو': 'Urdu',
    'punjabi': 'Punjabi', 'pa': 'Punjabi',
    # European
    'french': 'French', 'fr': 'French', 'français': 'French',
    'spanish': 'Spanish', 'es': 'Spanish', 'español': 'Spanish',
    'portuguese': 'Portuguese', 'pt': 'Portuguese', 'português': 'Portuguese',
}

# ── Two-step language picker: Step 1 = Region, Step 2 = Languages ──

LANGUAGE_REGION_PICKER = [
    {'id': 'region_popular', 'title': '\u2b50 Popular', 'description': 'English, Hindi, Bengali, Tamil & more'},
    {'id': 'region_asian', 'title': '\U0001f30f Asian', 'description': '\u4e2d\u6587, \u65e5\u672c\u8a9e, \ud55c\uad6d\uc5b4, \u0e44\u0e17\u0e22 & more'},
    {'id': 'region_middle_east', 'title': '\U0001f30d Middle East', 'description': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629, T\u00fcrk\u00e7e, \u0420\u0443\u0441\u0441\u043a\u0438\u0439, \u0627\u0631\u062f\u0648'},
    {'id': 'region_european', 'title': '\U0001f1ea\U0001f1fa European', 'description': 'Fran\u00e7ais, Espa\u00f1ol, Portugu\u00eas'},
]

LANGUAGE_BY_REGION = {
    'region_popular': [
        {'id': 'lang_english', 'title': 'English'},
        {'id': 'lang_hindi', 'title': 'हिन्दी / Hindi'},
        {'id': 'lang_hinglish', 'title': 'Hinglish'},
        {'id': 'lang_bengali', 'title': 'বাংলা / Bengali'},
        {'id': 'lang_tamil', 'title': 'தமிழ் / Tamil'},
        {'id': 'lang_telugu', 'title': 'తెలుగు / Telugu'},
        {'id': 'lang_gujarati', 'title': 'ગુજરાતી / Gujarati'},
        {'id': 'lang_marathi', 'title': 'मराठी / Marathi'},
        {'id': 'lang_kannada', 'title': 'ಕನ್ನಡ / Kannada'},
        {'id': 'lang_malayalam', 'title': 'മലയാളം / Malayalam'},
    ],
    'region_asian': [
        {'id': 'lang_chinese', 'title': '简体中文 / Chinese'},
        {'id': 'lang_japanese', 'title': '日本語 / Japanese'},
        {'id': 'lang_korean', 'title': '한국어 / Korean'},
        {'id': 'lang_thai', 'title': 'ไทย / Thai'},
        {'id': 'lang_vietnamese', 'title': 'Tiếng Việt / Vietnamese'},
        {'id': 'lang_indonesian', 'title': 'Indonesia / Indonesian'},
        {'id': 'lang_sinhala', 'title': 'සිංහල / Sinhala'},
    ],
    'region_middle_east': [
        {'id': 'lang_arabic', 'title': 'العربية / Arabic'},
        {'id': 'lang_turkish', 'title': 'Türkçe / Turkish'},
        {'id': 'lang_russian', 'title': 'Русский / Russian'},
        {'id': 'lang_urdu', 'title': 'اردو / Urdu'},
        {'id': 'lang_punjabi', 'title': 'ਪੰਜਾਬੀ / Punjabi'},
    ],
    'region_european': [
        {'id': 'lang_french', 'title': 'Français / French'},
        {'id': 'lang_spanish', 'title': 'Español / Spanish'},
        {'id': 'lang_portuguese', 'title': 'Português / Portuguese'},
    ],
}

# Flat map: lang ID → language name (built from all regions)
LANGUAGE_ID_MAP = {}
for _region_langs in LANGUAGE_BY_REGION.values():
    for _opt in _region_langs:
        LANGUAGE_ID_MAP[_opt['id']] = _opt['title'].split(' / ')[-1] if ' / ' in _opt['title'] else _opt['title']

LANGUAGE_CONFIRMATIONS = {
    'English': "Language set to English! 🌐 How can I help you today?",
    'Hindi': "भाषा हिंदी में सेट हो गई! 🌐 मैं आपकी कैसे मदद कर सकता हूँ?",
    'Hinglish': "Language Hinglish mein set ho gayi! 🌐 Kaise help kar sakta hoon?",
    'Bengali': "ভাষা বাংলায় সেট হয়েছে! 🌐 আমি কীভাবে সাহায্য করতে পারি?",
    'Tamil': "மொழி தமிழில் அமைக்கப்பட்டது! 🌐 நான் எப்படி உதவ முடியும்?",
    'Telugu': "భాష తెలుగులో సెట్ చేయబడింది! 🌐 నేను ఎలా సహాయం చేయగలను?",
    'Gujarati': "ભાષા ગુજરાતીમાં સેટ થઈ! 🌐 હું કેવી રીતે મદદ કરી શકું?",
    'Marathi': "भाषा मराठीत सेट झाली! 🌐 मी कशी मदत करू शकतो?",
    'Kannada': "ಭಾಷೆ ಕನ್ನಡಕ್ಕೆ ಹೊಂದಿಸಲಾಗಿದೆ! 🌐 ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
    'Malayalam': "ഭാഷ മലയാളത്തിൽ സജ്ജീകരിച്ചു! 🌐 ഞാൻ എങ്ങനെ സഹായിക്കാം?",
    'Chinese': "语言已设置为中文！🌐 我能帮您什么？",
    'Japanese': "言語が日本語に設定されました！🌐 何かお手伝いできますか？",
    'Korean': "언어가 한국어로 설정되었습니다! 🌐 무엇을 도와드릴까요?",
    'Thai': "ตั้งค่าภาษาเป็นภาษาไทยแล้ว! 🌐 ให้ช่วยอะไรดีคะ?",
    'Vietnamese': "Ngôn ngữ đã được đặt thành Tiếng Việt! 🌐 Tôi có thể giúp gì?",
    'Indonesian': "Bahasa diatur ke Indonesia! 🌐 Ada yang bisa saya bantu?",
    'Sinhala': "භාෂාව සිංහලට සකසා ඇත! 🌐 මට ඔබට උදව් කළ හැක්කේ කෙසේද?",
    'Arabic': "تم تعيين اللغة إلى العربية! 🌐 كيف يمكنني مساعدتك؟",
    'Turkish': "Dil Türkçe olarak ayarlandı! 🌐 Size nasıl yardımcı olabilirim?",
    'Russian': "Язык установлен на русский! 🌐 Чем могу помочь?",
    'Urdu': "زبان اردو میں سیٹ ہو گئی! 🌐 میں آپ کی کیسے مدد کر سکتا ہوں؟",
    'Punjabi': "ਭਾਸ਼ਾ ਪੰਜਾਬੀ ਵਿੱਚ ਸੈੱਟ ਹੋ ਗਈ! 🌐 ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?",
    'French': "Langue définie sur le français ! 🌐 Comment puis-je vous aider ?",
    'Spanish': "¡Idioma configurado en español! 🌐 ¿Cómo puedo ayudarte?",
    'Portuguese': "Idioma definido para português! 🌐 Como posso ajudar?",
}


# ============================================================================
# WHATSAPP BOT FLOW CONFIG (loaded from SystemConfigTable, dashboard-manageable)
# ============================================================================

DEFAULT_BOT_FLOW = {
    # ── AI & Language Disclaimer (dashboard-manageable) ──
    'disclaimer': "ℹ️ _This is an AI assistant. Responses are generated on a best-effort basis and may not always be accurate. Language and voice support is provided on a best-effort basis. Please verify important information independently or contact our team at +91 9330994400._",

    # ── Welcome messages ──
    'welcome': {
        'text': "Hi there! 👋 Welcome to WECARE.DIGITAL\n\nShop, pay, track requests, or get support \u2014 all right here.\n\nℹ️ _You\u2019re chatting with an AI assistant. Responses may not always be accurate. Please verify important details independently._\n\nTap Menu to get started 👇",
    },
    'welcomeBack': {
        'text': "Welcome back! 💛 What can we help with today? 👇",
    },

    # ── Main Menu (10 rows, 2 sections) ──
    'mainMenu': {
        'header': 'WECARE.DIGITAL',
        'body': "Pick what you need 👇",
        'footer': 'wecare.digital',
        'buttonText': 'Menu',
        'sections': [
            {
                'title': 'Explore',
                'rows': [
                    {'id': 'menu_store', 'title': '🛒 Store', 'description': 'Shop our brand marketplaces'},
                    {'id': 'menu_self_service', 'title': '🚀 Self Service', 'description': 'Submit, track & manage requests'},
                    {'id': 'menu_pay', 'title': '💳 Pay', 'description': 'Make a payment via WhatsApp'},
                    {'id': 'menu_subscribe', 'title': '📝 Subscribe', 'description': 'Sign up with name, email & phone'},
                ]
            },
            {
                'title': 'More',
                'rows': [
                    {'id': 'menu_app', 'title': '📱 Download App', 'description': 'Get the WECARE.DIGITAL app'},
                    {'id': 'menu_about', 'title': '💛 About Us', 'description': 'Our mission & brands'},
                    {'id': 'menu_audio', 'title': '🎧 Audio Response', 'description': 'Get replies as voice messages'},
                    {'id': 'menu_language', 'title': '🌐 Change Language', 'description': 'Choose your response language'},
                    {'id': 'menu_notifications', 'title': '🔔 Notifications', 'description': 'Manage your alert preferences'},
                    {'id': 'menu_human', 'title': '💬 Talk to Human', 'description': 'Connect with a live agent'},
                ]
            }
        ]
    },

    # ── Sub-Menus ──
    'subMenus': {
        'menu_store': {
            'header': 'Our Store',
            'body': "Explore our brands & gifting 👇",
            'footer': 'wecare.digital/store',
            'buttonText': 'Browse',
            'sections': [
                {
                    'title': 'Brands',
                    'rows': [
                        {'id': 'store_bnb_club', 'title': '✈️ BNB Club', 'description': 'Travel, visas, corporate & FIT'},
                        {'id': 'store_no_fault', 'title': '⚖️ No Fault', 'description': 'Faster online dispute resolution'},
                        {'id': 'store_expo_week', 'title': '🌍 Expo Week', 'description': 'Virtual fairs & digital events'},
                        {'id': 'store_ritual_guru', 'title': '🙏 Ritual Guru', 'description': 'Puja kits & step-by-step guides'},
                        {'id': 'store_legal_champ', 'title': '📄 Legal Champ', 'description': 'Business docs & registrations'},
                        {'id': 'store_swdhya', 'title': '🧘 Swdhya', 'description': 'Samvad — self-inquiry chats'},
                    ]
                },
                {
                    'title': 'Gifting',
                    'rows': [
                        {'id': 'store_gift_card', 'title': '🎁 Gift Card', 'description': 'Send a WECARE.DIGITAL gift card'},
                        {'id': 'menu_back', 'title': '↩️ Back to Menu', 'description': 'Return to main menu'},
                    ]
                }
            ]
        },
        'menu_self_service': {
            'header': 'Self Service',
            'body': "What do you need help with? 👇",
            'footer': 'wecare.digital/selfservice',
            'buttonText': 'Options',
            'sections': [
                {
                    'title': 'Requests',
                    'rows': [
                        {'id': 'menu_submit_request', 'title': '📩 Submit a Request', 'description': 'Start a new service request'},
                        {'id': 'menu_amend_request', 'title': '✏️ Amend a Request', 'description': 'Modify a previous request'},
                        {'id': 'menu_track_request', 'title': '📍 Track a Request', 'description': 'Check your request status'},
                    ]
                },
                {
                    'title': 'Services',
                    'rows': [
                        {'id': 'menu_rx_slot', 'title': '🗓️ RX Slot', 'description': 'Schedule a medical appointment'},
                        {'id': 'menu_drop_docs', 'title': '📤 Drop Docs', 'description': 'Upload supporting documents'},
                        {'id': 'menu_hours', 'title': '⏰ Business Hours', 'description': 'When we are available'},
                        {'id': 'menu_enterprise', 'title': '🤝 Enterprise Assist', 'description': 'Business & technical support'},
                        {'id': 'menu_back', 'title': '↩️ Back to Menu', 'description': 'Return to main menu'},
                    ]
                }
            ]
        },
    },

    # ── Menu Responses ──
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
            'text': "💬 Connecting you with a live agent... A team member will be with you shortly. 🙏",
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
            'text': "📩 *Submit a Request*\n\nSubmit a request — it\u2019s quick and easy. We\u2019ll review and keep you posted. 📬",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_amend_request': {
            'text': "✏️ *Amend a Request*\n\nNeed to modify a previous request? Update it anytime, subject to terms and approval. 🛠️",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_track_request': {
            'text': "📍 *Track a Request*\n\nCheck your request status — see when it\u2019s received, reviewed, or completed. 🔍",
            'cta': {'text': 'Start Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_rx_slot': {
            'text': "🗓️ *RX Slot*\n\nSchedule a medical appointment for your MEd Tour package via BNB Club. 🩺",
            'cta': {'text': 'Book Slot', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_drop_docs': {
            'text': "📤 *Drop Docs*\n\nUpload supporting documents directly to your request. All uploads are secure. 📎",
            'cta': {'text': 'Upload Now', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_enterprise': {
            'text': "🤝 *Enterprise Support*\n\nFor technical or business inquiries, our enterprise team is here. 💼",
            'cta': {'text': 'Get Support', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_hours': {
            'text': "⏰ *Business Hours*\n\nMon–Fri, 9 AM – 6 PM (IST). Our 24/7 self-service portal is always open. 🌐",
            'cta': {'text': 'Self Service', 'url': 'https://wecare.digital/selfservice'},
        },
        'menu_app': {
            'text': "📱 *Download the App*\n\nManage services on the go — iOS and Android. Track, schedule, and more. 📲",
            'cta': {'text': 'GET APP', 'url': 'https://wecare.digital/one'},
        },
        'menu_about': {
            'text': "💛 *About Us*\n\nWECARE.DIGITAL creates helpful products for everyday life — with you at the heart.\n\nOur brands: BNB Club, Expo Week, Legal Champ, No-Fault, Ritual Guru, and Swdhya.",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital'},
        },
        # Store brand responses
        'store_bnb_club': {
            'text': "✈️ *BNB Club — Travel*\n\nYour travel club for visas, corporate travel, FIT packages, and itinerary planning. 🌏",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/bnbclub'},
        },
        'store_no_fault': {
            'text': "⚖️ *No Fault — ODR*\n\nFaster, lower-cost online dispute resolution. Fair, transparent, efficient. 🤝",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/nofault'},
        },
        'store_expo_week': {
            'text': "🌍 *Expo Week — Digital Events*\n\nVirtual travel fairs, exclusive offers, and sustainable discovery. 🎪",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/expoweek'},
        },
        'store_ritual_guru': {
            'text': "🙏 *Ritual Guru — Culture*\n\nTemple-grade puja kits with step-by-step guides. Global delivery. 🙏",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/ritualguru'},
        },
        'store_legal_champ': {
            'text': "📄 *Legal Champ — Documentation*\n\nBusiness docs, registrations, and compliance made simple. 📋",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/legalchamp'},
        },
        'store_swdhya': {
            'text': "🧘 *Swdhya — Samvad*\n\nSelf-inquiry conversations for clarity and action. 🌱",
            'cta': {'text': 'Explore', 'url': 'https://wecare.digital/swdhya'},
        },
        'store_gift_card': {
            'text': "🎁 *Gift Card*\n\nGive the gift of choice! Redeemable across all WECARE.DIGITAL brands. 💛",
            'cta': {'text': 'Get Gift Card', 'url': 'https://www.wecare.digital/gift-card'},
        },
    },

    # ── Conversational flow prompts ──
    'flows': {
        'subscribe': {
            'step_name': "📝 Let\u2019s get you signed up! What\u2019s your full name?",
            'step_email': "Nice, {name}! Your email address? 📧",
            'step_phone': "Got it! Last one — phone number with country code? 📱",
            'done': "You\u2019re all set, {name}! ✅ Welcome aboard. 💛",
            'invalid_email': "Hmm, that doesn\u2019t look like a valid email. Try again? 📧",
            'invalid_phone': "That doesn\u2019t look right. Enter phone with country code (e.g. +91 98765 43210) 📱",
        },
        'pay': {
            'step_amount': "💳 Enter unit price (₹) (numbers only)\nExample: 500",
            'step_quantity': "📦 Enter quantity / units (type 1 for single)\nExample: 2",
            'invalid_amount': "⚠️ Please enter a valid number between 1 and 100000.",
            'invalid_quantity': "⚠️ Please enter a valid quantity between 1 and 999.",
            'sending': "Processing payment of ₹{amount}... ⏳",
            'default_item_name': 'Services/Goods',
            'default_gst_rate': 18,
            'default_shipping': 49,
            'default_promo': 15,
            'gstin': '19AADFW7431N1ZK',
        },
    },

    # ── Toggle messages ──
    'toggles': {
        'audio_on': "🎧 Audio replies enabled! You\u2019ll now receive voice messages too. 🔊\n\n_Voice is generated by AI on a best-effort basis. Some languages may use an approximate voice._",
        'audio_off': "🎧 Audio replies disabled. Text only from now. 📝",
        'audio_prompt': "🎧 Audio replies are {status}. Reply ON to hear responses in your language, or OFF for text only.\n\n_Voice is AI-generated on a best-effort basis._",
        'notifications_on': "🔔 Notifications enabled! You\u2019ll receive updates and alerts. 📨",
        'notifications_off': "🔔 Notifications turned off. Re-enable anytime from the menu.",
        'notifications_prompt': "🔔 Notifications are {status}. Reply ON to receive updates, or OFF to stop.",
    },

    # ── Options menu (after any action) ──
    'options': {
        'header': "What\u2019s next?",
        'body': "Pick an option below 👇",
        'footer': 'wecare.digital',
        'buttonText': 'Next',
        'sections': [
            {
                'title': 'Choose',
                'rows': [
                    {'id': 'opt_do_more', 'title': '🧭 Do more', 'description': 'Back to the main menu'},
                    {'id': 'opt_done', 'title': '✌️ Done here', 'description': 'All finished for now'},
                ]
            }
        ]
    },
    'doMore': {
        'text': "Let\u2019s go! 🚀 Pick what\u2019s next 👇",
    },
    'done': {
        'text': "All done? You crushed it. 👊 Catch you later! 💛",
    },

    # ── Rating ──
    'rating': {
        'header': 'Quick feedback',
        'body': "How was your experience? 🫶",
        'footer': 'wecare.digital',
        'buttonText': 'Rate',
        'sections': [
            {
                'title': 'How was it?',
                'rows': [
                    {'id': 'rate_good', 'title': 'Vibes immaculate 🙌', 'description': 'Great experience'},
                    {'id': 'rate_ok', 'title': '😐 Just okay', 'description': 'It was fine'},
                    {'id': 'rate_mid', 'title': 'Kinda mid 🫤', 'description': 'Could be better'},
                ]
            }
        ]
    },
    'ratingResponses': {
        'rate_good': "Thanks for vibin\u2019 with us! 🌟",
        'rate_ok': "Appreciate the honesty! We\u2019ll keep improving. 💪",
        'rate_mid': "Bet — glow-up in progress 🔧",
    },
    'errorMsg': "Whoops! That didn\u2019t register. Try picking from the menu. ⚠️",
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
- Keep responses SHORT (2-4 sentences max) — this is WhatsApp, not email
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
    """Generate AI response — routes to internal agent or external Converse API."""
    request_id = context.aws_request_id if context else 'local'

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }

    # Handle OPTIONS preflight
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

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
        # ── INTERNAL (admin) path — unchanged, uses Bedrock Agent ──
        if agent_context == 'internal-admin':
            return _handle_internal(body, headers, request_id)

        # ── EXTERNAL (WhatsApp) path — Converse API with multimodal ──
        return _handle_external(body, headers, request_id)

    except Exception as e:
        logger.error(json.dumps({'event': 'ai_generate_error', 'error': str(e), 'errorType': type(e).__name__, 'requestId': request_id}))
        import traceback
        logger.error(f"TRACEBACK: {traceback.format_exc()}")
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'suggestedResponse': _get_fallback_response(), 'error': str(e)})
        }


# ============================================================================
# INTERNAL PATH (FloatingAgent — unchanged)
# ============================================================================

def _handle_internal(body: Dict, headers: Dict, request_id: str) -> Dict:
    """Internal admin path using Bedrock Agent (unchanged)."""
    message_content = body.get('messageContent', '')
    message_id = body.get('messageId', '')
    contact_id = body.get('contactId', '')

    if not INTERNAL_AGENT_ID or not INTERNAL_AGENT_ALIAS:
        return {
            'statusCode': 200, 'headers': headers,
            'body': json.dumps({'suggestedResponse': _get_fallback_response(), 'error': 'Internal agent not configured'})
        }

    if not message_content:
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'suggestedResponse': _get_fallback_response()})}

    suggestion = _invoke_bedrock_agent(message_content, INTERNAL_AGENT_ID, INTERNAL_AGENT_ALIAS, INTERNAL_KB_ID, request_id)

    return {
        'statusCode': 200, 'headers': headers,
        'body': json.dumps({'suggestedResponse': suggestion, 'messageId': message_id, 'contactId': contact_id})
    }


# ============================================================================
# EXTERNAL PATH (WhatsApp — Converse API + multimodal + conversation history)
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

    # Hash phone for DynamoDB key (privacy)
    phone_hash = _hash_phone(sender_phone) if sender_phone else contact_id

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

    # ── Processing lock: prevent duplicate AI calls ──
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
        # ── Message size validation: truncate oversized text ──
        if message_content and len(message_content) > MAX_INPUT_TEXT_LENGTH:
            logger.warning(json.dumps({
                'event': 'message_truncated',
                'originalLength': len(message_content),
                'maxLength': MAX_INPUT_TEXT_LENGTH,
                'phoneHash': phone_hash,
                'requestId': request_id
            }))
            message_content = message_content[:MAX_INPUT_TEXT_LENGTH] + '...[truncated]'

        # ── Load conversation history ──
        logger.info(json.dumps({
            'event': 'loading_history',
            'phoneHash': phone_hash[:8],
            'requestId': request_id
        }))
        history = _load_conversation_history(phone_hash)

        # ── Check if this is a language selection reply ──
        lang_selection = _detect_language_selection(message_content, message_type)
        if lang_selection:
            # Region selection (Step 1) → return languages for that region
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
                        'suggestedResponse': f'🌐 Choose your language from {region_title} 👇',
                        'showLanguagePicker': True,
                        'languagePickerStep': 'languages',
                        'regionId': region_id,
                        'regionTitle': region_title,
                        'regionLanguages': region_languages,
                    })
                }

            # Language selection (Step 2) → save preference
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

        # ── Bot flow: handle menu/options/rating selections ──
        flow_config = _get_bot_flow_config()
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

        # ── Check if this is a brand-new session (no history) → send welcome text only ──
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
            # Just send welcome text — no auto menu
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

        # ── Build the user content blocks for Converse API ──
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

        # ── Session idle timeout: reset if idle too long ──
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

        # ── Check conversation limits ──
        session_msg_count = history.get('messageCount', 0)
        if session_msg_count >= MAX_SESSION_MESSAGES:
            logger.info(json.dumps({
                'event': 'session_reset_limit',
                'phoneHash': phone_hash,
                'messageCount': session_msg_count,
                'requestId': request_id
            }))
            history = {'messages': [], 'messageCount': 0}

        # ── Intent classification + human escalation ──
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
                escalation_msg = "I'd like to connect you with our team for the best help on this. 🙏 A team member will be with you shortly. You can also reach us at +91 9330994400."
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

        # ── Retrieve KB context for grounded answers ──
        # Only pre-fetch KB for the first message in a session (no history).
        # For subsequent messages, the model can use the search_knowledge_base tool
        # autonomously when it needs factual data, avoiding redundant KB calls.
        kb_context = ''
        if message_content and not history.get('messages'):
            kb_context = _retrieve_kb_context(message_content, request_id)

        # ── Build system prompt with KB context and language preference ──
        system_prompt = SYSTEM_PROMPT
        preferred_lang = history.get('preferredLanguage', '')
        if preferred_lang:
            system_prompt += f"\n\nUSER'S PREFERRED LANGUAGE: {preferred_lang}\nYou MUST respond in {preferred_lang}. This is the user's explicit choice."
        if kb_context:
            system_prompt += f"\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n{kb_context}"

        # ── Prepare messages for Converse API ──
        converse_messages = history.get('messages', [])[-MAX_HISTORY_MESSAGES:]
        converse_messages.append({'role': 'user', 'content': content_blocks})

        # ── Call Bedrock Converse API (with tool use loop) ──
        suggestion = _call_converse_with_tools(
            system_prompt=system_prompt,
            messages=converse_messages,
            sender_phone=sender_phone,
            phone_hash=phone_hash,
            request_id=request_id
        )

        if not suggestion:
            suggestion = _get_fallback_response()

        # ── Save updated conversation history ──
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
        # Fail open — don't escalate on classification error
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

    # Exhausted iterations — return whatever we have
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
            brand = tool_input.get('brand_name', '')
            return _get_brand_info(brand)

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
        # Try GSI first (phoneNumber-index), fall back to scan
        try:
            response = contacts_table.query(
                IndexName='phoneNumber-index',
                KeyConditionExpression='phoneNumber = :phone',
                ExpressionAttributeValues={':phone': clean_phone},
                Limit=1
            )
            items = response.get('Items', [])
        except Exception:
            # GSI may not exist — fall back to scan (less efficient but works)
            response = contacts_table.scan(
                FilterExpression='phoneNumber = :phone OR phone = :phone OR contains(phoneNumbers, :phone)',
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

def _retrieve_kb_context(query: str, request_id: str) -> str:
    """Retrieve relevant context from Knowledge Base for grounded answers."""
    if not EXTERNAL_KB_ID or not query:
        return ''
    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=EXTERNAL_KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {'numberOfResults': 3}
            }
        )
        results = response.get('retrievalResults', [])
        parts = []
        for r in results:
            text = r.get('content', {}).get('text', '')
            score = r.get('score', 0)
            if text and score > 0.4:
                parts.append(text)
        context = '\n\n'.join(parts[:3])
        logger.info(json.dumps({
            'event': 'kb_retrieve_success',
            'resultsCount': len(results),
            'usedCount': len(parts),
            'contextLength': len(context),
            'requestId': request_id
        }))
        return context
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'kb_retrieve_error',
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
    - Region picker reply ID (e.g. "region_popular") → returns dict with region languages
    - Interactive list reply ID (e.g. "lang_hindi") → returns language name string
    - Interactive list reply title (e.g. "हिंदी / Hindi")
    - Text commands like "language hindi", "lang: bengali"
    Returns:
    - str: normalized language name (for lang_ selections)
    - dict: {'region': region_id, 'languages': [...]} (for region_ selections)
    - None: not a language/region selection
    """
    if not message_content:
        return None

    content_lower = message_content.strip().lower()

    # ── Step 1 reply: Region selection (e.g. "region_popular") ──
    if content_lower.startswith('region_'):
        languages = LANGUAGE_BY_REGION.get(content_lower)
        if languages:
            return {'region': content_lower, 'languages': languages}

    # ── Step 2 reply: Language selection (e.g. "lang_hindi") ──
    if content_lower.startswith('lang_'):
        lang = LANGUAGE_ID_MAP.get(content_lower)
        if lang:
            return lang

    # Check interactive list reply title (e.g. "हिंदी / Hindi" → extract "Hindi")
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
# BOT FLOW ENGINE (menu → response → options → rating)
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

    # ── Fix #3: Escape words — cancel/back/exit during active flows ──
    ESCAPE_WORDS = {'cancel', 'menu', 'exit', 'stop', 'quit', 'main menu'}

    # ── Check for active conversational flow (state machine) ──
    flow_state = history.get('flowState')
    if flow_state:
        # Check escape words first
        if content_lower in ESCAPE_WORDS:
            _clear_flow_state(phone_hash)
            return {
                'suggestedResponse': "No worries! Back to the main menu 👇",
                'suggestion': "No worries! Back to the main menu 👇",
                'flowAction': 'showMainMenu',
            }

        flow_name = flow_state.get('flow', '')
        step = flow_state.get('step', '')
        data = flow_state.get('data', {})
        flows = flow_config.get('flows', {})

        # ── Subscribe flow ──
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
                    done_msg = sub_prompts.get('done', "You're all set! ✅").format(name=data.get('name', ''))
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

        # ── Pay flow ──
        if flow_name == 'pay':
            pay_prompts = flows.get('pay', {})
            default_gst = float(pay_prompts.get('default_gst_rate', 18))
            default_shipping = float(pay_prompts.get('default_shipping', 49))
            gstin = pay_prompts.get('gstin', '19AADFW7431N1ZK')
            default_item = pay_prompts.get('default_item_name', 'Services/Goods')

            # ── Due choice: pay ALL / pay ONE / new payment ──
            if step == 'awaiting_due_choice':
                if content_lower in ('1', 'all', 'pay all'):
                    pending_dues = data.get('pending_dues', [])
                    if pending_dues:
                        total_due = sum(d['amount'] for d in pending_dues)
                        data['amount'] = total_due
                        data['quantity'] = 1
                        brands = ', '.join(d.get('item', 'Due') for d in pending_dues[:3])
                        data['item_name'] = f"All Dues ({brands})"
                        data['payment_purpose'] = brands if brands != 'Due' else 'Pending Dues'
                        data['due_ref'] = pending_dues[0]['ref']
                        data['due_number'] = 'ALL'
                        data['from_dues'] = True
                        _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                        return _r(f"\u2705 All {len(pending_dues)} dues clubbed \u2192 \u20b9{total_due:,.2f}\n\n\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")
                    _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', {})
                    return _r(_pay_purpose_prompt())
                elif content_lower in ('2', 'one', 'pay one'):
                    pending_dues = data.get('pending_dues', [])
                    if len(pending_dues) == 1:
                        due = pending_dues[0]
                        brand = due.get('item', 'Due')
                        data['amount'] = due['amount']
                        data['quantity'] = 1
                        data['item_name'] = brand
                        data['payment_purpose'] = brand
                        data['due_ref'] = due['ref']
                        data['due_number'] = '1'
                        data['from_dues'] = True
                        _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                        return _r(f"\u2705 Due #1 \u2022 {brand} \u2022 \u20b9{due['amount']:,.2f}\n\n\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")
                    # Multiple dues — ask which one
                    lines = ["\U0001f4cb Pick one to pay\n"]
                    for i, d in enumerate(pending_dues[:5], 1):
                        brand = d.get('item', 'Due')
                        masked = f"...{d['ref'][-4:]}" if len(d['ref']) > 4 else d['ref']
                        due_date = ''
                        if d.get('createdAt'):
                            try:
                                import datetime
                                dt = datetime.datetime.fromtimestamp(d['createdAt'])
                                due_date = f" \u2022 Due: {dt.strftime('%d %b')}"
                            except Exception:
                                pass
                        lines.append(f" {i}. {brand} \u2022 \u20b9{d['amount']:,.2f}{due_date} ({masked})")
                    lines.append(f"\nReply 1\u2013{min(len(pending_dues), 5)} \u00b7 BACK \u00b7 CANCEL")
                    data['selecting_due'] = True
                    _save_flow_state(phone_hash, 'pay', 'awaiting_due_select', data)
                    return _r("\n".join(lines))
                elif content_lower in ('3', 'new', 'new payment', 'advance'):
                    _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', {})
                    return _r(_pay_purpose_prompt())
                else:
                    return _r("Reply 1 (pay all), 2 (pick one), or 3 (new payment) \u00b7 CANCEL")

            # ── Due selection (pick one) ──
            if step == 'awaiting_due_select':
                if content_lower == 'back':
                    pending_dues = data.get('pending_dues', [])
                    _save_flow_state(phone_hash, 'pay', 'awaiting_due_choice', data)
                    return _r(_dues_prompt(pending_dues))
                pending_dues = data.get('pending_dues', [])
                try:
                    idx = int(content_lower) - 1
                    if 0 <= idx < len(pending_dues):
                        due = pending_dues[idx]
                        brand = due.get('item', 'Due')
                        data['amount'] = due['amount']
                        data['quantity'] = 1
                        data['item_name'] = brand
                        data['payment_purpose'] = brand
                        data['due_ref'] = due['ref']
                        data['due_number'] = str(idx + 1)
                        data.pop('selecting_due', None)
                        data['from_dues'] = True
                        _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                        return _r(f"\u2705 Due #{idx + 1} \u2022 {brand} \u2022 \u20b9{due['amount']:,.2f}\n\n\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")
                except (ValueError, IndexError):
                    pass
                return _r(f"Reply 1\u2013{min(len(pending_dues), 5)} \u00b7 BACK \u00b7 CANCEL")

            # ── Purpose ──
            if step == 'awaiting_purpose':
                if content_lower == 'back':
                    # If came from dues, go back to due choice; otherwise show menu
                    if data.get('pending_dues'):
                        pending_dues = data.get('pending_dues', [])
                        _save_flow_state(phone_hash, 'pay', 'awaiting_due_choice', data)
                        return _r(_dues_prompt(pending_dues))
                    _clear_flow_state(phone_hash)
                    return {
                        'suggestedResponse': "Back to menu \U0001f44c",
                        'suggestion': "Back to menu \U0001f44c",
                        'flowAction': 'showMainMenu',
                    }
                if content_lower in PURPOSE_MAP:
                    purpose = PURPOSE_MAP[content_lower]
                else:
                    purpose = re.sub(r'\s+', ' ', message_content.strip()).title()[:40]
                data['payment_purpose'] = purpose
                _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                return _r(f"\u2705 Purpose: *{purpose}*\n\n\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")

            # ── Order ID ──
            if step == 'awaiting_order_id':
                if content_lower == 'back':
                    if data.get('from_dues'):
                        pending_dues = data.get('pending_dues', [])
                        if pending_dues:
                            _save_flow_state(phone_hash, 'pay', 'awaiting_due_choice', data)
                            return _r(_dues_prompt(pending_dues))
                    _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', data)
                    return _r(_pay_purpose_prompt())
                if content_lower in ('skip', 'na', 'none', 'offline', '-'):
                    data['order_id'] = 'Offline'
                else:
                    data['order_id'] = message_content.strip()[:40]
                # Always ask: Who is this for?
                _save_flow_state(phone_hash, 'pay', 'awaiting_pay_for', data)
                return _r(
                    f"\U0001f4cb Order: *{data['order_id']}*\n\n"
                    f"\U0001f464 Who is this payment for?\n"
                    f" 1 \u2192 Self\n"
                    f" 2 \u2192 Someone else\n\n"
                    f"Reply 1/2 \u00b7 BACK \u00b7 CANCEL"
                )

            # ── Reuse saved profile (Self only — 2 options) ──
            if step == 'awaiting_reuse_profile':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_pay_for', data)
                    return _r("\U0001f464 Who is this payment for?\n 1 \u2192 Self\n 2 \u2192 Someone else\n\nReply 1/2 \u00b7 BACK \u00b7 CANCEL")
                if content_lower in ('1', 'use', 'use saved', 'yes', 'y'):
                    profile = data.get('saved_profile', {})
                    data['customer_name'] = profile.get('customer_name', '')
                    data['customer_phone'] = profile.get('customer_phone', sender_phone)
                    data['customer_email'] = profile.get('customer_email', '')
                    data['shipping_address'] = profile.get('shipping_address', '')
                    data['billing_address'] = profile.get('billing_address', profile.get('shipping_address', ''))
                    data['pay_for'] = 'self'
                    data.pop('saved_profile', None)
                    # If shipping address missing, collect it
                    if not data.get('shipping_address'):
                        _save_flow_state(phone_hash, 'pay', 'awaiting_shipping_address', data)
                        return _r("\u2705 Profile loaded\n\n\U0001f4e6 Shipping address?\nBACK \u00b7 CANCEL")
                    # If dues flow, amount already set — go to summary
                    if data.get('from_dues') and data.get('amount'):
                        return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                    _save_flow_state(phone_hash, 'pay', 'awaiting_amount', data)
                    return _r("\u2705 Profile loaded\n\n\U0001f4b3 Amount? (e.g. 500, 500x2, 2x500)\nBACK \u00b7 CANCEL")
                elif content_lower in ('2', 'edit'):
                    data.pop('saved_profile', None)
                    data['pay_for'] = 'self'
                    data['customer_phone'] = sender_phone
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    return _r("\u270f\ufe0f Full name?\nBACK \u00b7 CANCEL")
                else:
                    return _r("Reply 1 (use saved) or 2 (edit) \u00b7 BACK \u00b7 CANCEL")

            # ── Pay for self or other ──
            if step == 'awaiting_pay_for':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                    return _r("\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")
                if content_lower in ('1', 'self', 'me'):
                    data['pay_for'] = 'self'
                    data['customer_phone'] = sender_phone
                    # Check for saved profile — show only for Self
                    profile = _load_customer_profile(phone_hash)
                    if not profile.get('customer_name'):
                        profile = _load_contact_as_profile(sender_phone)
                    if profile.get('customer_name'):
                        name = profile.get('customer_name', '')
                        phone_disp = profile.get('customer_phone', sender_phone)
                        email = profile.get('customer_email', '')
                        ship = profile.get('shipping_address', '')
                        data['saved_profile'] = profile
                        saved_msg = (
                            f"\U0001f464 *Saved Profile*\n"
                            f"\U0001f464 {name}\n"
                            f"\U0001f4de {phone_disp}\n"
                            f"\u2709\ufe0f {email or '\u2014'}\n"
                            f"\U0001f4e6 {ship or '\u2014'}\n\n"
                            " 1 \u2192 Use saved details\n"
                            " 2 \u2192 Edit details\n\n"
                            "Reply 1/2 \u00b7 BACK \u00b7 CANCEL"
                        )
                        _save_flow_state(phone_hash, 'pay', 'awaiting_reuse_profile', data)
                        return _r(saved_msg)
                    # No saved profile — collect name
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    return _r("\u270f\ufe0f Full name?\nBACK \u00b7 CANCEL")
                elif content_lower in ('2', 'other', 'someone', 'someone else'):
                    data['pay_for'] = 'other'
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    return _r("\u270f\ufe0f Customer\u2019s full name?\nBACK \u00b7 CANCEL")
                else:
                    return _r("\U0001f464 Reply 1 (Self) or 2 (Someone else) \u00b7 BACK \u00b7 CANCEL")

            # ── Customer name ──
            if step == 'awaiting_customer_name':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_pay_for', data)
                    return _r("\U0001f464 Who is this payment for?\n 1 \u2192 Self\n 2 \u2192 Someone else\n\nReply 1/2 \u00b7 BACK \u00b7 CANCEL")
                name = message_content.strip()
                if len(name) < 2 or len(name) > 100:
                    return _r("\u26a0\ufe0f Name must be 2\u2013100 characters \u00b7 BACK \u00b7 CANCEL")
                data['customer_name'] = name.title()
                if data.get('pay_for') == 'other':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_phone', data)
                    return _r("\U0001f4de Customer\u2019s phone (with country code)?\nBACK \u00b7 CANCEL")
                _save_flow_state(phone_hash, 'pay', 'awaiting_customer_email', data)
                return _r("\u2709\ufe0f Email? (SKIP if none)\nBACK \u00b7 CANCEL")

            # ── Customer phone (other only) ──
            if step == 'awaiting_customer_phone':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    return _r("\u270f\ufe0f Customer\u2019s full name?\nBACK \u00b7 CANCEL")
                phone = message_content.strip()
                if not re.match(r'^\+?\d[\d\s\-]{7,18}$', phone):
                    return _r("\u26a0\ufe0f Invalid phone. Example: +919876543210\nBACK \u00b7 CANCEL")
                data['customer_phone'] = re.sub(r'[\s\-]', '', phone)
                _save_flow_state(phone_hash, 'pay', 'awaiting_customer_email', data)
                return _r("\u2709\ufe0f Email? (SKIP if none)\nBACK \u00b7 CANCEL")

            # ── Customer email ──
            if step == 'awaiting_customer_email':
                if content_lower == 'back':
                    if data.get('pay_for') == 'other':
                        _save_flow_state(phone_hash, 'pay', 'awaiting_customer_phone', data)
                        return _r("\U0001f4de Customer\u2019s phone (with country code)?\nBACK \u00b7 CANCEL")
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    return _r("\u270f\ufe0f Full name?\nBACK \u00b7 CANCEL")
                email = message_content.strip()
                if content_lower in ('skip', 'na', 'none', '-'):
                    data['customer_email'] = ''
                elif re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
                    data['customer_email'] = email.lower()
                else:
                    return _r("\u26a0\ufe0f Invalid email. Try again or SKIP\nBACK \u00b7 CANCEL")
                _save_flow_state(phone_hash, 'pay', 'awaiting_shipping_address', data)
                return _r("\U0001f4e6 Shipping address?\n(Saved for future orders)\nBACK \u00b7 CANCEL")

            # ── Shipping address (mandatory) ──
            if step == 'awaiting_shipping_address':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_email', data)
                    return _r("\u2709\ufe0f Email? (SKIP if none)\nBACK \u00b7 CANCEL")
                addr = message_content.strip()
                if len(addr) < 5:
                    return _r("\u26a0\ufe0f Enter a valid shipping address\nBACK \u00b7 CANCEL")
                data['shipping_address'] = addr[:200]
                _save_flow_state(phone_hash, 'pay', 'awaiting_billing_same', data)
                return _r("\U0001f3e2 Billing same as shipping?\nYES / NO \u00b7 BACK \u00b7 CANCEL")

            # ── Billing same as shipping? ──
            if step == 'awaiting_billing_same':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_shipping_address', data)
                    return _r("\U0001f4e6 Shipping address?\nBACK \u00b7 CANCEL")
                if content_lower in ('yes', 'y', 'same', 'haan', 'ha'):
                    data['billing_address'] = data.get('shipping_address', '')
                else:
                    _save_flow_state(phone_hash, 'pay', 'awaiting_billing_address', data)
                    return _r("\U0001f3e2 Billing address?\nBACK \u00b7 CANCEL")
                _save_customer_profile(phone_hash, {
                    'customer_name': data.get('customer_name', ''),
                    'customer_phone': data.get('customer_phone', sender_phone),
                    'customer_email': data.get('customer_email', ''),
                    'shipping_address': data.get('shipping_address', ''),
                    'billing_address': data.get('billing_address', ''),
                })
                _update_contact_with_customer_info(sender_phone, data, request_id)
                # If dues flow, amount already set — go to summary
                if data.get('from_dues') and data.get('amount'):
                    return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                _save_flow_state(phone_hash, 'pay', 'awaiting_amount', data)
                return _r("\u2705 Saved\n\n\U0001f4b3 Amount? (e.g. 500, 500x2, 2x500)\nBACK \u00b7 CANCEL")

            # ── Billing address ──
            if step == 'awaiting_billing_address':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_billing_same', data)
                    return _r("\U0001f3e2 Billing same as shipping?\nYES / NO \u00b7 BACK \u00b7 CANCEL")
                addr = message_content.strip()
                if len(addr) < 5:
                    return _r("\u26a0\ufe0f Enter a valid billing address\nBACK \u00b7 CANCEL")
                data['billing_address'] = addr[:200]
                _save_customer_profile(phone_hash, {
                    'customer_name': data.get('customer_name', ''),
                    'customer_phone': data.get('customer_phone', sender_phone),
                    'customer_email': data.get('customer_email', ''),
                    'shipping_address': data.get('shipping_address', ''),
                    'billing_address': data.get('billing_address', ''),
                })
                _update_contact_with_customer_info(sender_phone, data, request_id)
                # If dues flow, amount already set — go to summary
                if data.get('from_dues') and data.get('amount'):
                    return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                _save_flow_state(phone_hash, 'pay', 'awaiting_amount', data)
                return _r("\u2705 Saved\n\n\U0001f4b3 Amount? (e.g. 500, 500x2, 2x500)\nBACK \u00b7 CANCEL")

            # ── Amount (flexible: 500, 500x2, 2x500, 500*2) ──
            if step == 'awaiting_amount':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_billing_same', data)
                    return _r("\U0001f3e2 Billing same as shipping?\nYES / NO \u00b7 BACK \u00b7 CANCEL")
                raw = message_content.strip()
                # Try PxN format (e.g. 500x2, 500*2)
                m_pxn = re.match(r'^(\d+(?:\.\d+)?)\s*[x*×]\s*(\d+)$', raw, re.IGNORECASE)
                if m_pxn:
                    price_val = float(m_pxn.group(1))
                    qty_val = int(m_pxn.group(2))
                    if 1 <= price_val <= 100000 and 1 <= qty_val <= 999:
                        data['amount'] = price_val
                        data['quantity'] = qty_val
                        data['item_name'] = data.get('item_name', default_item)
                        return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                    return _r("\u26a0\ufe0f Price 1\u2013100000, qty 1\u2013999\nBACK \u00b7 CANCEL")
                # Try NxP format (e.g. 2x500)
                m_nxp = re.match(r'^(\d+)\s*[x*×]\s*(\d+(?:\.\d+)?)$', raw, re.IGNORECASE)
                if m_nxp:
                    qty_val = int(m_nxp.group(1))
                    price_val = float(m_nxp.group(2))
                    if 1 <= price_val <= 100000 and 1 <= qty_val <= 999:
                        data['amount'] = price_val
                        data['quantity'] = qty_val
                        data['item_name'] = data.get('item_name', default_item)
                        return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                    return _r("\u26a0\ufe0f Price 1\u2013100000, qty 1\u2013999\nBACK \u00b7 CANCEL")
                # Plain number
                amount_str = re.sub(r'[^\d.]', '', raw)
                try:
                    amount = float(amount_str)
                    if amount < 1 or amount > 100000:
                        raise ValueError("out of range")
                except (ValueError, TypeError):
                    return _r("\u26a0\ufe0f Amount 1\u2013100000\nExamples: 500, 500x2, 2x500\nBACK \u00b7 CANCEL")
                data['amount'] = amount
                _save_flow_state(phone_hash, 'pay', 'awaiting_quantity', data)
                return _r(f"\U0001f4b3 \u20b9{amount:,.2f}\n\n\U0001f4e6 Quantity? (1 for single)\nBACK \u00b7 CANCEL")

            # ── Quantity ──
            if step == 'awaiting_quantity':
                if content_lower == 'back':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_amount', data)
                    return _r("\U0001f4b3 Amount? (e.g. 500, 500x2, 2x500)\nBACK \u00b7 CANCEL")
                qty_str = re.sub(r'[^\d]', '', message_content.strip())
                try:
                    qty = int(qty_str) if qty_str else 1
                    if qty < 1 or qty > 999:
                        raise ValueError("out of range")
                except (ValueError, TypeError):
                    return _r("\u26a0\ufe0f Quantity 1\u2013999\nBACK \u00b7 CANCEL")
                data['quantity'] = qty
                data['item_name'] = data.get('item_name', default_item)
                return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)

            # ── Confirmation (YES / NO / EDIT) ──
            if step == 'awaiting_confirmation':
                if content_lower in ('yes', 'y', 'confirm', 'ok', 'haan', 'ha'):
                    amount = data.get('subtotal', data.get('amount', 0))
                    _clear_flow_state(phone_hash)
                    sending_msg = "\u2705 Sending payment link\u2026\n\U0001f9fe You\u2019ll receive one link. Invoice follows after payment."
                    return {
                        'suggestedResponse': sending_msg,
                        'suggestion': sending_msg,
                        'flowAction': 'sendPayment',
                        'paymentAmount': data.get('amount', 0),
                        'paymentQuantity': data.get('quantity', 1),
                        'paymentItemName': data.get('item_name', default_item),
                        'paymentGstRate': data.get('gst_rate', default_gst),
                        'paymentShipping': data.get('shipping', default_shipping),
                        'paymentDiscount': data.get('discount', 0),
                        'paymentPurpose': data.get('payment_purpose', ''),
                        'paymentDueRef': data.get('due_ref', ''),
                        'paymentOrderId': data.get('order_id', 'Offline'),
                        'paymentCustomerName': data.get('customer_name', ''),
                        'paymentCustomerPhone': data.get('customer_phone', sender_phone),
                        'paymentCustomerEmail': data.get('customer_email', ''),
                        'paymentShippingAddress': data.get('shipping_address', ''),
                        'paymentBillingAddress': data.get('billing_address', ''),
                        'paymentPayFor': data.get('pay_for', 'self'),
                    }
                elif content_lower in ('no', 'n', 'nahi', 'nope'):
                    _clear_flow_state(phone_hash)
                    return {
                        'suggestedResponse': "\u274c Payment cancelled.",
                        'suggestion': "\u274c Payment cancelled.",
                        'flowAction': 'showMainMenu',
                    }
                elif content_lower in ('edit', 'change', 'modify'):
                    _save_flow_state(phone_hash, 'pay', 'awaiting_edit_choice', data)
                    return _r(EDIT_MENU)
                else:
                    return _r(f"*YES* to pay \u20b9{data.get('total', 0):,.2f} \u00b7 *NO* to cancel \u00b7 *EDIT*")

            # ── Edit menu ──

            if step == 'awaiting_edit_choice':
                if content_lower == 'back':
                    return _build_pay_summary(data, pay_prompts, default_gst, default_shipping, gstin, default_item, phone_hash, sender_phone)
                if content_lower == '1':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', data)
                    return _r(_pay_purpose_prompt())
                elif content_lower == '2':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_order_id', data)
                    return _r("\U0001f4cb Order ID?\nType SKIP if none \u00b7 BACK \u00b7 CANCEL")
                elif content_lower == '3':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_customer_name', data)
                    label = "Customer\u2019s full name?" if data.get('pay_for') == 'other' else "Full name?"
                    return _r(f"\u270f\ufe0f {label}\nBACK \u00b7 CANCEL")
                elif content_lower == '4':
                    _save_flow_state(phone_hash, 'pay', 'awaiting_amount', data)
                    return _r("\U0001f4b3 New amount? (e.g. 500, 500x2)\nBACK \u00b7 CANCEL")
                elif content_lower == '5':
                    _clear_flow_state(phone_hash)
                    return {
                        'suggestedResponse': '\u274c Payment cancelled.',
                        'suggestion': '\u274c Payment cancelled.',
                        'flowAction': 'showMainMenu',
                    }
                else:
                    return _r("Reply 1\u20135 \u00b7 BACK \u00b7 CANCEL")
        # ── Toggle flows (audio/notifications) ──
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

    # ── "menu" keyword trigger — show main menu on demand ──
    if content_lower in ('menu', 'main menu', 'show menu', 'hi', 'hello'):
        greeting = flow_config.get('welcome', {}).get('text', '') if not history.get('messages') else flow_config.get('welcomeBack', {}).get('text', "Here's the menu 👇")
        return {
            'suggestedResponse': greeting or "Here's the menu 👇",
            'suggestion': greeting or "Here's the menu 👇",
            'flowAction': 'showMainMenu',
        }

    # ── Keyword-based pay flow trigger ──
    PAY_KEYWORDS = {
        'pay', 'payment', 'i want to pay', 'make payment', 'make a payment',
        'send payment', 'pay now', 'pay bill', 'bill pay', 'pay due',
        'pay dues', 'pending payment', 'pending due', 'bhugtan', 'paisa',
        'rupees', 'amount pay', 'pay amount', 'invoice', 'pay invoice',
    }
    if content_lower in PAY_KEYWORDS or any(kw in content_lower for kw in ('want to pay', 'make payment', 'pay my', 'pay the', 'pay for')):
        pending = _check_pending_payments(phone_hash, request_id, sender_phone)
        flows_config = flow_config.get('flows', {}).get('pay', {})
        if pending:
            due_msg = _dues_prompt(pending)
            _save_flow_state(phone_hash, 'pay', 'awaiting_due_choice', {'pending_dues': pending})
            return {
                'suggestedResponse': due_msg,
                'suggestion': due_msg,
            }
        _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', {})
        return _r(_pay_purpose_prompt())

    # ── Main menu / store item selected ──
    if content_lower.startswith('menu_') or content_lower.startswith('store_'):
        menu_responses = flow_config.get('menuResponses', {})
        item = menu_responses.get(content_lower)
        if item:
            action = item.get('action', '')

            # Show language picker (Step 1: region picker)
            if action == 'show_language_picker':
                lp_config = _get_language_picker_config_from_db()
                return {
                    'suggestedResponse': '🌐 Choose your region to see available languages 👇',
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
                        'suggestedResponse': sub_menu.get('body', 'Choose an option 👇'),
                        'suggestion': sub_menu.get('body', 'Choose an option 👇'),
                        'flowAction': 'showSubMenu',
                        'subMenuConfig': sub_menu,
                    }
                return None

            # Back to main menu (from sub-menus)
            if action == 'show_main_menu':
                return {
                    'suggestedResponse': "Here's the menu 👇",
                    'suggestion': "Here's the menu 👇",
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

            # Start pay flow — check for pending dues first
            if action == 'start_pay_flow':
                pending = _check_pending_payments(phone_hash, request_id, sender_phone)
                flows_config = flow_config.get('flows', {}).get('pay', {})
                if pending:
                    due_msg = _dues_prompt(pending)
                    _save_flow_state(phone_hash, 'pay', 'awaiting_due_choice', {'pending_dues': pending})
                    return {
                        'suggestedResponse': due_msg,
                        'suggestion': due_msg,
                    }
                _save_flow_state(phone_hash, 'pay', 'awaiting_purpose', {})
                return _r(_pay_purpose_prompt())

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

    # ── Options: Do more ──
    if content_lower == 'opt_do_more':
        do_more = flow_config.get('doMore', {})
        return {
            'suggestedResponse': do_more.get('text', ''),
            'suggestion': do_more.get('text', ''),
            'flowAction': 'showMainMenu',
        }

    # ── Options: Done ──
    if content_lower == 'opt_done':
        done = flow_config.get('done', {})
        return {
            'suggestedResponse': done.get('text', ''),
            'suggestion': done.get('text', ''),
            'flowAction': 'showRating',
        }

    # ── Rating selection ──
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


# ── Pay helpers ──

def _r(msg: str) -> Dict:
    """Shorthand: return a simple suggestedResponse/suggestion pair."""
    return {'suggestedResponse': msg, 'suggestion': msg}


def _dues_prompt(pending_dues: list) -> str:
    """Build the pending dues prompt with brand, readable ref, amount, and due date."""
    total_due = sum(d['amount'] for d in pending_dues)
    dues_lines = []
    for i, d in enumerate(pending_dues[:5], 1):
        brand = d.get('item', 'Services/Goods')
        ref = d.get('ref', 'N/A')
        amount = d['amount']
        # Readable ref: Due #1, #2, etc. + masked original ref
        readable_ref = f"Due #{i}"
        masked_ref = f"...{ref[-4:]}" if len(ref) > 4 else ref
        # Due date from createdAt (show as DD Mon)
        created = d.get('createdAt', 0)
        due_date = ''
        if created:
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(created)
                due_date = dt.strftime('%d %b')
            except Exception:
                pass
        # Format: BNB Club • Due #1 • ₹1,000 • Due: 10 Feb (…a1b2)
        line_parts = [f" {i}. {brand}"]
        line_parts.append(f"{readable_ref}")
        line_parts.append(f"\u20b9{amount:,.2f}")
        if due_date:
            line_parts.append(f"Due: {due_date}")
        line_parts.append(f"({masked_ref})")
        dues_lines.append(" \u2022 ".join(line_parts))
    dues_text = "\n".join(dues_lines)
    return (
        f"\U0001f4cc *{len(pending_dues)} Pending* \u2014 Total \u20b9{total_due:,.2f}\n\n"
        f"{dues_text}\n\n"
        f" 1 \u2192 Pay ALL pending (\u20b9{total_due:,.2f})\n"
        f" 2 \u2192 Pay a specific due\n"
        f" 3 \u2192 Create a new payment\n\n"
        f"Reply 1/2/3 \u00b7 CANCEL"
    )


def _pay_purpose_prompt() -> str:
    """Return the formatted purpose list used in multiple places."""
    return (
        "\U0001f3af *Select a purpose*\n\n"
        "\U0001f3ea *Our Brands*\n"
        " 1. \u2708\ufe0f BNB Club \u2014 Travel\n"
        " 2. \u2696\ufe0f No Fault \u2014 ODR\n"
        " 3. \U0001f30d Expo Week \u2014 Events\n"
        " 4. \U0001f64f Ritual Guru \u2014 Puja\n"
        " 5. \U0001f4dc Legal Champ \u2014 Docs\n"
        " 6. \U0001f9d8 Swdhya \u2014 Samvad\n"
        " 7. \U0001f381 Gift Card\n\n"
        "\U0001f4c2 *General*\n"
        " 8. Advance Payment\n"
        " 9. Service Fee\n"
        " 10. Subscription\n"
        " 11. Consultation\n\n"
        "Reply 1\u201311 or type your own \u00b7 BACK \u00b7 CANCEL"
    )


PURPOSE_MAP = {
    '1': 'BNB Club — Travel',
    '2': 'No Fault — ODR',
    '3': 'Expo Week — Events',
    '4': 'Ritual Guru — Puja',
    '5': 'Legal Champ — Docs',
    '6': 'Swdhya — Samvad',
    '7': 'Gift Card',
    '8': 'Advance Payment',
    '9': 'Service Fee',
    '10': 'Subscription',
    '11': 'Consultation',
}


EDIT_MENU = (
    "\u270f\ufe0f *Edit Payment*\n\n"
    " 1. Purpose\n"
    " 2. Order ID\n"
    " 3. Customer details\n"
    " 4. Amount / Qty\n"
    " 5. Cancel payment\n\n"
    "Reply 1\u20135 \u00b7 BACK \u00b7 CANCEL"
)


# ── Pay summary builder ──

def _build_pay_summary(data: Dict, pay_prompts: Dict, default_gst: float,
                       default_shipping: float, gstin: str, default_item: str,
                       phone_hash: str, sender_phone: str = '') -> Dict:
    """Calculate breakdown with fixed promo and return summary + save confirmation state."""
    unit_price = data.get('amount', 0)
    qty = data.get('quantity', 1)
    item_name = data.get('item_name', default_item)
    promo = float(pay_prompts.get('default_promo', 15))
    subtotal = unit_price * qty
    # Cap promo so it never exceeds subtotal
    promo = min(promo, subtotal)
    after_promo = subtotal - promo
    gst_amount = round(after_promo * default_gst / 100, 2)
    shipping = default_shipping
    conv_base = round(after_promo * 0.02, 2)
    conv_gst = round(conv_base * 0.18, 2)
    conv_fee = round(conv_base + conv_gst, 2)
    total = round(after_promo + gst_amount + shipping + conv_fee, 2)

    data['subtotal'] = subtotal
    data['discount'] = promo
    data['gst_rate'] = default_gst
    data['gst_amount'] = gst_amount
    data['shipping'] = shipping
    data['conv_fee'] = conv_fee
    data['total'] = total

    # Build summary
    lines = ["\U0001f9fe *Order Summary*\n"]
    cust_name = data.get('customer_name', '')
    cust_phone = data.get('customer_phone', '')
    cust_email = data.get('customer_email', '')
    order_id = data.get('order_id', 'Offline')
    pay_for = data.get('pay_for', 'self')
    if cust_name:
        lines.append(f"\U0001f464 {cust_name}")
    if cust_phone:
        lines.append(f"\U0001f4de {cust_phone}")
    if cust_email:
        lines.append(f"\u2709\ufe0f {cust_email}")
    ship_addr = data.get('shipping_address', '')
    bill_addr = data.get('billing_address', '')
    if ship_addr:
        lines.append(f"\U0001f4e6 Ship: {ship_addr[:60]}")
    if bill_addr and bill_addr != ship_addr:
        lines.append(f"\U0001f3e2 Bill: {bill_addr[:60]}")
    if pay_for == 'other':
        lines.append(f"\U0001f4b3 Paid by: {sender_phone}")
    else:
        lines.append(f"\U0001f4b3 Paid by: Self")
    lines.append(f"\U0001f4cb Order: {order_id}")
    lines.append("\u2500" * 20)
    # Show purpose/brand as the item line instead of generic "Services/Goods"
    purpose = data.get('payment_purpose', '')
    display_item = purpose if purpose else item_name
    lines.append(f"*{display_item}*")
    if data.get('due_ref'):
        ref = data['due_ref']
        masked = f"...{ref[-6:]}" if len(ref) > 6 else ref
        # Generate readable due ref
        due_num = data.get('due_number', '')
        if due_num:
            lines.append(f"Due #{due_num} ({masked})")
        else:
            lines.append(f"Ref: {masked}")
    lines.append(f"\u20b9{unit_price:,.2f} \u00d7 {qty}")
    lines.append(f"Subtotal  \u20b9{subtotal:,.2f}")
    lines.append(f"Promo     \u2212\u20b9{promo:,.2f}")
    lines.append(f"GST {default_gst:.0f}%   \u20b9{gst_amount:,.2f}")
    lines.append(f"Shipping  \u20b9{shipping:,.2f}")
    lines.append(f"Conv Fee  \u20b9{conv_fee:,.2f}")
    lines.append("\u2500" * 20)
    lines.append(f"\u2705 *Total: \u20b9{total:,.2f}*")
    lines.append(f"GSTIN: {gstin}")
    lines.append("")
    lines.append("*YES* to pay \u00b7 *NO* to cancel \u00b7 *EDIT*")

    breakdown = "\n".join(lines)
    _save_flow_state(phone_hash, 'pay', 'awaiting_confirmation', data)
    return _r(breakdown)


# ── Customer profile helpers (for returning customers) ──

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


# ── Flow state helpers (DynamoDB) ──

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

            # Scan for pending payment_request records for this phone
            # (In production, a GSI on senderPhone+status would be ideal)
            try:
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

        # Fallback to KB if agent returns empty
        if kb_id:
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)

        return _get_fallback_response(lang_name)

    except Exception as e:
        logger.error(json.dumps({
            'event': 'bedrock_agent_error',
            'error': str(e),
            'requestId': request_id
        }))
        if kb_id:
            detected_lang, lang_name = _detect_language(user_message)
            return _query_knowledge_base(user_message, kb_id, detected_lang, lang_name, request_id)
        return _get_fallback_response()


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================

def _detect_language(text: str) -> Tuple[str, str]:
    """Detect language from text using character patterns."""
    if not text:
        return ('en', 'English')

    if re.search(r'[\u0900-\u097F]', text):
        marathi_words = ['आहे', 'काय', 'मला', 'तुम्ही', 'आम्ही']
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
# KB QUERY (for internal fallback — unchanged)
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
- Travel/Hotels/Visa → BNB Club (bnbclub.in)
- Documents/Registration/GST → Legal Champ (legalchamp.in)
- Disputes/Complaints → No Fault (nofault.in)
- Puja/Rituals → Ritual Guru (ritualguru.in)
- Self-inquiry/Reflection → Swdhya (swdhya.in)

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
        'Hindi': "नमस्ते! 👋 WECARE.DIGITAL से संपर्क करने के लिए धन्यवाद। त्वरित सहायता के लिए +91 9330994400 पर कॉल करें या one@wecare.digital पर ईमेल करें। 😊",
        'Bengali': "নমস্কার! 👋 WECARE.DIGITAL-এ যোগাযোগ করার জন্য ধন্যবাদ। দ্রুত সাহায্যের জন্য +91 9330994400-এ কল করুন বা one@wecare.digital-এ ইমেল করুন। 😊",
        'Hinglish': "Hi! 👋 WECARE.DIGITAL se contact karne ke liye thanks. Quick help ke liye +91 9330994400 pe call karein ya one@wecare.digital pe email karein. 😊",
        'Tamil': "வணக்கம்! 👋 WECARE.DIGITAL-ஐ தொடர்பு கொண்டதற்கு நன்றி। விரைவான உதவிக்கு +91 9330994400 அழைக்கவும் அல்லது one@wecare.digital மின்னஞ்சல் அனுப்பவும். 😊",
        'Telugu': "నమస్కారం! 👋 WECARE.DIGITAL ని సంప్రదించినందుకు ధన్యవాదాలు। త్వరిత సహాయం కోసం +91 9330994400 కు కాల్ చేయండి లేదా one@wecare.digital కు ఇమెయిల్ చేయండి. 😊",
        'Gujarati': "નમસ્તે! 👋 WECARE.DIGITAL નો સંપર્ક કરવા બદલ આભાર. ઝડપી મદદ માટે +91 9330994400 પર કૉલ કરો અથવા one@wecare.digital પર ઇમેઇલ કરો. 😊",
        'Marathi': "नमस्कार! 👋 WECARE.DIGITAL शी संपर्क साधल्याबद्दल धन्यवाद। जलद मदतीसाठी +91 9330994400 वर कॉल करा किंवा one@wecare.digital वर ईमेल करा. 😊",
    }
    return fallback_responses.get(lang_name, "Hi! 👋 Thanks for reaching out to WECARE.DIGITAL. For quick help, call us at +91 9330994400 or email one@wecare.digital. We're here to help! 😊")
