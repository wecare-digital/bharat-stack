/**
 * WhatsApp Unified Inbox
 * Single inbox showing messages from all WABAs
 * Select WABA when sending messages
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Layout from '../../../components/Layout';
import RichTextEditor from '../../../components/RichTextEditor';
import Toast, { useToast } from '../../../components/Toast';
import SEO, { PAGE_SEO } from '../../../components/SEO';
import * as api from '../../../api/client';
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
  whatsappMessageId?: string | null;
  mediaUrl?: string | null;
  messageType?: string | null;  // image, video, audio, document, sticker, text
  receivingPhone?: string | null;
  awsPhoneNumberId?: string | null;
  senderName?: string | null;
  senderPhone?: string | null;
}

interface Contact {
  id: string;
  name: string;
  phone: string;
  lastMessage?: string;
  lastMessageTime?: string;
  lastWabaId?: string;
  unread: number;
}

const WABA_CONFIG = {
  [WHATSAPP_PHONES.primary.id]: {
    name: WHATSAPP_PHONES.primary.name,
    phone: WHATSAPP_PHONES.primary.display,
    color: '#000',
    shortName: 'WC'
  },
  [WHATSAPP_PHONES.secondary.id]: {
    name: WHATSAPP_PHONES.secondary.name,
    phone: WHATSAPP_PHONES.secondary.display,
    color: '#4a4a4a',
    shortName: 'MA'
  },
};

const WhatsAppUnifiedInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [selectedWaba, setSelectedWaba] = useState<string>(WHATSAPP_PHONES.primary.id);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [contactsPage, setContactsPage] = useState(1);
  const CONTACTS_PER_PAGE = 20;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, selectedContact]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, messagesData] = await Promise.all([
        api.listContacts(),
        api.listMessages(undefined, 'WHATSAPP'),
      ]);

      // Process messages to get last message info per contact
      // Also track sender names from inbound messages
      const contactMsgMap = new Map<string, { lastMsg: any; lastWabaId: string; unread: number; senderName: string }>();
      
      messagesData.forEach(m => {
        const existing = contactMsgMap.get(m.contactId);
        const msgTime = new Date(m.timestamp).getTime();
        
        // Track sender name from inbound messages
        const senderName = m.direction === 'INBOUND' && m.senderName ? m.senderName : (existing?.senderName || '');
        
        if (!existing || msgTime > new Date(existing.lastMsg.timestamp).getTime()) {
          contactMsgMap.set(m.contactId, {
            lastMsg: m,
            lastWabaId: m.awsPhoneNumberId || '',
            unread: (existing?.unread || 0) + (m.direction === 'INBOUND' && m.status === 'received' ? 1 : 0),
            senderName: senderName || existing?.senderName || ''
          });
        } else if (senderName && !existing.senderName) {
          // Update sender name if we found one
          existing.senderName = senderName;
        }
      });

      const displayContacts: Contact[] = contactsData
        .filter(c => c.phone)
        .map(c => {
          const msgInfo = contactMsgMap.get(c.contactId);
          // Use contact name, or sender name from messages, or phone as fallback
          const displayName = c.name || msgInfo?.senderName || c.phone;
          
          // Format last message with media type indicator
          let lastMsgPreview = '';
          if (msgInfo?.lastMsg) {
            const msg = msgInfo.lastMsg;
            const msgType = msg.messageType?.toLowerCase();
            
            // Add media type icon prefix
            if (msgType === 'image') lastMsgPreview = '[Image] ';
            else if (msgType === 'video') lastMsgPreview = '[Video] ';
            else if (msgType === 'audio' || msgType === 'voice') lastMsgPreview = '[Audio] ';
            else if (msgType === 'document') lastMsgPreview = '[Doc] ';
            else if (msgType === 'sticker') lastMsgPreview = '[Sticker] ';
            else if (msgType === 'location') lastMsgPreview = '[Location] ';
            else if (msgType === 'contacts') lastMsgPreview = '[Contact] ';
            
            // Add content preview
            const content = msg.content || '';
            if (content.startsWith('[') && content.endsWith(']')) {
              // Special message type - show type name
              lastMsgPreview += content.replace(/[\[\]]/g, '');
            } else {
              lastMsgPreview += content.substring(0, 40);
              if (content.length > 40) lastMsgPreview += '...';
            }
          }
          
          return {
            id: c.contactId,
            name: displayName,
            phone: c.phone,
            lastMessage: lastMsgPreview,
            lastMessageTime: msgInfo?.lastMsg?.timestamp,
            lastWabaId: msgInfo?.lastWabaId || '',
            unread: msgInfo?.unread || 0,
          };
        })
        .sort((a, b) => {
          if (!a.lastMessageTime) return 1;
          if (!b.lastMessageTime) return -1;
          return new Date(b.lastMessageTime).getTime() - new Date(a.lastMessageTime).getTime();
        });

      setContacts(displayContacts);
      setMessages(messagesData.map(m => ({
        id: m.messageId,
        direction: m.direction.toLowerCase() as 'inbound' | 'outbound',
        content: m.content || '',
        timestamp: m.timestamp,
        status: m.status?.toLowerCase() || 'sent',
        contactId: m.contactId,
        whatsappMessageId: m.whatsappMessageId,
        mediaUrl: m.mediaUrl,  // Use pre-signed URL from API
        messageType: m.messageType,  // image, video, audio, document, sticker, text
        receivingPhone: m.receivingPhone,
        awsPhoneNumberId: m.awsPhoneNumberId,
        senderName: m.senderName,  // Sender's WhatsApp profile name
        senderPhone: m.senderPhone,  // Sender's phone number
      })));

      // Auto-select WABA based on last message
      if (selectedContact) {
        const contact = displayContacts.find(c => c.id === selectedContact.id);
        if (contact?.lastWabaId && WABA_CONFIG[contact.lastWabaId as keyof typeof WABA_CONFIG]) {
          setSelectedWaba(contact.lastWabaId);
        }
      }
    } catch (err) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [selectedContact]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  // When selecting a contact, auto-select the WABA they last messaged from
  useEffect(() => {
    if (selectedContact?.lastWabaId && WABA_CONFIG[selectedContact.lastWabaId as keyof typeof WABA_CONFIG]) {
      setSelectedWaba(selectedContact.lastWabaId);
    }
  }, [selectedContact]);

  const filteredMessages = messages
    .filter(m => {
      if (!selectedContact) return false;
      // Match by contactId - handle both inbound and outbound
      const contactMatch = m.contactId === selectedContact.id;
      if (!contactMatch) {
        console.debug('Message contactId mismatch:', {
          messageContactId: m.contactId,
          selectedContactId: selectedContact.id,
          messageId: m.id,
          direction: m.direction
        });
      }
      return contactMatch;
    })
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const filteredContacts = contacts.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.phone.includes(searchQuery)
  );

  // Pagination for contacts
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice(
    (contactsPage - 1) * CONTACTS_PER_PAGE,
    contactsPage * CONTACTS_PER_PAGE
  );

  // Reset page when search changes
  useEffect(() => {
    setContactsPage(1);
  }, [searchQuery]);

  const handleSend = async () => {
    if (!selectedContact || (!messageText.trim() && !mediaFile) || sending) return;
    setSending(true);

    try {
      let mediaBase64 = undefined;
      let mediaFileName = undefined;
      
      // Convert media file to base64 if present
      if (mediaFile) {
        mediaFileName = mediaFile.name; // Capture real filename
        mediaBase64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            const result = reader.result as string;
            // Extract base64 part (remove data:image/jpeg;base64, prefix)
            const base64 = result.split(',')[1];
            resolve(base64);
          };
          reader.onerror = reject;
          reader.readAsDataURL(mediaFile);
        });
      }

      const result = await api.sendWhatsAppMessage({
        contactId: selectedContact.id,
        content: messageText,
        phoneNumberId: selectedWaba,
        mediaFile: mediaBase64,
        mediaType: mediaFile?.type,
        mediaFileName: mediaFileName, // Pass real filename
      });

      if (result) {
        toast.success(`Sent via ${WABA_CONFIG[selectedWaba as keyof typeof WABA_CONFIG]?.name || 'WhatsApp'}`);
        setMessageText('');
        setMediaFile(null);
        setMediaPreview(null);
        await loadData();
      } else {
        toast.error('Failed to send. Check if 24h window is open or use a template.');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleMediaSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Validate filename - warn if it contains special characters
    const validFilenameChars = /^[a-zA-Z0-9\s._\-()]+$/;
    if (!validFilenameChars.test(file.name)) {
      const invalidChars = file.name.replace(/[a-zA-Z0-9\s._\-()]/g, '').split('').filter((v, i, a) => a.indexOf(v) === i);
      console.warn('Filename contains special characters that may be removed:', invalidChars);
      toast.error(`Filename contains invalid characters: ${invalidChars.join(', ')}. They will be removed.`);
    }
    
    // Validate file size based on type per AWS Social Messaging docs
    let maxSize = 5 * 1024 * 1024; // Default 5MB for images
    
    if (file.type.startsWith('video/')) {
      maxSize = 16 * 1024 * 1024; // 16MB for video
    } else if (file.type.startsWith('audio/')) {
      maxSize = 16 * 1024 * 1024; // 16MB for audio
    } else if (file.type === 'application/pdf' || file.type.startsWith('application/')) {
      maxSize = 100 * 1024 * 1024; // 100MB for documents
    } else if (file.type === 'image/webp') {
      maxSize = 500 * 1024; // 500KB for stickers
    }
    
    if (file.size > maxSize) {
      const maxSizeMB = maxSize / (1024 * 1024);
      toast.error(`File too large. Max size: ${maxSizeMB.toFixed(0)}MB`);
      return;
    }
    
    setMediaFile(file);
    
    // Create preview for images and videos
    if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
      const reader = new FileReader();
      reader.onload = (e) => setMediaPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      // For documents, show filename
      setMediaPreview(file.name);
    }
  };

  const clearMedia = () => {
    setMediaFile(null);
    setMediaPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleReaction = async (whatsappMessageId: string, wabaId?: string | null) => {
    if (!selectedContact || !whatsappMessageId) return;
    try {
      await api.sendWhatsAppReaction({
        contactId: selectedContact.id,
        reactionMessageId: whatsappMessageId,
        reactionEmoji: '👍',
        phoneNumberId: wabaId || selectedWaba,
      });
    } catch (err) {
      console.error('Reaction failed:', err);
    }
  };

  const handleDeleteMessage = async (msg: Message) => {
    if (!confirm('Delete this message?')) return;
    setDeleting(msg.id);
    try {
      const direction = msg.direction === 'inbound' ? 'INBOUND' : 'OUTBOUND';
      const success = await api.deleteMessage(msg.id, direction);
      if (success) {
        toast.success('Message deleted');
        await loadData();
      } else {
        toast.error('Failed to delete message');
      }
    } catch (err) {
      toast.error('Delete error occurred');
    } finally {
      setDeleting(null);
    }
  };

  const handleDeleteContact = async (contact: Contact) => {
    if (!confirm(`Delete contact "${contact.name}"?\n\nNote: Messages will remain in the database.`)) return;
    setDeleting(contact.id);
    try {
      const success = await api.deleteContact(contact.id);
      if (success) {
        toast.success('Contact deleted (messages preserved)');
        setSelectedContact(null);
        await loadData();
      } else {
        toast.error('Failed to delete contact');
      }
    } catch (err) {
      toast.error('Delete error occurred');
    } finally {
      setDeleting(null);
    }
  };

  const handleClearAllMessages = async () => {
    if (!selectedContact) return;
    const contactMessages = filteredMessages;
    if (contactMessages.length === 0) {
      toast.error('No messages to clear');
      return;
    }
    if (!confirm(`Clear all ${contactMessages.length} messages for "${selectedContact.name}"?\n\nThis will delete all messages but keep the contact.`)) return;
    
    setDeleting('clearing');
    try {
      let deleted = 0;
      let failed = 0;
      
      // Delete messages in batches to avoid overwhelming the API
      for (const msg of contactMessages) {
        try {
          const direction = msg.direction === 'inbound' ? 'INBOUND' : 'OUTBOUND';
          const success = await api.deleteMessage(msg.id, direction);
          if (success) {
            deleted++;
          } else {
            failed++;
          }
        } catch (e) {
          failed++;
          console.error('Failed to delete message:', msg.id, e);
        }
      }
      
      if (deleted > 0) {
        toast.success(`Cleared ${deleted} messages${failed > 0 ? ` (${failed} failed)` : ''}`);
      } else {
        toast.error('Failed to clear messages');
      }
      await loadData();
    } catch (err) {
      toast.error('Failed to clear messages');
    } finally {
      setDeleting(null);
    }
  };

  const getWabaInfo = (wabaId?: string | null) => {
    if (!wabaId) return null;
    return WABA_CONFIG[wabaId as keyof typeof WABA_CONFIG];
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 86400000) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diff < 604800000) {
      return date.toLocaleDateString([], { weekday: 'short' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  // Helper to detect media type from messageType, content, or URL
  const getMediaType = (msg: Message): 'image' | 'video' | 'audio' | 'document' | 'sticker' | null => {
    if (!msg.mediaUrl) return null;
    
    // First check messageType field from API
    const msgType = msg.messageType?.toLowerCase();
    if (msgType === 'image') return 'image';
    if (msgType === 'video') return 'video';
    if (msgType === 'audio' || msgType === 'voice') return 'audio';
    if (msgType === 'document') return 'document';
    if (msgType === 'sticker') return 'sticker';
    
    // Fallback: check content text
    const content = (msg.content || '').toLowerCase();
    if (content.includes('image') || content.includes('photo')) return 'image';
    if (content.includes('video')) return 'video';
    if (content.includes('audio') || content.includes('voice') || content.includes('ptt')) return 'audio';
    if (content.includes('document') || content.includes('file')) return 'document';
    if (content.includes('sticker')) return 'sticker';
    
    // Fallback: check URL extension
    const url = msg.mediaUrl.toLowerCase();
    if (url.includes('.jpg') || url.includes('.jpeg') || url.includes('.png') || url.includes('.gif')) return 'image';
    if (url.includes('.webp')) return 'sticker';
    if (url.includes('.mp4') || url.includes('.3gp') || url.includes('.mov')) return 'video';
    if (url.includes('.mp3') || url.includes('.ogg') || url.includes('.aac') || url.includes('.amr') || url.includes('.m4a') || url.includes('.opus')) return 'audio';
    if (url.includes('.pdf') || url.includes('.doc') || url.includes('.xls') || url.includes('.ppt') || url.includes('.txt')) return 'document';
    
    // Default to document for unknown types
    return 'document';
  };

  // Get icon for media type - Unicode only
  const getMediaIcon = (type: string | null): string => {
    switch (type) {
      case 'image': return '◫';
      case 'video': return '▶';
      case 'audio': return '♪';
      case 'sticker': return '◉';
      case 'document': return '⎘';
      default: return '◰';
    }
  };

  // Render message content with special handling for unsupported types
  const renderMessageContent = (msg: Message) => {
    const content = msg.content || '';
    const msgType = msg.messageType?.toLowerCase() || '';
    
    // Check if this is an unsupported message type
    const isUnsupported = msgType === 'unsupported' || 
                          content.includes('[Unsupported') || 
                          content.includes('[Message type not supported');
    
    // For unsupported messages with media, show download link
    if (isUnsupported && msg.mediaUrl) {
      return (
        <span className="unsupported-with-media">
          <span className="unsupported-label">Media attachment</span>
          <a 
            href={msg.mediaUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="media-download-link"
          >
            ↓ Download
          </a>
        </span>
      );
    }
    
    // For unsupported messages without media
    if (isUnsupported) {
      // Try to extract useful info from the content
      const match = content.match(/\[Unsupported: (.+?)\]/);
      const detail = match ? match[1] : 'Message type not viewable';
      return (
        <span className="unsupported-msg">
          {detail}
        </span>
      );
    }
    
    // Handle special message types with better display
    if (content === '[Sticker]' && msg.mediaUrl) {
      return null; // Sticker image is shown in media container
    }
    
    if (content === '[Audio]' && msg.mediaUrl) {
      return null; // Audio player is shown in media container
    }
    
    if (content.startsWith('[Image]') || content.startsWith('[Video]')) {
      // Show caption if present, otherwise hide (media shown above)
      const caption = content.replace(/^\[(Image|Video)\]\s*/, '').trim();
      return caption || null;
    }
    
    // Location messages
    if (content.startsWith('[Location:')) {
      const match = content.match(/\[Location: ([\d.-]+), ([\d.-]+)\]/);
      if (match) {
        const [, lat, lng] = match;
        return (
          <a 
            href={`https://maps.google.com/?q=${lat},${lng}`}
            target="_blank"
            rel="noopener noreferrer"
            className="location-link"
          >
            View Location
          </a>
        );
      }
    }
    
    // Contact card
    if (content === '[Contact Card]') {
      return <span className="special-msg">Contact Card</span>;
    }
    
    // Interactive messages
    if (content.startsWith('[Interactive:') || content.startsWith('[Button') || content.startsWith('[List')) {
      return <span className="special-msg">{content.replace(/[\[\]]/g, '')}</span>;
    }
    
    // Flow responses
    if (content.startsWith('[Flow Response:')) {
      return <span className="special-msg">Flow Response</span>;
    }
    
    // Order messages
    if (content === '[Order]') {
      return <span className="special-msg">Order</span>;
    }
    
    // System messages
    if (content === '[System Message]') {
      return <span className="system-msg">System Message</span>;
    }
    
    // Default: show content as-is
    return content;
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title={PAGE_SEO.whatsapp.title}
        description={PAGE_SEO.whatsapp.description}
        keywords={PAGE_SEO.whatsapp.keywords}
        canonical="/dm/whatsapp"
        noindex={true}
      />
      <Toast toasts={toast.toasts} onRemove={toast.removeToast} />
      <div className="whatsapp-inbox">
        {/* Contacts Sidebar */}
        <div className="contacts-sidebar">
          <div className="sidebar-header">
            <h2>WA Inbox</h2>
            <div className="search-box">
              <input
                type="text"
                placeholder="Search contacts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          
          <div className="contacts-list">
            {paginatedContacts.map(contact => {
              const wabaInfo = getWabaInfo(contact.lastWabaId);
              return (
                <div
                  key={contact.id}
                  className={`contact-item ${selectedContact?.id === contact.id ? 'selected' : ''}`}
                  onClick={() => setSelectedContact(contact)}
                >
                  <div className="contact-avatar">
                    {contact.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="contact-info">
                    <div className="contact-name">{contact.name}</div>
                    <div className="contact-last-msg">
                      {wabaInfo && (
                        <span 
                          className="waba-indicator" 
                          style={{ background: wabaInfo.color }}
                        >
                          {wabaInfo.shortName}
                        </span>
                      )}
                      {contact.lastMessage || 'No messages'}
                    </div>
                  </div>
                  <div className="contact-meta">
                    {contact.lastMessageTime && (
                      <span className="contact-time">{formatTime(contact.lastMessageTime)}</span>
                    )}
                    {contact.unread > 0 && (
                      <span className="unread-badge">{contact.unread}</span>
                    )}
                    <button 
                      className="contact-delete-btn"
                      onClick={(e) => { e.stopPropagation(); handleDeleteContact(contact); }}
                      disabled={deleting === contact.id}
                      title="Delete contact"
                    >
                      {deleting === contact.id ? '...' : '✕'}
                    </button>
                  </div>
                </div>
              );
            })}
            
            {filteredContacts.length === 0 && (
              <div style={{ padding: '20px', textAlign: 'center', color: '#8696a0' }}>
                {searchQuery ? 'No contacts found' : 'No WhatsApp conversations yet'}
              </div>
            )}

            {/* Pagination Controls */}
            {totalContactPages > 1 && (
              <div className="contacts-pagination">
                <button 
                  onClick={() => setContactsPage(p => Math.max(1, p - 1))}
                  disabled={contactsPage === 1}
                >
                  ←
                </button>
                <span>{contactsPage} / {totalContactPages}</span>
                <button 
                  onClick={() => setContactsPage(p => Math.min(totalContactPages, p + 1))}
                  disabled={contactsPage === totalContactPages}
                >
                  →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className="chat-area">
          {selectedContact ? (
            <>
              {/* Chat Header */}
              <div className="chat-header">
                <div className="chat-contact-info">
                  <div className="contact-avatar" style={{ width: 40, height: 40, fontSize: 16 }}>
                    {selectedContact.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="chat-contact-name">{selectedContact.name}</div>
                    <div className="chat-contact-phone">{selectedContact.phone}</div>
                  </div>
                </div>
                
                <div className="waba-selector">
                  <label>Send from:</label>
                  <select 
                    value={selectedWaba} 
                    onChange={(e) => setSelectedWaba(e.target.value)}
                  >
                    {Object.entries(WABA_CONFIG).map(([id, config]) => (
                      <option key={id} value={id}>
                        {config.name} ({config.phone})
                      </option>
                    ))}
                  </select>
                  <button 
                    className="clear-chat-btn"
                    onClick={handleClearAllMessages}
                    disabled={deleting === 'clearing' || filteredMessages.length === 0}
                    title="Clear all messages for this contact"
                  >
                    {deleting === 'clearing' ? '...' : '×'}
                  </button>
                </div>
              </div>

              {/* Messages */}
              <div className="messages-area">
                {loading && filteredMessages.length === 0 && (
                  <div style={{ textAlign: 'center', color: '#8696a0', padding: '20px' }}>
                    Loading messages...
                  </div>
                )}
                
                {filteredMessages.map((msg, idx) => {
                  const wabaInfo = getWabaInfo(msg.awsPhoneNumberId);
                  const showDate = idx === 0 || 
                    new Date(msg.timestamp).toDateString() !== 
                    new Date(filteredMessages[idx - 1].timestamp).toDateString();
                  
                  return (
                    <React.Fragment key={msg.id}>
                      {showDate && (
                        <div className="date-divider">
                          <span>{new Date(msg.timestamp).toLocaleDateString([], { 
                            weekday: 'long', 
                            month: 'short', 
                            day: 'numeric' 
                          })}</span>
                        </div>
                      )}
                      <div className={`message-bubble ${msg.direction}`}>
                        {msg.direction === 'inbound' && msg.senderName && (
                          <div className="message-sender-name">
                            {msg.senderName}
                          </div>
                        )}
                        {msg.mediaUrl && (
                          <div className="message-media-container">
                            {(() => {
                              const mediaType = getMediaType(msg);
                              
                              if (mediaType === 'image' || mediaType === 'sticker') {
                                return (
                                  <a href={msg.mediaUrl} target="_blank" rel="noopener noreferrer">
                                    <img 
                                      src={msg.mediaUrl} 
                                      alt={mediaType === 'sticker' ? 'Sticker' : 'Image'} 
                                      className={`message-media ${mediaType === 'sticker' ? 'message-sticker' : 'message-image'}`}
                                      onError={(e) => {
                                        console.error('Image load error:', msg.mediaUrl);
                                        (e.target as HTMLImageElement).style.display = 'none';
                                      }}
                                    />
                                  </a>
                                );
                              }
                              
                              if (mediaType === 'video') {
                                return (
                                  <video 
                                    src={msg.mediaUrl} 
                                    controls 
                                    className="message-media message-video"
                                    onError={(e) => {
                                      console.error('Video load error:', msg.mediaUrl);
                                      (e.target as HTMLVideoElement).style.display = 'none';
                                    }}
                                  />
                                );
                              }
                              
                              if (mediaType === 'audio') {
                                return (
                                  <audio 
                                    src={msg.mediaUrl} 
                                    controls 
                                    className="message-media message-audio"
                                    onError={(e) => {
                                      console.error('Audio load error:', msg.mediaUrl);
                                      (e.target as HTMLAudioElement).style.display = 'none';
                                    }}
                                  />
                                );
                              }
                              
                              // Document or unknown type
                              return (
                                <div className="message-media message-document">
                                  <a 
                                    href={msg.mediaUrl} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="document-link"
                                  >
                                    {getMediaIcon(mediaType)} View/Download File
                                  </a>
                                </div>
                              );
                            })()}
                          </div>
                        )}
                        <div className="message-content">
                          {renderMessageContent(msg)}
                        </div>
                        <div className="message-footer">
                          {wabaInfo && (
                            <span 
                              className="message-waba-tag" 
                              style={{ background: wabaInfo.color }}
                            >
                              {wabaInfo.shortName}
                            </span>
                          )}
                          <span className="message-time">
                            {new Date(msg.timestamp).toLocaleTimeString([], { 
                              hour: '2-digit', 
                              minute: '2-digit' 
                            })}
                          </span>
                          {msg.direction === 'outbound' && (
                            <span className="message-status">
                              {msg.status === 'read' ? '✓✓' : msg.status === 'delivered' ? '✓✓' : '✓'}
                            </span>
                          )}
                          {msg.mediaUrl && (
                            <a 
                              href={msg.mediaUrl} 
                              target="_blank"
                              rel="noopener noreferrer"
                              className="media-download-btn"
                              title="Open media in new tab"
                              download
                            >
                              ↓
                            </a>
                          )}
                        </div>
                        {msg.direction === 'inbound' && msg.whatsappMessageId && (
                          <div className="message-actions">
                            <button 
                              className="reaction-btn"
                              onClick={() => handleReaction(msg.whatsappMessageId!, msg.awsPhoneNumberId)}
                              title="React with thumbs up"
                            >
                              +
                            </button>
                            <button 
                              className="delete-msg-btn"
                              onClick={() => handleDeleteMessage(msg)}
                              disabled={deleting === msg.id}
                              title="Delete message"
                            >
                              {deleting === msg.id ? '...' : '✕'}
                            </button>
                          </div>
                        )}
                        {msg.direction === 'outbound' && (
                          <div className="message-actions">
                            <button 
                              className="delete-msg-btn"
                              onClick={() => handleDeleteMessage(msg)}
                              disabled={deleting === msg.id}
                              title="Delete message"
                            >
                              {deleting === msg.id ? '...' : '✕'}
                            </button>
                          </div>
                        )}
                      </div>
                    </React.Fragment>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="input-area">
                {/* Media Preview */}
                {mediaPreview && (
                  <div className="media-preview">
                    {mediaFile?.type.startsWith('image/') ? (
                      <img src={mediaPreview} alt="Preview" />
                    ) : (
                      <div className="file-preview">
                        <span>◰</span>
                        <span>{mediaFile?.name}</span>
                      </div>
                    )}
                    <button className="clear-media-btn" onClick={clearMedia}>×</button>
                  </div>
                )}
                
                <div className="input-wrapper">
                  {/* Hidden file input for RichTextEditor attachment button */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleMediaSelect}
                    accept="image/jpeg,image/png,image/webp,video/mp4,video/3gpp,audio/mpeg,audio/mp3,audio/ogg,audio/aac,audio/amr,audio/mp4,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/plain"
                    style={{ display: 'none' }}
                  />
                  
                  <div className="input-box">
                    <RichTextEditor
                      value={messageText}
                      onChange={setMessageText}
                      placeholder="Type a message..."
                      channel="whatsapp"
                      onSend={handleSend}
                      showAISuggestions={true}
                      selectedContactId={selectedContact?.id}
                      phoneNumberId={selectedWaba}
                      contactContext={selectedContact?.name}
                      onAttachClick={() => fileInputRef.current?.click()}
                    />
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-chat">
              <div className="empty-chat-icon">◈</div>
              <h3>WhatsApp Unified Inbox</h3>
              <p>Select a contact to view messages</p>
              <p style={{ fontSize: '13px', marginTop: '8px' }}>
                Messages from both WABAs appear here
              </p>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default WhatsAppUnifiedInbox;
