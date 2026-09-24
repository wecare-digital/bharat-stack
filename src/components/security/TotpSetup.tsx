/**
 * Authenticator-app (TOTP) enrolment for the signed-in operator.
 *
 * WHY THIS COMPONENT HAS TO EXIST, rather than a setting somewhere in AWS:
 * TOTP cannot be switched on for a user from the admin side. Measured against the
 * live pool on 2026-09-24, `AdminSetUserMFAPreference` with
 * `SoftwareTokenMfaSettings.Enabled` returns
 *
 *     InvalidParameterException: User does not have delivery config set to turn
 *     on SOFTWARE_TOKEN_MFA
 *
 * because Cognito requires the user to associate an authenticator first, and
 * `AssociateSoftwareToken` is documented as not evaluating IAM policies at all -
 * it takes the user's own access token or an auth-challenge session, so there is
 * no admin path by design. Pool-level TOTP was already enabled; this screen is
 * the missing half.
 *
 * THE SECRET NEVER LEAVES THE DEVICE. It is rendered, and it is put into an
 * `otpauth://` URI, which is a local scheme handled by the authenticator app on
 * the same device. It is deliberately NOT sent to a QR-image service: handing a
 * TOTP seed to a third party to draw a picture of it would defeat the factor.
 * It is also never logged, never put in a toast, and never in an analytics call,
 * and it is cleared from component state the moment verification succeeds.
 *
 * WHY NO QR IMAGE: rendering one needs a new dependency, and the two paths here
 * already cover both cases - tap the `otpauth://` link on a phone or in the
 * WebView and the authenticator opens pre-filled; copy the key on a desktop and
 * paste it into "enter a setup key". A QR is a nicety that would add an
 * unreviewed package to an auth flow, so it is a follow-up, not a blocker.
 *
 * ---------------------------------------------------------------------------
 * STYLED TO THE PUBLIC CONTRACT, not the inner-page system
 * ---------------------------------------------------------------------------
 * Owner asked for this screen to match the new home-page design, so every value
 * below is quoted from .kiro/steering/grahak-os-design.md and from
 * src/pages/grahak-os/index.tsx - nothing is approximated:
 *
 *   card heading   22px / 700 / lh 1.27 / ls -.25px / #000        (.capability-card h3)
 *   body, ONE level 20px / 400 / lh 1.4 / ls -.125px / rgba(0,0,0,.898)
 *   label/eyebrow  14px / 400 / rgba(0,0,0,.54), not uppercase, not tracked
 *   static card    1px solid #e5e7eb, radius 20px, padding 34px 30px  (.trust-card)
 *   pill button    14px 28px / 2px #e5e7eb / radius 50px / 17px / 600
 *                  hover: border #d1f470, colour #1a3a2a, translateY(-2px),
 *                  shadow 0 4px 12px rgba(26,58,42,.12)               (.pill)
 *   code panel     #000, radius 14px, 1.5px solid rgba(255,255,255,.92),
 *                  SF Mono 14px / lh 1.6 / #fff                    (.code-body)
 *   affirmative    #d1f470 fill + #1a3a2a type, no border, radius 9999px,
 *                  14px / 600 / ls -.125px                          (BrandBadge)
 *
 * The 2px weight on the pill and the input is the contract's rule working, not
 * drift: 2px means the element has a hover/focus that swaps the border to lime,
 * 1px means static. The card is static, so it is 1px.
 *
 * SELF-STYLING, because styled-jsx does not scope composite components - a
 * parent's <style jsx> cannot reach these class names.
 *
 * `ts-` prefix on every class, and `data-public-ui` on the controls. Both are
 * defences the contract names. The prefix keeps globally-imported CSS for generic
 * names (.pill, .btn, .tab) off these elements. The attribute is the documented
 * opt-out in inner-pages.css: its button and input rules use `!important` with up
 * to twelve class-level :not() arguments, so without the marker they would
 * overwrite the pill's radius, padding, weight and border and no class selector
 * could win.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  setUpTOTP,
  verifyTOTPSetup,
  updateMFAPreference,
  fetchMFAPreference,
  getCurrentUser,
} from 'aws-amplify/auth';

type Stage = 'loading' | 'idle' | 'enrolling' | 'verifying' | 'done' | 'error';

export interface MfaPreferenceView {
  enabled: string[];
  preferred?: string;
}

const APP_NAME = 'WECARE.DIGITAL';

/** Group a base32 secret into 4-character runs so it can be read and typed. */
export function groupSecret ( secret: string ): string {
  return ( secret || '' ).replace( /\s+/g, '' ).replace( /(.{4})/g, '$1 ' ).trim();
}

