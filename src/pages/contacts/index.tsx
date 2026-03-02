/**
 * Contacts Management Page
 * Full CRUD with sorting, pagination, tooltips, keyboard shortcuts
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Layout from '../../components/Layout';
import SEO, { PAGE_SEO } from '../../components/SEO';
import { SkeletonTable } from '../../components/Skeleton';
import { useToastContext } from '../../contexts/ToastContext';
import * as api from '../../api/client';

// SVG Icons — emerald theme (#059669)
const AddUserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 5v14m-7-7h14"/>
  </svg>
);
const UploadIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path fill="none" stroke="#059669" strokeMiterlimit="10" strokeWidth="1.5" d="M12 2.5v17.14m7.62-9.52L12 2.5l-7.62 7.62m15.24 8.57v3.81H4.38v-3.81"/>
  </svg>
);
const RefreshIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path fill="#059669" d="m13.146 11.05-.174-1.992 2.374-.208a5 5 0 1 0 .82 6.173l2.002.5a7 7 0 1 1-1.315-7.996l-.245-2.803L18.6 4.55l.523 5.977z"/>
  </svg>
);
const DownloadIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path stroke="#059669" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="m8 12 4 4m0 0 4-4m-4 4V6.8c0-1.39 0-2.086-.55-2.865-.366-.517-1.42-1.155-2.047-1.24-.945-.128-1.304.059-2.022.433A10 10 0 0 0 2 12c0 5.523 4.477 10 10 10s10-4.477 10-10a10 10 0 0 0-5-8.662"/>
  </svg>
);
const ExportIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);
const EditIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 4H6.8c-1.68 0-2.52 0-3.162.327a3 3 0 0 0-1.311 1.311C2 6.28 2 7.12 2 8.8v8.4c0 1.68 0 2.52.327 3.162a3 3 0 0 0 1.311 1.311C4.28 22 5.12 22 6.8 22h8.4c1.68 0 2.52 0 3.162-.327a3 3 0 0 0 1.311-1.311C20 19.72 20 18.88 20 17.2V13M8 16h1.675c.489 0 .733 0 .963-.055.204-.05.4-.13.579-.24.201-.123.374-.296.72-.642L21.5 5.5a2.121 2.121 0 0 0-3-3l-9.563 9.563c-.346.346-.519.519-.642.72a2 2 0 0 0-.24.579c-.055.23-.055.474-.055.963z"/>
  </svg>
);
const DeleteIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 3h6M3 6h18m-2 0-.701 10.52c-.106 1.583-.158 2.374-.499 2.98a3 3 0 0 1-1.298 1.215C16.56 21 15.767 21 14.182 21H9.818c-1.585 0-2.378 0-2.82-.285a3 3 0 0 1-1.298-1.215c-.341-.606-.393-1.397-.499-2.98L5 6m5 4.5v5m4-5v5"/>
  </svg>
);
const SortIcon = ({ dir }: { dir: 'asc' | 'desc' | null }) => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginLeft: 4, opacity: dir ? 1 : 0.3 }}>
    <path d="M6 1l3 4H3z" fill={dir === 'asc' ? '#059669' : '#d1d5db'} />
    <path d="M6 11l3-4H3z" fill={dir === 'desc' ? '#059669' : '#d1d5db'} />
  </svg>
);

type SortKey = 'name' | 'phone' | 'email' | 'updatedAt';
type SortDir = 'asc' | 'desc';
const PAGE_SIZE = 25;

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

  // Sorting
  const [sortKey, setSortKey] = useState<SortKey>('updatedAt');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);

  // Form state
  const [formName, setFormName] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formShippingAddress, setFormShippingAddress] = useState('');
  const [formBillingAddress, setFormBillingAddress] = useState('');
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

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listContacts();
      setContacts(data);
    } catch (err) {
      console.error('Failed to load contacts:', err);
      toast.error('Failed to load contacts');
    } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  // Keyboard shortcuts: N=new, /=search, Esc=close modals
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      if (e.key === 'Escape') {
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
  }, [showModal, showEditModal, showDeleteModal]);

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
      const cmp = av.localeCompare(bv, undefined, { sensitivity: 'base' });
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [contacts, searchQuery, sortKey, sortDir]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedContacts = filteredSorted.slice((safeCurrentPage - 1) * PAGE_SIZE, safeCurrentPage * PAGE_SIZE);

  // Reset page when search changes
  useEffect(() => { setCurrentPage(1); }, [searchQuery]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  const resetForm = () => {
    setFormName(''); setFormPhone(''); setFormEmail('');
    setFormShippingAddress(''); setFormBillingAddress('');
    setFormOptInWA(false); setFormOptInSms(false); setFormOptInEmail(false);
    setFormAllowlistWA(false); setFormAllowlistSms(false); setFormAllowlistEmail(false);
  };

  const handleCreate = async () => {
    if (!formPhone && !formEmail) { toast.warning('Phone or email is required'); return; }
    setSaving(true);
    try {
      const result = await api.createContact({
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined,
        billingAddress: formBillingAddress || undefined,
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
    setFormName(contact.name || ''); setFormPhone(contact.phone || ''); setFormEmail(contact.email || '');
    setFormShippingAddress(contact.shippingAddress || ''); setFormBillingAddress(contact.billingAddress || '');
    setFormOptInWA(contact.optInWhatsApp || false); setFormOptInSms(contact.optInSms || false); setFormOptInEmail(contact.optInEmail || false);
    setFormAllowlistWA(contact.allowlistWhatsApp || false); setFormAllowlistSms(contact.allowlistSms || false); setFormAllowlistEmail(contact.allowlistEmail || false);
    setShowEditModal(true);
  };

  const handleUpdate = async () => {
    if (!editingContact || (!formPhone && !formEmail)) { toast.warning('Phone or email is required'); return; }
    setSaving(true);
    try {
      const result = await api.updateContact(editingContact.contactId, {
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined,
        billingAddress: formBillingAddress || undefined,
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
      if (result) { toast.success('Contact deleted'); await loadContacts(); }
      else toast.error('Failed to delete contact');
    } catch { toast.error('Failed to delete contact'); }
  };

  // CSV import
  const handleFileSelect = (file: File) => {
    if (!file.name.endsWith('.csv') && !file.name.endsWith('.vcf')) { toast.error('Please select a CSV or VCF file'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      const parsed = file.name.endsWith('.vcf') ? parseVCard(content) : api.parseContactsCSV(content);
      setPreviewData(parsed); setImportResult(null);
    };
    reader.readAsText(file);
  };

  const parseVCard = (content: string): Partial<api.Contact>[] => {
    const results: Partial<api.Contact>[] = [];
    for (const vcard of content.split('END:VCARD')) {
      if (!vcard.includes('BEGIN:VCARD')) continue;
      const c: Partial<api.Contact> = {};
      const fn = vcard.match(/FN:(.+)/); if (fn) c.name = fn[1].trim();
      const tel = vcard.match(/TEL[^:]*:(.+)/); if (tel) { let p = tel[1].replace(/[^\d+]/g, ''); if (!p.startsWith('+')) p = '+' + p; c.phone = p; }
      const em = vcard.match(/EMAIL[^:]*:(.+)/); if (em) c.email = em[1].trim();
      if (c.phone || c.email) results.push(c);
    }
    return results;
  };

  const handleImport = async () => {
    if (previewData.length === 0) return;
    setImporting(true);
    try {
      const result = await api.importContacts(previewData);
      setImportResult(result);
      if (result.created > 0 || result.updated > 0) await loadContacts();
    } catch { toast.error('Import failed'); }
    finally { setImporting(false); }
  };

  const handleExport = () => {
    const csv = api.exportContactsToCSV(contacts);
    api.downloadFile(csv, `contacts_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
  };

  const downloadTemplate = () => {
    api.downloadFile(`name,phone,email\nJohn Doe,+919876543210,john@example.com\nJane Smith,+918765432109,`, 'contacts_template.csv', 'text/csv');
  };

  const SortHeader = ({ label, field, width }: { label: string; field: SortKey; width?: number }) => (
    <th style={{ cursor: 'pointer', userSelect: 'none', width, background: '#ECFDF5' }} onClick={() => toggleSort(field)}>
      <span style={{ display: 'inline-flex', alignItems: 'center' }}>
        {label}<SortIcon dir={sortKey === field ? sortDir : null} />
      </span>
    </th>
  );


  const [showOptIn, setShowOptIn] = useState(false);

  // Contact form fields (shared between add/edit modals)
  const renderContactForm = () => (
    <div className="ct-form-grid">
      <div className="ct-form-row">
        <label className="ct-label">Name</label>
        <input className="ct-input" value={formName} onChange={e => setFormName(e.target.value)} placeholder="Full name" />
      </div>
      <div className="ct-form-2col">
        <div className="ct-form-row">
          <label className="ct-label">Phone *</label>
          <input className="ct-input" value={formPhone} onChange={e => setFormPhone(e.target.value)} placeholder="+919876543210" />
        </div>
        <div className="ct-form-row">
          <label className="ct-label">Email</label>
          <input className="ct-input" value={formEmail} onChange={e => setFormEmail(e.target.value)} placeholder="email@example.com" />
        </div>
      </div>
      <div className="ct-form-2col">
        <div className="ct-form-row">
          <label className="ct-label">Shipping Address</label>
          <textarea className="ct-textarea" value={formShippingAddress} onChange={e => setFormShippingAddress(e.target.value)} placeholder="Shipping address" rows={2} />
        </div>
        <div className="ct-form-row">
          <label className="ct-label">Billing Address</label>
          <textarea className="ct-textarea" value={formBillingAddress} onChange={e => setFormBillingAddress(e.target.value)} placeholder="Billing address" rows={2} />
        </div>
      </div>
      <button type="button" className="ct-toggle-optin" onClick={() => setShowOptIn(!showOptIn)}>
        {showOptIn ? '▾' : '▸'} Opt-in &amp; Allowlist
      </button>
      {showOptIn && (
        <div className="ct-optin-section">
          <div className="ct-form-row">
            <label className="ct-label">Opt-in</label>
            <div className="ct-checks">
              <label className="ct-check"><input type="checkbox" checked={formOptInWA} onChange={e => setFormOptInWA(e.target.checked)} /> WhatsApp</label>
              <label className="ct-check"><input type="checkbox" checked={formOptInSms} onChange={e => setFormOptInSms(e.target.checked)} /> SMS</label>
              <label className="ct-check"><input type="checkbox" checked={formOptInEmail} onChange={e => setFormOptInEmail(e.target.checked)} /> Email</label>
            </div>
          </div>
          <div className="ct-form-row">
            <label className="ct-label">Allowlist</label>
            <div className="ct-checks">
              <label className="ct-check"><input type="checkbox" checked={formAllowlistWA} onChange={e => setFormAllowlistWA(e.target.checked)} /> WhatsApp</label>
              <label className="ct-check"><input type="checkbox" checked={formAllowlistSms} onChange={e => setFormAllowlistSms(e.target.checked)} /> SMS</label>
              <label className="ct-check"><input type="checkbox" checked={formAllowlistEmail} onChange={e => setFormAllowlistEmail(e.target.checked)} /> Email</label>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO {...PAGE_SEO.contacts} />
      <div className="ct-page">
        {/* Toolbar */}
        <div className="ct-toolbar">
          <div className="ct-toolbar-left">
            <button className="ct-icon-btn" onClick={() => { resetForm(); setShowModal(true); }} title="Add contact (N)"><AddUserIcon /></button>
            <button className="ct-icon-btn" onClick={() => setShowImport(!showImport)} title="Import CSV/VCF"><UploadIcon /></button>
            <button className="ct-icon-btn" onClick={handleExport} title="Export CSV"><ExportIcon /></button>
            <button className="ct-icon-btn" onClick={loadContacts} title="Refresh"><RefreshIcon /></button>
          </div>
          <div className="ct-toolbar-right">
            <span className="ct-count">{filteredSorted.length} contact{filteredSorted.length !== 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* Import section */}
        {showImport && (
          <div className="ct-import-section">
            <div className="ct-import-header">
              <span>Import Contacts</span>
              <button className="ct-link-btn" onClick={downloadTemplate}><DownloadIcon /> Template</button>
            </div>
            <div className="ct-import-body">
              <input ref={fileInputRef} type="file" accept=".csv,.vcf" onChange={e => e.target.files?.[0] && handleFileSelect(e.target.files[0])} style={{ display: 'none' }} />
              <button className="ct-btn ct-btn-outline" onClick={() => fileInputRef.current?.click()}>Choose File</button>
              {previewData.length > 0 && (
                <div className="ct-import-preview">
                  <span>{previewData.length} contacts ready</span>
                  <button className="ct-btn ct-btn-primary" onClick={handleImport} disabled={importing}>
                    {importing ? 'Importing...' : 'Import'}
                  </button>
                </div>
              )}
              {importResult && (
                <div className="ct-import-result">
                  Created: {importResult.created} | Updated: {importResult.updated} | Errors: {importResult.errors}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Search */}
        <div className="ct-search-wrap">
          <input
            ref={searchInputRef}
            className="ct-search"
            type="text"
            placeholder="Search contacts... (press /)"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Table */}
        {loading ? (
          <SkeletonTable rows={8} cols={8} />
        ) : (
          <>
            <div className="ct-table-wrap">
              <table className="ct-table">
                <thead>
                  <tr>
                    <th style={{ width: 40, background: '#ECFDF5' }}>#</th>
                    <SortHeader label="Name" field="name" />
                    <SortHeader label="Phone" field="phone" />
                    <SortHeader label="Email" field="email" />
                    <th style={{ background: '#ECFDF5' }}>Shipping</th>
                    <th style={{ background: '#ECFDF5' }}>Billing</th>
                    <SortHeader label="Updated" field="updatedAt" />
                    <th style={{ width: 90, background: '#ECFDF5' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedContacts.length === 0 ? (
                    <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: '#6b7280' }}>No contacts found</td></tr>
                  ) : paginatedContacts.map((c, i) => (
                    <tr key={c.contactId}>
                      <td style={{ color: '#9ca3af' }}>{(safeCurrentPage - 1) * PAGE_SIZE + i + 1}</td>
                      <td>{c.name || '—'}</td>
                      <td>{c.phone || '—'}</td>
                      <td>{c.email || '—'}</td>
                      <td><span className="ct-addr" title={c.shippingAddress || ''}>{c.shippingAddress || '—'}</span></td>
                      <td><span className="ct-addr" title={c.billingAddress || ''}>{c.billingAddress || '—'}</span></td>
                      <td className="ct-time" title={c.updatedAt ? new Date(c.updatedAt).toLocaleString() : ''}>{timeAgo(c.updatedAt)}</td>
                      <td>
                        <div className="ct-actions">
                          <button className="ct-act-btn" onClick={() => handleEdit(c)} title="Edit"><EditIcon size={16} /></button>
                          <button className="ct-act-btn ct-act-del" onClick={() => { setShowDeleteModal(c.contactId); setDeleteContactName(c.name || c.phone); }} title="Delete"><DeleteIcon size={16} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="ct-pagination">
                <button className="ct-page-btn" disabled={safeCurrentPage <= 1} onClick={() => setCurrentPage(p => p - 1)}>← Prev</button>
                <span className="ct-page-info">Page {safeCurrentPage} of {totalPages}</span>
                <button className="ct-page-btn" disabled={safeCurrentPage >= totalPages} onClick={() => setCurrentPage(p => p + 1)}>Next →</button>
              </div>
            )}
          </>
        )}

        {/* Add Contact Modal */}
        {showModal && (
          <div className="ct-overlay" onClick={() => setShowModal(false)}>
            <div className="ct-modal" onClick={e => e.stopPropagation()}>
              <div className="ct-modal-header">
                <span>New Contact</span>
                <button className="ct-modal-close" onClick={() => setShowModal(false)}>×</button>
              </div>
              {renderContactForm()}
              <div className="ct-modal-footer">
                <button className="ct-btn ct-btn-outline" onClick={() => setShowModal(false)}>Cancel</button>
                <button className="ct-btn ct-btn-primary" onClick={handleCreate} disabled={saving}>{saving ? 'Saving...' : 'Create'}</button>
              </div>
            </div>
          </div>
        )}

        {/* Edit Contact Modal */}
        {showEditModal && editingContact && (
          <div className="ct-overlay" onClick={() => { setShowEditModal(false); setEditingContact(null); }}>
            <div className="ct-modal" onClick={e => e.stopPropagation()}>
              <div className="ct-modal-header">
                <span>Edit Contact</span>
                <button className="ct-modal-close" onClick={() => { setShowEditModal(false); setEditingContact(null); }}>×</button>
              </div>
              {renderContactForm()}
              <div className="ct-modal-footer">
                <button className="ct-btn ct-btn-outline" onClick={() => { setShowEditModal(false); setEditingContact(null); }}>Cancel</button>
                <button className="ct-btn ct-btn-primary" onClick={handleUpdate} disabled={saving}>{saving ? 'Saving...' : 'Update'}</button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && (
          <div className="ct-overlay" onClick={() => setShowDeleteModal(null)}>
            <div className="ct-modal ct-modal-sm" onClick={e => e.stopPropagation()}>
              <div className="ct-modal-header">
                <span>Delete Contact</span>
                <button className="ct-modal-close" onClick={() => setShowDeleteModal(null)}>×</button>
              </div>
              <div style={{ padding: '16px 20px', color: '#374151' }}>
                Are you sure you want to delete <strong>{deleteContactName}</strong>? This cannot be undone.
              </div>
              <div className="ct-modal-footer">
                <button className="ct-btn ct-btn-outline" onClick={() => setShowDeleteModal(null)}>Cancel</button>
                <button className="ct-btn ct-btn-danger" onClick={() => handleDelete(showDeleteModal)}>Delete</button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .ct-page { padding: 12px 20px 20px; }
        .ct-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 0; gap: 12px; flex-wrap: wrap; }
        .ct-toolbar-left { display: flex; gap: 8px; align-items: center; }
        .ct-toolbar-right { display: flex; align-items: center; gap: 12px; }
        .ct-count { font-size: 13px; color: #6b7280; font-weight: 500; }
        .ct-icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border: 1.5px solid #D1FAE5; background: #fff; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
        .ct-icon-btn:hover { background: #ECFDF5; border-color: #059669; }
        .ct-import-section { border: 1.5px solid #D1FAE5; border-radius: 12px; padding: 16px; margin-bottom: 12px; background: #fff; }
        .ct-import-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-weight: 600; font-size: 14px; color: #111827; }
        .ct-import-body { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .ct-import-preview { display: flex; align-items: center; gap: 12px; font-size: 13px; color: #059669; }
        .ct-import-result { font-size: 13px; color: #059669; margin-top: 8px; }
        .ct-link-btn { display: inline-flex; align-items: center; gap: 4px; background: none; border: none; color: #059669; font-size: 13px; font-weight: 500; cursor: pointer; padding: 4px 0; }
        .ct-link-btn:hover { text-decoration: underline; }
        .ct-search-wrap { margin-bottom: 12px; }
        .ct-search { width: 100%; padding: 10px 14px; border: 1.5px solid #D1FAE5; border-radius: 10px; font-size: 14px; outline: none; background: #fff; transition: all 0.15s; }
        .ct-search:focus { border-color: #059669; box-shadow: 0 0 0 3px rgba(5,150,105,0.1); }
        .ct-table-wrap { overflow-x: auto; border: 1.5px solid #D1FAE5; border-radius: 12px; background: #fff; }
        .ct-table { width: 100%; border-collapse: collapse; font-size: 14px; }
        .ct-table th { padding: 10px 12px; text-align: left; font-weight: 600; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; background: #ECFDF5; border-bottom: 1.5px solid #D1FAE5; white-space: nowrap; }
        .ct-table td { padding: 10px 12px; border-bottom: 1px solid #ECFDF5; color: #111827; }
        .ct-table tbody tr:hover { background: #f0fdf9; }
        .ct-table tbody tr:last-child td { border-bottom: none; }
        .ct-addr { display: inline-block; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: help; }
        .ct-time { font-size: 13px; color: #6b7280; white-space: nowrap; cursor: help; }
        .ct-actions { display: flex; gap: 6px; }
        .ct-act-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: 1px solid #D1FAE5; background: #fff; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
        .ct-act-btn:hover { background: #ECFDF5; border-color: #059669; }
        .ct-act-del:hover { background: #fef2f2; border-color: #ef4444; }
        .ct-pagination { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 16px 0; }
        .ct-page-btn { padding: 8px 16px; border: 1.5px solid #D1FAE5; background: #fff; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; color: #059669; transition: all 0.15s; }
        .ct-page-btn:hover:not(:disabled) { background: #ECFDF5; border-color: #059669; }
        .ct-page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .ct-page-info { font-size: 13px; color: #6b7280; font-weight: 500; }
        .ct-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 10000; display: flex; align-items: center; justify-content: center; }
        .ct-modal { background: #fff; border-radius: 14px; width: 480px; max-width: calc(100vw - 32px); max-height: calc(100vh - 64px); overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
        .ct-modal-sm { width: 380px; }
        .ct-modal-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-bottom: 1px solid #D1FAE5; font-weight: 600; font-size: 16px; color: #111827; background: #ECFDF5; border-radius: 14px 14px 0 0; }
        .ct-modal-close { background: none; border: none; font-size: 22px; color: #9ca3af; cursor: pointer; line-height: 1; padding: 0; min-height: auto; }
        .ct-modal-close:hover { color: #374151; }
        .ct-modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 24px; border-top: 1px solid #D1FAE5; }
        .ct-form-grid { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
        .ct-form-row { display: flex; flex-direction: column; gap: 6px; }
        .ct-form-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .ct-label { font-size: 13px; font-weight: 600; color: #374151; letter-spacing: 0.2px; }
        .ct-input { padding: 10px 14px; border: 1.5px solid #D1FAE5; border-radius: 10px; font-size: 14px; outline: none; transition: all 0.15s; background: #fff; }
        .ct-input:focus { border-color: #059669; box-shadow: 0 0 0 3px rgba(5,150,105,0.1); }
        .ct-textarea { padding: 10px 14px; border: 1.5px solid #D1FAE5; border-radius: 10px; font-size: 14px; outline: none; resize: vertical; font-family: inherit; transition: all 0.15s; background: #fff; }
        .ct-textarea:focus { border-color: #059669; box-shadow: 0 0 0 3px rgba(5,150,105,0.1); }
        .ct-toggle-optin { background: none; border: none; color: #059669; font-size: 13px; font-weight: 600; cursor: pointer; padding: 0; text-align: left; min-height: auto; }
        .ct-toggle-optin:hover { text-decoration: underline; }
        .ct-optin-section { display: flex; flex-direction: column; gap: 14px; padding: 14px 16px; background: #ECFDF5; border-radius: 10px; }
        .ct-checks { display: flex; gap: 16px; flex-wrap: wrap; }
        .ct-check { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #374151; cursor: pointer; }
        .ct-check input[type="checkbox"] { accent-color: #059669; min-height: 16px; }
        .ct-btn { padding: 9px 18px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.15s; border: none; }
        .ct-btn-primary { background: #059669; color: #fff; }
        .ct-btn-primary:hover:not(:disabled) { background: #047857; }
        .ct-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .ct-btn-outline { background: #fff; color: #374151; border: 1.5px solid #D1FAE5; }
        .ct-btn-outline:hover { background: #ECFDF5; border-color: #059669; }
        .ct-btn-danger { background: #ef4444; color: #fff; }
        .ct-btn-danger:hover { background: #dc2626; }
      `}</style>
    </Layout>
  );
};

export default Contacts;