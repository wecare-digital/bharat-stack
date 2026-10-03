import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authFetch } from '../api/client';
import { metaAuthorizationURL, workspaceMCP } from './workspace-mcp';
vi.mock('../api/client', () => ({ authFetch: vi.fn() }));
const fetchMock = vi.mocked(authFetch);
beforeEach(() => vi.clearAllMocks());
describe('workspace MCP transport', () => {
  it('uses the protected same-origin endpoint and JSON-RPC tool call', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ result: { content: [{ type: 'text', text: '{"connections":[]}' }], isError: false } })));
    expect(await workspaceMCP('connections_list')).toEqual({ connections: [] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/workspace/mcp');
    expect(JSON.parse(init!.body as string).params).toEqual({ name: 'connections_list', arguments: {} });
  });
  it('rejects unauthorized sessions without rendering a success', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 401 }));
    await expect(workspaceMCP('aws_status')).rejects.toThrow('staff Admin');
  });
  it('treats a provider refusal inside HTTP 200 as a failure', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ result: { content: [{ type: 'text', text: 'Provider OAuth consent required' }], isError: true } })));
    await expect(workspaceMCP('connection_verify', { provider: 'whatsapp' })).rejects.toThrow('consent required');
  });
  it('refuses redirects outside the registered Meta app and callback', () => {
    const params = new URLSearchParams({ client_id: '2238810740192680', redirect_uri: 'https://wecare.digital/api/workspace/mcp/oauth/callback', code_challenge_method: 'S256', scope: 'ads_read business_management ads_mcp_management' });
    const url = `https://www.facebook.com/v26.0/dialog/oauth?${params}`;
    expect(metaAuthorizationURL(url)).toBe(url);
    expect(() => metaAuthorizationURL(url.replace('www.facebook.com', 'facebook.com.attacker.example'))).toThrow();
    const google = new URL('https://accounts.google.com/o/oauth2/v2/auth');
    google.search = new URLSearchParams({client_id: '756034744787-occ06h9v22rh0kbm83mmedpfqqqfni44.apps.googleusercontent.com', redirect_uri: 'https://wecare.digital/api/workspace/mcp/oauth/callback', code_challenge_method: 'S256', scope: 'https://www.googleapis.com/auth/adwords'}).toString();
    expect(metaAuthorizationURL(google.href)).toBe(google.href);
    expect(() => metaAuthorizationURL(google.href.replace('756034744787-', 'another-'))).toThrow();
    expect(() => metaAuthorizationURL('javascript:alert(1)')).toThrow();
  });
  it('accepts a Login for Business config_id in place of scope, and still requires one of them', () => {
    const base = { client_id: '2238810740192680', redirect_uri: 'https://wecare.digital/api/workspace/mcp/oauth/callback', code_challenge_method: 'S256' };
    const dialog = (extra: Record<string, string>) => `https://www.facebook.com/v26.0/dialog/oauth?${new URLSearchParams({ ...base, ...extra })}`;
    const configured = dialog({ config_id: 'test-login-config-123' });
    expect(metaAuthorizationURL(configured)).toBe(configured);
    const scoped = dialog({ scope: 'ads_read ads_mcp_management' });
    expect(metaAuthorizationURL(scoped)).toBe(scoped);
    expect(() => metaAuthorizationURL(dialog({}))).toThrow();
    expect(() => metaAuthorizationURL(dialog({ config_id: 'test-login-config-123', redirect_uri: 'https://attacker.example/callback' }))).toThrow();
    expect(() => metaAuthorizationURL(dialog({ config_id: 'test-login-config-123', code_challenge_method: 'plain' }))).toThrow();
  });
});
