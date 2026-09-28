import React from 'react';
import Link from 'next/link';

export interface Crumb {
  label: string;
  /** Omit on the last item: the current page is not a link to itself. */
  href?: string;
}

/**
 * A breadcrumb trail, on the site's own rungs.
 *
 * WHAT IT REPLACES. Post pages offered a single Link reading "Blog" with a CSS-generated
 * arrow, at 13px/650 in #1a3a2a. That is a back button, not a breadcrumb: it names one
 * ancestor, gives no sense of depth, and was the only control on the page at 13px when the
 * site's smallest UI rung is 12px/700 uppercase (.home-close-eyebrow) and its base body is
 * 17px. Meanwhile both blog templates already emit a JSON-LD BreadcrumbList - so the
 * structured data described a trail the page never rendered, which is the kind of mismatch
 * that makes a rich result disappear without explanation.
 *
 * MARKUP IS nav > ol > li, which is what assistive technology expects for an ordered path and
 * what the BreadcrumbList claims exists. The separator is a ::before on li + li, so it is
 * drawn rather than typed: a literal chevron or slash in the markup is announced by a screen
 * reader on every item ("Home slash Blog slash..."), and a CSS pseudo-element is not in the
 * accessibility tree at all.
 *
 * aria-current="page" MARKS THE LAST ITEM, which is how a screen reader user knows the trail
 * has ended without relying on it being visually dimmed. It is also not a link - linking a
 * page to itself is a documented WCAG annoyance rather than a help.
 *
 * TYPE IS THE 12px/700 UPPERCASE EYEBROW RUNG, byte for byte the declaration
 * .home-close-eyebrow uses for "Everyday Bharat". That is deliberate: a breadcrumb is page
 * furniture, and putting it on the body rung would give it the same weight as the writing
 * underneath it. No new size enters the ladder.
 *
 * THE CURRENT PAGE TRUNCATES AT 46ch rather than wrapping. Blog titles here run to 70-plus
 * characters ("A page view is not a person" is short for this corpus), and a trail that wraps
 * to three lines stops reading as a trail. The full title is the h1 immediately below, so
 * nothing is lost by clipping it here.
 *
 * SELF-STYLING, like BrandBadge and RotatingHero: styled-jsx cannot scope a composite
 * component from its parent, so this owns every rule it needs and the consumer owns placement.
 * Classes are bc- prefixed because the globally imported src/styles/*.css declares unscoped
 * rules for generic names.
 */
const Breadcrumbs: React.FC<{ items: Crumb[] }> = ( { items } ) => (
  <nav className="bc" aria-label="Breadcrumb">
    <ol>
      { items.map( ( item, i ) => (
        <li key={ `${item.label}-${i}` }>
          { item.href
            ? <Link href={ item.href }>{ item.label }</Link>
            // The last crumb: plain text, marked as the current page.
            : <span aria-current="page">{ item.label }</span> }
        </li>
      ) ) }
    </ol>

    <style jsx>{`
      .bc{margin:0 0 22px}
      .bc ol{display:flex;flex-wrap:wrap;align-items:center;gap:0;margin:0;padding:0;list-style:none}
      /* The eyebrow rung: 12px/700, .08em, uppercase - the same declaration
         .home-close-eyebrow uses. A breadcrumb is furniture, not body copy. */
      .bc li{
        display:flex;align-items:center;
        font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
        line-height:1.4;color:#1a3a2a;
      }
      /* DRAWN, NOT TYPED. A chevron character in the markup is read aloud on every item; a
         rotated border box is not in the accessibility tree. Same technique as the tick in
         the home page's closing band. */
      .bc li + li::before{
        content:'';display:inline-block;width:5px;height:5px;margin:0 10px;
        border-top:2px solid rgba(26,58,42,.42);
        border-right:2px solid rgba(26,58,42,.42);
        transform:rotate(45deg);
      }
      /* NO UNDERLINE AT REST, a lime one on hover - the footer rows' pattern, and legitimate
         here because these ARE links. The border is transparent rather than absent so the
         text never shifts by a pixel when it appears. */
      .bc a{
        color:#1a3a2a;text-decoration:none;
        border-bottom:2px solid transparent;transition:border-color .2s;
      }
      .bc a:hover{border-bottom-color:#d1f470}
      .bc a:focus-visible{outline:3px solid rgba(26,58,42,.28);outline-offset:3px;border-radius:2px}
      /* The current page, dimmed so the trail reads as a path with an end, and clipped
         because this corpus has long titles. */
      .bc [aria-current]{
        color:rgba(26,58,42,.58);
        max-width:46ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
      }
      @media(max-width:767px){
        /* 34ch on a phone: 46 would still overflow a 358px measure at this size. */
        .bc [aria-current]{max-width:34ch}
      }
      @media(prefers-reduced-motion:reduce){
        .bc a{transition:none}
      }
    `}</style>
  </nav>
);

export default Breadcrumbs;
