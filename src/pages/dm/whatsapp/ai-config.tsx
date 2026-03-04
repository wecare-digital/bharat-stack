/**
 * External AI Configuration Page (WhatsApp Auto-Reply)
 * 
 * Control AI auto-reply settings for WhatsApp messages (customer-facing):
 * - Enable/disable AI responses
 * - Configure which message types trigger AI
 * - Set language-specific prompts and fallbacks
 * - View AI interaction logs and statistics
 * 
 * External Agent: Z4YAK0ZLBO / Alias: WANPKHQGIB
 * KB: Static FAQ (Free, no OpenSearch)
 * 
 * Note: For Internal AI (FloatingAgent admin tasks), go to Dashboard → AI
 */

import { useState, useEffect } from 'react';
import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';
import Button from '../../../components/ui/Button';
import Tabs, { TabItem } from '../../../components/ui/Tabs';
import {
  getBedrockAIConfig,
  updateBedrockAIConfig,
  getAIPrompts,
  updateAIPrompt,
  getAIFallbacks,
  updateAIFallback,
  getAIInteractions,
  getAIStats,
  getSupportedLanguages,
  testBedrockAIResponse,
  BedrockAIConfig,
  AIInteraction,
  AIStats,
  SupportedLanguages,
} from '../../../api/client';
import { searchFAQs, formatSearchResponse, getAllFAQs, getCategoryName, type FAQSearchResult } from '../../../utils/faqSearch';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

