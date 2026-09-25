/**
 * Navigation — a short sidebar, and everything else behind the gear.
 *
 * THE GOVERNING RULE
 * ------------------
 *   Sidebar = streams you work in daily.  Gear = things you configure once.
 *
 * The sidebar held 11 top-level sections and 88 destinations, of which **30 were
 * WhatsApp sub-pages** — 34% of the whole navigation in one branch. Nothing was
 * broken; it was simply a settings tree wearing a sidebar's clothes, and the
 * things an operator touches hourly sat at the same level as "Flow Publish
 * Checklist".
 *
 * NOTHING IS UNREACHABLE. `getAllNavItems()` returns the sidebar AND the settings
 * tree, and that is the single function the command palette is built from. So
 * every destination that existed before is still findable by name with Ctrl+K.
 * That property is load-bearing rather than incidental: 21 of the 88 paths have no
 * link anywhere else in the app, so if the palette missed the settings tree this
 * change would strand them. There is a test on exactly that.
 *
 * TWO THINGS HAD TO LAND FIRST, and did:
 *   - The palette used to search its own hardcoded 14 entries and locked the
 *     renderer on keystroke. Fixed before this, because this change deletes the
 *     sidebar search box that was doing the job.
 *   - Fifteen routes rendered no shell at all. Wrapped before this, because
 *     without a sidebar they would have been dead ends.
 *
 * WHY Calls IS NOT HERE AS A PAGE: it is `/dm/inbox?channel=voice`. `dm/calls`
 * read the same canonical MessagesTable the inbox already reads, and the inbox
 * already renders voice with its own badge and an audio player. Call
 * *configuration* is under the gear.
 */

export interface NavSubItem {
  path: string;
  label: string;
  icon?: string;
  badge?: string;
  children?: NavSubItem[];
}

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  badge?: string;
  sectionLabel?: string;
  children?: NavSubItem[];
}

/** A named group in the settings tree the gear opens. */
export interface SettingsGroup {
  id: string;
  label: string;
  icon: string;
  /** One line saying what lives here, so the group is scannable. */
  hint: string;
  items: NavSubItem[];
}

// ---------------------------------------------------------------------------
// THE SIDEBAR — daily streams only
// ---------------------------------------------------------------------------
export const navigationConfig: NavItem[] = [
  {
    // The channel children are filters on ONE page, not separate pages. They exist
    // because jumping straight to "just the RCS threads" is a daily move, and the
    // in-page selector is one extra click away from the sidebar.
    path: '/dm/inbox',
    label: 'Inbox',
    icon: 'message',
    children: [
      { path: '/dm/inbox', label: 'All channels' },
      { path: '/dm/inbox?channel=whatsapp', label: 'WhatsApp' },
      { path: '/dm/inbox?channel=sms', label: 'SMS' },
      { path: '/dm/inbox?channel=rcs', label: 'RCS' },
      { path: '/dm/inbox?channel=email', label: 'Email' },
      { path: '/dm/inbox?channel=voice', label: 'Calls' },
    ],
  },
  {
    path: '/contacts',
    label: 'Contacts',
    icon: 'contacts',
    children: [
      { path: '/contacts', label: 'All contacts' },
      { path: '/dm/contact-360', label: 'Contact 360' },
    ],
  },
  {
    path: '/dm/broadcast',
    label: 'Broadcast',
    icon: 'message',
    children: [
      { path: '/dm/broadcast', label: 'Send a broadcast' },
      { path: '/dm/scheduled', label: 'Scheduled' },
      { path: '/dm/logs', label: 'Message logs' },
    ],
  },
  {
    path: '/pay',
    label: 'Payments',
    icon: 'payment',
    children: [
      { path: '/pay', label: 'Overview' },
      // The ledger: what was billed, paid and delivered. Read-only on purpose -
      // cancel, delete and resend all move money or message a customer.
      { path: '/pay/records', label: 'Invoice records' },
      { path: '/pay/flow', label: 'Pay Flow' },
      { path: '/pay/link', label: 'Pay Link' },
    ],
  },
  {
    // Owner leaned sidebar: ten child routes, and they are order-linked daily work
    // rather than configuration.
    path: '/dm/service-ops',
    label: 'Service Ops',
    icon: 'order',
    children: [
      { path: '/dm/service-ops', label: 'Orders' },
      { path: '/service/submit-request', label: 'Submit Request' },
      { path: '/service/track-request', label: 'Track Request' },
      { path: '/service/amend-request', label: 'Amend Request' },
      { path: '/dm/appointments', label: 'Appointments' },
      { path: '/dm/rx-slots', label: 'RX Slots' },
      { path: '/dm/documents', label: 'Drop Docs' },
      { path: '/dm/enterprise', label: 'Enterprise' },
      { path: '/dm/reviews', label: 'Reviews' },
      { path: '/dm/faq', label: 'FAQ' },
    ],
  },
  {
    path: '/store',
    label: 'Store',
    icon: 'store',
    children: [
      { path: '/store', label: 'Catalog' },
      { path: '/dm/commerce', label: 'Commerce' },
    ],
  },
  {
    path: '/forms',
    label: 'Forms',
    icon: 'form',
    children: [
      // Responses first: a submitted request nobody actioned is a customer who paid
      // and heard nothing, so the queue matters more than a builder would.
      { path: '/forms/responses', label: 'Responses' },
      // '/forms/create' ("Forms Builder") was here. Removed 2026-09-25 with the page: it
      // was a ComingSoon stub listing six features with no backend behind any of them,
      // and /forms/index.tsx redirected straight to it, so the whole /forms landing was a
      // redirect into a list of promises. /forms now goes to Responses.
      { path: '/forms/selfservice', label: 'Self-service Hub' },
    ],
  },
  {
    // No longer 'Soon'. It was a ComingSoon stub promising six features with no
    // backend at all; it is now the conversation-meta work queue, which is real
    // data the inbox already writes.
    path: '/task',
    label: 'Tasks',
    icon: 'checklist',
  },
];

