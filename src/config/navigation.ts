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
  },
  {
    path: '/dm',
    label: 'Messages',
    icon: 'message',
    children: [
      { path: '/dm/whatsapp', label: 'WhatsApp', icon: 'whatsapp' },
      { path: '/dm/sms', label: 'SMS', icon: 'sms' },
      { path: '/dm/voice', label: 'Voice', icon: 'voice' },
      { 
        path: '/dm/ses', 
        label: 'Email', 
        icon: 'email',
        children: [
          { path: '/dm/ses/inbox', label: 'Inbox' },
          { path: '/dm/ses/campaign', label: 'Campaign' },
          { path: '/dm/ses/logs', label: 'Logs' },
        ]
      },
      { 
        path: '/dm/rcs', 
        label: 'RCS', 
        icon: 'rcs',
        children: [
          { path: '/dm/rcs/inbox', label: 'Inbox' },
          { path: '/dm/rcs/campaign', label: 'Campaign' },
          { path: '/dm/rcs/logs', label: 'Logs' },
        ]
      },
      { path: '/dm/logs', label: 'All Logs', icon: 'logs' },
    ],
  },
  {
    path: '/pay',
    label: 'Pay',
    icon: 'payment',
    children: [
      { path: '/pay/flow', label: 'Flow' },
      { path: '/pay/wa', label: 'WhatsApp' },
      { path: '/pay/link', label: 'Link', badge: 'Soon' },
    ]
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
  // Coming Soon section
  {
    path: '/link',
    label: 'Link',
    icon: 'link',
    badge: 'Soon',
    sectionLabel: 'Coming Soon',
  },
  {
    path: '/forms',
    label: 'Forms',
    icon: 'form',
    badge: 'Soon',
  },
  {
    path: '/docs',
    label: 'Docs',
    icon: 'document',
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
