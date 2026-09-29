/**
 * THE LINK-PREVIEW IMAGE, AND THE WHATSAPP SHARE TARGET.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * /blog/ and /post/<slug>/ shipped NO og:image and NO twitter:image at all. Measured on the live
 * site:
 *
 *   /                      og:image present
 *   /blog/                 og:image MISSING, twitter:card MISSING
 *   /post/<slug>/          og:image MISSING, twitter:image MISSING
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
 * THE IMAGE IS THE EXISTING ICON, ON OWNER INSTRUCTION
 * ---------------------------------------------------
 * wecare-digital.png - the 1080x1080 bag-and-heart mark on a white ground, the same asset that
 * already serves apple-touch-icon, the schema.org Organization logo and the PWA manifest. Chosen
 * over the wide wd-brand-16x9.png card for one decisive reason: the icon is 86,123 bytes and the
 * card is 801,077.
 *
 * Meta's own WhatsApp link-preview documentation caps og:image at 600 KB, with field guidance
 * putting the working limit nearer 300 KB because WhatsApp discards an oversized image silently
 * rather than reporting it. The wide card failed that by a wide margin, so WhatsApp previews were
 * image-less on every page of a site whose business is WhatsApp - and fixing it meant re-exporting
 * the asset and uploading it to S3, which is a step this repo cannot take on its own. The icon is
 * already live, already opaque, and already inside every limit: 1080px wide against a 300px
 * minimum, 1:1 against a 4:1 ceiling, 84 KB against 600. Nothing has to be uploaded for previews
 * to start working.
 *
 * WHY NOT THE OTHER TWO ASSETS. wecaredigital.png is 68% transparent and is banned from this slot
 * outright - Apple and the preview services flatten alpha to black and the mark is black, so it
 * would unfurl as a black square. wd-brand-16x9.png is the designed card with the wordmark and the
 * tagline, and it is the better-looking preview; a re-export at 1200x675 / 273 KB is committed at
 * docs/brand/wd-brand-16x9.png if the wide card is ever wanted back. That is a one-line change
 * here plus the upload.
 *
 * WHAT THIS COSTS, STATED PLAINLY. A square image cannot be a full-width hero card. The preview is
 * now the compact form - a small square thumbnail beside the title and description - rather than a
 * wide branded banner, and it no longer carries the "Building digital railroads for Everyday
 * Bharat" line. In exchange it works today, everywhere, with no upload.
 *
 * WHICH IS WHY THE CARD TYPE CHANGED TOO. See SHARE_CARD_TYPE below - a 1:1 image in a
 * summary_large_image slot is centre-cropped, which is the defect BrandAssets.test.ts was written
 * to prevent. Square image, small card. The two go together and must not be separated.
 */

/** Canonical media folder. Must stay byte-identical to MEDIA_BASE in pages/_app.tsx. */
export const MEDIA_BASE = 'https://wecare.digital/get/o/stream/media/m';

/** 1080x1080, opaque white ground, 86,123 bytes. The link-preview image for every public surface. */
export const SOCIAL_CARD_URL = `${MEDIA_BASE}/wecare-digital.png`;

/**
 * Declared at the asset's REAL pixel size. These were once 512x512 against a 1080x1080 file;
 * crawlers use the hint to reserve layout before fetching, so a wrong value is worse than none.
 * ShareMeta.test.tsx fetches nothing, but it does hold these equal to the copies in _app.tsx, and
 * the pair is 1080x1080 because that is what the object at the URL above measures.
 */
export const SOCIAL_CARD_W = '1080';
export const SOCIAL_CARD_H = '1080';
export const SOCIAL_CARD_TYPE = 'image/png';

/**
 * THE CARD TYPE IS TIED TO THE IMAGE'S SHAPE, and that is the whole point of naming it here rather
 * than writing the string into three heads.
 *
 * "summary" renders a small square thumbnail beside the text, which is the correct frame for a 1:1
 * image. "summary_large_image" renders a wide banner and CENTRE-CROPS anything that is not roughly
 * 1.91:1 - so pairing it with this square icon would cut the top and bottom off the mark. That
 * exact mistake is what BrandAssets.test.ts was written to catch, and it is easy to reintroduce by
 * changing the image in one place and leaving the card type in another. Both now come from here.
 */
export const SHARE_CARD_TYPE = 'summary';

/**
 * og:image:alt is read out by screen readers on the platforms that render the card, so it
 * describes the image rather than repeating the page title - the title is already the next line
 * of the same card.
 */
export const SOCIAL_CARD_ALT = 'The WECARE.DIGITAL bag-and-heart mark';

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
