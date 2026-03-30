/**
 * WebRTC Calling Hook for WhatsApp Business Calling API
 *
 * Handles the full WebRTC lifecycle:
 * - Inbound: receive SDP offer from Meta → create answer → send back
 * - Outbound: create SDP offer → send to Meta → receive answer
 * - Media: microphone capture, remote audio playback, mute/unmute
 * - Polling: active call detection from backend
 *
 * SDP Exchange Flow (Inbound):
 *   Meta webhook → Lambda stores sdpOffer → frontend polls /active →
 *   RTCPeerConnection.setRemoteDescription(offer) → createAnswer() →
 *   POST /accept { callId, phoneNumberId, sdpAnswer } → Lambda → Meta Graph API
 *
 * SDP Exchange Flow (Outbound):
 *   RTCPeerConnection.createOffer() → POST /outbound { action: 'create', sdpOffer } →
 *   Lambda → Meta Graph API → Meta sends SDP answer via webhook →
 *   Lambda stores sdpAnswer → frontend polls → setRemoteDescription(answer)
 */

import { useState, useRef, useCallback, useEffect } from 'react';

const API_BASE = 'https://api.wecare.digital';

export type CallStatus =
  | 'idle'
  | 'ringing'
  | 'connecting'
  | 'connected'
  | 'ended'
  | 'failed'
  | 'rejected';

export interface ActiveCall {
  callId: string;
  phoneNumberId: string;
  fromNumber: string;
  toNumber?: string;
  callerName?: string;
  displayPhone?: string;
  direction: string;
  status: string;
  sdpOffer?: string;
  eventType?: string;
  timestamp?: string;
  createdAt?: number;
}

export interface CallLog {
  id: string;
  callId: string;
  fromNumber: string;
  callerName?: string;
  eventType: string;
  status: string;
  duration?: number;
  createdAt: number;
}

interface UseWebRTCCallingOptions {
  /** Poll interval in ms for active calls (default: 5000) */
  pollInterval?: number;
  /** Enable polling (default: false, enable on Live tab) */
  enablePolling?: boolean;
  /** STUN/TURN servers (Meta handles relay, STUN is for candidate gathering) */
  iceServers?: RTCIceServer[];
  /** Callback when call state changes */
  onCallStateChange?: (status: CallStatus, call?: ActiveCall) => void;
  /** Callback when remote audio starts */
  onRemoteAudioStart?: () => void;
}

