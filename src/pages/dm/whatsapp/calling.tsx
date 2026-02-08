/**
 * WhatsApp Calling Page
 * WhatsApp Business Calling API — VoIP calls within WhatsApp threads
 * Signaling: Graph API + Webhooks (HTTPS) or SIP (TLS) | Media: WebRTC (OPUS)
 * Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/calling
 */
import React, { useState } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';

interface PageProps { signOut?: () => void; user?: any; }

const PHONE_NUMBERS = [
  { id: 'phone-number-id-2ff05755631b41f29151c0573b7a4e2a', metaId: '1065003613352032', display: '+91 93309 94400', name: 'WECARE.DIGITAL', country: 'IN', tier: 'TIER_1K', quality: 'GREEN', callingReady: false },
  { id: 'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6', metaId: '1065809899939064', display: '+91 99033 00044', name: 'Manish Agarwal', country: 'IN', tier: 'TIER_10K', quality: 'GREEN', callingReady: true },
];

// Webhook configuration — LIVE
const WEBHOOK_CONFIG = {
  callbackUrl: 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-calling',
  verifyToken: 'wecare_calling_verify_2026',
  subscribedFields: ['calls'],
  lambda: 'wecare-whatsapp-calling',
  table: 'base-wecare-digital-WhatsAppCallingTable',
  status: 'deployed',  // deployed, verified, subscribed
};

// Meta Access Token info
const META_TOKEN = {
  appId: '1623342242027107',
  secretName: 'wecare/meta-system-user-token',
  scopes: ['whatsapp_business_messaging', 'whatsapp_business_management', 'public_profile'],
  wabaAccess: ['1728153881476046', '761651636983279'],
  tokenType: 'System User',
  status: 'active',
};

// Signaling & Media configurations from Meta docs
const SIGNAL_CONFIGS = [
  { config: 'Default (after enabling)', signaling: 'Graph APIs + Webhooks', transport: 'HTTPS', media: 'WebRTC (ICE + DTLS + SRTP)', codec: 'OPUS' },
  { config: 'SIP with WebRTC', signaling: 'SIP (explicit enablement)', transport: 'TLS', media: 'WebRTC (ICE + DTLS + SRTP)', codec: 'OPUS' },
  { config: 'SIP with SDES media', signaling: 'SIP (explicit enablement)', transport: 'TLS', media: 'SDES SRTP (explicit enablement)', codec: 'OPUS' },
];