// ---------------------------------------------------------------------------
// THE GEAR — everything configured rather than worked in
// ---------------------------------------------------------------------------
export const settingsConfig: SettingsGroup[] = [
  {
    id: 'account',
    label: 'Your account',
    icon: 'access',
    hint: 'Sign-in and second factors',
    items: [
      // Kept deliberately prominent. TOTP enrolment cannot be done from the admin
      // side — Cognito's AssociateSoftwareToken takes the user's own access token
      // and does not evaluate IAM — so the signed-in person must be able to reach
      // this. Burying it would work against the admin-MFA target.
      { path: '/access/security', label: 'Sign-in & MFA' },
      { path: '/access', label: 'Access' },
    ],
  },
  {
    id: 'whatsapp',
    label: 'WhatsApp',
    icon: 'whatsapp',
    hint: 'WABA setup, templates, flows, calling',
    items: [
      { path: '/dm/whatsapp', label: 'WhatsApp Inbox' },
      { path: '/dm/whatsapp/waba-dashboard', label: 'WABA Dashboard' },
      { path: '/dm/whatsapp/embedded-signup', label: 'Connect WABA' },
      { path: '/dm/whatsapp/connected-accounts', label: 'Connected Accounts' },
      { path: '/dm/whatsapp/my-account', label: 'My WhatsApp Account' },
      { path: '/dm/whatsapp/business-profile', label: 'Business Profile' },
      { path: '/dm/whatsapp/webhooks', label: 'Webhooks' },
      { path: '/dm/whatsapp/bsuid', label: 'BSUID & Usernames' },
      { path: '/dm/whatsapp/migration', label: 'WABA Migration' },
      { path: '/dm/whatsapp/settings', label: 'WhatsApp Settings' },
      { path: '/dm/whatsapp/send-test', label: 'Send Test' },
      { path: '/dm/whatsapp/campaign', label: 'WhatsApp Campaign' },
      { path: '/dm/whatsapp/interactive-lists', label: 'Interactive Lists' },
      { path: '/dm/whatsapp/auto-response', label: 'Auto Response' },
      { path: '/dm/whatsapp/conversions-api', label: 'Conversions API (CTWA)' },
      { path: '/dm/whatsapp/ctwa-ads', label: 'Ads to WhatsApp (CTWA)' },
      { path: '/dm/whatsapp/tech-partner', label: 'Tech Partner Readiness' },
      { path: '/dm/whatsapp/templates', label: 'Templates' },
      { path: '/dm/whatsapp/template-builder', label: 'Template Builder' },
      { path: '/dm/whatsapp/catalog-builder', label: 'Catalog & Flow Builder' },
      { path: '/dm/whatsapp/flow-hub', label: 'Flow Hub' },
      { path: '/dm/whatsapp/flows', label: 'Flows' },
      { path: '/dm/whatsapp/flow-publish', label: 'Flow Publish Checklist' },
      { path: '/dm/whatsapp/flow-responses', label: 'Flow Responses' },
      { path: '/dm/whatsapp/groups', label: 'Groups' },
      { path: '/dm/whatsapp/calling', label: 'Calling' },
      { path: '/dm/whatsapp/cost-controls', label: 'Cost Controls' },
      { path: '/dm/whatsapp/scripts', label: 'Scripts' },
      { path: '/dm/whatsapp/welcome', label: 'Welcome Message' },
    ],
  },
  {
    id: 'channels',
    label: 'Other channels',
    icon: 'message',
    hint: 'SMS, RCS, Email, Voice, Push',
    items: [
      // `/dm` is a real 160-line page (the Messages hub), not just a section
      // container. It was the old sidebar's "Messages" parent, so dropping the
      // parent would have orphaned an actual route.
      { path: '/dm', label: 'Messages hub' },
      { path: '/dm/channels', label: 'All channels' },
      { path: '/dm/settings', label: 'Channel Settings' },
      { path: '/dm/sms', label: 'SMS' },
      { path: '/dm/rcs', label: 'RCS' },
      { path: '/dm/ses', label: 'Email' },
      { path: '/dm/push', label: 'Push' },
      // Call CONFIGURATION. The call RECORDS are /dm/inbox?channel=voice.
      { path: '/dm/voice', label: 'Voice (outbound)' },
      { path: '/dm/voice-in', label: 'Voice In (IVR)' },
    ],
  },
  {
    id: 'messaging-tools',
    label: 'Messaging tools',
    icon: 'settings',
    hint: 'Automation, content, analytics, cost',
    items: [
      { path: '/dm/automation', label: 'Automation' },
      { path: '/dm/content', label: 'Content Library' },
      { path: '/dm/analytics', label: 'Analytics' },
      { path: '/dm/cost', label: 'Cost & Usage' },
      { path: '/dm/search', label: 'Message Search' },
      { path: '/dm/meta-agent', label: 'Meta AI Agent' },
      { path: '/dm/whatsapp/ai-agent', label: 'AI Agent' },
      { path: '/dm/docs', label: 'Docs Scraper' },
      { path: '/link', label: 'Short Links' },
    ],
  },
  {
    id: 'modules',
    label: 'Modules',
    icon: 'dashboard',
    hint: 'Growth and Commerce — read-only, behind flags',
    items: [
      // Flag-gated and currently OFF. Listed anyway: the whole point of
      // `getAllNavItems()` is that nothing is unreachable, and a flagged-off page that
      // explains WHY it is off is more use than a 404.
      //
      // '/growth' sat beside Commerce until 2026-09-25 and was removed with its page on
      // owner instruction. Commerce is the same shape and stays.
      { path: '/commerce', label: 'Commerce' },
    ],
  },
  {
    id: 'seo',
    label: 'SEO',
    icon: 'search',
    hint: 'Pages, schema, sitemaps, tracking',
    items: [
      { path: '/seo', label: 'SEO Dashboard' },
      { path: '/seo/pages', label: 'Pages' },
      { path: '/seo/issues', label: 'Issues' },
      { path: '/seo/analytics', label: 'Analytics' },
      { path: '/seo/tracking', label: 'Tracking' },
      { path: '/seo/schema', label: 'Schema' },
      { path: '/seo/properties', label: 'Properties' },
      { path: '/seo/sitemaps', label: 'Sitemaps' },
      { path: '/seo/tools', label: 'Tools' },
      { path: '/seo/blog-manager', label: 'Blog SEO' },
      { path: '/seo/pages-manager', label: 'Site Pages SEO' },
    ],
  },
  {
    id: 'platform',
    label: 'Platform',
    icon: 'dashboard',
    hint: 'Infrastructure, architecture, diagnostics',
    items: [
      { path: '/dashboard', label: 'Dashboard Overview' },
      { path: '/dashboard/system-architecture', label: 'Control Center' },
      { path: '/dashboard/lambda-functions', label: 'Lambda Functions' },
      { path: '/dashboard/code-repo', label: 'Code Repo' },
      { path: '/dashboard/waba-usernames', label: 'WABA Usernames' },
      { path: '/dashboard/wa-graph-tools', label: 'WA Graph Tools' },
      { path: '/dashboard/cors-settings', label: 'CORS Settings' },
      { path: '/dashboard/design-reference', label: 'Design Reference' },
      // '/carbon' and '/nocode' were here. Both removed 2026-09-25 with their pages:
      // each was a 15-line EmptyState reading "... coming soon" with nothing behind it
      // ("Sustainability and carbon tracking", "Visual workflow and form builder"). A
      // menu entry leading to a promise is exactly the failure mode the Growth/Commerce
      // comment above set out to avoid — a flagged-off page that explains itself is real
      // content, "coming soon" is not.
      { path: '/docs', label: 'Docs' },
    ],
  },
];

