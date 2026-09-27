# RCS template proposal — no video, card artwork instead

Drafted 2026-09-27. **Nothing here has been created.** These are proposals for you
to edit; §6 has the exact commands when you are ready.

Goal: replace the video-carrying rich cards with something lighter — either pure
text, or a card using the WECARE.DIGITAL card artwork.

---

## 1. What is actually in S3

Measured, not assumed: dimensions decoded from the PNG headers, content types read
from S3, dominant colour sampled from the pixels.

| Key under `stream/media/m/` | Pixels | Ratio | Size | Verdict |
|---|---|---|---|---|
| `wecare-digital-rcs-h.png` | 2800 × 1200 | **7:3** | 89 KB | **Correct shape already.** Used by `rcsmenu` today |
| `wdf.png` | 1254 × 1254 | 1:1 | 1.33 MB | Card **front** — logo, tagline, phone, email, QR |
| `wdb.png` | 1254 × 1254 | 1:1 | 1.08 MB | Card **back** — "hello" + #EverydayBharat |
| `selfservice.png` | 3375 × 3375 | 1:1 | 578 KB | Square, very large |
| `wecare-digital-rcs-v` | 1091 × 1441 | 0.76:1 | 1.16 MB | Portrait, **and no file extension** |
| `wecare-digital-rcs` | 3375 × 3375 | 1:1 | 578 KB | **No file extension** |
| `wecare-digital.png` | 1080 × 1080 | 1:1 | 86 KB | Logo tile |
| `WECARE+SC.png` | — | — | — | **Does not exist** — referenced by `get_started`, dead |

Card artwork brand green sampled from the pixels: **`#01643F`**. Note this is *not*
the site's CSS `--color-primary: #1a3a2a` — the print artwork uses a brighter
green, so anything composited against it must use `#01643F` or the seam shows.

---

## 2. The constraint that decides everything

For a **vertical** rich card the media sits across the top and must be
*horizontal*. Sinch names three acceptable ratios — **2:1, 16:9 or 7:3** —
and Google gives 1440 × 720 as the optimal 2:1 resolution with a **2 MB
recommended maximum** for images. A vertical card with `SHORT` height wants
roughly 3:1 (about 1440 × 480). For a **horizontal** card the thumbnail is
nearer 4:3 (around 605 × 452). Guidance also warns that media alone is a poor
rich card — always pair it with a suggested reply or action.

