/**
 * Layout Component - WECARE.DIGITAL
 */
import React, { ReactNode, useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/router';
import SearchModal from './SearchModal';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { navigationConfig, NavItem, NavSubItem, getAllNavItems } from '../config/navigation';
import { IconMap, ChevronRightIcon, MenuIcon, CloseIcon } from '../lib/icons';
import { Breadcrumbs, KeyboardShortcuts, useKeyboardShortcutsModal } from './ui';

interface LayoutProps {
  children: ReactNode;
  user?: any;
  onSignOut?: () => void;
  showBreadcrumbs?: boolean;
}

const Layout: React.FC<LayoutProps> = ({ children, user, onSignOut, showBreadcrumbs = true }) => {
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['/dashboard']));
  const [searchOpen, setSearchOpen] = useState(false);
  const [sidebarSearch, setSidebarSearch] = useState('');
  const shortcutsModal = useKeyboardShortcutsModal();

  useKeyboardShortcuts([
    { key: 'k', ctrl: true, action: () => setSearchOpen(true), description: 'Open search' },
    { key: '/', action: () => setSearchOpen(true), description: 'Open search' },
  ]);

  const isPathActive = (path: string): boolean => {
    if (path === '/') return router.pathname === '/';
    return router.pathname === path || router.pathname.startsWith(path + '/');
  };

  // Get all nav items for sidebar search
  const allNavItems = useMemo(() => getAllNavItems(), []);
  
  // Filter nav items based on search
  const filteredNavItems = useMemo(() => {
    if (!sidebarSearch.trim()) return [];
    const query = sidebarSearch.toLowerCase();
    return allNavItems.filter(item => 
      item.label.toLowerCase().includes(query) ||
      item.parent?.toLowerCase().includes(query)
    ).slice(0, 8);
  }, [sidebarSearch, allNavItems]);

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

  const handleSearchItemClick = (path: string) => {
    setSidebarSearch('');
    router.push(path);
  };

  const renderNavItems = (items: (NavItem | NavSubItem)[], level: number = 0) => {
    return items.map((item, index) => {
      const hasChildren = 'children' in item && item.children && item.children.length > 0;
      const isExpanded = expandedPaths.has(item.path);
      const isActive = isPathActive(item.path);
      const itemClass = level === 0 
        ? `nav-item ${hasChildren ? 'nav-item-expandable' : ''} ${isActive ? 'nav-item-active' : ''}`
        : `nav-subitem ${hasChildren ? 'nav-subitem-expandable' : ''} ${isActive ? 'nav-subitem-active' : ''}`;

      // Section label (e.g. "Coming Soon")
      const sectionLabel = 'sectionLabel' in item ? (item as NavItem).sectionLabel : undefined;
      const badge = 'badge' in item ? item.badge : undefined;

      return (
        <React.Fragment key={item.path}>
          {sectionLabel && (
            <div className="nav-section-label">{sectionLabel}</div>
          )}
          <div className={level === 0 ? 'nav-group' : 'nav-nested-group'}>
            {hasChildren ? (
              <>
                <button className={itemClass} onClick={() => toggleExpand(item.path)}>
                  {'icon' in item && <span className="nav-icon">{renderIcon(item.icon, level === 0 ? 16 : 14)}</span>}
                  <span className="nav-label">{item.label}</span>
                  {badge && <span className="nav-badge-soon">{badge}</span>}
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
                {badge && <span className="nav-badge-soon">{badge}</span>}
              </span>
            )}
          </div>
        </React.Fragment>
      );
    });
  };

  return (
    <div className="layout">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <button className="mobile-menu-toggle" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} aria-label="Toggle menu">
        {isMobileMenuOpen ? <CloseIcon size={18} /> : <MenuIcon size={18} />}
      </button>
      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <img src="https://app.wecare.digital/stream/media/m/wecare-digital.png" alt="Base CRM" className="sidebar-logo" />
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-main">Base CRM</span>
              <span className="sidebar-brand-sub">by WECARE.DIGITAL</span>
            </div>
          </div>
        </div>
        
        {/* Sidebar Search */}
        <div className="sidebar-search">
          <div className="sidebar-search-input-wrapper">
            <input
              type="text"
              placeholder="Search pages..."
              value={sidebarSearch}
              onChange={e => setSidebarSearch(e.target.value)}
              className="sidebar-search-input"
              aria-label="Search pages"
            />
            {sidebarSearch && (
              <button className="sidebar-search-clear" onClick={() => setSidebarSearch('')}>×</button>
            )}
          </div>
          {filteredNavItems.length > 0 && (
            <div className="sidebar-search-results">
              {filteredNavItems.map(item => (
                <div
                  key={item.path}
                  className="sidebar-search-item"
                  onClick={() => handleSearchItemClick(item.path)}
                >
                  <span className="sidebar-search-item-label">{item.label}</span>
                  {item.parent && <span className="sidebar-search-item-parent">{item.parent}</span>}
                </div>
              ))}
            </div>
          )}
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
      <main id="main-content" className="main-content">
        {showBreadcrumbs && <Breadcrumbs />}
        {children}
      </main>
      <SearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
      <KeyboardShortcuts isOpen={shortcutsModal.isOpen} onClose={shortcutsModal.close} />
    </div>
  );
};

export default Layout;
