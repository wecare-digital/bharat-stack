# The link-preview card, re-exported for WhatsApp

`wd-brand-16x9.png` in this folder is **not served from here**. It is the replacement for the
live object and exists in the repo so it can be reviewed in a diff and uploaded by someone with
write access to the bucket.

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

## ORDERING — this matters

`og:image:width` and `og:image:height` are declared in code, in `src/config/share.ts` and
`src/pages/_app.tsx`, and the PR that added this folder changes them from 1440x810 to 1200x675.
The repo already had a bug where these declared 512x512 against a 1080x1080 file, and
`BrandAssets.test.ts` exists partly to stop it recurring — so the declaration and the object need
to agree.

**Upload first, then merge**, and the two never disagree. If the code merges first the only
consequence is cosmetic and temporary: crawlers reserve layout from a size hint that is 240px too
tall until the upload lands. The image itself keeps working throughout, because the URL does not
change. It is worth getting the order right, but it is not an outage either way.
