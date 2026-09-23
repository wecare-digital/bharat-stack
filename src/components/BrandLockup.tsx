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
        THE DOT HAS BEEN THROUGH THREE COLOURS, and the reasoning matters because each
        change fixed the previous one's actual defect.
        It was lime (#d1f470), which the owner called "not viable" - correctly: lime on
        white measures about 1.4:1, so at 26px a single full stop in it was invisible.
        Lime is a fill colour here, sitting behind #1a3a2a type; it was never going to
        work AS a mark.
        It then became dark red (#991b1b) at about 7.5:1, which solved legibility and
        introduced a subtler problem the owner then named - asking for something "more
        visible, like neon". At 26px, one glyph of #991b1b reads as near-black: it is
        high-contrast but it does not read as a COLOUR, so the accent stopped registering
        as an accent. Contrast and vividness are not the same measurement.
        It is now #ff0040. That measures about 3.9:1 on white - lower than the dark red,
        deliberately, and still comfortably past the 3:1 that WCAG asks of a non-text
        graphic, which is the right bar for a decorative glyph in a wordmark rather than
        the 4.5:1 for body text. The gain is that it is unmistakably red on screen instead
        of reading as dark ink.
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
         and state, this marks the brand.
         No glow, deliberately. A text-shadow halo is the usual way to make a colour look
         "neon", and at 26px on white it would just blur the one glyph that has to stay
         crisp - the saturation is doing the work instead. */
      .brand-dot{color:#ff0040}
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
