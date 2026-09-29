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
 * wd-brand-16x9.png is 801,077 bytes - 782 KB. Meta's own WhatsApp link-preview documentation
 * requires og:image to be under 600 KB, and field guidance puts the safe ceiling nearer 300 KB
 * because WhatsApp drops an oversized image silently rather than reporting it. So WhatsApp
 * previews are likely image-less on EVERY page including the home page, and pointing the content
 * pages at the same asset does not change that either way - it fixes the platforms that do
 * accept it (Facebook, LinkedIn, X, Slack, Discord, iMessage, Teams) and leaves WhatsApp where
 * it already was.
 *
 * The fix is a re-export of the artwork at 1200x630 under 300 KB at the SAME canonical S3 key,
 * which repairs every surface at once and needs no code change. It is deliberately not done by
 * adding a second, lighter copy under public/: that would give the site two social cards and a
 * question about which is current, which is the class of problem BrandAssets.test.ts exists to
 * prevent. See the PR that introduced this file.
 *
 * 1200x630 (1.91:1) is the size every platform documents. This asset is 1440x810 (16:9, 1.78:1),
 * which is inside WhatsApp's stated 4:1 ceiling and renders as a full-width card everywhere, so
 * the dimensions are not the problem - the bytes are.
 */

/** Canonical media folder. Must stay byte-identical to MEDIA_BASE in pages/_app.tsx. */
export const MEDIA_BASE = 'https://wecare.digital/get/o/stream/media/m';

/** 1440x810, RGB, no alpha channel. The link-preview card for every public surface. */
export const SOCIAL_CARD_URL = `${MEDIA_BASE}/wd-brand-16x9.png`;

/**
 * Declared at the asset's REAL pixel size. These were once 512x512 against a 1080x1080 file;
 * crawlers use the hint to reserve layout before fetching, so a wrong value is worse than none.
 */
export const SOCIAL_CARD_W = '1440';
export const SOCIAL_CARD_H = '810';
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
