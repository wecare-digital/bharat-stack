import React from 'react';
import BrandMark from './BrandMark';

interface BrandBadgeProps {
  /** Full label, e.g. "Grahak OS · by Bharat Stack". */
  label: string;
}

/**
 * Small pill naming a product and its maker, sat above a page headline.
 *
 * Self-styling on purpose. styled-jsx does not scope composite components, so a
 * consuming page's `<style jsx>` cannot reach these class names and passing a
 * className in from the page would arrive unstyled — the same reason BrandLockup
 * carries its own block. Spacing is therefore NOT set here: the consumer wraps
 * this in an element it can style, or relies on its own flex gap.
 *
 * Neither class is called `badge`. Four globally imported stylesheets
 * (Dashboard, Pages, inner-pages, flex-layout) declare `.badge` unscoped, and
 * styled-jsx does not shield a page from those.
 *
 * Green comes from the lime the palette already owns, NOT from a new pale green.
 * The reference mock's fill was the near-miss-green family the contract retired
 * (#f2fbf6, #fbfff0).
 *
 * Fill is #d1f470 at FULL strength with #1a3a2a type — the same pair as
 * .tab.active and .msg.sent, which is the palette's established treatment for our
 * own surfaces and is pinned by a test on the Grahak OS page. It started at
 * rgba(209,244,112,.22), the Header nav-hover tint, but that composites to
 * (245,253,224) over white: a pale wash that read as barely-not-white rather than
 * as a green badge. Full strength is the next value up that the design language
 * actually contains, rather than an alpha invented between the two.
 *
 * No border, matching .tab.active and .msg.sent, which carry none. The 1px lime
 * hairline it used to have would now be the same colour as the fill; padding
 * absorbed that 1px (9/16 -> 10/17) so the pill's outer size is unchanged at 34px.
 *
 * Lime is legal here because the contract reserves it for OUR OWN surfaces, and a
 * badge naming our own product is precisely that. The rule it must not break is
 * the other one: never put lime on a third-party mark, which is why the Meta card
 * stays neutral.
 *
 * #1a3a2a on #d1f470 measures ~10:1.
 */
/**
 * data-wc-no-translate: the label is a BRAND NAME and must survive translation.
 * LanguageBar rewrites text nodes in place, and with the page set to Tamil this
 * badge was rendering as a translation of "Grahak OS · by Bharat Stack" - a product
 * and a company name, neither of which has a Tamil equivalent. The attribute is read
 * by collectTextNodes in LanguageBar.tsx and rejects the whole subtree.
 *
 * Marked here rather than at each call site so every surface inherits it: this badge
 * appears on Home, /grahak-os, /vayulok and the sign-in screen.
 */
const BrandBadge: React.FC<BrandBadgeProps> = ( { label } ) => (
  <span className="brand-badge" data-wc-no-translate="true">
    {/* The mark replaces a plain 10px dot. It inherits #1a3a2a through
        currentColor, so the badge stays a two-colour object. BrandMark sizes
        itself; styled-jsx cannot reach into it from here. */}
    <BrandMark />
    { label }
    <style jsx>{ `
      .brand-badge{display:inline-flex;align-items:center;gap:10px;padding:10px 17px;border-radius:9999px;background:#d1f470;font-size:14px;font-weight:600;letter-spacing:-.125px;line-height:1;color:#1a3a2a;white-space:nowrap}

      @media(max-width:480px){
        .brand-badge{white-space:normal}
      }
    ` }</style>
  </span>
);

export default BrandBadge;
