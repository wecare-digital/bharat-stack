/**
 * Navigation Configuration - WECARE.DIGITAL
 * Centralized sidebar navigation with nested items
 * Updated: 2026-02-15
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
      { path: '/dashboard', label: 'Overview', icon: 'dashboard' },
      { path: '/dashboard/system-architecture', label: 'Control Center', icon: 'dashboard' },
      { path: '/dashboard/admin', label: 'Admin', icon: 'settings' },
      { path: '/dashboard/lambda-functions', label: 'Lambda Functions', icon: 'settings' },
      { path: '/dashboard/code-repo', label: 'Code Repo', icon: 'settings' },
      { path: '/dashboard/wa-auto-response', label: 'Auto Response', icon: 'settings' },
    ],
  },
  {
    path: '/dm',
    label: 'Messages',
    icon: 'message',
    children: [
      { path: '/dm/whatsapp', label: 'WhatsApp', icon: 'whatsapp', children: [
        { path: '/dm/whatsapp', label: 'Inbox' },
        { path: '/dm/whatsapp/templates', label: 'Templates' },
        { path: '/dm/whatsapp/campaign', label: 'Campaign' },
        { path: '/dm/whatsapp/flows', label: 'Flows' },
        { path: '/dm/whatsapp/flow-hub', label: 'Flow Hub' },
        { path: '/dm/whatsapp/flow-responses', label: 'Flow Responses' },
        { path: '/dm/whatsapp/calling', label: 'Calling' },
        { path: '/dm/whatsapp/groups', label: 'Groups' },
        { path: '/dm/whatsapp/interactive-lists', label: 'Interactive Lists' },
        { path: '/dm/whatsapp/scripts', label: 'Scripts' },
        { path: '/dm/whatsapp/welcome', label: 'Welcome' },
        { path: '/dm/whatsapp/auto-response', label: 'Auto Response' },
        { path: '/dm/whatsapp/ai-config', label: 'AI Config' },
        { path: '/dm/whatsapp/waba-dashboard', label: 'WABA Dashboard' },
        { path: '/dm/whatsapp/business-profile', label: 'Business Profile' },
        { path: '/dm/whatsapp/webhooks', label: 'Webhooks' },
        { path: '/dm/whatsapp/migration', label: 'Migration' },
        { path: '/dm/whatsapp/logs', label: 'Logs' },
        { path: '/dm/whatsapp/settings', label: 'Settings' },
      ] },
      { path: '/dm/sms', label: 'SMS', icon: 'sms' },
      { path: '/dm/voice', label: 'Voice', icon: 'voice' },
      { path: '/dm/voice-in', label: 'Voice In', icon: 'voice' },
      { path: '/dm/ses', label: 'Email', icon: 'email', children: [
        { path: '/dm/ses', label: 'Inbox' },
        { path: '/dm/ses/campaign', label: 'Campaign' },
        { path: '/dm/ses/logs', label: 'Logs' },
      ] },
      { path: '/dm/rcs', label: 'RCS', icon: 'rcs', children: [
        { path: '/dm/rcs', label: 'Inbox' },
        { path: '/dm/rcs/campaign', label: 'Campaign' },
        { path: '/dm/rcs/logs', label: 'Logs' },
      ] },
      { path: '/dm/push', label: 'Push', icon: 'push' },
      { path: '/dm/logs', label: 'Logs', icon: 'settings' },
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
  {
    path: '/access',
    label: 'Access',
    icon: 'access',
  },
  {
    path: '/contact-test',
    label: 'Design Reference',
    icon: 'form',
  },
  {
    path: '/link',
    label: 'Link',
    icon: 'link',
    children: [
      { path: '/link', label: 'Links' },
      { path: '/link/create', label: 'Create' },
      { path: '/link/logs', label: 'Logs' },
    ],
  },
  // Coming Soon section
  {
    path: '/forms',
    label: 'Forms',
    icon: 'form',
    badge: 'Soon',
    sectionLabel: 'Coming Soon',
    children: [
      { path: '/forms', label: 'Forms Builder', icon: 'form' },
      { path: '/forms/selfservice', label: 'Self-Service', icon: 'checklist' },
    ],
  },
  {
    path: '/task',
    label: 'Task',
    icon: 'checklist',
    badge: 'Soon',
  },
];

// Flatten all navigation items for search
export function getAllNavItems(): { path: string; label: string; parent?: string }[] {
  const items: { path: string; label: string; parent?: string }[] = [];
  
  const traverse = (navItems: (NavItem | NavSubItem)[], parentLabel?: string) => {
    for (const item of navItems) {
      items.push({ path: item.path, label: item.label, parent: parentLabel });
      if ('children' in item && item.children) {
        traverse(item.children, item.label);
      }
    }
  };
  
  traverse(navigationConfig);
  return items;
}

/**
 * Get the parent path for a given route
 */
export function getParentPath(pathname: string): string | null {
  for (const item of navigationConfig) {
    if (item.children?.some(child => child.path === pathname)) {
      return item.path;
    }
    if (pathname.startsWith(item.path) && item.path !== '/') {
      return item.path;
    }
  }
  return null;
}

/**
 * Check if a nav item is active
 */
export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (item.path === '/') return pathname === '/';
  if (item.children) return pathname.startsWith(item.path);
  return pathname === item.path || pathname.startsWith(item.path + '/');
}

/**
 * Check if a sub-item is active (including nested children)
 */
export function isSubItemActive(subItem: NavSubItem, pathname: string): boolean {
  if (pathname === subItem.path) return true;
  if (subItem.children) {
    return subItem.children.some(child => pathname === child.path);
  }
  return pathname.startsWith(subItem.path + '/');
}
