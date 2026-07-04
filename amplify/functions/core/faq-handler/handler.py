"""
FAQ Handler Lambda Function

Purpose: Keyword-based FAQ search and response system
Cost: FREE - no external dependencies, no OpenSearch, no Bedrock
"""

import os
import json
import logging
from typing import Dict, Any, List, Tuple

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# Load FAQ configuration
FAQ_CONFIG = {
    "brand": {
        "name": "WECARE.DIGITAL",
        "website": "https://wecare.digital",
        "store": "https://store.wecare.digital",
        "email": "one@wecare.digital",
        "phone": "+91 9330994400",
        "whatsapp": "+91 9330994400"
    },
    "faqs": [
        {
            "id": "hours",
            "keywords": ["hours", "timing", "open", "close", "available", "when", "time"],
            "category": "general",
            "question": "What are your business hours?",
            "answer": "We are available 24/7 for online orders and support. For urgent assistance, call us at +91 9330994400 or email one@wecare.digital.",
            "shortAnswer": "24/7 available"
        },
        {
            "id": "contact",
            "keywords": ["contact", "reach", "call", "email", "phone", "support", "help"],
            "category": "general",
            "question": "How can I contact you?",
            "answer": "You can reach us via:\\n• Phone/WhatsApp: +91 9330994400\\n• Email: one@wecare.digital\\n• Website: https://wecare.digital",
            "shortAnswer": "Call +91 9330994400 or email one@wecare.digital"
        },
        {
            "id": "order",
            "keywords": ["order", "buy", "purchase", "shop", "product", "cart"],
            "category": "orders",
            "question": "How do I place an order?",
            "answer": "Visit our store at https://store.wecare.digital to browse products and place orders. You can also order via WhatsApp by sending us a message at +91 9330994400.",
            "shortAnswer": "Visit store.wecare.digital or WhatsApp us"
        },
        {
            "id": "payment",
            "keywords": ["payment", "pay", "price", "cost", "fee", "charge", "upi", "card"],
            "category": "payments",
            "question": "What payment methods do you accept?",
            "answer": "We accept:\\n• UPI (Google Pay, PhonePe, Paytm)\\n• Credit/Debit Cards\\n• Net Banking\\n• Razorpay Payment Gateway\\n\\nA 2% convenience fee + 18% GST applies to all payments.",
            "shortAnswer": "UPI, Cards, Net Banking (2% + GST fee applies)"
        },
        {
            "id": "delivery",
            "keywords": ["delivery", "shipping", "ship", "courier", "dispatch", "send"],
            "category": "orders",
            "question": "What are your delivery options?",
            "answer": "We offer standard shipping across India. Delivery time varies by location (typically 3-7 business days). Track your order status in the My Orders section.",
            "shortAnswer": "3-7 days across India"
        },
        {
            "id": "return",
            "keywords": ["return", "refund", "cancel", "exchange", "money back"],
            "category": "orders",
            "question": "What is your return policy?",
            "answer": "Returns are accepted within 7 days of delivery for eligible items. Contact us at one@wecare.digital with your order number to initiate a return. Refunds are processed within 5-7 business days.",
            "shortAnswer": "7-day return policy"
        },
        {
            "id": "track",
            "keywords": ["track", "status", "where", "order status", "tracking"],
            "category": "orders",
            "question": "How do I track my order?",
            "answer": "Log in to your account at https://store.wecare.digital and visit the My Orders page to track your order status in real-time.",
            "shortAnswer": "Check My Orders page"
        },
        {
            "id": "whatsapp",
            "keywords": ["whatsapp", "message", "chat", "wa", "messenger"],
            "category": "general",
            "question": "Can I order via WhatsApp?",
            "answer": "Yes! Send us a message on WhatsApp at +91 9330994400. Our AI assistant will help you browse products and place orders directly through chat.",
            "shortAnswer": "Yes, WhatsApp +91 9330994400"
        },
        {
            "id": "invoice",
            "keywords": ["invoice", "bill", "receipt", "gst", "tax"],
            "category": "payments",
            "question": "How do I get my invoice?",
            "answer": "Your invoice is automatically generated after payment and sent to your registered email. You can also download it from the My Orders section or request it via email.",
            "shortAnswer": "Check email or My Orders page"
        },
        {
            "id": "account",
            "keywords": ["account", "login", "register", "signup", "password", "profile"],
            "category": "general",
            "question": "How do I create an account?",
            "answer": "Visit https://store.wecare.digital and click on the account icon to register. You can also place orders as a guest without creating an account.",
            "shortAnswer": "Click account icon on store.wecare.digital"
        },
        {
            "id": "convenience-fee",
            "keywords": ["convenience fee", "extra charge", "additional fee", "why charge"],
            "category": "payments",
            "question": "What is the convenience fee?",
            "answer": "A 2% convenience fee is charged on the cart total, plus 18% GST on that fee. This covers payment gateway and processing costs. Total fee = (Cart × 2%) × 1.18",
            "shortAnswer": "2% + 18% GST on payment processing"
        },
        {
            "id": "bulk-order",
            "keywords": ["bulk", "wholesale", "large order", "quantity", "discount"],
            "category": "orders",
            "question": "Do you offer bulk order discounts?",
            "answer": "Yes! For bulk orders, please contact us at one@wecare.digital or call +91 9330994400. We offer special pricing for large quantities.",
            "shortAnswer": "Contact us for bulk pricing"
        }
    ],
    "greetings": {
        "keywords": ["hi", "hello", "hey", "namaste", "good morning", "good evening"],
        "response": "Hi! 👋 Welcome to WECARE.DIGITAL. How can I help you today?"
    },
    "defaultResponse": "I don't have specific information about that. Please contact us at +91 9330994400 or one@wecare.digital for assistance."
}


