/**
 * SMS Mega Page - AWS Pinpoint + Airtel IN + Campaign
 * Uses PageShell for section header + scrollable tab bar
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import PageShell, { ShellTab } from '../../../components/PageShell';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import { useToastContext } from '../../../contexts/ToastContext';
import { useConfirm } from '../../../contexts/ConfirmContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
interface Contact { contactId: string; name: string; phone: string; }
interface SmsMessage { 
  messageId: string; contactId: string; contactName?: string; phone: string; 
  content: string; status: string; direction: string; messageType?: string;
  campaignId?: string; campaignName?: string; timestamp: string; 
}
interface Campaign { id: string; name: string; recipients: number; sent: number; delivered: number; failed: number; createdAt: string; }
interface AirtelMessage { messageId: string; phone: string; content: string; status: string; direction: string; templateId?: string; messageType?: string; apiVersion?: string; recipientCount?: number; providerMessageId?: string; timestamp: string; }
interface DLTTemplate { templateId: string; name: string; content: string; messageType: string; senderId: string; entityId: string; variables: string[]; status: string; createdAt: number; }
interface PinpointTemplate { templateName: string; body: string; templateDescription: string; defaultSubstitutions?: string; version?: string; creationDate?: string; lastModifiedDate?: string; tags?: Record<string, string>; }

const ITEMS_PER_PAGE = 25;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';

const TABS: ShellTab[] = [
  { id: 'aws', label: 'AWS Pinpoint' },
  { id: 'airtel', label: 'Airtel IN' },
  { id: 'campaign', label: 'Campaign' },
  { id: 'templates', label: 'DLT Templates' },
  { id: 'pinpoint-tpl', label: 'Pinpoint Templates' },
];

const SmsPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  // AWS Pinpoint state
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendPhone, setSendPhone] = useState('');
  const [sendContent, setSendContent] = useState('');
  const [sendMessageType, setSendMessageType] = useState('PROMOTIONAL');
  const [sending, setSending] = useState(false);
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [campaignName, setCampaignName] = useState('');
  const [campaignContent, setCampaignContent] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [campaignSending, setCampaignSending] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'single' | 'campaign' | 'airtel' | null>(null);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [clearing, setClearing] = useState(false);

  // Airtel IN state
  const [airtelMessages, setAirtelMessages] = useState<AirtelMessage[]>([]);
  const [airtelLoading, setAirtelLoading] = useState(false);
  const [airtelPage, setAirtelPage] = useState(1);
  const [airtelSearch, setAirtelSearch] = useState('');
  const [showAirtelSendModal, setShowAirtelSendModal] = useState(false);
  const [airtelPhone, setAirtelPhone] = useState('');
  const [airtelContent, setAirtelContent] = useState('');
  const [airtelSending, setAirtelSending] = useState(false);
  const [airtelMsgType, setAirtelMsgType] = useState('SERVICE_IMPLICIT');
  const [airtelApiVer, setAirtelApiVer] = useState('v5');
  const [airtelTemplateId, setAirtelTemplateId] = useState('');
  const [airtelBulk, setAirtelBulk] = useState(false);

  // DLT Templates state
  const [dltTemplates, setDltTemplates] = useState<DLTTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [tplId, setTplId] = useState('');
  const [tplName, setTplName] = useState('');
  const [tplContent, setTplContent] = useState('');
  const [tplMessageType, setTplMessageType] = useState('SERVICE_EXPLICIT');
  const [tplSaving, setTplSaving] = useState(false);
  // Edit template state
  const [editingTemplate, setEditingTemplate] = useState<DLTTemplate | null>(null);
  const [showEditTemplateModal, setShowEditTemplateModal] = useState(false);
  const [editTplName, setEditTplName] = useState('');
  const [editTplContent, setEditTplContent] = useState('');
  const [editTplMessageType, setEditTplMessageType] = useState('SERVICE_IMPLICIT');
  const [editTplSaving, setEditTplSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  // Pinpoint Templates state (ap-south-1 India)
  const [pinpointTemplates, setPinpointTemplates] = useState<PinpointTemplate[]>([]);
  const [pinpointTplLoading, setPinpointTplLoading] = useState(false);
  const [showPinpointTplModal, setShowPinpointTplModal] = useState(false);
  const [ppTplName, setPpTplName] = useState('');
  const [ppTplBody, setPpTplBody] = useState('');
  const [ppTplDesc, setPpTplDesc] = useState('');
  const [ppTplSaving, setPpTplSaving] = useState(false);
  const [showEditPpTplModal, setShowEditPpTplModal] = useState(false);
  const [editPpTpl, setEditPpTpl] = useState<PinpointTemplate | null>(null);
  const [editPpTplBody, setEditPpTplBody] = useState('');
  const [editPpTplDesc, setEditPpTplDesc] = useState('');
  const [editPpTplSaving, setEditPpTplSaving] = useState(false);

  const toast = useToastContext();
  const confirm = useConfirm();

  const loadContacts = useCallback(async () => {
    setLoadingContacts(true);
    try {
      const data = await api.listContacts();
      setContacts(data.filter(c => c.phone).map(c => ({ contactId: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '' })));
    } catch (err) { console.error('Load contacts error:', err); } finally { setLoadingContacts(false); }
  }, []);

  const loadAwsData = useCallback(async () => {
    setLoading(true);
    try {
      const [smsData, contactsData] = await Promise.all([api.listSmsAwsMessages(), api.listContacts()]);
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach(c => contactMap.set(c.contactId, c));
      let formatted: SmsMessage[];
      if (smsData.length > 0) {
        formatted = smsData.map(m => ({
          messageId: m.messageId, contactId: m.contactId, contactName: contactMap.get(m.contactId)?.name,
          phone: m.phoneNumber || contactMap.get(m.contactId)?.phone || '', content: m.content || '', status: m.status || 'unknown',
          direction: m.direction || 'OUTBOUND', messageType: m.messageType, campaignId: (m as any).campaignId,
          campaignName: (m as any).campaignName, timestamp: m.createdAt ? new Date(m.createdAt * 1000).toISOString() : new Date().toISOString()
        }));
      } else {
        const messagesData = await api.listMessages(undefined, 'SMS');
        formatted = messagesData.map(m => ({
          messageId: m.messageId, contactId: m.contactId, contactName: contactMap.get(m.contactId)?.name,
          phone: (m as any).phoneNumber || m.senderPhone || m.receivingPhone || contactMap.get(m.contactId)?.phone || '',
          content: m.content || '', status: m.status || 'unknown', direction: m.direction,
          messageType: (m as any).messageType, campaignId: (m as any).campaignId,
          campaignName: (m as any).campaignName, timestamp: m.timestamp
        }));
      }
      formatted.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setMessages(formatted);
      const campaignMap = new Map<string, Campaign>();
      formatted.filter(m => m.campaignId).forEach(m => {
        const cid = m.campaignId!;
        if (!campaignMap.has(cid)) campaignMap.set(cid, { id: cid, name: m.campaignName || cid, recipients: 0, sent: 0, delivered: 0, failed: 0, createdAt: m.timestamp });
        const c = campaignMap.get(cid)!; c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered') c.sent++;
        if (m.status === 'delivered') c.delivered++;
        if (m.status === 'failed') c.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) { console.error('Load error:', err); toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  const loadAirtelData = useCallback(async () => {
    setAirtelLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel`);
      const data = await res.json();
      const msgs = (data.messages || []).map((m: any) => ({
        messageId: m.messageId || m.id, phone: m.phone || m.phoneNumber || '', content: m.content || m.message || '',
        status: m.status || 'sent', direction: m.direction || 'OUTBOUND', templateId: m.templateId || m.dltTemplateId,
        messageType: m.messageType || '', apiVersion: m.apiVersion || '', recipientCount: m.recipientCount || 1,
        providerMessageId: m.providerMessageId || '',
        timestamp: m.timestamp || (m.createdAt ? new Date(m.createdAt * 1000).toISOString() : new Date().toISOString())
      }));
      msgs.sort((a: AirtelMessage, b: AirtelMessage) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setAirtelMessages(msgs);
    } catch (err) { console.error('Airtel load error:', err); } finally { setAirtelLoading(false); }
  }, []);

  useEffect(() => { loadAwsData(); loadAirtelData(); }, [loadAwsData, loadAirtelData]);
  useEffect(() => { setPage(1); setAirtelPage(1); }, [searchQuery, directionFilter, airtelSearch]);
  useEffect(() => { if (showContactPicker) loadContacts(); }, [showContactPicker, loadContacts]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(contactSearch.toLowerCase()) || c.phone.includes(contactSearch));
  const selectContact = (contact: Contact) => {
    if (showContactPicker === 'single') { setSendPhone(contact.phone); setShowContactPicker(null); }
    else if (showContactPicker === 'airtel') { setAirtelPhone(contact.phone); setShowContactPicker(null); }
    else if (showContactPicker === 'campaign' && !selectedContacts.includes(contact.contactId)) setSelectedContacts(prev => [...prev, contact.contactId]);
    setContactSearch('');
  };

  const handleSendSms = async () => {
    if (!sendPhone || !sendContent) { toast.error('Phone and message required'); return; }
    setSending(true);
    try {
      const result = await api.sendSmsAws({ phoneNumber: sendPhone, content: sendContent, messageType: sendMessageType as 'TRANSACTIONAL' | 'PROMOTIONAL' });
      if (result && (result.messageId || result.status === 'sent')) { toast.success('SMS sent!'); setShowSendModal(false); setSendPhone(''); setSendContent(''); await loadAwsData(); }
      else toast.error('Failed to send SMS');
    } catch (err) { toast.error('Failed to send SMS'); } finally { setSending(false); }
  };

  const handleSendAirtel = async () => {
    if (!airtelPhone || !airtelContent) { toast.error('Phone and message required'); return; }
    setAirtelSending(true);
    try {
      const phones = airtelPhone.split(',').map(p => p.trim()).filter(Boolean);
      const payload: any = {
        content: airtelContent,
        messageType: airtelMsgType,
        dltTemplateId: airtelTemplateId,
        apiVersion: airtelApiVer,
      };
      if (airtelBulk && phones.length > 1) {
        payload.bulk = true;
        payload.phoneNumbers = phones;
      } else if (phones.length > 1) {
        payload.phoneNumbers = phones;
      } else {
        payload.phoneNumber = phones[0];
      }
      const res = await fetch(`${API_BASE}/sms-in/airtel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success || data.messageId) { toast.success(`Airtel SMS sent to ${phones.length} recipient(s)`); setShowAirtelSendModal(false); setAirtelPhone(''); setAirtelContent(''); await loadAirtelData(); }
      else toast.error(data.error || 'Failed to send');
    } catch (err) { toast.error('Failed to send Airtel SMS'); } finally { setAirtelSending(false); }
  };

  const handleSendCampaign = async () => {
    if (!campaignName.trim() || !campaignContent.trim() || selectedContacts.length === 0) { toast.error('Campaign name, message, and contacts required'); return; }
    setCampaignSending(true);
    try {
      let sent = 0, failed = 0;
      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }
        try { const result = await api.sendSmsAws({ contactId, phoneNumber: contact.phone, content: campaignContent, messageType: 'PROMOTIONAL' }); if (result && result.messageId) sent++; else failed++; } catch { failed++; }
        if (sent % 10 === 0) await new Promise(r => setTimeout(r, 200));
      }
      toast.success(`Campaign sent: ${sent} success, ${failed} failed`);
      setShowCampaignModal(false); setCampaignName(''); setCampaignContent(''); setSelectedContacts([]); await loadAwsData();
    } catch (err) { toast.error('Campaign failed'); } finally { setCampaignSending(false); }
  };

  const handleClearLogs = async (type: 'aws' | 'airtel') => {
    if (!(await confirm(`Clear all ${type === 'aws' ? 'AWS' : 'Airtel'} SMS logs?`))) return;
    setClearing(true);
    try {
      const endpoint = type === 'aws' ? 'sms-aws/clear-logs' : 'sms-in/airtel/clear-logs';
      const method = 'DELETE';
      const res = await fetch(`${API_BASE}/${endpoint}`, { method, headers: { 'Content-Type': 'application/json' } });
      const result = await res.json();
      if (result.success) { toast.success(`Cleared logs`); type === 'aws' ? await loadAwsData() : await loadAirtelData(); }
      else toast.error(result.error || 'Failed');
    } catch (err) { toast.error('Failed to clear logs'); } finally { setClearing(false); }
  };

  // DLT Template functions
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel/templates`);
      const data = await res.json();
      setDltTemplates(data.templates || []);
    } catch (err) { console.error('Load templates error:', err); } finally { setTemplatesLoading(false); }
  }, []);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  // Auto-select first DLT template when templates load (no hardcoded default)
  useEffect(() => {
    if (dltTemplates.length > 0 && !airtelTemplateId) {
      setAirtelTemplateId(dltTemplates[0].templateId);
    }
  }, [dltTemplates, airtelTemplateId]);

  const handleCreateTemplate = async () => {
    if (!tplId || !tplContent) { toast.error('Template ID and content are required'); return; }
    setTplSaving(true);
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel/templates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templateId: tplId, name: tplName, content: tplContent, messageType: tplMessageType })
      });
      const data = await res.json();
      if (data.success) { toast.success('Template saved'); setShowTemplateModal(false); setTplId(''); setTplName(''); setTplContent(''); await loadTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to save template'); } finally { setTplSaving(false); }
  };

  const handleDeleteTemplate = async (templateId: string) => {
    if (!(await confirm(`Delete template ${templateId}?`))) return;
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel/templates?templateId=${templateId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) { toast.success('Template deleted'); await loadTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to delete template'); }
  };

  const handleEditTemplate = (tpl: DLTTemplate) => {
    setEditingTemplate(tpl);
    setEditTplName(tpl.name);
    setEditTplContent(tpl.content);
    setEditTplMessageType(tpl.messageType);
    setShowEditTemplateModal(true);
  };

  const handleUpdateTemplate = async () => {
    if (!editingTemplate) return;
    setEditTplSaving(true);
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel/templates`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templateId: editingTemplate.templateId, name: editTplName, content: editTplContent, messageType: editTplMessageType })
      });
      const data = await res.json();
      if (data.success) { toast.success('Template updated'); setShowEditTemplateModal(false); setEditingTemplate(null); await loadTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to update template'); } finally { setEditTplSaving(false); }
  };

  const handleSeedTemplates = async () => {
    setSeeding(true);
    try {
      const res = await fetch(`${API_BASE}/sms-in/airtel/templates?action=seed`);
      const data = await res.json();
      if (data.success) { toast.success(data.message || 'Templates seeded'); await loadTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to seed templates'); } finally { setSeeding(false); }
  };

  // Pinpoint Template functions (ap-south-1)
  const loadPinpointTemplates = useCallback(async () => {
    setPinpointTplLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sms-aws/templates`);
      const data = await res.json();
      setPinpointTemplates(data.templates || []);
    } catch (err) { console.error('Load Pinpoint templates error:', err); } finally { setPinpointTplLoading(false); }
  }, []);

  useEffect(() => { loadPinpointTemplates(); }, [loadPinpointTemplates]);

  const handleCreatePinpointTemplate = async () => {
    if (!ppTplName || !ppTplBody) { toast.error('Template name and body are required'); return; }
    setPpTplSaving(true);
    try {
      const res = await fetch(`${API_BASE}/sms-aws/templates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templateName: ppTplName, body: ppTplBody, templateDescription: ppTplDesc })
      });
      const data = await res.json();
      if (data.success) { toast.success('Pinpoint template created'); setShowPinpointTplModal(false); setPpTplName(''); setPpTplBody(''); setPpTplDesc(''); await loadPinpointTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to create template'); } finally { setPpTplSaving(false); }
  };

  const handleEditPinpointTemplate = (tpl: PinpointTemplate) => {
    setEditPpTpl(tpl);
    setEditPpTplBody(tpl.body);
    setEditPpTplDesc(tpl.templateDescription || '');
    setShowEditPpTplModal(true);
  };

  const handleUpdatePinpointTemplate = async () => {
    if (!editPpTpl) return;
    setEditPpTplSaving(true);
    try {
      const res = await fetch(`${API_BASE}/sms-aws/templates`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templateName: editPpTpl.templateName, body: editPpTplBody, templateDescription: editPpTplDesc })
      });
      const data = await res.json();
      if (data.success) { toast.success('Template updated'); setShowEditPpTplModal(false); setEditPpTpl(null); await loadPinpointTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to update template'); } finally { setEditPpTplSaving(false); }
  };

  const handleDeletePinpointTemplate = async (templateName: string) => {
    if (!(await confirm(`Delete Pinpoint template "${templateName}"?`))) return;
    try {
      const res = await fetch(`${API_BASE}/sms-aws/templates?templateName=${encodeURIComponent(templateName)}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) { toast.success('Template deleted'); await loadPinpointTemplates(); }
      else toast.error(data.error || 'Failed');
    } catch (err) { toast.error('Failed to delete template'); }
  };

  // AWS filtered
  const filteredMessages = messages.filter(msg => {
    if (directionFilter === 'inbound' && msg.direction !== 'INBOUND') return false;
    if (directionFilter === 'outbound' && msg.direction !== 'OUTBOUND') return false;
    if (searchQuery) { const q = searchQuery.toLowerCase(); return msg.contactName?.toLowerCase().includes(q) || msg.phone?.includes(q) || msg.content?.toLowerCase().includes(q); }
    return true;
  });
  const totalPages = Math.ceil(filteredMessages.length / ITEMS_PER_PAGE);
  const paginatedMessages = filteredMessages.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);
  const inboundCount = messages.filter(m => m.direction === 'INBOUND').length;
  const outboundCount = messages.filter(m => m.direction === 'OUTBOUND').length;

  // Airtel filtered
  const filteredAirtel = airtelMessages.filter(m => {
    if (airtelSearch) { const q = airtelSearch.toLowerCase(); return m.phone.includes(q) || m.content.toLowerCase().includes(q); }
    return true;
  });
  const airtelTotalPages = Math.ceil(filteredAirtel.length / ITEMS_PER_PAGE);
  const paginatedAirtel = filteredAirtel.slice((airtelPage - 1) * ITEMS_PER_PAGE, airtelPage * ITEMS_PER_PAGE);

  const shellContent = (
    <>
      <PageShell title="SMS" subtitle="AWS Pinpoint & Airtel IN � Send, Campaign, Logs" tabs={TABS} defaultTab="aws">
        {(activeTab) => (
          <>
            {/* ===== AWS PINPOINT TAB ===== */}
            {activeTab === 'aws' && (
              <div className="sms-tab-content">
                <div className="tab-header">
                  <div className="tab-header-left"><span className="provider-badge">AWS Pinpoint</span><span className="region-badge">us-east-1</span></div>
                  <div className="tab-header-actions">
                    <Button variant="primary" onClick={() => setShowSendModal(true)}>Send SMS</Button>
                    <Button variant="secondary" onClick={() => handleClearLogs('aws')} disabled={clearing} loading={clearing}>Clear</Button>
                    <Button variant="secondary" icon="refresh" onClick={loadAwsData} disabled={loading} loading={loading}>Refresh</Button>
                  </div>
                </div>
                <div className="controls-row">
                  <div className="filter-tabs">
                    <button className={directionFilter === 'all' ? 'active' : ''} onClick={() => setDirectionFilter('all')}>All ({messages.length})</button>
                    <button className={directionFilter === 'inbound' ? 'active' : ''} onClick={() => setDirectionFilter('inbound')}>? In ({inboundCount})</button>
                    <button className={directionFilter === 'outbound' ? 'active' : ''} onClick={() => setDirectionFilter('outbound')}>? Out ({outboundCount})</button>
                  </div>
                  <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="sms-search" />
                  <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
                </div>
                <div className="table-area">{loading ? <div className="loading-state">Loading...</div> : (
                  <table><thead><tr><th>Time</th><th>Dir</th><th>Contact</th><th className="hide-mobile">Phone</th><th>Message</th><th>Status</th></tr></thead><tbody>
                    {paginatedMessages.map(msg => (<tr key={msg.messageId}><td className="time-cell">{new Date(msg.timestamp).toLocaleString()}</td><td><span className={msg.direction === 'INBOUND' ? 'dir-in' : 'dir-out'}>{msg.direction === 'INBOUND' ? '?' : '?'}</span></td><td>{msg.contactName || '-'}</td><td className="phone-cell hide-mobile">{msg.phone}</td><td className="content-cell" title={msg.content}>{msg.content?.substring(0, 40)}{msg.content?.length > 40 ? '...' : ''}</td><td><span className={`st-badge ${msg.status?.toLowerCase()}`}>{msg.status}</span></td></tr>))}
                    {paginatedMessages.length === 0 && <tr><td colSpan={6} className="empty-row">No messages</td></tr>}
                  </tbody></table>
                )}</div>
              </div>
            )}

            {/* ===== AIRTEL IN TAB ===== */}
            {activeTab === 'airtel' && (
              <div className="sms-tab-content">
                <div className="tab-header">
                  <div className="tab-header-left"><span className="provider-badge airtel">Airtel IN</span><span className="region-badge">India</span></div>
                  <div className="tab-header-actions">
                    <Button variant="primary" onClick={() => setShowAirtelSendModal(true)}>Send SMS</Button>
                    <Button variant="secondary" onClick={() => handleClearLogs('airtel')} disabled={clearing} loading={clearing}>Clear</Button>
                    <Button variant="secondary" icon="refresh" onClick={loadAirtelData} disabled={airtelLoading} loading={airtelLoading}>Refresh</Button>
                  </div>
                </div>
                <div className="controls-row">
                  <input type="text" placeholder="Search..." value={airtelSearch} onChange={e => setAirtelSearch(e.target.value)} className="sms-search" />
                  <Pagination currentPage={airtelPage} totalPages={airtelTotalPages} onPageChange={setAirtelPage} />
                </div>
                <div className="table-area">{airtelLoading ? <div className="loading-state">Loading...</div> : (
                  <table><thead><tr><th>Time</th><th>Dir</th><th>Phone</th><th>Message</th><th className="hide-mobile">Type</th><th className="hide-mobile">API</th><th>Status</th></tr></thead><tbody>
                    {paginatedAirtel.map(msg => (<tr key={msg.messageId}><td className="time-cell">{new Date(msg.timestamp).toLocaleString()}</td><td><span className={msg.direction === 'INBOUND' ? 'dir-in' : 'dir-out'}>{msg.direction === 'INBOUND' ? '↓' : '↑'}</span></td><td className="phone-cell">{msg.phone}{msg.recipientCount && msg.recipientCount > 1 ? ` (+${msg.recipientCount - 1})` : ''}</td><td className="content-cell" title={msg.content}>{msg.content?.substring(0, 50)}{msg.content?.length > 50 ? '...' : ''}</td><td className="hide-mobile"><span className="st-badge">{msg.messageType || '-'}</span></td><td className="hide-mobile">{msg.apiVersion || '-'}</td><td><span className={`st-badge ${msg.status?.toLowerCase()}`}>{msg.status}</span></td></tr>))}
                    {paginatedAirtel.length === 0 && <tr><td colSpan={7} className="empty-row">No Airtel messages</td></tr>}
                  </tbody></table>
                )}</div>
              </div>
            )}

            {/* ===== CAMPAIGN TAB ===== */}
            {activeTab === 'campaign' && (
              <div className="sms-tab-content">
                <div className="tab-header">
                  <div className="tab-header-left"><span className="provider-badge">SMS Campaigns</span></div>
                  <div className="tab-header-actions">
                    <Button variant="primary" onClick={() => { setShowCampaignModal(true); loadContacts(); }}>New Campaign</Button>
                  </div>
                </div>
                <div className="table-area">
                  <table><thead><tr><th>Campaign</th><th>Recipients</th><th>Sent</th><th>Delivered</th><th>Failed</th><th>Date</th></tr></thead><tbody>
                    {campaigns.map(c => (<tr key={c.id}><td className="name-cell">{c.name}</td><td>{c.recipients}</td><td className="success-cell">{c.sent}</td><td>{c.delivered}</td><td className="failed-cell">{c.failed}</td><td className="time-cell">{new Date(c.createdAt).toLocaleDateString()}</td></tr>))}
                    {campaigns.length === 0 && <tr><td colSpan={6} className="empty-row">No campaigns yet</td></tr>}
                  </tbody></table>
                </div>
              </div>
            )}

            {/* ===== DLT TEMPLATES TAB ===== */}
            {activeTab === 'templates' && (
              <div className="sms-tab-content">
                <div className="tab-header">
                  <div className="tab-header-left"><span className="provider-badge airtel">DLT Templates</span><span className="region-badge">Airtel IQ</span></div>
                  <div className="tab-header-actions">
                    <Button variant="primary" onClick={() => setShowTemplateModal(true)}>Add Template</Button>
                    <Button variant="secondary" onClick={handleSeedTemplates} disabled={seeding} loading={seeding}>Seed Defaults</Button>
                    <Button variant="secondary" icon="refresh" onClick={loadTemplates} disabled={templatesLoading} loading={templatesLoading}>Refresh</Button>
                  </div>
                </div>
                <div className="table-area">{templatesLoading ? <div className="loading-state">Loading...</div> : (
                  <table><thead><tr><th>Template ID</th><th>Name</th><th>Content</th><th>Type</th><th>Sender</th><th>Actions</th></tr></thead><tbody>
                    {dltTemplates.map(tpl => (<tr key={tpl.templateId}><td className="phone-cell">{tpl.templateId}</td><td className="name-cell">{tpl.name}</td><td className="content-cell" title={tpl.content}>{tpl.content?.substring(0, 60)}{tpl.content?.length > 60 ? '...' : ''}</td><td><span className="st-badge">{tpl.messageType}</span></td><td>{tpl.senderId}</td><td><button className="pick-btn" onClick={() => handleEditTemplate(tpl)}>Edit</button> <button className="pick-btn" onClick={() => handleDeleteTemplate(tpl.templateId)}>Delete</button></td></tr>))}
                    {dltTemplates.length === 0 && <tr><td colSpan={6} className="empty-row">No DLT templates. Click "Add Template" to register one, or "Seed Defaults" to add WA-Alert + ivr-default.</td></tr>}
                  </tbody></table>
                )}</div>
                <div style={{ padding: '12px', background: '#f9fafb', borderTop: '1px solid #f3f4f6', fontSize: '12px', color: '#6b7280' }}>
                  {dltTemplates.length} template(s) registered · PE ID: <code>1201161991108627443</code> · Sender: <code>WDBEEP</code> · Templates are managed in the DLT Templates tab
                </div>
              </div>
            )}

            {/* ===== PINPOINT TEMPLATES TAB (ap-south-1) ===== */}
            {activeTab === 'pinpoint-tpl' && (
              <div className="sms-tab-content">
                <div className="tab-header">
                  <div className="tab-header-left"><span className="provider-badge">Pinpoint Templates</span><span className="region-badge">ap-south-1 (India)</span></div>
                  <div className="tab-header-actions">
                    <Button variant="primary" onClick={() => setShowPinpointTplModal(true)}>Create Template</Button>
                    <Button variant="secondary" icon="refresh" onClick={loadPinpointTemplates} disabled={pinpointTplLoading} loading={pinpointTplLoading}>Refresh</Button>
                  </div>
                </div>
                <div className="table-area">{pinpointTplLoading ? <div className="loading-state">Loading...</div> : (
                  <table><thead><tr><th>Template Name</th><th>Body</th><th>Description</th><th>Version</th><th>Last Modified</th><th>Actions</th></tr></thead><tbody>
                    {pinpointTemplates.map(tpl => (<tr key={tpl.templateName}><td className="name-cell">{tpl.templateName}</td><td className="content-cell" title={tpl.body}>{tpl.body?.substring(0, 60)}{tpl.body?.length > 60 ? '...' : ''}</td><td>{tpl.templateDescription || '-'}</td><td>{tpl.version || '-'}</td><td className="time-cell">{tpl.lastModifiedDate ? new Date(tpl.lastModifiedDate).toLocaleString() : '-'}</td><td><button className="pick-btn" onClick={() => handleEditPinpointTemplate(tpl)}>Edit</button> <button className="pick-btn" onClick={() => handleDeletePinpointTemplate(tpl.templateName)}>Delete</button></td></tr>))}
                    {pinpointTemplates.length === 0 && <tr><td colSpan={6} className="empty-row">No Pinpoint SMS templates in ap-south-1. Click "Create Template" to add one.</td></tr>}
                  </tbody></table>
                )}</div>
                <div style={{ padding: '12px', background: '#f9fafb', borderTop: '1px solid #f3f4f6', fontSize: '12px', color: '#6b7280' }}>
                  {pinpointTemplates.length} template(s) · Region: <code>ap-south-1</code> · Sender ID: <code>WDBEEP</code> · India DLT compliant
                </div>
              </div>
            )}

            {/* ===== MODALS ===== */}
            {showSendModal && (<div className="modal-overlay" onClick={() => setShowSendModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Send SMS (AWS)</h3>
              <div className="form-group"><label>Phone *</label><div className="input-row"><input type="tel" value={sendPhone} onChange={e => setSendPhone(e.target.value)} placeholder="+1234567890" /><button type="button" className="pick-btn" onClick={() => setShowContactPicker('single')}>Contacts</button></div></div>
              <div className="form-group"><label>Message *</label><textarea value={sendContent} onChange={e => setSendContent(e.target.value)} placeholder="Enter message..." rows={3} /></div>
              <div className="form-group"><label>Type</label><select value={sendMessageType} onChange={e => setSendMessageType(e.target.value)}><option value="PROMOTIONAL">Promotional</option><option value="TRANSACTIONAL">Transactional</option></select></div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowSendModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendSms} loading={sending} disabled={!sendPhone || !sendContent}>Send</Button></div>
            </div></div>)}

            {showAirtelSendModal && (<div className="modal-overlay" onClick={() => setShowAirtelSendModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Send SMS (Airtel IQ)</h3>
              <div className="form-group"><label>Phone(s) * <span style={{fontSize:'11px',color:'#9ca3af'}}>comma-separated for multiple</span></label><div className="input-row"><input type="tel" value={airtelPhone} onChange={e => setAirtelPhone(e.target.value)} placeholder="8130078559, 9876543210" /><button type="button" className="pick-btn" onClick={() => setShowContactPicker('airtel')}>Contacts</button></div></div>
              <div className="form-group"><label>Message *</label><textarea value={airtelContent} onChange={e => setAirtelContent(e.target.value)} placeholder="Enter message..." rows={3} /></div>
              <div className="form-row">
                <div className="form-group half"><label>Message Type</label><select value={airtelMsgType} onChange={e => setAirtelMsgType(e.target.value)}><option value="SERVICE_IMPLICIT">SERVICE_IMPLICIT</option><option value="SERVICE_EXPLICIT">SERVICE_EXPLICIT</option><option value="TRANSACTIONAL">TRANSACTIONAL</option><option value="PROMOTIONAL">PROMOTIONAL</option></select></div>
                <div className="form-group half"><label>API Version</label><select value={airtelApiVer} onChange={e => setAirtelApiVer(e.target.value)}><option value="v4">v4 (Standard)</option><option value="v5">v5 (Content Mod)</option><option value="v6">v6 (Enhanced)</option></select></div>
              </div>
              <div className="form-group"><label>DLT Template</label><div className="input-row">{dltTemplates.length > 0 ? <select value={airtelTemplateId} onChange={e => { const t = dltTemplates.find(x => x.templateId === e.target.value); if (t) { setAirtelTemplateId(t.templateId); setAirtelContent(t.content); setAirtelMsgType(t.messageType); } else { setAirtelTemplateId(e.target.value); }}}>{dltTemplates.map(t => <option key={t.templateId} value={t.templateId}>{t.name || t.templateId.slice(0,16)} ({t.messageType})</option>)}<option value="">Custom...</option></select> : <input type="text" value={airtelTemplateId} onChange={e => setAirtelTemplateId(e.target.value)} placeholder="Add templates in DLT Templates tab" />}{!airtelTemplateId && <span style={{fontSize:'11px',color:'#ef4444'}}>Required for v4/v6</span>}</div></div>
              {airtelPhone.includes(',') && <div className="form-group"><label className="checkbox-label"><input type="checkbox" checked={airtelBulk} onChange={e => setAirtelBulk(e.target.checked)} /> Use Bulk/Conduit API <span style={{fontSize:'11px',color:'#9ca3af'}}>(per-recipient payload)</span></label></div>}
              <div style={{padding:'8px 0',fontSize:'11px',color:'#9ca3af'}}>Sender: WDBEEP · PE ID: 1201161991108627443{airtelMsgType === 'PROMOTIONAL' ? ' · No DLR for promotional' : ''}</div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowAirtelSendModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendAirtel} loading={airtelSending} disabled={!airtelPhone || !airtelContent}>Send{airtelPhone.includes(',') ? ` to ${airtelPhone.split(',').filter(Boolean).length}` : ''}</Button></div>
            </div></div>)}

            {showCampaignModal && (<div className="modal-overlay" onClick={() => setShowCampaignModal(false)}><div className="modal-content campaign-modal" onClick={e => e.stopPropagation()}>
              <h3>Create SMS Campaign</h3>
              <div className="form-group"><label>Name *</label><input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My Campaign" /></div>
              <div className="form-group"><label>Message *</label><textarea value={campaignContent} onChange={e => setCampaignContent(e.target.value)} placeholder="Enter message..." rows={3} /></div>
              <div className="form-group"><label>Recipients ({selectedContacts.length})</label><button type="button" className="pick-btn full-w" onClick={() => setShowContactPicker('campaign')}>Select Contacts</button>
                {selectedContacts.length > 0 && (<div className="tags">{selectedContacts.map(id => { const c = contacts.find(x => x.contactId === id); return c ? <span key={id} className="tag">{c.name} <button onClick={() => setSelectedContacts(prev => prev.filter(x => x !== id))}>�</button></span> : null; })}</div>)}
              </div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowCampaignModal(false)}>Cancel</Button><Button variant="primary" onClick={handleSendCampaign} loading={campaignSending} disabled={!campaignName || !campaignContent || selectedContacts.length === 0}>Send to {selectedContacts.length}</Button></div>
            </div></div>)}

            {showTemplateModal && (<div className="modal-overlay" onClick={() => setShowTemplateModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Add DLT Template</h3>
              <div className="form-group"><label>Template ID (DLT) *</label><input type="text" value={tplId} onChange={e => setTplId(e.target.value)} placeholder="DLT Template ID from portal" /></div>
              <div className="form-group"><label>Name</label><input type="text" value={tplName} onChange={e => setTplName(e.target.value)} placeholder="e.g. Self-Service IVR" /></div>
              <div className="form-group"><label>Content *</label><textarea value={tplContent} onChange={e => setTplContent(e.target.value)} placeholder="Template text with {#var#} placeholders" rows={4} /></div>
              <div className="form-group"><label>Message Type</label><select value={tplMessageType} onChange={e => setTplMessageType(e.target.value)}><option value="SERVICE_EXPLICIT">SERVICE_EXPLICIT</option><option value="SERVICE_IMPLICIT">SERVICE_IMPLICIT</option><option value="TRANSACTIONAL">TRANSACTIONAL</option><option value="PROMOTIONAL">PROMOTIONAL</option></select></div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowTemplateModal(false)}>Cancel</Button><Button variant="primary" onClick={handleCreateTemplate} loading={tplSaving} disabled={!tplId || !tplContent}>Save</Button></div>
            </div></div>)}

            {/* Edit DLT Template Modal */}
            {showEditTemplateModal && editingTemplate && (<div className="modal-overlay" onClick={() => setShowEditTemplateModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Edit DLT Template</h3>
              <div className="form-group"><label>Template ID</label><input type="text" value={editingTemplate.templateId} disabled style={{ background: '#f3f4f6' }} /></div>
              <div className="form-group"><label>Name</label><input type="text" value={editTplName} onChange={e => setEditTplName(e.target.value)} /></div>
              <div className="form-group"><label>Content *</label><textarea value={editTplContent} onChange={e => setEditTplContent(e.target.value)} rows={4} /></div>
              <div className="form-group"><label>Message Type</label><select value={editTplMessageType} onChange={e => setEditTplMessageType(e.target.value)}><option value="SERVICE_EXPLICIT">SERVICE_EXPLICIT</option><option value="SERVICE_IMPLICIT">SERVICE_IMPLICIT</option><option value="TRANSACTIONAL">TRANSACTIONAL</option><option value="PROMOTIONAL">PROMOTIONAL</option></select></div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowEditTemplateModal(false)}>Cancel</Button><Button variant="primary" onClick={handleUpdateTemplate} loading={editTplSaving} disabled={!editTplContent}>Update</Button></div>
            </div></div>)}

            {/* Create Pinpoint Template Modal */}
            {showPinpointTplModal && (<div className="modal-overlay" onClick={() => setShowPinpointTplModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Create Pinpoint SMS Template</h3>
              <div className="form-group"><label>Template Name *</label><input type="text" value={ppTplName} onChange={e => setPpTplName(e.target.value)} placeholder="e.g. wa-alert-india" /></div>
              <div className="form-group"><label>Body *</label><textarea value={ppTplBody} onChange={e => setPpTplBody(e.target.value)} placeholder="SMS template body text..." rows={4} /></div>
              <div className="form-group"><label>Description</label><input type="text" value={ppTplDesc} onChange={e => setPpTplDesc(e.target.value)} placeholder="Optional description" /></div>
              <div style={{padding:'8px 0',fontSize:'11px',color:'#9ca3af'}}>Region: ap-south-1 · Sender ID: WDBEEP</div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowPinpointTplModal(false)}>Cancel</Button><Button variant="primary" onClick={handleCreatePinpointTemplate} loading={ppTplSaving} disabled={!ppTplName || !ppTplBody}>Create</Button></div>
            </div></div>)}

            {/* Edit Pinpoint Template Modal */}
            {showEditPpTplModal && editPpTpl && (<div className="modal-overlay" onClick={() => setShowEditPpTplModal(false)}><div className="modal-content" onClick={e => e.stopPropagation()}>
              <h3>Edit Pinpoint Template</h3>
              <div className="form-group"><label>Template Name</label><input type="text" value={editPpTpl.templateName} disabled style={{ background: '#f3f4f6' }} /></div>
              <div className="form-group"><label>Body *</label><textarea value={editPpTplBody} onChange={e => setEditPpTplBody(e.target.value)} rows={4} /></div>
              <div className="form-group"><label>Description</label><input type="text" value={editPpTplDesc} onChange={e => setEditPpTplDesc(e.target.value)} /></div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowEditPpTplModal(false)}>Cancel</Button><Button variant="primary" onClick={handleUpdatePinpointTemplate} loading={editPpTplSaving} disabled={!editPpTplBody}>Update</Button></div>
            </div></div>)}

            {showContactPicker && (<div className="modal-overlay" onClick={() => setShowContactPicker(null)}><div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
              <h3>Select Contact{showContactPicker === 'campaign' ? 's' : ''}</h3>
              <input type="text" placeholder="Search..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
              <div className="contact-list">{loadingContacts ? <div className="loading-state">Loading...</div> : filteredContacts.length === 0 ? <div className="loading-state">No contacts</div> : (
                filteredContacts.slice(0, 50).map(contact => (<div key={contact.contactId} className={`contact-row ${selectedContacts.includes(contact.contactId) ? 'selected' : ''}`} onClick={() => selectContact(contact)}><div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div><div className="contact-details"><div className="c-name">{contact.name}</div><div className="c-phone">{contact.phone}</div></div>{showContactPicker === 'campaign' && selectedContacts.includes(contact.contactId) && <span className="check">?</span>}</div>))
              )}</div>
              <div className="modal-actions"><Button variant="secondary" onClick={() => setShowContactPicker(null)}>{showContactPicker === 'campaign' ? 'Done' : 'Cancel'}</Button></div>
            </div></div>)}
          </>
        )}
      </PageShell>

      <style jsx>{`
        .sms-tab-content { padding: 0; }
        .tab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }
        .tab-header-left { display: flex; align-items: center; gap: 8px; }
        .tab-header-actions { display: flex; gap: 6px; flex-wrap: wrap; }
        .provider-badge { background: #1a3a2a; color: #fff; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; }
        .provider-badge.airtel { background: #1a3a2a; }
        .region-badge { background: #f3f4f6; color: #6b7280; padding: 3px 8px; border-radius: 4px; font-size: 10px; }
        .controls-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 10px; flex-wrap: wrap; }
        .filter-tabs { display: flex; gap: 4px; }
        .filter-tabs button { padding: 6px 12px; border: 1px solid #e5e7eb; background: #fff; border-radius: 6px; cursor: pointer; font-size: 12px; min-height: 44px; }
        .filter-tabs button.active { background: #d1f470; color: #1a3a2a; border-color: #1a3a2a; }
        .sms-search { padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; width: 200px; max-width: 100%; font-size: 16px; min-height: 44px; box-sizing: border-box; }
        .sms-search:focus { outline: none; border-color: #1a3a2a; box-shadow: 0 0 0 3px rgba(209,244,112,0.3); }
        .table-area { background: #fff; border-radius: 12px; border: 1px solid #e5e7eb; overflow: auto; }
        .loading-state { padding: 40px; text-align: center; color: #6b7280; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #f3f4f6; font-size: 12px; white-space: nowrap; }
        th { background: #f9fafb; font-weight: 600; color: #374151; position: sticky; top: 0; z-index: 1; }
        tr:hover { background: #f9fafb; }
        .time-cell { font-size: 11px; color: #6b7280; }
        .phone-cell { font-family: monospace; color: #1a3a2a; font-size: 11px; }
        .content-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
        .name-cell { font-weight: 500; color: #111827; }
        .success-cell { color: #1a3a2a; font-weight: 500; }
        .failed-cell { color: #1a3a2a; font-weight: 500; }
        .dir-in { background: #1a3a2a; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .dir-out { background: #6b7280; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
        .st-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; background: #f1f5f9; color: #6b7280; }
        .st-badge.sent, .st-badge.delivered { background: #f9fafb; color: #1a3a2a; }
        .st-badge.failed { background: #f9fafb; color: #1a3a2a; }
        .empty-row { text-align: center; color: #6b7280; padding: 30px !important; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
        .modal-content { background: #fff; border-radius: 12px; padding: 20px; width: 100%; max-width: 420px; max-height: 90vh; overflow-y: auto; }
        .modal-content.campaign-modal { max-width: 480px; }
        .modal-content h3 { margin: 0 0 16px 0; color: #111827; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 5px; color: #374151; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: #1a3a2a; }
        .input-row { display: flex; gap: 6px; }
        .input-row input { flex: 1; }
        .form-row { display: flex; gap: 10px; }
        .form-group.half { flex: 1; }
        .checkbox-label { display: flex !important; align-items: center; gap: 6px; cursor: pointer; }
        .checkbox-label input[type="checkbox"] { width: auto; margin: 0; }
        .pick-btn { padding: 8px 12px; background: #f9fafb; border: 1px solid #1a3a2a; border-radius: 8px; color: #0f2a1d; font-size: 12px; cursor: pointer; }
        .pick-btn:hover { background: #f9fafb; }
        .pick-btn.full-w { width: 100%; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
        .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: #f3f4f6; border-radius: 4px; font-size: 11px; }
        .tag button { background: none; border: none; cursor: pointer; font-size: 14px; padding: 0; }
        .contact-picker { max-width: 360px; }
        .contact-search { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; margin-bottom: 10px; box-sizing: border-box; }
        .contact-list { max-height: 280px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
        .contact-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #f3f4f6; min-height: 44px; }
        .contact-row:hover { background: #f9fafb; }
        .contact-row.selected { background: #f9fafb; }
        .contact-avatar { width: 36px; height: 36px; background: #1a3a2a; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; flex-shrink: 0; }
        .contact-details { flex: 1; }
        .c-name { font-size: 13px; font-weight: 500; color: #111827; }
        .c-phone { font-size: 11px; color: #6b7280; font-family: monospace; }
        .check { color: #1a3a2a; font-weight: bold; }
        @media (max-width: 768px) {
          .tab-header { flex-direction: column; align-items: flex-start; }
          .controls-row { flex-direction: column; align-items: stretch; }
          .sms-search { width: 100%; }
          .filter-tabs { flex-wrap: wrap; }
          .modal-overlay { align-items: flex-end; padding: 0; }
          .modal-content { max-width: 100%; border-radius: 16px 16px 0 0; max-height: 85vh; }
          .modal-content.campaign-modal { max-width: 100%; }
          .contact-picker { max-width: 100%; }
          .modal-actions { flex-direction: column; }
          .modal-actions button { width: 100%; }
          .hide-mobile { display: none; }
          th, td { padding: 8px 10px; font-size: 11px; }
        }
        @media (max-width: 480px) {
          .tab-header-actions { width: 100%; }
          .tab-header-actions button { flex: 1; }
          .filter-tabs { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; flex-wrap: nowrap; }
          .filter-tabs button { flex-shrink: 0; }
        }
      `}</style>
    </>
  );

  if (embedded) return shellContent;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS" description="SMS — AWS Pinpoint & Airtel" />
      {shellContent}
    </Layout>
  );
};

export default SmsPage;
