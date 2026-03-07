/**
 * Internal Chat Tab - Dashboard embedded AI assistant
 * Full-featured chat with controls, logs, and settings
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { API_BASE } from '../../../config/constants';
import { fetchAuthSession } from 'aws-amplify/auth';

const API_ENDPOINT = `${API_BASE}/ai/generate`;

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
  toolsUsed?: string[];
  duration?: number;
}

interface ChatLog {
  id: string;
  timestamp: Date;
  query: string;
  response: string;
  toolsUsed: string[];
  duration: number;
  status: 'success' | 'error';
}

type SubTab = 'chat' | 'logs' | 'controls';

const TOOLS_LIST = [
  { id: 'search_contacts', name: 'Search Contacts', category: 'Contacts' },
  { id: 'create_contact', name: 'Create Contact', category: 'Contacts' },
  { id: 'update_contact', name: 'Update Contact', category: 'Contacts' },
  { id: 'add_contact_email', name: 'Add Email', category: 'Contacts' },
  { id: 'send_whatsapp', name: 'Send WhatsApp', category: 'Messaging' },
  { id: 'send_whatsapp_buttons', name: 'Send Buttons', category: 'Messaging' },
  { id: 'send_whatsapp_list', name: 'Send List', category: 'Messaging' },
  { id: 'send_whatsapp_pay', name: 'WhatsApp Pay', category: 'Messaging' },
  { id: 'send_whatsapp_flow', name: 'Send Flow', category: 'Messaging' },
  { id: 'make_voice_call', name: 'Voice Call', category: 'Messaging' },
  { id: 'send_sms', name: 'Send SMS', category: 'Messaging' },
  { id: 'send_email', name: 'Send Email', category: 'Messaging' },
  { id: 'get_messages', name: 'Get Messages', category: 'Analytics' },
  { id: 'get_stats', name: 'Get Stats', category: 'Analytics' },
  { id: 'schedule_message', name: 'Schedule Message', category: 'Scheduling' },
  { id: 'list_scheduled_messages', name: 'List Scheduled', category: 'Scheduling' },
  { id: 'list_templates', name: 'List Templates', category: 'Templates' },
  { id: 'send_template', name: 'Send Template', category: 'Templates' },
  { id: 'delete_contact', name: 'Delete Contact', category: 'Data' },
  { id: 'delete_messages', name: 'Delete Messages', category: 'Data' },
  { id: 'delete_media_files', name: 'Delete Media', category: 'Data' },
  { id: 'list_media_files', name: 'List Media', category: 'Data' },
  { id: 'clear_all_contact_data', name: 'Clear All Data', category: 'Data' },
  { id: 'get_voice_cdr', name: 'Voice CDR', category: 'Analytics' },
  { id: 'get_billing_summary', name: 'AWS Billing', category: 'Analytics' },
  { id: 'get_invoice_list', name: 'List Invoices', category: 'Invoicing' },
  { id: 'create_invoice', name: 'Create Invoice', category: 'Invoicing' },
  { id: 'get_wix_products', name: 'Wix Products', category: 'Ecommerce' },
  { id: 'get_wix_orders', name: 'Wix Orders', category: 'Ecommerce' },
  { id: 'list_submit_requests', name: 'Flow Submissions', category: 'Flows' },
];

const InternalChatTab: React.FC = () => {
  const [subTab, setSubTab] = useState<SubTab>('chat');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! I\'m your Stack CRM task assistant. I can help you manage contacts, send messages, check stats, and more. Type or use the quick actions below.',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [logs, setLogs] = useState<ChatLog[]>([]);
  const [sessionId] = useState(() => `dash-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const [enabledTools, setEnabledTools] = useState<Set<string>>(new Set(TOOLS_LIST.map(t => t.id)));
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  useEffect(() => {
    if (subTab === 'chat' && inputRef.current) inputRef.current.focus();
  }, [subTab]);

  const clearChat = useCallback(() => {
    setMessages([{
      id: Date.now().toString(),
      role: 'assistant',
      content: 'Chat cleared. How can I help you?',
      timestamp: new Date(),
    }]);
    setLogs([]);
  }, []);

  /** Strip <thinking>...</thinking> tags from AI responses */
  const cleanResponse = (text: string): string => {
    return text.replace(/<thinking>[\s\S]*?<\/thinking>\s*/gi, '').trim();
  };

  const extractResponse = (data: any): string | null => {
    if (!data) return null;
    let raw: string | null = null;
    if (data.suggestedResponse) raw = data.suggestedResponse;
    else if (data.suggestion) raw = data.suggestion;
    if (!raw && data.body) {
      try {
        const parsed = typeof data.body === 'string' ? JSON.parse(data.body) : data.body;
        if (parsed.suggestedResponse) raw = parsed.suggestedResponse;
        else if (parsed.suggestion) raw = parsed.suggestion;
      } catch { /* ignore */ }
    }
    return raw ? cleanResponse(raw) : null;
  };

  const MAX_MESSAGES = 100;

  const processCommand = async (text: string): Promise<string> => {
    const startTime = Date.now();
    try {
      setStatusMessage('Understanding your request...');

      let res: Response;
      try {
        const session = await fetchAuthSession();
        const token = session.tokens?.accessToken?.toString() ?? '';
        res = await fetch(API_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({
            messageContent: text,
            context: 'internal-admin',
            sessionId,
            temperature,
            maxTokens,
          }),
        });
      } catch (fetchErr: any) {
        setStatusMessage('');
        const duration = Date.now() - startTime;
        setLogs(prev => [{
          id: Date.now().toString(), timestamp: new Date(), query: text,
          response: 'Network error', toolsUsed: [], duration, status: 'error'
        }, ...prev]);
        return 'Unable to reach the server. Please check your connection and try again.';
      }

      setStatusMessage('Processing...');

      let data: any;
      try {
        data = await res.json();
      } catch {
        setStatusMessage('');
        const duration = Date.now() - startTime;
        setLogs(prev => [{
          id: Date.now().toString(), timestamp: new Date(), query: text,
          response: 'Invalid response', toolsUsed: [], duration, status: 'error'
        }, ...prev]);
        return 'Received an invalid response from the server. Please try again.';
      }

      setStatusMessage('');
      const duration = Date.now() - startTime;

      const response = extractResponse(data);
      if (response) {
        setLogs(prev => [{
          id: Date.now().toString(), timestamp: new Date(), query: text,
          response: response.substring(0, 200), toolsUsed: [], duration, status: 'success'
        }, ...prev]);
        return response;
      }

      // No response extracted — log as error
      const errMsg = data?.error || 'No response received';
      console.error('Unexpected response:', JSON.stringify(data).substring(0, 500));
      setLogs(prev => [{
        id: Date.now().toString(), timestamp: new Date(), query: text,
        response: errMsg, toolsUsed: [], duration, status: 'error'
      }, ...prev]);
      return 'Something went wrong on the server. Please try again.';
    } catch (error: any) {
      setStatusMessage('');
      const duration = Date.now() - startTime;
      setLogs(prev => [{
        id: Date.now().toString(), timestamp: new Date(), query: text,
        response: error.message, toolsUsed: [], duration, status: 'error'
      }, ...prev]);
      return 'Something went wrong. Please try again.';
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const text = input.trim();
    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', content: text, timestamp: new Date() };
    setMessages(prev => {
      const updated = [...prev, userMsg];
      return updated.length > MAX_MESSAGES ? updated.slice(-MAX_MESSAGES) : updated;
    });
    setInput('');
    setIsLoading(true);

    const loadingId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: loadingId, role: 'assistant', content: '...', timestamp: new Date(), status: 'sending' }]);

    const response = await processCommand(text);
    setMessages(prev => prev.map(m => m.id === loadingId ? { ...m, content: response, status: 'sent' } : m));
    setIsLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const quickAction = (text: string) => {
    setInput(text);
    setTimeout(() => { if (inputRef.current) inputRef.current.focus(); }, 50);
  };

  const toggleTool = (id: string) => {
    setEnabledTools(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const categories = [...new Set(TOOLS_LIST.map(t => t.category))];

  return (
    <div className="internalchat-tab">
      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', borderBottom: '1px solid #e5e7eb', paddingBottom: '8px' }}>
        {(['chat', 'logs', 'controls'] as SubTab[]).map(t => (
          <button key={t} onClick={() => setSubTab(t)} style={{
            padding: '8px 16px', border: 'none', borderRadius: '6px 6px 0 0', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
            background: subTab === t ? '#ECFDF5' : 'transparent',
            color: subTab === t ? '#059669' : '#6b7280',
            borderBottom: subTab === t ? '2px solid #059669' : '2px solid transparent',
          }}>
            {t === 'chat' ? 'Chat' : t === 'logs' ? 'Logs' : 'Controls'}
          </button>
        ))}
        {subTab === 'chat' && (
          <button onClick={clearChat} style={{
            marginLeft: 'auto', padding: '6px 12px', border: '1px solid #d1d5db', borderRadius: '6px',
            background: 'white', color: '#6b7280', cursor: 'pointer', fontSize: '12px',
          }}>
            Clear Chat
          </button>
        )}
      </div>

      {/* CHAT SUB-TAB */}
      {subTab === 'chat' && (
        <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 320px)', minHeight: '400px' }}>
          {/* Quick Actions */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
            {[
              { label: 'Find Contact', cmd: 'find contact ' },
              { label: 'Send Message', cmd: 'send message to ' },
              { label: 'Dashboard Stats', cmd: 'show dashboard stats' },
              { label: 'Voice CDR', cmd: 'show recent voice calls' },
              { label: 'AWS Billing', cmd: 'show current month billing' },
              { label: 'Invoices', cmd: 'list recent invoices' },
              { label: 'Wix Products', cmd: 'list wix products' },
              { label: 'Templates', cmd: 'list templates' },
              { label: 'Flow Submissions', cmd: 'list recent submit requests' },
              { label: 'Send Flow', cmd: 'send submit request flow to ' },
            ].map(a => (
              <button key={a.label} onClick={() => quickAction(a.cmd)} style={{
                padding: '4px 10px', border: '1px solid #d1fae5', borderRadius: '12px',
                background: '#ECFDF5', color: '#059669', cursor: 'pointer', fontSize: '12px',
              }}>
                {a.label}
              </button>
            ))}
          </div>

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px',
            padding: '12px', background: '#fafafa', borderRadius: '8px', border: '1px solid #e5e7eb',
          }}>
            {messages.map(msg => (
              <div key={msg.id} style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
              }}>
                <div style={{
                  padding: '10px 14px', borderRadius: '12px', fontSize: '13px', lineHeight: '1.5',
                  background: msg.role === 'user' ? '#059669' : '#ECFDF5',
                  color: msg.role === 'user' ? 'white' : '#1f2937',
                  opacity: msg.status === 'sending' ? 0.6 : 1,
                }}>
                  {msg.content.split('\n').map((line, i) => (
                    <React.Fragment key={i}>{line}{i < msg.content.split('\n').length - 1 && <br />}</React.Fragment>
                  ))}
                </div>
                <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px', textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))}
            {statusMessage && (
              <div style={{
                padding: '8px 12px', background: '#ECFDF5', border: '1px solid #a7f3d0',
                borderRadius: '8px', color: '#059669', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                <span style={{
                  width: '10px', height: '10px', border: '2px solid #059669', borderTopColor: 'transparent',
                  borderRadius: '50%', animation: 'spin 0.8s linear infinite', display: 'inline-block',
                }} />
                {statusMessage}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'flex-end' }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a command... (e.g. find contact Jignesh)"
              disabled={isLoading}
              rows={1}
              style={{
                flex: 1, padding: '10px 14px', border: '1px solid #d1d5db', borderRadius: '8px',
                fontSize: '13px', resize: 'none', outline: 'none', fontFamily: 'inherit',
                minHeight: '40px', maxHeight: '80px',
              }}
              onFocus={e => (e.target.style.borderColor = '#059669')}
              onBlur={e => (e.target.style.borderColor = '#d1d5db')}
            />
            <button onClick={handleSend} disabled={!input.trim() || isLoading} style={{
              padding: '10px 20px', background: !input.trim() || isLoading ? '#d1d5db' : '#059669',
              color: 'white', border: 'none', borderRadius: '8px', cursor: !input.trim() || isLoading ? 'not-allowed' : 'pointer',
              fontSize: '13px', fontWeight: 500, whiteSpace: 'nowrap',
            }}>
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      )}

      {/* LOGS SUB-TAB */}
      {subTab === 'logs' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', color: '#6b7280' }}>{logs.length} log entries</span>
            {logs.length > 0 && (
              <button onClick={() => setLogs([])} style={{
                padding: '4px 12px', border: '1px solid #d1d5db', borderRadius: '6px',
                background: 'white', color: '#6b7280', cursor: 'pointer', fontSize: '12px',
              }}>
                Clear Logs
              </button>
            )}
          </div>
          {logs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af', fontSize: '14px' }}>
              No logs yet. Start chatting to see activity logs here.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: 'calc(100vh - 340px)', overflowY: 'auto' }}>
              {logs.map(log => (
                <div key={log.id} style={{
                  padding: '12px', background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px',
                  borderLeft: `3px solid ${log.status === 'success' ? '#059669' : '#059669'}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>
                      {log.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                    <span style={{
                      fontSize: '11px', padding: '2px 8px', borderRadius: '10px',
                      background: log.status === 'success' ? '#ECFDF5' : '#f3f4f6',
                      color: log.status === 'success' ? '#059669' : '#6b7280',
                    }}>
                      {log.duration}ms
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: '#1f2937', marginBottom: '4px' }}>
                    {log.query}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280', whiteSpace: 'pre-wrap' }}>
                    {log.response}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* CONTROLS SUB-TAB */}
      {subTab === 'controls' && (
        <div style={{ maxHeight: 'calc(100vh - 320px)', overflowY: 'auto' }}>
          {/* Model Settings */}
          <div style={{ padding: '16px', background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937', marginBottom: '12px' }}>Model Settings</h3>
            <div style={{ display: 'grid', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>Temperature: {temperature}</label>
                <input type="range" min="0" max="1" step="0.1" value={temperature}
                  onChange={e => setTemperature(parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: '#059669' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#9ca3af' }}>
                  <span>Focused</span><span>Creative</span>
                </div>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#6b7280', display: 'block', marginBottom: '4px' }}>Max Tokens: {maxTokens}</label>
                <input type="range" min="512" max="4096" step="256" value={maxTokens}
                  onChange={e => setMaxTokens(parseInt(e.target.value))}
                  style={{ width: '100%', accentColor: '#059669' }} />
              </div>
            </div>
          </div>

          {/* Tool Capabilities */}
          <div style={{ padding: '16px', background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937' }}>Tool Capabilities ({enabledTools.size}/{TOOLS_LIST.length})</h3>
              <button onClick={() => {
                if (enabledTools.size === TOOLS_LIST.length) setEnabledTools(new Set());
                else setEnabledTools(new Set(TOOLS_LIST.map(t => t.id)));
              }} style={{
                padding: '4px 10px', border: '1px solid #d1d5db', borderRadius: '6px',
                background: 'white', color: '#6b7280', cursor: 'pointer', fontSize: '11px',
              }}>
                {enabledTools.size === TOOLS_LIST.length ? 'Disable All' : 'Enable All'}
              </button>
            </div>
            {categories.map(cat => (
              <div key={cat} style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#059669', marginBottom: '6px' }}>{cat}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {TOOLS_LIST.filter(t => t.category === cat).map(tool => (
                    <label key={tool.id} style={{
                      display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px',
                      border: `1px solid ${enabledTools.has(tool.id) ? '#a7f3d0' : '#e5e7eb'}`,
                      borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
                      background: enabledTools.has(tool.id) ? '#ECFDF5' : 'white',
                      color: enabledTools.has(tool.id) ? '#059669' : '#9ca3af',
                    }}>
                      <input type="checkbox" checked={enabledTools.has(tool.id)} onChange={() => toggleTool(tool.id)}
                        style={{ accentColor: '#059669', width: '12px', height: '12px' }} />
                      {tool.name}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Session Info */}
          <div style={{ padding: '16px', background: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937', marginBottom: '12px' }}>Session Info</h3>
            <div style={{ display: 'grid', gap: '8px', fontSize: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Session ID</span>
                <span style={{ color: '#1f2937', fontFamily: 'monospace', fontSize: '11px' }}>{sessionId.substring(0, 20)}...</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Messages</span>
                <span style={{ color: '#1f2937' }}>{messages.length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Log Entries</span>
                <span style={{ color: '#1f2937' }}>{logs.length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Model</span>
                <span style={{ color: '#1f2937' }}>Amazon Nova Lite</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6b7280' }}>Endpoint</span>
                <span style={{ color: '#1f2937', fontFamily: 'monospace', fontSize: '11px' }}>api.wecare.digital</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InternalChatTab;
