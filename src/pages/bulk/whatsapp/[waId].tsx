/**
 * Bulk WhatsApp Campaign - Specific WABA
 * Create and manage bulk WhatsApp campaigns with progress tracking
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import RichTextEditor from '../../../components/RichTextEditor';
import { ProgressBar } from '../../../components/Charts';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface BulkJob {
  id: string;
  jobId: string;
  status: string;
  totalRecipients: number;
  sentCount: number;
  failedCount: number;
  createdAt: string;
}

const WABA_INFO: Record<string, { name: string; phone: string }> = {
  [WHATSAPP_PHONES.primary.id]: { name: WHATSAPP_PHONES.primary.name, phone: WHATSAPP_PHONES.primary.display },
  [WHATSAPP_PHONES.secondary.id]: { name: WHATSAPP_PHONES.secondary.name, phone: WHATSAPP_PHONES.secondary.display },
};

const BulkWhatsAppCampaign: React.FC<PageProps> = ({ signOut, user }) => {
  const router = useRouter();
  const { waId } = router.query;
  const wabaInfo = waId ? WABA_INFO[waId as string] : null;

  const [jobs, setJobs] = useState<BulkJob[]>([]);
  const [contacts, setContacts] = useState<api.Contact[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  
  // Progress tracking state
  const [activeJob, setActiveJob] = useState<BulkJob | null>(null);
  const [sendingProgress, setSendingProgress] = useState({ sent: 0, failed: 0, total: 0 });
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsData, contactsData] = await Promise.all([
        api.listBulkJobs('WHATSAPP'),
        api.listContacts(),
      ]);
      setJobs(jobsData);
      setContacts(contactsData.filter(c => c.phone && c.optInWhatsApp));
      
      // Check for active jobs
      const inProgress = jobsData.find(j => j.status === 'IN_PROGRESS');
      if (inProgress) {
        setActiveJob(inProgress);
        startProgressTracking(inProgress.jobId || inProgress.id);
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, [loadData]);

  // Poll for job progress
  const startProgressTracking = (jobId: string) => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }
    
    progressIntervalRef.current = setInterval(async () => {
      try {
        const jobsData = await api.listBulkJobs('WHATSAPP');
        const job = jobsData.find(j => (j.jobId || j.id) === jobId);
        
        if (job) {
          setSendingProgress({
            sent: job.sentCount,
            failed: job.failedCount,
            total: job.totalRecipients,
          });
          
          if (job.status === 'COMPLETED' || job.status === 'FAILED' || job.status === 'CANCELLED') {
            setActiveJob(null);
            if (progressIntervalRef.current) {
              clearInterval(progressIntervalRef.current);
            }
            loadData();
          }
        }
      } catch (err) {
        console.error('Failed to fetch job progress:', err);
      }
    }, 2000);
  };

  const handleSelectAll = () => {
    if (selectedContacts.length === contacts.length) {
      setSelectedContacts([]);
    } else {
      setSelectedContacts(contacts.map(c => c.contactId));
    }
  };

  const handleToggleContact = (contactId: string) => {
    setSelectedContacts(prev =>
      prev.includes(contactId)
        ? prev.filter(id => id !== contactId)
        : [...prev, contactId]
    );
  };

  const handleCreateCampaign = async () => {
    if (selectedContacts.length === 0 || !messageText.trim()) return;
    setCreating(true);
    try {
      const newJob = await api.createBulkJob({
        channel: 'WHATSAPP',
        totalRecipients: selectedContacts.length,
      });
      
      if (newJob) {
        setActiveJob(newJob);
        setSendingProgress({ sent: 0, failed: 0, total: selectedContacts.length });
        startProgressTracking(newJob.jobId || newJob.id);
      }
      
      setShowCreate(false);
      setSelectedContacts([]);
      setMessageText('');
      await loadData();
    } catch (err) {
      console.error('Failed to create campaign:', err);
    } finally {
      setCreating(false);
    }
  };

  const handlePauseJob = async (jobId: string) => {
    try {
      await api.updateBulkJobStatus(jobId, 'PAUSED');
      loadData();
    } catch (err) {
      console.error('Failed to pause job:', err);
    }
  };

  const handleResumeJob = async (jobId: string) => {
    try {
      await api.updateBulkJobStatus(jobId, 'IN_PROGRESS');
      startProgressTracking(jobId);
      loadData();
    } catch (err) {
      console.error('Failed to resume job:', err);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    if (!confirm('Are you sure you want to cancel this campaign?')) return;
    try {
      await api.updateBulkJobStatus(jobId, 'CANCELLED');
      setActiveJob(null);
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      loadData();
    } catch (err) {
      console.error('Failed to cancel job:', err);
    }
  };

  const getProgressPercent = (job: BulkJob) => {
    if (job.totalRecipients === 0) return 0;
    return Math.round(((job.sentCount + job.failedCount) / job.totalRecipients) * 100);
  };

  if (!waId || !wabaInfo) {
    return (
      <Layout user={user} onSignOut={signOut}>
        <div className="page"><p>Loading...</p></div>
      </Layout>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="bulk-page">
        <div className="bulk-header">
          <button onClick={() => router.push('/bulk/whatsapp')} className="back-btn">←</button>
          <div className="bulk-header-info">
            <span className="bulk-icon">💬</span>
            <div>
              <h1>Bulk WhatsApp - {wabaInfo.name}</h1>
              <span className="bulk-phone">{wabaInfo.phone}</span>
            </div>
          </div>
          <button onClick={() => setShowCreate(true)} className="create-btn">+ New Campaign</button>
        </div>

        <div className="bulk-content">
          {/* Active Job Progress Banner */}
          {activeJob && (
            <div className="progress-banner">
              <div className="progress-header">
                <span className="progress-title">◉ Campaign in Progress</span>
                <div className="progress-actions">
                  {activeJob.status === 'IN_PROGRESS' && (
                    <button onClick={() => handlePauseJob(activeJob.jobId || activeJob.id)} className="pause-btn">⏸ Pause</button>
                  )}
                  {activeJob.status === 'PAUSED' && (
                    <button onClick={() => handleResumeJob(activeJob.jobId || activeJob.id)} className="resume-btn">▶ Resume</button>
                  )}
                  <button onClick={() => handleCancelJob(activeJob.jobId || activeJob.id)} className="cancel-btn">✕ Cancel</button>
                </div>
              </div>
              <div className="progress-stats">
                <span className="progress-sent">✓ {sendingProgress.sent} sent</span>
                <span className="progress-failed">✕ {sendingProgress.failed} failed</span>
                <span className="progress-remaining">◌ {sendingProgress.total - sendingProgress.sent - sendingProgress.failed} remaining</span>
              </div>
              <div className="progress-bar-container">
                <div className="progress-bar">
                  <div 
                    className="progress-fill success" 
                    style={{ width: `${(sendingProgress.sent / sendingProgress.total) * 100}%` }} 
                  />
                  <div 
                    className="progress-fill failed" 
                    style={{ width: `${(sendingProgress.failed / sendingProgress.total) * 100}%` }} 
                  />
                </div>
                <span className="progress-percent">
                  {Math.round(((sendingProgress.sent + sendingProgress.failed) / sendingProgress.total) * 100)}%
                </span>
              </div>
            </div>
          )}

          {/* Jobs List */}
          <div className="jobs-section">
            <h2>Campaigns</h2>
            {loading ? (
              <p>Loading...</p>
            ) : jobs.length === 0 ? (
              <div className="empty-state">
                <p>No campaigns yet</p>
                <button onClick={() => setShowCreate(true)}>Create First Campaign</button>
              </div>
            ) : (
              <div className="jobs-list">
                {jobs.map(job => (
                  <div key={job.id || job.jobId} className="job-card">
                    <div className="job-status">
                      <span className={`status-badge ${job.status.toLowerCase().replace('_', '-')}`}>{job.status.replace('_', ' ')}</span>
                    </div>
                    <div className="job-stats">
                      <div className="stat">
                        <span className="stat-value">{job.totalRecipients}</span>
                        <span className="stat-label">Recipients</span>
                      </div>
                      <div className="stat">
                        <span className="stat-value" style={{ color: '#25D366' }}>{job.sentCount}</span>
                        <span className="stat-label">Sent</span>
                      </div>
                      <div className="stat">
                        <span className="stat-value" style={{ color: job.failedCount > 0 ? '#F44336' : '#666' }}>{job.failedCount}</span>
                        <span className="stat-label">Failed</span>
                      </div>
                    </div>
                    <div className="job-progress">
                      <div className="mini-progress-bar">
                        <div className="mini-progress-fill" style={{ width: `${getProgressPercent(job)}%` }} />
                      </div>
                      <span className="mini-progress-text">{getProgressPercent(job)}%</span>
                    </div>
                    <div className="job-date">{new Date(job.createdAt).toLocaleDateString()}</div>
                    <div className="job-actions">
                      {job.status === 'PAUSED' && (
                        <button onClick={() => handleResumeJob(job.jobId || job.id)} className="action-btn resume">▶</button>
                      )}
                      {(job.status === 'IN_PROGRESS' || job.status === 'PAUSED') && (
                        <button onClick={() => handleCancelJob(job.jobId || job.id)} className="action-btn cancel">✕</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Create Campaign Modal */}
        {showCreate && (
          <div className="modal-overlay" onClick={() => setShowCreate(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>New WhatsApp Campaign</h2>
                <button onClick={() => setShowCreate(false)}>✕</button>
              </div>
              <div className="modal-body">
                <div className="form-section">
                  <h3>Select Recipients ({selectedContacts.length} selected)</h3>
                  <button className="select-all-btn" onClick={handleSelectAll}>
                    {selectedContacts.length === contacts.length ? 'Deselect All' : 'Select All'}
                  </button>
                  <div className="contacts-grid">
                    {contacts.map(contact => (
                      <label key={contact.contactId} className="contact-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedContacts.includes(contact.contactId)}
                          onChange={() => handleToggleContact(contact.contactId)}
                        />
                        <span>{contact.name || contact.phone}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="form-section">
                  <h3>Message</h3>
                  <RichTextEditor
                    value={messageText}
                    onChange={setMessageText}
                    placeholder="Type your bulk message..."
                    channel="whatsapp"
                    showAISuggestions={true}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                <button
                  className="btn-primary"
                  onClick={handleCreateCampaign}
                  disabled={creating || selectedContacts.length === 0 || !messageText.trim()}
                >
                  {creating ? 'Creating...' : `Send to ${selectedContacts.length} contacts`}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .bulk-page { height: calc(100vh - 60px); display: flex; flex-direction: column; }
        .bulk-header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #25D366; color: #fff; }
        .back-btn { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 8px 12px; border-radius: 8px; cursor: pointer; }
        .bulk-header-info { display: flex; align-items: center; gap: 12px; flex: 1; }
        .bulk-icon { font-size: 28px; }
        .bulk-header h1 { font-size: 18px; font-weight: 500; margin: 0; }
        .bulk-phone { font-size: 13px; opacity: 0.9; }
        .create-btn { background: #fff; color: #25D366; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 500; }
        .bulk-content { flex: 1; padding: 24px; overflow-y: auto; }
        
        /* Progress Banner */
        .progress-banner { background: #25D366; color: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; }
        .progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .progress-title { font-size: 16px; font-weight: 500; }
        .progress-actions { display: flex; gap: 8px; }
        .pause-btn, .resume-btn, .cancel-btn { background: rgba(255,255,255,0.2); border: none; color: #fff; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .pause-btn:hover, .resume-btn:hover { background: rgba(255,255,255,0.3); }
        .cancel-btn:hover { background: rgba(255,0,0,0.3); }
        .progress-stats { display: flex; gap: 20px; margin-bottom: 12px; font-size: 13px; }
        .progress-sent { color: #90EE90; }
        .progress-failed { color: #FFB6C1; }
        .progress-remaining { opacity: 0.8; }
        .progress-bar-container { display: flex; align-items: center; gap: 12px; }
        .progress-bar { flex: 1; height: 8px; background: rgba(255,255,255,0.2); border-radius: 4px; overflow: hidden; display: flex; }
        .progress-fill { height: 100%; transition: width 0.3s ease; }
        .progress-fill.success { background: #90EE90; }
        .progress-fill.failed { background: #FFB6C1; }
        .progress-percent { font-size: 14px; font-weight: 500; min-width: 40px; }
        
        .jobs-section h2 { font-size: 18px; margin: 0 0 16px 0; }
        .empty-state { text-align: center; padding: 40px; color: #666; }
        .empty-state button { margin-top: 12px; background: #fff; color: #000; border: 1px solid #000; padding: 10px 20px; border-radius: 13px; cursor: pointer; }
        .empty-state button:hover { background: #f5f5f5; }
        .jobs-list { display: grid; gap: 12px; }
        .job-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 13px; padding: 16px; display: flex; align-items: center; gap: 20px; }
        .status-badge { font-size: 12px; padding: 4px 12px; border-radius: 13px; text-transform: uppercase; }
        .status-badge.completed { background: #dcfce7; color: #166534; }
        .status-badge.in-progress { background: #dbeafe; color: #1e40af; }
        .status-badge.pending { background: #fef3c7; color: #92400e; }
        .status-badge.paused { background: #f3e8ff; color: #7c3aed; }
        .status-badge.failed, .status-badge.cancelled { background: #fee2e2; color: #991b1b; }
        .job-stats { display: flex; gap: 24px; flex: 1; }
        .stat { text-align: center; }
        .stat-value { display: block; font-size: 20px; font-weight: 500; }
        .stat-label { font-size: 12px; color: #666; }
        .job-progress { display: flex; align-items: center; gap: 8px; min-width: 100px; }
        .mini-progress-bar { flex: 1; height: 6px; background: #e5e5e5; border-radius: 3px; overflow: hidden; }
        .mini-progress-fill { height: 100%; background: #25D366; transition: width 0.3s ease; }
        .mini-progress-text { font-size: 12px; color: #666; min-width: 35px; }
        .job-date { font-size: 13px; color: #999; }
        .job-actions { display: flex; gap: 4px; }
        .action-btn { width: 28px; height: 28px; border-radius: 13px; border: none; cursor: pointer; font-size: 12px; }
        .action-btn.resume { background: #dcfce7; color: #166534; }
        .action-btn.cancel { background: #fee2e2; color: #991b1b; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal { background: #fff; border-radius: 13px; width: 90%; max-width: 700px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e5e5e5; }
        .modal-header h2 { margin: 0; font-size: 18px; }
        .modal-header button { background: none; border: none; font-size: 20px; cursor: pointer; }
        .modal-body { padding: 20px; flex: 1; overflow-y: auto; }
        .form-section { margin-bottom: 20px; }
        .form-section h3 { font-size: 14px; margin: 0 0 12px 0; }
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

export default BulkWhatsAppCampaign;
