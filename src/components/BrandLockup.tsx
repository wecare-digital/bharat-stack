import React from 'react';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';

interface BrandLockupProps {
  compact?: boolean;
  suffix?: React.ReactNode;
  className?: string;
}

const BrandLockup: React.FC<BrandLockupProps> = ( { className = '' } ) => (
  <span className={ `brand-lockup full ${className}`.trim() }>
    <img src={ LOGO_URL } alt="" aria-hidden="true" />
    {/* WECARE.DIGITAL, split across the same two lines the wordmark has always used.
        The owner asked for "WECARE.DIGITAL" to become WECARE.DIGITAL everywhere; this
        lockup was the one place where that is a shape decision rather than a string
        swap, because it is a two-line stacked wordmark, not a sentence. Splitting on
        the dot keeps the stacked silhouette and the existing two-span structure -
        collapsing it to one long line would have roughly doubled the lockup's width
        and pushed the nav trigger toward the middle of the header. */}
    {/* Split after the dot, with the dot itself carrying the accent - matching the
        owner's reference lockup, which sets WECARE. on the first line and DIGITAL on
        the second with the full stop picked out in colour.
        The dot is DARK RED, back to the reference. It was lime, and the owner's word for
        the result was "not viable" - which is the visibility problem, correctly
        identified: #d1f470 on white measures about 1.4:1, so at 26px a single full stop
        in it was effectively invisible. Lime is a fill colour on this site, sitting behind
        #1a3a2a type; it was never going to work AS the mark. #991b1b measures about 7.5:1
        on white, so the dot is finally legible at the one size it is ever drawn.
        An earlier pass split this as WECARE / .DIGITAL, which put the dot at the head of
        the second line where it reads as a leading separator rather than as the end of
        a sentence. The dot belongs to WECARE. */}
    <span className="brand-copy">
      <span>WECARE<span className="brand-dot">.</span></span>
      <span className="brand-stack">DIGITAL</span>
    </span>
    <style jsx>{ `
      /* Logo and wordmark both sized up, per request, but BOUNDED BY THE HEADER.
         .hdr-in is height:108px with 18px padding and box-sizing:border-box, so the
         content box is exactly 72px tall - a 72px logo would touch both edges, so 68px
         is the largest size that keeps any breathing room. Mobile is height:96px with
         14px padding, a 68px content box, so 60px there. Those header heights are
         pinned by Header.test.tsx and are not the thing to change.
         Type went 24 -> 26px desktop and 22 -> 24px mobile, keeping the step down from
         the logo rather than growing to match it. */
      .brand-lockup{display:inline-flex;align-items:center;gap:10px;flex-wrap:nowrap;min-width:0}
      .brand-lockup img{height:68px;width:auto;border-radius:12px;flex-shrink:0;display:block;object-fit:contain}
      .brand-copy{display:flex;flex-direction:column;justify-content:center;line-height:1.08}
      .brand-copy>span{font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-.4px}
      /* The accent is on the dot only, and it is the one place this site uses red. Kept to
         a single glyph so it never competes with lime for meaning: lime marks interaction
         and state, this marks the brand. */
      .brand-dot{color:#991b1b}
      .brand-stack{display:flex;align-items:center;gap:2px}
      @media(max-width:767px){
        .brand-lockup{gap:8px}
        .brand-lockup img{height:60px;border-radius:10px}
        .brand-copy>span{font-size:24px}
      }
    ` }</style>
  </span>
);

export default BrandLockup;
