/**
 * Bulk IN SMS Campaigns
 * Bulk SMS campaigns via IN SMS
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import RichTextEditor from '../../../components/RichTextEditor';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const TABS = ['Campaigns', 'Create', 'Templates', 'Analytics'];

const BulkINSms: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState('Campaigns');
  const [jobs, setJobs] = useState<api.BulkJob[]>([]);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsData, contactsData] = await Promise.all([
        api.listBulkJobs('SMS'),
        api.listContacts(),
      ]);
      setJobs(jobsData);
      setContacts(contactsData.filter(c => c.phone && c.optInSms));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSelectAll = () => {
    setSelectedContacts(prev => prev.length === contacts.length ? [] : contacts.map(c => c.contactId));
  };

  const handleCreateCampaign = async () => {
    if (selectedContacts.length === 0 || !messageText.trim()) return;
    setCreating(true);
    try {
      await api.createBulkJob({ channel: 'SMS', totalRecipients: selectedContacts.length });
      setActiveTab('Campaigns');
      setSelectedContacts([]);
      setMessageText('');
      await loadData();
    } finally {
      setCreating(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="bulk-page">
        <PageHeader 
          title="Bulk SMS - IN SMS" 
          subtitle="India SMS Gateway"
          icon="sms"
          backLink="/bulk/sms"
          backLabel="← Bulk SMS"
        />

        <div className="tabs">
          {TABS.map(tab => (
            <button key={tab} className={`tab ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>{tab}</button>
          ))}
        </div>

        <div className="main-content">
          <div className="tab-content">
            {activeTab === 'Campaigns' && (
              <div className="campaigns-section">
                {loading ? <p>Loading...</p> : jobs.length === 0 ? (
                  <div className="empty-state">
                    <p>No SMS campaigns yet</p>
                    <button onClick={() => setActiveTab('Create')}>Create First Campaign</button>
                  </div>
                ) : (
                  <div className="jobs-list">
                    {jobs.map(job => (
                      <div key={job.id} className="job-card">
                        <span className={`status-badge ${job.status.toLowerCase()}`}>{job.status}</span>
                        <div className="job-stats">
                          <div className="stat"><span className="stat-value">{job.totalRecipients}</span><span className="stat-label">Recipients</span></div>
                          <div className="stat"><span className="stat-value">{job.sentCount}</span><span className="stat-label">Sent</span></div>
                          <div className="stat"><span className="stat-value">{job.failedCount}</span><span className="stat-label">Failed</span></div>
                        </div>
                        <div className="job-date">{new Date(job.createdAt).toLocaleDateString()}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'Create' && (
              <div className="create-section">
                <h2>Create SMS Campaign</h2>
                <div className="form-section">
                  <h3>Select Recipients ({selectedContacts.length} selected)</h3>
                  <button className="select-all-btn" onClick={handleSelectAll}>
                    {selectedContacts.length === contacts.length ? 'Deselect All' : 'Select All'}
                  </button>
                  <div className="contacts-grid">
                    {contacts.map(c => (
                      <label key={c.contactId} className="contact-checkbox">
                        <input type="checkbox" checked={selectedContacts.includes(c.contactId)} onChange={() => setSelectedContacts(prev => prev.includes(c.contactId) ? prev.filter(id => id !== c.contactId) : [...prev, c.contactId])} />
                        <span>{c.name || c.phone}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="form-section">
                  <h3>Message ({messageText.length}/160 chars)</h3>
                  <RichTextEditor value={messageText} onChange={setMessageText} placeholder="Type your SMS..." channel="sms" maxLength={1600} showCharCount={true} />
                </div>
                <button className="btn-primary" onClick={handleCreateCampaign} disabled={creating || selectedContacts.length === 0 || !messageText.trim()}>
                  {creating ? 'Creating...' : `Send to ${selectedContacts.length} contacts`}
                </button>
              </div>
            )}

            {activeTab === 'Templates' && (
              <div className="coming-soon"><h2>Coming Soon</h2><p>DLT-approved SMS templates</p></div>
            )}

            {activeTab === 'Analytics' && (
              <div className="coming-soon"><h2>Coming Soon</h2><p>Campaign delivery rates and metrics</p></div>
            )}
          </div>

          <div className="info-panel">
            <h3>IN SMS</h3>
            <div className="info-section"><h4>Features</h4><ul><li>Transactional SMS</li><li>Promotional SMS</li><li>DLT Compliance</li><li>Delivery Reports</li></ul></div>
            <div className="info-section"><h4>Documentation</h4><a href="https://www.airtel.in/business/b2b/airtel-iq/api-docs/sms/overview" target="_blank" rel="noopener noreferrer">IN SMS API →</a></div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .bulk-page { height: calc(100vh - 60px); display: flex; flex-direction: column; background: #fff; }
        .tabs { display: flex; gap: 8px; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e5e5e5; }
        .tab { background: #fff; border: 1px solid #000; padding: 8px 16px; font-size: 14px; cursor: pointer; border-radius: 13px; color: #000; }
        .tab:hover { background: #f5f5f5; }
        .tab.active { background: #f5f5f5; color: #000; font-weight: 600; }
        .main-content { flex: 1; display: flex; overflow: hidden; }
        .tab-content { flex: 1; padding: 24px; overflow-y: auto; }
        .info-panel { width: 280px; background: #fff; border-left: 1px solid #e5e5e5; padding: 20px; overflow-y: auto; }
        .info-panel h3 { font-size: 16px; margin: 0 0 20px 0; color: #000; }
        .info-section { margin-bottom: 20px; }
        .info-section h4 { font-size: 12px; color: #4a4a4a; text-transform: uppercase; margin: 0 0 8px 0; }
        .info-section ul { list-style: none; padding: 0; margin: 0; font-size: 13px; color: #000; }
        .info-section li { padding: 4px 0; }
        .info-section a { color: #000; text-decoration: none; font-size: 13px; }
        .info-section a:hover { text-decoration: underline; }
        .empty-state { text-align: center; padding: 40px; color: #4a4a4a; }
        .empty-state button { margin-top: 12px; background: #fff; color: #000; border: 1px solid #000; padding: 10px 20px; border-radius: 13px; cursor: pointer; }
        .empty-state button:hover { background: #f5f5f5; }
        .jobs-list { display: grid; gap: 12px; }
        .job-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 13px; padding: 16px; display: flex; align-items: center; gap: 20px; }
        .status-badge { font-size: 12px; padding: 4px 12px; border-radius: 13px; text-transform: uppercase; background: #f5f5f5; color: #000; }
        .job-stats { display: flex; gap: 24px; flex: 1; }
        .stat { text-align: center; }
        .stat-value { display: block; font-size: 20px; font-weight: 500; color: #000; }
        .stat-label { font-size: 12px; color: #4a4a4a; }
        .job-date { font-size: 13px; color: #4a4a4a; }
        .create-section h2 { font-size: 20px; margin: 0 0 20px 0; color: #000; }
        .form-section { margin-bottom: 20px; }
        .form-section h3 { font-size: 14px; margin: 0 0 12px 0; color: #000; }
        .select-all-btn { background: #fff; border: 1px solid #000; padding: 6px 12px; border-radius: 13px; cursor: pointer; font-size: 12px; margin-bottom: 12px; color: #000; }
        .select-all-btn:hover { background: #f5f5f5; }
        .contacts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; max-height: 200px; overflow-y: auto; }
        .contact-checkbox { display: flex; align-items: center; gap: 8px; padding: 8px; background: #f9f9f9; border-radius: 13px; cursor: pointer; font-size: 13px; color: #000; }
        .btn-primary { background: #fff; color: #000; border: 1px solid #000; padding: 12px 24px; border-radius: 13px; cursor: pointer; font-size: 14px; }
        .btn-primary:hover { background: #f5f5f5; }
        .btn-primary:disabled { background: #f5f5f5; color: #999; border-color: #e5e5e5; cursor: not-allowed; }
        .coming-soon { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 40vh; text-align: center; }
        .coming-soon h2 { font-size: 28px; font-weight: 600; color: #000; margin: 0 0 8px 0; }
        .coming-soon p { font-size: 16px; color: #4a4a4a; margin: 0; }
        @media (max-width: 1024px) { .info-panel { display: none; } }
      `}</style>
    </Layout>
  );
};

export default BulkINSms;
