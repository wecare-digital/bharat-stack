/**
 * Voice-IN Inbox Page - Airtel IQ Voice Integration
 * Tabs: Click-to-Call (C2C), OBD Campaigns, Call Detail Records (CDR)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { contactId: string; name: string; phone: string; }
interface C2CCall { callId: string; fromNumber: string; toNumber: string; callerId: string; status: string; duration: number; recordingUrl?: string; correlationId?: string; createdAt: number; }
interface OBDCampaign { campaignId: string; name: string; status: string; totalRecipients: number; completedCalls: number; successCalls: number; failedCalls: number; createdAt: number; }
interface CDRRecord { id: string; vmSessionId: string; clientCorrelationId: string; callType: string; overallCallStatus: string; callerNumber: string; destinationNumber: string; durationSec: number; conversationDurationSec: number; hangupStatus: string; recordingURL?: string; circleNameCaller?: string; operatorNameCaller?: string; createdAt: number; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const ITEMS_PER_PAGE = 20;

const VoiceInInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'c2c' | 'obd' | 'cdr'>('c2c');
  const [c2cCalls, setC2cCalls] = useState<C2CCall[]>([]);
  const [obdCampaigns, setObdCampaigns] = useState<OBDCampaign[]>([]);
  const [cdrs, setCdrs] = useState<CDRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  
  // C2C Modal state
  const [showC2CModal, setShowC2CModal] = useState(false);
  const [c2cFromNumber, setC2cFromNumber] = useState('');
  const [c2cToNumber, setC2cToNumber] = useState('');
  const [c2cRecording, setC2cRecording] = useState(true);
  const [c2cCalling, setC2cCalling] = useState(false);
  
  // OBD Modal state
  const [showOBDModal, setShowOBDModal] = useState(false);
  const [obdNumbers, setObdNumbers] = useState('');
  const [obdCampaignName, setObdCampaignName] = useState('');
  const [obdCreating, setObdCreating] = useState(false);
  const [obdAudioType, setObdAudioType] = useState<'default' | 'tts' | 'upload' | 's3'>('default');
  const [obdTtsText, setObdTtsText] = useState('');
  const [obdAudioFile, setObdAudioFile] = useState<File | null>(null);
  const [obdS3Path, setObdS3Path] = useState('');
  const [obdUploading, setObdUploading] = useState(false);
  
  // Contacts state
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'c2c-from' | 'c2c-to' | 'obd' | null>(null);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  
  const toast = useToastContext();

  const loadContacts = useCallback(async () => {
    setLoadingContacts(true);
    try {
      const data = await api.listContacts();
      setContacts(data.filter(c => c.phone).map(c => ({ contactId: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '' })));
    } catch (err) { console.error('Load contacts error:', err); } finally { setLoadingContacts(false); }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [c2cResponse, obdResponse, cdrResponse] = await Promise.all([
        fetch(`${API_BASE}/voice-in/c2c`).then(r => r.json()).catch(() => ({ calls: [] })),
        fetch(`${API_BASE}/voice-in/obd`).then(r => r.json()).catch(() => ({ campaigns: [] })),
        fetch(`${API_BASE}/voice-cdr-webhook`).then(r => r.json()).catch(() => ({ cdrs: [] }))
      ]);
      setC2cCalls(c2cResponse.calls || []);
      setObdCampaigns(obdResponse.campaigns || []);
      setCdrs(cdrResponse.cdrs || []);
    } catch (err) { console.error('Load error:', err); toast.error('Failed to load data'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setPage(1); }, [activeTab, searchQuery]);
  useEffect(() => { if (showContactPicker) loadContacts(); }, [showContactPicker, loadContacts]);

  const filteredContacts = contacts.filter(c => 
    c.name.toLowerCase().includes(contactSearch.toLowerCase()) || 
    c.phone.includes(contactSearch)
  );

  const selectContact = (contact: Contact) => {
    if (showContactPicker === 'c2c-from') setC2cFromNumber(contact.phone);
    else if (showContactPicker === 'c2c-to') setC2cToNumber(contact.phone);
    else if (showContactPicker === 'obd') {
      const current = obdNumbers.trim();
      setObdNumbers(current ? `${current}\n${contact.phone}` : contact.phone);
    }
    setShowContactPicker(null);
    setContactSearch('');
  };

  const formatDuration = (seconds: number) => { 
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60); 
    const secs = Math.round(seconds % 60); 
    return `${mins}:${secs.toString().padStart(2, '0')}`; 
  };

  const handleC2CCall = async () => {
    if (!c2cFromNumber || !c2cToNumber) { toast.error('Both phone numbers are required'); return; }
    setC2cCalling(true);
    try {
      const response = await fetch(`${API_BASE}/voice-in/c2c`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ fromNumber: c2cFromNumber, toNumber: c2cToNumber, enableRecording: c2cRecording }) 
      });
      const result = await response.json();
      if (result.callId) { 
        toast.success('Click-to-Call initiated!'); 
        setShowC2CModal(false); 
        setC2cFromNumber(''); 
        setC2cToNumber(''); 
        await loadData(); 
      } else { 
        toast.error(result.error || 'Failed to initiate call'); 
      }
    } catch (err) { toast.error('Failed to initiate call'); } finally { setC2cCalling(false); }
  };

  const handleOBDCreate = async () => {
    if (!obdNumbers || !obdCampaignName) { toast.error('Campaign name and numbers are required'); return; }
    
    // Validate audio source
    if (obdAudioType === 'tts' && !obdTtsText) { toast.error('Text-to-Speech content is required'); return; }
    if (obdAudioType === 'upload' && !obdAudioFile) { toast.error('Please select an audio file'); return; }
    if (obdAudioType === 's3' && !obdS3Path) { toast.error('S3 path is required'); return; }
    
    setObdCreating(true);
    try {
      const numbers = obdNumbers.split(/[\n,]/).map(n => n.trim()).filter(n => n.length >= 10);
      
      let audioUrl = '';
      
      // Handle audio upload if needed
      if (obdAudioType === 'upload' && obdAudioFile) {
        setObdUploading(true);
        const reader = new FileReader();
        const audioData = await new Promise<string>((resolve) => {
          reader.onload = () => resolve(reader.result as string);
          reader.readAsDataURL(obdAudioFile);
        });
        
        const uploadResponse = await fetch(`${API_BASE}/voice-in/obd/upload-audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audioUrl: audioData, fileName: obdAudioFile.name })
        });
        const uploadResult = await uploadResponse.json();
        if (!uploadResult.success) {
          toast.error(uploadResult.error || 'Failed to upload audio');
          setObdUploading(false);
          setObdCreating(false);
          return;
        }
        audioUrl = uploadResult.audioUrl;
        setObdUploading(false);
      } else if (obdAudioType === 's3') {
        audioUrl = obdS3Path.startsWith('s3://') ? obdS3Path : `s3://auth.wecare.digital/voice/${obdS3Path}`;
      } else if (obdAudioType === 'tts') {
        // TTS will be handled by backend
        audioUrl = `tts:${obdTtsText}`;
      }
      
      const response = await fetch(`${API_BASE}/voice-in/obd`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          campaignName: obdCampaignName, 
          contacts: numbers,
          audioUrl: audioUrl || undefined,
          audioType: obdAudioType,
          ttsText: obdAudioType === 'tts' ? obdTtsText : undefined
        }) 
      });
      const result = await response.json();
      if (result.campaignId || result.success) { 
        toast.success('OBD Campaign created!'); 
        setShowOBDModal(false); 
        setObdNumbers(''); 
        setObdCampaignName('');
        setObdAudioType('default');
        setObdTtsText('');
        setObdAudioFile(null);
        setObdS3Path('');
        await loadData(); 
      } else { 
        toast.error(result.error || 'Failed to create campaign'); 
      }
    } catch (err) { toast.error('Failed to create campaign'); } finally { setObdCreating(false); setObdUploading(false); }
  };

  // Filter and paginate data
  const filterBySearch = (items: any[], fields: string[]) => {
    if (!searchQuery) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(item => fields.some(f => item[f]?.toString().toLowerCase().includes(q)));
  };

  const filteredC2C = filterBySearch(c2cCalls, ['fromNumber', 'toNumber', 'status', 'correlationId']);
  const filteredOBD = filterBySearch(obdCampaigns, ['name', 'status', 'campaignId']);
  const filteredCDR = filterBySearch(cdrs, ['callerNumber', 'destinationNumber', 'callType', 'overallCallStatus']);

  const getCurrentData = () => {
    switch (activeTab) {
      case 'c2c': return filteredC2C;
      case 'obd': return filteredOBD;
      case 'cdr': return filteredCDR;
      default: return [];
    }
  };

  const currentData = getCurrentData();
  const totalPages = Math.ceil(currentData.length / ITEMS_PER_PAGE);
  const paginatedData = currentData.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const tabItems: TabItem[] = [
    { id: 'c2c', label: `Click-to-Call (${c2cCalls.length})` },
    { id: 'obd', label: `OBD Campaigns (${obdCampaigns.length})` },
    { id: 'cdr', label: `CDR Logs (${cdrs.length})` }
  ];

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice-IN | Airtel IQ | WECARE.DIGITAL" description="Voice calls via Airtel IQ" />
      <div className="voice-page">
        <div className="page-header">
          <div className="header-title">
            <PhoneIcon />
            <h2>Voice IN</h2>
            <span className="badge">C2C + OBD + CDR</span>
          </div>
          <div className="header-actions">
            <Button variant="primary" onClick={() => setShowC2CModal(true)}>+ Click-to-Call</Button>
            <Button variant="secondary" onClick={() => setShowOBDModal(true)}>+ OBD Campaign</Button>
            <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
          </div>
        </div>

        <div className="tabs-row">
          <Tabs items={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as 'c2c' | 'obd' | 'cdr')} />
        </div>

        <div className="controls-row">
          <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </div>

        <div className="content-area">
          {loading ? (
            <div className="loading-state">Loading...</div>
          ) : (
            <>
              {/* C2C Tab */}
              {activeTab === 'c2c' && (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>From Number</th>
                        <th>To Number</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th>Correlation ID</th>
                        <th>Recording</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as C2CCall[]).map(call => (
                        <tr key={call.callId}>
                          <td>{new Date(call.createdAt * 1000).toLocaleString()}</td>
                          <td className="phone-cell">{call.fromNumber}</td>
                          <td className="phone-cell">{call.toNumber}</td>
                          <td>{formatDuration(call.duration)}</td>
                          <td><span className={`status-badge ${call.status?.toLowerCase()}`}>{call.status}</span></td>
                          <td className="id-cell">{call.correlationId?.slice(0, 12)}...</td>
                          <td>{call.recordingUrl ? <a href={call.recordingUrl} target="_blank" rel="noopener noreferrer" className="recording-link">🎙️ Play</a> : '-'}</td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={7} className="empty-state">No C2C calls yet. Click "+ Click-to-Call" to initiate a call.</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}

              {/* OBD Tab */}
              {activeTab === 'obd' && (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Created</th>
                        <th>Campaign Name</th>
                        <th>Status</th>
                        <th>Total</th>
                        <th>Completed</th>
                        <th>Success</th>
                        <th>Failed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as OBDCampaign[]).map(campaign => (
                        <tr key={campaign.campaignId}>
                          <td>{new Date(campaign.createdAt * 1000).toLocaleString()}</td>
                          <td className="name-cell">{campaign.name}</td>
                          <td><span className={`status-badge ${campaign.status?.toLowerCase()}`}>{campaign.status}</span></td>
                          <td>{campaign.totalRecipients}</td>
                          <td>{campaign.completedCalls}</td>
                          <td className="success-cell">{campaign.successCalls}</td>
                          <td className="failed-cell">{campaign.failedCalls}</td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={7} className="empty-state">No OBD campaigns yet. Click "+ OBD Campaign" to create one.</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}

              {/* CDR Tab */}
              {activeTab === 'cdr' && (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Call Type</th>
                        <th>Caller</th>
                        <th>Destination</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th>Hangup</th>
                        <th>Recording</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as CDRRecord[]).map(cdr => (
                        <tr key={cdr.id}>
                          <td>{new Date(cdr.createdAt * 1000).toLocaleString()}</td>
                          <td><span className="type-badge">{cdr.callType}</span></td>
                          <td className="phone-cell">{cdr.callerNumber}</td>
                          <td className="phone-cell">{cdr.destinationNumber}</td>
                          <td>{formatDuration(cdr.durationSec)}</td>
                          <td><span className={`status-badge ${cdr.overallCallStatus?.toLowerCase()}`}>{cdr.overallCallStatus}</span></td>
                          <td>{cdr.hangupStatus}</td>
                          <td>{cdr.recordingURL ? <a href={cdr.recordingURL} target="_blank" rel="noopener noreferrer" className="recording-link">🎙️ Play</a> : '-'}</td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={8} className="empty-state">No CDR records yet. CDRs are received via webhook from Airtel.</td></tr>}
                    </tbody>
                  </table>
                  <div className="webhook-info">
                    <strong>CDR Webhook URL:</strong>
                    <code>{API_BASE}/voice-cdr-webhook</code>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* C2C Modal */}
      {showC2CModal && (
        <div className="modal-overlay" onClick={() => setShowC2CModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Click-to-Call (C2C)</h3>
            <p className="modal-desc">Connect two parties on a call. First participant will be called, then connected to the second.</p>
            <div className="form-group">
              <label>From Number (First Participant) *</label>
              <div className="input-with-btn">
                <input type="tel" value={c2cFromNumber} onChange={e => setC2cFromNumber(e.target.value)} placeholder="10-digit mobile number" />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('c2c-from')}>📇 Contacts</button>
              </div>
            </div>
            <div className="form-group">
              <label>To Number (Second Participant) *</label>
              <div className="input-with-btn">
                <input type="tel" value={c2cToNumber} onChange={e => setC2cToNumber(e.target.value)} placeholder="10-digit mobile number" />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('c2c-to')}>📇 Contacts</button>
              </div>
            </div>
            <div className="form-group checkbox-group"><label><input type="checkbox" checked={c2cRecording} onChange={e => setC2cRecording(e.target.checked)} />Enable Call Recording</label></div>
            <div className="info-box"><strong>Airtel C2C Configuration:</strong><ul><li>Caller ID: 8047311032</li><li>API: iqvoice.airtel.in (Kong HMAC Auth)</li><li>App ID: WECAREDIG_fD4BKqUbC8k90jNrPR0n</li></ul></div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowC2CModal(false)}>Cancel</Button><Button variant="primary" onClick={handleC2CCall} loading={c2cCalling} disabled={!c2cFromNumber || !c2cToNumber}>Initiate Call</Button></div>
          </div>
        </div>
      )}

      {/* OBD Modal */}
      {showOBDModal && (
        <div className="modal-overlay" onClick={() => setShowOBDModal(false)}>
          <div className="modal-content obd-modal" onClick={e => e.stopPropagation()}>
            <h3>Create OBD Campaign</h3>
            <p className="modal-desc">Outbound Dialer campaign to call multiple numbers with voice message.</p>
            
            <div className="form-group">
              <label>Campaign Name *</label>
              <input type="text" value={obdCampaignName} onChange={e => setObdCampaignName(e.target.value)} placeholder="e.g. Promo Campaign Feb 2026" />
            </div>
            
            <div className="form-group">
              <label>Phone Numbers * (one per line or comma-separated)</label>
              <div className="textarea-with-btn">
                <textarea value={obdNumbers} onChange={e => setObdNumbers(e.target.value)} placeholder="9876543210&#10;9876543211&#10;9876543212" rows={4} />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('obd')}>📇 Add from Contacts</button>
              </div>
              <small>{obdNumbers.split(/[\n,]/).filter(n => n.trim().length >= 10).length} valid numbers</small>
            </div>
            
            <div className="form-group">
              <label>Voice Message Source *</label>
              <div className="audio-options">
                <label className={`audio-option ${obdAudioType === 'default' ? 'selected' : ''}`}>
                  <input type="radio" name="audioType" checked={obdAudioType === 'default'} onChange={() => setObdAudioType('default')} />
                  <span className="option-icon">🔔</span>
                  <span className="option-text">Default Jingle</span>
                </label>
                <label className={`audio-option ${obdAudioType === 'tts' ? 'selected' : ''}`}>
                  <input type="radio" name="audioType" checked={obdAudioType === 'tts'} onChange={() => setObdAudioType('tts')} />
                  <span className="option-icon">🗣️</span>
                  <span className="option-text">Text-to-Speech</span>
                </label>
                <label className={`audio-option ${obdAudioType === 'upload' ? 'selected' : ''}`}>
                  <input type="radio" name="audioType" checked={obdAudioType === 'upload'} onChange={() => setObdAudioType('upload')} />
                  <span className="option-icon">📤</span>
                  <span className="option-text">Upload Audio</span>
                </label>
                <label className={`audio-option ${obdAudioType === 's3' ? 'selected' : ''}`}>
                  <input type="radio" name="audioType" checked={obdAudioType === 's3'} onChange={() => setObdAudioType('s3')} />
                  <span className="option-icon">☁️</span>
                  <span className="option-text">S3 Audio</span>
                </label>
              </div>
            </div>
            
            {obdAudioType === 'tts' && (
              <div className="form-group">
                <label>Text-to-Speech Content *</label>
                <textarea value={obdTtsText} onChange={e => setObdTtsText(e.target.value)} placeholder="Enter the message to be converted to speech..." rows={3} />
                <small>{obdTtsText.length} characters</small>
              </div>
            )}
            
            {obdAudioType === 'upload' && (
              <div className="form-group">
                <label>Upload Audio File * (WAV/MP3)</label>
                <input type="file" accept=".wav,.mp3,audio/*" onChange={e => setObdAudioFile(e.target.files?.[0] || null)} className="file-input" />
                {obdAudioFile && <small>Selected: {obdAudioFile.name} ({(obdAudioFile.size / 1024).toFixed(1)} KB)</small>}
              </div>
            )}
            
            {obdAudioType === 's3' && (
              <div className="form-group">
                <label>S3 Audio Path *</label>
                <input type="text" value={obdS3Path} onChange={e => setObdS3Path(e.target.value)} placeholder="filename.wav or s3://auth.wecare.digital/voice/filename.wav" />
                <small>Base path: s3://auth.wecare.digital/voice/</small>
              </div>
            )}
            
            <div className="info-box">
              <strong>Airtel OBD Configuration:</strong>
              <ul>
                <li>Caller ID: 8040761117</li>
                <li>API: openapi.airtel.in / iqtelephony.airtel.in</li>
                <li>Call Flow ID: dfbeda76-f641-420f-95e7-b78d562a941f</li>
                <li>Retry: 2 attempts (on busy/no-answer)</li>
              </ul>
            </div>
            
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowOBDModal(false)}>Cancel</Button>
              <Button variant="primary" onClick={handleOBDCreate} loading={obdCreating || obdUploading} disabled={!obdNumbers || !obdCampaignName}>
                {obdUploading ? 'Uploading...' : 'Create Campaign'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Contact Picker Modal */}
      {showContactPicker && (
        <div className="modal-overlay" onClick={() => setShowContactPicker(null)}>
          <div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
            <h3>Select Contact</h3>
            <input type="text" placeholder="Search contacts..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
            <div className="contact-list">
              {loadingContacts ? (
                <div className="loading-contacts">Loading contacts...</div>
              ) : filteredContacts.length === 0 ? (
                <div className="no-contacts">No contacts found</div>
              ) : (
                filteredContacts.slice(0, 50).map(contact => (
                  <div key={contact.contactId} className="contact-row" onClick={() => selectContact(contact)}>
                    <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                    <div className="contact-details">
                      <div className="contact-name">{contact.name}</div>
                      <div className="contact-phone">{contact.phone}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setShowContactPicker(null)}>Cancel</Button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .voice-page { min-height: calc(100vh - 60px); background: #f0fdf4; padding: 20px; }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header-title { display: flex; align-items: center; gap: 12px; color: #065f46; }
        .header-title h2 { margin: 0; font-size: 1.25rem; }
        .badge { background: #10b981; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 500; }
        .header-actions { display: flex; gap: 8px; }
        .tabs-row { background: #fff; border-radius: 8px; padding: 0 16px; margin-bottom: 16px; border: 1px solid #d1fae5; }
        .controls-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 16px; }
        .search-input { padding: 10px 14px; border: 1px solid #a7f3d0; border-radius: 8px; width: 300px; font-size: 14px; }
        .search-input:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .content-area { background: #fff; border-radius: 12px; border: 1px solid #d1fae5; overflow: hidden; }
        .loading-state { padding: 60px; text-align: center; color: #047857; }
        .table-container { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ecfdf5; font-size: 13px; }
        th { background: #ecfdf5; font-weight: 600; color: #065f46; white-space: nowrap; }
        tr:hover { background: #f0fdf4; }
        .phone-cell { font-family: monospace; color: #047857; }
        .id-cell { font-family: monospace; font-size: 11px; color: #6b7280; }
        .name-cell { font-weight: 500; color: #065f46; }
        .success-cell { color: #059669; font-weight: 500; }
        .failed-cell { color: #dc2626; font-weight: 500; }
        .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; background: #f5f5f5; color: #6b7280; }
        .status-badge.initiated, .status-badge.completed, .status-badge.success, .status-badge.active { background: #d1fae5; color: #059669; }
        .status-badge.failed, .status-badge.error { background: #fee2e2; color: #dc2626; }
        .status-badge.pending, .status-badge.in_progress { background: #fef3c7; color: #92400e; }
        .type-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; background: #e0e7ff; color: #4338ca; }
        .recording-link { color: #10b981; text-decoration: none; font-size: 12px; }
        .recording-link:hover { text-decoration: underline; }
        .empty-state { text-align: center; color: #047857; padding: 40px !important; }
        .webhook-info { padding: 16px; background: #ecfdf5; border-top: 1px solid #d1fae5; }
        .webhook-info strong { display: block; margin-bottom: 8px; color: #065f46; font-size: 13px; }
        .webhook-info code { display: block; background: #fff; padding: 10px; border-radius: 6px; font-size: 12px; color: #047857; border: 1px solid #d1fae5; word-break: break-all; }
        
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 100%; max-width: 500px; max-height: 90vh; overflow-y: auto; }
        .modal-content.obd-modal { max-width: 560px; }
        .modal-content h3 { margin: 0 0 8px 0; color: #065f46; }
        .modal-desc { margin: 0 0 20px 0; color: #047857; font-size: 14px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #374151; }
        .form-group input, .form-group textarea { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; font-family: inherit; }
        .form-group input:focus, .form-group textarea:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .form-group small { display: block; margin-top: 4px; font-size: 12px; color: #6b7280; }
        .file-input { padding: 8px; background: #f9fafb; }
        .audio-options { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .audio-option { display: flex; align-items: center; gap: 10px; padding: 12px; border: 2px solid #e5e7eb; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
        .audio-option:hover { border-color: #a7f3d0; background: #f0fdf4; }
        .audio-option.selected { border-color: #10b981; background: #ecfdf5; }
        .audio-option input[type="radio"] { display: none; }
        .option-icon { font-size: 20px; }
        .option-text { font-size: 13px; font-weight: 500; color: #374151; }
        .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .checkbox-group input[type="checkbox"] { width: 18px; height: 18px; accent-color: #10b981; }
        .info-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-bottom: 16px; }
        .info-box strong { display: block; margin-bottom: 8px; color: #166534; font-size: 13px; }
        .info-box ul { margin: 0; padding-left: 20px; font-size: 13px; color: #166534; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }
        
        .input-with-btn { display: flex; gap: 8px; }
        .input-with-btn input { flex: 1; }
        .textarea-with-btn { display: flex; flex-direction: column; gap: 8px; }
        .fetch-btn { padding: 8px 12px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46; font-size: 12px; cursor: pointer; white-space: nowrap; transition: all 0.15s; }
        .fetch-btn:hover { background: #d1fae5; }
        
        .contact-picker { max-width: 400px; }
        .contact-search { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; margin-bottom: 12px; }
        .contact-search:focus { outline: none; border-color: #10b981; }
        .contact-list { max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
        .contact-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #f3f4f6; transition: background 0.15s; }
        .contact-row:hover { background: #f0fdf4; }
        .contact-row:last-child { border-bottom: none; }
        .contact-avatar { width: 36px; height: 36px; background: #10b981; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 14px; }
        .contact-details { flex: 1; }
        .contact-name { font-size: 14px; font-weight: 500; color: #065f46; }
        .contact-phone { font-size: 12px; color: #6b7280; font-family: monospace; }
        .loading-contacts, .no-contacts { padding: 30px; text-align: center; color: #6b7280; }
      `}</style>
    </Layout>
  );
};

const PhoneIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
  </svg>
);

export default VoiceInInbox;