// ---------------------------------------------------------------------------
// THE EIGHT MODULE HOMES (master prompt phase 8.1)
// ---------------------------------------------------------------------------
/**
 * The master prompt asks for eight module homes: Home, Communications, Customers,
 * Commerce, Growth, Service Operations, Platform Operations and Settings.
 *
 * RECONCILING THAT WITH THE SIDEBAR ABOVE
 * ---------------------------------------
 * These are not the same question, and conflating them is what made this look like a
 * contradiction. A **module home** is a route: the landing page for a domain, with its
 * inner pages separately routed and lazy-loaded. The **sidebar** is which of those are
 * one click away. The owner overrode the second — "just show main inbox, rest move
 * under settings" — and said nothing about the first.
 *
 * So the eight homes are declared here and every one is a real, reachable route. Six of
 * the eight were already live under different names; this registry stops that being
 * implicit, and `tests/test_module_homes.py` asserts each `path` exists as a page and
 * appears in `getAllNavItems()`.
 *
 * Settings is deliberately `null`. A `/settings` page would be one more destination to
 * navigate to *before* navigating, with its own shell, breadcrumb and a decision about
 * the page you were on — so it is a panel (`SettingsGear`) over `settingsConfig`, not a
 * route. That was a C1 decision and it stands; recording it as a home with no path is
 * more honest than inventing a route to satisfy a count.
 */
