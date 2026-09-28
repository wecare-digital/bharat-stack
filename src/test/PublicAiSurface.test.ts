import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { AI_SURFACE, MCP_TOOLS } from '../lib/ai-surface';

/**
 * HOLDS FIVE DESCRIPTIONS OF THE SAME PUBLIC SURFACE IN STEP.
 *
 * The site's public page set is now stated in five places, in four languages, because the
 * consumers cannot share a module: a React allowlist, a Node sitemap generator, a Node
 * llms.txt generator, a Python Lambda, and a TypeScript constants file for the /llm page.
 *
 *   src/pages/_app.tsx                PUBLIC_PAGE_META + the isPublic chain  (render allowlist)
 *   scripts/generate-sitemap.js       PUBLIC_EXACT                           (crawl allowlist)
 *   config/public-pages.json          the catalogue         (llms.txt + the MCP server's zip)
 *   amplify/functions/ai/mcp/  READ_ONLY_TOOLS, PROTOCOL_VERSIONS     (what /mcp serves)
 *   src/lib/ai-surface.ts             what /llm tells a reader /mcp does
 *
 * Every pair can drift, and each drift is silent in its own way:
 *
 *   catalogue has a page _app.tsx does not    -> llms.txt advertises a URL that serves the
 *                                                staff sign-in shell at HTTP 200
 *   _app.tsx has a page the catalogue lacks   -> the page is invisible to every agent
 *   ai-surface.ts disagrees with the handler  -> /llm documents tools that do not exist, and
 *                                                an operator configures a client against it
 *   robots.txt AI group loses a Disallow      -> a named crawler is granted /workspace/
 *
 * Nothing catches any of those at runtime. PublicRouteRegistration.test.ts already guards the
 * first two columns; this file guards the rest, and follows its technique of reading source as
 * TEXT rather than importing it - importing _app.tsx would execute Amplify.configure at module
 * scope, and the values under assertion are literals in the file rather than runtime exports.
 */

const ROOT = process.cwd();
const APP_PATH = path.join( ROOT, 'src', 'pages', '_app.tsx' );
const SITEMAP_PATH = path.join( ROOT, 'scripts', 'generate-sitemap.js' );
const CATALOG_PATH = path.join( ROOT, 'config', 'public-pages.json' );
const ROBOTS_PATH = path.join( ROOT, 'public', 'robots.txt' );
const MCP_HANDLER_PATH = path.join( ROOT, 'amplify', 'functions', 'ai', 'mcp', 'handler.py' );

const appSource = fs.readFileSync( APP_PATH, 'utf8' );
const sitemapSource = fs.readFileSync( SITEMAP_PATH, 'utf8' );
const robotsSource = fs.readFileSync( ROBOTS_PATH, 'utf8' );
const mcpSource = fs.readFileSync( MCP_HANDLER_PATH, 'utf8' );
const catalog = JSON.parse( fs.readFileSync( CATALOG_PATH, 'utf8' ) );

/** Keys of PUBLIC_PAGE_META, sliced the same way PublicRouteRegistration.test.ts does. */
const publicPageMeta = (): Map<string, string> => {
  const start = appSource.indexOf( 'const PUBLIC_PAGE_META' );
  expect( start, 'PUBLIC_PAGE_META not found in _app.tsx' ).toBeGreaterThan( -1 );
  const end = appSource.indexOf( '\nconst ', start + 10 );
  const block = appSource.slice( start, end === -1 ? undefined : end );
  const entries = new Map<string, string>();
  for ( const match of block.matchAll( /^\s*'(\/[a-z0-9-]+)'\s*:\s*\{[^}]*description:\s*'((?:[^'\\]|\\.)*)'/gm ) ) {
    entries.set( match[ 1 ], match[ 2 ].replace( /\\'/g, "'" ) );
  }
  expect( entries.size, 'parsed no PUBLIC_PAGE_META entries — this guard needs updating' ).toBeGreaterThan( 5 );
  return entries;
};

