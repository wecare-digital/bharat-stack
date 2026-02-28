/**
 * FAQ Search Utility - Frontend
 * 
 * Keyword-based FAQ search that works offline
 * No API calls needed for basic search
 */

export interface FAQ {
  id: string;
  keywords: string[];
  category: string;
  question: string;
  answer: string;
  shortAnswer: string;
}

export interface FAQSearchResult {
  id: string;
  question: string;
  answer: string;
  score: number;
  category: string;
  matchedKeywords: string[];
}

export interface BrandInfo {
  name: string;
  website: string;
  store: string;
  email: string;
  phone: string;
  whatsapp: string;
}

// FAQ Database - synced with backend
const FAQ_DATABASE: FAQ[] = [
  {
    id: 'hours',
    keywords: ['hours', 'timing', 'open', 'close', 'available', 'when', 'time'],
    category: 'general',
    question: 'What are your business hours?',
    answer: 'We are available 24/7 for online orders and support. For urgent assistance, call us at +91 9330994400 or email one@wecare.digital.',
    shortAnswer: '24/7 available'
  },
  {
    id: 'contact',
    keywords: ['contact', 'reach', 'call', 'email', 'phone', 'support', 'help'],
    category: 'general',
    question: 'How can I contact you?',
    answer: 'You can reach us via:\n• Phone/WhatsApp: +91 9330994400\n• Email: one@wecare.digital\n• Website: https://wecare.digital',
    shortAnswer: 'Call +91 9330994400 or email one@wecare.digital'
  },
  {
    id: 'order',
    keywords: ['order', 'buy', 'purchase', 'shop', 'product', 'cart'],
    category: 'orders',
    question: 'How do I place an order?',
    answer: 'Visit our store at https://store.wecare.digital to browse products and place orders. You can also order via WhatsApp by sending us a message at +91 9330994400.',
    shortAnswer: 'Visit store.wecare.digital or WhatsApp us'
  },
  {
    id: 'payment',
    keywords: ['payment', 'pay', 'price', 'cost', 'fee', 'charge', 'upi', 'card'],
    category: 'payments',
    question: 'What payment methods do you accept?',
    answer: 'We accept:\n• UPI (Google Pay, PhonePe, Paytm)\n• Credit/Debit Cards\n• Net Banking\n• Razorpay Payment Gateway\n\nA 2% convenience fee + 18% GST applies to all payments.',
    shortAnswer: 'UPI, Cards, Net Banking (2% + GST fee applies)'
  },
  {
    id: 'delivery',
    keywords: ['delivery', 'shipping', 'ship', 'courier', 'dispatch', 'send'],
    category: 'orders',
    question: 'What are your delivery options?',
    answer: 'We offer standard shipping across India. Delivery time varies by location (typically 3-7 business days). Track your order status in the My Orders section.',
    shortAnswer: '3-7 days across India'
  },
  {
    id: 'return',
    keywords: ['return', 'refund', 'cancel', 'exchange', 'money back'],
    category: 'orders',
    question: 'What is your return policy?',
    answer: 'Returns are accepted within 7 days of delivery for eligible items. Contact us at one@wecare.digital with your order number to initiate a return. Refunds are processed within 5-7 business days.',
    shortAnswer: '7-day return policy'
  },
  {
    id: 'track',
    keywords: ['track', 'status', 'where', 'order status', 'tracking'],
    category: 'orders',
    question: 'How do I track my order?',
    answer: 'Log in to your account at https://store.wecare.digital and visit the My Orders page to track your order status in real-time.',
    shortAnswer: 'Check My Orders page'
  },
  {
    id: 'whatsapp',
    keywords: ['whatsapp', 'message', 'chat', 'wa', 'messenger'],
    category: 'general',
    question: 'Can I order via WhatsApp?',
    answer: 'Yes! Send us a message on WhatsApp at +91 9330994400. Our AI assistant will help you browse products and place orders directly through chat.',
    shortAnswer: 'Yes, WhatsApp +91 9330994400'
  },
  {
    id: 'invoice',
    keywords: ['invoice', 'bill', 'receipt', 'gst', 'tax'],
    category: 'payments',
    question: 'How do I get my invoice?',
    answer: 'Your invoice is automatically generated after payment and sent to your registered email. You can also download it from the My Orders section or request it via email.',
    shortAnswer: 'Check email or My Orders page'
  },
  {
    id: 'account',
    keywords: ['account', 'login', 'register', 'signup', 'password', 'profile'],
    category: 'general',
    question: 'How do I create an account?',
    answer: 'Visit https://store.wecare.digital and click on the account icon to register. You can also place orders as a guest without creating an account.',
    shortAnswer: 'Click account icon on store.wecare.digital'
  },
  {
    id: 'convenience-fee',
    keywords: ['convenience fee', 'extra charge', 'additional fee', 'why charge'],
    category: 'payments',
    question: 'What is the convenience fee?',
    answer: 'A 2% convenience fee is charged on the cart total, plus 18% GST on that fee. This covers payment gateway and processing costs. Total fee = (Cart × 2%) × 1.18',
    shortAnswer: '2% + 18% GST on payment processing'
  },
  {
    id: 'bulk-order',
    keywords: ['bulk', 'wholesale', 'large order', 'quantity', 'discount'],
    category: 'orders',
    question: 'Do you offer bulk order discounts?',
    answer: 'Yes! For bulk orders, please contact us at one@wecare.digital or call +91 9330994400. We offer special pricing for large quantities.',
    shortAnswer: 'Contact us for bulk pricing'
  }
];

