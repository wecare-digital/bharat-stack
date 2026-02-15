/**
 * RCS Campaign Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { API_BASE } from '../../../config/constants';
import Button from '../../../components/ui/Button';
import Tabs, { TabItem } from '../../../components/ui/Tabs';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
type TabType = 'create' | 'logs';
interface CampaignLog { id: string; name: string; recipients: number; sent: number; delivered: number; read: number; failed: number; status: string; createdAt: string; }

const tabItems: TabItem[] = [
  { id: 'create', label: 'Create Campaign' },
  { id: 'logs', label: 'Campaign Logs' },
];

const RcsCampaignPage: React.FC<PageProps> = ({ signOut, user, embedded }) => {
  const [activeTab, setActiveTab] = useState<TabType>('create');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const toast = useToastContext();
  const [campaignName, setCampaignName] = useState('');
  const [messageContent, setMessageContent] = useState('');
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const contactsData = await api.listContacts();
      setContacts(contactsData.filter(c => c.phone));
      const messages = await api.listMessages(undefined, 'RCS');
      const campaignMsgs = messages.filter(m => (m as any).campaignId);
      const campaignMap = new Map<string, CampaignLog>();
      campaignMsgs.forEach(m => {
        const cid = (m as any).campaignId;
        if (!campaignMap.has(cid)) { campaignMap.set(cid, { id: cid, name: (m as any).campaignName || cid, recipients: 0, sent: 0, delivered: 0, read: 0, failed: 0, status: 'completed', createdAt: m.timestamp }); }
        const c = campaignMap.get(cid)!; c.recipients++;
        if (m.status === 'sent' || m.status === 'delivered' || m.status === 'read') c.sent++;
        if (m.status === 'delivered' || m.status === 'read') c.delivered++;
        if (m.status === 'read') c.read++;
        if (m.status === 'failed') c.failed++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) { toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);


  useEffect(() => { loadData(); }, [loadData]);

  const filteredContacts = contacts.filter(c => c.name?.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone?.includes(searchQuery));

  const handleSelectAll = () => {
    if (selectAll) { setSelectedContacts([]); } else { setSelectedContacts(filteredContacts.map(c => c.contactId)); }
    setSelectAll(!selectAll);
  };

  const toggleContact = (id: string) => { setSelectedContacts(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]); };

  const handleSendCampaign = async () => {
    if (!campaignName.trim()) { setMessage({ type: 'error', text: 'Campaign name required' }); return; }
    if (!messageContent.trim()) { setMessage({ type: 'error', text: 'Message content required' }); return; }
    if (selectedContacts.length === 0) { setMessage({ type: 'error', text: 'Select at least one contact' }); return; }
    setSending(true); setMessage(null);
    try {
      const campaignId = 'RC' + Date.now();
      let sent = 0, failed = 0;
      for (const contactId of selectedContacts) {
        const contact = contacts.find(c => c.contactId === contactId);
        if (!contact?.phone) { failed++; continue; }
        try {
          const response = await fetch(`${API_BASE}/rcs/send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ contactId, content: messageContent, campaignId, campaignName }) });
          if (response.ok) sent++; else failed++;
        } catch (e) { failed++; }
        if (sent % 10 === 0) await new Promise(r => setTimeout(r, 200));
      }
      setMessage({ type: sent > 0 ? 'success' : 'error', text: `Campaign sent: ${sent} success, ${failed} failed` });
      setCampaignName(''); setMessageContent(''); setSelectedContacts([]); setSelectAll(false); loadData();
    } catch (err: any) { setMessage({ type: 'error', text: err.message || 'Campaign failed' }); } finally { setSending(false); }
  };

  const content = (
      <div className="inner-page campaign-page">
        <div className="page-header"><h2>RCS Campaign</h2><Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} /></div>
        <Tabs items={tabItems.map(t => ({ ...t, count: t.id === 'logs' ? campaigns.length : undefined }))} activeTab={activeTab} onChange={(id) => setActiveTab(id as TabType)} variant="sub" />
        {message && <div className={'alert alert-' + message.type}>{message.text}<button onClick={() => setMessage(null)}>×</button></div>}
        {activeTab === 'create' && (
          <div className="form-section">
            <div className="form-group"><label>Campaign Name *</label><input type="text" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="My RCS Campaign" /></div>
            <div className="form-group"><label>Message Content *</label><textarea value={messageContent} onChange={e => setMessageContent(e.target.value)} placeholder="Enter your RCS message..." rows={4} /></div>
            <div className="contacts-section">
              <div className="contacts-header"><h3>Select Recipients ({selectedContacts.length} / {filteredContacts.length})</h3><div className="contacts-actions"><input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} /><button onClick={handleSelectAll}>{selectAll ? 'Deselect All' : 'Select All'}</button></div></div>
              <div className="contacts-grid">
                {filteredContacts.slice(0, 100).map(c => (<label key={c.contactId} className={'contact-item' + (selectedContacts.includes(c.contactId) ? ' selected' : '')}><input type="checkbox" checked={selectedContacts.includes(c.contactId)} onChange={() => toggleContact(c.contactId)} /><span className="contact-name">{c.name || c.phone}</span><span className="contact-phone">{c.phone}</span></label>))}
                {filteredContacts.length === 0 && <div className="empty-state">No contacts found</div>}
              </div>
            </div>
            <Button variant="primary" className="btn-block" onClick={handleSendCampaign} disabled={sending || selectedContacts.length === 0 || !messageContent.trim()} loading={sending}>{sending ? 'Sending...' : `Send Campaign to ${selectedContacts.length} Contacts`}</Button>
          </div>
        )}
        {activeTab === 'logs' && (
          <div className="table-container"><table><thead><tr><th>Campaign</th><th>Recipients</th><th>Sent</th><th>Delivered</th><th>Read</th><th>Failed</th><th>Date</th></tr></thead><tbody>
            {campaigns.map(c => (<tr key={c.id}><td><strong>{c.name}</strong></td><td>{c.recipients}</td><td className="text-success">{c.sent}</td><td>{c.delivered}</td><td>{c.read}</td><td className="text-error">{c.failed}</td><td>{new Date(c.createdAt).toLocaleDateString()}</td></tr>))}
            {campaigns.length === 0 && <tr><td colSpan={7} className="empty-state">No campaigns yet</td></tr>}
          </tbody></table></div>
        )}
      </div>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Campaign | WECARE.DIGITAL" description="Send bulk RCS campaigns" />
      {content}
    </Layout>
  );
};

export default RcsCampaignPage;