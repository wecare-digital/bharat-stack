import React, { useState } from 'react';

import PillButton from './PillButton';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const EMAIL_VERIFY_URL = `${API_BASE}/auth/email-verification`;
const PROFILE_URL = `${API_BASE}/customer/profile`;

type VerificationStep = 'idle' | 'sending' | 'sent' | 'verifying' | 'verified' | 'error';

export interface CheckoutProfileValue {
  contactId: string;
  name: string;
  email: string;
  phone: string;
}

interface Props {
  accessToken: string;
  onReady: ( profile: CheckoutProfileValue ) => void;
}

async function jsonPost (
  url: string,
  body: Record<string, unknown>,
  accessToken?: string,
): Promise<Record<string, any>> {
  const response = await fetch( url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...( accessToken ? { Authorization: `Bearer ${ accessToken }` } : {} ),
    },
    body: JSON.stringify( body ),
  } );
  const payload = await response.json().catch( () => ( {} ) );
  if ( !response.ok ) {
    const error = new Error( String( payload.error || 'REQUEST_FAILED' ) ) as Error & {
      payload?: Record<string, any>;
      status?: number;
    };
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return payload;
}

const CheckoutProfile: React.FC<Props> = ( { accessToken, onReady } ) => {
  const [ firstName, setFirstName ] = useState( '' );
  const [ lastName, setLastName ] = useState( '' );
  const [ email, setEmail ] = useState( '' );
  const [ code, setCode ] = useState( '' );
  const [ proof, setProof ] = useState( '' );
  const [ step, setStep ] = useState<VerificationStep>( 'idle' );
  const [ saving, setSaving ] = useState( false );
  const [ message, setMessage ] = useState( '' );

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test( email.trim() );
  const namesValid = firstName.trim().length > 0 && lastName.trim().length > 0;

  const resetEmail = ( next: string ) => {
    setEmail( next );
    setProof( '' );
    setCode( '' );
    setStep( 'idle' );
    setMessage( '' );
  };

  const sendCode = async () => {
    if ( !emailValid ) {
      setMessage( 'Enter a valid email address.' );
      setStep( 'error' );
      return;
    }
    setMessage( '' );
    setStep( 'sending' );
    try {
      await jsonPost( EMAIL_VERIFY_URL, {
        action: 'request',
        email: email.trim(),
        firstName: firstName.trim(),
      } );
      setStep( 'sent' );
      setMessage( 'Verification code sent to your email.' );
    } catch {
      setStep( 'error' );
      setMessage( 'We could not send the email code. Please try again.' );
    }
  };

  const verifyCode = async () => {
    if ( code.trim().length < 4 ) return;
    setMessage( '' );
    setStep( 'verifying' );
    try {
      const reply = await jsonPost( EMAIL_VERIFY_URL, {
        action: 'verify',
        email: email.trim(),
        code: code.trim(),
      } );
      const nextProof = String( reply.proof || '' );
      if ( reply.status !== 'VERIFIED' || !nextProof ) throw new Error( 'PROOF_MISSING' );
      setProof( nextProof );
      setCode( '' );
      setStep( 'verified' );
      setMessage( 'Email verified.' );
    } catch {
      setProof( '' );
      setStep( 'error' );
      setMessage( 'That email code is invalid or expired.' );
    }
  };

  const saveProfile = async () => {
    if ( !namesValid || !proof ) {
      setMessage( !namesValid
        ? 'Enter your first and last name.'
        : 'Verify your email before continuing.' );
      return;
    }
    setSaving( true );
    setMessage( '' );
    try {
      const reply = await jsonPost( PROFILE_URL, {
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim(),
        emailProof: proof,
      }, accessToken );
      if ( reply.status !== 'PROFILE_READY' ) throw new Error( 'PROFILE_NOT_READY' );
      onReady( {
        contactId: String( reply.contactId || '' ),
        name: String( reply.name || '' ),
        email: String( reply.email || '' ),
        phone: String( reply.phone || '' ),
      } );
      setMessage( 'Details saved. You can continue to secure payment.' );
    } catch ( error ) {
      const payload = ( error as Error & { payload?: Record<string, any> } ).payload || {};
      if ( payload.error === 'CONTACT_IDENTITY_CONFLICT' ) {
        setMessage( 'This phone and email are already linked to different contact records. Please contact us.' );
      } else if ( payload.error === 'EMAIL_VERIFICATION_REQUIRED' ) {
        setProof( '' );
        setStep( 'idle' );
        setMessage( 'Email verification expired. Please verify your email again.' );
      } else {
        setMessage( 'We could not save your checkout details. Please try again.' );
      }
    } finally {
      setSaving( false );
    }
  };

  return (
    <section className="checkout-profile" aria-labelledby="checkout-profile-title">
      <div className="checkout-profile-head">
        <div>
          <p className="checkout-profile-eyebrow">Checkout details</p>
          <h2 id="checkout-profile-title">Confirm who is placing the order</h2>
        </div>
        <span className="phone-verified">✓ WhatsApp verified by sign-in</span>
      </div>

      <div className="checkout-profile-grid">
        <label>
          <span>First name</span>
          <input
            value={ firstName }
            onChange={ event => setFirstName( event.target.value ) }
            autoComplete="given-name"
            maxLength={ 100 }
            placeholder="First name"
          />
        </label>

        <label>
          <span>Last name</span>
          <input
            value={ lastName }
            onChange={ event => setLastName( event.target.value ) }
            autoComplete="family-name"
            maxLength={ 100 }
            placeholder="Last name"
          />
        </label>

        <div className="email-field">
          <label htmlFor="checkout-email">Email</label>
          <input
            id="checkout-email"
            type="email"
            value={ email }
            onChange={ event => resetEmail( event.target.value ) }
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={ step === 'error' ? 'true' : undefined }
          />
          <div className="verify-row">
            { step === 'verified' ? (
              <span className="verified">✓ Email verified</span>
            ) : step === 'sent' || step === 'error' || step === 'verifying' ? (
              <>
                <input
                  className="otp"
                  value={ code }
                  onChange={ event => setCode( event.target.value.replace( /\D/g, '' ).slice( 0, 6 ) ) }
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  aria-label="Email verification code"
                  placeholder="Code"
                  disabled={ step === 'verifying' }
                />
                <button type="button" onClick={ verifyCode } disabled={ step === 'verifying' }>
                  { step === 'verifying' ? 'Checking…' : 'Verify' }
                </button>
              </>
            ) : (
              <button type="button" onClick={ sendCode } disabled={ step === 'sending' || !emailValid }>
                { step === 'sending' ? 'Sending…' : 'Send code' }
              </button>
            ) }
          </div>
        </div>
      </div>

      <p className="checkout-profile-note">
        Your verified phone and email are saved to the existing WECARE.DIGITAL Contacts workspace
        for this order. Purchasing does not automatically opt you into marketing.
      </p>

      { message && <p className="checkout-profile-status" role="status">{ message }</p> }

      <div className="checkout-profile-action">
        <PillButton
          as="button"
          type="button"
          label="Details"
          action={ saving ? 'Saving…' : 'Save & continue' }
          disabled={ saving || !namesValid || !proof }
          busy={ saving }
          onClick={ saveProfile }
        />
      </div>

      <style jsx>{`
        .checkout-profile{
          margin:28px 0 0;padding:22px;border:1px solid #e5e7eb;border-radius:14px;background:#fff;
        }
        .checkout-profile-head{
          display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px;
        }
        .checkout-profile-eyebrow{
          margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
        }
        h2{margin:0;font-size:22px;line-height:1.25;letter-spacing:-.25px;color:#1a1a1a}
        .phone-verified,.verified{
          flex:0 0 auto;padding:5px 10px;border-radius:999px;background:#d1f470;color:#1a3a2a;
          font-size:12px;font-weight:700;white-space:nowrap;
        }
        .checkout-profile-grid{display:grid;grid-template-columns:1fr 1fr 1.5fr;gap:12px;align-items:start}
        .checkout-profile-grid label,.email-field{display:flex;flex-direction:column;gap:7px}
        .checkout-profile-grid label>span,.email-field>label{
          font-size:12px;font-weight:700;color:#1a3a2a;
        }
        .checkout-profile-grid input{
          min-height:52px;box-sizing:border-box;border:1px solid #e5e7eb;border-radius:10px;
          padding:0 14px;background:#fff;color:#1a1a1a;font:inherit;font-size:16px;outline:none;
        }
        .checkout-profile-grid input:focus-visible{
          outline:3px solid #1a3a2a;outline-offset:2px;border-color:#1a3a2a;
        }
        .verify-row{display:flex;align-items:center;gap:8px;min-height:34px}
        .verify-row button{
          min-height:34px;padding:0 12px;border:1px solid #1a3a2a;border-radius:999px;background:#fff;
          color:#1a3a2a;font:inherit;font-size:12px;font-weight:700;cursor:pointer;
        }
        .verify-row button:hover:not(:disabled){background:#d1f470}
        .verify-row button:disabled{opacity:.55;cursor:default}
        .verify-row .otp{width:96px;min-height:34px;padding:0 10px;font-size:14px}
        .checkout-profile-note,.checkout-profile-status{
          margin:14px 0 0;font-size:14px;line-height:1.5;color:rgba(0,0,0,.66);
        }
        .checkout-profile-status{color:#1a3a2a;font-weight:600}
        .checkout-profile-action{margin-top:16px}
        @media(max-width:767px){
          .checkout-profile{padding:18px 14px}
          .checkout-profile-head{display:block}
          .phone-verified{display:inline-flex;margin-top:10px}
          .checkout-profile-grid{grid-template-columns:1fr}
        }
      `}</style>
    </section>
  );
};

export default CheckoutProfile;
