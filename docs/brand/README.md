# The link-preview card, re-exported for WhatsApp

> ## STATUS: OPTIONAL. Nothing is waiting on this upload.
>
> The site's `og:image` is now **`wecare-digital.png`**, the 1080x1080 icon that was already live
> at 86,123 bytes — chosen on owner instruction precisely because it needs no upload and is inside
> every limit described below. Link previews work today on every surface.
>
> This folder keeps the re-exported **wide** card as the documented way back to a bigger, more
> branded preview. It carries the mark, the wordmark and the tagline, which the icon does not, and
> it renders as a full-width banner rather than a compact thumbnail. If you want that, upload it
> and make the three-line change in *Adopting the wide card* at the bottom.
>
> The rest of this file is the record of why the original card could not be used as it was.

`wd-brand-16x9.png` in this folder is **not served from here**. It exists in the repo so it can be
reviewed in a diff and uploaded by someone with write access to the bucket.

## Why it was re-exported

The live card was **801,077 bytes (782 KB)**. Meta's own
[WhatsApp link-preview documentation](https://developers.facebook.com/docs/whatsapp/link-previews)
requires `og:image` to be an absolute URL **under 600 KB**, at least 300px wide, with an aspect
ratio of 4:1 or less. Field guidance puts the safe ceiling nearer **300 KB**, because WhatsApp
drops an oversized image silently rather than reporting it — Facebook and LinkedIn accept
megabytes, which is exactly why this went unnoticed.

So WhatsApp previews were most likely image-less on **every page on the site, including the home
page**, which already pointed at this asset. The dimensions were never the problem. The bytes
were.

## What changed

| | before | after |
|---|---|---|
| pixels | 1440 x 810 | **1200 x 675** |
| aspect | 16:9 (1.7778) | **16:9 (1.7778)** — unchanged |
| bytes | 801,077 (782.3 KB) | **279,367 (272.8 KB)** |
| colour type | 2, truecolour RGB | 3, palette (128 colours) |
| alpha | none | none — still fully opaque |

**The artwork is not cropped.** It is a straight LANCZOS downscale, so the composition, the
margins and every element are exactly as they were. That is why the aspect ratio is unchanged and
the `16x9` in the filename is still accurate.

1200 x 630 was considered, since 1.91:1 is the ratio the platforms document as ideal. It was
rejected: reaching it from 16:9 needs a 27px crop off each edge, and it would have made the
filename describe the wrong shape. 16:9 is comfortably inside every platform's limits and is what
this asset has always been, so the only thing worth changing was the weight.

**Palette rather than truecolour** is what buys the reduction. The artwork is flat — one green
ground, one off-white, one lighter green swoosh, plus antialiasing — so 128 colours reproduce it
at RMSE 1.19 against the downscale, with a maximum per-channel error of 19/255 and no visible
banding on the wordmark or the tagline panel. Recompressing at the original 1440 x 810 was tried
first and could not get under 300 KB at acceptable quality: palette-128 still measured 355 KB. The
resolution reduction is what makes it fit.

It remains **fully opaque**, which is the binding rule for this slot — see
`src/test/BrandAssets.test.ts`. There is no `tRNS` chunk and every alpha sample is 255. An asset
handed to a renderer we do not control must not rely on alpha, because Apple and the link-preview
services flatten it to black and the mark is light.

## How to publish it

Upload to the **same key**, so every existing share improves as the scraper caches expire and no
URL anywhere has to change:

```
s3://wecare-digital-get/o/stream/media/m/wd-brand-16x9.png
```

Keep `Content-Type: image/png`.

```sh
aws s3 cp docs/brand/wd-brand-16x9.png \
  s3://wecare-digital-get/o/stream/media/m/wd-brand-16x9.png \
  --content-type image/png --cache-control 'public, max-age=31536000, immutable'
```

Then invalidate the CloudFront path so the edge stops serving the 782 KB copy:

```sh
aws cloudfront create-invalidation --distribution-id E2GP22R4BIFGQ3 \
  --paths '/get/o/stream/media/m/wd-brand-16x9.png'
```

Verify:

```sh
curl -sI https://wecare.digital/get/o/stream/media/m/wd-brand-16x9.png \
  | grep -i 'content-length\|content-type'
```

`content-length` should read about 279367, not 801077.

## Adopting the wide card

Three values move together, and they must move in one commit. The shape of the image and the
Twitter card type are a pair: a 1.91:1 image in a `summary` slot is squeezed into a small square,
and a 1:1 image in a `summary_large_image` slot is centre-cropped top and bottom — which is the
defect that took the ends off this mark once already.

In `src/config/share.ts`:

```ts
export const SOCIAL_CARD_URL = `${MEDIA_BASE}/wd-brand-16x9.png`;
export const SOCIAL_CARD_W = '1200';
export const SOCIAL_CARD_H = '675';
export const SHARE_CARD_TYPE = 'summary_large_image';
```

And the matching three in `src/pages/_app.tsx`, which keeps its own copies — `SOCIAL_CARD_URL`
there is currently aliased to `LOGO_URL`, so it becomes the literal again, plus its inline
`twitter:card` string.

`src/test/ShareMeta.test.tsx` asserts the pairing rather than the values: if the declared image is
square the card must be `summary`, otherwise it must be the large one. So it will accept this
change and reject a half-finished one. `BrandAssets.test.ts` names the current asset explicitly and
will need its link-preview case updated with it.

**Upload before merging.** The declaration and the object should never disagree — the repo already
had a bug where these read 512x512 against a 1080x1080 file. Getting the order wrong is cosmetic
rather than an outage: crawlers reserve layout from a wrong size hint until the upload lands, and
the image keeps working throughout because the URL does not change.
