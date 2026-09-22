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
 * Deliberately not the pale green of the reference mock: that is the
 * near-miss-green family the palette retired (#f2fbf6, #fbfff0). White with the
 * shared #e5e7eb hairline and #1a3a2a type says the same thing in colours the
 * design contract owns. 1px because the pill is static, per the hairline rule.
 */
const BrandBadge: React.FC<BrandBadgeProps> = ( { label } ) => (
  <span className="brand-badge">
    <i className="brand-badge-dot" aria-hidden="true" />
    { label }
    <style jsx>{ `
      .brand-badge{display:inline-flex;align-items:center;gap:10px;padding:9px 16px;border:1px solid #e5e7eb;border-radius:9999px;background:#fff;font-size:14px;font-weight:600;letter-spacing:-.125px;line-height:1;color:#1a3a2a;white-space:nowrap}
      .brand-badge-dot{width:10px;height:10px;border-radius:50%;background:#1a3a2a;flex:0 0 auto}
      @media(max-width:480px){
        .brand-badge{white-space:normal}
      }
    ` }</style>
  </span>
);

export default BrandBadge;
