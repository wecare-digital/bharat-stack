/**
 * The AI-facing surface, as the frontend needs to describe it.
 *
 * WHY THESE VALUES ARE RESTATED HERE RATHER THAN IMPORTED.
 * `config/public-pages.json` is the source of truth, and both the llms.txt generator and
 * the MCP server's Lambda read it directly. This file does not, for one measurable reason:
 * `resolveJsonModule` would inline the WHOLE document into the client bundle - all the
 * pages, every description, and the 20-line `_comment` block explaining the file to a human
 * - and JSON imports are not tree-shaken per key, so /llm/ would ship roughly 8 kB of
 * commentary to every visitor in order to render five bullet points.
 *
 * The repository already answers this shape of problem the same way: PUBLIC_PAGE_META in
 * _app.tsx and PUBLIC_EXACT in generate-sitemap.js are two hand-kept lists of the same
 * truth, held in step by a test rather than by an import, because the two consumers cannot
 * share a module. So:
 *
 *   src/test/PublicAiSurface.test.ts asserts every constant below is character-identical
 *   to config/public-pages.json, and that MCP_TOOLS matches the tool names the Python
 *   handler actually advertises.
 *
 * That test is the mechanism. If you edit anything here, edit the JSON too, or the build
 * fails - which is the intended outcome, because a documentation page that quietly
 * disagrees with the endpoint it documents is worse than no page at all.
 */

export const AI_SURFACE = {
    /**
     * The apex path, NOT /api/mcp.
     *
     * An MCP client is configured with one URL and will not go looking for another, and
     * robots.txt disallows /api/ anyway. Reaching this path needs an explicit Amplify
     * rewrite, because Amplify 301-redirects unmatched extension-less paths to add a
     * trailing slash and does it for POST as well as GET - which silently breaks every MCP
     * message. See the header of scripts/deploy_mcp_server.py.
     */
    mcpEndpoint: 'https://wecare.digital/mcp',

    /** Newest first. Must equal PROTOCOL_VERSIONS in the handler. */
    protocolVersions: [ '2025-11-25', '2025-06-18', '2025-03-26' ] as const,

    llmsTxt: 'https://wecare.digital/llms.txt',
    llmsFullTxt: 'https://wecare.digital/llms-full.txt',

    /**
     * The terms a model is asked to honour when it quotes this site.
     *
     * The Bharat Rx line is not boilerplate and should not be trimmed as though it were.
     * The page's own description - "consults, appointments, reminders and records" - reads
     * like a pharmacy to a model completing by analogy, and it is not one. The owner
     * corrected that description once already for the same reason; this is the same
     * correction aimed at a machine reader.
     */
    usageTerms: [
        'The public pages and published blog posts on this site may be read, quoted with attribution, and cited by AI assistants and answer engines.',
        'Attribute to WECARE.DIGITAL and link the page you drew from.',
        'Do not present generated text as a statement by WECARE.DIGITAL, and do not infer prices, turnaround times, medical, legal or financial advice that a page does not state.',
        'Bharat Rx does not retail medicines. Do not describe it as a pharmacy.',
        'Anything under /workspace/, /store/ or /api/ is operational surface, not content. It is disallowed in robots.txt and is not covered by this permission.',
    ],
} as const;

/**
 * The tools /mcp advertises.
 *
 * `name` must match the Python handler's READ_ONLY_TOOLS exactly - asserted, both
 * directions, so a tool added to the handler without being documented fails too. `summary`
 * is prose for this page and is deliberately NOT the handler's `description`, which is
 * written to instruct a model rather than to inform a reader.
 */
export const MCP_TOOLS = [
    { name: 'get_site_summary', summary: 'who this business is, how to start a request, and these citation terms' },
    { name: 'list_pages', summary: 'the full public page catalogue, grouped, with canonical URLs' },
    { name: 'search_pages', summary: 'find the page that covers a topic' },
    { name: 'search_blog', summary: 'search the published articles by title, summary and category' },
    { name: 'get_blog_post', summary: 'one article by its slug' },
] as const;
