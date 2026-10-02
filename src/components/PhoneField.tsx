import React from 'react';
import { DIAL_CODES } from '../lib/dialCodes';

/**
 * ONE FIELD, DIVIDED: a country-code segment and a number segment inside a single rounded outline.
 *
 * WHAT THE OWNER ASKED FOR, AND THE HISTORY BEHIND IT. This control has been through both extremes.
 * It started as a separate <select> sitting BESIDE a national-number input - two boxes, visibly two
 * fields. The owner then asked for "phone numbr and whatsapp ountrycode hsod in one feid", so it
 * became a single <input> where the shopper typed "+91 9876543210" and the page parsed it. The
 * instruction now is "countcode + number should bin same dived divide and rounded corner": one
 * field, but divided, with rounded corners. That is the international-phone pattern - a single
 * outlined container, split by a hairline, holding two controls.
 *
 * It resolves the tension in the middle version rather than reverting it. Typing your own country
 * code is work, and getting it wrong was punished with an error message; a segment that always
 * carries a code removes both. The guarantee that mattered survives untouched: the country code is
 * SHOWN rather than inferred (see DEFAULT_DIAL_CODE), so nobody is quietly signed in as Indian.
 *
 * MATERIAL 3, AND WHERE THIS DEPARTS FROM IT. Anatomy follows the M3 outlined text field: an
 * outlined container, a label above, supporting text below, and a leading section inside the
 * container. Two deliberate departures, both named so neither looks like an oversight:
 *
 *   1. CORNER RADIUS. The M3 default is `--md-sys-shape-corner-extra-small` = 4px. This uses 10px,
 *      which is the radius every other field on this site already has. Site consistency wins over
 *      importing a framework default into a page that is not otherwise M3, and 10px is the more
 *      "rounded corner" of the two, which is what was asked for.
 *   2. THE DIVIDER IS NOT AN M3 FEATURE. M3 offers `prefix-text` for static in-field context (the
 *      "$" in a currency field) and leading/trailing icon slots. It has no interactive leading
 *      segment and no divider inside a text field, so there is no token to follow. The rule here is
 *      the site's own 1px #e5e7eb hairline, used as a segment separator on owner instruction.
 *
 * WHICH M3 REPO IS AUTHORITATIVE, because they disagree and the answer changed.
 *
 * Google's material-components/material-web is the original and is where the component docs still
 * live, but its own README is now carried forward by material-esm/material, a fork that states the
 * upstream project "seems to be on hold". The fork is the maintained one, so it is the reference of
 * record here. Both are cited: the doc prose is still only in Google's repo, the current code is in
 * the fork.
 *
 *   - Fork (maintained, code):  https://github.com/material-esm/material
 *   - Google (docs prose):      https://github.com/material-components/material-web/blob/main/docs/components/text-field.md
 *
 * WHAT THE FORK CHANGED, read from text/text-field.js rather than assumed:
 *   - ONE ELEMENT, NOT TWO. `<md-text-field color="outlined">` replaces `<md-outlined-text-field>`,
 *     so the token is `--md-text-field-container-shape`, NOT the `--md-outlined-text-field-...`
 *     spelling an earlier version of this comment named. That older name is simply wrong against the
 *     maintained library, which is why it is corrected rather than left as a second-best citation.
 *   - THE 4px DEFAULT SURVIVED. It still resolves
 *     `var(--md-text-field-container-shape, var(--md-sys-shape-corner-extra-small, 4px))`, so
 *     departure (1) above is still a real departure and the 10px here is still a deliberate choice,
 *     not a stale number.
 *   - PER-CORNER LOGICAL SHAPE TOKENS: container-shape-start-start / start-end / end-end /
 *     end-start. Worth recording because that is exactly the shape of what .pf-code and .pf-num do
 *     by hand below - square against the divider, 9px on the outside, spelled logically so the two
 *     segments swap in RTL. The approach matches the library's own, arrived at independently.
 *
 * NOTHING IS INSTALLED FROM EITHER REPO, and that is deliberate. Both ship Lit web components; this
 * site is Next.js with styled-jsx and has no Lit dependency, so adopting them would mean a runtime,
 * a custom-element registry and a second styling system on a page that currently has none of the
 * three. M3 is used here as a SPEC to measure against, not as a dependency.
 *
 * FOCUS IS PER SEGMENT, NOT PER CONTAINER, AND THAT IS AN ACCESSIBILITY DECISION. The obvious way to
 * keep the one-field illusion is `:focus-within` on the container - but there are TWO focusable
 * controls inside it, so a ring around the whole box tells a keyboard user that focus is somewhere
 * in there without saying which half. That fails what WCAG 2.4.7 is for. Each segment therefore
 * draws its own ring, INSET (outline-offset:-3px) so it sits inside the container's outline instead
 * of drawing a second box around it. The field still reads as one control; the focused half is
 * unambiguous.
 *
 * NO RED, on standing owner instruction. The invalid state is carried by aria-invalid and the
 * message the page renders beneath - not by a colour. A control that only says "wrong" in red says
 * nothing to a colour-blind shopper either way.
 */

