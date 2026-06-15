/**
 * Navigation Configuration - WECARE.DIGITAL
 * Centralized sidebar navigation with nested items
 *
 * Structure:
 *   Dashboard — overview, control center, lambda, code repo, auto response
 *   Messages  — WhatsApp, SMS, Voice, Email, RCS, Push
 *   Pay       — overview, pay flow, pay link
 *   Contacts
 *   Store
 *   Orders    — order management (order-centric hub)
 *   Service   — submit request, track request, amend request (order-linked flows)
 *   Booking   — appointments, RX slots
 *   Docs      — drop docs / document management
 *   Enterprise — enterprise assist cases
 *   Reviews   — customer feedback / moderation
 *   FAQ       — admin FAQ management
 *   Access
 *   Link
 *   Forms     — forms builder, self-service hub
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

export const navigationConfig: NavItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: 'dashboard',
    children: [
      { path: '/dashboard', label: 'Overview' },
      { path: '/dashboard/system-architecture', label: 'Control Center' },
      { path: '/dashboard/lambda-functions', label: 'Lambda Functions' },
      { path: '/dashboard/code-repo', label: 'Code Repo' },
      { path: '/dashboard/wa-auto-response', label: 'Auto Response' },
      { path: '/dashboard/waba-usernames', label: 'WABA Usernames' },
      { path: '/dashboard/design-reference', label: 'Design Reference' },
    ],
  },
  {
    path: '/dm',
    label: 'Messages',
    icon: 'message',
    children: [
      { path: '/dm/inbox', label: 'Unified Inbox', icon: 'message' },
      { path: '/dm/channels', label: 'Channels', icon: 'message' },
      { path: '/dm/broadcast', label: 'Broadcast', icon: 'message' },
      { path: '/dm/content', label: 'Content Library', icon: 'message' },
      { path: '/dm/calls', label: 'Calls', icon: 'voice' },
      {
        path: '/dm/whatsapp', label: 'WhatsApp', icon: 'whatsapp', children: [
          { path: '/dm/whatsapp', label: 'Inbox' },
          { path: '/dm/whatsapp/settings', label: 'Settings' },
        ]
      },
      { path: '/dm/sms', label: 'SMS', icon: 'sms' },
      { path: '/dm/voice', label: 'Voice', icon: 'voice' },
      { path: '/dm/voice-in', label: 'Voice In', icon: 'voice' },
      { path: '/dm/ses', label: 'Email', icon: 'email' },
      { path: '/dm/rcs', label: 'RCS', icon: 'rcs' },
      { path: '/dm/push', label: 'Push', icon: 'push' },
    ],
  },
  {
    path: '/pay',
    label: 'Pay',
    icon: 'payment',
    children: [
      { path: '/pay', label: 'Overview' },
      { path: '/pay/flow', label: 'Pay Flow' },
      { path: '/pay/link', label: 'Pay Link' },
    ],
  },
  {
    path: '/contacts',
    label: 'Contacts',
    icon: 'contacts',
  },
  {
    path: '/store',
    label: 'Store',
    icon: 'store',
  },
  // ── Service Operations (WhatsApp-Flow driven; Orders orchestrates) ──
  {
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
    path: '/access',
    label: 'Access',
    icon: 'access',
  },
  {
    path: '/link',
    label: 'Link',
    icon: 'link',
  },
  {
    path: '/forms',
    label: 'Forms',
    icon: 'form',
    children: [
      { path: '/forms', label: 'Forms Builder' },
    ],
  },
  {
    path: '/task',
    label: 'Task',
    icon: 'checklist',
    badge: 'Soon',
  },
  // ── SEO Platform ──
  {
    path: '/seo',
    label: 'SEO',
    icon: 'search',
    children: [
      { path: '/seo', label: 'Dashboard' },
      { path: '/seo/pages', label: 'Pages' },
      { path: '/seo/issues', label: 'Issues' },
      { path: '/seo/analytics', label: 'Analytics' },
      { path: '/seo/tracking', label: 'Tracking' },
      { path: '/seo/schema', label: 'Schema' },
      { path: '/seo/properties', label: 'Properties' },
      { path: '/seo/sitemaps', label: 'Sitemaps' },
      { path: '/seo/tools', label: 'Tools' },
      { path: '/seo/blog-manager', label: 'Blog SEO' },
      { path: '/seo/site-pages', label: 'Site Pages SEO' },
      { path: '/seo/product-pages', label: 'Product SEO' },
      { path: '/seo/system-pages', label: 'System Pages' },
    ],
  },
];

// Flatten all navigation items for search
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
  return items;
}

export function getParentPath ( pathname: string ): string | null {
  for ( const item of navigationConfig )
  {
    if ( item.children?.some( child => child.path === pathname ) ) return item.path;
    if ( pathname.startsWith( item.path ) && item.path !== '/' ) return item.path;
  }
  return null;
}

export function isNavItemActive ( item: NavItem, pathname: string ): boolean {
  if ( item.path === '/' ) return pathname === '/';
  if ( item.children ) return pathname.startsWith( item.path );
  return pathname === item.path || pathname.startsWith( item.path + '/' );
}

export function isSubItemActive ( subItem: NavSubItem, pathname: string ): boolean {
  if ( pathname === subItem.path ) return true;
  if ( subItem.children ) return subItem.children.some( child => pathname === child.path );
  return pathname.startsWith( subItem.path + '/' );
}
