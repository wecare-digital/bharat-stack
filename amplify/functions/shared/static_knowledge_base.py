"""
Static Knowledge Base - Free Alternative to OpenSearch

This module provides a simple, cost-free FAQ/knowledge base using static content.
No OpenSearch, no vector embeddings, just simple keyword matching.
"""

BRAND_INFO = {
    'name': 'WECARE.DIGITAL',
    'website': 'https://wecare.digital',
    'store': 'https://store.wecare.digital',
    'email': 'one@wecare.digital',
    'phone': '+91 9330994400',
    'whatsapp': '+91 9330994400',
    'description': 'Multi-channel messaging and e-commerce platform',
    'services': [
        'WhatsApp Business API',
        'SMS & Voice Services',
        'E-commerce Solutions',
        'Payment Processing',
        'AI-powered Customer Support'
    ]
}

FAQ_DATABASE = [
    {
        'keywords': ['hours', 'timing', 'open', 'close', 'available', 'when'],
        'question': 'What are your business hours?',
        'answer': 'We are available 24/7 for online orders and support. For urgent assistance, call us at +91 9330994400 or email one@wecare.digital.'
    },
    {
        'keywords': ['contact', 'reach', 'call', 'email', 'phone', 'support'],
        'question': 'How can I contact you?',
        'answer': 'You can reach us via:\n- Phone/WhatsApp: +91 9330994400\n- Email: one@wecare.digital\n- Website: https://wecare.digital'
    },
    {
        'keywords': ['order', 'buy', 'purchase', 'shop', 'product'],
        'question': 'How do I place an order?',
        'answer': 'Visit our store at https://store.wecare.digital to browse products and place orders. You can also order via WhatsApp by sending us a message.'
    },
    {
        'keywords': ['payment', 'pay', 'price', 'cost', 'fee', 'charge'],
        'question': 'What payment methods do you accept?',
        'answer': 'We accept:\n- UPI (Google Pay, PhonePe, Paytm)\n- Credit/Debit Cards\n- Net Banking\n- Razorpay Payment Gateway\n\nA 2% convenience fee + 18% GST applies to all payments.'
    },
    {
        'keywords': ['delivery', 'shipping', 'ship', 'courier', 'dispatch'],
        'question': 'What are your delivery options?',
        'answer': 'We offer standard shipping across India. Delivery time varies by location. Track your order status in the My Orders section.'
    },
    {
        'keywords': ['return', 'refund', 'cancel', 'exchange'],
        'question': 'What is your return policy?',
        'answer': 'Returns are accepted within 7 days of delivery for eligible items. Contact us at one@wecare.digital with your order number to initiate a return.'
    },
    {
        'keywords': ['track', 'status', 'where', 'order status'],
        'question': 'How do I track my order?',
        'answer': 'Log in to your account at https://store.wecare.digital and visit the My Orders page to track your order status.'
    },
    {
        'keywords': ['whatsapp', 'message', 'chat', 'wa'],
        'question': 'Can I order via WhatsApp?',
        'answer': 'Yes! Send us a message on WhatsApp at +91 9330994400. Our AI assistant will help you browse products and place orders.'
    },
    {
        'keywords': ['invoice', 'bill', 'receipt', 'gst'],
        'question': 'How do I get my invoice?',
        'answer': 'Your invoice is automatically generated after payment and sent to your registered email. You can also download it from the My Orders section.'
    },
    {
        'keywords': ['account', 'login', 'register', 'signup', 'password'],
        'question': 'How do I create an account?',
        'answer': 'Visit https://store.wecare.digital and click on the account icon to register. You can also place orders as a guest without creating an account.'
    }
]

SERVICES_INFO = {
    'whatsapp': {
        'name': 'WhatsApp Business API',
        'description': 'Professional WhatsApp messaging for businesses',
        'features': ['Automated responses', 'Bulk messaging', 'Rich media support', 'Analytics']
    },
    'sms': {
        'name': 'SMS Services',
        'description': 'Reliable SMS delivery across India',
        'features': ['Transactional SMS', 'Promotional SMS', 'OTP delivery', 'DLT compliant']
    },
    'voice': {
        'name': 'Voice Services',
        'description': 'Automated voice calls and IVR',
        'features': ['Text-to-speech', 'Call recording', 'IVR menus', 'Call analytics']
    },
    'ecommerce': {
        'name': 'E-commerce Solutions',
        'description': 'Complete online store management',
        'features': ['Product catalog', 'Payment gateway', 'Order management', 'Inventory tracking']
    }
}


def search_knowledge_base(query: str, max_results: int = 3) -> str:
    """
    Search the static knowledge base using simple keyword matching.
    
    Args:
        query: User's question or search query
        max_results: Maximum number of results to return
        
    Returns:
        Formatted string with relevant answers
    """
    query_lower = query.lower()
    matches = []
    
    # Score each FAQ entry based on keyword matches
    for faq in FAQ_DATABASE:
        score = sum(1 for keyword in faq['keywords'] if keyword in query_lower)
        if score > 0:
            matches.append((score, faq))
    
    # Sort by score (highest first) and take top results
    matches.sort(key=lambda x: x[0], reverse=True)
    top_matches = matches[:max_results]
    
    if not top_matches:
        return "I don't have specific information about that. Please contact us at +91 9330994400 or one@wecare.digital for assistance."
    
    # Format results
    results = []
    for score, faq in top_matches:
        results.append(f"Q: {faq['question']}\nA: {faq['answer']}")
    
    return "\n\n".join(results)


def get_brand_info() -> dict:
    """Get brand information."""
    return BRAND_INFO


def get_service_info(service_name: str = None) -> dict:
    """Get information about services."""
    if service_name and service_name.lower() in SERVICES_INFO:
        return SERVICES_INFO[service_name.lower()]
    return SERVICES_INFO
