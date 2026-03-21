/**
 * Address Message Composer
 * Request delivery address via WhatsApp interactive address_message.
 * Per WhatsApp Cloud API: POST /messages with type=interactive, interactive.type=address_message
 */
import React, { useState } from 'react';
import * as api from '../api/client';

interface AddressMessageComposerProps {
  contactId: string;
  phoneNumberId: string;
  recipientBsuid?: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

const AddressMessageComposer: React.FC<AddressMessageComposerProps> = ({
  contactId, phoneNumberId, recipientBsuid, onClose, onSent, onError,
}) => {
  const [sending, setSending] = useState(false);
  const [bodyText, setBodyText] = useState('Please provide your delivery address.');
  const [country, setCountry] = useState('IN');

  const handleSend = async () => {
    if (!bodyText.trim()) { onError('Body text is required'); return; }
    setSending(true);
    try {
      const content = JSON.stringify({
        _type: 'address_message',
        body: bodyText.trim(),
        parameters: { country: country || 'IN' },
      });
      await api.sendWhatsAppMessage({
        contactId, phoneNumberId, content,
        recipientBsuid: recipientBsuid || undefined,
      });
      onSent();
    } catch (e: any) {
      onError(e?.message || 'Failed to send address request');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-sm">Request Delivery Address</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
      </div>
      <textarea placeholder="Message body *" value={bodyText} onChange={e => setBodyText(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full" rows={2} />
      <div>
        <label className="text-xs text-gray-500 block mb-1" htmlFor="country-select">Country</label>
        <select id="country-select" value={country} onChange={e => setCountry(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm">
          <option value="IN">India</option>
          <option value="US">United States</option>
          <option value="AE">UAE</option>
          <option value="GB">United Kingdom</option>
          <option value="SG">Singapore</option>
        </select>
      </div>
      <button onClick={handleSend} disabled={sending}
        className="w-full bg-green-600 text-white rounded py-2 text-sm hover:bg-green-700 disabled:opacity-50">
        {sending ? 'Sending...' : 'Request Address'}
      </button>
    </div>
  );
};

export default AddressMessageComposer;