/**
 * True when TOTP is already registered for this user.
 *
 * Checked case-insensitively and against BOTH spellings, because Amplify has used
 * 'TOTP' while Cognito itself reports 'SOFTWARE_TOKEN_MFA'. Matching only one of
 * them is how a screen ends up telling an already-enrolled user to enrol again.
 */
export function hasTotp ( pref: MfaPreferenceView | null ): boolean {
  if ( !pref?.enabled ) return false;
  return pref.enabled.some(
    ( f ) => [ 'totp', 'software_token_mfa' ].includes( String( f ).toLowerCase() )
  );
}

export function isTotpPreferred ( pref: MfaPreferenceView | null ): boolean {
  const p = String( pref?.preferred || '' ).toLowerCase();
  return p === 'totp' || p === 'software_token_mfa';
}

/** Six digits, nothing else. Strips the spaces authenticator apps display. */
export function normaliseCode ( raw: string ): string {
  return ( raw || '' ).replace( /\D/g, '' ).slice( 0, 6 );
}

const TotpSetup: React.FC = () => {
  const [ stage, setStage ] = useState<Stage>( 'loading' );
  const [ pref, setPref ] = useState<MfaPreferenceView | null>( null );
  const [ secret, setSecret ] = useState( '' );
  const [ setupUri, setSetupUri ] = useState( '' );
  const [ code, setCode ] = useState( '' );
  const [ message, setMessage ] = useState( '' );
  const [ copied, setCopied ] = useState( false );
  const [ makePreferred, setMakePreferred ] = useState( false );

  const refresh = useCallback( async () => {
    try
    {
      const current = await fetchMFAPreference();
      setPref( {
        enabled: ( current.enabled || [] ) as string[],
        preferred: current.preferred as string | undefined,
      } );
      setStage( 'idle' );
    } catch
    {
      // Never surface a raw SDK error: it can carry the username.
      setMessage( 'Could not read your current sign-in factors.' );
      setStage( 'error' );
    }
  }, [] );

  useEffect( () => { void refresh(); }, [ refresh ] );

  const begin = useCallback( async () => {
    setMessage( '' );
    setCopied( false );
    try
    {
      const details = await setUpTOTP();
      const user = await getCurrentUser().catch( () => null );
      const account = user?.signInDetails?.loginId || user?.username || APP_NAME;
      setSecret( details.sharedSecret );
      setSetupUri( details.getSetupUri( APP_NAME, account ).toString() );
      setStage( 'enrolling' );
    } catch
    {
      setMessage( 'Could not start authenticator setup. Try again in a moment.' );
      setStage( 'error' );
    }
  }, [] );

  const confirm = useCallback( async () => {
    const six = normaliseCode( code );
    if ( six.length !== 6 )
    {
      setMessage( 'Enter the 6-digit code from your authenticator app.' );
      return;
    }
    setStage( 'verifying' );
    setMessage( '' );
    try
    {
      await verifyTOTPSetup( { code: six } );
      // ENABLED unless the operator explicitly asks for it as the default.
      // Silently moving someone's preferred factor is how a person who just set
      // up an app finds the email code they were waiting for never arrives.
      await updateMFAPreference( { totp: makePreferred ? 'PREFERRED' : 'ENABLED' } );
      setSecret( '' );
      setSetupUri( '' );
      setCode( '' );
      setStage( 'done' );
      setMessage( makePreferred
        ? 'Authenticator app added and set as your default sign-in code.'
        : 'Authenticator app added. Email remains your default sign-in code.' );
      await refresh();
    } catch ( err: any )
    {
      const name = String( err?.name || '' );
      setMessage(
        name.includes( 'EnableSoftwareTokenMFA' ) || name.includes( 'CodeMismatch' )
          ? 'That code was not accepted. Codes expire every 30 seconds, so try the next one.'
          : 'Could not confirm the code. Check your device clock, then try again.'
      );
      setStage( 'enrolling' );
    }
  }, [ code, makePreferred, refresh ] );

  const copySecret = useCallback( async () => {
    try
    {
      await navigator.clipboard.writeText( secret );
      setCopied( true );
    } catch
    {
      setCopied( false );
      setMessage( 'Copy failed. Select the key and copy it manually.' );
    }
  }, [ secret ] );

  const enrolled = hasTotp( pref );

  return (
    <section className="ts-card" aria-labelledby="ts-heading">
      <h2 className="ts-h" id="ts-heading">Authenticator app</h2>
      <p className="ts-body">
        A code generated on your own device, with no dependence on a mobile network
        or a mailbox. Works with Google Authenticator, Microsoft Authenticator,
        1Password, Authy or any TOTP app.
      </p>

      { stage === 'loading' && <p className="ts-body">Checking your sign-in factors…</p> }

      { stage !== 'loading' && (
        <div className="ts-status" role="status">
          <span className={ enrolled ? 'ts-mark ts-mark-on' : 'ts-mark ts-mark-off' }>
            { enrolled ? 'Registered' : 'Not registered' }
          </span>
          { pref?.enabled?.length ? (
            <span className="ts-label ts-label-inline">
              Active factors: { pref.enabled.join( ', ' ) }
              { pref.preferred ? ` · default ${pref.preferred}` : '' }
            </span>
          ) : null }
        </div>
      ) }

      { ( stage === 'idle' || stage === 'error' || stage === 'done' ) && (
        <button className="ts-pill" type="button" data-public-ui
          onClick={ () => void begin() }>
          { enrolled ? 'Replace authenticator app' : 'Add authenticator app' }
        </button>
      ) }

      { ( stage === 'enrolling' || stage === 'verifying' ) && (
        <div className="ts-steps">
          <p className="ts-body">
            On a phone, tap{ ' ' }
            <a className="ts-link" href={ setupUri }>open in your authenticator app</a>.
            On a desktop, choose <strong>enter a setup key</strong> and paste this:
          </p>

          <code className="ts-key" aria-label="Authenticator setup key">
            { groupSecret( secret ) }
          </code>
          <p className="ts-label">
            Treat this key like a password. Anyone holding it can generate your
            codes. It is shown once and this screen does not store it.
          </p>
          <button className="ts-pill" type="button" data-public-ui
            onClick={ () => void copySecret() }>
            { copied ? 'Copied' : 'Copy key' }
          </button>

          <label className="ts-label ts-label-field" htmlFor="ts-code">
            Then enter the 6-digit code your app shows
          </label>
          <input
            className="ts-code"
            id="ts-code"
            data-public-ui
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={ 6 }
            placeholder="123456"
            value={ code }
            onChange={ ( e ) => setCode( normaliseCode( e.target.value ) ) }
          />

          <label className="ts-choice">
            <input
              type="checkbox"
              data-public-ui
              checked={ makePreferred }
              onChange={ ( e ) => setMakePreferred( e.target.checked ) }
            />
            <span>Make this my default sign-in code instead of email</span>
          </label>

          <button
            className="ts-pill"
            type="button"
            data-public-ui
            disabled={ stage === 'verifying' || normaliseCode( code ).length !== 6 }
            onClick={ () => void confirm() }
          >
            { stage === 'verifying' ? 'Confirming…' : 'Confirm and turn on' }
          </button>
        </div>
      ) }

      { message && (
        <p className={ stage === 'done' ? 'ts-note ts-note-ok' : 'ts-note ts-note-warn' }>
          { message }
        </p>
      ) }

      <style jsx>{`
        /* ===== container: the contract's STATIC card - 1px, radius 20px ===== */
        .ts-card{
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          background:#fff;border:1px solid #e5e7eb;border-radius:20px;
          padding:34px 30px;max-width:720px;box-sizing:border-box;color:#1a1a1a;
        }

        /* ===== type ladder: card-heading rung, then the ONE body level ===== */
        .ts-h{
          font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
          color:#000;margin:0 0 14px;
        }
        .ts-body{
          font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
          color:rgba(0,0,0,.898);margin:0 0 18px;max-width:560px;
        }
        /* Label rung. Not uppercase and not letter-spaced, per the contract. */
        .ts-label{
          font-size:14px;font-weight:400;line-height:1.4;
          color:rgba(0,0,0,.54);margin:0 0 18px;max-width:560px;
        }
        .ts-label-inline{margin:0}
        .ts-label-field{display:block;margin:24px 0 8px}

        .ts-status{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 22px}

        /* Affirmative state = contract treatment 1, our own surface at full
           voice: #d1f470 fill, #1a3a2a type, NO border. Same pair as .msg.sent,
           .tab.active and BrandBadge, whose geometry this reuses. ~10:1. */
        .ts-mark{
          display:inline-flex;align-items:center;padding:10px 17px;
          border-radius:9999px;font-size:14px;font-weight:600;
          letter-spacing:-.125px;line-height:1;white-space:nowrap;
        }
        .ts-mark-on{background:#d1f470;color:#1a3a2a}
        /* Negative state is NOT a second lime tint: a static neutral hairline,
           because it is not one of our surfaces, it is the absence of one. */
        .ts-mark-off{background:#fff;border:1px solid #e5e7eb;color:rgba(0,0,0,.54)}

        /* ===== .pill, verbatim. 2px is legal because there IS a hover. ===== */
        .ts-pill{
          display:inline-flex;align-items:center;justify-content:center;
          font-family:inherit;padding:14px 28px;border:2px solid #e5e7eb;
          background:#fff;border-radius:50px;font-size:17px;font-weight:600;
          color:rgba(0,0,0,.898);cursor:pointer;transition:all .25s;
          margin:0 0 4px;box-shadow:none;min-height:0;
        }
        .ts-pill:hover:not(:disabled){
          border-color:#d1f470;color:#1a3a2a;transform:translateY(-2px);
          box-shadow:0 4px 12px rgba(26,58,42,.12);
        }
        .ts-pill:focus-visible{outline:none;border-color:#d1f470;box-shadow:0 0 0 3px rgba(26,58,42,.3)}
        .ts-pill:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}

        .ts-steps{margin-top:6px}
        .ts-link{color:#1a3a2a;text-decoration:underline}

        /* ===== .code-body, verbatim: #000 panel, 14px radius, white stroke ===== */
        .ts-key{
          display:block;width:auto;margin:0 0 12px;padding:15px 16px;
          border:1.5px solid rgba(255,255,255,.92);border-radius:14px;background:#000;
          font-family:'SF Mono',Monaco,Consolas,monospace;font-size:14px;
          line-height:1.6;color:#fff;white-space:pre-wrap;overflow-wrap:break-word;
        }

        /* 2px at rest because it has a :focus that swaps to lime - the hairline
           rule. A lime ring at REST is what made the sign-in inputs read as
           permanently focused, which is the defect this whole pass removed.
           Every property is declared, including min-height and background,
           because tokens.css styles the bare input element and anything left
           undeclared falls through - the leak the contract warns about.
           (No backticks anywhere in this comment: the whole block is a template
           literal and one backtick ends it. That is contract trap 3, and it broke
           this file's first test run.) */
        .ts-code{
          font-family:inherit;font-size:17px;font-weight:600;
          letter-spacing:4px;text-align:center;
          color:rgba(0,0,0,.898);background:#fff;
          border:2px solid #e5e7eb;border-radius:50px;
          padding:14px 24px;width:190px;min-height:0;box-sizing:border-box;
          transition:all .25s;
        }
        .ts-code:focus{outline:none;border-color:#d1f470}
        .ts-code::placeholder{color:rgba(0,0,0,.54);font-weight:400;letter-spacing:4px}

        .ts-choice{display:flex;align-items:center;gap:10px;margin:22px 0}
        .ts-choice span{
          font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
          color:rgba(0,0,0,.898);
        }
        .ts-choice input{accent-color:#1a3a2a;width:18px;height:18px;min-height:0}

        /* Notes take the body rung. The warning uses --warning #b45309, not the
           dark green: a state that cannot be told from another state is not a
           state, which is the defect this pass fixed three times. */
        .ts-note{
          font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
          margin:22px 0 0;padding:14px 18px;border-radius:14px;max-width:560px;
        }
        .ts-note-ok{background:#fafafa;border:1px solid #e5e7eb;color:#1a3a2a}
        .ts-note-warn{background:#fffbeb;border:1px solid #b45309;color:#b45309}

        @media(max-width:767px){
          .ts-card{padding:26px 20px;border-radius:16px}
          .ts-body,.ts-choice span,.ts-note{font-size:17px}
        }

        @media(prefers-reduced-motion:reduce){
          .ts-pill,.ts-code{transition:none}
          .ts-pill:hover:not(:disabled){transform:none}
        }
      `}</style>
    </section>
  );
};

export default TotpSetup;
