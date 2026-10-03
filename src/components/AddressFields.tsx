import React from 'react';

import { INDIA_SUBDIVISION_NAMES } from '../config/indiaSubdivisions';

/**
 * THE ONE DELIVERY-ADDRESS FORM IN THE PRODUCT, and the home of the `StoredAddress` type.
 *
 * WHY THIS IS ITS OWN COMPONENT
 * -----------------------------
 * Checkout collects a delivery address, and Phase 2 contribution will collect the same address
 * under different copy with the same rules and the same no-OTP semantics. Extracting the form
 * here is the reuse seam: a second page gets the PIN rule, the state table and the required-field
 * set for free rather than retyping three rules that decide whether an order can be priced.
 * Nothing else for Phase 2 is built here - no route, no contribution component, no flag.
 *
 * THE TYPE LIVES HERE BECAUSE THE FORM IS THE ONLY THING THAT CONSTRUCTS ONE. The identity card
 * only reads an address, and the cart page only passes one through, so a shared `src/types`
 * module would be a third file nobody owns.
 *
 * NINE STORED KEYS, SIX RENDERED INPUTS, AND THE TYPE IS THE WIRE SHAPE
 * --------------------------------------------------------------------
 * `StoredAddress` mirrors what `lambda_utils.ecommerce.contact_address.normalize_for_storage`
 * emits, exactly - including the three fields this form never collects:
 *
 *   - `locality` is always "" from here, carried because `normalize_address` emits it;
 *   - `country` / `countryCode` are fixed to India by this form, and the server defaults them;
 *   - `fullAddress` is SERVER-DERIVED and the identity card renders it verbatim.
 *
 * Keeping the type equal to the wire shape means `CheckoutProfileValue.address`, the save reply
 * and the `action:"profile"` reply are all one type with no mapping layer to drift.
 *
 * WHAT THIS FORM POSTS, AND WHAT IT DELIBERATELY OMITS
 * ---------------------------------------------------
 * `addressPayload` emits the five collected fields only. It does NOT send `countryCode`, because
 * `normalize_for_storage` defaults it to IN locally at its step 2 - before the PIN rule runs -
 * so an India address with no country code is the path that is actually tested server-side.
 * Sending a value the server is about to default would add a field with no reader.
 *
 * STATE IS A SELECT, NOT FREE TEXT, AND THAT IS A CORRECTNESS DECISION NOT A STYLING ONE
 * -------------------------------------------------------------------------------------
 * The subdivision is the place of supply, so it decides the CGST/SGST versus IGST split. A typed
 * state that `wix_address.india_subdivision` cannot resolve saves fine and then refuses at pay
 * time with nothing on screen to say which spelling was wanted. The options come from
 * `src/config/indiaSubdivisions.ts`, which a drift test holds equal to the Python table.
 *
 * THE CLIENT RULES ARE A MIRROR, NOT THE AUTHORITY
 * -----------------------------------------------
 * PIN `^[1-9][0-9]{5}$` and the required set (line 1, city, state, PIN) restate
 * `contact_address._RULES` so a customer gets immediate feedback instead of a round trip. The
 * server re-validates every one of them and names the failing field; `invalidField` is how that
 * answer gets marked on the right input.
 */
export interface StoredAddress {
  addressLine1: string;
  addressLine2: string;
  locality: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  countryCode: string;
  fullAddress: string;
}

/** What the six inputs hold. The five fields this form actually collects. */
export interface AddressDraft {
  addressLine1: string;
  addressLine2: string;
  city: string;
  state: string;
  postalCode: string;
}

/** The only country this form offers, matching `identity.address.DEFAULT_COUNTRY`. */
export const ADDRESS_COUNTRY = 'India';

/** `contact_address._INDIA_PIN_RE`, mirrored. Six digits, never leading zero. */
export const INDIA_PIN_RE = /^[1-9][0-9]{5}$/;

export const EMPTY_ADDRESS_DRAFT: AddressDraft = {
  addressLine1: '',
  addressLine2: '',
  city: '',
  state: '',
  postalCode: '',
};

/** Pre-fill from a stored address, dropping the server-derived and form-fixed fields. */
export function draftFromStored ( address: StoredAddress | null | undefined ): AddressDraft {
  if ( !address ) return { ...EMPTY_ADDRESS_DRAFT };
  return {
    addressLine1: String( address.addressLine1 || '' ),
    addressLine2: String( address.addressLine2 || '' ),
    city: String( address.city || '' ),
    state: String( address.state || '' ),
    postalCode: String( address.postalCode || '' ),
  };
}

/** The required-field and PIN mirrors, in one place so every mode asks the same question. */
export function addressDraftValid ( draft: AddressDraft ): boolean {
  return draft.addressLine1.trim().length > 0
    && draft.city.trim().length > 0
    && draft.state.trim().length > 0
    && INDIA_PIN_RE.test( draft.postalCode.trim() );
}

/** The `address` object to post. Five collected fields; the server defaults the rest. */
export function addressPayload ( draft: AddressDraft ): Record<string, string> {
  return {
    addressLine1: draft.addressLine1.trim(),
    addressLine2: draft.addressLine2.trim(),
    city: draft.city.trim(),
    state: draft.state.trim(),
    postalCode: draft.postalCode.trim(),
  };
}

