import React from 'react';

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
 * (#f2fbf6, #fbfff0); these two values instead have precedent in this very
 * codebase:
 *
 *   background  rgba(209,244,112,.22)  — #d1f470 at 22%, the exact tint Header
 *                                        uses for nav hover / active / expanded
 *   border      1px solid #d1f470      — the .nav-menu dropdown hairline
 *
 * Lime is legal here because the contract reserves it for OUR OWN surfaces, and a
 * badge naming our own product is precisely that. The rule it must not break is
 * the other one: never put lime on a third-party mark, which is why the Meta card
 * stays neutral. 1px because the pill is static, per the hairline rule.
 *
 * #1a3a2a on that tint measures ~11.9:1, so the type got more legible, not less.
 */
const BrandBadge: React.FC<BrandBadgeProps> = ( { label } ) => (
  <span className="brand-badge">
    <i className="brand-badge-dot" aria-hidden="true" />
    { label }
    <style jsx>{ `
      .brand-badge{display:inline-flex;align-items:center;gap:10px;padding:9px 16px;border:1px solid #d1f470;border-radius:9999px;background:rgba(209,244,112,.22);font-size:14px;font-weight:600;letter-spacing:-.125px;line-height:1;color:#1a3a2a;white-space:nowrap}
      .brand-badge-dot{width:10px;height:10px;border-radius:50%;background:#1a3a2a;flex:0 0 auto}
      @media(max-width:480px){
        .brand-badge{white-space:normal}
      }
    ` }</style>
  </span>
);

export default BrandBadge;