export interface PhoneFieldProps {
  /** id of the NUMBER input, so a visible <label htmlFor> outside this component can point at it. */
  id: string;
  /** The selected dial code, with its plus, e.g. "+91". */
  dialCode: string;
  onDialCodeChange: ( next: string ) => void;
  /** The national number, exactly as typed. Never normalised here. */
  number: string;
  onNumberChange: ( next: string ) => void;
  disabled?: boolean;
  /** Mirrors aria-invalid on both segments: the field is wrong as a whole, not one half of it. */
  invalid?: boolean;
  /** id list for aria-describedby - the hint, plus the error when there is one. */
  describedBy?: string;
  placeholder?: string;
  /**
   * Fires when the browser's own constraint validation refuses the number segment -
   * which, since `required` is the only constraint here, means it was empty at submit.
   *
   * WHY THE CONSUMER NEEDS THIS AT ALL. `required` makes the browser block submit and
   * show its native bubble, so the consumer's onSubmit never runs and the consumer's own
   * error state is never set. The result is a failure announced ONLY by a transient
   * native tooltip: no aria-invalid, no aria-describedby, nothing left on screen once the
   * bubble dismisses. This hook lets the consumer mirror the refusal into its own error
   * region without removing `required` - so the native affordance is kept and the
   * programmatic association is added, rather than one being traded for the other.
   */
  onInvalid?: ( event: React.FormEvent<HTMLInputElement> ) => void;
}

/**
 * A FORMAT MASK, NOT A SPECIMEN NUMBER, and the distinction is the whole point.
 *
 * This was `9876543210` - ten digits starting with 9, which is a structurally valid Indian
 * mobile number. Rendered in placeholder grey beside a segment already reading "+91 India",
 * it reads as a number that is ALREADY IN THE FIELD. A shopper who believes the field is
 * filled presses the CTA, the `required` constraint refuses an empty input, and the browser
 * answers "Please fill out this field." about a field that visibly contains a number. That
 * is the shape of the reported sign-in failure.
 *
 * Zeros in two groups cannot be mistaken for a value: an Indian mobile number never begins
 * with 0, and the grouping reads as a mask. It is also LANGUAGE-NEUTRAL, which a worded hint
 * would not be - placeholder text is an attribute, and SupportWidget's translation walker
 * rewrites text nodes only (the same cost recorded on the country-code aria-label below), so
 * "10-digit number" would stay English for every non-English shopper.
 *
 * The consumer may still override it; this is the default, not a constraint.
 */
export const NUMBER_FORMAT_HINT = '00000 00000';

