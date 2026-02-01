/**
 * Bulk Email - AWS SES
 * Bulk email campaigns via AWS Simple Email Service
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import RichTextEditor from '../../../components/RichTextEditor';
import * as api from '../../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const BulkSes: React.FC<PageProps> = ({ signOut, user }) => {
  const [jobs, setJobs] = useState<api.BulkJob[]>([]);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [subject, setSubject] = useState('');
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsData, contactsData] = await Promise.all([
        api.listBulkJobs('EMAIL'),
        api.listContacts(),
      ]);
      setJobs(jobsData);
      setContacts(contactsData.filter(c => c.email && c.optInEmail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSelectAll = () => {
    setSelectedContacts(prev => prev.length === contacts.length ? [] : contacts.map(c => c.contactId));
  };

  const handleCreateCampaign = async () => {
    if (selectedContacts.length === 0 || !messageText.trim() || !subject.trim()) return;
    setCreating(true);
    try {
      await api.createBulkJob({ channel: 'EMAIL', totalRecipients: selectedContacts.length });
      setShowCreate(false);
      setSelectedContacts([]);
      setSubject('');
      setMessageText('');
      await loadData();
    } finally {
      setCreating(false);
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="bulk-page">
        <div className="bulk-header">
          <a href="/bulk" className="back-btn">←</a>
          <div className="bulk-header-info">
            <span className="bulk-icon">✉️</span>
            <div>
              <h1>Bulk Email - AWS SES</h1>
              <span className="bulk-provider">Simple Email Service</span>
            </div>
          </div>
          <button onClick={() => setShowCreate(true)} className="create-btn">+ New Campaign</button>
        </div>

        <div className="bulk-content">
          <div className="jobs-section">
            <h2>Email Campaigns</h2>
            {loading ? <p>Loading...</p> : jobs.length === 0 ? (
              <div className="empty-state">
                <p>No email campaigns yet</p>
                <button onClick={() => setShowCreate(true)}>Create First Campaign</button>
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

          <div className="info-panel">
            <h3>AWS SES</h3>
            <div className="info-section">
              <h4>Sender Identity</h4>
              <p>noreply@wecare.digital</p>
              <span className="verified">✓ Verified</span>
            </div>
            <div className="info-section">
              <h4>Features</h4>
              <ul><li>✓ HTML Templates</li><li>✓ Bounce Handling</li><li>✓ Open/Click Tracking</li><li>✓ 50K emails/day</li></ul>
            </div>
          </div>
        </div>

        {showCreate && (
          <div className="modal-overlay" onClick={() => setShowCreate(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>New Email Campaign</h2>
                <button onClick={() => setShowCreate(false)}>✕</button>
              </div>
              <div className="modal-body">
                <div className="form-section">
                  <h3>Select Recipients ({selectedContacts.length} selected)</h3>
                  <button className="select-all-btn" onClick={handleSelectAll}>
                    {selectedContacts.length === contacts.length ? 'Deselect All' : 'Select All'}
                  </button>
                  <div className="contacts-grid">
                    {contacts.map(c => (
                      <label key={c.contactId} className="contact-checkbox">
                        <input type="checkbox" checked={selectedContacts.includes(c.contactId)} onChange={() => setSelectedContacts(prev => prev.includes(c.contactId) ? prev.filter(id => id !== c.contactId) : [...prev, c.contactId])} />
                        <span>{c.name || c.email}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="form-section">
                  <h3>Subject</h3>
                  <input type="text" value={subject} onChange={e => setSubject(e.target.value)} placeholder="Enter email subject..." className="subject-input" />
                </div>
                <div className="form-section">
                  <h3>Message</h3>
                  <RichTextEditor value={messageText} onChange={setMessageText} placeholder="Write your email..." channel="email" />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                <button className="btn-primary" onClick={handleCreateCampaign} disabled={creating || selectedContacts.length === 0 || !messageText.trim() || !subject.trim()}>
                  {creating ? 'Creating...' : `Send to ${selectedContacts.length} contacts`}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .bulk-page { height: calc(100vh - 60px); display: flex; flex-direction: column; }
        .bulk-header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #232f3e; color: #fff; }
        .back-btn { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 8px 12px; border-radius: 13px; cursor: pointer; text-decoration: none; }
        .back-btn:hover { background: rgba(255,255,255,0.3); }
        .bulk-header-info { display: flex; align-items: center; gap: 12px; flex: 1; }
        .bulk-icon { font-size: 28px; }
        .bulk-header h1 { font-size: 18px; font-weight: 500; margin: 0; }
        .bulk-provider { font-size: 13px; opacity: 0.9; }
        .create-btn { background: #fff; color: #000; border: 1px solid #000; padding: 8px 16px; border-radius: 13px; cursor: pointer; font-weight: 500; }
        .create-btn:hover { background: #f5f5f5; }
        .bulk-content { flex: 1; display: grid; grid-template-columns: 1fr 280px; overflow: hidden; }
        .jobs-section { padding: 24px; overflow-y: auto; }
        .jobs-section h2 { font-size: 18px; margin: 0 0 16px 0; }
        .empty-state { text-align: center; padding: 40px; color: #666; }
        .empty-state button { margin-top: 12px; background: #fff; color: #000; border: 1px solid #000; padding: 10px 20px; border-radius: 13px; cursor: pointer; }
        .empty-state button:hover { background: #f5f5f5; }
        .jobs-list { display: grid; gap: 12px; }
        .job-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 13px; padding: 16px; display: flex; align-items: center; gap: 20px; }
        .status-badge { font-size: 12px; padding: 4px 12px; border-radius: 13px; text-transform: uppercase; background: #f5f5f5; }
        .job-stats { display: flex; gap: 24px; flex: 1; }
        .stat { text-align: center; }
        .stat-value { display: block; font-size: 20px; font-weight: 500; }
        .stat-label { font-size: 12px; color: #666; }
        .job-date { font-size: 13px; color: #999; }
        .info-panel { background: #fff; border-left: 1px solid #e5e5e5; padding: 20px; overflow-y: auto; }
        .info-panel h3 { font-size: 16px; margin: 0 0 20px 0; }
        .info-section { margin-bottom: 20px; }
        .info-section h4 { font-size: 12px; color: #666; text-transform: uppercase; margin: 0 0 8px 0; }
        .info-section p { margin: 0; font-size: 14px; }
        .verified { font-size: 11px; color: #22c55e; }
        .info-section ul { list-style: none; padding: 0; margin: 0; font-size: 13px; }
        .info-section li { padding: 4px 0; }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal { background: #fff; border-radius: 13px; width: 90%; max-width: 700px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e5e5; }
        .modal-header h2 { margin: 0; font-size: 18px; }
        .modal-header button { background: none; border: none; font-size: 20px; cursor: pointer; }
        .modal-body { padding: 20px; flex: 1; overflow-y: auto; }
        .form-section { margin-bottom: 20px; }
        .form-section h3 { font-size: 14px; margin: 0 0 12px 0; }
        .subject-input { width: 100%; padding: 12px 14px; border: 1px solid #000; border-radius: 13px; font-size: 14px; }
        .subject-input:hover { background: #f5f5f5; }
        .subject-input:focus { outline: none; background: #fff; box-shadow: 0 0 0 3px rgba(0,0,0,0.1); }
        .select-all-btn { background: #fff; border: 1px solid #000; padding: 6px 12px; border-radius: 13px; cursor: pointer; font-size: 12px; margin-bottom: 12px; }
        .select-all-btn:hover { background: #f5f5f5; }
        .contacts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; max-height: 200px; overflow-y: auto; }
        .contact-checkbox { display: flex; align-items: center; gap: 8px; padding: 8px; background: #f9f9f9; border-radius: 13px; cursor: pointer; font-size: 13px; }
        .modal-footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 20px; border-top: 1px solid #e5e5e5; }
        .btn-secondary { background: #fff; border: 1px solid #000; padding: 10px 20px; border-radius: 13px; cursor: pointer; color: #000; }
        .btn-secondary:hover { background: #f5f5f5; }
        .btn-primary { background: #fff; color: #000; border: 1px solid #000; padding: 10px 20px; border-radius: 13px; cursor: pointer; }
        .btn-primary:hover { background: #f5f5f5; }
        .btn-primary:disabled { background: #f5f5f5; color: #999; border-color: #e5e5e5; cursor: not-allowed; }
      `}</style>
    </Layout>
  );
};

export default BulkSes;
