/**
 * Contacts Management Page
 * Full CRUD operations with Amplify Data API
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import ContactImportExport from '../../components/ContactImportExport';
import SEO, { PAGE_SEO } from '../../components/SEO';
import * as api from '../../api/client';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const Contacts: React.FC<PageProps> = ({ signOut, user }) => {
  const [showModal, setShowModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingContact, setEditingContact] = useState<api.Contact | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [formName, setFormName] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formEmail, setFormEmail] = useState('');
  // Opt-in fields
  const [formOptInWA, setFormOptInWA] = useState(false);
  const [formOptInSms, setFormOptInSms] = useState(false);
  const [formOptInEmail, setFormOptInEmail] = useState(false);
  // Allowlist fields (Requirement 3.2)
  const [formAllowlistWA, setFormAllowlistWA] = useState(false);
  const [formAllowlistSms, setFormAllowlistSms] = useState(false);
  const [formAllowlistEmail, setFormAllowlistEmail] = useState(false);
  
  // Contacts state
  const [contacts, setContacts] = useState<api.Contact[]>([]);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listContacts();
      setContacts(data);
      
      // Check connection status
      const connStatus = api.getConnectionStatus();
      if (connStatus.status === 'disconnected' && connStatus.lastError) {
        setError(`Connection issue: ${connStatus.lastError}`);
      }
    } catch (err) {
      console.error('Failed to load contacts:', err);
      setError('Failed to load contacts. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const filteredContacts = contacts.filter(c => 
    (c.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (c.phone || '').includes(searchQuery) ||
    (c.email || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const resetForm = () => {
    setFormName('');
    setFormPhone('');
    setFormEmail('');
    setFormOptInWA(false);
    setFormOptInSms(false);
    setFormOptInEmail(false);
    setFormAllowlistWA(false);
    setFormAllowlistSms(false);
    setFormAllowlistEmail(false);
  };

  const handleCreate = async () => {
    if (!formPhone && !formEmail) {
      setError('Phone or email is required');
      return;
    }
    
    setSaving(true);
    setError(null);
    try {
      const result = await api.createContact({
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        optInWhatsApp: formOptInWA,
        optInSms: formOptInSms,
        optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA,
        allowlistSms: formAllowlistSms,
        allowlistEmail: formAllowlistEmail,
      });
      
      if (result) {
        setShowModal(false);
        resetForm();
        await loadContacts();
      } else {
        setError('Failed to create contact');
      }
    } catch (err) {
      console.error('Create error:', err);
      setError('Failed to create contact');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (contact: api.Contact) => {
    setEditingContact(contact);
    setFormName(contact.name || '');
    setFormPhone(contact.phone || '');
    setFormEmail(contact.email || '');
    setFormOptInWA(contact.optInWhatsApp || false);
    setFormOptInSms(contact.optInSms || false);
    setFormOptInEmail(contact.optInEmail || false);
    setFormAllowlistWA(contact.allowlistWhatsApp || false);
    setFormAllowlistSms(contact.allowlistSms || false);
    setFormAllowlistEmail(contact.allowlistEmail || false);
    setShowEditModal(true);
  };

  const handleUpdate = async () => {
    if (!editingContact || (!formPhone && !formEmail)) {
      setError('Phone or email is required');
      return;
    }
    
    setSaving(true);
    setError(null);
    try {
      const result = await api.updateContact(editingContact.contactId, {
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        optInWhatsApp: formOptInWA,
        optInSms: formOptInSms,
        optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA,
        allowlistSms: formAllowlistSms,
        allowlistEmail: formAllowlistEmail,
      });
      
      if (result) {
        setShowEditModal(false);
        setEditingContact(null);
        resetForm();
        await loadContacts();
      } else {
        setError('Failed to update contact');
      }
    } catch (err) {
      console.error('Update error:', err);
      setError('Failed to update contact');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (contactId: string) => {
    if (!confirm('Are you sure you want to delete this contact?')) return;
    
    try {
      const result = await api.deleteContact(contactId);
      if (result) {
        await loadContacts();
      } else {
        setError('Failed to delete contact');
      }
    } catch (err) {
      console.error('Delete error:', err);
      setError('Failed to delete contact');
    }
  };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title={PAGE_SEO.contacts.title}
        description={PAGE_SEO.contacts.description}
        keywords={PAGE_SEO.contacts.keywords}
        canonical="/contacts"
        noindex={true}
      />
      <div className="page">
        <PageHeader 
          title="Contacts" 
          subtitle="Manage your contact database"
          icon="contacts"
          actions={
            <>
              <button className="btn-secondary" onClick={loadContacts} disabled={loading}>↻ {loading ? 'Loading...' : 'Refresh'}</button>
              <button className="btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>+ Add Contact</button>
            </>
          }
        />

        {error && <div className="error-banner">{error} <button onClick={() => setError(null)}>✕</button></div>}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{contacts.length}</div>
            <div className="stat-label">Total Contacts</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{contacts.filter(c => c.optInWhatsApp).length}</div>
            <div className="stat-label">WhatsApp Opt-In</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{contacts.filter(c => c.optInSms).length}</div>
            <div className="stat-label">SMS Opt-In</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{contacts.filter(c => c.optInEmail).length}</div>
            <div className="stat-label">Email Opt-In</div>
          </div>
        </div>

        {/* Import/Export Section */}
        <ContactImportExport 
          contacts={contacts} 
          onImportComplete={loadContacts} 
        />

        <div className="search-bar">
          <input
            type="text"
            className="search-input"
            placeholder="Search contacts by name, phone, or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="section">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Opt-In</th>
                  <th>Last Message</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredContacts.map(contact => (
                  <tr key={contact.contactId}>
                    <td><strong>{contact.name || '-'}</strong></td>
                    <td>{contact.phone || '-'}</td>
                    <td>{contact.email || '-'}</td>
                    <td>
                      <div className="opt-in-badges">
                        {contact.optInWhatsApp && contact.allowlistWhatsApp && <span className="badge badge-green">WA ✓</span>}
                        {contact.optInWhatsApp && !contact.allowlistWhatsApp && <span className="badge badge-yellow">WA</span>}
                        {contact.optInSms && contact.allowlistSms && <span className="badge badge-blue">SMS ✓</span>}
                        {contact.optInSms && !contact.allowlistSms && <span className="badge badge-yellow">SMS</span>}
                        {contact.optInEmail && contact.allowlistEmail && <span className="badge badge-purple">Email ✓</span>}
                        {contact.optInEmail && !contact.allowlistEmail && <span className="badge badge-yellow">Email</span>}
                        {!contact.optInWhatsApp && !contact.optInSms && !contact.optInEmail && (
                          <span className="badge badge-gray">None</span>
                        )}
                      </div>
                    </td>
                    <td>{contact.lastInboundMessageAt ? new Date(contact.lastInboundMessageAt).toLocaleDateString() : '-'}</td>
                    <td>
                      <div className="action-buttons">
                        <button className="btn-icon" title="Edit" onClick={() => handleEdit(contact)}>✎</button>
                        <button className="btn-icon" title="Message" onClick={() => window.location.href = '/messaging'}>✉</button>
                        <button className="btn-icon btn-icon-danger" title="Delete" onClick={() => handleDelete(contact.contactId)}>⌫</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredContacts.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-table">
                      {loading ? 'Loading...' : searchQuery ? 'No contacts match your search' : 'No contacts yet. Add your first contact!'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Add Contact Modal */}
        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <h2>Add Contact</h2>
              <div className="form-group">
                <label>Name</label>
                <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="Contact name" />
              </div>
              <div className="form-group">
                <label>Phone Number *</label>
                <input type="tel" value={formPhone} onChange={(e) => setFormPhone(e.target.value)} placeholder="+91 98765 43210" />
                <div className="help-text">Include country code</div>
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={formEmail} onChange={(e) => setFormEmail(e.target.value)} placeholder="email@example.com" />
              </div>
              <div className="form-group">
                <label>Opt-In Channels</label>
                <div className="checkbox-group">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInWA} onChange={(e) => setFormOptInWA(e.target.checked)} />
                    <span>WhatsApp</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInSms} onChange={(e) => setFormOptInSms(e.target.checked)} />
                    <span>SMS</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInEmail} onChange={(e) => setFormOptInEmail(e.target.checked)} />
                    <span>Email</span>
                  </label>
                </div>
              </div>
              <div className="form-group">
                <label>Allowlist (Required for Sending)</label>
                <div className="help-text" style={{marginBottom: '8px'}}>Contacts must be both opted-in AND allowlisted to receive messages</div>
                <div className="checkbox-group">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistWA} onChange={(e) => setFormAllowlistWA(e.target.checked)} disabled={!formOptInWA} />
                    <span>WhatsApp {!formOptInWA && '(opt-in first)'}</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistSms} onChange={(e) => setFormAllowlistSms(e.target.checked)} disabled={!formOptInSms} />
                    <span>SMS {!formOptInSms && '(opt-in first)'}</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistEmail} onChange={(e) => setFormAllowlistEmail(e.target.checked)} disabled={!formOptInEmail} />
                    <span>Email {!formOptInEmail && '(opt-in first)'}</span>
                  </label>
                </div>
              </div>
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button className="btn-primary" onClick={handleCreate} disabled={(!formPhone && !formEmail) || saving}>
                  {saving ? 'Saving...' : 'Add Contact'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edit Contact Modal */}
        {showEditModal && (
          <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <h2>Edit Contact</h2>
              <div className="form-group">
                <label>Name</label>
                <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="Contact name" />
              </div>
              <div className="form-group">
                <label>Phone Number *</label>
                <input type="tel" value={formPhone} onChange={(e) => setFormPhone(e.target.value)} placeholder="+91 98765 43210" />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={formEmail} onChange={(e) => setFormEmail(e.target.value)} placeholder="email@example.com" />
              </div>
              <div className="form-group">
                <label>Opt-In Channels</label>
                <div className="checkbox-group">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInWA} onChange={(e) => setFormOptInWA(e.target.checked)} />
                    <span>WhatsApp</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInSms} onChange={(e) => setFormOptInSms(e.target.checked)} />
                    <span>SMS</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formOptInEmail} onChange={(e) => setFormOptInEmail(e.target.checked)} />
                    <span>Email</span>
                  </label>
                </div>
              </div>
              <div className="form-group">
                <label>Allowlist (Required for Sending)</label>
                <div className="help-text" style={{marginBottom: '8px'}}>Contacts must be both opted-in AND allowlisted to receive messages</div>
                <div className="checkbox-group">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistWA} onChange={(e) => setFormAllowlistWA(e.target.checked)} disabled={!formOptInWA} />
                    <span>WhatsApp {!formOptInWA && '(opt-in first)'}</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistSms} onChange={(e) => setFormAllowlistSms(e.target.checked)} disabled={!formOptInSms} />
                    <span>SMS {!formOptInSms && '(opt-in first)'}</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={formAllowlistEmail} onChange={(e) => setFormAllowlistEmail(e.target.checked)} disabled={!formOptInEmail} />
                    <span>Email {!formOptInEmail && '(opt-in first)'}</span>
                  </label>
                </div>
              </div>
              <div className="form-actions">
                <button className="btn-secondary" onClick={() => { setShowEditModal(false); setEditingContact(null); }}>Cancel</button>
                <button className="btn-primary" onClick={handleUpdate} disabled={(!formPhone && !formEmail) || saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Contacts;
