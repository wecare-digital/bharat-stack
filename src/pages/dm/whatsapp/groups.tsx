/**
 * WhatsApp Groups Management
 * Create and manage WhatsApp Business groups
 * Ref: https://developers.facebook.com/docs/whatsapp/groups
 */
import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import { useConfirm } from '../../../contexts/ConfirmContext';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }

const WABAS = [
  { id: WHATSAPP_PHONES.primary.wabaId, phoneId: WHATSAPP_PHONES.primary.id, metaId: '960395407161423', name: WHATSAPP_PHONES.primary.name, display: WHATSAPP_PHONES.primary.display },
  { id: WHATSAPP_PHONES.secondary.wabaId, phoneId: WHATSAPP_PHONES.secondary.id, metaId: '997428863451102', name: WHATSAPP_PHONES.secondary.name, display: WHATSAPP_PHONES.secondary.display },
];

const GroupsPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const toast = useToastContext();
  const confirm = useConfirm();
  const [selectedWaba, setSelectedWaba] = useState(WABAS[0]);
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newSubject, setNewSubject] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newParticipants, setNewParticipants] = useState('');
  const [creating, setCreating] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<any>(null);
  const [groupDetail, setGroupDetail] = useState<any>(null);
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [addPhone, setAddPhone] = useState('');

  const loadGroups = async (waba: typeof WABAS[0]) => {
    setLoading(true);
    try {
      const data = await api.listGroups(waba.id);
      setGroups(data);
    } catch (e) { toast.error('Failed to load groups'); }
    setLoading(false);
  };

  useEffect(() => { loadGroups(selectedWaba); }, [selectedWaba]);

  const handleCreate = async () => {
    if (!newSubject.trim()) return;
    setCreating(true);
    try {
      const participants = newParticipants.split(',').map(p => p.trim()).filter(Boolean);
      const result = await api.createGroup(selectedWaba.metaId, newSubject.trim(), newDesc.trim() || undefined, participants.length ? participants : undefined);
      if (result) { toast.success('Group created'); setShowCreate(false); setNewSubject(''); setNewDesc(''); setNewParticipants(''); loadGroups(selectedWaba); }
      else toast.error('Create failed');
    } catch (e) { toast.error('Create failed'); }
    setCreating(false);
  };

  const handleDelete = async (groupId: string) => {
    if (!(await confirm('Delete this group?'))) return;
    const ok = await api.deleteGroup(groupId);
    if (ok) { toast.success('Group deleted'); setSelectedGroup(null); loadGroups(selectedWaba); }
    else toast.error('Delete failed');
  };

  const viewDetails = async (group: any) => {
    setSelectedGroup(group);
    const detail = await api.getGroup(group.id);
    setGroupDetail(detail);
  };

  const handleSendMessage = async () => {
    if (!selectedGroup || !msgText.trim()) return;
    setSending(true);
    const result = await api.sendGroupMessage(selectedWaba.metaId, selectedGroup.id, msgText.trim());
    if (result?.success) { toast.success('Message sent to group'); setMsgText(''); }
    else toast.error('Send failed');
    setSending(false);
  };

  const handleAddParticipant = async () => {
    if (!selectedGroup || !addPhone.trim()) return;
    const phones = addPhone.split(',').map(p => p.trim()).filter(Boolean);
    const ok = await api.manageGroupParticipants(selectedGroup.id, phones, 'add');
    if (ok) { toast.success('Participant(s) added'); setAddPhone(''); viewDetails(selectedGroup); }
    else toast.error('Add failed');
  };

  const handleRemoveParticipant = async (phone: string) => {
    if (!selectedGroup || !(await confirm(`Remove ${phone}?`))) return;
    const ok = await api.manageGroupParticipants(selectedGroup.id, [phone], 'remove');
    if (ok) { toast.success('Removed'); viewDetails(selectedGroup); }
    else toast.error('Remove failed');
  };

  const content = (
    <>
      <SEO title="WhatsApp Groups" description="Manage WhatsApp Groups" noindex />
      <div className="inner-page-container" style={{ background: '#fff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>WhatsApp Groups</h2>
          <button onClick={() => setShowCreate(true)} style={{ padding: '8px 16px', background: '#d1f470', color: '#1a3a2a', border: '1.5px solid #1a3a2a', borderRadius: 13, cursor: 'pointer', fontSize: 13 }}>
            + Create Group
          </button>
        </div>

        {/* Note about Groups API */}
        <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: 14, marginBottom: 20, fontSize: 13 }}>
          <strong>Note:</strong> WhatsApp Business Groups API is in limited availability. Groups allow businesses to communicate with up to 512 participants. Messages sent to groups are free of charge.
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          {WABAS.map(w => (
            <button key={w.id} onClick={() => { setSelectedWaba(w); setSelectedGroup(null); }}
              style={{ padding: '8px 16px', borderRadius: 6, border: selectedWaba.id === w.id ? '2px solid #1a3a2a' : '1px solid #ddd', background: selectedWaba.id === w.id ? '#f9fafb' : '#fff', cursor: 'pointer', fontSize: 13 }}>
              {w.name} ({w.display})
            </button>
          ))}
        </div>

        {/* Create Modal */}
        {showCreate && (
          <div style={{ background: '#f9fafb', padding: 20, borderRadius: 8, marginBottom: 20, border: '1px solid #e5e7eb' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Create New Group</h3>
            <div style={{ display: 'grid', gap: 12, marginBottom: 12 }}>
              <input value={newSubject} onChange={e => setNewSubject(e.target.value)} placeholder="Group subject (name)"
                style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }} />
              <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Description (optional)"
                style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }} />
              <input value={newParticipants} onChange={e => setNewParticipants(e.target.value)} placeholder="Participants (comma-separated phone numbers, e.g. 919330994400)"
                style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleCreate} disabled={creating} style={{ padding: '8px 16px', background: '#d1f470', color: '#1a3a2a', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
                {creating ? 'Creating...' : 'Create'}
              </button>
              <button onClick={() => setShowCreate(false)} style={{ padding: '8px 16px', background: '#fff', border: '1px solid #ddd', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Cancel</button>
            </div>
          </div>
        )}

        {/* Groups List */}
        {loading ? <p>Loading groups...</p> : groups.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
            <p style={{ fontSize: 16 }}>No groups found</p>
            <p style={{ fontSize: 13 }}>Create a group to start messaging multiple participants</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {groups.map(group => (
              <div key={group.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>{group.subject || group.name || 'Unnamed Group'}</span>
                    {group.participants_count && <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>{group.participants_count} members</span>}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => viewDetails(group)} style={{ padding: '4px 10px', fontSize: 12, border: '1px solid #ddd', borderRadius: 4, background: '#fff', cursor: 'pointer' }}>Details</button>
                    <button onClick={() => handleDelete(group.id)} style={{ padding: '4px 10px', fontSize: 12, border: 'none', borderRadius: 4, background: '#d1f470', color: '#1a3a2a', cursor: 'pointer' }}>Delete</button>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>ID: {group.id}</div>
              </div>
            ))}
          </div>
        )}

        {/* Group Detail Panel */}
        {selectedGroup && (
          <div style={{ marginTop: 20, background: '#f9fafb', padding: 20, borderRadius: 8, border: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>{groupDetail?.subject || selectedGroup.subject || 'Group Details'}</h3>
              <button onClick={() => { setSelectedGroup(null); setGroupDetail(null); }} style={{ padding: '4px 10px', fontSize: 12, border: '1px solid #ddd', borderRadius: 4, background: '#fff', cursor: 'pointer' }}>Close</button>
            </div>

            {groupDetail && (
              <div style={{ fontSize: 13, marginBottom: 16 }}>
                <div><span style={{ color: '#666' }}>ID:</span> {groupDetail.id}</div>
                <div><span style={{ color: '#666' }}>Description:</span> {groupDetail.description || 'None'}</div>
                <div><span style={{ color: '#666' }}>Owner:</span> {groupDetail.owner || 'N/A'}</div>
              </div>
            )}

            {/* Participants */}
            {groupDetail?.participants && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ fontSize: 14, marginBottom: 8 }}>Participants</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(groupDetail.participants.data || groupDetail.participants || []).map((p: any, i: number) => (
                    <span key={i} style={{ padding: '4px 10px', background: '#e5e7eb', borderRadius: 16, fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                      {p.wa_id || p.phone || p}
                      <button onClick={() => handleRemoveParticipant(p.wa_id || p.phone || p)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#1a3a2a', fontSize: 14, padding: 0 }}>×</button>
                    </span>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <input value={addPhone} onChange={e => setAddPhone(e.target.value)} placeholder="Phone number(s) to add"
                    style={{ flex: 1, padding: '6px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }} />
                  <button onClick={handleAddParticipant} style={{ padding: '6px 14px', background: '#d1f470', color: '#1a3a2a', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>Add</button>
                </div>
              </div>
            )}

            {/* Send Message */}
            <div>
              <h4 style={{ fontSize: 14, marginBottom: 8 }}>Send Group Message</h4>
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={msgText} onChange={e => setMsgText(e.target.value)} placeholder="Type a message..."
                  style={{ flex: 1, padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }}
                  onKeyDown={e => e.key === 'Enter' && handleSendMessage()} />
                <button onClick={handleSendMessage} disabled={sending} style={{ padding: '8px 16px', background: '#d1f470', color: '#1a3a2a', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
                  {sending ? '...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
};

export default GroupsPage;
