/**
 * Contacts Management Page
 * Full CRUD operations with Amplify Data API
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../components/Layout';
import PageHeader from '../../components/PageHeader';
import ContactImportExport from '../../components/ContactImportExport';
import SEO, { PAGE_SEO } from '../../components/SEO';
import Button from '../../components/ui/Button';
import { SkeletonTable } from '../../components/Skeleton';
import { useToastContext } from '../../contexts/ToastContext';
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
  const toast = useToastContext();
  
  // Form state
  const [formName, setFormName] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formShippingAddress, setFormShippingAddress] = useState('');
  const [formBillingAddress, setFormBillingAddress] = useState('');
  // Opt-in fields
  const [formOptInWA, setFormOptInWA] = useState(false);
  const [formOptInSms, setFormOptInSms] = useState(false);
  const [formOptInEmail, setFormOptInEmail] = useState(false);
  // Allowlist fields (Requirement 3.2)
  const [formAllowlistWA, setFormAllowlistWA] = useState(false);
  const [formAllowlistSms, setFormAllowlistSms] = useState(false);
  const [formAllowlistEmail, setFormAllowlistEmail] = useState(false);
  
  // Delete confirmation modal
  const [showDeleteModal, setShowDeleteModal] = useState<string | null>(null);
  const [deleteContactName, setDeleteContactName] = useState('');
  
  // Contacts state
  const [contacts, setContacts] = useState<api.Contact[]>([]);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listContacts();
      setContacts(data);
      
      // Check connection status
      const connStatus = api.getConnectionStatus();
      if (connStatus.status === 'disconnected' && connStatus.lastError) {
        toast.warning(`Connection issue: ${connStatus.lastError}`);
      }
    } catch (err) {
      console.error('Failed to load contacts:', err);
      toast.error('Failed to load contacts. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [toast]);

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
    setFormShippingAddress('');
    setFormBillingAddress('');
    setFormOptInWA(false);
    setFormOptInSms(false);
    setFormOptInEmail(false);
    setFormAllowlistWA(false);
    setFormAllowlistSms(false);
    setFormAllowlistEmail(false);
  };

  const handleCreate = async () => {
    if (!formPhone && !formEmail) {
      toast.warning('Phone or email is required');
      return;
    }
    
    setSaving(true);
    try {
      const result = await api.createContact({
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined,
        billingAddress: formBillingAddress || undefined,
        optInWhatsApp: formOptInWA,
        optInSms: formOptInSms,
        optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA,
        allowlistSms: formAllowlistSms,
        allowlistEmail: formAllowlistEmail,
      });
      
      if (result) {
        toast.success('Contact created successfully');
        setShowModal(false);
        resetForm();
        await loadContacts();
      } else {
        toast.error('Failed to create contact');
      }
    } catch (err) {
      console.error('Create error:', err);
      toast.error('Failed to create contact');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (contact: api.Contact) => {
    setEditingContact(contact);
    setFormName(contact.name || '');
    setFormPhone(contact.phone || '');
    setFormEmail(contact.email || '');
    setFormShippingAddress(contact.shippingAddress || '');
    setFormBillingAddress(contact.billingAddress || '');
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
      toast.warning('Phone or email is required');
      return;
    }
    
    setSaving(true);
    try {
      const result = await api.updateContact(editingContact.contactId, {
        name: formName,
        phone: formPhone.startsWith('+') ? formPhone : `+${formPhone}`,
        email: formEmail || undefined,
        shippingAddress: formShippingAddress || undefined,
        billingAddress: formBillingAddress || undefined,
        optInWhatsApp: formOptInWA,
        optInSms: formOptInSms,
        optInEmail: formOptInEmail,
        allowlistWhatsApp: formAllowlistWA,
        allowlistSms: formAllowlistSms,
        allowlistEmail: formAllowlistEmail,
      });
      
      if (result) {
        toast.success('Contact updated successfully');
        setShowEditModal(false);
        setEditingContact(null);
        resetForm();
        await loadContacts();
      } else {
        toast.error('Failed to update contact');
      }
    } catch (err) {
      console.error('Update error:', err);
      toast.error('Failed to update contact');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (contactId: string) => {
    setShowDeleteModal(null);
    
    try {
      const result = await api.deleteContact(contactId);
      if (result) {
        toast.success('Contact deleted');
        await loadContacts();
      } else {
        toast.error('Failed to delete contact');
      }
    } catch (err) {
      console.error('Delete error:', err);
      toast.error('Failed to delete contact');
    }
  };

  const openDeleteModal = (contact: api.Contact) => {
    setShowDeleteModal(contact.contactId);
    setDeleteContactName(contact.name || contact.phone || 'this contact');
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
              <Button variant="secondary" icon="refresh" onClick={loadContacts} disabled={loading} loading={loading}>Refresh</Button>
              <Button variant="primary" icon="create" onClick={() => { resetForm(); setShowModal(true); }}>Add Contact</Button>
            </>
          }
        />

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
          {loading ? (
            <div style={{ padding: '20px' }}>
              <SkeletonTable rows={5} cols={6} />
            </div>
          ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Shipping</th>
                  <th>Billing</th>
                  <th>Opt-In</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredContacts.map(contact => (
                  <tr key={contact.contactId}>
                    <td><strong>{contact.name || '-'}</strong></td>
                    <td>{contact.phone || '-'}</td>
                    <td>{contact.email || '-'}</td>
                    <td style={{ maxWidth: 150, fontSize: '0.8rem', color: '#4b5563' }}>{contact.shippingAddress ? (contact.shippingAddress.length > 30 ? contact.shippingAddress.slice(0, 30) + '...' : contact.shippingAddress) : <span style={{ color: '#d1d5db', fontStyle: 'italic' }}>Not set</span>}</td>
                    <td style={{ maxWidth: 150, fontSize: '0.8rem', color: '#4b5563' }}>{contact.billingAddress ? (contact.billingAddress.length > 30 ? contact.billingAddress.slice(0, 30) + '...' : contact.billingAddress) : <span style={{ color: '#d1d5db', fontStyle: 'italic' }}>Not set</span>}</td>
                    <td>
                      <div className="opt-in-badges">
                        {contact.optInWhatsApp && contact.allowlistWhatsApp && <span className="badge badge-active">WA</span>}
                        {contact.optInWhatsApp && !contact.allowlistWhatsApp && <span className="badge badge-pending">WA</span>}
                        {contact.optInSms && contact.allowlistSms && <span className="badge badge-active">SMS</span>}
                        {contact.optInSms && !contact.allowlistSms && <span className="badge badge-pending">SMS</span>}
                        {contact.optInEmail && contact.allowlistEmail && <span className="badge badge-active">Email</span>}
                        {contact.optInEmail && !contact.allowlistEmail && <span className="badge badge-pending">Email</span>}
                        {!contact.optInWhatsApp && !contact.optInSms && !contact.optInEmail && (
                          <span className="badge badge-gray">None</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(contact)}>Edit</Button>
                        <Button variant="ghost" size="sm" onClick={() => window.location.href = '/messaging'}>Msg</Button>
                        <Button variant="danger" size="sm" onClick={() => openDeleteModal(contact)}>Del</Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredContacts.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-table">
                      {searchQuery ? 'No contacts match your search' : 'No contacts yet. Add your first contact!'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          )}
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
                <label>Shipping Address</label>
                <input type="text" value={formShippingAddress} onChange={(e) => setFormShippingAddress(e.target.value)} placeholder="123 Park Street, Kolkata 700016" />
              </div>
              <div className="form-group">
                <label>Billing Address</label>
                <input type="text" value={formBillingAddress} onChange={(e) => setFormBillingAddress(e.target.value)} placeholder="Same as shipping or different" />
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
                <Button variant="secondary" onClick={() => setShowModal(false)}>Cancel</Button>
                <Button variant="primary" onClick={handleCreate} disabled={(!formPhone && !formEmail)} loading={saving}>
                  {saving ? 'Saving...' : 'Add Contact'}
                </Button>
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
                <label>Shipping Address</label>
                <input type="text" value={formShippingAddress} onChange={(e) => setFormShippingAddress(e.target.value)} placeholder="123 Park Street, Kolkata 700016" />
              </div>
              <div className="form-group">
                <label>Billing Address</label>
                <input type="text" value={formBillingAddress} onChange={(e) => setFormBillingAddress(e.target.value)} placeholder="Same as shipping or different" />
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
                <Button variant="secondary" onClick={() => { setShowEditModal(false); setEditingContact(null); }}>Cancel</Button>
                <Button variant="primary" onClick={handleUpdate} disabled={(!formPhone && !formEmail)} loading={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && (
          <div className="confirm-modal-overlay" onClick={() => setShowDeleteModal(null)}>
            <div className="confirm-modal" onClick={e => e.stopPropagation()}>
              <div className="confirm-modal-header">
                <h3>Delete Contact</h3>
              </div>
              <div className="confirm-modal-body">
                <p>Are you sure you want to delete "{deleteContactName}"?</p>
                <p style={{ color: '#6b7280', fontSize: '13px', marginTop: '8px' }}>
                  This action cannot be undone.
                </p>
              </div>
              <div className="confirm-modal-footer">
                <Button variant="secondary" onClick={() => setShowDeleteModal(null)}>Cancel</Button>
                <Button variant="danger" onClick={() => handleDelete(showDeleteModal)}>Delete</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Contacts;
