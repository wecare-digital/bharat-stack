/**
 * Navigation Configuration - WECARE.DIGITAL
 * Centralized sidebar navigation with nested items
 * Updated: 2026-04-12
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
    ],
  },
  {
    path: '/dm',
    label: 'Messages',
    icon: 'message',
    children: [
      { path: '/dm/whatsapp', label: 'WhatsApp', icon: 'whatsapp', children: [
        { path: '/dm/whatsapp', label: 'Inbox' },
        { path: '/dm/whatsapp/settings', label: 'Settings' },
      ] },
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
      { path: '/forms/selfservice', label: 'Self-Service' },
    ],
  },
  {
    path: '/faq',
    label: 'FAQ',
    icon: 'form',
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
