/**
 * SMS-IN Campaign Page (Inbound SMS - View Only)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';

interface PageProps { signOut?: () => void; user?: any; }
interface CampaignLog { id: string; name: string; recipients: number; received: number; createdAt: string; }

const SmsInCampaignPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignLog[]>([]);
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const messages = await api.listMessages(undefined, 'SMS_IN');
      const campaignMsgs = messages.filter(m => (m as any).campaignId);
      const campaignMap = new Map<string, CampaignLog>();
      campaignMsgs.forEach(m => {
        const cid = (m as any).campaignId;
        if (!campaignMap.has(cid)) { campaignMap.set(cid, { id: cid, name: (m as any).campaignName || cid, recipients: 0, received: 0, createdAt: m.timestamp }); }
        const c = campaignMap.get(cid)!; c.recipients++; if (m.status === 'received') c.received++;
      });
      setCampaigns(Array.from(campaignMap.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
    } catch (err) { toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS-IN Campaign Logs | WECARE.DIGITAL" description="View inbound SMS campaign logs" />
      <div className="inner-page campaign-page">
        <div className="page-header"><h2>SMS-IN Campaign Logs</h2><Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} /></div>
        <p className="info-text">Inbound SMS campaigns are receive-only. View responses from your outbound campaigns here.</p>
        <div className="table-container"><table><thead><tr><th>Campaign</th><th>Recipients</th><th>Received</th><th>Date</th></tr></thead><tbody>
          {campaigns.map(c => (<tr key={c.id}><td><strong>{c.name}</strong></td><td>{c.recipients}</td><td className="text-success">{c.received}</td><td>{new Date(c.createdAt).toLocaleDateString()}</td></tr>))}
          {campaigns.length === 0 && <tr><td colSpan={4} className="empty-state">No inbound campaign responses yet</td></tr>}
        </tbody></table></div>
      </div>
    </Layout>
  );
};

export default SmsInCampaignPage;