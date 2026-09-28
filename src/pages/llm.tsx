/**
 * /llm — what this site offers to AI assistants, and on what terms.
 *
 * WHY A HUMAN-READABLE PAGE FOR A MACHINE INTERFACE.
 * /mcp answers JSON-RPC and /llms.txt is a text file. Neither is somewhere a person can be
 * sent, and three different audiences need to be: an operator wiring a client up and
 * wanting the endpoint URL and a config snippet; anyone auditing what an unauthenticated
 * route on this domain exposes; and a model that has followed the link from llms.txt or
 * robots.txt and wants the citation terms in prose rather than as a JSON array.
 *
 * ROUTING: '/llm' is in the isPublic chain in _app.tsx and NOT in PUBLIC_PAGE_META, which is
 * the '/get' arrangement. Being on that chain is the ONLY thing that makes a page render at
 * all - a route missing from it falls through to the authenticated branch and serves the
 * staff sign-in screen at HTTP 200, which _app.tsx calls "a 404 that does not look like one"
 * and which reached the live site exactly that way once already.
 *
 * Deliberately NOT in PUBLIC_PAGE_META, and therefore not in the sitemap and carrying no
 * WebPage/BreadcrumbList schema: that map is the indexable marketing and content set, and
 * this is a machine-facing reference page. It is still very much discoverable, by the route
 * that actually matters for its audience - robots.txt links it, /llms.txt links it, and the
 * MCP server's own `instructions` string names it. An agent will find it; a search for
 * "customer engagement India" should not.
 *
 * trailingSlash is set, so the canonical URL is /llm/ and the slashless form 301s. That
 * redirect is harmless for a browser page. It is NOT harmless for /mcp, which is why that
 * path needs an explicit Amplify rewrite - see scripts/deploy_mcp_server.py.
 *
 * EVERY FACT ON THIS PAGE IS ALSO ASSERTED SOMEWHERE ELSE. The endpoint URL, the protocol
 * versions and the tool list are checked against the handler by
 * src/test/PublicAiSurface.test.ts and tests/test_mcp_server.py, because a documentation
 * page that drifts from the thing it documents is worse than no page: it sends an operator
 * to an endpoint that answers differently from the description they were given.
 */

import React from 'react';
import Link from 'next/link';
import PageMeta from '../components/PageMeta';
import { AI_SURFACE, MCP_TOOLS } from '../lib/ai-surface';

const LIME = '#d1f470';
const INK = '#1a3a2a';

const panel: React.CSSProperties = {
    border: `2px solid ${INK}`,
    borderRadius: 14,
    padding: '22px 24px',
    background: '#fff',
    marginBottom: 18,
};

const h2: React.CSSProperties = {
    fontSize: 'clamp(28px,3.2vw,40px)',
    fontWeight: 700,
    lineHeight: 1.08,
    letterSpacing: '-1.2px',
    margin: '0 0 14px',
};

const body: React.CSSProperties = {
    fontSize: 20,
    fontWeight: 400,
    lineHeight: 1.4,
    letterSpacing: '-.125px',
    margin: '0 0 14px',
};

const code: React.CSSProperties = {
    display: 'block',
    whiteSpace: 'pre',
    overflowX: 'auto',
    background: INK,
    color: '#eafbd0',
    borderRadius: 10,
    padding: '16px 18px',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: 14,
    lineHeight: 1.55,
    margin: '0 0 14px',
};

/**
 * The client config, built from the same constants the page quotes elsewhere so the snippet
 * cannot drift from the endpoint it configures. `type: "http"` is the Streamable HTTP
 * transport; the older `sse` type would try the deprecated HTTP+SSE transport, which this
 * server does not implement and which would fail at the GET.
 */
const CLIENT_CONFIG = JSON.stringify( {
    mcpServers: {
        'wecare-digital': { type: 'http', url: AI_SURFACE.mcpEndpoint },
    },
}, null, 2 );

