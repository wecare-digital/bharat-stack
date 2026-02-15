/**
 * Pay Flow — Customer Management for WhatsApp Pay Flow
 * 
 * Create/edit customers here so their details auto-fill
 * when they use the WhatsApp pay flow (no re-entry needed).
 * Shows pending payment dues per customer.
 */

import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import Button from '../../../components/ui/Button';
import * as api from '../../../api/client';
import { API_BASE } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface CustomerRecord {
  id: string;
  contactId: string;
  name: string;
  phone: string;
  email: string;
  shippingAddress: string;
  billingAddress: string;
  createdAt: string;
  updatedAt: string;
}

interface PendingDue {
  ref: string;
  amount: number;
  item: string;
  timestamp: string;
}

const emptyForm = { name: '', phone: '', email: '', shippingAddress: '', billingAddress: '' };

const PayFlowPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load customers from contacts API (raw, to get shippingAddress/billingAddress)
  const loadCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/contacts`);
      if (!res.ok) throw new Error('Failed to load');
      const json = await res.json();
      const rawContacts: any[] = json.contacts || (Array.isArray(json) ? json : []);
      const mapped: CustomerRecord[] = rawContacts
        .filter((c: any) => !c.deletedAt)
        .map((c: any) => ({
          id: c.id || c.contactId || '',
          contactId: c.contactId || c.id || '',
          name: c.name || '',
          phone: c.phone || '',
          email: c.email || '',
          shippingAddress: c.shippingAddress || '',
          billingAddress: c.billingAddress || '',
          createdAt: c.createdAt ? new Date(Number(c.createdAt) * 1000).toLocaleDateString() : '',
          updatedAt: c.updatedAt ? new Date(Number(c.updatedAt) * 1000).toLocaleDateString() : '',
        }));
      setCustomers(mapped);
    } catch (err) {
      console.error('Load customers error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCustomers(); }, [loadCustomers]);

  const handleSave = async () => {
    if (!form.name || !form.phone) {
      setMsg({ type: 'error', text: 'Name and phone are required' });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const cleanPhone = form.phone.replace(/[\s\-]/g, '');
      if (editId) {
        // Update existing
        const updates: any = {
          name: form.name,
          phone: cleanPhone,
          email: form.email || undefined,
          shippingAddress: form.shippingAddress || undefined,
          billingAddress: form.billingAddress || undefined,
        };
        const result = await api.updateContact(editId, updates);
        if (result) {
          setMsg({ type: 'success', text: 'Customer updated' });
        } else {
          setMsg({ type: 'error', text: 'Update failed' });
        }
      } else {
        // Create new
        const contact = await api.createContact({
          name: form.name,
          phone: cleanPhone,
          email: form.email || undefined,
        } as any);
        if (contact) {
          // Update with shipping/billing
          const extras: any = {};
          if (form.shippingAddress) extras.shippingAddress = form.shippingAddress;
          if (form.billingAddress) extras.billingAddress = form.billingAddress;
          if (Object.keys(extras).length > 0) {
            await api.updateContact(contact.id, extras as any);
          }
          setMsg({ type: 'success', text: 'Customer created — will auto-fill in WhatsApp pay flow' });
        } else {
          setMsg({ type: 'error', text: 'Create failed' });
        }
      }
      setShowForm(false);
      setEditId(null);
      setForm(emptyForm);
      await loadCustomers();
    } catch (err: any) {
      setMsg({ type: 'error', text: err.message || 'Error saving' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (c: CustomerRecord) => {
    setEditId(c.id);
    setForm({
      name: c.name,
      phone: c.phone,
      email: c.email,
      shippingAddress: c.shippingAddress,
      billingAddress: c.billingAddress,
    });
    setShowForm(true);
    setMsg(null);
  };

  const handleNew = () => {
    setEditId(null);
    setForm(emptyForm);
    setShowForm(true);
    setMsg(null);
  };

  const filtered = search.trim()
    ? customers.filter(c =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.phone.includes(search) ||
        c.email.toLowerCase().includes(search.toLowerCase())
      )
    : customers;

  // Count customers with addresses filled
  const withAddress = customers.filter(c => c.shippingAddress).length;

  return (
    <Layout user={user} onSignOut={signOut}>
      <div className="flow-page">
        <PageHeader
          title="Pay Flow — Customers"
          subtitle="Manage customer records for WhatsApp pay flow auto-fill"
          icon="payment"
          backLink="/pay"
          backLabel="← Pay"
          actions={
            <Button variant="primary" onClick={handleNew}>+ New Customer</Button>
          }
        />

        {msg && (
          <div className={`flow-msg ${msg.type}`}>
            {msg.text}
            <button onClick={() => setMsg(null)}>×</button>
          </div>
        )}

        {/* Stats */}
        <div className="flow-stats">
          <div className="flow-stat">
            <div className="flow-stat-val">{customers.length}</div>
            <div className="flow-stat-lbl">Total Customers</div>
          </div>
          <div className="flow-stat">
            <div className="flow-stat-val">{withAddress}</div>
            <div className="flow-stat-lbl">With Address</div>
          </div>
          <div className="flow-stat">
            <div className="flow-stat-val">{customers.length - withAddress}</div>
            <div className="flow-stat-lbl">Missing Address</div>
          </div>
        </div>

        {/* How it works */}
        <div className="flow-info">
          <span className="flow-info-icon">💡</span>
          <div>
            <span className="flow-info-title">How it works:</span> When a customer starts the WhatsApp pay flow, their name, phone, email, shipping and billing address are auto-filled from this table. No need to re-enter details each time.
          </div>
        </div>

        {/* Search */}
        <div className="flow-search">
          <input
            type="text"
            placeholder="Search by name, phone, or email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && <button className="flow-search-clear" onClick={() => setSearch('')}>×</button>}
        </div>

        {/* Customer Table */}
        {loading ? (
          <div className="flow-loading">Loading customers...</div>
        ) : (
          <div className="flow-table-wrap">
            <table className="flow-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Shipping Address</th>
                  <th>Billing Address</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr key={c.id}>
                    <td className="flow-td-name">{c.name || '—'}</td>
                    <td className="flow-td-phone">{c.phone || '—'}</td>
                    <td>{c.email || '—'}</td>
                    <td className="flow-td-addr">{c.shippingAddress ? c.shippingAddress.slice(0, 40) + (c.shippingAddress.length > 40 ? '…' : '') : <span className="flow-missing">Not set</span>}</td>
                    <td className="flow-td-addr">{c.billingAddress ? c.billingAddress.slice(0, 40) + (c.billingAddress.length > 40 ? '…' : '') : <span className="flow-missing">Not set</span>}</td>
                    <td className="flow-td-date">{c.updatedAt}</td>
                    <td>
                      <button className="flow-edit-btn" onClick={() => handleEdit(c)}>Edit</button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} className="flow-empty">{search ? 'No matches' : 'No customers yet — click + New Customer'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Create/Edit Modal */}
        {showForm && (
          <div className="flow-modal-overlay" onClick={() => { setShowForm(false); setEditId(null); }}>
            <div className="flow-modal" onClick={e => e.stopPropagation()}>
              <h3>{editId ? 'Edit Customer' : 'New Customer'}</h3>
              <p className="flow-modal-sub">
                {editId ? 'Update details — changes auto-fill in WhatsApp pay flow' : 'Add a customer — their details will auto-fill in WhatsApp pay flow'}
              </p>
              {[
                { label: 'Full Name *', key: 'name', type: 'text', placeholder: 'Rahul Sharma' },
                { label: 'Phone *', key: 'phone', type: 'tel', placeholder: '+919876543210' },
                { label: 'Email', key: 'email', type: 'email', placeholder: 'rahul@example.com' },
                { label: 'Shipping Address', key: 'shippingAddress', type: 'text', placeholder: '123 Park Street, Kolkata 700016' },
                { label: 'Billing Address', key: 'billingAddress', type: 'text', placeholder: 'Same as shipping or different' },
              ].map(f => (
                <div key={f.key} className="flow-field">
                  <label>{f.label}</label>
                  <input
                    type={f.type}
                    value={(form as any)[f.key] || ''}
                    placeholder={f.placeholder}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  />
                </div>
              ))}
              <div className="flow-modal-actions">
                <Button variant="secondary" onClick={() => { setShowForm(false); setEditId(null); }}>Cancel</Button>
                <Button variant="primary" onClick={handleSave} loading={saving}>{saving ? 'Saving...' : editId ? 'Update' : 'Create'}</Button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .flow-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .flow-msg { padding: 10px 14px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
        .flow-msg.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
        .flow-msg.error { background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; }
        .flow-msg button { background: none; border: none; font-size: 16px; cursor: pointer; color: inherit; }
        .flow-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
        .flow-stat { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; text-align: center; }
        .flow-stat-val { font-size: 1.5rem; font-weight: 700; color: #111827; }
        .flow-stat-lbl { font-size: 0.75rem; color: #6b7280; margin-top: 2px; }
        .flow-info { display: flex; gap: 10px; align-items: flex-start; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-size: 0.85rem; color: #166534; }
        .flow-info-icon { font-size: 1.2rem; }
        .flow-info-title { font-weight: 600; }
        .flow-search { position: relative; margin-bottom: 16px; }
        .flow-search input { width: 100%; padding: 10px 14px; border: 1.5px solid #10B981; border-radius: 10px; font-size: 14px; box-sizing: border-box; }
        .flow-search input:focus { outline: none; box-shadow: 0 0 0 3px rgba(16,185,129,0.2); }
        .flow-search-clear { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 18px; cursor: pointer; color: #6b7280; }
        .flow-loading { text-align: center; padding: 3rem; color: #6b7280; }
        .flow-table-wrap { overflow-x: auto; }
        .flow-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        .flow-table th { text-align: left; padding: 10px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; font-weight: 600; color: #374151; white-space: nowrap; }
        .flow-table td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; }
        .flow-table tr:hover { background: #f0fdf4; }
        .flow-td-name { font-weight: 600; color: #111827; }
        .flow-td-phone { font-family: monospace; font-size: 0.8rem; }
        .flow-td-addr { max-width: 200px; font-size: 0.8rem; color: #4b5563; }
        .flow-td-date { font-size: 0.75rem; color: #9ca3af; white-space: nowrap; }
        .flow-missing { color: #d1d5db; font-style: italic; font-size: 0.8rem; }
        .flow-edit-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid #6366f1; background: #eef2ff; color: #4f46e5; cursor: pointer; font-size: 0.75rem; }
        .flow-edit-btn:hover { background: #e0e7ff; }
        .flow-empty { text-align: center; padding: 2rem; color: #9ca3af; }
        .flow-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .flow-modal { background: #fff; border-radius: 12px; padding: 24px; width: 440px; max-height: 85vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
        .flow-modal h3 { margin: 0 0 4px; font-size: 1.1rem; }
        .flow-modal-sub { margin: 0 0 16px; font-size: 0.8rem; color: #6b7280; }
        .flow-field { margin-bottom: 12px; }
        .flow-field label { display: block; font-size: 0.75rem; color: #6b7280; margin-bottom: 3px; }
        .flow-field input { width: 100%; padding: 8px 12px; border: 1.5px solid #d1d5db; border-radius: 8px; font-size: 0.9rem; box-sizing: border-box; }
        .flow-field input:focus { outline: none; border-color: #10B981; box-shadow: 0 0 0 3px rgba(16,185,129,0.15); }
        .flow-modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
        @media (max-width: 768px) {
          .flow-stats { grid-template-columns: 1fr; }
          .flow-modal { width: 95%; margin: 0 10px; }
        }
      `}</style>
    </Layout>
  );
};

export default PayFlowPage;