export interface ModuleHome {
  /** The master prompt's name for the module. */
  id: string;
  label: string;
  /** The live route, or null when the module is a panel rather than a page. */
  path: string | null;
  /** Where its inner pages live, for the lazy-loading requirement. */
  innerPages: string[];
  /** Why this route is the home, when the name does not match the master prompt's. */
  note?: string;
}

export const moduleHomes: ModuleHome[] = [
  {
    id: 'home', label: 'Home', path: '/dashboard',
    innerPages: ['/dashboard/system-architecture', '/dashboard/lambda-functions',
      '/dashboard/code-repo', '/dashboard/cors-settings'],
    note: 'Tab bodies are lazy via next/dynamic; OverviewTab stays eager because it is '
      + 'the default tab and lazy-loading it would only add a round trip.',
  },
  {
    id: 'communications', label: 'Communications', path: '/dm',
    // The master prompt is explicit: Communications exposes EXACTLY these three.
    innerPages: ['/dm/inbox', '/dm/whatsapp', '/dm/voice'],
    note: 'Common Inbox, WhatsApp Business and Business Calling — exactly three, as '
      + 'specified. The other channels (SMS, RCS, Email, Push) are filters on the '
      + 'common inbox plus configuration under the gear, not peers of these three.',
  },
  {
    id: 'customers', label: 'Customers', path: '/contacts',
    innerPages: ['/dm/contact-360'],
  },
  {
    id: 'commerce', label: 'Commerce', path: '/commerce',
    innerPages: ['/store', '/dm/commerce', '/pay', '/pay/records'],
    note: 'Behind NEXT_PUBLIC_ENABLE_COMMERCE_MODULE, and OFF — not because it is '
      + 'unfinished but because the storefront is live, so a new surface over a '
      + 'production store opens deliberately. With the flag off it links to the working '
      + 'pages rather than shadowing them.',
  },
  // The 'growth' module home was here, gated on NEXT_PUBLIC_ENABLE_GROWTH_MODULE.
  // Removed 2026-09-25 with /growth/index.tsx on owner instruction. The pages it listed
  // as innerPages are all still reachable in their own right — /seo, /seo/pages,
  // /seo/analytics, /seo/tracking, /seo/schema, /dm/whatsapp/ctwa-ads and
  // /dm/whatsapp/conversions-api each have their own nav entry — so nothing became
  // unreachable, only the grouping page went.
  {
    id: 'service-operations', label: 'Service Operations', path: '/dm/service-ops',
    innerPages: ['/service/submit-request', '/service/track-request',
      '/service/amend-request', '/dm/appointments', '/dm/rx-slots',
      '/dm/documents', '/dm/enterprise', '/dm/reviews', '/dm/faq'],
  },
  {
    id: 'platform-operations', label: 'Platform Operations',
    path: '/dashboard/system-architecture',
    innerPages: ['/dashboard/lambda-functions', '/dashboard/code-repo',
      '/dashboard/cors-settings', '/dashboard/design-reference'],
  },
  {
    id: 'settings', label: 'Settings', path: null,
    innerPages: [],
    note: 'A panel, not a route. See the block comment above.',
  },
];

