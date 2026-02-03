/**
 * AWS Voice DM
 * Voice calls via Amazon Connect / Pinpoint Voice in us-east-1
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import { RefreshIcon } from '../../../lib/icons';
import { API_BASE } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

interface VoiceCall {
  id: string;
  callId: string;
  contactId: string;
  phoneNumber: string;
  callType: string;
  status: string;
  direction: string;
  duration: number;
  createdAt: number;
}

const AWSVoiceDM: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialerNumber, setDialerNumber] = useState('');
  const [messageText, setMessageText] = useState('');
  const [calling, setCalling] = useState(false);
  const [callResult, setCallResult] = useState<{ success: boolean; message: string } | null>(null);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/voice-aws/calls`);
      if (response.ok) {
        const data = await response.json();
        setCalls(data.calls || []);
      }
    } catch (err) {
      setError('Failed to load calls');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  const handleMakeCall = async () => {
    if (!dialerNumber.trim()) {
      setCallResult({ success: false, message: 'Phone number is required' });
      return;
    }
    
    setCalling(true);
    setCallResult(null);
    
    try {
      const response = await fetch(`${API_BASE}/voice-aws/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phoneNumber: dialerNumber,
          callType: messageText ? 'tts' : 'audio',
          messageText: messageText,
          voiceId: 'Joanna'
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setCallResult({ success: true, message: `Call initiated! ID: ${data.callId}` });
        setDialerNumber('');
        setMessageText('');
        loadCalls();
      } else {
        setCallResult({ success: false, message: data.error || 'Failed to make call' });
      }
    } catch (err: any) {
      setCallResult({ success: false, message: err.message || 'Network error' });
    } finally {
      setCalling(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const styles = `
    .voice-page { height: ${embedded ? '100%' : 'calc(100vh - 60px)'}; display: flex; flex-direction: column; background: #fff; }
    .error-bar { background: #f0fdf4; color: #065f46; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #a7f3d0; }
    .result-bar { padding: 10px 16px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
    .result-bar.success { background: #d1fae5; color: #065f46; }
    .result-bar.error { background: #f3f4f6; color: #6b7280; }
    .result-bar button { background: none; border: none; font-size: 18px; cursor: pointer; }
    .voice-layout { display: grid; grid-template-columns: 320px 1fr 260px; flex: 1; overflow: hidden; }
    .dialer-section { padding: 20px; border-right: 1px solid #e5e5e5; }
    .dialer-section h3 { margin: 0 0 16px 0; font-size: 16px; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
    .form-group input, .form-group textarea { width: 100%; padding: 10px 12px; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 14px; }
    .form-group textarea { resize: vertical; }
    .call-btn { width: 100%; padding: 12px; background: #10b981; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
    .call-btn:disabled { background: #9ca3af; cursor: not-allowed; }
    .calls-section { padding: 20px; overflow-y: auto; }
    .calls-section h3 { margin: 0 0 16px 0; font-size: 16px; }
    .calls-list { display: flex; flex-direction: column; gap: 8px; }
    .call-item { padding: 12px; background: #f9f9f9; border-radius: 8px; }
    .call-info { display: flex; justify-content: space-between; margin-bottom: 6px; }
    .call-phone { font-weight: 500; }
    .call-type { font-size: 12px; color: #666; background: #e5e5e5; padding: 2px 8px; border-radius: 4px; }
    .call-meta { display: flex; gap: 12px; font-size: 12px; color: #666; }
    .call-status { padding: 2px 8px; border-radius: 4px; }
    .call-status.initiated { background: #dbeafe; color: #1d4ed8; }
    .call-status.completed { background: #d1fae5; color: #065f46; }
    .call-status.failed { background: #f3f4f6; color: #6b7280; }
    .empty { color: #666; text-align: center; padding: 40px; }
    .info-panel { padding: 20px; border-left: 1px solid #e5e5e5; background: #fafafa; }
    .info-panel h3 { margin: 0 0 16px 0; font-size: 16px; }
    .info-section { margin-bottom: 20px; }
    .info-section h4 { font-size: 12px; color: #666; text-transform: uppercase; margin: 0 0 8px 0; }
    .info-section ul { list-style: none; padding: 0; margin: 0; font-size: 13px; }
    .info-section li { padding: 4px 0; }
    .info-section p { margin: 0; font-size: 13px; }
    .info-section a { color: #000; text-decoration: none; font-size: 13px; }
    .info-section a:hover { text-decoration: underline; }
    @media (max-width: 1024px) { .voice-layout { grid-template-columns: 280px 1fr; } .info-panel { display: none; } }
    @media (max-width: 768px) { .voice-layout { grid-template-columns: 1fr; } .dialer-section { border-right: none; border-bottom: 1px solid #e5e5e5; } }
  `;

  const content = (
    <div className="voice-page">
      {!embedded && (
        <PageHeader 
          title="AWS Voice" 
          subtitle="Amazon Connect & Polly TTS"
          icon="voice"
          actions={
            <button onClick={loadCalls} className="refresh-btn" disabled={loading}>
              {loading ? '...' : <RefreshIcon size={18} />}
            </button>
          }
        />
      )}

      {error && <div className="error-bar">{error}</div>}
      
      {callResult && (
        <div className={`result-bar ${callResult.success ? 'success' : 'error'}`}>
          {callResult.message}
          <button onClick={() => setCallResult(null)}>×</button>
        </div>
      )}

      <div className="voice-layout">
        {/* Dialer */}
        <div className="dialer-section">
          <h3>Make a Call</h3>
          <div className="form-group">
            <label>Phone Number</label>
            <input
              type="tel"
              value={dialerNumber}
              onChange={(e) => setDialerNumber(e.target.value.replace(/[^0-9+]/g, ''))}
              placeholder="+1 XXX XXX XXXX"
            />
          </div>
          <div className="form-group">
            <label>Message (TTS)</label>
            <textarea
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder="Enter message for text-to-speech..."
              rows={3}
            />
          </div>
          <button 
            className="call-btn"
            onClick={handleMakeCall}
            disabled={calling || !dialerNumber.trim()}
          >
            {calling ? 'Calling...' : 'Make Call'}
          </button>
        </div>

        {/* Call History */}
        <div className="calls-section">
          <h3>Recent Calls</h3>
          <div className="calls-list">
            {calls.length === 0 ? (
              <div className="empty">No calls yet</div>
            ) : (
              calls.map(call => (
                <div key={call.id} className="call-item">
                  <div className="call-info">
                    <span className="call-phone">{call.phoneNumber}</span>
                    <span className="call-type">{call.callType}</span>
                  </div>
                  <div className="call-meta">
                    <span className={`call-status ${call.status.toLowerCase()}`}>{call.status}</span>
                    <span className="call-duration">{formatDuration(call.duration)}</span>
                    <span className="call-time">{new Date(call.createdAt * 1000).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Info Panel */}
        <div className="info-panel">
          <h3>AWS Voice</h3>
          <div className="info-section">
            <h4>Features</h4>
            <ul>
              <li>Amazon Connect</li>
              <li>Polly TTS</li>
              <li>IVR Integration</li>
              <li>Call Recording</li>
            </ul>
          </div>
          <div className="info-section">
            <h4>Region</h4>
            <p>us-east-1</p>
          </div>
          <div className="info-section">
            <h4>Documentation</h4>
            <a href="https://docs.aws.amazon.com/connect/" target="_blank" rel="noopener noreferrer">
              AWS Connect Docs →
            </a>
          </div>
        </div>
      </div>

    </div>
  );

  if (embedded) {
    return (
      <>
        {content}
        <style jsx>{styles}</style>
      </>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
      <style jsx>{styles}</style>
    </Layout>
  );
};

export default AWSVoiceDM;
