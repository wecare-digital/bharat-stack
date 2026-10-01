import React, { useEffect, useState } from 'react';
import { cartCount, CART_CHANGED_EVENT } from '../lib/cart';

/**
 * The Shopping Bag control on the right of the public header.
 *
 * SELF-STYLING, like BrandLockup and RotatingHero. styled-jsx only attaches its scoping class to
 * lowercase DOM tags it can see in the file it compiles, never to a capitalised component, so a
 * `<style jsx>` block in Header.tsx cannot reach in here. The component owns its CSS and Header
 * owns nothing but the placement of the element - which is why `margin-inline-start:auto` is
 * declared below rather than in the parent.
 *
 * A PLAIN <a>, NOT next/link, for the same reason the logo above it is one: styled-jsx cannot
 * scope `<Link className="...">`, and every other row in this header is a plain anchor too. The
 * trailing slash is load-bearing - next.config.js sets trailingSlash, so /cart would 308 before
 * resolving.
 *
 * THE GLYPH IS INLINE SVG, which is a new pattern in this header (the menu chevron is drawn from
 * two borders). It is the right one here: the bag carries a live numeric badge inside it, so it
 * must inherit `currentColor` and re-paint with the control's state, and an <img> from the media
 * CDN would add a request and a layout shift to the first paint of every public page. A standalone
 * copy of the same artwork is committed at public/icons/shopping-bag.svg for upload to the media
 * prefix; nothing in the code points at a hosted URL, because a URL that 404s is worse than no URL.
 *
 * Artwork: Material Symbols Outlined "shopping_bag", 48px, FILL 0 / wght 400 / GRAD 0 / opsz 48,
 * Apache-2.0, recoloured from the stock #1f1f1f to this site's #1a3a2a.
 *
 * THE COUNT IS READ AFTER MOUNT, AND THAT IS NOT LAZINESS. The cart lives in localStorage
 * (src/lib/cart.ts) and these pages are statically exported, so the server render has no cart to
 * read. Rendering a server-side 0 and then swapping it for 3 is a hydration mismatch; rendering
 * nothing until the effect runs is not. `null` therefore means "not read yet" and is distinct from
 * 0, and the badge is absent in both cases - so there is no flash of a wrong number, only a badge
 * that appears.
 *
 * THE NUMBER IS A TEXT NODE, NOT AN ATTRIBUTE. SupportWidget's translation walker rewrites text
 * nodes and never attribute text, so an aria-label carrying the count would stay English in every
 * language (skill §5: 1329 such strings sitewide). The accessible name is therefore built from
 * real text: a visible "Shopping Bag" label and a visually-hidden count phrase. The digits drawn
 * inside the bag are decorative - the glyph is aria-hidden - and carry data-wc-no-translate for
 * the same reason prices do: a regrouped numeral is a different number.
 */

/** Above this, the badge reads as a smudge rather than a number. */
const BADGE_CEILING = 99;

