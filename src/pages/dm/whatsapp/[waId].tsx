/**
 * WhatsApp Conversation View
 * Full messaging interface for specific WABA
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import RichTextEditor from '../../../components/RichTextEditor';
import InteractiveMessageComposer from '../../../components/InteractiveMessageComposer';
import TemplateSender from '../../../components/TemplateSender';
import Button from '../../../components/ui/Button';
import { SkeletonContact, SkeletonMessage } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { useChatShortcuts } from '../../../hooks/useKeyboardShortcuts';
import { useNotificationSound } from '../../../hooks/useNotificationSound';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface Message {
  id: string;
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  status: string;
  contactId: string;
  whatsappMessageId?: string;
  mediaUrl?: string;
  s3Key?: string;
  messageType?: string;
  receivingPhone?: string;
  awsPhoneNumberId?: string;
  transcription?: string;       // English transcription of voice notes
  detectedLanguage?: string;    // Detected language of voice note
}

interface Contact {
  id: string;
  name: string;
  phone: string;
  bsuid?: string;
  username?: string;
  contactBookName?: string;
  hasName: boolean;  // Track if contact has a real name vs using phone as display
  windowOpen: boolean;
  windowExpiresAt: number;  // Timestamp when window expires
  unread: number;
  lastMessage?: string;
}

const WABA_INFO: Record<string, { name: string; phone: string }> = {
  [WHATSAPP_PHONES.primary.id]: { name: WHATSAPP_PHONES.primary.name, phone: WHATSAPP_PHONES.primary.display },
  [WHATSAPP_PHONES.secondary.id]: { name: WHATSAPP_PHONES.secondary.name, phone: WHATSAPP_PHONES.secondary.display },
};

// ── Language code to human-readable label ──
const LANG_LABELS: Record<string, string> = {
  'en-US': 'English', 'en-GB': 'English', 'en-IN': 'English',
  'en-AU': 'English', 'en-NZ': 'English', 'en-ZA': 'English',
  'hi-IN': 'Hindi', 'ar-SA': 'Arabic', 'es-US': 'Spanish',
  'es-ES': 'Spanish', 'es-MX': 'Spanish', 'fr-FR': 'French',
  'fr-CA': 'French', 'de-DE': 'German', 'ja-JP': 'Japanese',
  'ko-KR': 'Korean', 'pt-BR': 'Portuguese', 'pt-PT': 'Portuguese',
  'zh-CN': 'Chinese', 'it-IT': 'Italian', 'tr-TR': 'Turkish',
  'ru-RU': 'Russian', 'nl-NL': 'Dutch', 'pl-PL': 'Polish',
  'sv-SE': 'Swedish', 'da-DK': 'Danish', 'nb-NO': 'Norwegian',
  'fi-FI': 'Finnish', 'ca-ES': 'Catalan', 'ro-RO': 'Romanian',
  'id-ID': 'Indonesian', 'ms-MY': 'Malay', 'th-TH': 'Thai',
  'vi-VN': 'Vietnamese', 'ta-IN': 'Tamil', 'te-IN': 'Telugu',
  'bn-IN': 'Bengali', 'mr-IN': 'Marathi', 'gu-IN': 'Gujarati',
  'kn-IN': 'Kannada', 'ml-IN': 'Malayalam', 'ur-IN': 'Urdu',
  'pa-IN': 'Punjabi', 'arb': 'Arabic', 'cy-GB': 'Welsh',
};

// ── Voice Note Transcription sub-component ──
const VoiceTranscript: React.FC<{ msg: Message }> = ({ msg }) => {
  const [expanded, setExpanded] = useState(false);
  const [transcription, setTranscription] = useState(msg.transcription || '');
  const [detectedLang, setDetectedLang] = useState(msg.detectedLanguage || '');
  const [loading, setLoading] = useState(false);

  const handleTranscribe = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const result = await api.transcribeVoiceNote({
        messageId: msg.id,
        s3Key: msg.s3Key || undefined,
        direction: msg.direction === 'inbound' ? 'INBOUND' : 'OUTBOUND',
      });
      if (result?.transcription) {
        setTranscription(result.transcription);
        setDetectedLang(result.detectedLanguage || '');
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  if (transcription) {
    const langLabel = LANG_LABELS[detectedLang] || detectedLang || '';
    return (
      <div className="voice-transcription" style={{ marginTop: 4, width: '100%' }}>
        <button
          className="transcription-toggle"
          onClick={() => setExpanded(!expanded)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: '0.75rem', color: '#6b7280', display: 'flex',
            alignItems: 'center', gap: 4, padding: '2px 0',
          }}
        >
          <span style={{ fontSize: '0.7rem' }}>📝</span>
          {expanded ? 'Hide transcript' : 'Show transcript'}
          {langLabel && <span style={{
            fontSize: '0.65rem', background: '#e5e7eb', borderRadius: 4,
            padding: '1px 4px', marginLeft: 4,
          }}>{langLabel}</span>}
        </button>
        {expanded && (
          <p style={{
            margin: '4px 0 0', fontSize: '0.8rem', color: '#374151',
            lineHeight: 1.4, fontStyle: 'italic', padding: '4px 8px',
            background: 'rgba(0,0,0,0.03)', borderRadius: 6,
            borderLeft: '2px solid #9ca3af',
          }}>
            {transcription}
          </p>
        )}
      </div>
    );
  }

  // No transcription yet — show "Transcribe" button
  return (
    <div className="voice-transcription" style={{ marginTop: 4 }}>
      <button
        onClick={handleTranscribe}
        disabled={loading}
        style={{
          background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
          cursor: loading ? 'wait' : 'pointer', fontSize: '0.72rem',
          color: '#6b7280', padding: '2px 8px', display: 'flex',
          alignItems: 'center', gap: 4,
        }}
      >
        <span style={{ fontSize: '0.7rem' }}>{loading ? '⏳' : '📝'}</span>
        {loading ? 'Transcribing...' : 'Transcribe'}
      </button>
    </div>
  );
};

const WhatsAppConversation: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const { waId } = router.query;
  const wabaInfo = waId ? WABA_INFO[waId as string] : null;

  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const toast = useToastContext();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Voice note recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Interactive message composer state
  const [showInteractiveComposer, setShowInteractiveComposer] = useState(false);

  // Template sender state
  const [showTemplateSender, setShowTemplateSender] = useState(false);

  // Window countdown state
  const [windowCountdown, setWindowCountdown] = useState<string>('');

  // Message search state
  const [messageSearchQuery, setMessageSearchQuery] = useState('');
  const [showMessageSearch, setShowMessageSearch] = useState(false);
  
  // Contact search state
  const [contactSearchQuery, setContactSearchQuery] = useState('');
  
  // Starred messages
  const [starredMessages, setStarredMessages] = useState<string[]>([]);
  
  // Notification sounds
  const { playMessageSound } = useNotificationSound();
  const prevMessageCount = useRef(0);

  // Chat keyboard shortcuts
  useChatShortcuts({
    onSend: () => handleSend(),
    onSearch: () => setShowMessageSearch(true),
    onTemplate: () => setShowTemplateSender(true),
    onInteractive: () => setShowInteractiveComposer(true),
    onEscape: () => {
      setShowMessageSearch(false);
      setShowTemplateSender(false);
      setShowInteractiveComposer(false);
    },
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load starred messages from localStorage
  useEffect(() => {
    setStarredMessages(api.getStarredMessages());
  }, []);

  // Play sound on new inbound message
  useEffect(() => {
    const inboundCount = messages.filter(m => m.direction === 'inbound').length;
    if (prevMessageCount.current > 0 && inboundCount > prevMessageCount.current) {
      playMessageSound();
    }
    prevMessageCount.current = inboundCount;
  }, [messages, playMessageSound]);

  const loadData = useCallback(async () => {
    if (!waId) return;
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([
        api.listContacts(),
        api.listMessages(undefined, 'WHATSAPP'),
      ]);

      // Filter messages STRICTLY for this WABA only
      const wabaMessages = messagesData.filter(m => m.awsPhoneNumberId === waId);

      // Get contact IDs that have messages in this WABA
      const contactIdsWithMessages = new Set(wabaMessages.map(m => m.contactId));

      // Only show contacts that have messages in this specific WABA
      // Include BSUID-only contacts (no phone) that have messages
      const displayContacts: Contact[] = contactsData
        .filter(c => (c.phone || c.bsuid) && contactIdsWithMessages.has(c.contactId))
        .map(c => {
          const contactMsgs = wabaMessages.filter(m => m.contactId === c.contactId);
          const lastMsg = contactMsgs[0];
          const lastInbound = c.lastInboundMessageAt ? new Date(c.lastInboundMessageAt).getTime() : 0;
          const windowEnd = lastInbound + 24 * 60 * 60 * 1000;
          // Keep name and phone separate - use phone as display name only if name is empty
          const displayName = c.name && c.name.trim() && c.name !== '~' ? c.name : '';
          return {
            id: c.contactId,
            name: displayName || c.phone || c.username || c.bsuid || 'Unknown',
            phone: c.phone,
            bsuid: c.bsuid || '',
            username: c.username || '',
            contactBookName: c.contactBookName || '',
            hasName: !!displayName,  // Track if contact has a real name
            windowOpen: Date.now() < windowEnd,
            windowExpiresAt: windowEnd,
            unread: contactMsgs.filter(m => m.direction === 'INBOUND' && m.status === 'received').length,
            lastMessage: lastMsg?.content?.substring(0, 40) || '',
          };
        });

      setContacts(displayContacts);
      setMessages(wabaMessages.map(m => ({
        id: m.messageId,
        direction: m.direction.toLowerCase() as 'inbound' | 'outbound',
        content: m.content || '',
        timestamp: m.timestamp,
        status: m.status?.toLowerCase() || 'sent',
        contactId: m.contactId,
        whatsappMessageId: m.whatsappMessageId,
        // Use pre-signed URL from API, fallback to direct S3 URL
        mediaUrl: m.mediaUrl || (m.s3Key ? `https://app.wecare.digital.s3.amazonaws.com/${m.s3Key}` : undefined),
        s3Key: m.s3Key,
        messageType: m.messageType || (m.s3Key ? 'media' : 'text'),
        transcription: m.transcription,
        detectedLanguage: m.detectedLanguage,
      })));
    } catch (err) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [waId]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Window countdown timer
  useEffect(() => {
    if (!selectedContact?.windowOpen || !selectedContact?.windowExpiresAt) {
      setWindowCountdown('');
      return;
    }

    const updateCountdown = () => {
      const now = Date.now();
      const remaining = selectedContact.windowExpiresAt - now;
      
      if (remaining <= 0) {
        setWindowCountdown('Expired');
        return;
      }

      const hours = Math.floor(remaining / (1000 * 60 * 60));
      const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
      
      if (hours > 0) {
        setWindowCountdown(`${hours}h ${minutes}m`);
      } else {
        setWindowCountdown(`${minutes}m`);
      }
    };

    updateCountdown();
    const timer = setInterval(updateCountdown, 60000); // Update every minute
    return () => clearInterval(timer);
  }, [selectedContact?.windowOpen, selectedContact?.windowExpiresAt]);

  const filteredMessages = messages.filter(m => {
    // Filter by selected contact
    if (!selectedContact || m.contactId !== selectedContact.id) return false;
    // Filter by search query
    if (messageSearchQuery.trim()) {
      return m.content?.toLowerCase().includes(messageSearchQuery.toLowerCase());
    }
    return true;
  });

  // Filter contacts by search (includes BSUID, username, contactBookName)
  const filteredContacts = contacts.filter(c => {
    if (!contactSearchQuery.trim()) return true;
    const q = contactSearchQuery.toLowerCase();
    return c.name.toLowerCase().includes(q) ||
      c.phone.includes(contactSearchQuery) ||
      (c.bsuid && c.bsuid.toLowerCase().includes(q)) ||
      (c.username && c.username.toLowerCase().includes(q)) ||
      (c.contactBookName && c.contactBookName.toLowerCase().includes(q));
  });

  // Toggle star on message
  const toggleStar = (messageId: string) => {
    const isNowStarred = api.toggleStarMessage(messageId);
    setStarredMessages(api.getStarredMessages());
  };

  // Export chat as text
  const exportChat = () => {
    if (!selectedContact) return;
    const chatMessages = messages.filter(m => m.contactId === selectedContact.id);
    const text = api.exportChatToText(
      chatMessages.map(m => ({
        ...m,
        direction: m.direction.toUpperCase() as 'INBOUND' | 'OUTBOUND',
        channel: 'WHATSAPP' as const,
        messageId: m.id,
      })),
      selectedContact.name
    );
    api.downloadFile(text, `chat_${selectedContact.name}_${new Date().toISOString().split('T')[0]}.txt`, 'text/plain');
  };

  // Export chat as PDF
  const exportChatPDF = () => {
    if (!selectedContact) return;
    const chatMessages = messages.filter(m => m.contactId === selectedContact.id);
    api.exportChatToPDF(
      chatMessages.map(m => ({
        ...m,
        direction: m.direction.toUpperCase() as 'INBOUND' | 'OUTBOUND',
        channel: 'WHATSAPP' as const,
        messageId: m.id,
      })),
      selectedContact.name,
      wabaInfo?.name
    );
  };

  const handleSend = async () => {
    if (!selectedContact || !messageText.trim() || sending) return;
    setSending(true);

    try {
      const result = await api.sendWhatsAppMessage({
        contactId: selectedContact.id,
        content: messageText,
        phoneNumberId: waId as string,
        recipientBsuid: selectedContact.bsuid || undefined,
      });

      if (result) {
        toast.success('Message sent');
        setMessageText('');
        await loadData();
      } else {
        toast.error('Failed to send message');
      }
    } catch (err) {
      toast.error('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleReaction = async (whatsappMessageId: string) => {
    if (!selectedContact || !whatsappMessageId) return;
    try {
      await api.sendWhatsAppReaction({
        contactId: selectedContact.id,
        reactionMessageId: whatsappMessageId,
        reactionEmoji: '👍',
        phoneNumberId: waId as string,
        recipientBsuid: selectedContact.bsuid || undefined,
      });
    } catch (err) {
      console.error('Reaction failed:', err);
    }
  };

  // Voice note recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/ogg' });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start(100);
      setIsRecording(true);
      setRecordingTime(0);
      
      // Start timer
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Failed to start recording:', err);
      toast.error('Microphone access denied');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }
    }
  };

  const cancelRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingTime(0);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const sendVoiceNote = async () => {
    if (!selectedContact || !audioBlob || sending) return;
    setSending(true);

    try {
      // Convert blob to base64
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = async () => {
        const base64data = reader.result as string;
        // Remove data URL prefix (data:audio/ogg;base64,)
        const base64Audio = base64data.split(',')[1];

        const result = await api.sendWhatsAppMessage({
          contactId: selectedContact.id,
          content: '',
          phoneNumberId: waId as string,
          mediaFile: base64Audio,
          mediaType: 'audio/ogg',
          mediaFileName: `voice-note-${Date.now()}.ogg`,
          recipientBsuid: selectedContact.bsuid || undefined,
        });

        if (result) {
          toast.success('Voice note sent');
          setAudioBlob(null);
          setAudioUrl(null);
          setRecordingTime(0);
          await loadData();
        } else {
          toast.error('Failed to send voice note');
        }
        setSending(false);
      };
    } catch (err) {
      console.error('Voice note send error:', err);
      toast.error('Failed to send voice note');
      setSending(false);
    }
  };

  const formatRecordingTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Render message content based on type
  const renderMessageContent = (msg: Message) => {
    const { messageType, content, mediaUrl, s3Key } = msg;
    
    // Reaction messages
    if (messageType === 'reaction') {
      return (
        <div className="reaction-message">
          <span className="reaction-emoji">{content || '👍'}</span>
          <span className="reaction-label">Reacted to a message</span>
        </div>
      );
    }
    
    // Image messages (check media BEFORE text to handle mistyped records)
    if (messageType === 'image' || (mediaUrl && s3Key?.match(/\.(jpg|jpeg|png)$/i))) {
      return (
        <div className="media-message">
          <div className="media-container">
            <img src={mediaUrl} alt="Image" className="message-media image" loading="lazy" />
            {renderDownloadButton(mediaUrl)}
          </div>
          {content && content !== '[Image]' && <div className="media-caption">{content}</div>}
        </div>
      );
    }
    
    // Sticker messages
    if (messageType === 'sticker' || s3Key?.match(/\.webp$/i)) {
      return (
        <div className="sticker-message">
          <img src={mediaUrl} alt="Sticker" className="message-sticker" loading="lazy" />
        </div>
      );
    }
    
    // Video messages
    if (messageType === 'video' || s3Key?.match(/\.(mp4|3gp|3gpp)$/i)) {
      return (
        <div className="media-message">
          <div className="media-container">
            <video src={mediaUrl} controls className="message-media video" preload="metadata" />
            {renderDownloadButton(mediaUrl)}
          </div>
          {content && content !== '[Video]' && <div className="media-caption">{content}</div>}
        </div>
      );
    }
    
    // Audio/Voice note messages
    if (messageType === 'audio' || s3Key?.match(/\.(aac|amr|mp3|m4a|ogg|opus)$/i)) {
      const isVoiceNote = s3Key?.match(/\.(ogg|opus)$/i) || content === '[Audio]';
      return (
        <div className={`audio-message ${isVoiceNote ? 'voice-note' : ''}`}>
          <div className="audio-icon">{isVoiceNote ? 'Voice' : 'Audio'}</div>
          <audio src={mediaUrl} controls className="message-audio" preload="metadata" />
          {renderDownloadButton(mediaUrl)}
          <VoiceTranscript msg={msg} />
        </div>
      );
    }
    
    // Document messages
    if (messageType === 'document' || s3Key?.match(/\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt)$/i)) {
      const fileName = s3Key?.split('/').pop() || content || 'Document';
      const docIcon = getDocumentIcon(s3Key || '');
      return (
        <div className="document-message">
          <a href={mediaUrl} target="_blank" rel="noopener noreferrer" className="document-link">
            <span className="doc-icon">{docIcon}</span>
            <div className="doc-info">
              <span className="doc-name">{fileName}</span>
              <span className="doc-type">{getDocumentType(s3Key || '')}</span>
            </div>
            <span className="doc-download">DL</span>
          </a>
        </div>
      );
    }
    
    // Location messages
    if (messageType === 'location' || content?.startsWith('[Location:')) {
      const match = content?.match(/\[Location: ([\d.-]+), ([\d.-]+)\]/);
      if (match) {
        const [, lat, lng] = match;
        return (
          <div className="location-message">
            <a 
              href={`https://maps.google.com/?q=${lat},${lng}`}
              target="_blank"
              rel="noopener noreferrer"
              className="location-link"
            >
              <div className="location-preview">
                <img 
                  src={`https://maps.googleapis.com/maps/api/staticmap?center=${lat},${lng}&zoom=15&size=200x120&markers=${lat},${lng}&key=`}
                  alt="Location"
                  className="location-map"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
                <div className="location-overlay">
                  <span className="location-icon">Loc</span>
                  <span>View on Maps</span>
                </div>
              </div>
              <div className="location-coords">{lat}, {lng}</div>
            </a>
          </div>
        );
      }
    }
    
    // Contact card messages
    if (messageType === 'contacts' || content === '[Contact Card]') {
      return (
        <div className="contact-card-message">
          <div className="contact-card-icon">C</div>
          <div className="contact-card-info">
            <span className="contact-card-label">Contact Card</span>
            <span className="contact-card-hint">Tap to view contact details</span>
          </div>
        </div>
      );
    }
    
    // Interactive messages (button_reply, list_reply, nfm_reply)
    if (messageType === 'interactive' || content?.startsWith('[Interactive:') || 
        content?.startsWith('[Button Reply]') || content?.startsWith('[List Reply]') || 
        content?.startsWith('[Flow Response:')) {
      const interactiveType = content?.match(/\[Interactive: (\w+)\]/)?.[1] || 
                              content?.match(/\[(Button Reply|List Reply|Flow Response)/)?.[1] || 'reply';
      return (
        <div className="interactive-message">
          <div className="interactive-icon">
            {interactiveType.includes('Button') ? 'Btn' : 
             interactiveType.includes('List') ? 'List' : 
             interactiveType.includes('Flow') ? 'Flow' : 'Msg'}
          </div>
          <div className="interactive-content">
            <span className="interactive-label">{interactiveType}</span>
            <span className="interactive-value">{content?.replace(/\[.*?\]\s*/, '') || 'User selection'}</span>
          </div>
        </div>
      );
    }
    
    // Order messages
    if (messageType === 'order' || content === '[Order]') {
      return (
        <div className="order-message">
          <div className="order-icon">Order</div>
          <div className="order-info">
            <span className="order-label">Order Received</span>
            <span className="order-hint">View order details in dashboard</span>
          </div>
        </div>
      );
    }
    
    // Payment messages
    if (messageType === 'payment') {
      return (
        <div className="payment-message">
          <div className="payment-icon">Pay</div>
          <div className="payment-info">
            <span className="payment-label">Payment</span>
            <span className="payment-content">{content}</span>
          </div>
        </div>
      );
    }
    
    // Template messages (authentication OTP, marketing, utility)
    if (messageType === 'template') {
      // Check if it's an OTP/authentication template (contains code pattern)
      const otpMatch = content?.match(/\b(\d{4,8})\b/);
      const isOtpTemplate = otpMatch && (
        content?.toLowerCase().includes('code') || 
        content?.toLowerCase().includes('otp') || 
        content?.toLowerCase().includes('verification') ||
        content?.toLowerCase().includes('password')
      );
      
      // Check for utility template patterns (order, shipping, delivery, payment, booking)
      const isUtilityTemplate = content?.toLowerCase().match(
        /order|shipping|delivery|payment|booking|appointment|confirmation|update|status|tracking|receipt|invoice/
      );
      
      // Check for marketing template patterns (offer, discount, sale, promo)
      const isMarketingTemplate = content?.toLowerCase().match(
        /offer|discount|sale|promo|deal|limited|exclusive|special|free|win|congratulations|welcome/
      );
      
      // OTP/Authentication template
      if (isOtpTemplate && otpMatch) {
        return (
          <div className="template-message otp-template">
            <div className="template-header">
              <span className="template-icon">Auth</span>
              <span className="template-label">Authentication</span>
            </div>
            <div className="template-body">
              <div className="otp-code">{otpMatch[1]}</div>
              <div className="otp-text">{content?.replace(otpMatch[1], '').trim() || 'Your verification code'}</div>
            </div>
            <div className="template-button copy-code-btn" onClick={() => {
              navigator.clipboard.writeText(otpMatch[1]);
            }}>
              <span className="btn-icon">Copy</span>
              <span>Copy Code</span>
            </div>
          </div>
        );
      }
      
      // Utility template (transactional)
      if (isUtilityTemplate) {
        // Determine utility sub-type for better icon and styling
        const isOrderRelated = content?.toLowerCase().match(/order|package|shipped|tracking|delivery|refund|cancel/);
        const isAccountAlert = content?.toLowerCase().match(/account|balance|payment|reminder|subscription|profile|alert|security/);
        const isFeedback = content?.toLowerCase().match(/feedback|survey|review|rating|experience/);
        const isOptIn = content?.toLowerCase().match(/opt-in|opt-out|subscribe|unsubscribe|confirm/);
        const isAppointment = content?.toLowerCase().match(/appointment|booking|reservation|schedule|visit/);
        
        // Select icon based on sub-type
        const utilityIcon = isOrderRelated ? (
          content?.toLowerCase().includes('shipped') || content?.toLowerCase().includes('delivery') ? 'Ship' :
          content?.toLowerCase().includes('tracking') ? 'Track' :
          content?.toLowerCase().includes('refund') ? 'Refund' :
          content?.toLowerCase().includes('cancel') ? 'Cancel' : 'Order'
        ) : isAccountAlert ? (
          content?.toLowerCase().includes('balance') ? 'Bal' :
          content?.toLowerCase().includes('payment') || content?.toLowerCase().includes('reminder') ? 'Alert' :
          content?.toLowerCase().includes('security') || content?.toLowerCase().includes('alert') ? 'Alert' : 'Acct'
        ) : isFeedback ? 'Review' :
        isOptIn ? 'Sub' :
        isAppointment ? 'Appt' : 'Update';
        
        // Determine sub-label
        const utilitySubLabel = isOrderRelated ? 'Order Update' :
          isAccountAlert ? 'Account Alert' :
          isFeedback ? 'Feedback Request' :
          isOptIn ? 'Subscription' :
          isAppointment ? 'Appointment' : 'Update';
        
        // Check for tracking numbers or order IDs
        const trackingMatch = content?.match(/tracking[:\s#]*([A-Z0-9]{8,20})/i);
        const orderMatch = content?.match(/order[:\s#]*([A-Z0-9-]{4,20})/i);
        
        return (
          <div className="template-message utility-template">
            <div className="template-header">
              <span className="template-icon">{utilityIcon}</span>
              <span className="template-label">Utility</span>
              <span className="template-sublabel">{utilitySubLabel}</span>
            </div>
            <div className="template-body">
              <div className="template-text">{content}</div>
              {(trackingMatch || orderMatch) && (
                <div className="utility-reference">
                  {orderMatch && (
                    <div className="reference-item">
                      <span className="ref-label">Order:</span>
                      <span className="ref-value">{orderMatch[1]}</span>
                    </div>
                  )}
                  {trackingMatch && (
                    <div className="reference-item">
                      <span className="ref-label">Tracking:</span>
                      <span className="ref-value">{trackingMatch[1]}</span>
                      <span className="ref-copy" onClick={() => navigator.clipboard.writeText(trackingMatch[1])}>Copy</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      }
      
      // Marketing template (promotional)
      if (isMarketingTemplate) {
        // Check for coupon/promo codes (uppercase alphanumeric, 4-15 chars)
        const couponMatch = content?.match(/\b([A-Z0-9]{4,15})\b/);
        const hasCoupon = couponMatch && (
          content?.toLowerCase().includes('code') ||
          content?.toLowerCase().includes('coupon') ||
          content?.toLowerCase().includes('use')
        );
        
        // Check for limited time offers
        const isLimitedTime = content?.toLowerCase().match(/limited|expires?|valid until|ends?|hurry|last chance|today only/);
        
        // Check for URLs
        const urlMatch = content?.match(/(https?:\/\/[^\s]+)/);
        
        return (
          <div className="template-message marketing-template">
            <div className="template-header">
              <span className="template-icon">Promo</span>
              <span className="template-label">Marketing</span>
              {isLimitedTime && <span className="template-badge urgent">Limited Time</span>}
            </div>
            <div className="template-body">
              <div className="template-text">{content}</div>
              {hasCoupon && couponMatch && (
                <div className="coupon-code" onClick={() => navigator.clipboard.writeText(couponMatch[1])}>
                  <span className="coupon-label">Promo Code:</span>
                  <span className="coupon-value">{couponMatch[1]}</span>
                  <span className="coupon-copy">Copy</span>
                </div>
              )}
              {urlMatch && (
                <a href={urlMatch[1]} target="_blank" rel="noopener noreferrer" className="template-cta-btn">
                  <span>Link</span>
                  <span>Open Link</span>
                </a>
              )}
            </div>
          </div>
        );
      }
      
      // Generic template message
      return (
        <div className="template-message">
          <div className="template-header">
            <span className="template-icon">Tmpl</span>
            <span className="template-label">Template</span>
          </div>
          <div className="template-body">
            <div className="template-text">{content}</div>
          </div>
        </div>
      );
    }
    
    // Button messages (quick reply buttons from templates)
    if (messageType === 'button' || content?.startsWith('[Button]')) {
      return (
        <div className="button-message">
          <div className="button-icon">Btn</div>
          <div className="button-content">
            <span className="button-text">{content?.replace('[Button]', '').trim() || 'Button pressed'}</span>
          </div>
        </div>
      );
    }
    
    // System messages
    if (messageType === 'system' || content === '[System Message]') {
      return (
        <div className="system-message">
          <span className="system-icon">Info</span>
          <span className="system-text">{content?.replace('[System Message]', '') || 'System notification'}</span>
        </div>
      );
    }
    
    // Request welcome (user clicked Message button)
    if (messageType === 'request_welcome' || content?.includes('requested to start conversation')) {
      return (
        <div className="welcome-message">
          <span className="welcome-icon">Hi</span>
          <span className="welcome-text">User started the conversation</span>
        </div>
      );
    }
    
    // Referral messages (click-to-WhatsApp ads, social posts)
    if (messageType === 'referral' || content?.startsWith('[Referral:')) {
      const detail = content?.replace(/^\[Referral: ?\w*\]\s*/, '').trim();
      return (
        <div className="referral-message">
          <span className="referral-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></span>
          <span className="referral-text">{detail || 'Came from an ad or referral'}</span>
        </div>
      );
    }
    
    // Ad click messages
    if (messageType === 'ad_click' || content?.startsWith('[Ad Click')) {
      return (
        <div className="referral-message">
          <span className="referral-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg></span>
          <span className="referral-text">Clicked a WhatsApp ad</span>
        </div>
      );
    }
    
    // Product / catalog messages
    if (messageType === 'product' || messageType === 'product_inquiry' || content?.startsWith('[Product')) {
      const detail = content?.replace(/[\[\]]/g, '') || 'Product inquiry';
      return (
        <div className="product-message">
          <span className="product-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg></span>
          <span className="product-text">{detail}</span>
        </div>
      );
    }
    
    // Poll messages
    if (messageType === 'poll' || content?.startsWith('[Poll')) {
      const question = content?.match(/\[Poll: (.+?)\]/)?.[1] || 'Poll';
      return (
        <div className="poll-message">
          <span className="poll-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1a3a2a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="12" width="4" height="9"/><rect x="10" y="3" width="4" height="18"/><rect x="17" y="8" width="4" height="13"/></svg></span>
          <span className="poll-text">{question}</span>
        </div>
      );
    }
    
    // Unsupported messages
    if (messageType === 'unsupported' || content?.includes('[Unsupported') || content?.includes('[Message type not supported')) {
      // Detect OTP / authentication messages (hidden by WhatsApp for security)
      const isOtp = content?.includes('OTP') || content?.includes('authentication') || content?.includes('security');
      if (isOtp) {
        return (
          <div className="unsupported-message otp-notice">
            <span className="unsupported-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span>
            <span className="unsupported-text">OTP / verification message — content hidden by WhatsApp for security</span>
          </div>
        );
      }
      return (
        <div className="unsupported-message">
          {mediaUrl ? (
            <>
              <span className="unsupported-icon">File</span>
              <span className="unsupported-text">Media attachment</span>
              <a href={mediaUrl} target="_blank" rel="noopener noreferrer" className="unsupported-download">
                Download
              </a>
            </>
          ) : (
            <>
              <span className="unsupported-icon">!</span>
              <span className="unsupported-text">
                {content?.match(/\[Unsupported: (.+?)\]/)?.[1] || 'Message type not viewable'}
              </span>
            </>
          )}
        </div>
      );
    }
    
    // Fallback: show media if available, otherwise show content
    if (mediaUrl || s3Key) {
      return (
        <div className="media-message">
          <div className="media-container">
            <div className="generic-media">
              <span className="generic-icon">File</span>
              <span>Attachment</span>
            </div>
            {renderDownloadButton(mediaUrl)}
          </div>
          {content && <div className="media-caption">{content}</div>}
        </div>
      );
    }
    
    // Default: plain text
    return <div className="message-text">{content}</div>;
  };

  // Helper: Download button for media
  const renderDownloadButton = (url?: string) => {
    if (!url) return null;
    return (
      <a href={url} download target="_blank" rel="noopener noreferrer" className="download-btn" title="Download">
        DL
      </a>
    );
  };

  // Helper: Get document icon based on file extension
  const getDocumentIcon = (filename: string): string => {
    if (filename.match(/\.pdf$/i)) return 'PDF';
    if (filename.match(/\.(doc|docx)$/i)) return 'DOC';
    if (filename.match(/\.(xls|xlsx)$/i)) return 'XLS';
    if (filename.match(/\.(ppt|pptx)$/i)) return 'PPT';
    if (filename.match(/\.txt$/i)) return 'TXT';
    return 'FILE';
  };

  // Helper: Get document type label
  const getDocumentType = (filename: string): string => {
    if (filename.match(/\.pdf$/i)) return 'PDF Document';
    if (filename.match(/\.(doc|docx)$/i)) return 'Word Document';
    if (filename.match(/\.(xls|xlsx)$/i)) return 'Excel Spreadsheet';
    if (filename.match(/\.(ppt|pptx)$/i)) return 'PowerPoint';
    if (filename.match(/\.txt$/i)) return 'Text File';
    return 'Document';
  };

  if (!waId || !wabaInfo) {
    return (
      <Layout user={user} onSignOut={signOut}>
        <div className="page">
          <p>Loading...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="wa-page">
        <div className="wa-header">
          <button onClick={() => router.push('/dm/whatsapp')} className="btn btn-sm btn-ghost">Back</button>
          <div className="wa-header-info">
            <span className="wa-icon">WA</span>
            <div>
              <h1>{wabaInfo.name}</h1>
              <span className="wa-phone">{wabaInfo.phone}</span>
            </div>
          </div>
          <Button variant="secondary" icon="refresh" onClick={loadData} disabled={loading} loading={loading}>Refresh</Button>
        </div>

        <div className="wa-layout">
          {/* Contacts Sidebar */}
          <div className="wa-sidebar">
            <div className="sidebar-search">
              <input 
                type="text" 
                placeholder="Search contacts..." 
                value={contactSearchQuery}
                onChange={(e) => setContactSearchQuery(e.target.value)}
              />
            </div>
            <div className="contacts-list">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} style={{ padding: '12px 16px' }}>
                    <SkeletonContact />
                  </div>
                ))
              ) : filteredContacts.map(contact => (
                <div
                  key={contact.id}
                  className={`contact-row ${selectedContact?.id === contact.id ? 'active' : ''}`}
                  onClick={() => setSelectedContact(contact)}
                >
                  <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                  <div className="contact-details">
                    <div className="contact-name">
                      {contact.name}{contact.username ? <span style={{ color: '#9ca3af', fontWeight: 400, fontSize: 12, marginLeft: 4 }}>{contact.username}</span> : null}
                      {contact.unread > 0 && <span className="unread">{contact.unread}</span>}
                    </div>
                    {/* Show phone below name if contact has a real name */}
                    {contact.hasName && contact.phone && (
                      <div className="contact-phone-sub">{contact.phone}</div>
                    )}
                    {!contact.phone && contact.bsuid && (
                      <div className="contact-phone-sub" style={{ color: '#9ca3af', fontSize: 11 }}>{contact.bsuid} (BSUID)</div>
                    )}
                    <div className="contact-preview">{contact.lastMessage || 'No messages'}</div>
                  </div>
                  {contact.windowOpen && <span className="window-indicator">●</span>}
                </div>
              ))}
              {!loading && filteredContacts.length === 0 && (
                <div className="no-contacts">
                  {contactSearchQuery ? 'No contacts match search' : 'No conversations yet'}
                </div>
              )}
            </div>
          </div>

          {/* Chat Area */}
          <div className="wa-chat">
            {selectedContact ? (
              <>
                <div className="chat-header">
                  <div className="chat-contact">
                    <div className="contact-avatar large">{selectedContact.name.charAt(0).toUpperCase()}</div>
                    <div>
                      <div className="chat-name">{selectedContact.name}</div>
                      {/* Show phone/BSUID and username */}
                      <div className="chat-phone">
                        {selectedContact.phone || selectedContact.bsuid || 'No identifier'}
                        {selectedContact.username ? ` · ${selectedContact.username}` : ''}
                        {!selectedContact.phone && selectedContact.bsuid ? ' (BSUID)' : ''}
                      </div>
                    </div>
                  </div>
                  <div className="chat-header-actions">
                    <button 
                      className="chat-action-btn" 
                      onClick={() => setShowMessageSearch(!showMessageSearch)}
                      title="Search messages (Ctrl+F)"
                    >
                      Search
                    </button>
                    <div className="export-dropdown">
                      <button 
                        className="chat-action-btn" 
                        title="Export chat"
                      >
                        Export
                      </button>
                      <div className="export-menu">
                        <button onClick={exportChat}>Export as Text</button>
                        <button onClick={exportChatPDF}>Export as PDF</button>
                      </div>
                    </div>
                    <div className={`window-badge ${selectedContact.windowOpen ? 'open' : 'closed'}`}>
                      {selectedContact.windowOpen 
                        ? `● Open ${windowCountdown ? `(${windowCountdown})` : ''}` 
                        : '○ Closed'}
                    </div>
                  </div>
                </div>

                {/* Message Search Bar */}
                {showMessageSearch && (
                  <div className="message-search-bar">
                    <input
                      type="text"
                      placeholder="Search in conversation..."
                      value={messageSearchQuery}
                      onChange={(e) => setMessageSearchQuery(e.target.value)}
                      autoFocus
                    />
                    {messageSearchQuery && (
                      <span className="search-count">
                        {filteredMessages.length} found
                      </span>
                    )}
                    <button className="btn btn-sm btn-ghost" onClick={() => { setShowMessageSearch(false); setMessageSearchQuery(''); }}>×</button>
                  </div>
                )}

                <div className="messages-area">
                  {filteredMessages.map(msg => (
                    <div key={msg.id} className={`message ${msg.direction}`}>
                      <div className="message-bubble">
                        {/* Render message based on type */}
                        {renderMessageContent(msg)}
                        <div className="message-footer">
                          <span className="message-time">
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          {msg.direction === 'outbound' && (
                            <span className={`message-status ${msg.status}`}>
                              {msg.status === 'read' ? '✓✓' : msg.status === 'delivered' ? '✓✓' : msg.status === 'failed' ? '✗' : '✓'}
                            </span>
                          )}
                        </div>
                      </div>
                      {msg.direction === 'inbound' && msg.whatsappMessageId && (
                        <button 
                          className="reaction-btn" 
                          onClick={() => handleReaction(msg.whatsappMessageId!)}
                          title="React"
                        >
                          +
                        </button>
                      )}
                      <button 
                        className={`star-btn ${starredMessages.includes(msg.id) ? 'starred' : ''}`}
                        onClick={() => toggleStar(msg.id)}
                        title={starredMessages.includes(msg.id) ? 'Unstar message' : 'Star message'}
                      >
                        {starredMessages.includes(msg.id) ? '★' : '☆'}
                      </button>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                <div className="compose-area">
                  {/* Window Closed Warning */}
                  {!selectedContact.windowOpen && (
                    <div className="window-closed-warning">
                      <span className="warning-icon">!</span>
                      <span className="warning-text">24-hour window closed. You can only send template messages.</span>
                      <button 
                        className="template-btn"
                        onClick={() => setShowTemplateSender(true)}
                      >
                        Send Template
                      </button>
                    </div>
                  )}
                  
                  {/* Voice Note Recording UI */}
                  {isRecording ? (
                    <div className="voice-recording">
                      <button className="cancel-record-btn" onClick={cancelRecording} title="Cancel">
                        ×
                      </button>
                      <div className="recording-indicator">
                        <span className="recording-dot">●</span>
                        <span className="recording-time">{formatRecordingTime(recordingTime)}</span>
                      </div>
                      <button className="stop-record-btn" onClick={stopRecording} title="Stop Recording">
                        ⬜
                      </button>
                    </div>
                  ) : audioBlob ? (
                    <div className="voice-preview">
                      <button className="cancel-record-btn" onClick={cancelRecording} title="Discard">
                        ×
                      </button>
                      <audio src={audioUrl || ''} controls className="preview-audio" />
                      <button 
                        className="send-voice-btn" 
                        onClick={sendVoiceNote} 
                        disabled={sending}
                        title="Send Voice Note"
                      >
                        {sending ? '...' : '➤'}
                      </button>
                    </div>
                  ) : (
                    <div className="compose-row">
                      <button 
                        className="voice-btn" 
                        onClick={startRecording}
                        title="Record Voice Note"
                        disabled={!selectedContact.windowOpen}
                      >
                        Mic
                      </button>
                      <button 
                        className="interactive-btn" 
                        onClick={() => setShowInteractiveComposer(true)}
                        title="Send Interactive Message"
                        disabled={!selectedContact.windowOpen}
                      >
                        List
                      </button>
                      <button 
                        className="template-send-btn" 
                        onClick={() => setShowTemplateSender(true)}
                        title="Send Template Message"
                      >
                        Tmpl
                      </button>
                      <div className="compose-input">
                        <RichTextEditor
                          value={messageText}
                          onChange={setMessageText}
                          placeholder={selectedContact.windowOpen ? "Type a message..." : "Window closed - use template"}
                          channel="whatsapp"
                          showAISuggestions={true}
                          onSend={handleSend}
                          disabled={sending || !selectedContact.windowOpen}
                          contactContext={selectedContact.name}
                        />
                      </div>
                    </div>
                  )}
                  
                  {/* Interactive Message Composer */}
                  {showInteractiveComposer && selectedContact && (
                    <InteractiveMessageComposer
                      contactId={selectedContact.id}
                      phoneNumberId={waId as string}
                      recipientBsuid={selectedContact.bsuid || undefined}
                      onClose={() => setShowInteractiveComposer(false)}
                      onSent={() => loadData()}
                      onError={(msg) => toast.error(msg)}
                    />
                  )}
                  
                  {/* Template Sender */}
                  {showTemplateSender && selectedContact && (
                    <TemplateSender
                      contactId={selectedContact.id}
                      contactName={selectedContact.name}
                      phoneNumberId={waId as string}
                      recipientBsuid={selectedContact.bsuid || undefined}
                      onClose={() => setShowTemplateSender(false)}
                      onSent={() => loadData()}
                      onError={(msg) => toast.error(msg)}
                    />
                  )}
                </div>
              </>
            ) : (
              <div className="no-chat">
                <p>Select a conversation</p>
                <small>Choose a contact from the list</small>
              </div>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        .wa-page { height: calc(100vh - 60px); display: flex; flex-direction: column; }
        .wa-header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #000; color: #fff; }
        .back-btn, .refresh-btn { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 8px 12px; border-radius: 13px; cursor: pointer; }
        .wa-header-info { display: flex; align-items: center; gap: 12px; flex: 1; }
        .wa-icon { font-size: 14px; font-weight: 600; background: #fff; color: #000; padding: 4px 8px; border-radius: 6px; }
        .wa-header h1 { font-size: 18px; font-weight: 500; margin: 0; }
        .wa-phone { font-size: 13px; opacity: 0.9; }
        .error-bar { background: #f5f5f5; color: #000; padding: 8px 16px; font-size: 13px; border: 1px solid #000; }
        .wa-layout { display: grid; grid-template-columns: 300px 1fr; flex: 1; overflow: hidden; }
        .wa-sidebar { background: #fff; border-right: 1px solid #e5e5e5; display: flex; flex-direction: column; }
        .sidebar-search { padding: 12px; border-bottom: 1px solid #e5e5e5; }
        .sidebar-search input { width: 100%; padding: 10px 14px; border: 1px solid #000; border-radius: 13px; font-size: 14px; }
        .contacts-list { flex: 1; overflow-y: auto; }
        .contact-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; }
        .contact-row:hover { background: #f5f5f5; }
        .contact-row.active { background: #f5f5f5; }
        .contact-avatar { width: 44px; height: 44px; background: #e5e5e5; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; color: #666; }
        .contact-avatar.large { width: 40px; height: 40px; }
        .contact-details { flex: 1; min-width: 0; }
        .contact-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .contact-phone-sub { font-size: 11px; color: #666; margin-top: 1px; }
        .contact-preview { font-size: 12px; color: #999; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .unread { background: #000; color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
        .window-indicator { color: #000; font-size: 10px; }
        .wa-chat { display: flex; flex-direction: column; background: #e5ddd5; }
        .chat-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #f0f0f0; border-bottom: 1px solid #e5e5e5; }
        .chat-contact { display: flex; align-items: center; gap: 12px; }
        .chat-name { font-weight: 500; }
        .chat-phone { font-size: 12px; color: #666; }
        .window-badge { font-size: 12px; padding: 4px 12px; border-radius: 12px; }
        .window-badge.open { background: #f9fafb; color: #0f2a1d; }
        .window-badge.closed { background: #f3f4f6; color: #6b7280; }
        .messages-area { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 8px; }
        .message { display: flex; align-items: flex-end; gap: 4px; max-width: 70%; }
        .message.inbound { align-self: flex-start; }
        .message.outbound { align-self: flex-end; flex-direction: row-reverse; }
        .message-bubble { background: #fff; padding: 8px 12px; border-radius: 8px; max-width: 100%; }
        .message.outbound .message-bubble { background: #dcf8c6; }
        
        /* Text messages */
        .message-text { font-size: 14px; line-height: 1.4; word-wrap: break-word; white-space: pre-wrap; }
        
        /* Media messages */
        .media-message { display: flex; flex-direction: column; gap: 6px; }
        .media-container { position: relative; display: inline-block; }
        .message-media { max-width: 240px; max-height: 300px; border-radius: 8px; object-fit: cover; cursor: pointer; }
        .message-media.image:hover { opacity: 0.95; }
        .message-media.video { background: #000; }
        .media-caption { font-size: 14px; line-height: 1.4; margin-top: 4px; }
        .download-btn { position: absolute; top: 6px; right: 6px; background: rgba(0,0,0,0.6); color: #fff; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; text-decoration: none; font-size: 14px; opacity: 0; transition: opacity 0.2s; }
        .media-container:hover .download-btn { opacity: 1; }
        .download-btn:hover { background: rgba(0,0,0,0.8); }
        
        /* Sticker messages */
        .sticker-message { padding: 4px; }
        .message-sticker { max-width: 150px; max-height: 150px; }
        
        /* Audio/Voice note messages */
        .audio-message { display: flex; align-items: center; gap: 10px; min-width: 200px; }
        .audio-message.voice-note { background: #e7f5e7; padding: 8px 12px; border-radius: 20px; margin: -8px -12px; }
        .audio-icon { font-size: 20px; }
        .message-audio { flex: 1; height: 36px; max-width: 180px; }
        
        /* Document messages */
        .document-message { min-width: 200px; }
        .document-link { display: flex; align-items: center; gap: 12px; padding: 12px; background: #f5f5f5; border-radius: 8px; text-decoration: none; color: inherit; transition: background 0.2s; }
        .document-link:hover { background: #eee; }
        .doc-icon { font-size: 28px; }
        .doc-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
        .doc-name { font-size: 13px; font-weight: 500; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .doc-type { font-size: 11px; color: #666; }
        .doc-download { font-size: 16px; opacity: 0.6; }
        .document-link:hover .doc-download { opacity: 1; }
        
        /* Location messages */
        .location-message { min-width: 200px; }
        .location-link { display: block; text-decoration: none; color: inherit; }
        .location-preview { position: relative; border-radius: 8px; overflow: hidden; background: #e5e5e5; min-height: 100px; }
        .location-map { width: 100%; height: 100px; object-fit: cover; }
        .location-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.3); display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff; gap: 4px; }
        .location-icon { font-size: 24px; }
        .location-coords { font-size: 11px; color: #666; margin-top: 4px; text-align: center; }
        
        /* Contact card messages */
        .contact-card-message { display: flex; align-items: center; gap: 12px; padding: 8px; background: #f5f5f5; border-radius: 8px; min-width: 180px; }
        .contact-card-icon { font-size: 28px; background: #e5e5e5; width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .contact-card-info { display: flex; flex-direction: column; }
        .contact-card-label { font-size: 13px; font-weight: 500; }
        .contact-card-hint { font-size: 11px; color: #666; }
        
        /* Interactive messages (button/list/flow replies) */
        .interactive-message { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #f9fafb; border-radius: 8px; border-left: 3px solid #1a3a2a; }
        .interactive-icon { font-size: 18px; }
        .interactive-content { display: flex; flex-direction: column; }
        .interactive-label { font-size: 11px; color: #1a3a2a; font-weight: 500; text-transform: uppercase; }
        .interactive-value { font-size: 14px; color: #333; }
        
        /* Order messages */
        .order-message { display: flex; align-items: center; gap: 12px; padding: 12px; background: #f9fafb; border-radius: 8px; border-left: 3px solid #1a3a2a; }
        .order-icon { font-size: 24px; }
        .order-info { display: flex; flex-direction: column; }
        .order-label { font-size: 13px; font-weight: 500; color: #0f2a1d; }
        .order-hint { font-size: 11px; color: #0f2a1d; }
        
        /* Payment messages */
        .payment-message { display: flex; align-items: center; gap: 12px; padding: 12px; background: #f3f4f6; border-radius: 8px; border-left: 3px solid #1a3a2a; }
        .payment-icon { font-size: 24px; }
        .payment-info { display: flex; flex-direction: column; }
        .payment-label { font-size: 11px; color: #0f2a1d; font-weight: 500; text-transform: uppercase; }
        .payment-content { font-size: 14px; color: #0f2a1d; }
        
        /* Template messages (OTP, authentication, marketing, utility) */
        .template-message { display: flex; flex-direction: column; gap: 8px; min-width: 200px; }
        .template-header { display: flex; align-items: center; gap: 6px; padding-bottom: 6px; border-bottom: 1px solid #e5e5e5; }
        .template-icon { font-size: 16px; }
        .template-label { font-size: 11px; color: #666; font-weight: 500; text-transform: uppercase; }
        .template-body { padding: 4px 0; }
        .template-text { font-size: 14px; line-height: 1.4; white-space: pre-wrap; }
        
        /* OTP/Authentication template */
        .otp-template .template-header { border-color: #e5e7eb; }
        .otp-template .template-label { color: #0f2a1d; }
        .otp-template .template-body { text-align: center; padding: 8px 0; }
        .otp-code { font-size: 28px; font-weight: 700; font-family: monospace; letter-spacing: 4px; color: #0f2a1d; background: #f9fafb; padding: 12px 20px; border-radius: 8px; margin-bottom: 8px; }
        .otp-text { font-size: 13px; color: #666; }
        .template-button { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 16px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
        .template-button:hover { background: #f3f4f6; border-color: #1a3a2a; }
        .template-button .btn-icon { font-size: 14px; }
        .copy-code-btn { color: #0f2a1d; font-weight: 500; font-size: 13px; }
        
        /* Utility template (transactional) */
        .utility-template .template-header { border-color: #d1d5db; }
        .utility-template .template-label { color: #374151; }
        .utility-template { background: #f9fafb; margin: -8px -12px; padding: 8px 12px; border-radius: 8px; }
        .template-sublabel { font-size: 10px; color: #6b7280; margin-left: auto; background: #e5e7eb; padding: 2px 6px; border-radius: 4px; }
        .utility-reference { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; padding: 8px; background: #fff; border-radius: 6px; border: 1px solid #e5e7eb; }
        .reference-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
        .ref-label { color: #6b7280; font-weight: 500; }
        .ref-value { font-family: monospace; color: #374151; background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
        .ref-copy { cursor: pointer; opacity: 0.6; font-size: 12px; }
        .ref-copy:hover { opacity: 1; }
        
        /* Marketing template (promotional) */
        .marketing-template .template-header { border-color: #e5e7eb; }
        .marketing-template .template-label { color: #0f2a1d; }
        .marketing-template { background: #f9fafb; margin: -8px -12px; padding: 8px 12px; border-radius: 8px; }
        .template-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: auto; }
        .template-badge.urgent { background: #f9fafb; color: #1a3a2a; }
        .coupon-code { display: flex; align-items: center; gap: 8px; background: #f3f4f6; padding: 8px 12px; border-radius: 6px; margin-top: 8px; cursor: pointer; border: 1px dashed #1a3a2a; }
        .coupon-code:hover { background: #e5e7eb; }
        .coupon-label { font-size: 11px; color: #0f2a1d; }
        .coupon-value { font-size: 16px; font-weight: 700; font-family: monospace; color: #0f2a1d; letter-spacing: 1px; }
        .coupon-copy { font-size: 14px; margin-left: auto; opacity: 0.6; }
        .coupon-code:hover .coupon-copy { opacity: 1; }
        .template-cta-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 8px 16px; background: #d1f470; color: #1a3a2a; border-radius: 6px; margin-top: 8px; text-decoration: none; font-size: 13px; font-weight: 500; transition: background 0.2s; }
        .template-cta-btn:hover { background: #c5e866; }
        
        /* Button messages (quick reply) */
        .button-message { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #f3f4f6; border-radius: 8px; border-left: 3px solid #1a3a2a; }
        .button-icon { font-size: 18px; }
        .button-content { display: flex; flex-direction: column; }
        .button-text { font-size: 14px; color: #0f2a1d; }
        
        /* Reaction messages */
        .reaction-message { display: flex; align-items: center; gap: 8px; padding: 4px 8px; }
        .reaction-emoji { font-size: 24px; }
        .reaction-label { font-size: 12px; color: #666; font-style: italic; }
        
        /* System messages */
        .system-message { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: #f5f5f5; border-radius: 12px; font-size: 12px; color: #666; }
        .system-icon { font-size: 14px; }
        .system-text { font-style: italic; }
        
        /* Welcome messages */
        .welcome-message { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #f9fafb; border-radius: 8px; }
        .welcome-icon { font-size: 20px; }
        .welcome-text { font-size: 13px; color: #0f2a1d; }
        
        /* Unsupported messages */
        .unsupported-message { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #f3f4f6; border-radius: 8px; }
        .unsupported-icon { font-size: 16px; }
        .unsupported-text { font-size: 13px; color: #6b7280; font-style: italic; }
        .unsupported-download { font-size: 12px; color: #1a3a2a; text-decoration: none; margin-left: auto; }
        .unsupported-download:hover { text-decoration: underline; }
        
        /* Generic media fallback */
        .generic-media { display: flex; align-items: center; gap: 8px; padding: 12px; background: #f5f5f5; border-radius: 8px; }
        .generic-icon { font-size: 24px; }
        
        /* Message footer */
        .message-footer { display: flex; justify-content: flex-end; gap: 4px; margin-top: 4px; }
        .message-time { font-size: 11px; color: #999; }
        .message-status { font-size: 12px; }
        .message-status.read, .message-status.delivered { color: #1a3a2a; }
        .message-status.failed { color: #1a3a2a; }
        .reaction-btn { background: none; border: none; cursor: pointer; font-size: 14px; opacity: 0.5; }
        .reaction-btn:hover { opacity: 1; }
        
        /* Compose area */
        .compose-area { padding: 12px 16px; background: #f0f0f0; }
        .window-closed-warning { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #f9fafb; border-radius: 8px; margin-bottom: 10px; border: 1px solid #e5e7eb; }
        .warning-icon { font-size: 16px; }
        .warning-text { flex: 1; font-size: 13px; color: #0f2a1d; }
        .template-btn { background: #1a3a2a; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; white-space: nowrap; }
        .template-btn:hover { background: #1a3a2a; }
        .compose-row { display: flex; align-items: flex-end; gap: 8px; }
        .compose-input { flex: 1; }
        .voice-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #000; background: #fff; color: #000; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }
        .voice-btn:hover:not(:disabled) { background: #f5f5f5; transform: scale(1.05); }
        .voice-btn:disabled { background: #9ca3af; cursor: not-allowed; opacity: 0.6; }
        .interactive-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #000; background: #fff; color: #000; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }
        .interactive-btn:hover:not(:disabled) { background: #f5f5f5; transform: scale(1.05); }
        .interactive-btn:disabled { background: #9ca3af; cursor: not-allowed; opacity: 0.6; }
        .template-send-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #000; background: #fff; color: #000; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }
        .template-send-btn:hover { background: #f5f5f5; transform: scale(1.05); }
        .voice-recording { display: flex; align-items: center; gap: 12px; background: #fff; padding: 12px 16px; border-radius: 24px; }
        .cancel-record-btn { width: 32px; height: 32px; border-radius: 50%; border: none; background: #6b7280; color: #fff; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .cancel-record-btn:hover { background: #4b5563; }
        .recording-indicator { flex: 1; display: flex; align-items: center; gap: 8px; }
        .recording-dot { color: #1a3a2a; font-size: 12px; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .recording-time { font-size: 16px; font-weight: 500; color: #333; font-family: monospace; }
        .stop-record-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #000; background: #fff; color: #000; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .stop-record-btn:hover { background: #f5f5f5; }
        .voice-preview { display: flex; align-items: center; gap: 12px; background: #fff; padding: 8px 16px; border-radius: 24px; }
        .preview-audio { flex: 1; height: 36px; }
        .send-voice-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #000; background: #fff; color: #000; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .send-voice-btn:hover { background: #f5f5f5; }
        .send-voice-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .no-chat { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #999; }
        .no-chat p { font-size: 24px; margin: 0; }
        .no-chat small { margin-top: 8px; }
        
        /* Chat header actions */
        .chat-header-actions { display: flex; align-items: center; gap: 8px; }
        .chat-action-btn { background: none; border: none; cursor: pointer; font-size: 18px; padding: 6px; border-radius: 6px; opacity: 0.7; transition: all 0.2s; }
        .chat-action-btn:hover { opacity: 1; background: rgba(0,0,0,0.05); }
        
        /* Export dropdown */
        .export-dropdown { position: relative; }
        .export-dropdown:hover .export-menu { display: block; }
        .export-menu { display: none; position: absolute; top: 100%; right: 0; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); min-width: 160px; z-index: 100; overflow: hidden; }
        .export-menu button { display: flex; align-items: center; gap: 8px; width: 100%; padding: 10px 14px; border: none; background: none; cursor: pointer; font-size: 13px; text-align: left; transition: background 0.2s; }
        .export-menu button:hover { background: #f5f5f5; }
        
        /* Message search bar */
        .message-search-bar { display: flex; align-items: center; gap: 8px; padding: 8px 16px; background: #fff; border-bottom: 1px solid #e5e5e5; }
        .message-search-bar input { flex: 1; padding: 8px 12px; border: 1px solid #e5e5e5; border-radius: 20px; font-size: 14px; }
        .message-search-bar input:focus { outline: none; border-color: #000; }
        .message-search-bar .search-count { font-size: 12px; color: #666; }
        .message-search-bar button { background: none; border: none; cursor: pointer; font-size: 16px; color: #999; padding: 4px; }
        .message-search-bar button:hover { color: #333; }
        
        /* Star button */
        .star-btn { background: none; border: none; cursor: pointer; font-size: 14px; opacity: 0.3; transition: all 0.2s; padding: 2px; }
        .star-btn:hover { opacity: 0.7; }
        .star-btn.starred { opacity: 1; color: #1a3a2a; }
        
        /* No contacts message */
        .no-contacts { padding: 20px; text-align: center; color: #999; font-size: 13px; }
      `}</style>
    </Layout>
  );
};

export default WhatsAppConversation;
