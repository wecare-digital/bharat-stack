/**
 * Location Send Composer
 * Send WhatsApp location messages with lat/lng, name, and address.
 * Per WhatsApp Cloud API: POST /messages with type=location
 */
import React, { useState } from 'react';
import * as api from '../api/client';

interface LocationSendComposerProps {
  contactId: string;
  phoneNumberId: string;
  recipientBsuid?: string;
  onClose: () => void;
  onSent: () => void;
  onError: (msg: string) => void;
}

const LocationSendComposer: React.FC<LocationSendComposerProps> = ({
  contactId, phoneNumberId, recipientBsuid, onClose, onSent, onError,
}) => {
  const [sending, setSending] = useState(false);
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');

  const handleSend = async () => {
    const lat = parseFloat(latitude);
    const lng = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lng)) { onError('Valid latitude and longitude are required'); return; }
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) { onError('Coordinates out of range'); return; }
    setSending(true);
    try {
      const content = JSON.stringify({ _type: 'location', latitude: lat, longitude: lng, name, address });
      await api.sendWhatsAppMessage({
        contactId, phoneNumberId, content,
        recipientBsuid: recipientBsuid || undefined,
      });
      onSent();
    } catch (e: any) {
      onError(e?.message || 'Failed to send location');
    } finally {
      setSending(false);
    }
  };

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) { onError('Geolocation not supported'); return; }
    navigator.geolocation.getCurrentPosition(
      pos => { setLatitude(String(pos.coords.latitude)); setLongitude(String(pos.coords.longitude)); },
      () => onError('Could not get your location'),
    );
  };

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-sm">Send Location</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input placeholder="Latitude *" value={latitude} onChange={e => setLatitude(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" type="number" step="any" />
        <input placeholder="Longitude *" value={longitude} onChange={e => setLongitude(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm" type="number" step="any" />
      </div>
      <button onClick={handleUseMyLocation} type="button"
        className="text-xs text-blue-600 hover:underline">📍 Use my location</button>
      <input placeholder="Location name (optional)" value={name} onChange={e => setName(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full" />
      <input placeholder="Address (optional)" value={address} onChange={e => setAddress(e.target.value)}
        className="border rounded px-2 py-1.5 text-sm w-full" />
      <button onClick={handleSend} disabled={sending}
        className="w-full bg-green-600 text-white rounded py-2 text-sm hover:bg-green-700 disabled:opacity-50">
        {sending ? 'Sending...' : 'Send Location'}
      </button>
    </div>
  );
};

export default LocationSendComposer;
