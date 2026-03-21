/**
 * Location Request Composer
 * Request user's location via WhatsApp interactive location_request_message.
 * Per WhatsApp Cloud API: POST /messages with type=interactive, interactive.type=location_request_message
 */
import React, { useState } from 'react';
import * as api from '../api/client';

interface LocationRequestComposerProps {
  contactId: string;
  phoneNumberId: string;
  recipientBsuid?: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

const LocationRequestComposer: React.FC<LocationRequestComposerProps> = ({
  contactId, phoneNumberId, recipientBsuid, onClose, onSent, onError,
}) => {
  const [sending, setSending] = useState(false);
  const [bodyText, setBodyText] = useState('Please share your current location so we can assist you.');

  const handleSend = async () => {
    if (!bodyText.trim()) { onError('Body text is required'); return; }
    setSending(true);
    try {
      const content = JSON.stringify({ _type: 'location_request', body: bodyText.trim() });
      await api.sendWhatsAppMessage({
        contactId, phoneNumberId, content,
        recipientBsuid: recipientBsuid || undefined,
      });
      onSent();
    } catch (e: any) {
      onError(e?.message || 'Failed to send location request');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-sm">Request Location</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
      </div>
      <textarea placeholder="Message body *" value={bodyText} onChange={e => setBodyText(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full" rows={3} />
      <p className="text-xs text-gray-500">The recipient will see a &quot;Send Location&quot; button.</p>
      <button onClick={handleSend} disabled={sending}
        className="w-full bg-green-600 text-white rounded py-2 text-sm hover:bg-green-700 disabled:opacity-50">
        {sending ? 'Sending...' : 'Request Location'}
      </button>
    </div>
  );
};

export default LocationRequestComposer;
