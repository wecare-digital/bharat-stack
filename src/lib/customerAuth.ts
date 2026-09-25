/**
 * WhatsApp-OTP sign-in for customers, against the customer Cognito pool.
 *
 * Why this exists instead of using Amplify Auth
 * ---------------------------------------------
 * There are two Cognito pools in this account and they are deliberately separate:
 *
 *   us-east-1_cSx0RHCIR   WECARE.DIGITAL            staff. Admin/Operator/Viewer.
 *   us-east-1_46ULYuukt   WECARE.DIGITAL-CUSTOMERS  customers. Phone-keyed, CUSTOM_AUTH.
 *
 * `aws-amplify/auth` is configured against the staff pool, so `fetchAuthSession`
 * returns a staff session and cannot speak to the customer pool at all. Pointing
 * Amplify at the customer pool instead would break every staff page.
 *
 * So this talks to the Cognito Identity Provider REST API directly. That needs no
 * SDK and no credentials: InitiateAuth and RespondToAuthChallenge are public,
 * unauthenticated endpoints, and the app client was created with
 * `GenerateSecret: false`, so no SECRET_HASH is required either.
 *
 * The OTP itself is delivered over WhatsApp by the pool's CreateAuthChallenge
 * trigger. Nothing here sees or handles the code beyond passing back what the
 * customer typed.
 *
 * Token storage
 * -------------
 * The access token goes in `sessionStorage`, not `localStorage`: it is valid for
 * 60 minutes, and sessionStorage dies with the tab, so a shared or public browser
 * does not keep a usable session after the tab closes. It is still readable by
 * script on this origin, which is the normal tradeoff for a browser SPA session -
 * the mitigation is that these tokens reach only the customer's own file list and
 * expire quickly.
 */

const REGION = process.env.NEXT_PUBLIC_COGNITO_REGION || 'us-east-1';
/** Public identifiers. Neither is a secret; both are safe in client code. */
const CLIENT_ID = process.env.NEXT_PUBLIC_CUSTOMER_CLIENT_ID || '4avmt9n4gpmkvkdk88qbtit33o';

const ENDPOINT = `https://cognito-idp.${REGION}.amazonaws.com/`;
const TOKEN_KEY = 'wecare.customer.accessToken';
const EXPIRY_KEY = 'wecare.customer.expiresAt';

export interface OtpChallenge {
  session: string;
  /** Masked by the Cognito trigger, e.g. `********0044`. Never the full number. */
  destination: string;
  expiresInSeconds: number;
}

export interface CustomerSession {
  accessToken: string;
  expiresAt: number;
}

async function cognito<T> ( target: string, body: unknown ): Promise<T> {
  const response = await fetch( ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify( body ),
  } );

  const text = await response.text();
  const parsed = text ? JSON.parse( text ) : {};

  if ( !response.ok )
  {
    // Cognito puts the useful part in __type, e.g. NotAuthorizedException.
    const kind = String( parsed.__type || '' ).split( '#' ).pop() || 'RequestFailed';
    const error = new Error( parsed.message || kind );
    error.name = kind;
    throw error;
  }
  return parsed as T;
}

/**
 * Ask for an OTP over WhatsApp.
 *
 * `PreventUserExistenceErrors` is enabled on the app client, so an unknown number
 * still returns a challenge with a masked destination rather than an error. That is
 * deliberate - it stops this endpoint being used to discover which numbers are
 * registered - and it means "no code arrived" is indistinguishable here from "not a
 * customer". The UI must say so rather than claiming a code was sent.
 */
export async function requestOtp ( mobile: string ): Promise<OtpChallenge> {
  const normalised = normaliseMobile( mobile );
  const result = await cognito<{
    Session?: string;
    ChallengeParameters?: Record<string, string>;
  }>( 'InitiateAuth', {
    ClientId: CLIENT_ID,
    AuthFlow: 'CUSTOM_AUTH',
    AuthParameters: { USERNAME: normalised },
  } );

  return {
    session: result.Session || '',
    destination: result.ChallengeParameters?.destination || '',
    expiresInSeconds: Number( result.ChallengeParameters?.expiresInSeconds || 600 ),
  };
}

/**
 * Submit the code. Returns null when it was wrong but attempts remain, so the UI
 * can invite a retry; throws when Cognito has failed the whole attempt.
 */
export async function submitOtp (
  mobile: string,
  code: string,
  session: string,
): Promise<CustomerSession | null> {
  const normalised = normaliseMobile( mobile );
  const result = await cognito<{
    AuthenticationResult?: { AccessToken?: string; ExpiresIn?: number };
    Session?: string;
    ChallengeName?: string;
  }>( 'RespondToAuthChallenge', {
    ClientId: CLIENT_ID,
    ChallengeName: 'CUSTOM_CHALLENGE',
    Session: session,
    ChallengeResponses: { USERNAME: normalised, ANSWER: code.trim() },
  } );

  const token = result.AuthenticationResult?.AccessToken;
  if ( !token )
  {
    // Cognito re-issued the challenge: wrong code, attempts left.
    return null;
  }

  const expiresAt = Date.now() + ( result.AuthenticationResult?.ExpiresIn || 3600 ) * 1000;
  storeSession( token, expiresAt );
  return { accessToken: token, expiresAt };
}

/** The session Cognito returns alongside a rejected code, for the next attempt. */
export function nextSessionFrom ( error: unknown ): string {
  return String( ( error as { session?: string } )?.session || '' );
}

export function storeSession ( accessToken: string, expiresAt: number ): void {
  if ( typeof window === 'undefined' ) return;
  window.sessionStorage.setItem( TOKEN_KEY, accessToken );
  window.sessionStorage.setItem( EXPIRY_KEY, String( expiresAt ) );
}

/** The stored token, or null when absent or expired. */
export function getSession (): CustomerSession | null {
  if ( typeof window === 'undefined' ) return null;
  const accessToken = window.sessionStorage.getItem( TOKEN_KEY );
  const expiresAt = Number( window.sessionStorage.getItem( EXPIRY_KEY ) || 0 );
  if ( !accessToken || !expiresAt ) return null;
  // Treat a token inside its last 30 seconds as gone, so a request cannot expire
  // mid-flight and surface as a confusing 401.
  if ( Date.now() > expiresAt - 30_000 )
  {
    clearSession();
    return null;
  }
  return { accessToken, expiresAt };
}

export function clearSession (): void {
  if ( typeof window === 'undefined' ) return;
  window.sessionStorage.removeItem( TOKEN_KEY );
  window.sessionStorage.removeItem( EXPIRY_KEY );
}

/**
 * Digits to E.164, matching the backend's normalisation exactly.
 *
 * If these two ever disagree, a customer signs in successfully and then owns
 * nothing, because the file was registered against a differently-formatted number.
 */
export function normaliseMobile ( raw: string ): string {
  const digits = String( raw || '' ).replace( /\D/g, '' );
  const withCountry = digits.length === 10 && /^[6-9]/.test( digits ) ? `91${digits}` : digits;
  if ( withCountry.length < 10 || withCountry.length > 15 )
  {
    throw new Error( 'Enter a valid mobile number' );
  }
  return `+${withCountry}`;
}