const HeaderCart: React.FC = () => {
  const [ count, setCount ] = useState<number | null>( null );

  useEffect( () => {
    const sync = (): void => setCount( cartCount() );
    sync();
    // `storage` covers another tab; the custom event covers this one, where a write made by
    // /shop/<slug>/'s add-to-cart button does not fire `storage` on its own window.
    window.addEventListener( 'storage', sync );
    window.addEventListener( CART_CHANGED_EVENT, sync );
    return () => {
      window.removeEventListener( 'storage', sync );
      window.removeEventListener( CART_CHANGED_EVENT, sync );
    };
  }, [] );

  const badge = count !== null && count > 0
    ? ( count > BADGE_CEILING ? `${BADGE_CEILING}+` : String( count ) )
    : '';

  /** The spoken half of the name. Absent before the cart has been read, rather than guessed. */
  const spokenCount = count === null
    ? ''
    : count === 0 ? 'empty' : `${count} ${count === 1 ? 'item' : 'items'}`;

  return (
    // A plain anchor rather than next/link: styled-jsx does not scope a capitalised component, so
    // `<Link className="hdr-cart">` would render with none of the CSS below. The logo in Header.tsx
    // and every row of the nav menu carry the same exemption for the same reason.
    // eslint-disable-next-line @next/next/no-html-link-for-pages
    <a className="hdr-cart" href="/cart/">
      <span className="hdr-cart-glyph" aria-hidden="true">
        <svg viewBox="0 -960 960 960" focusable="false">
          <path d="M220-80q-24 0-42-18t-18-42v-520q0-24 18-42t42-18h110v-10q0-63 43.5-106.5T480-880q63 0 106.5 43.5T630-730v10h110q24 0 42 18t18 42v520q0 24-18 42t-42 18H220Zm0-60h520v-520H630v90q0 12.75-8.68 21.37-8.67 8.63-21.5 8.63-12.82 0-21.32-8.63-8.5-8.62-8.5-21.37v-90H390v90q0 12.75-8.68 21.37-8.67 8.63-21.5 8.63-12.82 0-21.32-8.63-8.5-8.62-8.5-21.37v-90H220v520Zm170-580h180v-10q0-38-26-64t-64-26q-38 0-64 26t-26 64v10ZM220-140v-520 520Z" />
        </svg>
        { badge && (
          <span className="hdr-cart-n" data-wc-no-translate="true">{ badge }</span>
        ) }
      </span>
      <span className="hdr-cart-label">Shopping Bag</span>
      { spokenCount && <span className="hdr-cart-spoken">{ spokenCount }</span> }

      <style jsx>{`
        /* THE SAME CHIP AS .nav-trigger, VALUE FOR VALUE, because the two controls sit 10px apart
           and anything else reads as two design languages in one bar: #f4f7ee fill, #cfe0a6
           hairline, 10px radius at rest, and the lime fill with a 2px #1a3a2a edge on
           hover/focus/press. Dark green on lime measures 10.04:1, and the edge rather than the
           fill carries the luminance step - the measurements behind that are recorded on
           .nav-trigger in Header.tsx.
           box-sizing:border-box so the 1px -> 2px border step changes nothing outside the chip.
           margin-inline-start:auto is what puts this on the right of .hdr-in's flex row; it is
           logical, so the control moves to the left edge in a mirrored document on its own.
           flex-shrink:0 because the brand lockup beside it is nowrap - without it a narrow
           viewport squeezes the bag instead of the empty space. */
        .hdr-cart{
          margin-inline-start:auto;flex-shrink:0;
          display:inline-flex;align-items:center;gap:10px;
          min-height:44px;padding:0 12px;box-sizing:border-box;
          background:#f4f7ee;border:1px solid #cfe0a6;border-radius:10px;
          color:#1a3a2a;text-decoration:none;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          font-size:15px;font-weight:700;letter-spacing:-.01em;line-height:1;
          transition:background-color .18s ease,border-color .18s ease,border-width .18s ease;
        }
        .hdr-cart:hover,.hdr-cart:focus-visible{
          background:#d1f470;border-color:#1a3a2a;border-width:2px;outline:none;
        }
        /* The two-tone ring .nav-trigger uses: a 2px white spacer so the ring is not drawn flush
           against the chip it surrounds, then 3px of opaque #1a3a2a, which measures 12.48:1
           against the white header. A single translucent stop was measured at 1.44:1 and failed
           WCAG 1.4.11 on the sibling control. */
        .hdr-cart:focus-visible{box-shadow:0 0 0 2px #fff,0 0 0 5px #1a3a2a}

        /* 30px of glyph inside the 44px target. The bag is drawn FILL@0, so its body is hollow -
           which is the whole reason the number can sit inside it rather than on a separate dot
           pinned to a corner. */
        .hdr-cart-glyph{position:relative;display:inline-flex;flex-shrink:0;inline-size:30px;block-size:30px}
        .hdr-cart-glyph svg{inline-size:30px;block-size:30px;display:block;fill:currentColor}

        /* CENTRED IN THE BAG'S BODY, NOT IN THE ICON BOX. The glyph's viewBox is 0 -960 960 960
           and the body runs from y=-660 to y=-140, so its centre is at y=-400 - which is 58.3%
           of the way down the box, not 50%. 60% is that, rounded to the nearest percent the
           30px box can actually resolve (0.3px steps).
           Dark green digits on the hollow white interior, never lime: lime means actionable on
           this site and a page is allowed one lime surface, which /cart/ spends on its
           Proceed-to-checkout button. tabular-nums so 1 and 11 sit on the same centre. */
        .hdr-cart-n{
          position:absolute;inset-inline-start:50%;inset-block-start:60%;
          transform:translate(-50%,-50%);
          font-size:11px;font-weight:700;line-height:1;letter-spacing:-.02em;
          font-variant-numeric:tabular-nums;color:currentColor;pointer-events:none;
        }

        .hdr-cart-label{white-space:nowrap}

        /* The spoken count is always clipped - it exists so the accessible name carries the
           number, which the decorative digits inside the aria-hidden glyph cannot. clip rather
           than display:none or opacity:0: display:none drops it from the accessible name, and
           opacity:0 would leave it occupying layout. */
        .hdr-cart-spoken{
          position:absolute;inline-size:1px;block-size:1px;padding:0;margin:-1px;
          overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
        }

        /* BELOW 768px THE LABEL IS SPOKEN ONLY, and that is a width calculation rather than a
           preference. Measured on the built header at 280px (Galaxy Fold, folded): the brand
           lockup plus the menu trigger occupy 212.8px of a 248px content box, leaving 35.2px.
           Header.tsx tightens its own gutter below 340px to make room for the 44px chip; there
           is no width at which "Shopping Bag" also fits, and clipping the text keeps it in the
           accessible name while taking no space. The bag is the affordance on a phone, which is
           the convention every storefront already uses. */
        @media(max-width:767px){
          .hdr-cart{gap:0;padding:0;inline-size:44px;justify-content:center}
          .hdr-cart-label{
            position:absolute;inline-size:1px;block-size:1px;padding:0;margin:-1px;
            overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
          }
        }
        @media(prefers-reduced-motion:reduce){
          .hdr-cart{transition:none}
        }
      `}</style>
    </a>
  );
};

export default HeaderCart;
