/**
 * Contacts Management Page
 * Full CRUD with sorting, pagination, tooltips, keyboard shortcuts,
 * bulk actions, inline edit, column visibility, detail panel, duplicate detection, tags
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Layout from '../../components/Layout';
import SEO, { PAGE_SEO } from '../../components/SEO';
import { SkeletonTable } from '../../components/Skeleton';
import { useToastContext } from '../../contexts/ToastContext';
import * as api from '../../api/client';

// SVG Icons — emerald theme (#059669)
const AddUserIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 5v14m-7-7h14"/></svg>);
const UploadIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path fill="none" stroke="#059669" strokeMiterlimit="10" strokeWidth="1.5" d="M12 2.5v17.14m7.62-9.52L12 2.5l-7.62 7.62m15.24 8.57v3.81H4.38v-3.81"/></svg>);
const RefreshIcon = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path fill="#059669" d="m13.146 11.05-.174-1.992 2.374-.208a5 5 0 1 0 .82 6.173l2.002.5a7 7 0 1 1-1.315-7.996l-.245-2.803L18.6 4.55l.523 5.977z"/></svg>);
const DownloadIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="m8 12 4 4m0 0 4-4m-4 4V6.8c0-1.39 0-2.086-.55-2.865-.366-.517-1.42-1.155-2.047-1.24-.945-.128-1.304.059-2.022.433A10 10 0 0 0 2 12c0 5.523 4.477 10 10 10s10-4.477 10-10a10 10 0 0 0-5-8.662"/></svg>);
const ExportIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>);
const EditIcon = ({ size = 18 }: { size?: number }) => (<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H6.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C2 6.28 2 7.12 2 8.8v8.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C4.28 22 5.12 22 6.8 22h8.4c1.68 0 2.52 0 3.162-.327a3 3 0 0 0 1.311-1.311C20 19.72 20 18.88 20 17.2V13M8 16h1.675c.489 0 .733 0 .963-.055.204-.05.4-.13.579-.24.201-.123.374-.296.72-.642L21.5 5.5a2.121 2.121 0 0 0-3-3l-9.563 9.563c-.346.346-.519.519-.642.72a2 2 0 0 0-.24.579c-.055.23-.055.474-.055.963z"/></svg>);
const DeleteIcon = ({ size = 18 }: { size?: number }) => (<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 3h6M3 6h18m-2 0-.701 10.52c-.106 1.583-.158 2.374-.499 2.98a3 3 0 0 1-1.298 1.215C16.56 21 15.767 21 14.182 21H9.818c-1.585 0-2.378 0-2.82-.285a3 3 0 0 1-1.298-1.215c-.341-.606-.393-1.397-.499-2.98L5 6m5 4.5v5m4-5v5"/></svg>);
const SortIcon = ({ dir }: { dir: 'asc' | 'desc' | null }) => (<svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginLeft: 4, opacity: dir ? 1 : 0.3 }}><path d="M6 1l3 4H3z" fill={dir === 'asc' ? '#059669' : '#d1d5db'} /><path d="M6 11l3-4H3z" fill={dir === 'desc' ? '#059669' : '#d1d5db'} /></svg>);
const CloseIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>);

type SortKey = 'name' | 'phone' | 'email' | 'updatedAt';
type SortDir = 'asc' | 'desc';
const PAGE_SIZE = 25;
const TAG_OPTIONS = ['VIP', 'Lead', 'Customer', 'Prospect', 'Partner', 'Vendor'] as const;
const TAG_COLORS: Record<string, string> = { VIP: '#dc2626', Lead: '#2563eb', Customer: '#059669', Prospect: '#d97706', Partner: '#7c3aed', Vendor: '#0891b2' };

type ColumnKey = 'shipping' | 'billing' | 'updated' | 'tags';
const ALL_COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: 'shipping', label: 'Shipping' },
  { key: 'billing', label: 'Billing' },
  { key: 'updated', label: 'Updated' },
  { key: 'tags', label: 'Tags' },
];

function timeAgo(dateStr?: string): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '—';
  const now = Date.now();
  const diff = now - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

interface PageProps { signOut?: () => void; user?: any; }

const Contacts: React.FC<PageProps> = ({ signOut, user }) => {
  const [showModal, setShowModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingContact, setEditingContact] = useState<api.Contact | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const toast = useToastContext();

  // Sorting & Pagination
  const [sortKey, setSortKey] = useState<SortKey>('updatedAt');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [currentPage, setCurrentPage] = useState(1);

  // Form state
  const [formName, setFormName] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formShippingAddress, setFormShippingAddress] = useState('');
  const [formBillingAddress, setFormBillingAddress] = useState('');
  const [formCountryCode, setFormCountryCode] = useState('+91');
  const [showCountryDropdown, setShowCountryDropdown] = useState(false);
  const [countrySearch, setCountrySearch] = useState('');
  const [formOptInWA, setFormOptInWA] = useState(false);
  const [formOptInSms, setFormOptInSms] = useState(false);
  const [formOptInEmail, setFormOptInEmail] = useState(false);
  const [formAllowlistWA, setFormAllowlistWA] = useState(false);
  const [formAllowlistSms, setFormAllowlistSms] = useState(false);
  const [formAllowlistEmail, setFormAllowlistEmail] = useState(false);

  // Delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState<string | null>(null);
  const [deleteContactName, setDeleteContactName] = useState('');

  // CSV import
  const [previewData, setPreviewData] = useState<Partial<api.Contact>[]>([]);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<api.ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [contacts, setContacts] = useState<api.Contact[]>([]);

  // === NEW FEATURES STATE ===
  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Column visibility
  const [hiddenCols, setHiddenCols] = useState<Set<ColumnKey>>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('ct-hidden-cols');
      if (saved) return new Set(JSON.parse(saved) as ColumnKey[]);
    }
    return new Set();
  });
  const [showColMenu, setShowColMenu] = useState(false);

  // Inline edit
  const [inlineEdit, setInlineEdit] = useState<{ id: string; field: 'name' | 'email'; value: string } | null>(null);

  // Detail panel
  const [detailContact, setDetailContact] = useState<api.Contact | null>(null);

  // Tags (stored in-memory per session — would need backend support for persistence)
  const [contactTags, setContactTags] = useState<Record<string, string[]>>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('ct-tags');
      if (saved) return JSON.parse(saved);
    }
    return {};
  });
  const [showTagMenu, setShowTagMenu] = useState<string | null>(null);
  const [showOptIn, setShowOptIn] = useState(false);

  // Persist column visibility & tags
  useEffect(() => { localStorage.setItem('ct-hidden-cols', JSON.stringify([...hiddenCols])); }, [hiddenCols]);
  useEffect(() => { localStorage.setItem('ct-tags', JSON.stringify(contactTags)); }, [contactTags]);

  const colVisible = (key: ColumnKey) => !hiddenCols.has(key);
  const toggleCol = (key: ColumnKey) => {
    setHiddenCols(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  };

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try { const data = await api.listContacts(); setContacts(data); }
    catch { toast.error('Failed to load contacts'); }
    finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      if (e.key === 'Escape') {
        if (detailContact) { setDetailContact(null); return; }
        if (showModal) { setShowModal(false); return; }
        if (showEditModal) { setShowEditModal(false); setEditingContact(null); return; }
        if (showDeleteModal) { setShowDeleteModal(null); return; }
      }
      if (inInput) return;
      if (e.key === 'n' || e.key === 'N') { e.preventDefault(); resetForm(); setShowModal(true); }
      if (e.key === '/') { e.preventDefault(); searchInputRef.current?.focus(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [showModal, showEditModal, showDeleteModal, detailContact]);

  // Filter + sort
  const filteredSorted = useMemo(() => {
    let list = contacts.filter(c =>
      (c.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.phone || '').includes(searchQuery) ||
      (c.email || '').toLowerCase().includes(searchQuery.toLowerCase())
    );
    list.sort((a, b) => {
      const av = (a[sortKey] || '') as string;
      const bv = (b[sortKey] || '') as string;
      if (sortKey === 'updatedAt') {
        const da = new Date(av).getTime() || 0;
        const db = new Date(bv).getTime() || 0;
        return sortDir === 'asc' ? da - db : db - da;
      }
      return sortDir === 'asc' ? av.localeCompare(bv, undefined, { sensitivity: 'base' }) : bv.localeCompare(av, undefined, { sensitivity: 'base' });
    });
    return list;
  }, [contacts, searchQuery, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedContacts = filteredSorted.slice((safeCurrentPage - 1) * PAGE_SIZE, safeCurrentPage * PAGE_SIZE);
  useEffect(() => { setCurrentPage(1); }, [searchQuery]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  const resetForm = () => {
    setFormName(''); setFormPhone(''); setFormEmail('');
    setFormShippingAddress(''); setFormBillingAddress(''); setFormCountryCode('+91');
    setFormOptInWA(true); setFormOptInSms(true); setFormOptInEmail(true);
    setFormAllowlistWA(true); setFormAllowlistSms(true); setFormAllowlistEmail(true);
  };

  // Duplicate detection
  const checkDuplicate = (phone: string, email: string, excludeId?: string): string | null => {
    const fullPhone = phone ? (phone.startsWith('+') ? phone : `${formCountryCode}${phone.replace(/^0+/, '')}`) : '';
    for (const c of contacts) {
      if (excludeId && c.contactId === excludeId) continue;
      if (fullPhone && c.phone === fullPhone) return `Phone ${fullPhone} already exists (${c.name || 'unnamed'})`;
      if (email && c.email && c.email.toLowerCase() === email.toLowerCase()) return `Email ${email} already exists (${c.name || 'unnamed'})`;
    }
    return null;
  };

  const handleCreate = async () => {
    if (!formPhone && !formEmail) { toast.warning('Phone or email is required'); return; }
    const dup = checkDuplicate(formPhone, formEmail);
    if (dup) { toast.warning(dup); return; }
    const fullPhone = formPhone ? (formPhone.startsWith('+') ? formPhone : `${formCountryCode}${formPhone.replace(/^0+/, '')}`) : '';
    setSaving(true);
    try {
      const result = await api.createContact({
        name: formName, phone: fullPhone || undefined, email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined, billingAddress: formBillingAddress || undefined,
        optInWhatsApp: formOptInWA, optInSms: formOptInSms, optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA, allowlistSms: formAllowlistSms, allowlistEmail: formAllowlistEmail,
      });
      if (result) { toast.success('Contact created'); setShowModal(false); resetForm(); await loadContacts(); }
      else toast.error('Failed to create contact');
    } catch { toast.error('Failed to create contact'); }
    finally { setSaving(false); }
  };

  const handleEdit = (contact: api.Contact) => {
    setEditingContact(contact);
    setFormName(contact.name || '');
    const ph = contact.phone || '';
    const ccMatch = ph.match(/^(\+\d{1,4})/);
    if (ccMatch) { setFormCountryCode(ccMatch[1]); setFormPhone(ph.slice(ccMatch[1].length)); }
    else { setFormCountryCode('+91'); setFormPhone(ph); }
    setFormEmail(contact.email || '');
    setFormShippingAddress(contact.shippingAddress || ''); setFormBillingAddress(contact.billingAddress || '');
    setFormOptInWA(contact.optInWhatsApp || false); setFormOptInSms(contact.optInSms || false); setFormOptInEmail(contact.optInEmail || false);
    setFormAllowlistWA(contact.allowlistWhatsApp || false); setFormAllowlistSms(contact.allowlistSms || false); setFormAllowlistEmail(contact.allowlistEmail || false);
    setShowEditModal(true);
  };

  const handleUpdate = async () => {
    if (!editingContact || (!formPhone && !formEmail)) { toast.warning('Phone or email is required'); return; }
    const dup = checkDuplicate(formPhone, formEmail, editingContact.contactId);
    if (dup) { toast.warning(dup); return; }
    const fullPhone = formPhone ? (formPhone.startsWith('+') ? formPhone : `${formCountryCode}${formPhone.replace(/^0+/, '')}`) : '';
    setSaving(true);
    try {
      const result = await api.updateContact(editingContact.contactId, {
        name: formName, phone: fullPhone || undefined, email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined, billingAddress: formBillingAddress || undefined,
        optInWhatsApp: formOptInWA, optInSms: formOptInSms, optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA, allowlistSms: formAllowlistSms, allowlistEmail: formAllowlistEmail,
      });
      if (result) { toast.success('Contact updated'); setShowEditModal(false); setEditingContact(null); resetForm(); await loadContacts(); }
      else toast.error('Failed to update contact');
    } catch { toast.error('Failed to update contact'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (contactId: string) => {
    setShowDeleteModal(null);
    try {
      const result = await api.deleteContact(contactId);
      if (result) { toast.success('Contact deleted'); selectedIds.delete(contactId); setSelectedIds(new Set(selectedIds)); await loadContacts(); }
      else toast.error('Failed to delete contact');
    } catch { toast.error('Failed to delete contact'); }
  };

  // Bulk delete
  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    const count = selectedIds.size;
    if (!confirm(`Delete ${count} contact${count > 1 ? 's' : ''}?`)) return;
    let deleted = 0;
    for (const id of selectedIds) {
      try { const r = await api.deleteContact(id); if (r) deleted++; } catch {}
    }
    setSelectedIds(new Set());
    toast.success(`Deleted ${deleted} contact${deleted > 1 ? 's' : ''}`);
    await loadContacts();
  };

  // Bulk export selected
  const handleBulkExport = () => {
    const selected = contacts.filter(c => selectedIds.has(c.contactId));
    if (selected.length === 0) return;
    const csv = api.exportContactsToCSV(selected);
    api.downloadFile(csv, `contacts_selected_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
  };

  // Select all on current page
  const allPageSelected = paginatedContacts.length > 0 && paginatedContacts.every(c => selectedIds.has(c.contactId));
  const toggleSelectAll = () => {
    const next = new Set(selectedIds);
    if (allPageSelected) { paginatedContacts.forEach(c => next.delete(c.contactId)); }
    else { paginatedContacts.forEach(c => next.add(c.contactId)); }
    setSelectedIds(next);
  };
  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };

  // Inline edit
  const commitInlineEdit = async () => {
    if (!inlineEdit) return;
    const { id, field, value } = inlineEdit;
    setInlineEdit(null);
    try {
      const result = await api.updateContact(id, { [field]: value });
      if (result) { toast.success(`${field} updated`); await loadContacts(); }
    } catch { toast.error('Failed to update'); }
  };

  // Tags
  const toggleTag = (contactId: string, tag: string) => {
    setContactTags(prev => {
      const tags = prev[contactId] || [];
      const next = tags.includes(tag) ? tags.filter(t => t !== tag) : [...tags, tag];
      return { ...prev, [contactId]: next };
    });
  };

  // CSV import handlers
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (file.name.endsWith('.vcf')) {
        setPreviewData(parseVCard(text));
      } else {
        const lines = text.split('\n').filter(l => l.trim());
        if (lines.length < 2) { toast.warning('CSV file is empty'); return; }
        const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
        const nameIdx = headers.findIndex(h => h === 'name');
        const phoneIdx = headers.findIndex(h => h === 'phone');
        const emailIdx = headers.findIndex(h => h === 'email');
        const rows: Partial<api.Contact>[] = [];
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',').map(c => c.trim());
          rows.push({
            name: nameIdx >= 0 ? cols[nameIdx] : '',
            phone: phoneIdx >= 0 ? cols[phoneIdx] : '',
            email: emailIdx >= 0 ? cols[emailIdx] : '',
          });
        }
        setPreviewData(rows);
      }
    };
    reader.readAsText(file);
  };

  const parseVCard = (text: string): Partial<api.Contact>[] => {
    const cards = text.split('BEGIN:VCARD').filter(c => c.trim());
    return cards.map(card => {
      const lines = card.split('\n');
      let name = '', phone = '', email = '';
      for (const line of lines) {
        if (line.startsWith('FN:')) name = line.slice(3).trim();
        if (line.startsWith('TEL') && !phone) { const m = line.match(/:([\d+\s-]+)/); if (m) phone = m[1].replace(/[\s-]/g, ''); }
        if (line.startsWith('EMAIL')) { const m = line.match(/:(.+)/); if (m) email = m[1].trim(); }
      }
      return { name, phone, email };
    }).filter(c => c.phone || c.email);
  };

  const handleImport = async () => {
    if (previewData.length === 0) return;
    setImporting(true);
    try {
      const result = await api.importContacts(previewData);
      setImportResult(result);
      toast.success(`Imported ${result.created} of ${result.total} contacts`);
      await loadContacts();
    } catch { toast.error('Import failed'); }
    finally { setImporting(false); }
  };

  const handleExport = () => {
    const csv = api.exportContactsToCSV(contacts);
    api.downloadFile(csv, `contacts_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
  };

  const downloadTemplate = () => {
    api.downloadFile('Name,Phone,Email\nJohn Doe,+919000090000,[email]', 'contacts_template.csv', 'text/csv');
  };

  // Country codes
  const countryCodes = [
    { code: '+91', country: 'India' }, { code: '+1', country: 'USA/Canada' }, { code: '+44', country: 'UK' },
    { code: '+61', country: 'Australia' }, { code: '+971', country: 'UAE' }, { code: '+966', country: 'Saudi Arabia' },
    { code: '+65', country: 'Singapore' }, { code: '+60', country: 'Malaysia' }, { code: '+49', country: 'Germany' },
    { code: '+33', country: 'France' }, { code: '+81', country: 'Japan' }, { code: '+86', country: 'China' },
    { code: '+82', country: 'South Korea' }, { code: '+55', country: 'Brazil' }, { code: '+27', country: 'South Africa' },
    { code: '+234', country: 'Nigeria' }, { code: '+254', country: 'Kenya' }, { code: '+62', country: 'Indonesia' },
    { code: '+63', country: 'Philippines' }, { code: '+7', country: 'Russia' },
  ];

  // SortHeader component
  const SortHeader = ({ label, sKey, style }: { label: string; sKey: SortKey; style?: React.CSSProperties }) => (
    <th onClick={() => toggleSort(sKey)} style={{ cursor: 'pointer', userSelect: 'none', padding: '12px 14px', textAlign: 'left', fontSize: 14, fontWeight: 600, color: '#374151', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2, ...style }}>
      <span style={{ display: 'inline-flex', alignItems: 'center' }}>{label}<SortIcon dir={sortKey === sKey ? sortDir : null} /></span>
    </th>
  );

  // Inline styles for form (bypasses Next.js style jsx scoping)
  const S: Record<string, React.CSSProperties> = {
    label: { display: 'block', fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 5 },
    input: { width: '100%', padding: '10px 14px', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 15, outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s', background: '#fff' },
    row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 },
    hint: { fontSize: 12, color: '#9ca3af', marginTop: 3 },
  };
  const focusStyle = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => { e.target.style.borderColor = '#059669'; e.target.style.boxShadow = '0 0 0 3px rgba(5,150,105,0.1)'; };
  const blurStyle = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => { e.target.style.borderColor = '#D1FAE5'; e.target.style.boxShadow = 'none'; };

  const renderContactForm = (isEdit: boolean) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '20px 24px' }}>
      {/* Name */}
      <div>
        <label style={S.label}>Name</label>
        <input style={S.input} value={formName} onChange={e => setFormName(e.target.value)} placeholder="Full name" onFocus={focusStyle} onBlur={blurStyle} />
      </div>
      {/* Phone */}
      <div>
        <label style={S.label}>Phone</label>
        <div style={{ display: 'flex', gap: 6 }}>
          {/* Searchable Country Code Dropdown */}
          <div style={{ position: 'relative', width: 120, flexShrink: 0 }}>
            <input
              type="text"
              value={showCountryDropdown ? countrySearch : formCountryCode}
              onChange={e => { setCountrySearch(e.target.value); setShowCountryDropdown(true); }}
              onFocus={() => { setShowCountryDropdown(true); setCountrySearch(''); }}
              onBlur={() => setTimeout(() => setShowCountryDropdown(false), 200)}
              placeholder="Code"
              style={{ width: '100%', padding: '8px 8px', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 14, outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s', background: '#fff', color: '#374151', cursor: 'pointer' }}
              onFocusCapture={focusStyle}
              onBlurCapture={blurStyle}
            />
            {showCountryDropdown && (
              <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4, maxHeight: 200, overflowY: 'auto', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 1000 }}>
                {countryCodes
                  .filter(cc => 
                    cc.code.includes(countrySearch) || 
                    cc.country.toLowerCase().includes(countrySearch.toLowerCase())
                  )
                  .map(cc => (
                    <div
                      key={cc.code}
                      onMouseDown={() => { setFormCountryCode(cc.code); setShowCountryDropdown(false); setCountrySearch(''); }}
                      style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 13, color: '#374151', transition: 'background 0.15s' }}
                      onMouseEnter={e => e.currentTarget.style.background = '#ECFDF5'}
                      onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                    >
                      {cc.code} {cc.country}
                    </div>
                  ))}
              </div>
            )}
          </div>
          <input style={S.input} value={formPhone} onChange={e => setFormPhone(e.target.value)} placeholder="[Phone]" onFocus={focusStyle} onBlur={blurStyle} />
        </div>
        <p style={S.hint}>Include country code</p>
      </div>
      {/* Email */}
      <div>
        <label style={S.label}>Email</label>
        <input style={S.input} type="email" value={formEmail} onChange={e => setFormEmail(e.target.value)} placeholder="[email]" onFocus={focusStyle} onBlur={blurStyle} />
      </div>
      {/* Shipping + Billing row */}
      <div style={S.row}>
        <div>
          <label style={S.label}>Shipping Address</label>
          <textarea style={{ ...S.input, minHeight: 60, resize: 'vertical' } as any} value={formShippingAddress} onChange={e => setFormShippingAddress(e.target.value)} placeholder="[Shipping Address]" onFocus={focusStyle as any} onBlur={blurStyle as any} />
        </div>
        <div>
          <label style={S.label}>Billing Address</label>
          <textarea style={{ ...S.input, minHeight: 60, resize: 'vertical' } as any} value={formBillingAddress} onChange={e => setFormBillingAddress(e.target.value)} placeholder="[Billing Address]" onFocus={focusStyle as any} onBlur={blurStyle as any} />
          <button 
            type="button"
            onClick={() => setFormBillingAddress(formShippingAddress)}
            disabled={!formShippingAddress}
            style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: 4, 
              fontSize: 11, 
              color: '#059669', 
              fontWeight: 600, 
              marginTop: 6, 
              cursor: formShippingAddress ? 'pointer' : 'not-allowed',
              opacity: formShippingAddress ? 1 : 0.5,
              background: 'none',
              border: 'none',
              padding: 0
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            Copy from shipping
          </button>
        </div>
      </div>
      {/* Opt-in toggle */}
      <div>
        <button type="button" onClick={() => setShowOptIn(!showOptIn)} style={{ fontSize: 14, color: '#059669', background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
          <span style={{ transform: showOptIn ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s', display: 'inline-block', color: '#059669', fontSize: 16 }}>▶</span>
          Opt-in &amp; Allowlist
        </button>
        {showOptIn && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10, padding: 14, background: '#f9fafb', borderRadius: 13, border: '2px solid #D1FAE5' }}>
            {[
              { label: 'WhatsApp Opt-in', val: formOptInWA, set: setFormOptInWA },
              { label: 'WhatsApp Allowlist', val: formAllowlistWA, set: setFormAllowlistWA },
              { label: 'SMS Opt-in', val: formOptInSms, set: setFormOptInSms },
              { label: 'SMS Allowlist', val: formAllowlistSms, set: setFormAllowlistSms },
              { label: 'Email Opt-in', val: formOptInEmail, set: setFormOptInEmail },
              { label: 'Email Allowlist', val: formAllowlistEmail, set: setFormAllowlistEmail },
            ].map(item => (
              <label key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, cursor: 'pointer' }}>
                <input type="checkbox" checked={item.val} onChange={e => item.set(e.target.checked)} style={{ accentColor: '#059669', width: 16, height: 16 }} />
                {item.label}
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <Layout onSignOut={signOut} user={user}>
      <SEO {...PAGE_SEO.contacts} />
      <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
        {/* Toolbar */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          {/* Contact count badge */}
          <span style={{ background: '#ECFDF5', color: '#059669', fontWeight: 600, fontSize: 13, padding: '4px 12px', borderRadius: 13 }}>
            {filteredSorted.length} contact{filteredSorted.length !== 1 ? 's' : ''}
          </span>

          {/* Search */}
          <div style={{ position: 'relative', flex: '1 1 200px', maxWidth: 320 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
              <path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="m21 21-4.35-4.35M11 6a5 5 0 0 1 5 5m3 0a8 8 0 1 1-16 0 8 8 0 0 1 16 0"/>
            </svg>
            <input ref={searchInputRef} value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="" style={{ width: '100%', padding: '8px 12px 8px 34px', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 14, outline: 'none', background: '#fff' }} onFocus={focusStyle} onBlur={blurStyle} />
          </div>

          {/* Action buttons */}
          <button onClick={() => { resetForm(); setShowModal(true); }} title="Add contact (N)" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px', background: '#059669', color: '#fff', border: 'none', borderRadius: 13, cursor: 'pointer' }}>
            <AddUserIcon />
          </button>
          <button onClick={() => setShowImport(!showImport)} title="Import contacts" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px', background: '#fff', color: '#374151', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer' }}>
            <UploadIcon />
          </button>
          <button onClick={handleExport} title="Export all contacts" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px', background: '#fff', color: '#374151', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer' }}>
            <ExportIcon />
          </button>
          <button onClick={loadContacts} title="Refresh" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer' }}>
            <RefreshIcon />
          </button>

          {/* Column visibility */}
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowColMenu(!showColMenu)} title="Toggle columns" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '8px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0H5a2 2 0 0 1-2-2v-4m6 6h10a2 2 0 0 0 2-2v-4M3 9h18M3 15h18"/></svg>
            </button>
            {showColMenu && (
              <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 4, background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, padding: 8, zIndex: 50, minWidth: 160, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                {ALL_COLUMNS.map(col => (
                  <label key={col.key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', fontSize: 13, cursor: 'pointer', borderRadius: 8 }}>
                    <input type="checkbox" checked={colVisible(col.key)} onChange={() => toggleCol(col.key)} style={{ accentColor: '#059669' }} />
                    {col.label}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Bulk action bar */}
        {selectedIds.size > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', marginBottom: 12, background: '#ECFDF5', borderRadius: 13, border: '2px solid #D1FAE5' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#059669' }}>{selectedIds.size} selected</span>
            <button onClick={handleBulkExport} title="Export selected" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '6px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer' }}>
              <ExportIcon />
            </button>
            <button onClick={handleBulkDelete} title="Delete selected" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '6px', background: '#fff', border: '2px solid #dc2626', borderRadius: 13, cursor: 'pointer' }}>
              <DeleteIcon size={14} />
            </button>
            <button onClick={() => setSelectedIds(new Set())} style={{ marginLeft: 'auto', fontSize: 12, color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}>Clear selection</button>
          </div>
        )}

        {/* Import section */}
        {showImport && (
          <div style={{ marginBottom: 16, padding: 16, border: '2px solid #D1FAE5', borderRadius: 13, background: '#ECFDF5' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <label title="Choose CSV/VCF file" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: '#fff', color: '#059669', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
                <UploadIcon /> Choose File
                <input ref={fileInputRef} type="file" accept=".csv,.vcf" onChange={handleFileSelect} style={{ display: 'none' }} />
              </label>
              <label onClick={downloadTemplate} title="Download template" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: '#fff', color: '#059669', border: '2px solid #D1FAE5', borderRadius: 13, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
                <ExportIcon /> Template
              </label>
            </div>
            {previewData.length > 0 && (
              <div>
                <p style={{ fontSize: 13, color: '#374151', marginBottom: 8 }}>{previewData.length} contacts ready to import</p>
                <div style={{ maxHeight: 150, overflow: 'auto', border: '2px solid #D1FAE5', borderRadius: 13, marginBottom: 8 }}>
                  <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                    <thead><tr>{['Name','Phone','Email'].map(h => <th key={h} style={{ padding: '6px 8px', background: '#ECFDF5', textAlign: 'left', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0 }}>{h}</th>)}</tr></thead>
                    <tbody>{previewData.slice(0, 10).map((r, i) => <tr key={i}><td style={{ padding: '4px 8px', borderBottom: '1px solid #D1FAE5' }}>{r.name}</td><td style={{ padding: '4px 8px', borderBottom: '1px solid #D1FAE5' }}>{r.phone}</td><td style={{ padding: '4px 8px', borderBottom: '1px solid #D1FAE5' }}>{r.email}</td></tr>)}</tbody>
                  </table>
                </div>
                <button onClick={handleImport} disabled={importing} style={{ padding: '8px 16px', background: '#059669', color: '#fff', border: 'none', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: importing ? 0.6 : 1 }}>
                  {importing ? 'Importing...' : `Import ${previewData.length} contacts`}
                </button>
              </div>
            )}
            {importResult && (
              <p style={{ fontSize: 13, color: '#059669', marginTop: 8 }}>
                Done: {importResult.created} created, {importResult.failed} failed, {importResult.errors.length} errors
              </p>
            )}
          </div>
        )}

        {/* Main content area with table + detail panel */}
        <div style={{ display: 'flex', gap: 0 }}>
          {/* Table */}
          <div style={{ flex: 1, minWidth: 0, border: '2px solid #D1FAE5', borderRadius: 13, overflow: 'hidden', background: '#fff' }}>
            {loading ? <div style={{ padding: 24 }}><SkeletonTable rows={8} /></div> : filteredSorted.length === 0 ? (
              <div style={{ padding: 48, textAlign: 'center' }}>
                {searchQuery ? (
                  <div>
                    <p style={{ fontSize: 15, color: '#6b7280' }}>No results for &quot;{searchQuery}&quot;</p>
                    <button onClick={() => setSearchQuery('')} style={{ marginTop: 8, fontSize: 13, color: '#059669', background: 'none', border: 'none', cursor: 'pointer' }}>Clear search</button>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: 32, marginBottom: 8 }}>📇</p>
                    <p style={{ fontSize: 15, color: '#6b7280' }}>No contacts yet</p>
                    <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>Press <kbd style={{ padding: '2px 6px', background: '#f3f4f6', borderRadius: 4, fontSize: 11 }}>N</kbd> to add one</p>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ maxHeight: 'calc(100vh - 240px)', overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                  <thead>
                    <tr>
                      <th style={{ width: 40, padding: '12px 10px', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2 }}>
                        <input type="checkbox" checked={allPageSelected} onChange={toggleSelectAll} style={{ accentColor: '#059669', width: 16, height: 16 }} />
                      </th>
                      <SortHeader label="Name" sKey="name" />
                      <SortHeader label="Phone" sKey="phone" />
                      <SortHeader label="Email" sKey="email" />
                      {colVisible('shipping') && <th style={{ padding: '12px 14px', textAlign: 'left', fontSize: 14, fontWeight: 600, color: '#374151', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2 }}>Shipping</th>}
                      {colVisible('billing') && <th style={{ padding: '12px 14px', textAlign: 'left', fontSize: 14, fontWeight: 600, color: '#374151', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2 }}>Billing</th>}
                      {colVisible('updated') && <SortHeader label="Updated" sKey="updatedAt" />}
                      {colVisible('tags') && <th style={{ padding: '12px 14px', textAlign: 'left', fontSize: 14, fontWeight: 600, color: '#374151', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2 }}>Tags</th>}
                      <th style={{ width: 100, padding: '12px 10px', background: '#ECFDF5', borderBottom: '2px solid #D1FAE5', position: 'sticky', top: 0, zIndex: 2 }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedContacts.map((c, rowIndex) => (
                      <tr key={c.contactId} onClick={() => setDetailContact(c)} style={{ cursor: 'pointer', transition: 'background 0.15s' }} onMouseEnter={e => (e.currentTarget.style.background = '#ECFDF5')} onMouseLeave={e => (e.currentTarget.style.background = '')}>
                        <td style={{ padding: '10px', borderBottom: '1px solid #D1FAE5', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                          <input type="checkbox" checked={selectedIds.has(c.contactId)} onChange={() => toggleSelect(c.contactId)} style={{ accentColor: '#059669', width: 16, height: 16 }} />
                        </td>
                        {/* Name — inline editable */}
                        <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', fontWeight: 500, fontSize: 14 }} onDoubleClick={e => { e.stopPropagation(); setInlineEdit({ id: c.contactId, field: 'name', value: c.name }); }}>
                          {inlineEdit?.id === c.contactId && inlineEdit.field === 'name' ? (
                            <input autoFocus value={inlineEdit.value} onChange={e => setInlineEdit({ ...inlineEdit, value: e.target.value })} onBlur={commitInlineEdit} onKeyDown={e => { if (e.key === 'Enter') commitInlineEdit(); if (e.key === 'Escape') setInlineEdit(null); }} onClick={e => e.stopPropagation()} style={{ width: '100%', padding: '6px 10px', border: '2px solid #059669', borderRadius: 8, fontSize: 14, outline: 'none' }} />
                          ) : (c.name || <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>unnamed</span>)}
                        </td>
                        <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', fontSize: 14 }}>{c.phone}</td>
                        {/* Email — inline editable */}
                        <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', fontSize: 14 }} onDoubleClick={e => { e.stopPropagation(); setInlineEdit({ id: c.contactId, field: 'email', value: c.email || '' }); }}>
                          {inlineEdit?.id === c.contactId && inlineEdit.field === 'email' ? (
                            <input autoFocus value={inlineEdit.value} onChange={e => setInlineEdit({ ...inlineEdit, value: e.target.value })} onBlur={commitInlineEdit} onKeyDown={e => { if (e.key === 'Enter') commitInlineEdit(); if (e.key === 'Escape') setInlineEdit(null); }} onClick={e => e.stopPropagation()} style={{ width: '100%', padding: '6px 10px', border: '2px solid #059669', borderRadius: 8, fontSize: 14, outline: 'none' }} />
                          ) : (c.email || '—')}
                        </td>
                        {colVisible('shipping') && <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 14 }}>{c.shippingAddress || '—'}</td>}
                        {colVisible('billing') && <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 14 }}>{c.billingAddress || '—'}</td>}
                        {colVisible('updated') && <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5', color: '#6b7280', fontSize: 13 }} title={c.updatedAt ? new Date(c.updatedAt).toLocaleString() : ''}>{timeAgo(c.updatedAt)}</td>}
                        {colVisible('tags') && (
                          <td style={{ padding: '10px 14px', borderBottom: '1px solid #D1FAE5' }} onClick={e => e.stopPropagation()}>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                              {(contactTags[c.contactId] || []).map(tag => (
                                <span key={tag} style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 10, fontSize: 12, fontWeight: 600, color: '#fff', background: TAG_COLORS[tag] || '#6b7280' }}>{tag}</span>
                              ))}
                              <div style={{ position: 'relative' }}>
                                <button onClick={() => setShowTagMenu(showTagMenu === c.contactId ? null : c.contactId)} style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid #059669', background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0 }}>
                                  <svg width="14" height="14" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v14m-7-7h14"/>
                                  </svg>
                                </button>
                                {showTagMenu === c.contactId && (
                                  <div style={{ 
                                    position: 'absolute', 
                                    ...(rowIndex < 3 ? { top: '100%', marginTop: 4 } : { bottom: '100%', marginBottom: 4 }),
                                    left: 0, 
                                    background: '#fff', 
                                    border: '2px solid #D1FAE5', 
                                    borderRadius: 13, 
                                    padding: 6, 
                                    zIndex: 50, 
                                    minWidth: 130, 
                                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)' 
                                  }}>
                                    {TAG_OPTIONS.map(tag => {
                                      const active = (contactTags[c.contactId] || []).includes(tag);
                                      return (
                                        <button key={tag} onClick={() => toggleTag(c.contactId, tag)} style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '6px 10px', border: 'none', background: active ? '#ECFDF5' : 'transparent', borderRadius: 8, fontSize: 13, cursor: 'pointer', textAlign: 'left' }}>
                                          <span style={{ width: 12, height: 12, borderRadius: '50%', background: TAG_COLORS[tag] }}></span>
                                          {tag}
                                          {active && <span style={{ marginLeft: 'auto', color: '#059669', fontWeight: 600 }}>✓</span>}
                                        </button>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        )}
                        <td style={{ padding: '10px', borderBottom: '1px solid #D1FAE5', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                          <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                            <button onClick={() => handleEdit(c)} title="Edit" style={{ padding: 6, background: 'none', border: 'none', cursor: 'pointer', borderRadius: 6 }}><EditIcon size={18} /></button>
                            <button onClick={() => { setShowDeleteModal(c.contactId); setDeleteContactName(c.name); }} title="Delete" style={{ padding: 6, background: 'none', border: 'none', cursor: 'pointer', borderRadius: 6 }}><DeleteIcon size={18} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Detail side panel */}
          {detailContact && (
            <div style={{ width: 340, flexShrink: 0, borderLeft: '2px solid #D1FAE5', background: '#fff', overflow: 'auto', marginLeft: -2, borderRadius: '0 13px 13px 0' }}>
              <div style={{ padding: '16px 20px', background: '#ECFDF5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #D1FAE5' }}>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#374151' }}>Contact Details</h3>
                <button onClick={() => setDetailContact(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}><CloseIcon /></button>
              </div>
              <div style={{ padding: 20 }}>
                <div style={{ textAlign: 'center', marginBottom: 20 }}>
                  <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#ECFDF5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px', fontSize: 24, color: '#059669', fontWeight: 700 }}>
                    {(detailContact.name || '?')[0]?.toUpperCase()}
                  </div>
                  <p style={{ fontSize: 16, fontWeight: 600, color: '#111827', margin: 0 }}>{detailContact.name || 'Unnamed'}</p>
                  <p style={{ fontSize: 13, color: '#6b7280', margin: '4px 0 0' }}>{detailContact.phone}</p>
                </div>
                {[
                  { label: 'Email', value: detailContact.email },
                  { label: 'Shipping', value: detailContact.shippingAddress },
                  { label: 'Billing', value: detailContact.billingAddress },
                  { label: 'Created', value: detailContact.createdAt ? new Date(detailContact.createdAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—' },
                  { label: 'Updated', value: timeAgo(detailContact.updatedAt) },
                  { label: 'Last Message', value: timeAgo(detailContact.lastInboundMessageAt) },
                ].map(item => (
                  <div key={item.label} style={{ marginBottom: 12 }}>
                    <p style={{ fontSize: 11, color: '#9ca3af', margin: '0 0 2px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</p>
                    <p style={{ fontSize: 13, color: '#374151', margin: 0, wordBreak: 'break-word' }}>{item.value || '—'}</p>
                  </div>
                ))}
                {/* Tags in detail */}
                <div style={{ marginBottom: 12 }}>
                  <p style={{ fontSize: 11, color: '#9ca3af', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tags</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {(contactTags[detailContact.contactId] || []).map(tag => (
                      <span key={tag} style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, color: '#fff', background: TAG_COLORS[tag] || '#6b7280' }}>{tag}</span>
                    ))}
                    {(contactTags[detailContact.contactId] || []).length === 0 && <span style={{ fontSize: 12, color: '#9ca3af' }}>No tags</span>}
                  </div>
                </div>
                {/* Opt-in status */}
                <div style={{ marginBottom: 12 }}>
                  <p style={{ fontSize: 11, color: '#9ca3af', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Opt-in Status</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {[
                      { label: 'WA', on: detailContact.optInWhatsApp },
                      { label: 'SMS', on: detailContact.optInSms },
                      { label: 'Email', on: detailContact.optInEmail },
                    ].map(ch => (
                      <span key={ch.label} style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 500, background: ch.on ? '#ECFDF5' : '#f3f4f6', color: ch.on ? '#059669' : '#9ca3af' }}>
                        {ch.on ? '✓' : '✗'} {ch.label}
                      </span>
                    ))}
                  </div>
                </div>
                {/* Actions */}
                <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                  <button onClick={() => { handleEdit(detailContact); setDetailContact(null); }} style={{ flex: 1, padding: '8px 12px', background: '#059669', color: '#fff', border: 'none', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Edit</button>
                  <button onClick={() => { setShowDeleteModal(detailContact.contactId); setDeleteContactName(detailContact.name); setDetailContact(null); }} style={{ flex: 1, padding: '8px 12px', background: '#fff', color: '#dc2626', border: '2px solid #dc2626', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Delete</button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages >= 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 16 }}>
            <button onClick={() => setCurrentPage(1)} disabled={safeCurrentPage <= 1} title="First page" style={{ padding: '6px 10px', border: '2px solid #D1FAE5', borderRadius: 13, background: '#fff', cursor: safeCurrentPage <= 1 ? 'default' : 'pointer', opacity: safeCurrentPage <= 1 ? 0.4 : 1, fontSize: 13 }}>«</button>
            <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={safeCurrentPage <= 1} style={{ padding: '6px 12px', border: '2px solid #D1FAE5', borderRadius: 13, background: '#fff', cursor: safeCurrentPage <= 1 ? 'default' : 'pointer', opacity: safeCurrentPage <= 1 ? 0.4 : 1, fontSize: 13 }}>‹</button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).filter(p => p === 1 || p === totalPages || Math.abs(p - safeCurrentPage) <= 1).map((p, idx, arr) => (
              <React.Fragment key={p}>
                {idx > 0 && arr[idx - 1] !== p - 1 && <span style={{ color: '#9ca3af' }}>…</span>}
                <button onClick={() => setCurrentPage(p)} style={{ padding: '6px 10px', border: '2px solid #D1FAE5', borderRadius: 13, background: p === safeCurrentPage ? '#059669' : '#fff', color: p === safeCurrentPage ? '#fff' : '#374151', fontWeight: p === safeCurrentPage ? 600 : 400, cursor: 'pointer', fontSize: 13 }}>{p}</button>
              </React.Fragment>
            ))}
            <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={safeCurrentPage >= totalPages} style={{ padding: '6px 12px', border: '2px solid #D1FAE5', borderRadius: 13, background: '#fff', cursor: safeCurrentPage >= totalPages ? 'default' : 'pointer', opacity: safeCurrentPage >= totalPages ? 0.4 : 1, fontSize: 13 }}>›</button>
            <button onClick={() => setCurrentPage(totalPages)} disabled={safeCurrentPage >= totalPages} title="Last page" style={{ padding: '6px 10px', border: '2px solid #D1FAE5', borderRadius: 13, background: '#fff', cursor: safeCurrentPage >= totalPages ? 'default' : 'pointer', opacity: safeCurrentPage >= totalPages ? 0.4 : 1, fontSize: 13 }}>»</button>
          </div>
        )}
      </div>

      {/* Add Contact Modal */}
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => setShowModal(false)}>
          <div style={{ background: '#fff', borderRadius: 14, width: 560, maxHeight: '85vh', overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '20px 24px', background: '#ECFDF5', borderRadius: '14px 14px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #D1FAE5' }}>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#374151' }}>Add Contact</h2>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}><CloseIcon /></button>
            </div>
            {renderContactForm(false)}
            <div style={{ padding: '16px 24px', borderTop: '2px solid #D1FAE5', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowModal(false)} style={{ padding: '8px 16px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 13, cursor: 'pointer', color: '#374151' }}>Cancel</button>
              <button onClick={handleCreate} disabled={saving} style={{ padding: '8px 20px', background: '#059669', color: '#fff', border: 'none', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: saving ? 0.6 : 1 }}>{saving ? 'Saving...' : 'Create'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Contact Modal */}
      {showEditModal && editingContact && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => { setShowEditModal(false); setEditingContact(null); }}>
          <div style={{ background: '#fff', borderRadius: 14, width: 560, maxHeight: '85vh', overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }} onClick={e => e.stopPropagation()}>
            <div style={{ padding: '20px 24px', background: '#ECFDF5', borderRadius: '14px 14px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #D1FAE5' }}>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#374151' }}>Edit Contact</h2>
              <button onClick={() => { setShowEditModal(false); setEditingContact(null); }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}><CloseIcon /></button>
            </div>
            {renderContactForm(true)}
            <div style={{ padding: '16px 24px', borderTop: '2px solid #D1FAE5', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setShowEditModal(false); setEditingContact(null); }} style={{ padding: '8px 16px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 13, cursor: 'pointer', color: '#374151' }}>Cancel</button>
              <button onClick={handleUpdate} disabled={saving} style={{ padding: '8px 20px', background: '#059669', color: '#fff', border: 'none', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: saving ? 0.6 : 1 }}>{saving ? 'Saving...' : 'Update'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => setShowDeleteModal(null)}>
          <div style={{ background: '#fff', borderRadius: 14, width: 400, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 600, color: '#374151' }}>Delete Contact</h3>
            <p style={{ fontSize: 14, color: '#6b7280', margin: '0 0 20px' }}>
              Are you sure you want to delete <strong>{deleteContactName || 'this contact'}</strong>? This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowDeleteModal(null)} style={{ padding: '8px 16px', background: '#fff', border: '2px solid #D1FAE5', borderRadius: 13, fontSize: 13, cursor: 'pointer', color: '#374151' }}>Cancel</button>
              <button onClick={() => handleDelete(showDeleteModal)} style={{ padding: '8px 20px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* Click outside to close menus */}
      {(showColMenu || showTagMenu) && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => { setShowColMenu(false); setShowTagMenu(null); }} />
      )}
    </Layout>
  );
};

export default Contacts;