const PhoneField: React.FC<PhoneFieldProps> = ( {
  id, dialCode, onDialCodeChange, number, onNumberChange,
  disabled, invalid, describedBy, placeholder, onInvalid,
} ) => (
  <div className="pf">
    {/*
      * aria-label, and the cost is stated rather than hidden: attribute text is not translated by
      * SupportWidget's walker, which rewrites text nodes only. The alternative was a visually
      * hidden <label>, and the owner has explicitly rejected hidden text elsewhere in this header.
      * A select with no name at all is not an option - it announces as a bare combobox.
      */}
    <select
      className="pf-code"
      aria-label="Country code"
      value={ dialCode }
      onChange={ e => onDialCodeChange( e.target.value ) }
      disabled={ disabled }
      aria-invalid={ invalid ? 'true' : undefined }
    >
      { DIAL_CODES.map( entry => (
        // The code is the value AND the start of the label, so the closed select shows "+91" while
        // the open list shows which country that is. data-wc-no-translate on the code would be
        // wrong here - the country name SHOULD translate - so only the name is free text.
        <option key={ entry.code } value={ entry.code }>
          { entry.code } { entry.country }
        </option>
      ) ) }
    </select>

    <input
      id={ id }
      className="pf-num"
      type="tel"
      inputMode="tel"
      /*
       * tel-national, NOT tel. The browser is filling the number segment only - the country code is
       * the select's job - and offering a full international number here would land a "+91" inside
       * a field that already has one beside it.
       */
      autoComplete="tel-national"
      placeholder={ placeholder === undefined ? NUMBER_FORMAT_HINT : placeholder }
      required
      value={ number }
      onChange={ e => onNumberChange( e.target.value ) }
      onInvalid={ onInvalid }
      disabled={ disabled }
      aria-invalid={ invalid ? 'true' : undefined }
      aria-describedby={ describedBy }
    />

    <style jsx>{`
      /* THE ONE FIELD. The outline, the radius and the height live here, on the container, and the
         two segments inside carry none of their own - that is what makes it read as a single
         control rather than two boxes that happen to touch.
         52px matches the CTA this field feeds and every other input on the site. 10px is the site's
         field radius; see the note above for why it is not M3's 4px default.
         overflow:hidden so neither segment's own background can square off the rounded corners. */
      .pf{
        display:flex;align-items:stretch;
        min-height:52px;box-sizing:border-box;
        border:1px solid #e5e7eb;border-radius:10px;background:#fff;
        margin-bottom:20px;overflow:hidden;
      }

      /* THE DIVIDER, as a logical inline-end border on the leading segment rather than a separate
         element: one declaration, and it mirrors on its own in an RTL document, where the code
         segment moves to the right and the hairline has to move with it. border-inline-end is why
         this does not need an rtlcheck exception. */
      .pf-code{
        flex:0 0 auto;
        border:0;border-inline-end:1px solid #e5e7eb;
        padding-inline:12px;
        background:#fff;color:#1a1a1a;
        font-family:inherit;font-size:17px;
        cursor:pointer;
        /* LOGICAL CORNERS, 9px = the container's 10px minus its 1px border, so this segment's
           leading corners sit flush inside the container's and its trailing corners stay square
           against the divider. Measured reason, not neatness: the inset focus ring follows
           border-radius, and src/styles/button.css puts a GLOBAL 13px radius on controls, which was
           measured bleeding onto the number input - a 13px ring corner inside a 10px container.
           The start/end spellings mirror on their own, so the rounded end follows the code segment
           when it moves to the right in an RTL document. */
        border-start-start-radius:9px;border-end-start-radius:9px;
        border-start-end-radius:0;border-end-end-radius:0;
      }
      /* The platform's own disclosure arrow is kept - a CSS-drawn one would be a second chevron on a
         page that already has the header's, drawn by different means. */

      /* The number segment takes the rest. min-inline-size:0 because a flex item's default
         min-width:auto lets a long value push the container wider than its parent. */
      .pf-num{
        flex:1 1 auto;min-inline-size:0;
        border:0;padding-inline:16px;
        background:#fff;color:#1a1a1a;
        font-family:inherit;font-size:17px;
        /* scroll-margin-top CLEARS THE FIXED 108px HEADER, and it is on the INPUT rather
           than on .pf because the input is what the browser scrolls to.
           MEASURED, not precautionary. When the browser reveals this control - on focus,
           on autofocus, or as part of refusing an empty required field - it scrolls it
           to the top of the scrollport, and the scrollport's top is UNDER the fixed
           header. At 320x568 the field landed 36px behind the header and at 390x400 (the
           height a phone has left with its keyboard open) 50px behind it, so the shopper
           could not see the number they were typing. With this declaration both measure
           0px covered.
           128px/112px are the site's existing clearance constants for this exact header,
           used the same way by .lgd-section and .cl in LegalDocument and ContactLocation.
           WHY NOT html{scroll-padding-top}, which is the tidier-looking fix: those two
           components already carry their own scroll-margin-top, and scroll-padding on the
           scrollport ADDS to scroll-margin on the target - so a document-level inset would
           silently double their anchor clearance to 256px. Measured both ways; this one
           fixes the field without touching anything else. */
        scroll-margin-top:128px;
        /* The mirror image of the code segment's corners: square against the divider, 9px on the
           outside. This is also what overrides the global 13px from button.css. */
        border-start-start-radius:0;border-end-start-radius:0;
        border-start-end-radius:9px;border-end-end-radius:9px;
      }

      /* INSET RINGS, one per segment. outline-offset:-3px draws the ring inside the segment, so the
         container's own rounded outline stays whole and the focused half is named unambiguously.
         The ring is the site's #1a3a2a at 3px, the same indicator every other control uses. */
      .pf-code:focus-visible,
      .pf-num:focus-visible{
        outline:3px solid #1a3a2a;outline-offset:-3px;
      }

      /* Disabled is a tint on the whole field, not on one segment, because both go at once. */
      .pf-code:disabled,.pf-num:disabled{background:#f6f7f5;color:rgba(0,0,0,.54);cursor:default}

      /* NARROW VIEWPORTS. At 320px the field has roughly 288px to work with; the code segment is
         content-sized so a three-digit code like +971 does not get clipped, and the number segment
         absorbs the rest. The padding tightens rather than the segments shrinking, so the 52px
         target height is never traded away. */
      /* The header is 96px below 768px, so the clearance steps with it - the same
         128px/112px pair .lgd-section and .cl use. Declared in its own query because the
         header's breakpoint is 767px and the padding tightening below is at 360px. */
      @media(max-width:767px){
        .pf-num{scroll-margin-top:112px}
      }

      @media(max-width:360px){
        .pf-code{padding-inline:8px}
        .pf-num{padding-inline:12px}
      }
    `}</style>
  </div>
);

export default PhoneField;
