/**
 * Internal AI Configuration Page
 * 
 * Control settings for the Internal Bedrock Agent (FloatingAgent)
 * Used for admin tasks like sending messages, finding contacts, etc.
 * 
 * Internal Agent/KB:
 * - Agent ID: TJAZR473IJ
 * - Agent Alias: O4U1HF2MSX
 * - KB ID: 7IWHVB0ZXQ
 */

import { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

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
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="spinner" />
          <p>Loading Internal AI configuration...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user} onSignOut={signOut}>
      <div style={{ padding: '1.5rem', maxWidth: '1000px', margin: '0 auto' }}>
        {/* Header */}
        <PageHeader 
          title="Internal AI Assistant" 
          subtitle="Configure the FloatingAgent AI for admin tasks"
          icon="ai"
        />

        {/* Info Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          <div className="info-card">
            <div className="info-label">Agent ID</div>
            <div className="info-value">{config.agentId}</div>
          </div>
          <div className="info-card">
            <div className="info-label">Agent Alias</div>
            <div className="info-value">{config.agentAlias}</div>
          </div>
          <div className="info-card">
            <div className="info-label">Knowledge Base</div>
            <div className="info-value">{config.knowledgeBaseId}</div>
          </div>
          <div className="info-card">
            <div className="info-label">Model</div>
            <div className="info-value">Nova Lite</div>
          </div>
        </div>

        {/* Configuration */}
        <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Configuration</h3>
          
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                style={{ width: '1.25rem', height: '1.25rem' }}
              />
              <span style={{ fontWeight: 600 }}>Enable Internal AI Assistant</span>
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Max Tokens</label>
              <input
                type="number"
                value={config.maxTokens}
                onChange={(e) => setConfig({ ...config, maxTokens: parseInt(e.target.value) || 1024 })}
                min={256}
                max={4096}
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Temperature</label>
              <input
                type="number"
                value={config.temperature}
                onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) || 0.7 })}
                min={0}
                max={1}
                step={0.1}
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>System Prompt</label>
            <textarea
              value={config.systemPrompt}
              onChange={(e) => setConfig({ ...config, systemPrompt: e.target.value })}
              rows={6}
              style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', fontFamily: 'monospace', fontSize: '0.85rem' }}
            />
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            style={{ padding: '0.5rem 1.5rem', background: '#3b82f6', color: 'white', border: 'none', borderRadius: '0.375rem', cursor: 'pointer' }}
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

        {/* Test Section */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Test Internal AI</h3>
          <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Test how the internal AI responds to admin commands.
          </p>
          
          <div style={{ marginBottom: '1rem' }}>
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              rows={2}
              style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
              placeholder="Try: 'Show today's stats' or 'Find contact +919330994400'"
            />
          </div>

          <button
            onClick={handleTest}
            disabled={saving || !testMessage.trim()}
            style={{ padding: '0.5rem 1.5rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '0.375rem', cursor: 'pointer', marginBottom: '1rem' }}
          >
            {saving ? 'Testing...' : '🧪 Test Response'}
          </button>

          {testResult && (
            <div style={{ padding: '1rem', background: '#f0fdf4', borderRadius: '0.5rem', border: '1px solid #bbf7d0' }}>
              <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>AI Response:</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{testResult}</div>
            </div>
          )}
        </div>

        {/* Architecture Info */}
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
          <strong>Architecture Note:</strong> This is the Internal AI used by the FloatingAgent for admin tasks.
          For WhatsApp auto-reply AI (customer-facing), go to Messages → WhatsApp → AI Config.
        </div>

        {/* Toast */}
        {toast && (
          <div style={{
            position: 'fixed',
            bottom: '1rem',
            right: '1rem',
            padding: '0.75rem 1.5rem',
            background: toast.type === 'success' ? '#22c55e' : '#ef4444',
            color: 'white',
            borderRadius: '0.5rem',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            zIndex: 1000,
          }}>
            {toast.message}
          </div>
        )}
      </div>

      <style jsx>{`
        .card {
          background: white;
          border-radius: 0.5rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .info-card {
          background: white;
          padding: 1rem;
          border-radius: 0.5rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .info-label {
          font-size: 0.75rem;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .info-value {
          font-size: 0.9rem;
          font-weight: 600;
          color: #1f2937;
          font-family: monospace;
          margin-top: 0.25rem;
        }
        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid #e5e7eb;
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Layout>
  );
}