/**
 * PUBLIC_EXACT from the sitemap generator.
 *
 * COMMENT LINES ARE STRIPPED FIRST, and they have to be. That declaration carries long
 * explanatory comments between its entries which themselves quote route paths - '/swdhya'
 * and '/open-possibility', the two names /anew used to have. Matching the raw block picks up
 * 24 paths for 21 entries, so the comparison below would fail against a correct catalogue
 * and the obvious "fix" would be to add two dead routes to it.
 */
const publicExact = (): Set<string> => {
  const start = sitemapSource.indexOf( 'const PUBLIC_EXACT' );
  expect( start, 'PUBLIC_EXACT not found in generate-sitemap.js' ).toBeGreaterThan( -1 );
  const block = sitemapSource.slice( start, sitemapSource.indexOf( '] )', start ) )
    .split( '\n' )
    .filter( line => !line.trim().startsWith( '//' ) )
    .join( '\n' );
  return new Set( Array.from( block.matchAll( /'(\/[a-z0-9-]*)'/g ) ).map( m => m[ 1 ] ) );
};

/** Routes the isPublic chain admits by a bare pathname comparison. */
const isPublicLiterals = (): Set<string> => {
  const start = appSource.indexOf( 'const isPublic' );
  expect( start, 'isPublic not found in _app.tsx' ).toBeGreaterThan( -1 );
  const block = appSource.slice( start, appSource.indexOf( ';', start ) );
  return new Set( Array.from( block.matchAll( /router\.pathname === '([^']+)'/g ) ).map( m => m[ 1 ] ) );
};

/** A `NAME = frozenset({...})` or `NAME = (...)` literal of strings from the Python handler. */
const pyStringSet = ( name: string ): Set<string> => {
  const start = mcpSource.indexOf( `${name} = ` );
  expect( start, `${name} not found in the MCP handler` ).toBeGreaterThan( -1 );
  const block = mcpSource.slice( start, mcpSource.indexOf( '\n\n', start ) );
  const found = Array.from( block.matchAll( /"([^"]+)"/g ) ).map( m => m[ 1 ] );
  expect( found.length, `parsed no strings out of ${name}` ).toBeGreaterThan( 0 );
  return new Set( found );
};

const catalogPaths = new Set<string>( catalog.pages.map( ( p: { path: string } ) => p.path ) );

/** Disallow values inside the rule group a User-agent line belongs to. */
const disallowsForAgent = ( agent: string ): Set<string> => {
  const lines = robotsSource.split( '\n' ).map( line => line.trim() );
  const index = lines.findIndex( line => line.toLowerCase() === `user-agent: ${agent.toLowerCase()}` );
  expect( index, `robots.txt has no group for ${agent}` ).toBeGreaterThan( -1 );
  // A group is consecutive User-agent lines followed by rules, ending at the next
  // User-agent line that comes AFTER at least one rule.
  const out = new Set<string>();
  let seenRule = false;
  for ( let i = index; i < lines.length; i += 1 ) {
    const line = lines[ i ];
    if ( !line || line.startsWith( '#' ) ) continue;
    const isAgent = /^user-agent\s*:/i.test( line );
    if ( isAgent && seenRule ) break;
    if ( isAgent ) continue;
    if ( /^sitemap\s*:/i.test( line ) ) break;
    seenRule = true;
    const disallow = line.match( /^disallow\s*:\s*(.+)$/i );
    if ( disallow ) out.add( disallow[ 1 ].trim() );
  }
  return out;
};

// --------------------------------------------------------------------------- //

describe( 'the catalogue matches the allowlists that decide what is public', () => {
  it( 'lists exactly the pages the sitemap allowlist does', () => {
    /**
     * PUBLIC_EXACT is the right comparison rather than PUBLIC_PAGE_META, because it is the
     * superset: it carries '/' and '/blog', which qualify through the isPublic chain and
     * isContentPublic rather than through the meta map.
     */
    expect( [ ...catalogPaths ].sort() ).toEqual( [ ...publicExact() ].sort() );
  } );

  it( 'reuses the description _app.tsx already publishes for each page', () => {
    /**
     * Not cosmetic. PUBLIC_PAGE_META.description feeds WebPage.description in the schema
     * graph, so a different sentence here means a crawler and a model reading llms.txt get
     * two different accounts of the same page - and the difference would be invisible in
     * both places.
     */
    const meta = publicPageMeta();
    const mismatched: string[] = [];
    for ( const page of catalog.pages ) {
      const expected = meta.get( page.path );
      if ( expected === undefined ) continue; // '/' and '/blog' have no meta entry
      if ( expected !== page.description ) {
        mismatched.push( `${page.path}\n    _app.tsx: ${expected}\n    catalogue: ${page.description}` );
      }
    }
    expect( mismatched, `descriptions disagree:\n  ${mismatched.join( '\n  ' )}` ).toEqual( [] );
  } );

  it( 'puts every page in a declared group', () => {
    const groups = new Set( catalog.groups.map( ( g: { id: string } ) => g.id ) );
    for ( const page of catalog.pages ) expect( groups ).toContain( page.group );
  } );

  it( 'declares no empty group, so llms.txt cannot emit a bare heading', () => {
    for ( const group of catalog.groups ) {
      expect(
        catalog.pages.some( ( p: { group: string } ) => p.group === group.id ),
        `group '${group.id}' has no pages`,
      ).toBe( true );
    }
  } );
} );

describe( '/llm is registered the way /get is', () => {
  it( 'is in the isPublic chain, so it renders instead of the staff sign-in', () => {
    expect( isPublicLiterals() ).toContain( '/llm' );
  } );

  it( 'is absent from the sitemap allowlist and the schema map', () => {
    /**
     * Deliberate, and asserted so it is a decision rather than an omission. /llm is a
     * machine-facing reference page: WebPage structured data and a sitemap entry would put
     * it in front of search queries it cannot answer. Its audience arrives from robots.txt,
     * /llms.txt and the MCP server's own instructions string.
     */
    expect( publicExact() ).not.toContain( '/llm' );
    expect( [ ...publicPageMeta().keys() ] ).not.toContain( '/llm' );
    expect( catalogPaths ).not.toContain( '/llm' );
  } );

  it( 'has a page file to render', () => {
    expect( fs.existsSync( path.join( ROOT, 'src', 'pages', 'llm.tsx' ) ) ).toBe( true );
  } );
} );

describe( 'what /llm claims matches what /mcp serves', () => {
  it( 'documents exactly the tools the handler advertises', () => {
    /**
     * Both directions. A tool added to the handler but not here leaves an undocumented
     * public capability; a tool listed here but absent there sends an operator to configure
     * a client against something that will answer "Unknown tool".
     */
    const documented = MCP_TOOLS.map( tool => tool.name ).sort();
    expect( documented ).toEqual( [ ...pyStringSet( 'READ_ONLY_TOOLS' ) ].sort() );
  } );

  it( 'gives every documented tool a summary', () => {
    for ( const tool of MCP_TOOLS ) expect( tool.summary.length ).toBeGreaterThan( 10 );
  } );

  it( 'advertises exactly the protocol versions the handler speaks', () => {
    expect( [ ...AI_SURFACE.protocolVersions ].sort() )
      .toEqual( [ ...pyStringSet( 'PROTOCOL_VERSIONS' ) ].sort() );
  } );

  it( 'agrees with the catalogue on every URL and on the usage terms', () => {
    expect( AI_SURFACE.mcpEndpoint ).toBe( catalog.ai_surface.mcp_endpoint );
    expect( AI_SURFACE.llmsTxt ).toBe( catalog.ai_surface.llms_txt );
    expect( AI_SURFACE.llmsFullTxt ).toBe( catalog.ai_surface.llms_full_txt );
    expect( [ ...AI_SURFACE.protocolVersions ] ).toEqual( catalog.ai_surface.mcp_protocol_versions );
    expect( [ ...AI_SURFACE.usageTerms ] ).toEqual( catalog.usage_terms );
  } );

  it( 'points at the apex path, not /api/mcp', () => {
    /**
     * robots.txt disallows /api/, and an MCP client is handed one URL and does not go
     * looking for another. Reaching the apex path needs the Amplify rewrite that
     * scripts/deploy_mcp_server.py installs.
     */
    expect( AI_SURFACE.mcpEndpoint ).toBe( 'https://wecare.digital/mcp' );
    expect( AI_SURFACE.mcpEndpoint ).not.toContain( '/api/' );
  } );
} );

describe( 'robots.txt does not grant a named AI crawler more than everyone else', () => {
  const wildcard = disallowsForAgent( '*' );

  it( 'gives the wildcard group the dashboard Disallows', () => {
    // Sanity-check the parser before trusting the comparison below.
    expect( wildcard ).toContain( '/workspace/' );
    expect( wildcard ).toContain( '/api/' );
  } );

  it.each( [
    'GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-User',
    'Claude-SearchBot', 'Google-Extended', 'PerplexityBot', 'Perplexity-User',
    'Applebot-Extended', 'meta-externalagent', 'Bytespider', 'cohere-ai',
    'DuckAssistBot', 'MistralAI-User',
  ] )( '%s is restricted at least as tightly as *', agent => {
    /**
     * THE FOOTGUN THIS EXISTS FOR. robots.txt has no inheritance: a named User-agent group
     * REPLACES the * group for that agent. So
     *
     *     User-agent: GPTBot
     *     Allow: /
     *
     * does not mean "same as everyone, and welcome" - it means GPTBot has no Disallow at
     * all, which grants it /workspace/, the authenticated dashboard that the * group is the
     * only thing holding out of the index. Welcoming a crawler by name and publishing the
     * internal route map is the same edit, and nothing else in the build would notice.
     */
    const theirs = disallowsForAgent( agent );
    for ( const rule of wildcard ) {
      expect( theirs, `${agent} is missing Disallow: ${rule}` ).toContain( rule );
    }
  } );

  it( 'still declares the sitemap', () => {
    expect( robotsSource ).toMatch( /^Sitemap:\s*https:\/\/wecare\.digital\/sitemap\.xml$/m );
  } );
} );

describe( 'the build actually produces the files being advertised', () => {
  it( 'runs the llms.txt generator after the blog search index', () => {
    /**
     * Order, not presence. The generator reads out/blog/search-index.json rather than
     * fetching /api/seo-tools/blog-public a fourth time during one build - that endpoint
     * returns the whole 889-post corpus as 924 kB in about five seconds and is already the
     * hottest function in the fleet. Run it first and the article section silently vanishes.
     */
    const build = JSON.parse( fs.readFileSync( path.join( ROOT, 'package.json' ), 'utf8' ) ).scripts.build;
    expect( build ).toContain( 'generate-llms-txt.js' );
    expect( build.indexOf( 'generate-llms-txt.js' ) )
      .toBeGreaterThan( build.indexOf( 'generate-blog-search-index.js' ) );
  } );

  it( 'keeps the MCP catalogue out of the client bundle', () => {
    /**
     * resolveJsonModule would inline the entire catalogue - every description plus the
     * 20-line _comment block - into any chunk that imports it, and JSON imports are not
     * tree-shaken per key. /llm/ would ship ~8 kB of commentary to render five bullets.
     */
    const surfaceSource = fs.readFileSync( path.join( ROOT, 'src', 'lib', 'ai-surface.ts' ), 'utf8' );
    // Asserts on an IMPORT, not on the filename: that module's header explains at length why
    // it does not import the catalogue, so a substring check would fail on its own rationale.
    expect( surfaceSource ).not.toMatch( /^\s*import\s[^\n]*public-pages\.json/m );
    expect( surfaceSource ).not.toMatch( /require\(\s*['"][^'"]*public-pages\.json/ );
  } );
} );
