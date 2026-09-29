/**
 * THE LINK-PREVIEW CARD, AND THE WHATSAPP SHARE TARGET.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * /blog/ and /post/<slug>/ shipped NO og:image, NO twitter:image and - on the post page - a
 * twitter:card of "summary" rather than "summary_large_image". Measured on the live site:
 *
 *   /                      og:image present, twitter:card summary_large_image
 *   /blog/                 og:image MISSING, twitter:card MISSING
 *   /post/<slug>/          og:image MISSING, twitter:image MISSING, twitter:card summary
 *
 * The cause is the same `!isContentPublic` gate in pages/_app.tsx that used to swallow the
 * favicon: the sitewide Head carrying og:image is suppressed for the five content routes
 * because they declare their own, and their own never declared an image. So every blog and post
 * link shared to WhatsApp, Facebook, LinkedIn, X, Slack or iMessage unfurled as text only - on
 * the pages most likely to be shared.
 *
 * _app.tsx KEEPS ITS OWN COPY of these literals and is not changed to import this file.
 * src/test/BrandAssets.test.ts pins those declarations to that file by source string, and
 * rewriting them would mean moving six assertions for no behavioural gain. Instead
 * ShareMeta.test.tsx asserts the value here and the literal there are the SAME string, so the
 * two cannot drift apart silently. Content pages read this file; the marketing branch reads its
 * own; a test holds them equal.
 *
 * WHICH ASSET, AND WHY NOT THE OTHER TWO
 * --------------------------------------
 * wd-brand-16x9.png only. BrandAssets.test.ts explains the rule at length: an asset handed to a
 * renderer we do not control must be OPAQUE, because Apple and the link-preview services
 * flatten alpha to black and the mark is black. wecaredigital.png is 68% transparent and is
 * banned from exactly this slot. wecare-digital.png is opaque but square, and a 1:1 image in a
 * summary_large_image card is centre-cropped top and bottom.
 *
 * KNOWN DEFECT, NOT INTRODUCED HERE, AND IT AFFECTS THE WHOLE SITE
 * ---------------------------------------------------------------
 * The first version of this file recorded the card as a known defect: wd-brand-16x9.png was
 * 801,077 bytes - 782 KB - against the 600 KB ceiling Meta's own WhatsApp link-preview
 * documentation states, with field guidance putting the working limit nearer 300 KB because
 * WhatsApp discards an oversized image silently rather than reporting it. WhatsApp previews were
 * therefore image-less on EVERY page including the home page, which already pointed here.
 *
 * THAT IS NOW FIXED, and the replacement is committed at docs/brand/wd-brand-16x9.png: the same
 * artwork downscaled to 1200x675 with a 128-colour palette, 279,367 bytes, no crop, still fully
 * opaque. It goes to the SAME canonical S3 key, so no URL changes anywhere and every existing
 * share improves as the scraper caches expire.
 *
 * WHAT WAS REJECTED. 1200x630 is the 1.91:1 ratio the platforms document as ideal, and reaching it
 * from 16:9 needs a 27px crop off each edge - which would also have made the 16x9 in the filename
 * describe the wrong shape. 16:9 is well inside WhatsApp's 4:1 ceiling and is what this asset has
 * always been, so the only thing worth changing was the weight. A second, lighter copy under
 * public/ was rejected too: two social cards on one site is a question about which is current,
 * which is the class of problem BrandAssets.test.ts exists to prevent.
 *
 * ORDERING: the upload should land before this code does, because SOCIAL_CARD_W/H below now
 * declare 1200x675. See docs/brand/README.md, which also explains why getting it the wrong way
 * round is cosmetic rather than an outage.
 */

/** Canonical media folder. Must stay byte-identical to MEDIA_BASE in pages/_app.tsx. */
export const MEDIA_BASE = 'https://wecare.digital/get/o/stream/media/m';

/** 1200x675, 16:9, palette PNG with no alpha. The link-preview card for every public surface. */
export const SOCIAL_CARD_URL = `${MEDIA_BASE}/wd-brand-16x9.png`;

/**
 * Declared at the asset's REAL pixel size. These were once 512x512 against a 1080x1080 file;
 * crawlers use the hint to reserve layout before fetching, so a wrong value is worse than none.
 *
 * 1200x675, DOWN FROM 1440x810, and the reason is bytes rather than shape. The old export was
 * 801,077 bytes against the 600 KB ceiling Meta documents for a WhatsApp preview, so the card was
 * being dropped on the one platform this company is built around. A straight downscale to 1200
 * wide plus a 128-colour palette brings the same artwork to 279,367 bytes with no crop and no
 * visible loss; recompressing at 1440x810 could not get under 300 KB at acceptable quality, so the
 * resolution reduction is what makes it fit. The aspect ratio is unchanged, which is why the 16x9
 * in the filename is still true.
 *
 * ShareMeta.test.tsx reads the committed replacement in docs/brand/ and asserts its real IHDR
 * dimensions equal these two strings, so the pair cannot drift from the asset again.
 * See docs/brand/README.md for the upload, and for why it should land before this does.
 */
export const SOCIAL_CARD_W = '1200';
export const SOCIAL_CARD_H = '675';
export const SOCIAL_CARD_TYPE = 'image/png';

/**
 * og:image:alt is read out by screen readers on the platforms that render the card, so it
 * describes the image rather than repeating the page title - the title is already the next line
 * of the same card.
 */
export const SOCIAL_CARD_ALT = 'The WECARE.DIGITAL wordmark on a white field';

export const SITE_ORIGIN = 'https://wecare.digital';

/**
 * WHATSAPP SHARE URL: api.whatsapp.com, NOT wa.me - and that is a correctness issue rather than
 * a preference.
 *
 * Both hosts accept the same ?text= parameter, but wa.me is built around wa.me/<number>: called
 * without a phone number it serves an error page instead of a chat picker. A share button does
 * not know who the reader wants to send the link to, so the number cannot be supplied, and
 * api.whatsapp.com/send is the documented form that opens the contact picker with the message
 * pre-filled. It also resolves correctly on desktop, where it hands off to WhatsApp Web.
 *
 * The text is a single encoded string holding the title and the URL, because WhatsApp has one
 * message field - there is no separate url parameter to fill.
 */
export const whatsappShareHref = ( title: string, url: string ): string =>
  `https://api.whatsapp.com/send?text=${encodeURIComponent( `${title}\n\n${url}` )}`;
