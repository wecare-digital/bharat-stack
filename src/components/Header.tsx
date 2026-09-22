import React, { useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import BrandLockup from './BrandLockup';

interface HeaderProps {
  homeBrand?: boolean;
}

interface NavLink {
  label: string;
  href: string;
  /** router.pathname value that marks this link as the current page. */
  match?: string;
  /** Group heading. Empty string means "render with no heading above it". */
  group: '' | 'Products' | 'Service' | 'Account';
}

// One list, grouped by type, rather than four hand-written anchors.
//
// Selfservice and Partners are ABSOLUTE URLs onto the marketing site, and the two
// pages that used to back them (src/pages/faq.tsx, src/pages/partners.tsx) are
// gone along with their entries in the isPublic allowlist in _app.tsx. Keep them
// absolute: pointing these at local routes again resurrects two pages that no
// longer exist and the allowlist would render them as a blank 200.
//
// They open in the SAME tab, which is why neither carries target="_blank". That is
// the default for a plain anchor, so it is the absence of an attribute doing the
// work here - do not "fix" it by adding target, and note rel="noopener" would be
// inert without one.
//
// Neither external entry has a `match`: it is compared against router.pathname,
// which can never equal an absolute URL, so a value there would be misleading
// dead weight.
//
// Trailing slashes are load-bearing on the static pages: next.config.js sets
// trailingSlash, so /vayulok would redirect before resolving. /access is bare
// deliberately - it is the authenticated entry point, not an exported public page
// - but it still needs `match`, because without it the Sign in row was the only
// item in this menu that never lit up on its own page: every other route got the
// lime .22 active tint at weight 800 and /access stayed transparent at 600.
const LINKS: NavLink[] = [
  { label: 'Home', href: '/', match: '/', group: '' },
  { label: 'Grahak OS', href: '/grahak-os/', match: '/grahak-os', group: 'Products' },
  { label: 'VayuLok', href: '/vayulok/', match: '/vayulok', group: 'Products' },
  { label: 'Selfservice', href: 'https://www.wecare.digital/selfservice', group: 'Service' },
  { label: 'Partners', href: 'https://www.wecare.digital/product-page/referral-partner', group: 'Service' },
  { label: 'Sign in', href: '/access', match: '/access', group: 'Account' },
];

// 'Service', not 'Company'. Neither row under it is about the company: one is the
// customer self-help portal and the other is a product page for prospective
// referral partners, so the old heading described the wrong thing.
//
// This union is the only place a group name is declared - the headings render
// straight from these strings and GROUP_ORDER below sets their order - so renaming
// a group means editing the type, the LINKS entries and this array together, and
// tsc catches it if you miss one. No test asserts on the heading text.
const GROUP_ORDER: Array<NavLink[ 'group' ]> = [ '', 'Products', 'Service', 'Account' ];

const Header: React.FC<HeaderProps> = ( { homeBrand = false } ) => {
  const [ open, setOpen ] = useState( false );
  const [ query, setQuery ] = useState( '' );
  const router = useRouter();

  const term = query.trim().toLocaleLowerCase();
  const searching = term.length > 0;

  const filtered = useMemo( () => (
    searching ? LINKS.filter( link => link.label.toLocaleLowerCase().includes( term ) ) : LINKS
  ), [ searching, term ] );

  const close = () => { setOpen( false ); setQuery( '' ); };

  // Driven off router.pathname, which carries no trailing slash even though the
  // hrefs do - hence the separate `match` field.
  //
  // This returns a BOOLEAN, and className is written inline on each anchor, on
  // purpose. Returning a props object and spreading it silently broke the whole
  // menu: styled-jsx appends its own className attribute AFTER a spread, so the
  // spread's className lost and every anchor exported as class="jsx-hash" with no
  // nav-item on it at all - no padding, no row height, no hover, no active weight.
  // The 33 unit tests still passed, because they assert role, name and href and
  // never look at classes. Only reading the built HTML caught it.
  const isActive = ( link: NavLink ) => link.match !== undefined && router.pathname === link.match;

  return (
    <header className={ `hdr ${homeBrand ? 'hdr-home' : ''}`.trim() }>
      <div className="hdr-in">
        <div className="logo-nav">
          <a href="/" className="logo" aria-label="Bharat Stack home">
            <BrandLockup />
          </a>
          <div className="nav-dropdown">
            {/* This must stay the FIRST button in the header. Header.test.tsx reaches
                the trigger with container.querySelector('button') to assert the chevron
                is drawn rather than typed, so the search field below is an input and no
                control is added ahead of this element. */}
            <button
              type="button"
              className="nav-trigger"
              aria-label="Open navigation"
              aria-expanded={ open }
              onClick={ () => { setOpen( value => !value ); setQuery( '' ); } }
            >
              <span className="nav-arrow" aria-hidden="true" />
            </button>
            <nav className={ `nav-menu ${open ? 'open' : ''}` } aria-label="Public navigation">
              {/* Not autofocused. The language panel autofocuses its search because
                  searching is the only way to use it, but this menu is readable at a
                  glance - popping the on-screen keyboard over a six-item list on a
                  phone would cost more than it saves. */}
              <input
                className="nav-search"
                type="search"
                value={ query }
                placeholder="Search"
                aria-label="Search navigation"
                onChange={ event => setQuery( event.target.value ) }
                onKeyDown={ event => { if ( event.key === 'Escape' ) close(); } }
              />

              {/* Flat results while searching: group headings over a filtered list
                  describe categories that are no longer all present, which reads as
                  missing items rather than as a narrowed list. */}
              { searching && filtered.map( link => (
                <a
                  key={ link.href }
                  href={ link.href }
                  className={ `nav-item ${isActive( link ) ? 'active' : ''}`.trim() }
                  aria-current={ isActive( link ) ? 'page' : undefined }
                  onClick={ close }
                >{ link.label }</a>
              ) ) }
              { searching && !filtered.length && (
                <p className="nav-empty">No matching page.</p>
              ) }

              { !searching && GROUP_ORDER.map( group => {
                const items = LINKS.filter( link => link.group === group );
                if ( !items.length ) return null;
                return (
                  <div key={ group || 'ungrouped' } className="nav-group">
                    { group && <span className="nav-group-label">{ group }</span> }
                    { items.map( link => (
                      <a
                        key={ link.href }
                        href={ link.href }
                        className={ `nav-item ${isActive( link ) ? 'active' : ''}`.trim() }
                        aria-current={ isActive( link ) ? 'page' : undefined }
                        onClick={ close }
                      >{ link.label }</a>
                    ) ) }
                  </div>
                );
              } ) }
            </nav>
          </div>
        </div>
      </div>
      <style jsx>{`
        .hdr{position:fixed;top:0;left:0;right:0;z-index:1001;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
        .hdr-in{max-width:1300px;margin:0 auto;padding:18px 24px;display:flex;align-items:center;box-sizing:border-box;height:108px}
        .logo{display:flex;align-items:center;text-decoration:none}
        .logo-nav{display:flex;align-items:center;gap:10px}
        .nav-dropdown{position:relative}
        .nav-trigger{min-width:46px;min-height:46px;background:none;border:0;border-radius:10px;cursor:pointer;padding:8px;display:flex;align-items:center;justify-content:center}
        .nav-trigger:hover,.nav-trigger:focus-visible{background:rgba(209,244,112,.22);outline:none}
        .nav-trigger:focus-visible{box-shadow:0 0 0 3px rgba(26,58,42,.2)}
        .nav-trigger[aria-expanded='true']{background:rgba(209,244,112,.22)}
        .nav-arrow{width:7px;height:7px;box-sizing:border-box;margin:0;border-right:2px solid #1a3a2a;border-bottom:2px solid #1a3a2a;transform:translateY(-2px) rotate(45deg);transition:transform .2s}
        .nav-trigger[aria-expanded='true'] .nav-arrow{transform:translateY(2px) rotate(225deg)}
        /* min-width went 216 -> 268px with the search field: a 19px item plus a full
           width input needs the room, and "Grahak OS" must not sit against the padding. */
        .nav-menu{position:absolute;top:calc(100% + 4px);left:0;background:#fff;border:1px solid #d1f470;border-radius:10px;padding:10px 0;min-width:268px;opacity:0;visibility:hidden;transform:translateY(4px);transition:all .2s;box-shadow:0 8px 28px rgba(0,0,0,.10)}
        .nav-dropdown:hover .nav-menu,.nav-dropdown:focus-within .nav-menu,.nav-menu.open{opacity:1;visibility:visible;transform:translateY(0)}

        /* Search field. Sized off the language panel's input rather than a new set of
           numbers - same 42px row, same 10px radius, same focus ring - so the two
           search fields on the site are recognisably the same control. */
        .nav-search{width:calc(100% - 28px);margin:2px 14px 8px;min-height:42px;box-sizing:border-box;border:1px solid rgba(0,0,0,.12);border-radius:10px;padding:10px 12px;font-size:15px;font-weight:400;line-height:1.3;color:rgba(0,0,0,.898);font-family:inherit;outline:none}
        .nav-search::placeholder{color:rgba(0,0,0,.42)}
        .nav-search:focus{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(26,58,42,.1)}

        /* 12px/500 muted, matching the language panel's group label. A heading over
           menu items must read as a category and not as a disabled item, which is why
           it is well below the 19px the items themselves use. */
        .nav-group{display:flex;flex-direction:column}
        .nav-group + .nav-group{margin-top:6px;padding-top:6px;border-top:1px solid #e5e7eb}
        .nav-group-label{padding:6px 22px 2px;font-size:12px;font-weight:500;letter-spacing:.04em;color:rgba(0,0,0,.42)}
        .nav-empty{margin:0;padding:10px 22px 12px;font-size:14px;color:rgba(0,0,0,.5)}

        /* 15px/46px was undersized against a 108px header and a 24px brand lockup,
           and it sat below the 16-17px the global .nav-item rules use for the same
           control elsewhere. 17px on a 54px row also clears the 44px minimum touch
           target with room to spare. min-width went with it so "Grahak OS" cannot
           end up near the padding at the larger size. */
        /* Sized in two passes, and the first one was wrong in a way worth recording:
           the row went to 54px while the type only went to 17px, so the box grew
           proportionally more than the glyphs and the text read SMALLER than before
           rather than larger. 19px puts the type-to-row ratio at ~2.8, near the
           2.5-ish a notion-style menu sits at, and keeps a deliberate step down from
           the 24px brand lockup instead of near-matching it.
           Nothing global was fighting this: the styled-jsx rule carries a jsx class,
           so it beats Layout.css's plain .nav-item on specificity, and
           inner-pages.css's .layout .nav-item block is empty and out of scope for the
           public header anyway. */
        .nav-item{display:flex;align-items:center;min-height:54px;padding:0 22px;font-size:19px;font-weight:600;color:#1a3a2a;text-decoration:none}
        .nav-item:hover,.nav-item:focus-visible,.nav-item.active{background:rgba(209,244,112,.22);outline:none}
        .nav-item.active{font-weight:800}
        /* The .nav-item override here is NOT redundant with the base rule: Layout.css
           declares .nav-item inside its own mobile media queries at 16px and 17px, and
           it is imported globally by _app.tsx. This keeps the public header's size its
           own decision at the breakpoint where those rules switch on. */
        /* The panel breaks out of the dropdown's relative box below 768px. Anchored
           to the trigger it is 268px wide starting about 152px in, which ran 60px past
           a 360px viewport - and the old 216px panel overflowed here too, by 8px, it
           was just less visible. Fixed to the viewport with a 16px gutter each side
           instead, sitting just under the 96px mobile header.
           NOTE: .hdr-in must stay the first rule inside this media query - Header.test
           asserts the literal string "@media(max-width:767px){.hdr-in{height:96px". */
        @media(max-width:767px){.hdr-in{height:96px;padding:14px 16px}.logo-nav{gap:8px}.nav-item{font-size:19px;min-height:56px}.nav-menu{position:fixed;top:100px;left:16px;right:16px;min-width:0;width:auto}}
      `}</style>
    </header>
  );
};

export default Header;
