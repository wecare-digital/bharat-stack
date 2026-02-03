/**
 * WhatsApp Welcome Message Configuration
 */

import React, { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import Button from '../../../components/ui/Button';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import { WHATSAPP_PHONES } from '../../../config/constants';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

interface WelcomeConfig {
  enabled: boolean;
  textMessage: string;
  delaySeconds: number;
  phoneNumberId: string;
}

const defaultConfig: WelcomeConfig = {
  enabled: false,
  textMessage: 'Hello! Welcome to WECARE.DIGITAL. How can we help you today?',
  delaySeconds: 2,
  phoneNumberId: WHATSAPP_PHONES.primary.id,
};

const WelcomeConfigPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [config, setConfig] = useState<WelcomeConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const toast = useToastContext();

  useEffect(() => { loadConfig(); }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const data = await api.getSystemConfig('welcome_message');
      if (data) setConfig({ ...defaultConfig, ...data });
    } catch (err) {
      console.error('Failed to load welcome config:', err);
      toast.error('Failed to load welcome config');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.updateSystemConfig('welcome_message', config);
      toast.success('Configuration saved!');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    const loadingContent = <div style={{ padding: 20, textAlign: 'center' }}>Loading...</div>;
    if (embedded) return loadingContent;
    return (
      <Layout user={user} onSignOut={signOut}>
        {loadingContent}
      </Layout>
    );
  }

  const content = (
    <div style={{ padding: embedded ? 0 : 20, maxWidth: 800, margin: '0 auto' }}>
      {!embedded && (
        <>
          <h1 style={{ fontSize: 22, marginBottom: 4 }}>Welcome Message</h1>
          <p style={{ color: '#666', marginBottom: 24 }}>Configure automated welcome messages</p>
        </>
      )}

      <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: embedded ? 'none' : '0 1px 3px rgba(0,0,0,0.08)' }}>
        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
              style={{ width: 18, height: 18 }}
            />
            <span>Enable Welcome Message</span>
          </label>
        </div>

        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Phone Number</h3>
          <select
            value={config.phoneNumberId}
            onChange={(e) => setConfig({ ...config, phoneNumberId: e.target.value })}
            style={{ width: '100%', padding: 10, border: '1px solid #000', borderRadius: 13 }}
          >
            <option value={WHATSAPP_PHONES.primary.id}>
              {WHATSAPP_PHONES.primary.display} ({WHATSAPP_PHONES.primary.name})
            </option>
            <option value={WHATSAPP_PHONES.secondary.id}>
              {WHATSAPP_PHONES.secondary.display} ({WHATSAPP_PHONES.secondary.name})
            </option>
          </select>
        </div>

        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Welcome Text</h3>
          <textarea
            value={config.textMessage}
            onChange={(e) => setConfig({ ...config, textMessage: e.target.value })}
            placeholder="Enter your welcome message..."
            rows={4}
            style={{ width: '100%', padding: 10, border: '1px solid #000', borderRadius: 13, resize: 'vertical', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Delay</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="number"
              value={config.delaySeconds}
              onChange={(e) => setConfig({ ...config, delaySeconds: parseInt(e.target.value) || 0 })}
              min={0}
              max={30}
              style={{ width: 80, padding: 10, border: '1px solid #000', borderRadius: 13 }}
            />
            <span style={{ color: '#666' }}>seconds before sending</span>
          </div>
        </div>

        <Button variant="primary" onClick={saveConfig} disabled={saving} loading={saving} className="welcome-save-btn">
          {saving ? 'Saving...' : 'Save Configuration'}
        </Button>
      </div>
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
};

export default WelcomeConfigPage;
