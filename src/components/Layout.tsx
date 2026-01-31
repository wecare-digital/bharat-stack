/**
 * Layout Component - WECARE.DIGITAL
 */
import React, { ReactNode, useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import FloatingAgent from './FloatingAgent';
import SearchModal from './SearchModal';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { navigationConfig, NavItem, NavSubItem } from '../config/navigation';
import { IconMap, ChevronRightIcon, MenuIcon, CloseIcon, SearchIcon } from '../lib/icons';

interface LayoutProps {
  children: ReactNode;
  user?: any;
  onSignOut?: () => void;
}

const Layout: React.FC<LayoutProps> = ({ children, user, onSignOut }) => {
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['/dashboard']));
  const [searchOpen, setSearchOpen] = useState(false);

  useKeyboardShortcuts([
    { key: 'k', ctrl: true, action: () => setSearchOpen(true), description: 'Open search' },
    { key: '/', action: () => setSearchOpen(true), description: 'Open search' },
  ]);

  const isPathActive = (path: string): boolean => {
    if (path === '/') return router.pathname === '/';
    return router.pathname === path || router.pathname.startsWith(path + '/');
  };

  useEffect(() => {
    const newExpanded = new Set<string>(['/dashboard']); // Always keep Dashboard expanded
    const findParents = (items: (NavItem | NavSubItem)[], parents: string[] = []) => {
      for (const item of items) {
        if (isPathActive(item.path)) {
          parents.forEach(p => newExpanded.add(p));
          newExpanded.add(item.path);
        }
        if ('children' in item && item.children) {
          findParents(item.children, [...parents, item.path]);
        }
      }
    };
    findParents(navigationConfig);
    setExpandedPaths(newExpanded);
  }, [router.pathname]);

  useEffect(() => { setIsMobileMenuOpen(false); }, [router.pathname]);

  const toggleExpand = (path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  const renderIcon = (iconName?: string, size: number = 16) => {
    if (!iconName) return null;
    const Icon = IconMap[iconName];
    return Icon ? <Icon size={size} /> : null;
  };

  const renderNavItems = (items: (NavItem | NavSubItem)[], level: number = 0) => {
    return items.map(item => {
      const hasChildren = 'children' in item && item.children && item.children.length > 0;
      const isExpanded = expandedPaths.has(item.path);
      const isActive = isPathActive(item.path);
      const itemClass = level === 0 
        ? `nav-item ${hasChildren ? 'nav-item-expandable' : ''} ${isActive ? 'nav-item-active' : ''}`
        : `nav-subitem ${hasChildren ? 'nav-subitem-expandable' : ''} ${isActive ? 'nav-subitem-active' : ''}`;

      return (
        <div key={item.path} className={level === 0 ? 'nav-group' : 'nav-nested-group'}>
          {hasChildren ? (
            <>
              <button className={itemClass} onClick={() => toggleExpand(item.path)}>
                {'icon' in item && <span className="nav-icon">{renderIcon(item.icon, level === 0 ? 16 : 14)}</span>}
                <span className="nav-label">{item.label}</span>
                <span className={`nav-arrow ${isExpanded ? 'expanded' : ''}`}>
                  <ChevronRightIcon size={level === 0 ? 12 : 10} />
                </span>
              </button>
              {isExpanded && (
                <div className={level === 0 ? 'nav-subitems' : 'nav-nested-items'}>
                  {renderNavItems(item.children!, level + 1)}
                </div>
              )}
            </>
          ) : (
            <span className={itemClass} onClick={() => router.push(item.path)}>
              {'icon' in item && <span className="nav-icon">{renderIcon(item.icon, level === 0 ? 16 : 14)}</span>}
              <span className="nav-label">{item.label}</span>
            </span>
          )}
        </div>
      );
    });
  };

  return (
    <div className="layout">
      <button className="mobile-menu-toggle" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} aria-label="Toggle menu">
        {isMobileMenuOpen ? <CloseIcon size={18} /> : <MenuIcon size={18} />}
      </button>
      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <img src="https://auth.wecare.digital/stream/media/m/wecare-digital.png" alt="Base CRM" className="sidebar-logo" />
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-main">Base CRM</span>
              <span className="sidebar-brand-sub">by WECARE.DIGITAL</span>
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {renderNavItems(navigationConfig)}
        </nav>
        <div className="sidebar-footer">
          {user && (
            <div className="user-info">
              <span className="user-role">{user.role || 'Operator'}</span>
              <span className="user-email">{user.signInDetails?.loginId || user.email}</span>
              <button className="btn-signout" onClick={onSignOut}>Sign Out</button>
            </div>
          )}
        </div>
      </aside>
      {isMobileMenuOpen && <div className="mobile-overlay" onClick={() => setIsMobileMenuOpen(false)} />}
      <main className="main-content">{children}</main>
      <FloatingAgent />
      <SearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
};

export default Layout;