/**
 * Every destination, sidebar AND settings.
 *
 * This is the one function the command palette is built from, so anything missing
 * here becomes genuinely unreachable once the sidebar is short. `getAllNavItems`
 * therefore walks both trees, and a test asserts the settings paths are present.
 */
export function getAllNavItems (): { path: string; label: string; parent?: string }[] {
  const items: { path: string; label: string; parent?: string }[] = [];
  const traverse = ( navItems: ( NavItem | NavSubItem )[], parentLabel?: string ) => {
    for ( const item of navItems )
    {
      items.push( { path: item.path, label: item.label, parent: parentLabel } );
      if ( 'children' in item && item.children )
      {
        traverse( item.children, item.label );
      }
    }
  };
  traverse( navigationConfig );
  for ( const group of settingsConfig )
  {
    traverse( group.items, group.label );
  }
  return items;
}

/** Just the settings destinations, for the gear panel and for tests. */
export function getSettingsItems (): { path: string; label: string; group: string }[] {
  return settingsConfig.flatMap( ( g ) =>
    g.items.map( ( i ) => ( { path: i.path, label: i.label, group: g.label } ) ) );
}

/**
 * Strip a query string before comparing to a route.
 *
 * The Inbox children are `/dm/inbox?channel=rcs` — one page, six entries. Without
 * this, active-state matching compares a path against a path-plus-query and never
 * matches, so the sidebar would highlight nothing on the page you are looking at.
 */
function basePath ( p: string ): string {
  const i = p.indexOf( '?' );
  return i === -1 ? p : p.slice( 0, i );
}

export function getParentPath ( pathname: string ): string | null {
  for ( const item of navigationConfig )
  {
    if ( item.children?.some( ( child ) => basePath( child.path ) === pathname ) )
      return item.path;
    if ( pathname.startsWith( basePath( item.path ) ) && item.path !== '/' )
      return item.path;
  }
  return null;
}

export function isNavItemActive ( item: NavItem, pathname: string ): boolean {
  const base = basePath( item.path );
  if ( base === '/' ) return pathname === '/';
  if ( item.children ) return pathname.startsWith( base );
  return pathname === base || pathname.startsWith( base + '/' );
}

export function isSubItemActive ( subItem: NavSubItem, pathname: string ): boolean {
  const base = basePath( subItem.path );
  if ( pathname === base ) return true;
  if ( subItem.children )
    return subItem.children.some( ( child ) => pathname === basePath( child.path ) );
  return pathname.startsWith( base + '/' );
}
