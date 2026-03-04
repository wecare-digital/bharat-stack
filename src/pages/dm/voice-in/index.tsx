/**
 * Voice-IN Page - Airtel IQ Voice Integration
 * Tabs: Click-to-Call (C2C), OBD Campaigns, Call Detail Records (CDR)
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { useToastContext } from '../../../contexts/ToastContext';
import { useConfirm } from '../../../contexts/ConfirmContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
interface Contact { contactId: string; name: string; phone: string; }
interface C2CCall { callId: string; fromNumber: string; toNumber: string; callerId: string; status: string; duration: number; recordingUrl?: string; correlationId?: string; createdAt: number; }
interface OBDCampaign { id: string; airtelCampaignId: string; campaignName: string; status: string; audioUrl: string; contactCount?: number; createdAt: number; }
interface CDRRecord { id: string; vmSessionId: string; clientCorrelationId: string; callType: string; overallCallStatus: string; callerNumber: string; destinationNumber: string; durationSec: number; conversationDurationSec: number; hangupStatus: string; recordingURL?: string; circleNameCaller?: string; operatorNameCaller?: string; createdAt: number; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';
const ITEMS_PER_PAGE = 20;

const VoiceInPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [activeTab, setActiveTab] = useState<'c2c' | 'obd' | 'cdr'>('c2c');
  const [c2cCalls, setC2cCalls] = useState<C2CCall[]>([]);
  const [obdCampaigns, setObdCampaigns] = useState<OBDCampaign[]>([]);
  const [cdrs, setCdrs] = useState<CDRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  
  const [showC2CModal, setShowC2CModal] = useState(false);
  const [c2cFromNumber, setC2cFromNumber] = useState('');
  const [c2cToNumber, setC2cToNumber] = useState('');
  const [c2cRecording, setC2cRecording] = useState(true);
  const [c2cCalling, setC2cCalling] = useState(false);
  
  const [showOBDModal, setShowOBDModal] = useState(false);
  const [obdNumbers, setObdNumbers] = useState('');
  const [obdCampaignName, setObdCampaignName] = useState('');
  const [obdCreating, setObdCreating] = useState(false);
  const [obdVariables, setObdVariables] = useState<{[phone: string]: {[key: string]: string}}>({});
  const [obdVarNames, setObdVarNames] = useState<string[]>([]);

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showContactPicker, setShowContactPicker] = useState<'c2c-from' | 'c2c-to' | 'obd' | null>(null);
  const [contactSearch, setContactSearch] = useState('');
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [cdrDirectionFilter, setCdrDirectionFilter] = useState<'all' | 'INBOUND' | 'OUTBOUND'>('all');
  
  const toast = useToastContext();
  const confirm = useConfirm();

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
        fetch(`${API_BASE}/voice-cdr-read`).then(r => r.json()).catch(() => ({ records: [] }))
      ]);
      setC2cCalls(c2cResponse.calls || []);
      setObdCampaigns(obdResponse.campaigns || []);
      setCdrs(cdrResponse.records || []);
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
    
    setObdCreating(true);
    try {
      const numbers = obdNumbers.split(/[\n,]/).map(n => n.trim()).filter(n => n.length >= 10);

      const response = await fetch(`${API_BASE}/voice-in/obd`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          campaignName: obdCampaignName, 
          contacts: numbers,
          variables: Object.keys(obdVariables).length > 0 ? obdVariables : undefined
        }) 
      });
      const result = await response.json();
      if (result.campaignId || result.success) { 
        toast.success('OBD Campaign created!'); 
        setShowOBDModal(false); 
        setObdNumbers(''); 
        setObdCampaignName('');
        setObdVariables({});
        setObdVarNames([]);
        await loadData(); 
      } else { 
        toast.error(result.error || 'Failed to create campaign'); 
      }
    } catch (err) { toast.error('Failed to create campaign'); } finally { setObdCreating(false); }
  };

  const addOBDVariable = () => {
    const varName = prompt('Enter variable name (e.g., name, amount):');
    if (varName && /^\w+$/.test(varName) && !obdVarNames.includes(varName)) {
      setObdVarNames(prev => [...prev, varName]);
    }
  };

  const handleClearLogs = async (type: 'c2c' | 'obd' | 'cdr') => {
    if (!(await confirm(`Clear all ${type.toUpperCase()} logs? This cannot be undone.`))) return;
    setClearing(true);
    try {
      const endpoint = type === 'cdr' ? 'voice-cdr-webhook' : `voice-in/${type}`; // CDR clear goes to webhook handler which owns the data
      const response = await fetch(`${API_BASE}/${endpoint}/clear-logs`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clearAll: true, hardDelete: true })
      });
      const result = await response.json();
      if (result.success) {
        setTimeout(() => toast.success(`Cleared ${result.deletedCount || 0} ${type.toUpperCase()} logs`), 100);
        await loadData();
      } else {
        setTimeout(() => toast.error(result.error || 'Failed to clear logs'), 100);
      }
    } catch (err) { 
      console.error('Clear logs error:', err);
      setTimeout(() => toast.error('Failed to clear logs'), 100); 
    } finally { setClearing(false); }
  };

  const filterBySearch = (items: any[], fields: string[]) => {
    if (!searchQuery) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(item => fields.some(f => item[f]?.toString().toLowerCase().includes(q)));
  };

  const filteredC2C = filterBySearch(c2cCalls, ['fromNumber', 'toNumber', 'status', 'correlationId']);
  const filteredOBD = filterBySearch(obdCampaigns, ['campaignName', 'status', 'airtelCampaignId']);
  const filteredCDR = filterBySearch(cdrs, ['callerNumber', 'destinationNumber', 'callType', 'overallCallStatus'])
    .filter(cdr => cdrDirectionFilter === 'all' || cdr.callType === cdrDirectionFilter);

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
    { id: 'c2c', label: `C2C (${c2cCalls.length})` },
    { id: 'obd', label: `OBD (${obdCampaigns.length})` },
    { id: 'cdr', label: `CDR (${cdrs.length})` }
  ];

  const pageContent = (
    <>
      <div className="voice-page">
        <div className="page-header">
          <div className="header-title">
            <PhoneIcon />
            <h2>Voice IN</h2>
            <span className="badge">C2C + OBD + CDR</span>
          </div>
          <div className="header-actions">
            <Button variant="primary" onClick={() => setShowC2CModal(true)}>C2C</Button>
            <Button variant="secondary" onClick={() => setShowOBDModal(true)}>OBD</Button>
            <Button variant="secondary" onClick={() => handleClearLogs(activeTab)} disabled={clearing} loading={clearing}>Clear</Button>
            <Button variant="secondary" icon="refresh" onClick={loadData} disabled={loading} loading={loading}>Refresh</Button>
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
              {activeTab === 'c2c' && (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th className="hide-mobile">Correlation ID</th>
                        <th>Recording</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as C2CCall[]).map(call => (
                        <tr key={call.callId}>
                          <td className="time-cell">{new Date(call.createdAt * 1000).toLocaleString()}</td>
                          <td className="phone-cell">{call.fromNumber}</td>
                          <td className="phone-cell">{call.toNumber}</td>
                          <td>{formatDuration(call.duration)}</td>
                          <td><span className={`status-badge ${call.status?.toLowerCase()}`}>{call.status}</span></td>
                          <td className="id-cell hide-mobile">{call.correlationId?.slice(0, 12)}...</td>
                          <td>{call.recordingUrl ? <a href={call.recordingUrl} target="_blank" rel="noopener noreferrer" className="recording-link">Rec</a> : '-'}</td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={7} className="empty-state">No C2C calls yet</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'obd' && (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Created</th>
                        <th>Campaign</th>
                        <th>Airtel ID</th>
                        <th>Contacts</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as OBDCampaign[]).map(campaign => (
                        <tr key={campaign.id}>
                          <td className="time-cell">{new Date(campaign.createdAt * 1000).toLocaleString()}</td>
                          <td className="name-cell">{campaign.campaignName}</td>
                          <td className="id-cell">{campaign.airtelCampaignId?.slice(0, 12)}...</td>
                          <td>{campaign.contactCount || '-'}</td>
                          <td><span className={`status-badge ${campaign.status?.toLowerCase()}`}>{campaign.status}</span></td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={5} className="empty-state">No OBD campaigns yet</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'cdr' && (
                <div className="table-container">
                  <div style={{ padding: '8px 12px', background: '#ecfdf5', borderBottom: '1px solid #d1fae5', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#065f46', fontWeight: 500 }}>Direction:</span>
                    {(['all', 'INBOUND', 'OUTBOUND'] as const).map(dir => (
                      <button key={dir} onClick={() => setCdrDirectionFilter(dir)} style={{ padding: '3px 10px', borderRadius: '4px', border: '1px solid', borderColor: cdrDirectionFilter === dir ? '#059669' : '#d1fae5', background: cdrDirectionFilter === dir ? '#d1fae5' : '#fff', color: '#065f46', fontSize: '11px', cursor: 'pointer', fontWeight: cdrDirectionFilter === dir ? 600 : 400 }}>
                        {dir === 'all' ? 'All' : dir}
                      </button>
                    ))}
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Caller</th>
                        <th>Destination</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th className="hide-mobile">Hangup</th>
                        <th>Rec</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paginatedData as CDRRecord[]).map(cdr => (
                        <tr key={cdr.id}>
                          <td className="time-cell">{new Date(cdr.createdAt * 1000).toLocaleString()}</td>
                          <td><span className="type-badge">{cdr.callType}</span></td>
                          <td className="phone-cell">{cdr.callerNumber}</td>
                          <td className="phone-cell">{cdr.destinationNumber}</td>
                          <td>{formatDuration(cdr.durationSec)}</td>
                          <td><span className={`status-badge ${cdr.overallCallStatus?.toLowerCase()}`}>{cdr.overallCallStatus}</span></td>
                          <td className="hide-mobile">{cdr.hangupStatus}</td>
                          <td>{cdr.recordingURL ? <a href={cdr.recordingURL} target="_blank" rel="noopener noreferrer" className="recording-link">Rec</a> : '-'}</td>
                        </tr>
                      ))}
                      {paginatedData.length === 0 && <tr><td colSpan={8} className="empty-state">No CDR records yet</td></tr>}
                    </tbody>
                  </table>
                  <div className="webhook-info">
                    <strong>CDR Webhook (Airtel → Us):</strong>
                    <code>{API_BASE}/voice-cdr-webhook</code>
                    <div style={{ marginTop: '4px', fontSize: '11px', color: '#6b7280' }}>Receives CDRs from Airtel for all call types: direct inbound, C2C, and OBD campaigns</div>
                    <strong style={{ marginTop: '8px', display: 'block' }}>CDR Read API (Dashboard):</strong>
                    <code>{API_BASE}/voice-cdr-read</code>
                    <div style={{ marginTop: '4px', fontSize: '11px', color: '#6b7280' }}>Read CDRs with filters, stats, and dashboard aggregations (?dashboard=true)</div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {showC2CModal && (
        <div className="modal-overlay" onClick={() => setShowC2CModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Click-to-Call (C2C)</h3>
            <p className="modal-desc">Connect two parties on a call.</p>
            <div className="form-group">
              <label>From Number *</label>
              <div className="input-with-btn">
                <input type="tel" value={c2cFromNumber} onChange={e => setC2cFromNumber(e.target.value)} placeholder="10-digit mobile" />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('c2c-from')}>Contacts</button>
              </div>
            </div>
            <div className="form-group">
              <label>To Number *</label>
              <div className="input-with-btn">
                <input type="tel" value={c2cToNumber} onChange={e => setC2cToNumber(e.target.value)} placeholder="10-digit mobile" />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('c2c-to')}>Contacts</button>
              </div>
            </div>
            <div className="form-group checkbox-group"><label><input type="checkbox" checked={c2cRecording} onChange={e => setC2cRecording(e.target.checked)} />Enable Recording</label></div>
            <div className="info-box"><strong>Config:</strong> Caller ID: 8047311032 | App: WECAREDIG_fD4BKqUbC8k90jNrPR0n</div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowC2CModal(false)}>Cancel</Button><Button variant="primary" onClick={handleC2CCall} loading={c2cCalling} disabled={!c2cFromNumber || !c2cToNumber}>Call</Button></div>
          </div>
        </div>
      )}

      {showOBDModal && (
        <div className="modal-overlay" onClick={() => setShowOBDModal(false)}>
          <div className="modal-content obd-modal" onClick={e => e.stopPropagation()}>
            <h3>Create OBD Campaign</h3>
            <p className="modal-desc">Outbound Dialer campaign with default Airtel jingle.</p>
            <div className="form-group">
              <label>Campaign Name *</label>
              <input type="text" value={obdCampaignName} onChange={e => setObdCampaignName(e.target.value)} placeholder="e.g. Promo Feb 2026" />
            </div>
            <div className="form-group">
              <label>Phone Numbers *</label>
              <div className="textarea-with-btn">
                <textarea value={obdNumbers} onChange={e => setObdNumbers(e.target.value)} placeholder="One per line or comma-separated" rows={3} />
                <button type="button" className="fetch-btn" onClick={() => setShowContactPicker('obd')}>Contacts</button>
              </div>
              <small>{obdNumbers.split(/[\n,]/).filter(n => n.trim().length >= 10).length} valid</small>
            </div>
            {obdVarNames.length > 0 && (
              <div className="form-group">
                <label>Variables</label>
                <div className="var-list">
                  {obdVarNames.map(v => (
                    <span key={v} className="var-tag">{v} <button onClick={() => setObdVarNames(prev => prev.filter(x => x !== v))}>×</button></span>
                  ))}
                </div>
                <small>Variables will be mapped from CSV columns</small>
              </div>
            )}
            <div className="form-group">
              <button type="button" className="fetch-btn var-btn" onClick={addOBDVariable}>+ Variable</button>
            </div>
            <div className="info-box">
              <strong>Airtel OBD:</strong> Info-Only call flow | 16bits 8000Hz Mono audio | TRANSACTIONAL<br/>
              <strong>Config:</strong> Caller ID: 8040761117 | Flow: dfbeda76-f641-420f-95e7-b78d562a941f
            </div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowOBDModal(false)}>Cancel</Button><Button variant="primary" onClick={handleOBDCreate} loading={obdCreating} disabled={!obdNumbers || !obdCampaignName}>Create</Button></div>
          </div>
        </div>
      )}

      {showContactPicker && (
        <div className="modal-overlay" onClick={() => setShowContactPicker(null)}>
          <div className="modal-content contact-picker" onClick={e => e.stopPropagation()}>
            <h3>Select Contact</h3>
            <input type="text" placeholder="Search..." value={contactSearch} onChange={e => setContactSearch(e.target.value)} className="contact-search" />
            <div className="contact-list">
              {loadingContacts ? <div className="loading-contacts">Loading...</div> : filteredContacts.length === 0 ? <div className="no-contacts">No contacts</div> : (
                filteredContacts.slice(0, 50).map(contact => (
                  <div key={contact.contactId} className="contact-row" onClick={() => selectContact(contact)}>
                    <div className="contact-avatar">{contact.name.charAt(0).toUpperCase()}</div>
                    <div className="contact-details"><div className="contact-name">{contact.name}</div><div className="contact-phone">{contact.phone}</div></div>
                  </div>
                ))
              )}
            </div>
            <div className="modal-actions"><Button variant="secondary" onClick={() => setShowContactPicker(null)}>Cancel</Button></div>
          </div>
        </div>
      )}

      <style jsx>{`
        .voice-page { height: 100%; display: flex; flex-direction: column; background: #ecfdf5; padding: 16px; box-sizing: border-box; overflow: hidden; }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
        .header-title { display: flex; align-items: center; gap: 10px; color: #065f46; flex-wrap: wrap; }
        .header-title h2 { margin: 0; font-size: 1.1rem; }
        .badge { background: #059669; color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 500; }
        .header-actions { display: flex; gap: 6px; flex-wrap: wrap; }
        .tabs-row { background: #fff; border-radius: 8px; padding: 0 12px; margin-bottom: 12px; border: 1px solid #d1fae5; flex-shrink: 0; overflow-x: auto; }
        .controls-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; flex-shrink: 0; }
        .search-input { padding: 8px 12px; border: 1px solid #a7f3d0; border-radius: 8px; width: 100%; max-width: 280px; font-size: 14px; }
        .search-input:focus { outline: none; border-color: #059669; }
        .content-area { flex: 1; background: #fff; border-radius: 12px; border: 1px solid #d1fae5; overflow: auto; min-height: 0; }
        .loading-state { padding: 40px; text-align: center; color: #047857; }
        .table-container { min-width: 100%; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecfdf5; font-size: 12px; white-space: nowrap; }
        th { background: #ecfdf5; font-weight: 600; color: #065f46; position: sticky; top: 0; z-index: 1; }
        tr:hover { background: #ecfdf5; }
        .time-cell { font-size: 11px; }
        .phone-cell { font-family: monospace; color: #047857; font-size: 11px; }
        .id-cell { font-family: monospace; font-size: 10px; color: #6b7280; }
        .name-cell { font-weight: 500; color: #065f46; max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
        .success-cell { color: #059669; font-weight: 500; }
        .failed-cell { color: #059669; font-weight: 500; }
        .status-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 500; background: #f5f5f5; color: #6b7280; }
        .status-badge.initiated, .status-badge.completed, .status-badge.success, .status-badge.active { background: #d1fae5; color: #059669; }
        .status-badge.failed, .status-badge.error { background: #ECFDF5; color: #059669; }
        .status-badge.pending, .status-badge.in_progress { background: #ecfdf5; color: #059669; }
        .type-badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; background: #ecfdf5; color: #059669; }
        .recording-link { color: #059669; text-decoration: none; }
        .empty-state { text-align: center; color: #047857; padding: 30px !important; }
        .webhook-info { padding: 12px; background: #ecfdf5; border-top: 1px solid #d1fae5; font-size: 12px; }
        .webhook-info strong { color: #065f46; }
        .webhook-info code { display: block; background: #fff; padding: 8px; border-radius: 6px; font-size: 11px; color: #047857; border: 1px solid #d1fae5; margin-top: 6px; word-break: break-all; white-space: normal; }

        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
        .modal-content { background: #fff; border-radius: 12px; padding: 20px; width: 100%; max-width: 440px; max-height: 90vh; overflow-y: auto; }
        .modal-content.obd-modal { max-width: 480px; }
        .modal-content h3 { margin: 0 0 6px 0; color: #065f46; font-size: 1rem; }
        .modal-desc { margin: 0 0 16px 0; color: #047857; font-size: 13px; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 5px; color: #374151; }
        .form-group input, .form-group textarea { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
        .form-group input:focus, .form-group textarea:focus { outline: none; border-color: #059669; }
        .form-group small { display: block; margin-top: 3px; font-size: 11px; color: #9ca3af; }
        .file-input { padding: 6px; background: #f9fafb; }
        .audio-options { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .audio-option { display: flex; align-items: center; gap: 8px; padding: 10px; border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; font-size: 12px; }
        .audio-option:hover { border-color: #a7f3d0; background: #ecfdf5; }
        .audio-option.selected { border-color: #059669; background: #ecfdf5; }
        .audio-option input[type="radio"] { display: none; }
        .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; }
        .checkbox-group input[type="checkbox"] { width: 16px; height: 16px; accent-color: #059669; }
        .info-box { background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 10px; margin-bottom: 14px; font-size: 12px; color: #065f46; }
        .info-box strong { color: #065f46; }
        .info-box.warning { background: #ecfdf5; border-color: #a7f3d0; color: #065f46; }
        .info-box.warning strong { color: #059669; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
        .input-with-btn { display: flex; gap: 6px; }
        .input-with-btn input { flex: 1; }
        .textarea-with-btn { display: flex; flex-direction: column; gap: 6px; }
        .fetch-btn { padding: 8px 10px; background: #ecfdf5; border: 1px solid #059669; border-radius: 8px; color: #065f46; font-size: 12px; cursor: pointer; white-space: nowrap; }
        .fetch-btn:hover { background: #d1fae5; }
        .var-btn { background: #ecfdf5; border-color: #059669; color: #059669; }
        .var-btn:hover { background: #d1fae5; }
        .var-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
        .var-tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 8px; background: #ecfdf5; border-radius: 4px; font-size: 11px; color: #059669; }
        .var-tag button { background: none; border: none; color: #059669; cursor: pointer; font-size: 14px; padding: 0; line-height: 1; }
        .contact-picker { max-width: 360px; }
        .contact-search { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; margin-bottom: 10px; box-sizing: border-box; }
        .contact-list { max-height: 250px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
        .contact-row { display: flex; align-items: center; gap: 10px; padding: 8px 10px; cursor: pointer; border-bottom: 1px solid #f3f4f6; }
        .contact-row:hover { background: #ecfdf5; }
        .contact-row:last-child { border-bottom: none; }
        .contact-avatar { width: 32px; height: 32px; background: #059669; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; flex-shrink: 0; }
        .contact-details { flex: 1; min-width: 0; }
        .contact-name { font-size: 13px; font-weight: 500; color: #065f46; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .contact-phone { font-size: 11px; color: #6b7280; font-family: monospace; }
        .loading-contacts, .no-contacts { padding: 24px; text-align: center; color: #6b7280; font-size: 13px; }
        
        @media (max-width: 768px) {
          .voice-page { padding: 12px; }
          .page-header { flex-direction: column; align-items: flex-start; }
          .header-actions { width: 100%; justify-content: flex-start; }
          .controls-row { flex-direction: column; align-items: stretch; }
          .search-input { max-width: 100%; }
          .hide-mobile { display: none; }
          th, td { padding: 8px 6px; font-size: 11px; }
          .phone-cell { font-size: 10px; }
          .modal-content { padding: 16px; max-height: 85vh; }
          .audio-options { grid-template-columns: 1fr 1fr; }
        }
        
        @media (max-width: 480px) {
          .voice-page { padding: 8px; }
          .header-title h2 { font-size: 1rem; }
          .badge { font-size: 9px; padding: 2px 6px; }
          th, td { padding: 6px 4px; font-size: 10px; }
          .time-cell { max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
          .modal-content { padding: 14px; }
          .audio-options { grid-template-columns: 1fr; }
        }
      `}</style>
    </>
  );

  if (embedded) return pageContent;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="Voice-IN | Airtel IQ | WECARE.DIGITAL" description="Voice calls via Airtel IQ" />
      {pageContent}
    </Layout>
  );
};

const PhoneIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
  </svg>
);

export default VoiceInPage;