export default function AIConfigPage({ signOut, user, embedded = false }: PageProps) {
  const [config, setConfig] = useState<BedrockAIConfig | null>(null);
  const [prompts, setPrompts] = useState<Record<string, string>>({});
  const [fallbacks, setFallbacks] = useState<Record<string, string>>({});
  const [interactions, setInteractions] = useState<AIInteraction[]>([]);
  const [stats, setStats] = useState<AIStats | null>(null);
  const [languages, setLanguages] = useState<SupportedLanguages>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'config' | 'prompts' | 'fallbacks' | 'logs' | 'test' | 'faqs'>('config');
  const [selectedLang, setSelectedLang] = useState('en');
  const [testMessage, setTestMessage] = useState('');
  const [testResult, setTestResult] = useState<{ response: string; language: string } | null>(null);
  const [faqResults, setFaqResults] = useState<FAQSearchResult[]>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [configData, promptsData, fallbacksData, interactionsData, statsData, langsData] = await Promise.all([
        getBedrockAIConfig(),
        getAIPrompts() as Promise<Record<string, string>>,
        getAIFallbacks() as Promise<Record<string, string>>,
        getAIInteractions(50),
        getAIStats(),
        getSupportedLanguages(),
      ]);
      setConfig(configData);
      setPrompts(promptsData);
      setFallbacks(fallbacksData);
      setInteractions(interactionsData);
      setStats(statsData);
      setLanguages(langsData);
    } catch (error) {
      console.error('Failed to load AI config:', error);
      setLoadError('Failed to load AI configuration. Check API connection.');
      showToast('Failed to load configuration', 'error');
    }
    setLoading(false);
  };

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleConfigUpdate = async (updates: Partial<BedrockAIConfig>) => {
    setSaving(true);
    const result = await updateBedrockAIConfig(updates);
    if (result) {
      setConfig(result);
      showToast('Configuration updated', 'success');
    } else {
      showToast('Failed to update configuration', 'error');
    }
    setSaving(false);
  };

  const handlePromptUpdate = async () => {
    setSaving(true);
    const success = await updateAIPrompt(selectedLang, prompts[selectedLang] || '');
    showToast(success ? 'Prompt updated' : 'Failed to update prompt', success ? 'success' : 'error');
    setSaving(false);
  };

  const handleFallbackUpdate = async () => {
    setSaving(true);
    const success = await updateAIFallback(selectedLang, fallbacks[selectedLang] || '');
    showToast(success ? 'Fallback updated' : 'Failed to update fallback', success ? 'success' : 'error');
    setSaving(false);
  };

  const handleTestAI = async () => {
    if (!testMessage.trim()) return;
    setSaving(true);
    // Run FAQ search locally (instant)
    const localResults = searchFAQs(testMessage, { maxResults: 3 });
    setFaqResults(localResults);
    // Run Bedrock test (API call)
    const result = await testBedrockAIResponse(testMessage);
    setTestResult({ response: result.response, language: result.detectedLanguage });
    setSaving(false);
  };

  if (loading) {
    const loadingContent = (
      <div style={{ padding: '2rem', textAlign: 'center', background: '#fff' }}>
        <div className="spinner" />
        <p>Loading AI configuration...</p>
      </div>
    );

    if (embedded) return loadingContent;

    return (
      <Layout user={user} onSignOut={signOut}>
        {loadingContent}
      </Layout>
    );
  }

  if (loadError && !config) {
    const errorContent = (
      <div style={{ textAlign: 'center', padding: 48, background: '#fff' }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
        <p style={{ fontSize: 16, fontWeight: 600, color: '#374151' }}>AI Config Unavailable</p>
        <p style={{ fontSize: 13, color: '#6b7280', marginTop: 8 }}>{loadError}</p>
        <button onClick={loadData} style={{ marginTop: 16, padding: '8px 20px', background: '#059669', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>Retry</button>
      </div>
    );

    if (embedded) return errorContent;

    return (
      <Layout user={user} onSignOut={signOut}>
        {errorContent}
      </Layout>
    );
  }

  const content = (
    <>
      <div style={{ padding: '1rem 1.5rem', maxWidth: '1200px', margin: '0 auto', background: '#fff' }}>
        {/* Header */}
        <PageHeader 
          title="WhatsApp AI Auto-Reply" 
          subtitle="Control AI auto-reply settings for WhatsApp messages (customer-facing)"
          icon="ai"
        />
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <span style={{ padding: '0.25rem 0.5rem', background: '#f5f5f5', color: '#1a1a1a', borderRadius: '0.25rem', fontSize: '0.75rem', fontWeight: 600, border: '1px solid #000' }}>
              EXTERNAL
            </span>
            <span style={{ padding: '0.25rem 0.5rem', background: '#f5f5f5', color: '#4a4a4a', borderRadius: '0.25rem', fontSize: '0.75rem' }}>
              Customer-Facing
            </span>
          </div>
          <p style={{ color: '#6b6b6b', fontSize: '0.8rem', marginTop: '0.25rem' }}>
            Agent: Z4YAK0ZLBO | KB: Static FAQ (Free) | For internal admin AI, go to Dashboard → AI
          </p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="stat-card">
              <div className="stat-value">{stats.totalInteractions}</div>
              <div className="stat-label">Total Interactions</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.approvedResponses}</div>
              <div className="stat-label">Approved Responses</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.approvalRate}%</div>
              <div className="stat-label">Approval Rate</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: config?.enabled ? '#059669' : '#6b7280' }}>
                {config?.enabled ? 'ON' : 'OFF'}
              </div>
              <div className="stat-label">AI Status</div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <Tabs
          items={[
            { id: 'config', label: 'Settings' },
            { id: 'prompts', label: 'Prompts' },
            { id: 'fallbacks', label: 'Fallbacks' },
            { id: 'logs', label: 'Logs' },
            { id: 'test', label: 'Test' },
            { id: 'faqs', label: 'FAQs' },
          ]}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as typeof activeTab)}
        />

        {/* Config Tab */}
        {activeTab === 'config' && config && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>AI Settings</h3>
            
            {/* Master Toggle */}
            <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(e) => handleConfigUpdate({ enabled: e.target.checked })}
                  style={{ width: '1.25rem', height: '1.25rem' }}
                />
                <span style={{ fontWeight: 600 }}>Enable AI System</span>
              </label>
              <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem', marginLeft: '2rem' }}>
                Master switch for all AI features
              </p>
            </div>

            <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#f8fafc', borderRadius: '0.5rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={config.autoReplyEnabled}
                  onChange={(e) => handleConfigUpdate({ autoReplyEnabled: e.target.checked })}
                  disabled={!config.enabled}
                  style={{ width: '1.25rem', height: '1.25rem' }}
                />
                <span style={{ fontWeight: 600 }}>Auto-Reply to Messages</span>
              </label>
              <p style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.5rem', marginLeft: '2rem' }}>
                Automatically send AI-generated responses to incoming messages
              </p>
            </div>

            {/* Message Type Toggles */}
            <h4 style={{ marginBottom: '0.75rem', marginTop: '1.5rem' }}>Respond to Message Types</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem' }}>
              {[
                { key: 'respondToText', label: 'Text Messages', desc: 'Regular text messages' },
                { key: 'respondToInteractive', label: 'Interactive Replies', desc: 'Button and list replies' },
                { key: 'respondToLocation', label: 'Location Messages', desc: 'Shared locations' },
                { key: 'respondToMedia', label: 'Media Messages', desc: 'Images, videos, documents' },
              ].map(item => (
                <label key={item.key} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.75rem', background: '#f8fafc', borderRadius: '0.375rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={(config as any)[item.key]}
                    onChange={(e) => handleConfigUpdate({ [item.key]: e.target.checked })}
                    disabled={!config.enabled}
                    style={{ marginTop: '0.25rem' }}
                  />
                  <div>
                    <div style={{ fontWeight: 500 }}>{item.label}</div>
                    <div style={{ fontSize: '0.8rem', color: '#666' }}>{item.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            {/* Response Settings */}
            <h4 style={{ marginBottom: '0.75rem', marginTop: '1.5rem' }}>Response Settings</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Max Response Length</label>
                <input
                  type="number"
                  value={config.maxResponseLength}
                  onChange={(e) => handleConfigUpdate({ maxResponseLength: parseInt(e.target.value) || 500 })}
                  min={100}
                  max={2000}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Response Delay (seconds)</label>
                <input
                  type="number"
                  value={config.responseDelay}
                  onChange={(e) => handleConfigUpdate({ responseDelay: parseInt(e.target.value) || 0 })}
                  min={0}
                  max={10}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                />
              </div>
            </div>

            {/* Bedrock Settings */}
            <h4 style={{ marginBottom: '0.75rem', marginTop: '1.5rem' }}>Bedrock Configuration</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Agent ID</label>
                <input type="text" value={config.agentId} readOnly style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', background: '#f3f4f6' }} />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Agent Alias</label>
                <input type="text" value={config.agentAlias} readOnly style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', background: '#f3f4f6' }} />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Knowledge Base ID</label>
                <input type="text" value={config.knowledgeBaseId} readOnly style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', background: '#f3f4f6' }} />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Model ID</label>
                <input type="text" value={config.modelId} readOnly style={{ width: '100%', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', background: '#f3f4f6' }} />
              </div>
            </div>
          </div>
        )}

        {/* Prompts Tab */}
        {activeTab === 'prompts' && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Language-Specific Prompts</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Customize the AI system prompt for each language. The AI will respond in the detected language.
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Select Language</label>
              <select
                value={selectedLang}
                onChange={(e) => setSelectedLang(e.target.value)}
                style={{ width: '100%', maxWidth: '300px', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
              >
                {Object.entries(languages).map(([code, name]) => (
                  <option key={code} value={code}>{name} ({code})</option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
                Prompt for {languages[selectedLang] || selectedLang}
              </label>
              <textarea
                value={prompts[selectedLang] || ''}
                onChange={(e) => setPrompts({ ...prompts, [selectedLang]: e.target.value })}
                rows={12}
                style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem', fontFamily: 'monospace', fontSize: '0.85rem' }}
                placeholder="Enter the system prompt for this language..."
              />
            </div>

            <Button
              variant="primary"
              onClick={handlePromptUpdate}
              disabled={saving}
              loading={saving}
            >
              Save Prompt
            </Button>
          </div>
        )}

        {/* Fallbacks Tab */}
        {activeTab === 'fallbacks' && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Fallback Messages</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Set fallback messages for when AI cannot generate a response. These are sent in the user's detected language.
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Select Language</label>
              <select
                value={selectedLang}
                onChange={(e) => setSelectedLang(e.target.value)}
                style={{ width: '100%', maxWidth: '300px', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
              >
                {Object.entries(languages).map(([code, name]) => (
                  <option key={code} value={code}>{name} ({code})</option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>
                Fallback for {languages[selectedLang] || selectedLang}
              </label>
              <textarea
                value={fallbacks[selectedLang] || ''}
                onChange={(e) => setFallbacks({ ...fallbacks, [selectedLang]: e.target.value })}
                rows={4}
                style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                placeholder="Enter the fallback message for this language..."
              />
            </div>

            <Button
              variant="primary"
              onClick={handleFallbackUpdate}
              disabled={saving}
              loading={saving}
            >
              Save Fallback
            </Button>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>AI Interaction Logs</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Recent AI interactions showing queries and generated responses.
            </p>
            
            {interactions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                No AI interactions recorded yet
              </div>
            ) : (
              <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc' }}>
                      <th style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Time</th>
                      <th style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Query</th>
                      <th style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Response</th>
                      <th style={{ padding: '0.75rem', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Lang</th>
                    </tr>
                  </thead>
                  <tbody>
                    {interactions.map((item, idx) => (
                      <tr key={item.interactionId || idx} style={{ borderBottom: '1px solid #e5e7eb' }}>
                        <td style={{ padding: '0.75rem', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                          {new Date(item.timestamp * 1000).toLocaleString()}
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.85rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {item.query}
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.85rem', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {item.response}
                        </td>
                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                          <span style={{ padding: '0.25rem 0.5rem', background: '#f5f5f5', borderRadius: '0.25rem', fontSize: '0.75rem' }}>
                            {item.detectedLanguage || 'en'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Test Tab */}
        {activeTab === 'test' && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Test AI Response</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Test how the AI responds. Shows both local FAQ matches (instant, free) and Bedrock AI response.
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 500 }}>Test Message</label>
              <textarea
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                rows={3}
                style={{ width: '100%', padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: '0.375rem' }}
                placeholder="Type a message to test AI response..."
              />
            </div>

            <Button
              variant="primary"
              onClick={handleTestAI}
              disabled={saving || !testMessage.trim()}
              loading={saving}
              style={{ marginBottom: '1rem' }}
            >
              Test Response
            </Button>

            {/* FAQ Results (instant, local) */}
            {faqResults.length > 0 && (
              <div style={{ marginTop: '1rem', padding: '1rem', background: '#ecfdf5', borderRadius: '13px', border: '1px solid #a7f3d0' }}>
                <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#065f46', fontSize: '0.9rem' }}>
                  Static FAQ Matches (Free, Instant)
                </div>
                {faqResults.map((r) => (
                  <div key={r.id} style={{ padding: '0.5rem 0', borderBottom: '1px solid #d1fae5' }}>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{r.question}</div>
                    <div style={{ fontSize: '0.85rem', color: '#444', marginTop: '0.25rem', whiteSpace: 'pre-line' }}>{r.answer}</div>
                    <div style={{ fontSize: '0.75rem', color: '#888', marginTop: '0.25rem' }}>
                      Score: {r.score} | Keywords: {r.matchedKeywords.join(', ')}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {faqResults.length === 0 && testMessage.trim() && !saving && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#ecfdf5', borderRadius: '8px', border: '1px solid #a7f3d0', fontSize: '0.85rem', color: '#065f46' }}>
                No FAQ matches found for this query. The AI will generate a response using Bedrock.
              </div>
            )}

            {/* Bedrock AI Result */}
            {testResult && (
              <div style={{ marginTop: '1rem', padding: '1rem', background: '#f5f5f5', borderRadius: '13px', border: '1px solid #e5e5e5' }}>
                <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                  Bedrock AI Response
                </div>
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 500, fontSize: '0.85rem' }}>Detected Language:</span>{' '}
                  <span style={{ padding: '0.25rem 0.5rem', background: '#e5e5e5', borderRadius: '0.25rem', fontSize: '0.8rem' }}>
                    {testResult.language}
                  </span>
                </div>
                <div style={{ marginTop: '0.5rem', padding: '0.75rem', background: 'white', borderRadius: '0.375rem', whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                  {testResult.response}
                </div>
              </div>
            )}
          </div>
        )}

        {/* FAQs Tab */}
        {activeTab === 'faqs' && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>FAQ Knowledge Base</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
              These FAQs power the AI auto-reply. Edit <code>shared/faq-config.json</code> and run <code>python scripts/sync_faq.py</code> to update.
            </p>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {(() => {
                const allFaqs = getAllFAQs();
                return Object.entries(allFaqs).map(([category, faqs]) => (
                  <div key={category}>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.5rem', color: '#059669', borderBottom: '2px solid #059669', paddingBottom: '0.25rem' }}>
                      {getCategoryName(category)} ({faqs.length})
                    </div>
                    {faqs.map((faq) => (
                      <div key={faq.id} style={{ padding: '0.75rem', background: '#f8fafc', borderRadius: '0.375rem', marginBottom: '0.5rem', border: '1px solid #e5e7eb' }}>
                        <div style={{ fontWeight: 500, fontSize: '0.85rem', marginBottom: '0.25rem' }}>{faq.question}</div>
                        <div style={{ fontSize: '0.8rem', color: '#555', whiteSpace: 'pre-line' }}>{faq.answer}</div>
                        <div style={{ fontSize: '0.7rem', color: '#999', marginTop: '0.25rem' }}>
                          Keywords: {faq.keywords.join(', ')}
                        </div>
                      </div>
                    ))}
                  </div>
                ));
              })()}
            </div>
          </div>
        )}

        {/* Toast */}
        {toast && (
          <div style={{
            position: 'fixed',
            bottom: '1rem',
            right: '1rem',
            padding: '0.75rem 1.5rem',
            background: toast.type === 'success' ? '#059669' : '#6b7280',
            color: 'white',
            borderRadius: '13px',
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
        .stat-card {
          background: white;
          padding: 1rem;
          border-radius: 0.5rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          text-align: center;
        }
        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: #1f2937;
        }
        .stat-label {
          font-size: 0.85rem;
          color: #6b7280;
          margin-top: 0.25rem;
        }
        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid #e5e7eb;
          border-top-color: #059669;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      {content}
    </Layout>
  );
}
