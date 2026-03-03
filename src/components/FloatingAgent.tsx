/**
 * Floating Agent - Internal Admin Chatbot
 * WECARE.DIGITAL Admin Platform
 * 
 * AI-powered assistant for internal task automation
 * Uses local FAQ search + Bedrock AI fallback via API
 * 
 * Model: Amazon Nova Lite (~$0.06/1M input tokens)
 * 
 * Note: External (WhatsApp auto-reply) uses separate AI pipeline
 */

import React, { useState, useRef, useEffect } from 'react';
import { searchFAQs, formatSearchResponse } from '../utils/faqSearch';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

const FloatingAgent: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! I\'m your Base CRM assistant. I can help you send messages, find contacts, check stats, and answer questions. Just type what you need!',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 100) + 'px';
    }
  }, [input]);

  // Keyboard shortcut: Ctrl+. to toggle
  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === '.') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
    };
    document.addEventListener('keydown', handleGlobalKey);
    return () => document.removeEventListener('keydown', handleGlobalKey);
  }, []);


  const processCommand = async (text: string): Promise<string> => {
    const lowerText = text.toLowerCase();
    
    try {
      // Send WhatsApp message - more flexible matching
      // Match: "send ... to PHONE" or "send ... PHONE" with optional message content
      if (lowerText.includes('send')) {
        // Match phone numbers - look for 10+ digit sequences
        const phoneMatch = text.match(/(\+?\d[\d\s-]{8,}\d)/);
        // Match message content after "saying", "as", "message", "content", "text", or ":"
        const contentMatch = text.match(/(?:saying|as|message|content|text|:)\s+["']?(.+?)["']?$/i);
        
        if (!phoneMatch) {
          return 'Please provide a phone number. Example: "Send to +919330994400 saying Hello!" or "Send hi to 447447840003"';
        }
        
        // Clean phone number - remove +, spaces, dashes
        const phone = phoneMatch[1].replace(/[\s\-\+]/g, '');
        const contactsRes = await fetch(`${API_BASE}/contacts?q=${encodeURIComponent(phone)}`);
        const contactsData = await contactsRes.json();
        const contacts = contactsData.contacts || [];
        
        if (contacts.length === 0) {
          return `No contact found with phone ${phone}. Use "find contact ${phone}" to search or add the contact first.`;
        }
        
        const contact = contacts[0];
        
        // Try to extract message content
        let messageContent = contentMatch?.[1]?.trim();
        
        // If no content match, try to find text before "to PHONE"
        if (!messageContent) {
          const beforePhoneMatch = text.match(/send\s+(?:a\s+)?(?:test\s+)?(?:message\s+)?["']?(.+?)["']?\s+to\s+\+?\d/i);
          if (beforePhoneMatch && beforePhoneMatch[1] && beforePhoneMatch[1].trim().length > 0) {
            messageContent = beforePhoneMatch[1].trim();
          }
        }
        
        if (!messageContent) {
          return `Found: ${contact.name || 'Unknown'} (${contact.phone})\n\nWhat message would you like to send? Try: "send hi to ${phone}"`;
        }
        
        const sendRes = await fetch(`${API_BASE}/whatsapp/send`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contactId: contact.contactId || contact.id,
            content: messageContent,
          }),
        });
        
        if (sendRes.ok) {
          const result = await sendRes.json();
          return `✓ Message sent!\n\nTo: ${contact.name || contact.phone}\nMessage: "${messageContent}"\nStatus: ${result.status || 'sent'}`;
        }
        const errorData = await sendRes.json().catch(() => ({}));
        return `Failed to send message: ${errorData.error || sendRes.statusText}`;
      }
      
      // Find contact
      if (lowerText.includes('find') || lowerText.includes('search') || lowerText.includes('contact')) {
        const phoneMatch = text.match(/(\+?\d[\d\s-]{8,})/);
        const nameMatch = text.match(/(?:named?|called?|for)\s+["']?(\w+)["']?/i);
        // Clean phone number - remove +, spaces, dashes to match stored format
        const query = phoneMatch?.[1]?.replace(/[\s\-\+]/g, '') || nameMatch?.[1] || '';
        
        if (!query) {
          return 'Please provide a phone number or name to search.';
        }
        
        const res = await fetch(`${API_BASE}/contacts?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        const contacts = data.contacts || [];
        
        if (contacts.length === 0) {
          return `No contacts found matching "${query}"`;
        }
        
        const results = contacts.slice(0, 5).map((c: any) => 
          `• ${c.name || 'Unknown'} - ${c.phone || 'No phone'}`
        ).join('\n');
        
        return `Found ${contacts.length} contact(s):\n\n${results}`;
      }
      
      // Stats
      if (lowerText.includes('stats') || lowerText.includes('dashboard') || lowerText.includes('today')) {
        const [contactsRes, messagesRes] = await Promise.all([
          fetch(`${API_BASE}/contacts`),
          fetch(`${API_BASE}/messages`),
        ]);
        
        const contactsData = await contactsRes.json();
        const messagesData = await messagesRes.json();
        
        const contacts = contactsData.contacts || [];
        const allMessages = messagesData.messages || [];
        
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const todayMessages = allMessages.filter((m: any) => new Date(m.timestamp) >= today);
        const inbound = todayMessages.filter((m: any) => m.direction === 'INBOUND').length;
        const outbound = todayMessages.filter((m: any) => m.direction === 'OUTBOUND').length;
        
        return `Today's Stats:\n\nMessages: ${todayMessages.length}\n  - Inbound: ${inbound}\n  - Outbound: ${outbound}\n\nTotal Contacts: ${contacts.length}`;
      }
      
      // Help
      if (lowerText.includes('help') || lowerText.includes('what can')) {
        return `I can help you with:\n\n• Send WhatsApp to +91... saying Hello\n• Find contact +91... or named John\n• Show today's stats\n• Check recent messages\n\nJust type naturally!`;
      }
      
      // AI fallback — try local FAQ first (instant, free), then API
      const faqResults = searchFAQs(text, { maxResults: 1 });
      if (faqResults.length > 0 && faqResults[0].score >= 2) {
        return faqResults[0].answer;
      }

      try {
        const aiRes = await fetch(`${API_BASE}/ai/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messageContent: text,
            context: 'internal',
          }),
        });
        
        if (aiRes.ok) {
          const aiData = await aiRes.json();
          // Handle Lambda proxy response format
          if (aiData.body) {
            try {
              const parsed = typeof aiData.body === 'string' ? JSON.parse(aiData.body) : aiData.body;
              if (parsed.suggestion || parsed.suggestedResponse) {
                return parsed.suggestion || parsed.suggestedResponse;
              }
            } catch (e) {
              // Continue to direct response check
            }
          }
          // Direct response format
          if (aiData.suggestion || aiData.suggestedResponse) {
            return aiData.suggestion || aiData.suggestedResponse;
          }
        }
      } catch (aiError) {
        console.error('AI fallback error:', aiError);
      }

      // Final fallback — return FAQ result even with low score, or default
      if (faqResults.length > 0) {
        return faqResults[0].answer;
      }
      
      return 'I can help you send messages, find contacts, or check stats. Try "help" for examples.';
      
    } catch (error: any) {
      console.error('Agent error:', error);
      return `Connection error: ${error.message || 'Please try again.'}`;
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const loadingId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: loadingId,
      role: 'assistant',
      content: '...',
      timestamp: new Date(),
      status: 'sending',
    }]);

    const response = await processCommand(userMessage.content);

    setMessages(prev => prev.map(m => 
      m.id === loadingId ? { ...m, content: response, status: 'sent' } : m
    ));
    setIsLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';

  if (!isOpen) {
    return (
      <button className="agent-fab" onClick={() => setIsOpen(true)} title="Open Assistant (Ctrl+.)" aria-label="Open assistant chat">
        <img src={LOGO_URL} alt="" className="agent-fab-logo" />
      </button>
    );
  }

  return (
    <div className="agent-panel">
      <div className="agent-header">
        <div className="agent-header-info">
          <img src={LOGO_URL} alt="Base CRM" className="agent-avatar-logo" />
          <div className="agent-header-text">
            <span className="agent-name">Base CRM</span>
            <span className="agent-subtitle">by WECARE.DIGITAL</span>
          </div>
        </div>
        <button className="agent-close" onClick={() => setIsOpen(false)} aria-label="Close assistant">×</button>
      </div>

      <div className="agent-messages" aria-live="polite" aria-relevant="additions">
        {messages.map((msg) => (
          <div key={msg.id} className={`agent-message ${msg.role}`}>
            <div className="agent-message-content">
              {msg.content.split('\n').map((line, i) => (
                <React.Fragment key={i}>
                  {line}
                  {i < msg.content.split('\n').length - 1 && <br />}
                </React.Fragment>
              ))}
            </div>
            <div className="agent-message-time">
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="agent-input-area">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message or command..."
          disabled={isLoading}
          rows={1}
          aria-label="Chat message input"
          style={{ paddingRight: 42 }}
        />
        <button 
          className="agent-send-btn" 
          onClick={handleSend} 
          disabled={!input.trim() || isLoading}
          aria-label="Send message"
        >
          {isLoading ? '·' : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>}
        </button>
      </div>
    </div>
  );
};

export default FloatingAgent;
