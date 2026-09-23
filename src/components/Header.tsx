import React, { useEffect, useMemo, useRef, useState } from 'react';
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
  /** True for absolute URLs off this app. Same tab either way - see PENDING_HREF. */
  external?: boolean;
}

interface NavSection {
  /** '' renders the links with no heading above them. */
  heading: string;
  /** When set, the heading itself is a link. Used by Selfservice, which is both a
   *  real destination and the parent of the rows beneath it. */
  headingHref?: string;
  links: NavLink[];
}

/** One column of the mega menu. Columns may hold more than one section. */
interface NavColumn {
  sections: NavSection[];
}

const SELFSERVICE = 'https://www.wecare.digital/selfservice';
const PARTNERS = 'https://www.wecare.digital/product-page/referral-partner';

// PLACEHOLDER, pending the owner's per-service URLs.
//
// Every Selfservice child points at the Selfservice landing page for now. That is a
// deliberate choice over href="#" or a guessed path: "#" scrolls the page to the top
// and looks broken, and an invented path like /selfservice/submit-request would 404
// on the marketing site. Pointing at the parent means every row in the menu works
// today and lands the visitor one click from what they wanted.
//
// To wire the real links: replace PENDING_HREF on each row below with its URL. The
// constant is referenced rather than inlined so `grep PENDING_HREF` lists exactly
// what is still outstanding, and Header.test.tsx asserts all seven rows exist so a
// typo during that edit cannot silently drop one.
const PENDING_HREF = SELFSERVICE;

// One structure, rendered as columns, rather than the single flat list this used to
// be. The Selfservice group is why: seven children under one parent made a
// single-column dropdown roughly 700px tall, past the bottom of a laptop viewport.
//
// Trailing slashes are load-bearing on the static pages: next.config.js sets
// trailingSlash, so /vayulok would redirect before resolving. /access is bare
// deliberately - it is the authenticated entry point, not an exported public page -
// but it still needs `match`, or the Sign in row is the only item in this menu that
// never lights up on its own page.
//
// The external entries carry no target, so they open in the SAME tab. That is the
// default for a plain anchor, so it is the ABSENCE of an attribute doing the work -
// do not "fix" it by adding target, and note rel="noopener" would be inert without
// one. They also carry no `match`: it is compared against router.pathname, which can
// never equal an absolute URL.
const COLUMNS: NavColumn[] = [
  {
    sections: [
      { heading: '', links: [ { label: 'Home', href: '/', match: '/' } ] },
      {
        heading: 'Products',
        links: [
          { label: 'Grahak OS', href: '/grahak-os/', match: '/grahak-os' },
          { label: 'VayuLok', href: '/vayulok/', match: '/vayulok' },
          // Bharat Rx moved here from Selfservice: it is a product, not one of the
          // request actions the Selfservice column lists. Still on PENDING_HREF -
          // it has no page of its own yet, so it points at the marketing site.
          { label: 'Bharat Rx', href: PENDING_HREF, external: true },
        ],
      },
    ],
  },
  {
    sections: [
      {
        heading: 'Selfservice',
        headingHref: SELFSERVICE,
        links: [
          // FAQ removed on request. The local /faq page was already deleted; this
          // drops the menu row too, so there is no FAQ entry point left anywhere.
          { label: 'Submit Request', href: PENDING_HREF, external: true },
          { label: 'Request Amendment', href: PENDING_HREF, external: true },
          // "My Order" REPLACES the old "Request Tracking" row rather than sitting beside
          // it: the two answer the same question, and offering both sends one visitor to
          // two places for one answer. Unlike its siblings this is a local page, so it
          // carries `match` and lights up on its own route.
          { label: 'My Order', href: '/my-order/', match: '/my-order' },
          { label: 'Drop Docs', href: PENDING_HREF, external: true },
          { label: 'Leave Review', href: PENDING_HREF, external: true },
          // Local pages, so these carry `match` and light up on their own route.
          // Trailing slashes are load-bearing: trailingSlash is set, so /contact
          // would redirect before resolving.
          { label: 'Contact', href: '/contact/', match: '/contact' },
        ],
      },
      {
        // "Legal Stuff", matching the heading on the published document this content
        // came from, rather than the shorter "Legal" used while it was a placeholder.
        //
        // Privacy IS listed now. It was deliberately absent while its text was a
        // placeholder - an unfindable page was preferable to advertising an empty
        // policy - and the owner asked for it once the real policy landed. Header.test
        // asserts both rows, so the earlier guard against adding Privacy is retired
        // rather than silently broken.
        heading: 'Legal Stuff',
        links: [
          { label: 'Terms', href: '/terms/', match: '/terms' },
          { label: 'Privacy', href: '/privacy/', match: '/privacy' },
        ],
      },
    ],
  },
  {
    sections: [
      // "Work with us", NOT "Company" - that word was explicitly retired from this
      // menu, and restructuring into columns nearly reintroduced it. Not "Service"
      // either: that would sit one column away from "Selfservice" and read as the
      // same category. This heading says who the column is for, which is the honest
      // distinction - Selfservice is for existing customers, this is for prospective
      // referral partners.
      { heading: 'Work with us', links: [ { label: 'Partners', href: PARTNERS, external: true } ] },
      { heading: 'Account', links: [ { label: 'Sign in', href: '/access', match: '/access' } ] },
    ],
  },
];