const SETUP_STEPS = [
  {
    step: 1, done: true,
    title: 'Prerequisites',
    desc: 'Cloud API ✓ | whatsapp_business_messaging permission ✓ | System User token created (App 1623342242027107) ✓ | +919903300044 has TIER_10K (meets 2K requirement) ✓ | +919330994400 has TIER_1K (needs upgrade to 2K for calling).',
  },
  {
    step: 2, done: false,
    title: 'Enable Calling on Phone Number',
    desc: 'POST to /{phone-number-id}/settings with the calling object. Configure call icon visibility, business call hours, and callback request settings.',
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
    step: 3, done: false,
    title: 'Configure Call Control (Optional)',
    desc: 'Inbound call control: prevent users from placing calls. Business call hours: avoid missed calls, direct users to message when closed. Callback requests: offer users the option to request a callback when you don\'t pick up.',
    code: `// Disable inbound calls (outbound only)
POST /{phone-number-id}/settings
{ "calling": { "call_icon_visibility": "disable_all" } }

// Restrict call icon to specific countries
POST /{phone-number-id}/settings
{ "calling": { "restrict_to_user_countries": ["IN", "AE"] } }`,
  },
  {
    step: 4, done: false,
    title: 'Handle User-Initiated Calls (Inbound)',
    desc: 'When a user calls, you receive a "connect" webhook with SDP offer. Respond with pre-accept → accept (with SDP answer) to establish WebRTC media. If you don\'t respond, the call times out and you get a "terminate" webhook.',
    code: `// Webhook: call connection event
{
  "entry": [{
    "changes": [{
      "value": {
        "event": "connect",
        "call_id": "wamid.xxx",
        "from": "919330994400",
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
    desc: 'Send an interactive message with type "call_permission_request" or use a template. Limits: 1 request per 24h, 2 per 7 days per user. Once granted: up to 100 connected calls/day per user (updated Dec 2025).',
    code: `POST /{phone-number-id}/messages
{
  "messaging_product": "whatsapp",
  "to": "919330994400",
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
    desc: 'After permission is granted, initiate a call with an SDP offer. The user receives a ringing notification in WhatsApp. You get a "connect" webhook with their SDP answer when they pick up. Note: Business-initiated calling is NOT available in USA, Canada, Turkey, Egypt, Vietnam, Nigeria.',
    code: `POST /{phone-number-id}/calls
{
  "action": "create",
  "to": "919330994400",
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
  { service: 'API Gateway', resource: 'k4vqzmi07b', purpose: 'Webhook endpoint for Meta call events + messaging', status: 'active' },
  { service: 'Lambda', resource: 'wecare-whatsapp-calling', purpose: 'Calling webhook handler (verify + call events)', status: 'active' },
  { service: 'Lambda', resource: 'wecare-whatsapp-voice', purpose: 'TTS generation, media upload, audio messages', status: 'active' },
  { service: 'DynamoDB', resource: 'WhatsAppCallingTable', purpose: 'Call event logs (connect, terminate, permission)', status: 'active' },
  { service: 'DynamoDB', resource: 'WhatsAppVoiceTable', purpose: 'TTS logs, voice note logs', status: 'active' },
  { service: 'Amazon Polly', resource: 'SynthesizeSpeech', purpose: 'Neural TTS for IVR prompts and voice notes (OPUS)', status: 'active' },
  { service: 'S3', resource: 'auth.wecare.digital/whatsapp-media/', purpose: 'TTS audio files, call recordings', status: 'active' },
  { service: 'Secrets Manager', resource: 'wecare/meta-app-secret', purpose: 'Meta App Secret for webhook verification', status: 'active' },
];

const CALL_LIMITS = [
  { limit: 'Messaging limit required', value: '2,000+ business-initiated conversations / 24h rolling window' },
  { limit: 'Permission requests', value: '1 per 24h, 2 per 7 days per user' },
  { limit: 'Connected calls (after permission)', value: '100 per day per user (updated Dec 2025)' },
  { limit: 'Unanswered call threshold', value: '2 consecutive → warning, 4 consecutive → permission revoked' },
  { limit: 'Audio codec', value: 'OPUS (G.711 coming soon — Alpha for select partners)' },
  { limit: 'Call icon visibility', value: '"default" (show), "disable_all" (hide), or restrict_to_user_countries' },
  { limit: 'Signaling protocol', value: 'Graph API + Webhooks (HTTPS) or SIP (TLS)' },
  { limit: 'Media protocol', value: 'WebRTC (ICE + DTLS + SRTP) or SDES SRTP' },
];

const BLOCKED_COUNTRIES = ['USA', 'Canada', 'Turkey', 'Egypt', 'Vietnam', 'Nigeria'];

const CHANGELOG = [
  { date: 'Dec 19, 2025', title: 'Business-initiated call limit increased', desc: 'Up to 100 calls/day per user (from 10/day)' },
  { date: 'Dec 10, 2025', title: 'restrict_to_user_countries', desc: 'Control which countries see the call icon' },
  { date: 'Oct 13, 2025', title: 'Limit increase + Sandbox docs', desc: 'Calls increased to 10/day. Testing & Sandbox section added' },
  { date: 'Sep 29, 2025', title: 'Asterisk integration guide', desc: 'New guide to integrate with Asterisk PBX' },
  { date: 'Sep 24, 2025', title: 'Context propagation', desc: 'Opaque string in call buttons/deep links for tracking call origin' },
  { date: 'Sep 8, 2025', title: 'Health Status API update', desc: 'New can_receive_call_sip field for SIP setup diagnostics' },
  { date: 'Sep 5, 2025', title: 'Low call pickup restrictions', desc: 'Restrictions for low call pickup rates now in effect' },
  { date: 'Jul 21, 2025', title: 'Account settings webhooks', desc: 'Get webhooks when calling settings are updated' },
];

const WhatsAppCallingPage: React.FC<PageProps> = ({ signOut, user }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'live' | 'webhook' | 'setup' | 'resources'>('overview');
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [autoPickup, setAutoPickup] = useState(false);
  const [autoPickupLoading, setAutoPickupLoading] = useState(false);
  const [activeCalls, setActiveCalls] = useState<any[]>([]);
  const [callLogs, setCallLogs] = useState<any[]>([]);
  const [loadingCalls, setLoadingCalls] = useState(false);
  const toast = useToastContext();

  const API_BASE = 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod';

  // Load auto-pickup config
  const loadConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/config`);
      if (res.ok) {
        const data = await res.json();
        setAutoPickup(data.autoPickup || false);
      }
    } catch (e) { console.error('Config load error:', e); }
  };

  // Toggle auto-pickup
  const toggleAutoPickup = async () => {
    setAutoPickupLoading(true);
    try {
      const newVal = !autoPickup;
      const res = await fetch(`${API_BASE}/whatsapp-calling/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autoPickup: newVal }),
      });
      if (res.ok) {
        setAutoPickup(newVal);
        toast.success(`Auto-pickup ${newVal ? 'enabled' : 'disabled'}`);
      }
    } catch (e) { toast.error('Failed to update config'); }
    setAutoPickupLoading(false);
  };

  // Load active calls
  const loadActiveCalls = async () => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/active`);
      if (res.ok) {
        const data = await res.json();
        setActiveCalls(data.calls || []);
      }
    } catch (e) { console.error('Active calls error:', e); }
  };

  // Load call logs
  const loadCallLogs = async () => {
    setLoadingCalls(true);
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/logs`);
      if (res.ok) {
        const data = await res.json();
        setCallLogs(data.logs || []);
      }
    } catch (e) { console.error('Logs error:', e); }
    setLoadingCalls(false);
  };

  // Reject a ringing call
  const rejectCall = async (callId: string, phoneNumberId: string) => {
    try {
      await fetch(`${API_BASE}/whatsapp-calling/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callId, phoneNumberId }),
      });
      toast.success('Call rejected');
      loadActiveCalls();
    } catch (e) { toast.error('Failed to reject call'); }
  };

  // Hangup an active call
  const hangupCall = async (callId: string, phoneNumberId: string) => {
    try {
      await fetch(`${API_BASE}/whatsapp-calling/hangup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callId, phoneNumberId }),
      });
      toast.success('Call ended');
      loadActiveCalls();
    } catch (e) { toast.error('Failed to hang up'); }
  };

  // WebRTC state
  const peerConnectionRef = React.useRef<RTCPeerConnection | null>(null);
  const localStreamRef = React.useRef<MediaStream | null>(null);

  // Answer a call using WebRTC — sets up peer connection, generates SDP answer, sends to backend
  const answerCallWebRTC = async (call: any) => {
    const { callId, phoneNumberId, sdpOffer } = call;

    if (!sdpOffer) {
      // No SDP in the call record — just do server-side accept (auto-pickup style)
      toast.info('No SDP offer available — sending server-side accept');
      try {
        const res = await fetch(`${API_BASE}/whatsapp-calling/accept`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ callId, phoneNumberId, sdpAnswer: '' }),
        });
        const data = await res.json();
        if (data.success) toast.success('Call accepted (server-side)');
        else toast.error(`Accept failed: ${JSON.stringify(data.error || data)}`);
      } catch (e) { toast.error('Failed to accept call'); }
      loadActiveCalls();
      return;
    }

    try {
      // 1. Get microphone access
      toast.info('Requesting microphone access...');
      const localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStreamRef.current = localStream;

      // 2. Create RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
        ],
      });
      peerConnectionRef.current = pc;

      // 3. Add local audio tracks
      localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

      // 4. Handle remote audio stream
      pc.ontrack = (event) => {
        const audioEl = document.getElementById('remoteAudio') as HTMLAudioElement;
        if (audioEl && event.streams[0]) {
          audioEl.srcObject = event.streams[0];
        }
      };

      // 5. Log ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          console.log('ICE candidate:', event.candidate.candidate);
        }
      };

      pc.onconnectionstatechange = () => {
        console.log('WebRTC connection state:', pc.connectionState);
        if (pc.connectionState === 'connected') {
          toast.success('WebRTC audio connected');
        } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
          toast.error(`WebRTC ${pc.connectionState}`);
        }
      };

      // 6. Set remote description (SDP offer from Meta)
      await pc.setRemoteDescription({ type: 'offer', sdp: sdpOffer });

      // 7. Create SDP answer
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // 8. Wait for ICE gathering to complete (or timeout after 3s)
      const sdpAnswer = await new Promise<string>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve(pc.localDescription?.sdp || answer.sdp || '');
          return;
        }
        const timeout = setTimeout(() => resolve(pc.localDescription?.sdp || answer.sdp || ''), 3000);
        pc.onicegatheringstatechange = () => {
          if (pc.iceGatheringState === 'complete') {
            clearTimeout(timeout);
            resolve(pc.localDescription?.sdp || answer.sdp || '');
          }
        };
      });

      // 9. Send pre_accept + accept with SDP answer to backend → Meta
      toast.info('Sending SDP answer to Meta...');
      const res = await fetch(`${API_BASE}/whatsapp-calling/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callId, phoneNumberId, sdpAnswer }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success('Call connected — audio active');
      } else {
        toast.error(`Accept failed: ${data.step || 'unknown'} — ${JSON.stringify(data.error || {})}`);
        cleanupWebRTC();
      }
      loadActiveCalls();

    } catch (err: any) {
      console.error('WebRTC answer error:', err);
      toast.error(`WebRTC error: ${err.message || err}`);
      cleanupWebRTC();
    }
  };

  // Cleanup WebRTC resources
  const cleanupWebRTC = () => {
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(t => t.stop());
      localStreamRef.current = null;
    }
    const audioEl = document.getElementById('remoteAudio') as HTMLAudioElement;
    if (audioEl) audioEl.srcObject = null;
  };

  // Load on mount + poll active calls every 5s when on Live tab
  React.useEffect(() => {
    loadConfig();
    loadCallLogs();
  }, []);

  React.useEffect(() => {
    if (activeTab === 'live') {
      loadActiveCalls();
      const interval = setInterval(loadActiveCalls, 5000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

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

  const thStyle: React.CSSProperties = { padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#374151', fontSize: '12px', whiteSpace: 'nowrap' };
  const tdStyle: React.CSSProperties = { padding: '8px 12px', fontSize: '12px', color: '#6b7280' };

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="WhatsApp Calling | WECARE.DIGITAL" description="WhatsApp Business Calling API" />
      <div style={s.page}>
        {/* Header */}
        <div style={s.header}>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', color: '#065f46' }}>📞 WhatsApp Business Calling</h2>
            <p style={{ margin: '6px 0 0', fontSize: '13px', color: '#047857' }}>
              VoIP calls in WhatsApp threads — Graph API/SIP signaling + WebRTC media (OPUS) + Amazon Polly IVR
            </p>
          </div>
          <span style={badge('active')}>Webhook Deployed</span>
        </div>

        {/* Tabs */}
        <div style={s.tabs}>
          <button style={tab(activeTab === 'overview')} onClick={() => setActiveTab('overview')}>Overview</button>
          <button style={tab(activeTab === 'live')} onClick={() => setActiveTab('live')}>🔴 Live Calls</button>
          <button style={tab(activeTab === 'webhook')} onClick={() => setActiveTab('webhook')}>Webhook Config</button>
          <button style={tab(activeTab === 'setup')} onClick={() => setActiveTab('setup')}>Setup Guide</button>
          <button style={tab(activeTab === 'resources')} onClick={() => setActiveTab('resources')}>AWS Resources</button>
        </div>

        {/* LIVE CALLS TAB — WebRTC Call Handling */}
        {activeTab === 'live' && (
          <div>
            {/* Auto-pickup toggle */}
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '15px', color: '#065f46' }}>Live Call Dashboard</h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#047857' }}>
                  Incoming calls appear here in real-time. Answer calls to establish WebRTC audio in your browser.
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button onClick={loadActiveCalls} style={{ padding: '6px 14px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>
                  Refresh
                </button>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#065f46', cursor: 'pointer' }}>
                  <input type="checkbox" checked={autoPickup} onChange={toggleAutoPickup} disabled={autoPickupLoading}
                    style={{ width: '16px', height: '16px', accentColor: '#10b981' }} />
                  Auto-pickup
                </label>
              </div>
            </div>

            {/* Active / Ringing Calls */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#111827' }}>
                Active Calls {activeCalls.length > 0 && <span style={{ ...badge('active'), marginLeft: '8px' }}>{activeCalls.length}</span>}
              </h4>
              {activeCalls.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: '#9ca3af' }}>
                  <div style={{ fontSize: '36px', marginBottom: '8px' }}>📞</div>
                  <p style={{ margin: 0, fontSize: '14px' }}>No active calls</p>
                  <p style={{ margin: '4px 0 0', fontSize: '12px' }}>Incoming calls will appear here when a user calls your WhatsApp number</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {activeCalls.map((call: any, i: number) => (
                    <div key={call.callId || i} style={{
                      padding: '14px 16px', borderRadius: '10px',
                      background: call.status === 'ringing' ? '#fef3c7' : call.status === 'connected' ? '#ecfdf5' : '#f3f4f6',
                      border: `1px solid ${call.status === 'ringing' ? '#fde68a' : call.status === 'connected' ? '#a7f3d0' : '#e5e7eb'}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                        <div>
                          <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>
                            {call.callerName || call.fromNumber || 'Unknown'}
                          </span>
                          {call.callerName && <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '8px' }}>{call.fromNumber}</span>}
                          <span style={{ ...badge(call.status === 'ringing' ? 'planned' : call.status === 'connected' ? 'active' : 'default'), marginLeft: '8px' }}>
                            {call.status === 'ringing' ? '🔔 Ringing' : call.status === 'connected' ? '🟢 Connected' : call.status}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {call.status === 'ringing' && (
                            <>
                              <button onClick={() => answerCallWebRTC(call)}
                                style={{ padding: '6px 16px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>
                                ✅ Answer
                              </button>
                              <button onClick={() => rejectCall(call.callId, call.phoneNumberId)}
                                style={{ padding: '6px 16px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>
                                ❌ Reject
                              </button>
                            </>
                          )}
                          {call.status === 'connected' && (
                            <button onClick={() => { hangupCall(call.callId, call.phoneNumberId); cleanupWebRTC(); }}
                              style={{ padding: '6px 16px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>
                              📴 Hang Up
                            </button>
                          )}
                        </div>
                      </div>
                      <div style={{ marginTop: '6px', fontSize: '11px', color: '#6b7280' }}>
                        Call ID: <code style={{ fontSize: '10px' }}>{call.callId}</code>
                        {call.displayPhone && <> | To: {call.displayPhone}</>}
                        {call.direction && <> | {call.direction}</>}
                        {call.timestamp && <> | {new Date(parseInt(call.timestamp) * 1000).toLocaleTimeString()}</>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* WebRTC Status */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>WebRTC Status</h4>
              <div style={{ fontSize: '13px', color: '#6b7280', lineHeight: 1.8 }}>
                <div>Browser WebRTC: <span style={{ color: typeof window !== 'undefined' && (window as any).RTCPeerConnection ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  {typeof window !== 'undefined' && (window as any).RTCPeerConnection ? '✓ Supported' : '✗ Not supported'}
                </span></div>
                <div>Microphone: <span style={{ fontWeight: 500 }}>Will request permission when answering a call</span></div>
                <div>Audio codec: <span style={{ fontWeight: 500 }}>OPUS (required by Meta)</span></div>
                <div>ICE servers: <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>stun:stun.l.google.com:19302</span></div>
              </div>
              {/* Hidden audio element for remote stream */}
              <audio id="remoteAudio" autoPlay style={{ display: 'none' }} />
            </div>

            {/* Recent Call Logs */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h4 style={{ margin: 0, fontSize: '14px', color: '#111827' }}>Recent Call Logs</h4>
                <button onClick={loadCallLogs} style={{ padding: '4px 12px', background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '6px', cursor: 'pointer', fontSize: '11px' }}>
                  {loadingCalls ? 'Loading...' : 'Refresh'}
                </button>
              </div>
              {callLogs.length === 0 ? (
                <p style={{ margin: 0, fontSize: '13px', color: '#9ca3af', textAlign: 'center', padding: '16px' }}>No call logs yet</p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                        <th style={thStyle}>Time</th>
                        <th style={thStyle}>From</th>
                        <th style={thStyle}>Event</th>
                        <th style={thStyle}>Status</th>
                        <th style={thStyle}>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {callLogs.slice(0, 20).map((log: any, i: number) => (
                        <tr key={log.id || i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                          <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                            {log.createdAt ? new Date(parseFloat(log.createdAt) * 1000).toLocaleString() : '-'}
                          </td>
                          <td style={tdStyle}>{log.callerName || log.fromNumber || '-'}</td>
                          <td style={tdStyle}>{log.eventType || '-'}</td>
                          <td style={tdStyle}>
                            <span style={badge(log.status === 'connected' ? 'active' : log.status === 'ringing' ? 'planned' : 'default')}>
                              {log.status || '-'}
                            </span>
                          </td>
                          <td style={tdStyle}>{log.duration ? `${log.duration}s` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div>
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0' }}>
              <h3 style={{ margin: '0 0 8px', fontSize: '15px', color: '#065f46' }}>How it works</h3>
              <p style={{ margin: 0, fontSize: '13px', color: '#047857', lineHeight: 1.6 }}>
                The WhatsApp Business Calling API (launched July 2025) enables bidirectional VoIP calls
                within WhatsApp conversation threads. Default signaling uses Graph APIs + HTTPS webhooks.
                SIP signaling is available with explicit enablement. Media uses WebRTC with OPUS codec
                (G.711 coming soon). Calls appear in the same chat thread as messages.
              </p>
            </div>

            {/* Signaling Configurations Table */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Signaling & Media Configurations</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                      <th style={thStyle}>Configuration</th>
                      <th style={thStyle}>Signaling</th>
                      <th style={thStyle}>Transport</th>
                      <th style={thStyle}>Media</th>
                      <th style={thStyle}>Codec</th>
                    </tr>
                  </thead>
                  <tbody>
                    {SIGNAL_CONFIGS.map((c, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ ...tdStyle, fontWeight: 500, color: '#111827' }}>{c.config}</td>
                        <td style={tdStyle}>{c.signaling}</td>
                        <td style={tdStyle}>{c.transport}</td>
                        <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '11px' }}>{c.media}</td>
                        <td style={tdStyle}>{c.codec}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ margin: '8px 0 0', fontSize: '11px', color: '#9ca3af' }}>
                Note: You can use SDES instead of ICE+DTLS with Graph API + Webhook signaling too.
              </p>
            </div>

            {/* Call Flow Diagram */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#111827' }}>Call Flow (User-Initiated)</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
                {[
                  { icon: '📱', label: 'User calls', desc: 'User taps call icon in WhatsApp' },
                  { icon: '🔔', label: 'Webhook: connect', desc: 'Meta sends call event + SDP offer' },
                  { icon: '✅', label: 'Pre-accept → Accept', desc: 'Business responds with SDP answer' },
                  { icon: '🎙', label: 'WebRTC call', desc: 'Audio via OPUS codec' },
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

            {/* Availability */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 8px', fontSize: '14px', color: '#111827' }}>Availability</h4>
              <div style={{ fontSize: '13px', color: '#6b7280', lineHeight: 1.6 }}>
                <p style={{ margin: '0 0 8px' }}>
                  <span style={{ fontWeight: 500, color: '#065f46' }}>User-initiated calling:</span> Available everywhere Cloud API is available.
                </p>
                <p style={{ margin: '0 0 8px' }}>
                  <span style={{ fontWeight: 500, color: '#065f46' }}>Business-initiated calling:</span> Available everywhere Cloud API is available, except:
                </p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {BLOCKED_COUNTRIES.map((c, i) => (
                    <span key={i} style={{ padding: '2px 10px', background: '#fef2f2', color: '#991b1b', borderRadius: '12px', fontSize: '11px', fontWeight: 500, border: '1px solid #fecaca' }}>{c}</span>
                  ))}
                </div>
                <p style={{ margin: '8px 0 0', fontSize: '12px', color: '#9ca3af' }}>
                  The business phone number's country code must be in the supported list. Consumer phone can be from any Cloud API country.
                  Our numbers (+91) are eligible for both user-initiated and business-initiated calling.
                </p>
              </div>
            </div>

            {/* Phone Numbers */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>WABA Phone Numbers</h4>
              {PHONE_NUMBERS.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0', borderBottom: i < PHONE_NUMBERS.length - 1 ? '1px solid #f3f4f6' : 'none', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>{p.display}</span>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>{p.name}</span>
                  <span style={badge('available')}>{p.country}</span>
                  <span style={{ ...badge(p.quality === 'GREEN' ? 'active' : 'planned'), fontSize: '10px' }}>Quality: {p.quality}</span>
                  <span style={{ ...badge(p.tier === 'TIER_10K' || p.tier === 'TIER_UNLIMITED' ? 'active' : 'planned'), fontSize: '10px' }}>Tier: {p.tier}</span>
                  <span style={{ ...badge(p.callingReady ? 'active' : 'planned'), fontSize: '10px' }}>{p.callingReady ? 'Calling Ready' : 'Needs 2K Tier'}</span>
                  <code style={{ fontSize: '10px', color: '#9ca3af', marginLeft: 'auto', wordBreak: 'break-all' }}>Meta: {p.metaId}</code>
                </div>
              ))}
            </div>

            {/* Changelog */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Changelog (Meta)</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                      <th style={{ ...thStyle, width: '110px' }}>Date</th>
                      <th style={thStyle}>Update</th>
                      <th style={thStyle}>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CHANGELOG.map((c, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap', fontWeight: 500, color: '#374151' }}>{c.date}</td>
                        <td style={{ ...tdStyle, fontWeight: 500, color: '#111827' }}>{c.title}</td>
                        <td style={tdStyle}>{c.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Docs */}
            <div style={{ ...s.card, marginTop: '16px' }}>
              <h4 style={{ margin: '0 0 8px', fontSize: '14px', color: '#111827' }}>Documentation</h4>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Meta Calling API', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling' },
                  { label: 'Getting Started (Access Token)', url: 'https://developers.facebook.com/docs/business-messaging/whatsapp/get-started' },
                  { label: 'Webhooks Overview', url: 'https://developers.facebook.com/docs/business-messaging/whatsapp/webhooks/overview' },
                  { label: 'User-Initiated Calls', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/receive-calls' },
                  { label: 'Business-Initiated Calls', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/place-calls' },
                  { label: 'Call Control Settings', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/call-control' },
                  { label: 'SIP Integration', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/sip' },
                  { label: 'Asterisk Guide', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/asterisk' },
                  { label: 'Sandbox Testing', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling/sandbox' },
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

        {/* WEBHOOK CONFIG TAB */}
        {activeTab === 'webhook' && (
          <div>
            {/* Webhook Status */}
            <div style={{ ...s.card, background: '#f0fdf4', border: '1px solid #a7f3d0', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '18px' }}>🔗</span>
                <h3 style={{ margin: 0, fontSize: '15px', color: '#065f46' }}>Webhook Endpoint — Deployed & Verified</h3>
                <span style={badge('active')}>live</span>
              </div>
              <p style={{ margin: 0, fontSize: '13px', color: '#047857', lineHeight: 1.6 }}>
                Lambda <code style={{ background: '#d1fae5', padding: '1px 6px', borderRadius: '4px', fontSize: '12px' }}>wecare-whatsapp-calling</code> handles
                webhook verification (GET hub.challenge) and call events (POST connect/terminate/permission).
                Logs stored in DynamoDB <code style={{ background: '#d1fae5', padding: '1px 6px', borderRadius: '4px', fontSize: '12px' }}>WhatsAppCallingTable</code>.
              </p>
            </div>

            {/* Callback URL + Verify Token */}
            <div style={s.card}>
              <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#111827' }}>Meta Dashboard Configuration</h4>
              <p style={{ margin: '0 0 12px', fontSize: '12px', color: '#6b7280' }}>
                Enter these values in <a href="https://developers.facebook.com/apps/1623342242027107/whatsapp-business/wa-dev-console/" target="_blank" rel="noopener noreferrer" style={{ color: '#10b981' }}>Meta App Dashboard → WhatsApp → Configuration</a>
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}>Callback URL</label>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <code style={{ flex: 1, background: '#1e293b', color: '#e2e8f0', padding: '10px 14px', borderRadius: '8px', fontSize: '12px', wordBreak: 'break-all' }}>
                      {WEBHOOK_CONFIG.callbackUrl}
                    </code>
                    <button onClick={() => { navigator.clipboard.writeText(WEBHOOK_CONFIG.callbackUrl); toast.success('Copied'); }}
                      style={{ padding: '8px 14px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      Copy
                    </button>
                  </div>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}>Verify Token</label>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <code style={{ flex: 1, background: '#1e293b', color: '#e2e8f0', padding: '10px 14px', borderRadius: '8px', fontSize: '12px' }}>
                      {WEBHOOK_CONFIG.verifyToken}
                    </code>
                    <button onClick={() => { navigator.clipboard.writeText(WEBHOOK_CONFIG.verifyToken); toast.success('Copied'); }}
                      style={{ padding: '8px 14px', background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      Copy
                    </button>
                  </div>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#374151', marginBottom: '4px' }}>Webhook Fields to Subscribe</label>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {['calls', 'messages', 'message_template_status_update', 'account_update'].map((field, i) => (
                      <span key={i} style={{
                        padding: '4px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 500,
                        background: field === 'calls' ? '#ecfdf5' : '#f3f4f6',
                        color: field === 'calls' ? '#065f46' : '#6b7280',
                        border: `1px solid ${field === 'calls' ? '#a7f3d0' : '#e5e7eb'}`,
                      }}>
                        {field} {field === 'calls' && '← required for calling'}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Meta Access Token Info */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Meta Access Token</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <tbody>
                    {[
                      { label: 'App ID', value: META_TOKEN.appId },
                      { label: 'Secrets Manager', value: META_TOKEN.secretName },
                      { label: 'Token Type', value: META_TOKEN.tokenType },
                      { label: 'Status', value: META_TOKEN.status },
                      { label: 'Scopes', value: META_TOKEN.scopes.join(', ') },
                      { label: 'WABA Access', value: META_TOKEN.wabaAccess.join(', ') },
                    ].map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 500, color: '#374151', whiteSpace: 'nowrap', width: '140px' }}>{row.label}</td>
                        <td style={{ padding: '8px 12px', color: '#6b7280', fontFamily: 'monospace', fontSize: '12px' }}>{row.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Step-by-step: How to configure in Meta Dashboard */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 12px', fontSize: '14px', color: '#111827' }}>How to Configure Webhook in Meta Dashboard</h4>
              <ol style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#374151', lineHeight: 1.8 }}>
                <li>Go to <a href="https://developers.facebook.com/apps/1623342242027107/whatsapp-business/wa-dev-console/" target="_blank" rel="noopener noreferrer" style={{ color: '#10b981' }}>developers.facebook.com → Your App → WhatsApp → Configuration</a></li>
                <li>Under "Webhook", click "Edit" (or "Configure" if first time)</li>
                <li>Paste the Callback URL above</li>
                <li>Paste the Verify Token above</li>
                <li>Click "Verify and Save" — Meta will send a GET request with hub.challenge, our Lambda responds correctly</li>
                <li>After verification, click "Manage" next to Webhook fields</li>
                <li>Subscribe to: <strong>calls</strong> (required), optionally messages, account_update</li>
                <li>Important: If app is unpublished, only test webhooks from dashboard will work. Publish the app for production data.</li>
              </ol>
            </div>

            {/* Phone Number Readiness */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Phone Number Calling Readiness</h4>
              {PHONE_NUMBERS.map((p, i) => (
                <div key={i} style={{ padding: '10px 0', borderBottom: i < PHONE_NUMBERS.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: '14px', color: '#111827' }}>{p.display}</span>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>{p.name}</span>
                    <span style={badge(p.callingReady ? 'active' : 'planned')}>{p.callingReady ? '✓ Ready' : '⚠ Not Ready'}</span>
                  </div>
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#6b7280' }}>
                    Tier: <strong>{p.tier}</strong> | Quality: <strong>{p.quality}</strong> | Meta ID: <code style={{ fontSize: '11px' }}>{p.metaId}</code>
                    {!p.callingReady && <span style={{ color: '#dc2626', marginLeft: '8px' }}>Needs TIER_2K+ (currently {p.tier})</span>}
                  </div>
                </div>
              ))}
            </div>

            {/* Documentation Links */}
            <div style={{ ...s.card, marginTop: '12px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '14px', color: '#111827' }}>Documentation</h4>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Getting Started (Access Token)', url: 'https://developers.facebook.com/docs/business-messaging/whatsapp/get-started' },
                  { label: 'Webhooks Overview', url: 'https://developers.facebook.com/docs/business-messaging/whatsapp/webhooks/overview' },
                  { label: 'Calling API Docs', url: 'https://developers.facebook.com/docs/whatsapp/cloud-api/calling' },
                  { label: 'App Dashboard', url: 'https://developers.facebook.com/apps/1623342242027107/whatsapp-business/wa-dev-console/' },
                  { label: 'Meta Business Settings', url: 'https://business.facebook.com/settings' },
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
                Follow these steps to enable WhatsApp Business Calling. Default: Graph API + Webhooks (HTTPS) signaling with WebRTC media. SIP available with explicit enablement.
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

            {/* Sandbox Testing Info */}
            <div style={{ ...s.card, marginTop: '8px', background: '#fffbeb', border: '1px solid #fde68a' }}>
              <h4 style={{ margin: '0 0 8px', fontSize: '14px', color: '#92400e' }}>Sandbox Testing</h4>
              <p style={{ margin: '0 0 8px', fontSize: '13px', color: '#78350f', lineHeight: 1.5 }}>
                Sandbox accounts (Tech Partners only) and public test numbers have relaxed limits for integration testing.
                No 2,000 messaging limit requirement for test numbers.
              </p>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid #fde68a' }}>
                      <td style={{ padding: '6px 10px', fontWeight: 500, color: '#78350f' }}>Permission requests</td>
                      <td style={{ padding: '6px 10px', color: '#92400e', fontFamily: 'monospace' }}>25/day, 100/week (vs 1/day, 2/week prod)</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid #fde68a' }}>
                      <td style={{ padding: '6px 10px', fontWeight: 500, color: '#78350f' }}>Unanswered → warning</td>
                      <td style={{ padding: '6px 10px', color: '#92400e', fontFamily: 'monospace' }}>5 consecutive (vs 2 prod)</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '6px 10px', fontWeight: 500, color: '#78350f' }}>Unanswered → revoke</td>
                      <td style={{ padding: '6px 10px', color: '#92400e', fontFamily: 'monospace' }}>10 consecutive (vs 4 prod)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
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
