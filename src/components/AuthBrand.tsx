import React from 'react';
import BrandBadge from './BrandBadge';

/**
 * Brand line above the sign-in form, handed to Amplify's Authenticator through its
 * `components.Header` slot (typed as `Header?: () => JSX.Element | null` in
 * @aws-amplify/ui-react's defaultComponents).
 *
 * Self-styling, for the same reason BrandBadge and BrandLockup are: styled-jsx does
 * not scope composite components, so _app.tsx cannot reach these class names from
 * its own <style jsx>, and a className passed in from there would arrive unstyled.
 *
 * The badge and nothing else. The Authenticator renders its own "Sign In" heading
 * immediately below this, so a headline here would state the same thing twice - and
 * the ask was for the brand line above the form, not a new title. The site Header
 * is already present too (AuthGate renders it around the form when unauthenticated),
 * so this does not need to carry navigation either.
 *
 * Lime is legal here on the same grounds as the home page badge: the design contract
 * reserves it for OUR OWN surfaces, and this names our own product. The label is
 * character-for-character the one src/pages/index.tsx uses, so the signed-out
 * journey from home to sign-in shows one string rather than two variants of it.
 */
// Typed as a zero-argument function rather than React.FC on purpose. The slot is
// declared `Header?: () => React.JSX.Element | null`, and React.FC is
// `(props, context?) => ...`, so an FC is NOT assignable to it - tsc rejects it with
// "Target signature provides too few arguments. Expected 1 or more, but got 0."
const AuthBrandHeader = (): React.JSX.Element => (
  <div className="authbrand">
    <BrandBadge label="WECARE.DIGITAL" />
    <style jsx>{`
      /* Centred, because the form beneath it is centred - left-aligning it would
         hang the pill off the card's left edge. The 20px below is what lets the
         card's own box-shadow read as a separate object rather than as a halo
         around the badge. Horizontal padding is for 360px screens, where the pill
         wraps (BrandBadge allows that under 480px) and would otherwise touch the
         viewport edge. */
      .authbrand{display:flex;justify-content:center;padding:0 16px 20px}
    `}</style>
  </div>
);

export default AuthBrandHeader;
