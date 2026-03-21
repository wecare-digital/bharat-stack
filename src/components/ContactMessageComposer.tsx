/**
 * Contact Message Composer
 * Send WhatsApp contact card messages (vCard format).
 * Per WhatsApp Cloud API: POST /messages with type=contacts
 */
import React, { useState } from 'react';
import * as api from '../api/client';

interface ContactMessageComposerProps {
  contactId: string;
  phoneNumberId: string;
  recipientBsuid?: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

interface ContactCard {
  name: { formatted_name: string; first_name: string; last_name: string };
  phones: { phone: string; type: string }[];
  emails: { email: string; type: string }[];
  org?: { company: string; title: string };
}

const ContactMessageComposer: React.FC<ContactMessageComposerProps> = ({
  contactId, phoneNumberId, recipientBsuid, onClose, onSent, onError,
}) => {
  const [sending, setSending] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [phoneType, setPhoneType] = useState('CELL');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');

  const handleSend = async () => {
    if (!firstName.trim()) { onError('First name is required'); return; }
    if (!phone.trim()) { onError('Phone number is required'); return; }
    setSending(true);
    try {
      const contact: ContactCard = {
        name: {
          formatted_name: `${firstName} ${lastName}`.trim(),
          first_name: firstName.trim(),
          last_name: lastName.trim(),
        },
        phones: [{ phone: phone.trim(), type: phoneType }],
        emails: email ? [{ email: email.trim(), type: 'WORK' }] : [],
      };
      if (company) contact.org = { company, title };
      const content = JSON.stringify({ _type: 'contacts', contacts: [contact] });
      await api.sendWhatsAppMessage({
        contactId, phoneNumberId, content,
        recipientBsuid: recipientBsuid || undefined,
      });
      onSent();
    } catch (e: any) {
      onError(e?.message || 'Failed to send contact');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-sm">Send Contact Card</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input placeholder="First name *" value={firstName} onChange={e => setFirstName(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" />
        <input placeholder="Last name" value={lastName} onChange={e => setLastName(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" />
      </div>
      <div className="flex gap-2">
        <input placeholder="Phone number *" value={phone} onChange={e => setPhone(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm flex-1" />
        <select value={phoneType} onChange={e => setPhoneType(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" aria-label="Phone type">
          <option value="CELL">Cell</option>
          <option value="WORK">Work</option>
          <option value="HOME">Home</option>
        </select>
      </div>
      <input placeholder="Email (optional)" value={email} onChange={e => setEmail(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full" />
      <div className="grid grid-cols-2 gap-2">
        <input placeholder="Company" value={company} onChange={e => setCompany(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" />
        <input placeholder="Job title" value={title} onChange={e => setTitle(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" />
      </div>
      <button onClick={handleSend} disabled={sending}
        className="w-full bg-green-600 text-white rounded py-2 text-sm hover:bg-green-700 disabled:opacity-50">
        {sending ? 'Sending...' : 'Send Contact'}
      </button>
    </div>
  );
};

export default ContactMessageComposer;
