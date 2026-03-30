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

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';
const CONTACT_URL = 'https://www.wecare.digital/contact';

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
  const [brandDropdownOpen, setBrandDropdownOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('sidebarCollapsed') === 'true';
    }
    return false;
  });
  const shortcutsModal = useKeyboardShortcutsModal();

  // Persist sidebar collapsed state
  useEffect(() => {
    localStorage.setItem('sidebarCollapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

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
    // When sidebar is collapsed, only render top-level items (icons only)
    if (sidebarCollapsed && level > 0) return null;

    // Filter by sidebar search
    const query = sidebarSearch.trim().toLowerCase();
    const matchesSearch = (item: NavItem | NavSubItem): boolean => {
      if (!query) return true;
      if (item.label.toLowerCase().includes(query)) return true;
      if ('children' in item && item.children) return item.children.some(matchesSearch);
      return false;
    };

    return items.filter(matchesSearch).map((item, index) => {
      const hasChildren = 'children' in item && item.children && item.children.length > 0;
      const isExpanded = expandedPaths.has(item.path) || (!!query && hasChildren);
      const isActive = isPathActive(item.path);
      const itemClass = level === 0 
        ? `nav-item ${hasChildren ? 'nav-item-expandable' : ''} ${isActive ? 'nav-item-active' : ''}`
        : `nav-subitem ${hasChildren ? 'nav-subitem-expandable' : ''} ${isActive ? 'nav-subitem-active' : ''}`;

      // Section label (e.g. "Coming Soon")
      const sectionLabel = 'sectionLabel' in item ? (item as NavItem).sectionLabel : undefined;
      const badge = 'badge' in item ? item.badge : undefined;

      // In collapsed mode, clicking a parent nav item navigates to its path
      const handleCollapsedClick = () => {
        if (sidebarCollapsed && hasChildren) {
          router.push(item.path);
        } else if (hasChildren) {
          toggleExpand(item.path);
        } else {
          router.push(item.path);
        }
      };

      return (
        <React.Fragment key={item.path}>
          {sectionLabel && !sidebarCollapsed && (
            <div className="nav-section-label">{sectionLabel}</div>
          )}
          <div className={level === 0 ? 'nav-group' : 'nav-nested-group'}>
            {hasChildren ? (
              <>
                <button className={itemClass} onClick={handleCollapsedClick} title={sidebarCollapsed ? item.label : undefined}>
                  {'icon' in item && <span className="nav-icon">{renderIcon(item.icon, level === 0 ? 16 : 14)}</span>}
                  <span className="nav-label">{item.label}</span>
                  {badge && <span className="nav-badge-soon">{badge}</span>}
                  <span className={`nav-arrow ${isExpanded ? 'expanded' : ''}`}>
                    <ChevronRightIcon size={level === 0 ? 12 : 10} />
                  </span>
                </button>
                {isExpanded && !sidebarCollapsed && (
                  <div className={level === 0 ? 'nav-subitems' : 'nav-nested-items'}>
                    {renderNavItems(item.children!, level + 1)}
                  </div>
                )}
              </>
            ) : (
              <span className={itemClass} onClick={() => router.push(item.path)} title={sidebarCollapsed ? item.label : undefined}>
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
    <>
      <div className={`layout ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <button className="mobile-menu-toggle" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} aria-label="Toggle menu">
        {isMobileMenuOpen ? <CloseIcon size={18} /> : <MenuIcon size={18} />}
      </button>
      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
        {/* Brand */}
        <div style={{padding: '10px 12px 6px', flexShrink: 0, borderBottom: '2px solid #d1f470'}}>
          {!sidebarCollapsed ? (
            <div style={{display: 'flex', alignItems: 'center', gap: 8, minHeight: 46}}>
              <img src={LOGO_URL} alt="" style={{height: 44, width: 'auto', borderRadius: 10, flexShrink: 0}} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              <div style={{display: 'flex', flexDirection: 'column', lineHeight: 1.15}}>
                <span style={{fontSize: 19, fontWeight: 800, color: '#1a3a2a', letterSpacing: '-0.3px'}}>Bharat</span>
                <div style={{display: 'flex', alignItems: 'center', gap: 2}}>
                  <span style={{fontSize: 19, fontWeight: 800, color: '#1a3a2a', letterSpacing: '-0.3px'}}>Stack</span>
                  <span style={{position: 'relative', display: 'inline-flex'}}>
                    <span onClick={() => setBrandDropdownOpen(!brandDropdownOpen)} style={{fontSize: 10, color: '#666', cursor: 'pointer', padding: '0 4px', userSelect: 'none'}}>▼</span>
                    {brandDropdownOpen && (
                      <>
                        <div onClick={() => setBrandDropdownOpen(false)} style={{position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9998}} />
                        <div style={{position: 'absolute', top: 'calc(100% + 4px)', left: 0, background: '#fff', border: '2px solid #d1f470', borderRadius: 12, padding: '8px 0', minWidth: 170, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', zIndex: 9999, display: 'flex', flexDirection: 'column'}}>
                          <a href="/" onClick={() => setBrandDropdownOpen(false)} style={{display: 'block', padding: '10px 20px', fontSize: 14, fontWeight: 500, color: '#1a3a2a', textDecoration: 'none'}}>Home</a>
                          <a href="/dashboard" onClick={() => setBrandDropdownOpen(false)} style={{display: 'block', padding: '10px 20px', fontSize: 14, fontWeight: 500, color: '#1a3a2a', textDecoration: 'none'}}>CRM</a>
                          <a href="/studio" onClick={() => setBrandDropdownOpen(false)} style={{display: 'block', padding: '10px 20px', fontSize: 14, fontWeight: 500, color: '#1a3a2a', textDecoration: 'none'}}>Studio</a>
                          <a href="/sustainability" onClick={() => setBrandDropdownOpen(false)} style={{display: 'block', padding: '10px 20px', fontSize: 14, fontWeight: 500, color: '#1a3a2a', textDecoration: 'none'}}>Sustainability</a>
                          <a href="/access" onClick={() => setBrandDropdownOpen(false)} style={{display: 'block', padding: '10px 20px', fontSize: 14, fontWeight: 500, color: '#1a3a2a', textDecoration: 'none'}}>Sign in</a>
                        </div>
                      </>
                    )}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{display: 'flex', justifyContent: 'center'}}>
              <img src={LOGO_URL} alt="" style={{height: 36, width: 36, borderRadius: 8}} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            </div>
          )}
          <button className="sidebar-collapse-btn" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={sidebarCollapsed ? 'Expand' : 'Collapse'} style={{marginTop: 6}}>
            <ChevronRightIcon size={14} />
          </button>
        </div>
        
        {/* Sidebar Search */}
        {!sidebarCollapsed && (
        <div className="sidebar-search">
          <div className="sidebar-search-input-wrapper">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ marginLeft: 10, flexShrink: 0 }}>
              <path stroke="#1a3a2a" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="m21 21-4.35-4.35M11 6a5 5 0 0 1 5 5m3 0a8 8 0 1 1-16 0 8 8 0 0 1 16 0"/>
            </svg>
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
        </div>
        )}
        
        <nav className="sidebar-nav">
          {renderNavItems(navigationConfig)}
        </nav>
        <div className="sidebar-footer">
          {user && !sidebarCollapsed && (
            <div className="user-info">
              <span className="user-role">{user.role || 'Operator'}</span>
              <span className="user-email">{user.signInDetails?.loginId || user.email}</span>
              <button className="btn-signout" onClick={onSignOut}>Sign Out</button>
            </div>
          )}
          {user && sidebarCollapsed && (
            <button className="btn-signout" onClick={onSignOut} style={{ width: '100%', fontSize: 11 }}>Out</button>
          )}
          {!sidebarCollapsed && (
            <a href={CONTACT_URL} target="_blank" rel="noopener noreferrer" style={{ display: 'block', marginTop: 8, fontSize: 13, fontWeight: 500, color: '#6b7280', textDecoration: 'none', transition: 'color 0.2s' }}>
              Contact Us
            </a>
          )}
        </div>
      </aside>
      {isMobileMenuOpen && <div className="mobile-overlay" onClick={() => setIsMobileMenuOpen(false)} />}
      <main id="main-content" className="main-content">
        {showBreadcrumbs && <Breadcrumbs />}
        <div className="inner-content-container">
          {children}
        </div>
      </main>
      <SearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
      <KeyboardShortcuts isOpen={shortcutsModal.isOpen} onClose={shortcutsModal.close} />
    </div>
    </>
  );
};

export default Layout;