export function useWebRTCCalling(options: UseWebRTCCallingOptions = {}) {
  const {
    pollInterval = 5000,
    enablePolling = false,
    iceServers = [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' },
    ],
    onCallStateChange,
    onRemoteAudioStart,
  } = options;

  // ─── State ──────────────────────────────────────────────────────
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [currentCall, setCurrentCall] = useState<ActiveCall | null>(null);
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // ─── Refs ───────────────────────────────────────────────────────
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const durationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Helpers ────────────────────────────────────────────────────

  const updateStatus = useCallback((status: CallStatus, call?: ActiveCall) => {
    setCallStatus(status);
    onCallStateChange?.(status, call);
  }, [onCallStateChange]);

  /** Attach the remote audio element (call from component with ref to <audio>) */
  const setRemoteAudioElement = useCallback((el: HTMLAudioElement | null) => {
    remoteAudioRef.current = el;
  }, []);

  /** Start call duration timer */
  const startDurationTimer = useCallback(() => {
    setCallDuration(0);
    durationTimerRef.current = setInterval(() => {
      setCallDuration(prev => prev + 1);
    }, 1000);
  }, []);

  /** Stop call duration timer */
  const stopDurationTimer = useCallback(() => {
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
  }, []);

  // ─── WebRTC Lifecycle ───────────────────────────────────────────

  /** Create a new RTCPeerConnection with event handlers */
  const createPeerConnection = useCallback((): RTCPeerConnection => {
    const pc = new RTCPeerConnection({ iceServers });

    pc.ontrack = (event) => {
      if (remoteAudioRef.current && event.streams[0]) {
        remoteAudioRef.current.srcObject = event.streams[0];
        remoteAudioRef.current.play().catch(() => {});
        onRemoteAudioStart?.();
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('[WebRTC] ICE candidate:', event.candidate.candidate.substring(0, 60));
      }
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      console.log('[WebRTC] Connection state:', state);
      if (state === 'connected') {
        updateStatus('connected', currentCall ?? undefined);
        startDurationTimer();
      } else if (state === 'failed') {
        setError('WebRTC connection failed');
        updateStatus('failed', currentCall ?? undefined);
        cleanup();
      } else if (state === 'disconnected') {
        // Might recover, but if it doesn't, cleanup after a timeout
        setTimeout(() => {
          if (pcRef.current?.connectionState === 'disconnected') {
            cleanup();
            updateStatus('ended', currentCall ?? undefined);
          }
        }, 5000);
      }
    };

    pc.oniceconnectionstatechange = () => {
      console.log('[WebRTC] ICE state:', pc.iceConnectionState);
    };

    pcRef.current = pc;
    return pc;
  }, [iceServers, currentCall, onRemoteAudioStart, updateStatus, startDurationTimer]);

  /** Get microphone stream and add tracks to peer connection */
  const acquireMicrophone = useCallback(async (pc: RTCPeerConnection): Promise<MediaStream> => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    localStreamRef.current = stream;
    stream.getTracks().forEach(track => pc.addTrack(track, stream));
    return stream;
  }, []);

  /** Wait for ICE gathering to complete (or timeout) */
  const waitForICEGathering = useCallback((pc: RTCPeerConnection, timeoutMs = 3000): Promise<string> => {
    return new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') {
        resolve(pc.localDescription?.sdp || '');
        return;
      }
      const timeout = setTimeout(() => {
        resolve(pc.localDescription?.sdp || '');
      }, timeoutMs);

      pc.onicegatheringstatechange = () => {
        if (pc.iceGatheringState === 'complete') {
          clearTimeout(timeout);
          resolve(pc.localDescription?.sdp || '');
        }
      };
    });
  }, []);

  /** Cleanup all WebRTC resources */
  const cleanup = useCallback(() => {
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(t => t.stop());
      localStreamRef.current = null;
    }
    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
    }
    stopDurationTimer();
    setIsMuted(false);
  }, [stopDurationTimer]);

  // ─── Inbound Call: Answer with WebRTC ─────────────────────────

  /**
   * Answer an inbound call using browser WebRTC.
   *
   * SDP Exchange:
   * 1. Meta sent SDP offer via webhook → stored in DynamoDB
   * 2. We set it as remoteDescription on RTCPeerConnection
   * 3. createAnswer() generates our SDP answer
   * 4. Wait for ICE candidates to be gathered
   * 5. POST /accept sends { callId, phoneNumberId, sdpAnswer } to Lambda
   * 6. Lambda calls Meta Graph API: POST /{phoneNumberId}/calls { action: pre_accept }
   *    then POST /{phoneNumberId}/calls { action: accept, sdp_answer: ... }
   * 7. Meta bridges the WebRTC session — audio flows
   */
  const answerCall = useCallback(async (call: ActiveCall): Promise<boolean> => {
    setError(null);
    setCurrentCall(call);

    // If no SDP offer, fall back to server-side accept (auto-pickup style)
    if (!call.sdpOffer) {
      updateStatus('connecting', call);
      try {
        const res = await fetch(`${API_BASE}/whatsapp-calling/accept`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            callId: call.callId,
            phoneNumberId: call.phoneNumberId,
            sdpAnswer: '',
          }),
        });
        const data = await res.json();
        if (data.success) {
          updateStatus('connected', call);
          startDurationTimer();
          return true;
        }
        setError(data.error?.detail || 'Server-side accept failed');
        updateStatus('failed', call);
        return false;
      } catch (e: any) {
        setError(e.message);
        updateStatus('failed', call);
        return false;
      }
    }

    try {
      updateStatus('connecting', call);

      // 1. Create peer connection
      const pc = createPeerConnection();

      // 2. Get microphone
      await acquireMicrophone(pc);

      // 3. Set Meta's SDP offer as remote description
      await pc.setRemoteDescription(
        new RTCSessionDescription({ type: 'offer', sdp: call.sdpOffer })
      );

      // 4. Create SDP answer
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // 5. Wait for ICE gathering
      const sdpAnswer = await waitForICEGathering(pc);

      if (!sdpAnswer) {
        throw new Error('Failed to generate SDP answer');
      }

      console.log('[WebRTC] SDP answer generated, length:', sdpAnswer.length);

      // 6. Send to backend → Meta
      const res = await fetch(`${API_BASE}/whatsapp-calling/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          callId: call.callId,
          phoneNumberId: call.phoneNumberId,
          sdpAnswer,
        }),
      });
      const data = await res.json();

      if (!data.success) {
        throw new Error(
          `Accept failed at ${data.step || 'unknown'}: ${JSON.stringify(data.error || {})}`
        );
      }

      // Connection state handler will set 'connected' when WebRTC connects
      return true;
    } catch (e: any) {
      console.error('[WebRTC] Answer error:', e);
      setError(e.message);
      updateStatus('failed', call);
      cleanup();
      return false;
    }
  }, [createPeerConnection, acquireMicrophone, waitForICEGathering, cleanup, updateStatus, startDurationTimer]);

  // ─── Outbound Call: Create with WebRTC ────────────────────────

  /**
   * Initiate an outbound call.
   *
   * Two-step process:
   * Step A: Send call permission request (interactive message)
   *   POST /outbound { action: 'permission_request', phoneNumberId, to, bodyText }
   *   User sees "Can we call you?" in WhatsApp → taps Allow
   *   Meta sends call_permission_response webhook → Lambda logs it
   *
   * Step B: After permission granted, create the call with SDP offer
   *   1. Create RTCPeerConnection + get microphone
   *   2. createOffer() → setLocalDescription
   *   3. Wait for ICE gathering
   *   4. POST /outbound { action: 'create', phoneNumberId, to, sdpOffer }
   *   5. Lambda → Meta Graph API: POST /{phoneNumberId}/calls { action: create, to, sdp_offer }
   *   6. User's WhatsApp rings → they pick up → Meta sends connect webhook with SDP answer
   *   7. Frontend polls /active → gets the SDP answer → setRemoteDescription
   */
  const requestCallPermission = useCallback(async (
    phoneNumberId: string,
    toNumber: string,
    bodyText = 'Can we call you to discuss your query?'
  ): Promise<boolean> => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/outbound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phoneNumberId,
          to: toNumber,
          action: 'permission_request',
          bodyText,
        }),
      });
      const data = await res.json();
      return data.success === true;
    } catch (e: any) {
      setError(e.message);
      return false;
    }
  }, []);

  const initiateOutboundCall = useCallback(async (
    phoneNumberId: string,
    toNumber: string
  ): Promise<boolean> => {
    setError(null);

    try {
      updateStatus('connecting');

      // 1. Create peer connection + microphone
      const pc = createPeerConnection();
      await acquireMicrophone(pc);

      // 2. Create SDP offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // 3. Wait for ICE gathering
      const sdpOffer = await waitForICEGathering(pc);

      if (!sdpOffer) {
        throw new Error('Failed to generate SDP offer');
      }

      console.log('[WebRTC] Outbound SDP offer generated, length:', sdpOffer.length);

      // 4. Send to backend → Meta
      const res = await fetch(`${API_BASE}/whatsapp-calling/outbound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phoneNumberId,
          to: toNumber,
          action: 'create',
          sdpOffer,
        }),
      });
      const data = await res.json();

      if (!data.success) {
        throw new Error(JSON.stringify(data.error || data));
      }

      setCurrentCall({
        callId: data.result?.call_id || '',
        phoneNumberId,
        fromNumber: phoneNumberId,
        toNumber,
        direction: 'BUSINESS_INITIATED',
        status: 'ringing',
      });

      updateStatus('ringing');
      return true;
    } catch (e: any) {
      console.error('[WebRTC] Outbound call error:', e);
      setError(e.message);
      updateStatus('failed');
      cleanup();
      return false;
    }
  }, [createPeerConnection, acquireMicrophone, waitForICEGathering, cleanup, updateStatus]);

  // ─── Call Control ──────────────────────────────────────────────

  /** Reject a ringing call */
  const rejectCall = useCallback(async (callId: string, phoneNumberId: string): Promise<boolean> => {
    try {
      await fetch(`${API_BASE}/whatsapp-calling/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callId, phoneNumberId }),
      });
      if (currentCall?.callId === callId) {
        updateStatus('rejected', currentCall);
        setCurrentCall(null);
        cleanup();
      }
      return true;
    } catch (e: any) {
      setError(e.message);
      return false;
    }
  }, [currentCall, cleanup, updateStatus]);

  /** Hang up an active call */
  const hangup = useCallback(async (): Promise<boolean> => {
    if (!currentCall) return false;
    try {
      await fetch(`${API_BASE}/whatsapp-calling/hangup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          callId: currentCall.callId,
          phoneNumberId: currentCall.phoneNumberId,
        }),
      });
      updateStatus('ended', currentCall);
      setCurrentCall(null);
      cleanup();
      return true;
    } catch (e: any) {
      setError(e.message);
      cleanup();
      return false;
    }
  }, [currentCall, cleanup, updateStatus]);

  /** Toggle microphone mute */
  const toggleMute = useCallback(() => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  }, []);

  // ─── Polling & Data Fetching ──────────────────────────────────

  /** Fetch active/ringing calls from backend */
  const fetchActiveCalls = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/active`);
      if (res.ok) {
        const data = await res.json();
        setActiveCalls(data.calls || []);
      }
    } catch (e) {
      console.error('[WebRTC] Poll active calls error:', e);
    }
  }, []);

  /** Fetch call logs */
  const fetchCallLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/logs`);
      if (res.ok) {
        const data = await res.json();
        setCallLogs(data.logs || []);
      }
    } catch (e) {
      console.error('[WebRTC] Fetch logs error:', e);
    }
    setLoadingLogs(false);
  }, []);

  /** Clear all call logs */
  const clearLogs = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setCallLogs([]);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  // ─── Auto-Pickup Config ───────────────────────────────────────

  const [autoPickup, setAutoPickup] = useState(true);
  const [ivrUrl, setIvrUrl] = useState('https://app.wecare.digital/stream/media/ivr/incoming_welcome.sln16');

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/config`);
      if (res.ok) {
        const data = await res.json();
        setAutoPickup(data.autoPickup !== false);
        if (data.ivrUrl) setIvrUrl(data.ivrUrl);
      }
    } catch (e) {
      console.error('[WebRTC] Config fetch error:', e);
    }
  }, []);

  const updateAutoPickup = useCallback(async (enabled: boolean): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autoPickup: enabled }),
      });
      if (res.ok) {
        setAutoPickup(enabled);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  const updateIvrUrl = useCallback(async (url: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/whatsapp-calling/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ivrUrl: url }),
      });
      if (res.ok) {
        setIvrUrl(url);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  // ─── Effects ──────────────────────────────────────────────────

  // Poll active calls when enabled
  useEffect(() => {
    if (!enablePolling) {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    fetchActiveCalls();
    pollTimerRef.current = setInterval(fetchActiveCalls, pollInterval);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [enablePolling, pollInterval, fetchActiveCalls]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [cleanup]);

  // ─── Browser Capabilities ─────────────────────────────────────

  const isWebRTCSupported = typeof window !== 'undefined' && !!window.RTCPeerConnection;
  const isSecureContext = typeof window !== 'undefined' && window.isSecureContext;

  // ─── Return ───────────────────────────────────────────────────

  return {
    // State
    callStatus,
    currentCall,
    activeCalls,
    callLogs,
    isMuted,
    callDuration,
    error,
    loadingLogs,
    autoPickup,
    ivrUrl,

    // Inbound
    answerCall,

    // Outbound
    requestCallPermission,
    initiateOutboundCall,

    // Call control
    rejectCall,
    hangup,
    toggleMute,
    cleanup,

    // Data fetching
    fetchActiveCalls,
    fetchCallLogs,
    clearLogs,

    // Config
    fetchConfig,
    updateAutoPickup,
    updateIvrUrl,

    // Audio element binding
    setRemoteAudioElement,

    // Capabilities
    isWebRTCSupported,
    isSecureContext,

    // Format helper
    formatDuration: (seconds: number) => {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    },
  };
}

export default useWebRTCCalling;
