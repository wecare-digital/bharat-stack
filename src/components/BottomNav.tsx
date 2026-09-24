/**
 * Phone bottom bar — phase 8.3's adaptive navigation, thumb end.
 *
 * WHY A BOTTOM BAR WHEN A DRAWER ALREADY WORKED
 * ---------------------------------------------
 * The hamburger drawer is functional, and that is exactly the problem with leaving it
 * as the only phone navigation: it costs a tap to open, it covers the page you were
 * reading, and its targets sit at the TOP of a 6-inch screen where a thumb does not
 * reach. The drawer stays — it is how you get to all 95 destinations — but the streams
 * you switch between hourly belong within thumb reach.
 *
 * FIVE, NOT EIGHT
 * ---------------
 * `navigationConfig` has eight top-level entries. Eight targets across a phone width
 * gives each about 45px, below the 44px minimum once padding is taken off, and the
 * labels truncate to nonsense. So the bar shows the first four and a "More" button that
 * opens the same drawer. Four plus More is a deliberate cut, not a truncation: the
 * drawer is one tap away and holds everything.
 *
 * THE Z-INDEX IT MUST NOT FIGHT
 * -----------------------------
 * `#wecarewa-widget` is injected by an external script at `right:16px bottom:120px`,
 * 64x64, with `z-index: 2147483647` — the maximum 32-bit integer, so nothing can ever
 * be stacked above it. This bar is 60px tall at `bottom:0`, so it occupies 0–60px and
 * the widget occupies 120–184px. They clear each other GEOMETRICALLY, which is the only
 * way to win against that z-index. Raising this bar's height past ~120px would put the
 * green circle through it.
 *
 * SAFE AREA
 * ---------
 * `env(safe-area-inset-bottom)` keeps the row above the iPhone home indicator. Without
 * it the last 34px of the bar is unreachable on any notched device, which is the
 * WebView/WKWebView readiness the owner's override requires the web app to keep.
 */
import React from 'react';
import { useRouter } from 'next/router';
import { navigationConfig, isNavItemActive } from '../config/navigation';
import { IconMap, MenuIcon } from '../lib/icons';

interface BottomNavProps {
  /** Opens the existing drawer. The bar does not own a second navigation surface. */
  onMore: () => void;
  moreOpen?: boolean;
}

/** Four streams plus More. See the note above on why not eight. */
const PRIMARY_COUNT = 4;

const BottomNav: React.FC<BottomNavProps> = ( { onMore, moreOpen } ) => {
  const router = useRouter();
  const items = navigationConfig.slice( 0, PRIMARY_COUNT );

  const renderIcon = ( iconName?: string ) => {
    if ( !iconName ) return null;
    const Icon = IconMap[ iconName ];
    return Icon ? <Icon size={ 20 } /> : null;
  };

  return (
    <nav className="bottom-nav" aria-label="Primary">
      { items.map( ( item ) => {
        const active = isNavItemActive( item, router.pathname );
        return (
          <button
            key={ item.path }
            type="button"
            className={ `bn-item ${active ? 'active' : ''}` }
            aria-current={ active ? 'page' : undefined }
            onClick={ () => router.push( item.path ) }
          >
            <span className="bn-icon">{ renderIcon( item.icon ) }</span>
            <span className="bn-label">{ item.label }</span>
          </button>
        );
      } ) }
      <button
        type="button"
        className={ `bn-item ${moreOpen ? 'active' : ''}` }
        onClick={ onMore }
        aria-expanded={ !!moreOpen }
        aria-label="More navigation"
      >
        <span className="bn-icon"><MenuIcon size={ 20 } /></span>
        <span className="bn-label">More</span>
      </button>
    </nav>
  );
};

export default BottomNav;
