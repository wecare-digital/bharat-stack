/**
 * Factory Reset Tab — Full system cleanup with all DynamoDB tables and S3 prefixes
 */
import React, { useState, useCallback, useEffect } from 'react';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import type { DashboardData } from '../../../types/dashboard';

interface DataTabProps {
  data: DashboardData;
  onRefresh: () => void;
}

const CLEANUP_FALLBACK: api.CleanupResource[] = [
  // Messages
  { id: 'whatsapp_inbox', label: 'WhatsApp Inbox (Inbound)', category: 'Messages', type: 'dynamodb', table: 'WhatsAppInboundTable', count: -1 },
  { id: 'whatsapp_outbox', label: 'WhatsApp Outbox (Outbound)', category: 'Messages', type: 'dynamodb', table: 'WhatsAppOutboundTable', count: -1 },
  { id: 'scheduled_messages', label: 'Scheduled Messages', category: 'Messages', type: 'dynamodb', table: 'ScheduledMessagesTable', count: -1 },
  { id: 'dlq_messages', label: 'DLQ Messages (Failed Retry Queue)', category: 'Messages', type: 'dynamodb', table: 'DLQMessagesTable', count: -1 },
  { id: 'messages_legacy', label: 'Messages (Legacy Table)', category: 'Messages', type: 'dynamodb', table: 'MessagesTable', count: -1 },
  // Contacts
  { id: 'contacts', label: 'Contacts', category: 'Contacts', type: 'dynamodb', table: 'ContactsTable', count: -1 },
  // Media
  { id: 'media_files', label: 'Media Files (DB records)', category: 'Media', type: 'dynamodb', table: 'MediaFilesTable', count: -1 },
  // AI
  { id: 'conversation_history', label: 'AI Conversation History', category: 'AI', type: 'dynamodb', table: 'ConversationHistoryTable', count: -1 },
  { id: 'ai_interactions', label: 'AI Interactions Log', category: 'AI', type: 'dynamodb', table: 'AIInteractionsTable', count: -1 },
  // Voice
  { id: 'whatsapp_calling', label: 'WhatsApp Call Logs', category: 'Voice', type: 'dynamodb', table: 'WhatsAppCallingTable', count: -1 },
  { id: 'voice_cdr', label: 'Voice CDR Records', category: 'Voice', type: 'dynamodb', table: 'VoiceCDRTable', count: -1 },
  { id: 'voice_calls', label: 'Voice Calls (Airtel)', category: 'Voice', type: 'dynamodb', table: 'VoiceCalls', count: -1 },
  { id: 'voice_aws', label: 'Voice AWS (Pinpoint)', category: 'Voice', type: 'dynamodb', table: 'VoiceAwsTable', count: -1 },
  { id: 'whatsapp_voice_log', label: 'WhatsApp Voice (TTS) Log', category: 'Voice', type: 'dynamodb', table: 'WhatsAppVoiceTable', count: -1 },
  { id: 'obd_campaigns', label: 'OBD Campaigns', category: 'Voice', type: 'dynamodb', table: 'OBDCampaigns', count: -1 },
  { id: 'airtel_c2c', label: 'Airtel C2C Records', category: 'Voice', type: 'dynamodb', table: 'AirtelC2CTable', count: -1 },
  // SMS
  { id: 'sms_aws', label: 'SMS AWS (Pinpoint)', category: 'SMS', type: 'dynamodb', table: 'SmsAwsTable', count: -1 },
  { id: 'airtel_sms', label: 'Airtel SMS Messages', category: 'SMS', type: 'dynamodb', table: 'AirtelSMSTable', count: -1 },
  { id: 'dlt_templates', label: 'DLT Templates (Airtel SMS)', category: 'SMS', type: 'dynamodb', table: 'DLTTemplates', count: -1 },
  // Invoices & Payments
  { id: 'invoices', label: 'Invoices', category: 'Invoices & Payments', type: 'dynamodb', table: 'InvoicesTable', count: -1 },
  { id: 'invoice_items', label: 'Invoice Line Items', category: 'Invoices & Payments', type: 'dynamodb', table: 'InvoiceItemsTable', count: -1 },
  { id: 'invoice_assets', label: 'Invoice Assets (PDFs)', category: 'Invoices & Payments', type: 'dynamodb', table: 'InvoiceAssetsTable', count: -1 },
  { id: 'invoice_delivery_log', label: 'Invoice Delivery Log', category: 'Invoices & Payments', type: 'dynamodb', table: 'InvoiceDeliveryLogTable', count: -1 },
  { id: 'invoice_sequence', label: 'Invoice Sequence Counter', category: 'Invoices & Payments', type: 'dynamodb', table: 'InvoiceSequenceTable', count: -1 },
  { id: 'payments', label: 'Payments', category: 'Invoices & Payments', type: 'dynamodb', table: 'PaymentsTable', count: -1 },
  { id: 'razorpay_webhook_log', label: 'Razorpay Webhook Log', category: 'Invoices & Payments', type: 'dynamodb', table: 'RazorpayWebhookLogTable', count: -1 },
  { id: 'payu_webhook_log', label: 'PayU Webhook Log', category: 'Invoices & Payments', type: 'dynamodb', table: 'PayUWebhookLogTable', count: -1 },
  // Bulk
  { id: 'bulk_jobs', label: 'Bulk Jobs', category: 'Bulk', type: 'dynamodb', table: 'BulkJobsTable', count: -1 },
  { id: 'bulk_recipients', label: 'Bulk Recipients', category: 'Bulk', type: 'dynamodb', table: 'BulkRecipientsTable', count: -1 },
  // Ecommerce
  { id: 'wix_products_cache', label: 'Wix Products Cache', category: 'Ecommerce', type: 'dynamodb', table: 'WixProductsCache', count: -1 },
  { id: 'wix_orders_cache', label: 'Wix Orders Cache', category: 'Ecommerce', type: 'dynamodb', table: 'WixOrdersCache', count: -1 },
  { id: 'wix_order_ids', label: 'Wix Order ID Mapping', category: 'Ecommerce', type: 'dynamodb', table: 'WixOrderIds', count: -1 },
  // Analytics & Logs
  { id: 'template_analytics', label: 'Template Analytics', category: 'Analytics & Logs', type: 'dynamodb', table: 'TemplateAnalyticsTable', count: -1 },
  { id: 'submit_requests', label: 'Flow Submit Requests', category: 'Analytics & Logs', type: 'dynamodb', table: 'SubmitRequestsTable', count: -1 },
  { id: 'audit_logs', label: 'Audit Logs', category: 'Analytics & Logs', type: 'dynamodb', table: 'AuditLog', count: -1 },
  // System (optional)
  { id: 'rate_limit', label: 'Rate Limit Trackers', category: 'System', type: 'dynamodb', table: 'RateLimitTracker', count: -1 },
  // S3 Storage
  { id: 's3_invoices', label: 'S3: Invoice Files', category: 'S3 Storage', type: 's3', prefix: 'base/invoices/', count: -1 },
  { id: 's3_whatsapp_media', label: 'S3: WhatsApp Media', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/', count: -1 },
  { id: 's3_whatsapp_media_incoming', label: 'S3: WhatsApp Media (Incoming)', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/incoming/', count: -1 },
  { id: 's3_whatsapp_media_outgoing', label: 'S3: WhatsApp Media (Outgoing)', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/outgoing/', count: -1 },
  { id: 's3_voice_recordings', label: 'S3: Voice Recordings', category: 'S3 Storage', type: 's3', prefix: 'base/voice/', count: -1 },
  { id: 's3_whatsapp_voice', label: 'S3: WhatsApp Voice (TTS)', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/voice/', count: -1 },
  { id: 's3_template_headers', label: 'S3: Template Headers', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/template-headers/', count: -1 },
  { id: 's3_product_images', label: 'S3: Product Images', category: 'S3 Storage', type: 's3', prefix: 'base/store/products/', count: -1 },
  { id: 's3_reports', label: 'S3: Reports & Exports', category: 'S3 Storage', type: 's3', prefix: 'base/reports/', count: -1 },
  { id: 's3_whatsapp_calling_ai', label: 'S3: WhatsApp Calling AI Audio', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/calling-ai/', count: -1 },
  { id: 's3_whatsapp_downloads', label: 'S3: WhatsApp Media Downloads', category: 'S3 Storage', type: 's3', prefix: 'base/whatsapp-media/downloads/', count: -1 },
  // SQS Queues
  { id: 'sqs_inbound_dlq', label: 'SQS: Inbound DLQ', category: 'SQS Queues', type: 'sqs', queue: 'base-wecare-digital-inbound-dlq', count: -1 },
  { id: 'sqs_bulk_dlq', label: 'SQS: Bulk DLQ', category: 'SQS Queues', type: 'sqs', queue: 'base-wecare-digital-bulk-dlq', count: -1 },
  { id: 'sqs_bulk_queue', label: 'SQS: Bulk Queue', category: 'SQS Queues', type: 'sqs', queue: 'base-wecare-digital-bulk-queue', count: -1 },
  { id: 'sqs_outbound_dlq', label: 'SQS: Outbound DLQ', category: 'SQS Queues', type: 'sqs', queue: 'base-wecare-digital-outbound-dlq', count: -1 },
];

const DataTab: React.FC<DataTabProps> = ({ data, onRefresh }) => {
  const { contacts, messages } = data;
  const toast = useToastContext();

  // Delete mode
  const [deleteMode, setDeleteMode] = useState<'messages' | 'hard' | 'clearAll' | 'systemCleanup' | null>(null);
  const [selectedContact, setSelectedContact] = useState('');
  const [selectedMessages, setSelectedMessages] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);


  // Modals
  const [showHardDeleteModal, setShowHardDeleteModal] = useState(false);
  const [showClearAllModal, setShowClearAllModal] = useState(false);

  // System cleanup
  const [cleanupResources, setCleanupResources] = useState<api.CleanupResource[]>([]);
  const [cleanupSelected, setCleanupSelected] = useState<Set<string>>(new Set());
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupRunning, setCleanupRunning] = useState(false);
  const [cleanupResults, setCleanupResults] = useState<api.CleanupResult[] | null>(null);
  const [showCleanupConfirm, setShowCleanupConfirm] = useState(false);
  const [cleanupConfirmText, setCleanupConfirmText] = useState('');

  const contactMessages = selectedContact
    ? messages.filter(m => m.contactId === selectedContact)
    : messages;

  // --- Handlers ---

  const handleDeleteMessages = async () => {
    if (selectedMessages.length === 0) return;
    setDeleting(true);
    try {
      for (const msgId of selectedMessages) {
        const msg = messages.find(m => m.id === msgId);
        if (msg) await api.deleteMessage(msgId, msg.direction);
      }
      setSelectedMessages([]);
      setDeleteMode(null);
      onRefresh();
      toast.success(`${selectedMessages.length} message(s) deleted`);
    } catch (err) {
      console.error('Delete error:', err);
      toast.error('Failed to delete messages');
    } finally {
      setDeleting(false);
    }
  };

  const handleHardDelete = async () => {
    if (!selectedContact) return;
    setShowHardDeleteModal(false);
    setDeleting(true);
    try {
      await api.hardDeleteContact(selectedContact);
      setSelectedContact('');
      setDeleteMode(null);
      onRefresh();
      toast.success('Contact permanently deleted');
    } catch (err) {
      console.error('Delete error:', err);
      toast.error('Failed to delete contact');
    } finally {
      setDeleting(false);
    }
  };

  const handleClearAllData = async () => {
    setShowClearAllModal(false);
    setDeleting(true);
    try {
      await api.clearAllInboxData();
      setDeleteMode(null);
      onRefresh();
      toast.success('All data cleared');
    } catch (err) {
      console.error('Clear all error:', err);
      toast.error('Failed to clear data');
    } finally {
      setDeleting(false);
    }
  };

  const loadCleanupPreview = useCallback(async () => {
    setCleanupLoading(true);
    setCleanupResults(null);
    try {
      const resources = await api.getCleanupPreview();
      setCleanupResources(resources && resources.length > 0 ? resources : CLEANUP_FALLBACK);
    } catch {
      setCleanupResources(CLEANUP_FALLBACK);
    } finally {
      setCleanupLoading(false);
    }
  }, []);

  const toggleCleanupItem = (id: string) => {
    setCleanupSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleCleanupCategory = (category: string) => {
    const items = cleanupResources.filter(r => r.category === category);
    const allSelected = items.every(r => cleanupSelected.has(r.id));
    setCleanupSelected(prev => {
      const next = new Set(prev);
      items.forEach(r => { if (allSelected) next.delete(r.id); else next.add(r.id); });
      return next;
    });
  };

  const selectAllCleanup = () => {
    if (cleanupSelected.size === cleanupResources.length) {
      setCleanupSelected(new Set());
    } else {
      setCleanupSelected(new Set(cleanupResources.map(r => r.id)));
    }
  };

  const executeSystemCleanup = async () => {
    setShowCleanupConfirm(false);
    setCleanupConfirmText('');
    setCleanupRunning(true);
    const selected = Array.from(cleanupSelected);
    try {
      const response = await api.executeCleanup(selected);
      if (response.results && response.results.length > 0) {
        setCleanupResults(response.results);
        setCleanupSelected(new Set());
        await loadCleanupPreview();
        onRefresh();
      }
    } catch {
      // Lambda not deployed — show error
      setCleanupResults(selected.map(id => ({
        id,
        label: CLEANUP_FALLBACK.find(r => r.id === id)?.label || id,
        deleted: 0,
        error: 'Cleanup endpoint not available',
      })));
    } finally {
      setCleanupRunning(false);
    }
  };


  // --- Confirmation Modal ---
  const ConfirmModal = ({ isOpen, title, message, confirmText = 'Confirm', confirmInput, onConfirm, onCancel }: {
    isOpen: boolean; title: string; message: React.ReactNode; confirmText?: string;
    confirmInput?: string; onConfirm: () => void; onCancel: () => void;
  }) => {
    const [inputValue, setInputValue] = React.useState('');
    React.useEffect(() => { if (!isOpen) setInputValue(''); }, [isOpen]);
    if (!isOpen) return null;
    const canConfirm = !confirmInput || inputValue === confirmInput;
    return (
      <div className="confirm-modal-overlay" onClick={onCancel}>
        <div className="confirm-modal" onClick={e => e.stopPropagation()}>
          <div className="confirm-modal-header"><h3>{title}</h3></div>
          <div className="confirm-modal-body">
            {message}
            {confirmInput && (
              <div className="confirm-input-wrapper">
                <label>Type &quot;{confirmInput}&quot; to confirm:</label>
                <input type="text" value={inputValue} onChange={e => setInputValue(e.target.value)} placeholder={confirmInput} autoFocus />
              </div>
            )}
          </div>
          <div className="confirm-modal-footer">
            <button className="confirm-modal-cancel" onClick={onCancel}>Cancel</button>
            <button className="confirm-modal-confirm" onClick={onConfirm} disabled={!canConfirm}>{confirmText}</button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Modals */}
      <ConfirmModal
        isOpen={showHardDeleteModal}
        title="Hard Delete Contact"
        message={
          <div>
            <p>This will permanently delete:</p>
            <ul style={{ margin: '8px 0 8px 20px', lineHeight: 1.6 }}>
              <li>Contact: {contacts.find(c => c.id === selectedContact)?.name || selectedContact}</li>
              <li>{contactMessages.length} messages</li>
              <li>{contactMessages.filter(m => m.s3Key).length} media files from S3</li>
            </ul>
            <p style={{ color: '#065f46', fontWeight: 500 }}>This action cannot be undone!</p>
          </div>
        }
        confirmInput="DELETE"
        confirmText="Hard Delete"
        onConfirm={handleHardDelete}
        onCancel={() => setShowHardDeleteModal(false)}
      />
      <ConfirmModal
        isOpen={showClearAllModal}
        title="Clear All Data"
        message={
          <div>
            <p style={{ color: '#065f46', fontWeight: 500, marginBottom: 12 }}>WARNING: This will permanently delete ALL data</p>
            <ul style={{ margin: '0 0 12px 20px', lineHeight: 1.6 }}>
              <li>All WhatsApp messages (inbound &amp; outbound)</li>
              <li>All SMS messages</li>
              <li>All Voice call records</li>
              <li>All {contacts.length} contacts</li>
              <li>All {messages.filter(m => m.s3Key).length} media files from S3</li>
            </ul>
            <p style={{ color: '#065f46', fontWeight: 500 }}>This action cannot be undone!</p>
          </div>
        }
        confirmInput="DELETE ALL"
        confirmText="Clear Everything"
        onConfirm={handleClearAllData}
        onCancel={() => setShowClearAllModal(false)}
      />

      <div className="data-tab">
        <h3>Factory Reset</h3>

        <div className="delete-options">
          <button className={deleteMode === 'messages' ? 'active' : ''} onClick={() => setDeleteMode(deleteMode === 'messages' ? null : 'messages')}>Delete Messages</button>
          <button className={deleteMode === 'hard' ? 'active' : ''} onClick={() => setDeleteMode(deleteMode === 'hard' ? null : 'hard')}>Hard Delete</button>
          <button className={deleteMode === 'clearAll' ? 'active' : ''} onClick={() => setDeleteMode(deleteMode === 'clearAll' ? null : 'clearAll')}>Clear All</button>
          <button className={deleteMode === 'systemCleanup' ? 'active' : ''} onClick={() => { setDeleteMode(deleteMode === 'systemCleanup' ? null : 'systemCleanup'); if (deleteMode !== 'systemCleanup') loadCleanupPreview(); }}>Cleanup</button>
        </div>

        {/* Delete Messages */}
        {deleteMode === 'messages' && (
          <div className="delete-panel">
            <div className="form-row">
              <label>Filter by Contact</label>
              <select value={selectedContact} onChange={e => setSelectedContact(e.target.value)}>
                <option value="">All contacts</option>
                {contacts.map(c => (<option key={c.id} value={c.id}>{c.name || c.phone}</option>))}
              </select>
            </div>
            <div className="msg-select-list">
              <div className="select-header">
                <span>{selectedMessages.length} selected</span>
                <button onClick={() => setSelectedMessages(selectedMessages.length === contactMessages.length ? [] : contactMessages.map(m => m.id))}>
                  {selectedMessages.length === contactMessages.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>
              {contactMessages.slice(0, 30).map(msg => (
                <label key={msg.id} className="msg-select-row">
                  <input type="checkbox" checked={selectedMessages.includes(msg.id)} onChange={() => setSelectedMessages(prev => prev.includes(msg.id) ? prev.filter(id => id !== msg.id) : [...prev, msg.id])} />
                  <span className="dir">{msg.direction === 'INBOUND' ? '↓' : '↑'}</span>
                  <span className="content">{msg.content?.slice(0, 40) || '[Media]'}</span>
                  <span className="time">{new Date(msg.timestamp).toLocaleDateString()}</span>
                </label>
              ))}
            </div>
            <div className="delete-actions">
              <Button variant="secondary" onClick={() => { setDeleteMode(null); setSelectedMessages([]); }}>Cancel</Button>
              <Button variant="danger" onClick={handleDeleteMessages} disabled={deleting || selectedMessages.length === 0} loading={deleting}>Delete {selectedMessages.length}</Button>
            </div>
          </div>
        )}

        {/* Hard Delete Contact */}
        {deleteMode === 'hard' && (
          <div className="delete-panel">
            <div className="warning">This will permanently delete the contact, all their messages, and media files.</div>
            <div className="form-row">
              <label>Select Contact</label>
              <select value={selectedContact} onChange={e => setSelectedContact(e.target.value)}>
                <option value="">Select...</option>
                {contacts.map(c => (<option key={c.id} value={c.id}>{c.name || c.phone}</option>))}
              </select>
            </div>
            {selectedContact && (
              <div className="preview">
                <p>Contact: {contacts.find(c => c.id === selectedContact)?.name || selectedContact}</p>
                <p>{contactMessages.length} messages, {contactMessages.filter(m => m.s3Key).length} media files</p>
              </div>
            )}
            <div className="delete-actions">
              <Button variant="secondary" onClick={() => { setDeleteMode(null); setSelectedContact(''); }}>Cancel</Button>
              <Button variant="danger" onClick={() => setShowHardDeleteModal(true)} disabled={deleting || !selectedContact} loading={deleting}>Hard Delete</Button>
            </div>
          </div>
        )}

        {/* Clear All */}
        {deleteMode === 'clearAll' && (
          <div className="delete-panel">
            <div className="warning">
              This will permanently delete ALL data including:
              <ul style={{ margin: '8px 0 0 16px', fontSize: '12px' }}>
                <li>All WhatsApp messages (inbound &amp; outbound)</li>
                <li>All SMS messages</li>
                <li>All Voice call records</li>
                <li>All contacts</li>
                <li>All media files from S3</li>
              </ul>
            </div>
            <div className="preview">
              <p>Total Contacts: {contacts.length}</p>
              <p>Total Messages: {messages.length}</p>
              <p>Media Files: {messages.filter(m => m.s3Key).length}</p>
            </div>
            <div className="delete-actions">
              <Button variant="secondary" onClick={() => setDeleteMode(null)}>Cancel</Button>
              <Button variant="danger" onClick={() => setShowClearAllModal(true)} disabled={deleting} loading={deleting}>Clear All Data</Button>
            </div>
          </div>
        )}


        {/* System Cleanup */}
        {deleteMode === 'systemCleanup' && (
          <div className="delete-panel">
            <div className="warning">Select specific resources to permanently delete. SystemConfig is always preserved.</div>
            {cleanupLoading && <p className="cleanup-loading">Loading resource counts...</p>}
            {!cleanupLoading && cleanupResources.length > 0 && (
              <>
                <div className="cleanup-header">
                  <label className="cleanup-select-all">
                    <input type="checkbox" checked={cleanupSelected.size === cleanupResources.length && cleanupResources.length > 0} onChange={selectAllCleanup} />
                    Select All
                  </label>
                  <span className="cleanup-count">{cleanupSelected.size} selected</span>
                </div>
                {Array.from(new Set(cleanupResources.map(r => r.category))).map(category => {
                  const items = cleanupResources.filter(r => r.category === category);
                  const allCatSelected = items.every(r => cleanupSelected.has(r.id));
                  const someCatSelected = items.some(r => cleanupSelected.has(r.id));
                  return (
                    <div key={category} className="cleanup-category">
                      <label className="cleanup-category-label">
                        <input type="checkbox" checked={allCatSelected} ref={el => { if (el) el.indeterminate = someCatSelected && !allCatSelected; }} onChange={() => toggleCleanupCategory(category)} />
                        {category}
                      </label>
                      {items.map(res => (
                        <label key={res.id} className="cleanup-item">
                          <input type="checkbox" checked={cleanupSelected.has(res.id)} onChange={() => toggleCleanupItem(res.id)} />
                          <span className="cleanup-item-label">{res.label}</span>
                          <span className={`cleanup-item-count ${res.count > 0 ? 'has-data' : ''}`}>{res.count === -1 ? '—' : res.count}</span>
                        </label>
                      ))}
                    </div>
                  );
                })}
              </>
            )}
            {cleanupResults && (
              <div className="cleanup-results">
                <p className="cleanup-results-title">Cleanup Complete</p>
                {cleanupResults.map(r => (
                  <div key={r.id} className="cleanup-result-row">
                    <span>{r.label}</span>
                    <span className={r.error ? 'cleanup-result-error' : 'cleanup-result-success'}>
                      {r.error ? `Error: ${r.error}` : `${r.deleted} deleted${r.elapsed ? ` (${r.elapsed}s)` : ''}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="delete-actions">
              <Button variant="secondary" onClick={() => { setDeleteMode(null); setCleanupResults(null); setCleanupSelected(new Set()); }}>Cancel</Button>
              <Button variant="secondary" onClick={loadCleanupPreview} disabled={cleanupLoading}>Refresh</Button>
              <Button variant="danger" onClick={() => setShowCleanupConfirm(true)} disabled={cleanupRunning || cleanupSelected.size === 0} loading={cleanupRunning}>
                Delete {cleanupSelected.size} Resource{cleanupSelected.size !== 1 ? 's' : ''}
              </Button>
            </div>
            {showCleanupConfirm && (
              <div className="cleanup-confirm">
                <p className="cleanup-confirm-text">Type <strong>CONFIRM DELETE</strong> to permanently delete {cleanupSelected.size} resource{cleanupSelected.size !== 1 ? 's' : ''}:</p>
                <ul className="cleanup-confirm-list">
                  {Array.from(cleanupSelected).map(id => {
                    const res = cleanupResources.find(r => r.id === id);
                    return <li key={id}>{res?.label || id}</li>;
                  })}
                </ul>
                <input type="text" value={cleanupConfirmText} onChange={e => setCleanupConfirmText(e.target.value)} placeholder="Type CONFIRM DELETE" />
                <div className="delete-actions">
                  <Button variant="secondary" onClick={() => { setShowCleanupConfirm(false); setCleanupConfirmText(''); }}>Cancel</Button>
                  <Button variant="danger" onClick={executeSystemCleanup} disabled={cleanupConfirmText !== 'CONFIRM DELETE'}>Permanently Delete</Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Default stats when no mode selected */}
        {!deleteMode && (
          <div className="stats-grid">
            <div className="stat-card"><div className="stat-value">{contacts.length}</div><div className="stat-label">Contacts</div></div>
            <div className="stat-card"><div className="stat-value">{messages.length}</div><div className="stat-label">Messages</div></div>
            <div className="stat-card"><div className="stat-value">{messages.filter(m => m.s3Key).length}</div><div className="stat-label">Media</div></div>
          </div>
        )}
      </div>
    </>
  );
};

export default DataTab;