const BRAND_INFO: BrandInfo = {
  name: 'WECARE.DIGITAL',
  website: 'https://wecare.digital',
  store: 'https://store.wecare.digital',
  email: 'one@wecare.digital',
  phone: '+91 9330994400',
  whatsapp: '+91 9330994400'
};

const GREETINGS = ['hi', 'hello', 'hey', 'namaste', 'good morning', 'good evening'];
const DEFAULT_RESPONSE = "I don't have specific information about that. Please contact us at +91 9330994400 or one@wecare.digital for assistance.";

/**
 * Search FAQs using keyword matching
 */
export function searchFAQs(
  query: string,
  options: {
    maxResults?: number;
    shortAnswer?: boolean;
    category?: string;
  } = {}
): FAQSearchResult[] {
  const { maxResults = 3, shortAnswer = false, category } = options;
  const queryLower = query.toLowerCase().trim();
  
  if (!queryLower) return [];
  
  // Check for greetings
  if (GREETINGS.some(g => queryLower.includes(g))) {
    return [{
      id: 'greeting',
      question: 'Greeting',
      answer: 'Hi! 👋 Welcome to WECARE.DIGITAL. How can I help you today?',
      score: 100,
      category: 'general',
      matchedKeywords: ['greeting']
    }];
  }
  
  // Score each FAQ
  const matches: FAQSearchResult[] = [];
  
  for (const faq of FAQ_DATABASE) {
    // Skip if category filter doesn't match
    if (category && faq.category !== category) continue;
    
    let score = 0;
    const matchedKeywords: string[] = [];
    
    for (const keyword of faq.keywords) {
      if (queryLower.includes(keyword.toLowerCase())) {
        score++;
        matchedKeywords.push(keyword);
      }
    }
    
    if (score > 0) {
      matches.push({
        id: faq.id,
        question: faq.question,
        answer: shortAnswer ? faq.shortAnswer : faq.answer,
        score,
        category: faq.category,
        matchedKeywords
      });
    }
  }
  
  // Sort by score (highest first) and limit results
  return matches
    .sort((a, b) => b.score - a.score)
    .slice(0, maxResults);
}

/**
 * Get all FAQs grouped by category
 */
export function getAllFAQs(shortAnswer: boolean = false): Record<string, FAQ[]> {
  const grouped: Record<string, FAQ[]> = {
    general: [],
    orders: [],
    payments: []
  };
  
  for (const faq of FAQ_DATABASE) {
    if (!grouped[faq.category]) {
      grouped[faq.category] = [];
    }
    grouped[faq.category].push(faq);
  }
  
  return grouped;
}

/**
 * Get FAQ by ID
 */
export function getFAQById(id: string): FAQ | undefined {
  return FAQ_DATABASE.find(faq => faq.id === id);
}

/**
 * Get brand information
 */
export function getBrandInfo(): BrandInfo {
  return BRAND_INFO;
}

/**
 * Get formatted response text from search results
 */
export function formatSearchResponse(results: FAQSearchResult[]): string {
  if (results.length === 0) {
    return DEFAULT_RESPONSE;
  }
  
  if (results.length === 1) {
    return results[0].answer;
  }
  
  return results
    .map(r => `Q: ${r.question}\nA: ${r.answer}`)
    .join('\n\n');
}

/**
 * Get category display name
 */
export function getCategoryName(category: string): string {
  const names: Record<string, string> = {
    general: 'General Information',
    orders: 'Orders & Delivery',
    payments: 'Payments & Billing'
  };
  return names[category] || category;
}
