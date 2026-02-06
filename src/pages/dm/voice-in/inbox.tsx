/**
 * Voice-IN Inbox Page - Airtel Voice Integration (C2C + OBD + CDR)
 * Click-to-Call, OBD Campaigns, and Call Detail Records
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import { SkeletonContact } from '../../../components/Skeleton';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';

interface PageProps { signOut?: () => void; user?: any; }
interface Contact { id: string; name: string; phone: string; callCount: number; lastCall?: string; }
interface C2CCall { callId: string; contactId: string; fromNumber: string; toNumber: string; callerId: string; status: string; duration: number; recordingUrl?: string; correlationId?: string; createdAt: number; }
interface CDRRecord { id: string; vmSessionId: string; clientCorrelationId: string; callType: string; overallCallStatus: string; callerNumber: string; destinationNumber: string; durationSec: number; conversationDurationSec: number; hangupStatus: string; recordingURL?: string; circleNameCaller?: string; operatorNameCaller?: string; createdAt: number; }

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';
const CONTACTS_PER_PAGE = 20;

const VoiceInInbox: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'c2c' | 'cdr'>('c2c');
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [c2cCalls, setC2cCalls] = useState<C2CCall[]>([]);
  const [cdrs, setCdrs] = useState<CDRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [contactsPage, setContactsPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  
  // C2C Modal state
  const [showC2CModal, setShowC2CModal] = useState(false);
  const [c2cFromNumber, setC2cFromNumber] = useState('');
  const [c2cToNumber, setC2cToNumber] = useState('');
  const [c2cRecording, setC2cRecording] = useState(true);
  const [c2cCalling, setC2cCalling] = useState(false);
  
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [contactsData, c2cResponse, cdrResponse] = await Promise.all([
        api.listContacts(),
        fetch(`${API_BASE}/voice-in/c2c`).then(r => r.json()).catch(() => ({ calls: [] })),
        fetch(`${API_BASE}/voice-cdr-webhook`).then(r => r.json()).catch(() => ({ cdrs: [] }))
      ]);
      
      const calls = c2cResponse.calls || [];
      const cdrRecords = cdrResponse.cdrs || [];
      
      const displayContacts: Contact[] = contactsData.filter(c => c.phone).map(c => {
        const contactCalls = calls.filter((m: any) => m.toNumber?.includes(c.phone?.slice(-10)) || m.fromNumber?.includes(c.phone?.slice(-10)));
        const lastCall = contactCalls[0];
        return { id: c.contactId, name: c.name || c.phone || 'Unknown', phone: c.phone || '', callCount: contactCalls.length, lastCall: lastCall?.createdAt ? new Date(lastCall.createdAt * 1000).toISOString() : undefined };
      });
      
      setContacts(displayContacts);
      setC2cCalls(calls);
      setCdrs(cdrRecords);
    } catch (err) { 
      console.error('Load error:', err);
      toast.error('Failed to load data'); 
    } finally { 
      setLoading(false); 
    }
  }, [toast]);

  useEffect(() => { loadData(); const interval = setInterval(loadData, 60000); return () => clearInterval(interval); }, [loadData]);
  useEffect(() => { setContactsPage(1); }, [searchQuery]);

  const filteredContacts = contacts.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.phone.includes(searchQuery));
  const totalContactPages = Math.ceil(filteredContacts.length / CONTACTS_PER_PAGE);
  const paginatedContacts = filteredContacts.slice((contactsPage - 1) * CONTACTS_PER_PAGE, contactsPage * CONTACTS_PER_PAGE);
  const filteredCalls = c2cCalls.filter(c => selectedContact && (c.toNumber?.includes(selectedContact.phone?.slice(-10)) || c.fromNumber?.includes(selectedContact.phone?.slice(-10))));

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try { for (const id of selectedIds) { await api.deleteContact(id); } toast.success(`Deleted ${selectedIds.size} contact(s)`); setSelectedIds(new Set()); setSelectedContact(null); await loadData(); } catch (err) { toast.error('Failed to delete contacts'); } finally { setDeleting(false); }
  };

  const toggleSelect = (id: string) => { const newSet = new Set(selectedIds); if (newSet.has(id)) newSet.delete(id); else newSet.add(id); setSelectedIds(newSet); };

  const formatDuration = (seconds: number) => {
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
      } else { toast.error(result.error || 'Failed to initiate call'); }
    } catch (err) { toast.error('Failed to initiate call'); } finally { setC2cCalling(false); }
  };

  const tabItems: TabItem[] = [
    { id: 'c2c', label: 'Click-to-Call' },
    { id: 'cdr', label: 'Call Records (CDR)' },
  ];