def search_faqs(query: str, max_results: int = 3, short_answer: bool = False) -> List[Dict]:
    """
    Search FAQs using keyword matching.
    
    Args:
        query: User's question
        max_results: Maximum number of results
        short_answer: Return short answers instead of full answers
        
    Returns:
        List of matching FAQ entries with scores
    """
    query_lower = query.lower()
    matches = []
    
    # Check for greetings first
    greeting_keywords = FAQ_CONFIG.get('greetings', {}).get('keywords', [])
    if any(keyword in query_lower for keyword in greeting_keywords):
        return [{
            'id': 'greeting',
            'question': 'Greeting',
            'answer': FAQ_CONFIG['greetings']['response'],
            'score': 100,
            'category': 'general'
        }]
    
    # Score each FAQ based on keyword matches
    for faq in FAQ_CONFIG['faqs']:
        score = 0
        matched_keywords = []
        
        for keyword in faq['keywords']:
            if keyword.lower() in query_lower:
                score += 1
                matched_keywords.append(keyword)
        
        if score > 0:
            matches.append({
                'id': faq['id'],
                'question': faq['question'],
                'answer': faq['shortAnswer'] if short_answer else faq['answer'],
                'score': score,
                'category': faq['category'],
                'matchedKeywords': matched_keywords
            })
    
    # Sort by score (highest first)
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return matches[:max_results]


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    FAQ Handler - keyword-based search.
    
    Query params:
        - query: Search query
        - maxResults: Max results (default 3)
        - shortAnswer: Return short answers (default false)
        - category: Filter by category
    """
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    headers = cors_headers(origin)
    
    # Handle OPTIONS
    if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
        return options_response(origin)

    from lambda_utils.middleware import require_auth
    _auth = require_auth(event)
    if _auth is not None:
        return _auth
    
    # Get query parameters
    params = event.get('queryStringParameters') or {}
    query = params.get('query', '')
    max_results = int(params.get('maxResults', 3))
    short_answer = params.get('shortAnswer', 'false').lower() == 'true'
    category_filter = params.get('category', '')
    
    logger.info(json.dumps({
        'event': 'faq_search',
        'query': query[:100],
        'maxResults': max_results,
        'shortAnswer': short_answer,
        'category': category_filter,
        'requestId': request_id
    }))
    
    if not query:
        # Return all FAQs grouped by category
        faqs_by_category = {}
        for faq in FAQ_CONFIG['faqs']:
            cat = faq['category']
            if cat not in faqs_by_category:
                faqs_by_category[cat] = []
            faqs_by_category[cat].append({
                'id': faq['id'],
                'question': faq['question'],
                'answer': faq['shortAnswer'] if short_answer else faq['answer'],
                'category': cat
            })
        
        return cors_response(200, {
            'faqs': faqs_by_category,
            'brand': FAQ_CONFIG['brand'],
            'categories': {
                'general': 'General Information',
                'orders': 'Orders & Delivery',
                'payments': 'Payments & Billing'
            }
        }, origin)
    
    # Search FAQs
    results = search_faqs(query, max_results, short_answer)
    
    # Filter by category if specified
    if category_filter:
        results = [r for r in results if r['category'] == category_filter]
    
    # Build response
    if not results:
        response_text = FAQ_CONFIG['defaultResponse']
    elif len(results) == 1:
        response_text = results[0]['answer']
    else:
        response_text = '\n\n'.join([f"Q: {r['question']}\nA: {r['answer']}" for r in results])
    
    logger.info(json.dumps({
        'event': 'faq_search_complete',
        'resultsCount': len(results),
        'requestId': request_id
    }))
    
    return cors_response(200, {
        'query': query,
        'results': results,
        'responseText': response_text,
        'brand': FAQ_CONFIG['brand']
    }, origin)
