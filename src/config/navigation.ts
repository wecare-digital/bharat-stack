/**
 * Navigation Configuration - WECARE.DIGITAL
 * Centralized sidebar navigation with nested items
 * Updated: 2026-02-03
 */

export interface NavSubItem {
  path: string;
  label: string;
  icon?: string;
  children?: NavSubItem[];
}

export interface NavItem {
  path: string;
  label: string;
  icon: string;
  children?: NavSubItem[];
}

export const navigationConfig: NavItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: 'dashboard',
  },
  {
    path: '/pay',
    label: 'Pay',
    icon: 'payment',
    children: [
      { path: '/pay/link', label: 'Link' },
      { path: '/pay/wa', label: 'WhatsApp' },
      { path: '/pay/logs', label: 'Logs' },
    ]
  },
  {
    path: '/link',
    label: 'Link',
    icon: 'link',
    children: [
      { path: '/link/create', label: 'Create' },
      { path: '/link/logs', label: 'Logs' },
    ]
  },
  {
    path: '/forms',
    label: 'Forms',
    icon: 'form',
    children: [
      { path: '/forms/create', label: 'Create' },
      { path: '/forms/logs', label: 'Logs' },
    ]
  },
  {
    path: '/docs',
    label: 'Docs',
    icon: 'document',
    children: [
      { path: '/docs/create', label: 'Create' },
      { path: '/docs/logs', label: 'Logs' },
    ]
  },
  {
    path: '/invoice',
    label: 'Invoice',
    icon: 'invoice',
    children: [
      { path: '/invoice/create', label: 'Create' },
      { path: '/invoice/logs', label: 'Logs' },
    ]
  },
  {
    path: '/dm',
    label: 'Messages',
    icon: 'message',
    children: [
      { 
        path: '/dm/whatsapp', 
        label: 'WhatsApp', 
        icon: 'whatsapp',
        children: [
          { path: '/dm/whatsapp/board', label: 'Board' },
          { path: '/dm/whatsapp/inbox', label: 'Inbox' },
          { path: '/dm/whatsapp/campaign', label: 'Campaign' },
          { path: '/dm/whatsapp/logs', label: 'Logs' },
          { path: '/dm/whatsapp/templates', label: 'Templates' },
        ]
      },
      { 
        path: '/dm/sms', 
        label: 'SMS', 
        icon: 'sms',
        children: [
          { path: '/dm/sms/inbox', label: 'Inbox' },
          { path: '/dm/sms/campaign', label: 'Campaign' },
          { path: '/dm/sms/logs', label: 'Logs' },
        ]
      },
      { 
        path: '/dm/sms-in', 
        label: 'SMS IN', 
        icon: 'sms',
      },
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
        path: '/dm/voice', 
        label: 'Voice', 
        icon: 'voice',
        children: [
          { path: '/dm/voice/inbox', label: 'Inbox' },
          { path: '/dm/voice/campaign', label: 'Campaign' },
          { path: '/dm/voice/logs', label: 'Logs' },
        ]
      },
      { 
        path: '/dm/voice-in', 
        label: 'Voice IN', 
        icon: 'voice',
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
