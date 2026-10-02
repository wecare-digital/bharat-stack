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
    const params = new URLSearchParams({ client_id: '2238810740192680', redirect_uri: 'https://wecare.digital/api/workspace/mcp/oauth/callback', code_challenge_method: 'S256' });
    const url = `https://www.facebook.com/v26.0/dialog/oauth?${params}`;
    expect(metaAuthorizationURL(url)).toBe(url);
    expect(() => metaAuthorizationURL(url.replace('www.facebook.com', 'facebook.com.attacker.example'))).toThrow();
    expect(() => metaAuthorizationURL(url.replace('2238810740192680', 'another-app'))).toThrow();
    expect(() => metaAuthorizationURL('javascript:alert(1)')).toThrow();
  });
});