interface Props {
  value: AddressDraft;
  onChange: ( next: AddressDraft ) => void;
  /** True while a save is in flight. */
  disabled?: boolean;
  /**
   * The field name the server returned alongside `INVALID_ADDRESS`, so the form marks the input
   * the customer has to fix rather than showing a form-level message for a single bad field.
   */
  invalidField?: string;
}

const AddressFields: React.FC<Props> = ( { value, onChange, disabled, invalidField } ) => {
  const patch = ( field: keyof AddressDraft, next: string ) =>
    onChange( { ...value, [ field ]: next } );

  const pinEntered = value.postalCode.trim().length > 0;
  const pinBad = pinEntered && !INDIA_PIN_RE.test( value.postalCode.trim() );

  /*
   * The six fields are written out inline rather than mapped from a table or lifted into a
   * helper. styled-jsx only stamps its scoping class onto JSX that sits in the same return tree
   * as the <style jsx> block, so JSX produced by a helper would render with unhashed class names
   * and lose every rule below. PillButton and RotatingHero both record this costing a debugging
   * round; do not refactor these into a loop.
   */
  return (
    <fieldset className="address-fields" disabled={ disabled }>
      <legend>Delivery address</legend>

      <div className="address-grid">
        <label className="span-2">
          <span>Address line 1</span>
          <input
            value={ value.addressLine1 }
            onChange={ event => patch( 'addressLine1', event.target.value ) }
            autoComplete="address-line1"
            maxLength={ 200 }
            placeholder="House or flat, building, street"
            aria-invalid={ invalidField === 'addressLine1' ? 'true' : undefined }
          />
        </label>

        <label className="span-2">
          <span>Address line 2</span>
          <input
            value={ value.addressLine2 }
            onChange={ event => patch( 'addressLine2', event.target.value ) }
            autoComplete="address-line2"
            maxLength={ 200 }
            placeholder="Area or landmark (optional)"
            aria-invalid={ invalidField === 'addressLine2' ? 'true' : undefined }
          />
        </label>

        <label>
          <span>City</span>
          <input
            value={ value.city }
            onChange={ event => patch( 'city', event.target.value ) }
            autoComplete="address-level2"
            maxLength={ 100 }
            placeholder="City"
            aria-invalid={ invalidField === 'city' ? 'true' : undefined }
          />
        </label>

        <label>
          <span>State</span>
          <select
            value={ value.state }
            onChange={ event => patch( 'state', event.target.value ) }
            autoComplete="address-level1"
            aria-invalid={ invalidField === 'state' ? 'true' : undefined }
          >
            <option value="">Select a state</option>
            { INDIA_SUBDIVISION_NAMES.map( name => (
              <option key={ name } value={ name }>{ name }</option>
            ) ) }
          </select>
        </label>

        <label>
          <span>PIN code</span>
          <input
            value={ value.postalCode }
            onChange={ event => patch( 'postalCode', event.target.value.replace( /\D/g, '' ).slice( 0, 6 ) ) }
            autoComplete="postal-code"
            inputMode="numeric"
            maxLength={ 6 }
            placeholder="560001"
            aria-invalid={ pinBad || invalidField === 'postalCode' ? 'true' : undefined }
            aria-describedby="address-pin-help"
          />
        </label>

        <label>
          <span>Country</span>
          <input
            value={ ADDRESS_COUNTRY }
            readOnly
            aria-readonly="true"
            autoComplete="country-name"
            className="fixed"
          />
        </label>
      </div>

      <p id="address-pin-help" className="address-help">
        { pinBad
          ? 'Enter a six-digit Indian PIN code.'
          : 'We deliver within India only.' }
      </p>

      <style jsx>{`
        .address-fields{
          margin:18px 0 0;padding:0;border:0;min-inline-size:0;
        }
        legend{
          padding:0;margin:0 0 10px;font-size:12px;font-weight:700;letter-spacing:.08em;
          text-transform:uppercase;color:#1a3a2a;
        }
        .address-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}
        .span-2{grid-column:1 / -1}
        label{display:flex;flex-direction:column;gap:7px;min-inline-size:0}
        label>span{font-size:12px;font-weight:700;color:#1a3a2a}
        input,select{
          min-height:52px;box-sizing:border-box;border:1px solid #e5e7eb;border-radius:10px;
          padding:0 14px;background:#fff;color:#1a1a1a;font:inherit;font-size:16px;outline:none;
        }
        input:focus-visible,select:focus-visible{
          outline:3px solid #1a3a2a;outline-offset:2px;border-color:#1a3a2a;
        }
        input[aria-invalid='true'],select[aria-invalid='true']{border-color:#8c1d18}
        .fixed{background:#f6f7f6;color:rgba(0,0,0,.66)}
        .address-help{margin:10px 0 0;font-size:14px;line-height:1.5;color:rgba(0,0,0,.66)}
        @media(max-width:767px){
          .address-grid{grid-template-columns:1fr}
          .span-2{grid-column:auto}
        }
      `}</style>
    </fieldset>
  );
};

export default AddressFields;