const LlmPage: React.FC = () => (
    <>
        <PageMeta
            title="AI access — MCP endpoint and llms.txt | WECARE.DIGITAL"
            description="How AI assistants can read WECARE.DIGITAL: a read-only Model Context Protocol server over Streamable HTTP, llms.txt and llms-full.txt, and the terms for citing this content."
            path="/llm/"
        />
        <main style={ { maxWidth: 880, margin: '0 auto', padding: '48px 20px 80px' } }>
            <p style={ {
                display: 'inline-block', background: LIME, color: INK, fontWeight: 700,
                fontSize: 13, letterSpacing: '.02em', textTransform: 'uppercase',
                borderRadius: 50, padding: '7px 16px', margin: '0 0 18px',
            } }>
                For AI assistants and agents
            </p>

            <h1 style={ { ...h2, fontSize: 'clamp(34px,4.4vw,52px)' } }>
                Read this site properly, without guessing.
            </h1>
            <p style={ body }>
                Everything published on <strong>wecare.digital</strong> is available to AI assistants
                in a machine-readable form. There is a live query interface and there are two static
                index files. Both are read-only, neither needs a credential, and what each one can
                and cannot tell you is set out below.
            </p>

            <section style={ { ...panel, background: '#f7fdee' } }>
                <h2 style={ { ...h2, fontSize: 'clamp(24px,2.6vw,32px)' } }>
                    Model Context Protocol endpoint
                </h2>
                <p style={ body }>
                    <code style={ { fontFamily: 'ui-monospace, monospace', fontSize: 18 } }>
                        { AI_SURFACE.mcpEndpoint }
                    </code>
                </p>
                <p style={ body }>
                    Streamable HTTP transport, stateless, protocol
                    version{ AI_SURFACE.protocolVersions.length > 1 ? 's' : '' }{ ' ' }
                    { AI_SURFACE.protocolVersions.join( ', ' ) }. POST a JSON-RPC message and you get
                    one JSON object back. A GET returns <strong>405</strong> on purpose: this server
                    offers no Server-Sent Events stream, which the specification lists as the
                    explicit alternative to opening one, and it issues no session, so there is
                    nothing to resume or delete.
                </p>
                <p style={ body }>Add it to an MCP client like this:</p>
                <code style={ code }>{ CLIENT_CONFIG }</code>
                <p style={ { ...body, marginBottom: 0 } }>
                    Prefer this over the index files. It searches on demand rather than handing over
                    a snapshot, so it cannot go stale between publishes.
                </p>
            </section>

            <section style={ panel }>
                <h2 style={ { ...h2, fontSize: 'clamp(24px,2.6vw,32px)' } }>What it exposes</h2>
                <p style={ body }>
                    { MCP_TOOLS.length } tools, every one of them a read of content that is already
                    public:
                </p>
                <ul style={ { ...body, paddingLeft: 22 } }>
                    { MCP_TOOLS.map( tool => (
                        <li key={ tool.name } style={ { marginBottom: 8 } }>
                            <code style={ { fontFamily: 'ui-monospace, monospace', fontSize: 17 } }>
                                { tool.name }
                            </code>
                            { ' — ' }{ tool.summary }
                        </li>
                    ) ) }
                </ul>
                <p style={ { ...body, marginBottom: 0 } }>
                    Plus two resources: a site summary and the full page catalogue, both as JSON.
                </p>
            </section>

            <section style={ { ...panel, borderColor: '#b23a48', background: '#fff7f7' } }>
                <h2 style={ { ...h2, fontSize: 'clamp(24px,2.6vw,32px)' } }>What it cannot do</h2>
                <p style={ body }>
                    This is worth stating plainly rather than leaving to inference. The endpoint
                    <strong> cannot act</strong>. It cannot send a WhatsApp message, SMS or email;
                    create, amend or cancel a request; take, capture or refund a payment; or read
                    any contact, order or message record. It reaches nothing behind a sign-in.
                </p>
                <p style={ { ...body, marginBottom: 0 } }>
                    That is not a permission setting that could be changed by mistake — the
                    capability is absent from the code, and the test suite asserts the tool list
                    against a frozen allowlist so a tool with a side effect cannot be added
                    quietly. If you want to <em>do</em> something, a person should use{ ' ' }
                    { /* next/link, because /contact IS a route in this export. The .txt and
                         .xml links further down stay as plain <a>: they are generated files in
                         out/, not Next pages, and Link would try to client-navigate to them. */ }
                    <Link href="/contact/" style={ { color: INK, fontWeight: 700 } }>the contact page</Link>.
                </p>
            </section>

            <section style={ panel }>
                <h2 style={ { ...h2, fontSize: 'clamp(24px,2.6vw,32px)' } }>Index files</h2>
                <ul style={ { ...body, paddingLeft: 22 } }>
                    <li style={ { marginBottom: 8 } }>
                        <a href="/llms.txt" style={ { color: INK, fontWeight: 700 } }>/llms.txt</a>
                        { ' — ' }the curated map: every public page with a one-line description,
                        grouped, following the llmstxt.org convention.
                    </li>
                    <li style={ { marginBottom: 8 } }>
                        <a href="/llms-full.txt" style={ { color: INK, fontWeight: 700 } }>/llms-full.txt</a>
                        { ' — ' }the same plus every published article with its summary. An expanded
                        index, not the body text; fetch the article URL for that.
                    </li>
                    <li style={ { marginBottom: 8 } }>
                        <a href="/sitemap.xml" style={ { color: INK, fontWeight: 700 } }>/sitemap.xml</a>
                        { ' — ' }every indexable URL.
                    </li>
                    <li>
                        <a href="/robots.txt" style={ { color: INK, fontWeight: 700 } }>/robots.txt</a>
                        { ' — ' }the authoritative crawl permissions. The llms.txt files grant
                        nothing; this is the file that does.
                    </li>
                </ul>
                <p style={ { ...body, marginBottom: 0 } }>
                    Both index files are generated at build time from one source, so they describe
                    the site that is actually deployed rather than the site someone last remembered
                    to write down.
                </p>
            </section>

            <section style={ panel }>
                <h2 style={ { ...h2, fontSize: 'clamp(24px,2.6vw,32px)' } }>Citing this content</h2>
                <ul style={ { ...body, paddingLeft: 22, marginBottom: 0 } }>
                    { AI_SURFACE.usageTerms.map( term => (
                        <li key={ term } style={ { marginBottom: 8 } }>{ term }</li>
                    ) ) }
                </ul>
            </section>
        </main>
    </>
);

export default LlmPage;
