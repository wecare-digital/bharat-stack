import { authFetch } from '../api/client';

export interface MCPConnection {
  provider: string;
  kind: string;
  status: string;
  lastVerifiedAt?: number | null;
}

export async function workspaceMCP<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
  const response = await authFetch('/api/workspace/mcp', {
    method: 'POST',
    headers: { 'MCP-Protocol-Version': '2025-11-25' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } }),
    signal: AbortSignal.timeout(30000),
  });
  if (response.status === 401 || response.status === 403) throw new Error('Sign in with a staff Admin account to manage connections.');
  if (!response.ok) throw new Error('Connection service unavailable. Please try again.');
  const message = await response.json();
  if (message.error) throw new Error('The connection check could not complete. Please try again.');
  const text = message.result?.content?.find((item: { type: string }) => item.type === 'text')?.text;
  if (typeof text !== 'string') throw new Error('The connection service returned an invalid response.');
  if (message.result?.isError) throw new Error(text);
  return JSON.parse(text) as T;
}

export function metaAuthorizationURL(value: string): string {
  const url = new URL(value);
  if (url.origin !== 'https://www.facebook.com' || url.pathname !== '/v26.0/dialog/oauth'
    || url.searchParams.get('client_id') !== '2238810740192680'
    || url.searchParams.get('redirect_uri') !== 'https://wecare.digital/api/workspace/mcp/oauth/callback'
    || url.searchParams.get('code_challenge_method') !== 'S256') {
    throw new Error('The authorization link could not be verified.');
  }
  return url.href;
}
