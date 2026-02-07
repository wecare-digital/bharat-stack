/**
 * WhatsApp Calling Page
 * WhatsApp Business Calling API — VoIP calls within WhatsApp threads
 * Signaling: HTTPS webhooks or SIP | Media: WebRTC
 * Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/calling
 */
import React, { useState } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';

interface PageProps { signOut?: () => void; user?: any; }

const PHONE_NUMBERS = [
  { id: 'phone-number-id-2ff05755631b41f29151c0573b7a4e2a', display: '+91 93309 94400', name: 'WECARE.DIGITAL' },
  { id: 'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6', display: '+91 99033 00044', name: 'MERA ASHIANA' },
];

const SETUP_STEPS = [
  {
    step: 1, done: false,
    title: 'Prerequisites',
    desc: 'Existing Cloud API integration, access token with whatsapp_business_messaging + whatsapp_business_management permissions, messaging limit of 1,000+ business-initiated conversations per 24h rolling window.',
  },
  {
    step: 2, done: false,
    title: 'Subscribe to "calls" webhook field',
    desc: 'In Meta App Dashboard → WhatsApp → Configuration → subscribe to the "calls" webhook field. This delivers call connection and termination events to your webhook URL.',
    code: 'Webhook field: calls (under WhatsApp Business Account)',
  },
  {
    step: 3, done: false,
    title: 'Enable Calling via API',
    desc: 'POST to /{phone-number-id}/settings with the calling object to enable the feature and configure call icon visibility and call hours.',
    code: `POST /{phone-number-id}/settings
{
  "calling": {
    "call_icon_visibility": "default",
    "call_hours": {
      "timezone": "Asia/Kolkata",
      "sun": [{ "from": "09:00", "to": "21:00" }],
      "mon": [{ "from": "09:00", "to": "21:00" }],
      "tue": [{ "from": "09:00", "to": "21:00" }],
      "wed": [{ "from": "09:00", "to": "21:00" }],
      "thu": [{ "from": "09:00", "to": "21:00" }],
      "fri": [{ "from": "09:00", "to": "21:00" }],
      "sat": [{ "from": "09:00", "to": "21:00" }]
    }
  }
}`,
  },
  {
    step: 4, done: false,
    title: 'Handle User-Initiated Calls (Inbound)',
    desc: 'When a user calls, you receive a "connect" webhook. Respond with pre-accept → accept (with SDP answer) to establish WebRTC media. Store the call_id for subsequent actions. If you don\'t respond, the call times out and you get a "terminate" webhook.',
    code: `// Webhook: call connection event
{
  "entry": [{
    "changes": [{
      "value": {
        "event": "connect",
        "call_id": "wamid.xxx",
        "from": "919667664137",
        "sdp_offer": "v=0\\r\\no=..."
      }
    }]
  }]
}

// Respond: pre-accept then accept
POST /{phone-number-id}/calls
{ "action": "pre_accept", "call_id": "wamid.xxx" }

POST /{phone-number-id}/calls
{ "action": "accept", "call_id": "wamid.xxx", "sdp_answer": "..." }`,
  },
  {
    step: 5, done: false,
    title: 'Request Call Permission (for Outbound)',
    desc: 'Send an interactive message with type "call_permission_request" or use a template. User grants temporary permission. Limits: max 1 request per 24h, 2 per 7 days. Once granted: max 5 connected calls/day, 35 per 7 days.',
    code: `POST /{phone-number-id}/messages
{
  "messaging_product": "whatsapp",
  "to": "919667664137",
  "type": "interactive",
  "interactive": {
    "type": "call_permission_request",
    "body": { "text": "Can we call you to discuss your query?" }
  }
}`,
  },
  {
    step: 6, done: false,
    title: 'Make Business-Initiated Calls (Outbound)',
    desc: 'After permission is granted, initiate a call with an SDP offer. The user receives a ringing notification in WhatsApp. You get a "connect" webhook with their SDP answer when they pick up.',
    code: `POST /{phone-number-id}/calls
{
  "action": "create",
  "to": "919667664137",
  "sdp_offer": "v=0\\r\\no=..."
}`,
  },
  {
    step: 7, done: false,
    title: 'Deploy Call Handler Lambda',
    desc: 'Lambda processes call webhooks (connect, terminate), manages WebRTC signaling, integrates Amazon Polly for IVR prompts, and logs calls to DynamoDB.',
  },
];