Sources: [Sinch — sending rich files with RCS](https://support.sinch.com/hc/en-us/articles/53771584704019-Sending-rich-files-with-RCS),
[Google RCS overview](https://pepipost.readme.io/docs/google-rcs-overview),
[RCS rich card media and layout requirements](https://www.smsgatewaycenter.com/blog/kb/what-are-the-media-and-layout-requirements-for-rcs-rich-cards/),
[MessageFlow technical specifications](https://docs.messageflow.com/rcs/first-steps/technical-specifications),
[EnableX rich media reference](https://developer.enablex.io/messaging/rcs-rich-media.html).
*Content was rephrased for compliance with licensing restrictions.*

**So the card artwork cannot be dropped in as-is.** `wdf.png` and `wdb.png` are
1:1. In a vertical card a square gets centre-cropped to roughly 2:1 or 3:1, which
on the front would slice off the QR code and the contact block — the two things
that make it a business card. That is why option C letterboxes rather than crops.

---

## 3. Option A — text only, no media at all

The literal answer to "without video + image". Nothing to host, nothing to crop,
no size limit, renders identically on every handset.

```
name : wd_menu_text
type : text_message
```

```
Thanks for contacting WECARE.DIGITAL!

Submit your request: https://wecare.digital/selfservice
Or message / voice note us on WhatsApp: https://wecare.digital/r/wa

We'll review it and follow up if needed.
```

Trade-off: no branding, and no tappable button — an RCS text template carries no
suggestions, so the links are plain text the user must long-press.

---

## 4. Option B — rich card, image only, no video  ← recommended

Uses the image that is **already the right shape**: `wecare-digital-rcs-h.png`,
2800 × 1200 = exactly 7:3, 89 KB. No new asset, no upload, no crop, and it is
already proven in production inside `rcsmenu`.

```
name        : wd_menu_img
type        : rich_card
orientation : VERTICAL
media height: MEDIUM
media       : https://wecare.digital/get/o/stream/media/m/wecare-digital-rcs-h.png
title       : Thanks for contacting WECARE.DIGITAL!
description : Submit your request here: https://wecare.digital/selfservice
              or send us a message / voice note on WhatsApp:
              https://wecare.digital/r/wa.

              We'll review it and follow up if needed.
              WECARE.DIGITAL
suggestion  : "Get Started" → https://wecare.digital/r/getstarted
```

This is `rcsmenu` with the video swapped for its own thumbnail image, and the two
retired hosts replaced by the migrated ones. Lowest risk of the three.

---

## 5. Option C — rich card using the WECARE.DIGITAL card artwork

I letterboxed both faces to 7:3 on the sampled `#01643F`, so **nothing is
cropped** — the QR and contact block survive in full — and the pad is invisible
because the colour matches the artwork exactly.

Generated, not yet uploaded:

| Local file | Pixels | Ratio | Size |
|---|---|---|---|
| `.scratch/rcsimg/wdf-rcs-7x3.png` | 1440 × 617 | 7:3 | 498 KB |
| `.scratch/rcsimg/wdb-rcs-7x3.png` | 1440 × 617 | 7:3 | 408 KB |

Both are comfortably under the 2 MB guidance.

**C1 — card front** (`wdf`): full business card, QR included.

```
name        : wd_card_front
type        : rich_card
orientation : VERTICAL
media height: TALL          ← TALL, so the card is as large as possible
media       : https://wecare.digital/get/o/stream/media/m/wd-card-front-7x3.png
title       : WECARE.DIGITAL
description : Building digital railroads for Everyday Bharat.

              Submit a request: https://wecare.digital/selfservice
              WhatsApp us: https://wecare.digital/r/wa
suggestion  : "Get Started" → https://wecare.digital/r/getstarted
```

> **QR caveat.** At 1440 px wide the QR is about 190 px. Rendered in a TALL
> vertical card it lands near 60–70 px on a typical handset, which is marginal to
> scan. The card already prints the URL and phone number as text, so treat the QR
> as decoration here, not as the call to action. If scanning matters, use the
> horizontal-thumbnail layout instead and accept a smaller overall card, or crop
> the QR out and let the button do the work.

**C2 — card back** (`wdb`): the "hello" / #EverydayBharat face. Decorative, so
nothing is lost at any crop or size, and it is the stronger *greeting* image.
My pick if this is the post-call "thanks for calling" card.

```
name        : wd_card_hello
type        : rich_card
orientation : VERTICAL
media height: MEDIUM
media       : https://wecare.digital/get/o/stream/media/m/wd-card-hello-7x3.png
title       : Thanks for contacting WECARE.DIGITAL!
description : Submit your request here: https://wecare.digital/selfservice
              or send us a message / voice note on WhatsApp:
              https://wecare.digital/r/wa.

              We'll review it and follow up if needed.
suggestion  : "Get Started" → https://wecare.digital/r/getstarted
```

Option C needs the asset uploaded first:

```bash
aws s3 cp .scratch/rcsimg/wdf-rcs-7x3.png \
  s3://wecare-digital-get/o/stream/media/m/wd-card-front-7x3.png \
  --content-type image/png --cache-control 'public, max-age=31536000'

aws s3 cp .scratch/rcsimg/wdb-rcs-7x3.png \
  s3://wecare-digital-get/o/stream/media/m/wd-card-hello-7x3.png \
  --content-type image/png --cache-control 'public, max-age=31536000'
```

Upload to **`wecare-digital-get/o/`**, not `app.wecare.digital`. New assets should
not add to the 6 approved templates already pinning the host we are trying to
retire.

---

## 6. Creating them

`create_template` takes `type` and, for `rich_card`, the card JSON as a **string**
in the `text` field. Creation on this provider returned `status: approved`
immediately for `rcsmenu_apex`, so there is no approval wait.

Text template:

```bash
aws lambda invoke --function-name wecare-rcs-send --cli-binary-format raw-in-base64-out \
  --payload '{"body":"{\"action\":\"create_template\",\"name\":\"wd_menu_text\",\"type\":\"text_message\",\"text\":\"Thanks for contacting WECARE.DIGITAL!\\n\\nSubmit your request: https://wecare.digital/selfservice\\nOr message / voice note us on WhatsApp: https://wecare.digital/r/wa\\n\\nWe will review it and follow up if needed.\"}"}' \
  /dev/stdout
```

Rich card — build the payload in Python rather than escaping JSON inside JSON by
hand:

```python
import boto3, json
card = {"richCard": {"standaloneCard": {
    "cardOrientation": "VERTICAL",
    "cardContent": {
        "title": "Thanks for contacting WECARE.DIGITAL!",
        "description": ("Submit your request here: https://wecare.digital/selfservice "
                        "or send us a message / voice note on WhatsApp: "
                        "https://wecare.digital/r/wa.\n\nWe'll review it and follow "
                        "up if needed."),
        "media": {"height": "MEDIUM", "contentInfo": {
            "fileUrl": "https://wecare.digital/get/o/stream/media/m/wd-card-hello-7x3.png",
            "forceRefresh": False}},
        "suggestions": [{"action": {
            "text": "Get Started", "postbackData": "wd_card_hello",
            "openUrlAction": {"url": "https://wecare.digital/r/getstarted",
                              "application": "BROWSER"}}}],
    }}}}

boto3.client("lambda", region_name="us-east-1").invoke(
    FunctionName="wecare-rcs-send",
    Payload=json.dumps({"requestContext": {"http": {"method": "POST"}},
                        "body": json.dumps({"action": "create_template",
                                            "name": "wd_card_hello",
                                            "type": "rich_card",
                                            "text": json.dumps(card)})}).encode())
```

Note `thumbnailUrl` is **omitted** on purpose in all three options — it is only
needed alongside a video. With an image as the media, a thumbnail is redundant,
and a wrong one is how `get_started` ended up pointing at a file that does not
exist.

Then test to the owner-nominated QA number before pointing anything at it:

```bash
aws lambda invoke --function-name wecare-rcs-send --cli-binary-format raw-in-base64-out \
  --payload '{"body":"{\"action\":\"send\",\"phoneNumber\":\"+918100640044\",\"template\":\"wd_card_hello\",\"language\":\"en\"}"}' \
  /dev/stdout
```

---

## 7. Switching the post-call card over

Creating a template changes nothing on its own. Two places name the template, and
both default to `rcsmenu`:

| Where | How to change |
|---|---|
| `lambda_utils/sinch_rcs.send_rcs_ivr_notification` | hardcoded `'rcsmenu'` — a code change plus deploy and alias move |
| `notifications/policy.RCS_INDIA_TEMPLATE` | env `NOTIF_RCS_TEMPLATE_NAME`, no deploy needed |

Leave `rcsmenu` in place until the replacement has been sent to a handset and
looked right — it is the template every post-call RCS currently uses.

---

## 8. Recommendation

1. **Option B** if you want this done with no new assets and no risk. It is
   `rcsmenu` minus the video, on the migrated URLs, using an image that is already
   exactly 7:3.
2. **Option C2** (`hello` face) if you want the card artwork — it is the better
   greeting and loses nothing to cropping.
3. **Option C1** (front face) only where the recipient will actually read details;
   the QR is too small to rely on at card size.
4. **Option A** as a fallback for handsets or routes where rich cards are not
   worth the weight.
