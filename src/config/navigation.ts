/**
 * Navigation Configuration - WECARE.DIGITAL
 * Centralized sidebar navigation with nested items
 * Updated: 2026-01-29
 */

export interface NavSubItem {
  path: string;
  label: string;
  icon?: string;
  children?: NavSubItem[];  // Support for nested sub-items
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
  },
  {
    path: '/docs',
    label: 'Docs',
    icon: 'document',
  },
  {
    path: '/invoice',
    label: 'Invoice',
    icon: 'invoice',
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
          { path: '/dm/whatsapp/inbox', label: 'Inbox' },
          { path: '/dm/whatsapp/board', label: 'Board' },
          { path: '/dm/whatsapp/campaign', label: 'Campaign' },
          { path: '/dm/whatsapp/templates', label: 'Templates' },
        ]
      },
      { 
        path: '/dm/sms', 
        label: 'SMS', 
        icon: 'sms',
        children: [
          { path: '/dm/sms/aws', label: 'AWS' },
          { path: '/dm/sms/aws/campaign', label: 'Campaign' },
          { path: '/dm/sms/airtel', label: 'Airtel' },
        ]
      },
      { path: '/dm/sms-in', label: 'SMS IN', icon: 'sms' },
      { path: '/dm/ses', label: 'Email', icon: 'email' },
      { 
        path: '/dm/voice', 
        label: 'Voice', 
        icon: 'voice',
        children: [
          { path: '/dm/voice/aws', label: 'AWS' },
          { path: '/dm/voice/aws/campaign', label: 'Campaign' },
          { path: '/dm/voice/airtel', label: 'Airtel' },
        ]
      },
      { path: '/dm/voice-in', label: 'Voice IN', icon: 'voice' },
      { path: '/dm/rcs', label: 'RCS', icon: 'rcs' },
      { path: '/dm/logs', label: 'Logs', icon: 'logs' },
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
