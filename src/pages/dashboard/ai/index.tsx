/**
 * Internal AI Configuration Page
 * Enhanced responsive design
 */

import { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import SEO from '../../../components/SEO';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

interface InternalAIConfig {
  enabled: boolean;
  agentId: string;
  agentAlias: string;
  knowledgeBaseId: string;
  modelId: string;
  maxTokens: number;
  temperature: number;
  systemPrompt: string;
}

const DEFAULT_CONFIG: InternalAIConfig = {
  enabled: true,
  agentId: 'TJAZR473IJ',
  agentAlias: 'O4U1HF2MSX',
  knowledgeBaseId: '7IWHVB0ZXQ',
  modelId: 'amazon.nova-lite-v1:0',
  maxTokens: 1024,
  temperature: 0.7,
  systemPrompt: `You are WECARE.DIGITAL's internal admin assistant.
Help operators with:
- Sending WhatsApp messages
- Finding and managing contacts
- Checking message statistics
- Answering questions about the platform`,
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';

export default function InternalAIConfigPage({ signOut, user }: PageProps) {
  const [config, setConfig] = useState<InternalAIConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testMessage, setTestMessage] = useState('');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai/internal/config`);
      if (res.ok) {
        const data = await res.json();
        if (data.config) {
          setConfig({ ...DEFAULT_CONFIG, ...data.config });
        }
      }
    } catch (error) {
      console.log('Using default internal AI config');
    }
    setLoading(false);
  };

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/ai/internal/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        showToast('Configuration saved', 'success');
      } else {
        showToast('Failed to save configuration', 'error');
      }
    } catch (error) {
      showToast('Failed to save configuration', 'error');
    }
    setSaving(false);
  };

  const handleTest = async () => {
    if (!testMessage.trim()) return;
    setSaving(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/ai/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messageContent: testMessage,
          context: 'internal-admin',
        }),
      });
      const data = await res.json();
      const body = typeof data.body === 'string' ? JSON.parse(data.body) : data;
      setTestResult(body.suggestedResponse || body.suggestion || 'No response');
    } catch (error) {
      setTestResult('Error: Failed to get AI response');
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <Layout user={user} onSignOut={signOut}>
        <div className="page-content" style={{ textAlign: 'center', paddingTop: '100px' }}>
          <div className="loading">Loading AI configuration...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO 
        title="AI Assistant | WECARE.DIGITAL"
        description="Configure the internal AI assistant"
      />
      <div className="page-content">
        <PageHeader 
          title="AI Assistant" 
          subtitle="Configure the FloatingAgent AI for admin tasks"
          icon="ai"
        />

        {/* Info Cards */}
        <div className="stats-grid" style={{ marginBottom: '24px' }}>
          <div className="stat-card">
            <div className="stat-label">Agent ID</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', marginTop: '4px' }}>{config.agentId}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Agent Alias</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', marginTop: '4px' }}>{config.agentAlias}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Knowledge Base</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', marginTop: '4px' }}>{config.knowledgeBaseId}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Model</div>
            <div style={{ fontFamily: 'monospace', fontSize: '13px', marginTop: '4px' }}>Nova Lite</div>
          </div>
        </div>

        {/* Configuration */}
        <div className="section">
          <h3 className="section-title">Configuration</h3>
          
          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                style={{ width: '20px', height: '20px', accentColor: '#10b981' }}
              />
              <span style={{ fontWeight: 600 }}>Enable Internal AI Assistant</span>
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div className="form-group">
              <label>Max Tokens</label>
              <input
                type="number"
                value={config.maxTokens}
                onChange={(e) => setConfig({ ...config, maxTokens: parseInt(e.target.value) || 1024 })}
                min={256}
                max={4096}
              />
            </div>
            <div className="form-group">
              <label>Temperature</label>
              <input
                type="number"
                value={config.temperature}
                onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) || 0.7 })}
                min={0}
                max={1}
                step={0.1}
              />
            </div>
          </div>

          <div className="form-group">
            <label>System Prompt</label>
            <textarea
              value={config.systemPrompt}
              onChange={(e) => setConfig({ ...config, systemPrompt: e.target.value })}
              rows={6}
              style={{ fontFamily: 'monospace', fontSize: '13px' }}
            />
          </div>

          <div className="form-actions">
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </div>

        {/* Test Section */}
        <div className="section">
          <h3 className="section-title">Test AI</h3>
          <p className="section-description">
            Test how the internal AI responds to admin commands.
          </p>
          
          <div className="form-group">
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              rows={2}
              placeholder="Try: 'Show today's stats' or 'Find contact +919330994400'"
            />
          </div>

          <button
            className="btn-secondary"
            onClick={handleTest}
            disabled={saving || !testMessage.trim()}
          >
            {saving ? 'Testing...' : 'Test Response'}
          </button>

          {testResult && (
            <div style={{ 
              marginTop: '16px',
              padding: '16px', 
              background: '#ecfdf5', 
              borderRadius: '13px', 
              border: '1px solid #bbf7d0' 
            }}>
              <div style={{ fontWeight: 600, marginBottom: '8px', fontSize: '13px', color: '#059669' }}>AI Response:</div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '14px' }}>{testResult}</div>
            </div>
          )}
        </div>

        {/* Architecture Info */}
        <div style={{ 
          marginTop: '24px', 
          padding: '16px', 
          background: 'var(--color-bg-secondary)', 
          borderRadius: '12px', 
          fontSize: '13px', 
          color: 'var(--color-secondary)' 
        }}>
          <strong>Note:</strong> This is the Internal AI used by the FloatingAgent for admin tasks.
          For WhatsApp auto-reply AI (customer-facing), go to Messages → WhatsApp → AI Config.
        </div>

        {/* Toast */}
        {toast && (
          <div style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            padding: '12px 24px',
            background: toast.type === 'success' ? '#10b981' : '#ef4444',
            color: 'white',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 1000,
            fontWeight: 500,
          }}>
            {toast.message}
          </div>
        )}
      </div>
    </Layout>
  );
}