const AWS_RESOURCES = [
  { service: 'API Gateway', resource: 'k4vqzmi07b', purpose: 'Webhook endpoint for Meta call events', status: 'active' },
  { service: 'Lambda', resource: 'wecare-whatsapp-voice', purpose: 'TTS generation, media upload, call webhook handler', status: 'active' },
  { service: 'Amazon Polly', resource: 'SynthesizeSpeech', purpose: 'Neural TTS for IVR prompts and voice notes', status: 'active' },
  { service: 'S3', resource: 'auth.wecare.digital/whatsapp-media/', purpose: 'TTS audio files, call recordings', status: 'active' },
  { service: 'DynamoDB', resource: 'WhatsAppVoiceTable', purpose: 'TTS logs, call event logs', status: 'active' },
  { service: 'Secrets Manager', resource: 'wecare/meta-app-secret', purpose: 'Meta App Secret for webhook verification', status: 'active' },
];

const CALL_LIMITS = [
  { limit: 'Permission requests', value: '1 per 24h, 2 per 7 days per user' },
  { limit: 'Connected calls (after permission)', value: '5 per day, 35 per 7 days per user' },
  { limit: 'Messaging limit required', value: '1,000+ business-initiated conversations / 24h' },
  { limit: 'Call icon visibility', value: '"default" (show) or "disable_all" (hide, use CTA buttons)' },
  { limit: 'Signaling protocol', value: 'HTTPS (webhooks) or SIP' },
  { limit: 'Media protocol', value: 'WebRTC (audio)' },
];

const WhatsAppCallingPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'setup' | 'resources'>('overview');
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const toast = useToastContext();

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success('Copied to clipboard');
  };

  const s = {
    page: { padding: '24px', maxWidth: '1100px', margin: '0 auto' } as React.CSSProperties,
    header: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' as const,
      marginBottom: '24px', padding: '20px 24px', gap: '12px',
      background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)',
      borderRadius: '12px', border: '1px solid #a7f3d0',
    } as React.CSSProperties,
    tabs: {
      display: 'flex', gap: '4px', marginBottom: '20px', background: '#f0fdf4',
      padding: '4px', borderRadius: '10px', border: '1px solid #d1fae5', flexWrap: 'wrap' as const,
    } as React.CSSProperties,
    card: {
      background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px',
      padding: '16px 20px', marginBottom: '12px',
    } as React.CSSProperties,
  };

  const tab = (active: boolean): React.CSSProperties => ({
    padding: '8px 20px', border: 'none', borderRadius: '8px', cursor: 'pointer',
    fontSize: '13px', fontWeight: active ? 600 : 500,
    background: active ? '#10b981' : 'transparent', color: active ? '#fff' : '#065f46',
  });

  const badge = (status: string): React.CSSProperties => ({
    display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,
    background: status === 'active' || status === 'available' ? '#ecfdf5' : status === 'planned' ? '#fef3c7' : '#f3f4f6',
    color: status === 'active' || status === 'available' ? '#065f46' : status === 'planned' ? '#92400e' : '#6b7280',
    border: `1px solid ${status === 'active' || status === 'available' ? '#a7f3d0' : status === 'planned' ? '#fde68a' : '#e5e7eb'}`,
  });

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="WhatsApp Calling | WECARE.DIGITAL" description="WhatsApp Business Calling API" />
      <div style={s.page}>
        {/* Header */}
        <div style={s.header}>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', color: '#065f46' }}>📞 WhatsApp Business Calling</h2>
            <p style={{ margin: '6px 0 0', fontSize: '13px', color: '#047857' }}>
              VoIP calls in WhatsApp threads — HTTPS/SIP signaling + WebRTC media + Amazon Polly IVR
            </p>
          </div>
          <span style={badge('planned')}>Setup Required</span>
        </div>

        {/* Tabs */}
        <div style={s.tabs}>
          <button style={tab(activeTab === 'overview')} onClick={() => setActiveTab('overview')}>Overview</button>
          <button style={tab(activeTab === 'setup')} onClick={() => setActiveTab('setup')}>Setup Guide</button>
          <button style={tab(activeTab === 'resources')} onClick={() => setActiveTab('resources')}>AWS Resources</button>
        </div>

        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div>
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0' }}>
              <h3 style={{ margin: '0 0 8px', fontSize: '15px', color: '#065f46' }}>How it works</h3>
              <p style={{ margin: 0, fontSize: '13px', color: '#047857', lineHeight: 1.6 }}>
                The WhatsApp Business Calling API (launched July 2025) enables bidirectional VoIP calls
                within WhatsApp conversation threads. Signaling uses HTTPS webhooks or SIP protocol.
                Media is exchanged via WebRTC. Calls appear in the same chat thread as messages,
                maintaining full conversation context.
              </p>
            </div>

            {/* Call Flow Diagram */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#111827' }}>Call Flow</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
                {[
                  { icon: '📱', label: 'User calls', desc: 'User taps call icon in WhatsApp' },
                  { icon: '🔔', label: 'Webhook: connect', desc: 'Meta sends call event + SDP offer' },
                  { icon: '✅', label: 'Pre-accept → Accept', desc: 'Business responds with SDP answer' },
                  { icon: '🎙', label: 'WebRTC call', desc: 'Audio streams via WebRTC' },
                  { icon: '📴', label: 'Webhook: terminate', desc: 'Call ends, log to DynamoDB' },
                ].map((f, i) => (
                  <div key={i} style={{ padding: '12px', background: '#f9fafb', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', marginBottom: '6px' }}>{f.icon}</div>
                    <div style={{ fontWeight: 600, fontSize: '12px', color: '#111827', marginBottom: '2px' }}>{f.label}</div>
                    <div style={{ fontSize: '11px', color: '#6b7280' }}>{f.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Limits */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Limits & Configuration</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <tbody>
                    {CALL_LIMITS.map((l, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 500, color: '#374151', whiteSpace: 'nowrap' }}>{l.limit}</td>
                        <td style={{ padding: '8px 12px', color: '#6b7280', fontFamily: 'monospace', fontSize: '12px' }}>{l.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Phone Numbers */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>WABA Phone Numbers</h4>
              {PHONE_NUMBERS.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0', borderBottom: i < PHONE_NUMBERS.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>{p.display}</span>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>{p.name}</span>
                  <code style={{ fontSize: '11px', color: '#9ca3af', marginLeft: 'auto', wordBreak: 'break-all' }}>{p.id}</code>
                </div>
              ))}
            </div>

            {/* Docs */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 8px', fontSize: '14px', color: '#111827' }}>Documentation</h4>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Meta Calling API', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling' },
                  { label: 'Calling Prerequisites', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling#step-1--prerequisites' },
                  { label: 'SIP Integration', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/sip' },
                  { label: 'Amazon Polly', url: 'https://docs.aws.amazon.com/polly/latest/dg/what-is.html' },
                  { label: 'AWS Social Messaging', url: 'https://docs.aws.amazon.com/social-messaging/latest/APIReference/Welcome.html' },
                ].map((d, i) => (
                  <a key={i} href={d.url} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: '13px', color: '#10b981', textDecoration: 'none' }}>
                    {d.label} ↗
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SETUP TAB */}
        {activeTab === 'setup' && (
          <div>
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0', marginBottom: '20px' }}>
              <p style={{ margin: 0, fontSize: '13px', color: '#065f46' }}>
                Follow these steps to enable WhatsApp Business Calling. You need webhooks (HTTPS) or SIP for signaling, and WebRTC for media.
              </p>
            </div>
            {SETUP_STEPS.map((step) => (
              <div key={step.step} style={{ ...s.card, cursor: step.code ? 'pointer' : 'default' }}
                onClick={() => step.code && setExpandedStep(expandedStep === step.step ? null : step.step)}>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
                    background: step.done ? '#10b981' : '#e5e7eb', color: step.done ? '#fff' : '#6b7280',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '14px', fontWeight: 700,
                  }}>
                    {step.done ? '✓' : step.step}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>{step.title}</span>
                      {step.code && (
                        <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                          {expandedStep === step.step ? '▼' : '▶'} code
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '13px', color: '#6b7280', lineHeight: 1.5 }}>{step.desc}</div>
                  </div>
                </div>
                {step.code && expandedStep === step.step && (
                  <div style={{ marginTop: '12px', marginLeft: '48px' }}>
                    <div style={{ position: 'relative' }}>
                      <pre style={{
                        background: '#1e293b', color: '#e2e8f0', padding: '14px 16px',
                        borderRadius: '8px', fontSize: '12px', lineHeight: 1.5,
                        overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                      }}>
                        {step.code}
                      </pre>
                      <button
                        onClick={(e) => { e.stopPropagation(); copyCode(step.code!); }}
                        style={{
                          position: 'absolute', top: '8px', right: '8px',
                          background: '#334155', border: 'none', color: '#94a3b8',
                          padding: '4px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer',
                        }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* RESOURCES TAB */}
        {activeTab === 'resources' && (
          <div>
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0', marginBottom: '20px' }}>
              <p style={{ margin: 0, fontSize: '13px', color: '#065f46' }}>
                AWS resources for WhatsApp Calling + TTS integration. Region: us-east-1.
              </p>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                    <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Service</th>
                    <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Resource</th>
                    <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Purpose</th>
                    <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {AWS_RESOURCES.map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 500, color: '#111827' }}>{r.service}</td>
                      <td style={{ padding: '10px 14px', color: '#6b7280', fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all' }}>{r.resource}</td>
                      <td style={{ padding: '10px 14px', color: '#6b7280' }}>{r.purpose}</td>
                      <td style={{ padding: '10px 14px' }}><span style={badge(r.status)}>{r.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default WhatsAppCallingPage;