const Header: React.FC<HeaderProps> = ( { homeBrand = false } ) => {
  const [ open, setOpen ] = useState( false );
  const [ query, setQuery ] = useState( '' );
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement | null>( null );
  const triggerRef = useRef<HTMLButtonElement | null>( null );
  const hasOpened = useRef( false );

  const term = query.trim().toLocaleLowerCase();
  const searching = term.length > 0;

  // Flattened once, from the same structure the columns render, so a link can never
  // exist in the menu but be missing from search.
  const allLinks = useMemo( () => COLUMNS.flatMap( column => column.sections.flatMap( section => (
    section.headingHref
      ? [ { label: section.heading, href: section.headingHref, external: true }, ...section.links ]
      : section.links
  ) ) ), [] );

  const filtered = useMemo( () => (
    searching ? allLinks.filter( link => link.label.toLocaleLowerCase().includes( term ) ) : allLinks
  ), [ allLinks, searching, term ] );

  const close = () => { setOpen( false ); setQuery( '' ); };

  // Escape closes from anywhere, and an outside pointerdown dismisses. Neither
  // existed before: the menu could only be closed by clicking the trigger again or
  // following a link, so Escape did nothing and a click elsewhere left it open over
  // the page. Matches the language widget, so both menus answer to the same keys.
  useEffect( () => {
    if ( !open ) return undefined;
    const onKeyDown = ( event: KeyboardEvent ) => { if ( event.key === 'Escape' ) close(); };
    const onPointerDown = ( event: PointerEvent ) => {
      if ( rootRef.current && !rootRef.current.contains( event.target as Node ) ) close();
    };
    document.addEventListener( 'keydown', onKeyDown );
    document.addEventListener( 'pointerdown', onPointerDown );
    return () => {
      document.removeEventListener( 'keydown', onKeyDown );
      document.removeEventListener( 'pointerdown', onPointerDown );
    };
  }, [ open ] );

  // Focus returns to the trigger on close, so a keyboard user is not dropped onto
  // <body> and made to tab from the top of the document again.
  useEffect( () => {
    if ( open ) { hasOpened.current = true; return; }
    if ( hasOpened.current ) triggerRef.current?.focus();
  }, [ open ] );

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

  // NO renderLink() HELPER. The anchor markup is duplicated inline in both branches
  // below, on purpose, and it must stay that way.
  //
  // It was briefly a shared renderLink( link, extraClass ) helper, which silently
  // unstyled the entire menu. styled-jsx only attaches its scoping class to JSX it
  // can see statically inside the return tree; markup produced by a separate function
  // gets a different hash, so none of the .nav-item rules in the style block below
  // matched, and every row fell through to the unscoped global .nav-item in
  // Layout.css:659 - 15px at weight 560 with no lime hover and no active tint.
  //
  // This is the first trap in the design contract, and it is invisible to the tests:
  // 112 browser assertions passed while every row was unstyled, because they assert
  // text, href and aria-current and never read computed style. Only
  // CSS.getMatchedStylesForNode showed that the jsx rules were not matching at all.
  // megamenu.js now asserts computed font-size, weight and the active background so
  // this cannot recur silently.

  return (
    <header className={ `hdr ${homeBrand ? 'hdr-home' : ''}`.trim() }>
      <div className="hdr-in">
        <div className="logo-nav">
          <a href="/" className="logo" aria-label="WECARE.DIGITAL home">
            <BrandLockup />
          </a>
          <div className="nav-dropdown" ref={ rootRef }>
            {/* This must stay the FIRST button in the header. Header.test.tsx reaches
                the trigger with container.querySelector('button') to assert the chevron
                is drawn rather than typed, so the search field below is an input and no
                control is added ahead of this element. */}
            <button
              ref={ triggerRef }
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
                  glance - popping the on-screen keyboard over the whole catalogue on a
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

              {/* Flat results while searching: column headings over a filtered list
                  describe categories that are no longer all present, which reads as
                  missing items rather than as a narrowed list. */}
              { searching && (
                <div className="nav-results">
                  { filtered.map( link => (
                    <a
                      key={ link.label + link.href }
                      href={ link.href }
                      className={ `nav-item ${isActive( link ) ? 'active' : ''}`.trim() }
                      aria-current={ isActive( link ) ? 'page' : undefined }
                      onClick={ close }
                    >{ link.label }</a>
                  ) ) }
                  { !filtered.length && <p className="nav-empty">No matching page.</p> }
                </div>
              ) }

              { !searching && (
                <div className="nav-cols">
                  { COLUMNS.map( ( column, columnIndex ) => (
                    <div key={ columnIndex } className="nav-col">
                      { column.sections.map( ( section, sectionIndex ) => (
                        <div key={ section.heading || sectionIndex } className="nav-group">
                          { section.heading && ( section.headingHref
                            ? (
                              // The heading is the parent destination as well as a
                              // label, so it is a link. Styled as a heading rather
                              // than as a row so the hierarchy still reads.
                              <a
                                href={ section.headingHref }
                                className="nav-group-label nav-group-link"
                                onClick={ close }
                              >{ section.heading }</a>
                            )
                            : <span className="nav-group-label">{ section.heading }</span>
                          ) }
                          { section.links.map( link => (
                            <a
                              key={ link.label + link.href }
                              href={ link.href }
                              className={ `nav-item ${section.headingHref ? 'nav-sub' : ''} ${isActive( link ) ? 'active' : ''}`.trim() }
                              aria-current={ isActive( link ) ? 'page' : undefined }
                              onClick={ close }
                            >{ link.label }</a>
                          ) ) }
                        </div>
                      ) ) }
                    </div>
                  ) ) }
                </div>
              ) }
            </nav>
          </div>
        </div>
      </div>
      <style jsx>{`
        /* OPAQUE BY DEFAULT, translucent only where the blur actually works.
           It was rgba(255,255,255,.97) with backdrop-filter:blur(20px) unconditionally.
           Measured, backdrop-filter computes to the keyword none in environments that
           do not support it - and without the blur the 3% translucency is not a frosted
           effect, it is just bleed-through. On the marketing pages that is invisible
           because almost nothing scrolls under the header; on /terms/ and /privacy/,
           which are 40,000 characters of dense prose, lines were faintly legible
           through it and behind the logo.
           So the base rule is a solid #fff, and the translucent treatment is restored
           inside @supports where the blur it depends on is real. */
        .hdr{position:fixed;top:0;left:0;right:0;z-index:1001;background:#fff}
        @supports ((backdrop-filter:blur(20px)) or (-webkit-backdrop-filter:blur(20px))){
          .hdr{background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
        }
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

        /* MEGA PANEL.
           WIDTH IS 760px, NOT THE PAGE MEASURE. It was first built at the site's
           1252px measure, which measured 1252x393 with its three columns only
           158/308/148px tall - a panel more than half empty, and it looked it. Twelve
           rows do not need the full page width. 760px is what the content asks for:
           the widest label, "Request Amendment" at 17px/600, needs ~210px of row, so
           three of those plus the 20px gutters and 14px padding comes to ~700px.
           Anchored left of the trigger rather than centred, because a narrow panel
           centred in the viewport under a left-aligned trigger reads as unrelated to
           it. min() against calc(100vw - 256px) is what stops the absolute
           positioning overflowing on a narrow window before the mobile rule takes
           over.

           THAT 256 IS COUPLED TO THE BRAND LOCKUP'S WIDTH, and it has now been wrong
           twice. The panel's left edge is wherever the lockup plus the trigger ends:
           a first attempt reserved 176px from a guessed 152px offset and overflowed
           by 4px at 900px wide; measuring gave 180px, so it became 208; then the logo
           was sized up from 60px to 68px, the offset moved to 225px, and 208 overflowed
           again at 768-960px. 225 + 24px of gutter is 249, taken to 256.
           So: if BrandLockup's logo height or type size changes, THIS NUMBER MOVES.
           Re-measure it, do not nudge it - the width sweep in megamenu.js is what
           catches it, and it caught both of these.

           max-height CLEARS THE WHATSAPP BUTTON GEOMETRICALLY, which is the only way
           to clear it. #wecarewa-widget is injected by an external script at
           z-index 2147483647, the maximum 32-bit integer, so nothing can ever be
           stacked above it - measured here, the full-height mobile panel ran straight
           through it and the green circle painted over the Selfservice rows. The
           design contract records this for .wc-langbar; it applies to any floating
           panel. The measured footprint (60x60, 80px from the bottom) does not match
           the documented one (64x64, 120px), so the reserve clears the LARGER of the
           two plus a gap. overflow-y:auto is what keeps the rows reachable once the
           panel is capped.

           z-index is declared rather than left at auto. It cannot win against the
           widget above, but leaving it implicit meant the panel's stacking depended
           entirely on .hdr's context, which is fragile to reorder.

           Opening is driven ONLY by React state now. It used to also open on
           :hover and :focus-within, which meant the panel could be visible while
           aria-expanded was false - the arrow unrotated and a screen reader announcing
           it as collapsed. A mega panel appearing on an accidental mouse-over is also
           far more disruptive than a small dropdown was. */
        .nav-menu{position:absolute;top:calc(100% + 8px);left:0;z-index:1002;width:min(760px,calc(100vw - 256px));max-height:calc(100vh - 320px);overflow-y:auto;-webkit-overflow-scrolling:touch;background:#fff;border:1px solid #d1f470;border-radius:14px;padding:14px;opacity:0;visibility:hidden;transform:translateY(4px);transition:opacity .2s,transform .2s,visibility 0s linear .2s;box-shadow:0 8px 28px rgba(0,0,0,.10)}
        .nav-menu.open{opacity:1;visibility:visible;transform:translateY(0);transition:opacity .2s,transform .2s,visibility 0s}

        /* Search field. Sized off the language panel's input rather than a new set of
           numbers - same 42px row, same 10px radius, same focus ring - so the two
           search fields on the site are recognisably the same control. */
        .nav-search{width:100%;margin:0 0 12px;min-height:42px;box-sizing:border-box;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;font-size:15px;font-weight:400;line-height:1.3;color:rgba(0,0,0,.898);font-family:inherit;outline:none}
        .nav-search::placeholder{color:rgba(0,0,0,.42)}
        .nav-search:focus{border-color:#1a3a2a;box-shadow:0 0 0 3px rgba(209,244,112,.3)}

        /* Three equal columns with minmax(0,1fr) rather than 1fr: a bare 1fr uses
           min-content as its floor, so "Request Amendment" would force its column
           wider than a third and push the others narrow. */
        .nav-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 20px;align-items:start}
        .nav-col{display:flex;flex-direction:column;gap:10px;min-width:0}
        .nav-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:2px 20px}

        /* 12px/500 muted, matching the language panel's group label. A heading over
           menu items must read as a category and not as a disabled item, which is why
           it is well below the 19px the items themselves use. */
        .nav-group{display:flex;flex-direction:column}
        .nav-group-label{display:block;padding:6px 12px 4px;font-size:12px;font-weight:500;letter-spacing:.04em;color:rgba(0,0,0,.42);text-transform:none}
        /* The Selfservice heading is a link, so it needs an affordance the plain
           headings do not have - without one it looks like the same inert label. */
        .nav-group-link{color:#1a3a2a;text-decoration:none;border-radius:8px}
        .nav-group-link:hover,.nav-group-link:focus-visible{background:rgba(209,244,112,.22);outline:none}
        .nav-empty{margin:0;padding:10px 12px 12px;font-size:14px;color:rgba(0,0,0,.54)}

        /* 15px/46px was undersized against a 108px header and a 24px brand lockup,
           and it sat below the 16-17px the global .nav-item rules use for the same
           control elsewhere. 19px puts the type-to-row ratio at ~2.8, near the
           2.5-ish a notion-style menu sits at, and keeps a deliberate step down from
           the 24px brand lockup instead of near-matching it.
           Nothing global was fighting this: the styled-jsx rule carries a jsx class,
           so it beats Layout.css's plain .nav-item on specificity, and
           inner-pages.css's .layout .nav-item block is empty and out of scope for the
           public header anyway.
           The row is 46px here, not the 54px of the old single column: three columns
           of 19px rows at 54px made the panel taller than the Selfservice list needs,
           and 46px still clears the 44px minimum touch target. */
        .nav-item{display:flex;align-items:center;min-height:46px;padding:0 12px;font-size:19px;font-weight:600;color:#1a3a2a;text-decoration:none;border-radius:8px}
        .nav-item:hover,.nav-item:focus-visible,.nav-item.active{background:rgba(209,244,112,.22);outline:none}
        .nav-item.active{font-weight:800}
        /* Children of a linked heading step down to 17px. Same weight and colour, so
           they read as the same kind of thing at a lower level rather than as a
           different control - and the size difference is what carries the hierarchy
           now that indentation alone would be ambiguous inside a column. */
        .nav-sub{font-size:17px;min-height:42px}

        /* The panel breaks to fewer columns before the columns get too narrow to hold
           "Request Amendment" on one line. Measured rather than guessed: at 19px/17px
           the widest label needs ~210px of row, so three columns stop fitting inside
           the 1252px measure once the viewport is under ~820px. */
        @media(max-width:1024px){.nav-cols,.nav-results{grid-template-columns:repeat(2,minmax(0,1fr))}}
        /* NOTE: .hdr-in must stay the first rule inside this media query - Header.test
           asserts the literal string "@media(max-width:767px){.hdr-in{height:96px".
           Below 768px the panel is a single scrolling column pinned to the viewport
           with a 16px gutter, sitting just under the 96px mobile header. max-height
           plus overflow-y is what stops twelve rows running off the bottom of a
           phone - the old six-item dropdown never needed it. */
        @media(max-width:767px){.hdr-in{height:96px;padding:14px 16px}.logo-nav{gap:8px}.nav-menu{position:fixed;top:100px;left:16px;right:16px;width:auto;max-height:calc(100vh - 308px)}.nav-cols,.nav-results{grid-template-columns:minmax(0,1fr)}.nav-item{font-size:19px;min-height:52px}.nav-sub{font-size:17px;min-height:46px}}

        @media(prefers-reduced-motion:reduce){
          .nav-menu{transition:none}
          .nav-arrow{transition:none}
        }
      `}</style>
    </header>
  );
};

export default Header;
