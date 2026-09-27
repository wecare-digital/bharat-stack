# Post-call templates — final spec, no redirects and no old links

Drafted 2026-09-27 for approval. Every URL here was followed to its terminal
address and the hop count recorded; nothing is quoted from memory.

---

## 0. BLOCKER — fix this before any template ships

**`https://wecare.digital/selfservice` returns 404.**

```
https://wecare.digital/selfservice   301 -> /selfservice/
https://wecare.digital/selfservice/  404
```

That is the primary call to action in the **DLT-approved SMS body**, in the
approved `rcsmenu` / `wecaremenu` / `wdorder` RCS cards, and behind the
`/r/getstarted` short link every RCS "Get Started" button uses.

Cause, dated rather than guessed: PR **#47** (`6bc44a35`, 2026-09-24 18:08)
removed the in-repo `/selfservice` and `/product-page` redirect stubs. No Amplify
rule replaced them — the live app has **zero** custom rules mentioning
`selfservice`, out of 104. So the route has been dead for three days.

It is **not** a side effect of the `/workspace/` nesting (`c143301d`,
2026-09-27 05:44), which landed three days later and is what added the working
`/forms/<*>` redirect.

The page itself is alive at `https://wecare.digital/workspace/forms/selfservice/`
(200). The fix is one Amplify rule. **The SMS body cannot be changed to route
around it** — it is frozen by DLT approval — so the rule is the only option that
repairs SMS.

---

## 1. Terminal URLs — measured

| Candidate | First | Hops | Terminal | Verdict |
|---|---|---:|---|---|
| `wecare.digital/selfservice` | 301 | 1 | **404** | **broken** |
| `wecare.digital/r/getstarted` | 302 | → above | **404** | broken + a redirect |
| `wecare.digital/workspace/forms/selfservice/` | **200** | **0** | itself | terminal ✓ |
| `wecare.digital/r/wa` | 302 | 2 | api.whatsapp.com | 2 redirects |
| `wa.me/message/APDM5HUWH26SG1` | 302 | 1 | api.whatsapp.com | 1 redirect |
| `api.whatsapp.com/message/APDM5HUWH26SG1` | **200** | **0** | itself | terminal ✓ |
| `api.whatsapp.com/send?phone=919330994400` | **200** | **0** | itself | terminal ✓ |

So the only zero-redirect pair is:

```
Get Started   https://wecare.digital/workspace/forms/selfservice/
WhatsApp      https://api.whatsapp.com/message/APDM5HUWH26SG1
Call          dialer action — no URL at all
```

**One thing to decide.** The terminal self-service URL sits inside
`/workspace/`, which is the *authenticated* namespace. It serves 200 to an
anonymous visitor today, but sending customers into an internal-looking path is a
naming decision, not a technical one. Two options:

* **A —** point the buttons at `/workspace/forms/selfservice/`. Zero redirects
  today, but a customer-facing URL that reads as internal.
* **B —** restore a real page at `/selfservice` (not a redirect stub), then point
  the buttons there. Zero redirects **and** a clean public URL. Needs one page
  added, and it repairs the DLT-frozen SMS at the same time.

**B is the recommendation.** It is the only option that also fixes SMS, because
the SMS body already says `wecare.digital/selfservice` and cannot be edited.

---

## 2. The image

`wd-brand-16x9.png` — 1440 × 810, exactly 16:9, 782 KB, live at
`https://wecare.digital/get/o/stream/media/m/wd-brand-16x9.png` (200, `image/png`).

Built from the card artwork's branding block (x 64–1189, y 136–690 of the 1254²
original), recomposed with even margins on the sampled brand green `#01643F`.
Contains the logo, the WECARE.DIGITAL wordmark and the tagline pill. The phone,
email, website and QR were **dropped** — the buttons carry those actions now.

No video anywhere in this spec.

---

## 3. SMS

**Cannot be changed.** Body must match DLT template `ivr-default`
(`1007277993798259629`) character for character; the registry table
`stack-wecare-digital-DLTTemplates` is empty, so no other content is approved.

| | |
|---|---|
| Sender | `WDBEEP` |
| Route | AWS End User Messaging, `ap-south-1` |
| Image | none — SMS carries no media |
| Buttons | none — SMS has no buttons |

Text, exactly as approved and as sent today:

```
Thanks for contacting WECARE.DIGITAL!

Submit your request here: https://wecare.digital/selfservice or send us a
message / voice note on WhatsApp: https://wecare.digital/r/wa.

We'll review it and follow up if needed.
```

This is the one place the old short link and the broken URL **must** remain, until
new DLT content is registered. Delivery measured healthy: 60 of 68 parts in 7 days.

**Needs you:** register new DLT content on the portal if the copy is to change.

---

## 4. WhatsApp — WABA1, +91 93309 94400

| | |
|---|---|
| Name | `wd_call_menu` |
| Language / category | `en` / `UTILITY` |
| Header | **IMAGE** — `wd-brand-16x9.png` |
| Footer | `WECARE.DIGITAL` |

Body — no links, no variables:

```
Thanks for contacting WECARE.DIGITAL!

Building digital railroads for Everyday Bharat.

Tap a button below and we'll follow up.
```

Buttons and actions:

| # | Label | Type | Action | Redirects |
|---|---|---|---|---|
| 1 | `Get Started` | `URL` | opens the self-service page | **0** once §1 is settled |
| 2 | `Call us` | `PHONE_NUMBER` | dials `+919330994400` | n/a |

**No "WhatsApp us" button** — the reader is already in WhatsApp, so it would waste
a slot on a no-op.

---

## 5. RCS — Sinch India

| | |
|---|---|
| Name | `wd_card_clean` |
| Type / orientation | `rich_card` / `VERTICAL` |
| Media | `wd-brand-16x9.png`, height `MEDIUM` |
| Title | `WECARE.DIGITAL` |

Body — no links:

```
Thanks for contacting us.
Building digital railroads for Everyday Bharat.

Choose an option below and we'll follow up.
```

Buttons and actions — 3 of the 4 a rich card allows:

| # | Label | Type | Action | Redirects |
|---|---|---|---|---|
| 1 | `Get Started` | `openUrlAction` | self-service page | **0** once §1 is settled |
| 2 | `WhatsApp us` | `openUrlAction` | `api.whatsapp.com/message/APDM5HUWH26SG1` | **0** |
| 3 | `Call us` | `dialAction` | `+919330994400` | n/a |

The dialer type **was accepted** by this provider — tested, not assumed. The 4th
slot is left free.

---

## 6. Summary of link policy

| Channel | Old / redirect links remaining |
|---|---|
| SMS | **2** — `wecare.digital/selfservice`, `wecare.digital/r/wa`. Frozen by DLT. |
| WhatsApp | **0** |
| RCS | **0** |

Nothing in the two new templates uses `r.wecare.digital`, `wecare.digital/r/*`, or
`wa.me`. The live approved `wd_menu` and `rcsmenu` still carry the old
`r.wecare.digital/wa` host; approved bodies are frozen, so they were left rather
than pushed back into review — and that is why `r.wecare.digital` cannot be retired.

---

## 7. State, stated plainly

| Channel | Template | Status |
|---|---|---|
| SMS | `ivr-default` | unchanged; new copy needs DLT registration by you |
| WhatsApp | `wd_call_menu`, id `2168548787028295` | **created, PENDING** Meta review |
| RCS | `wd_card_clean` | **created, approved**, test-sent `01M3GEM24ZZ79YYN8T5GH5PQYB` |

Both created templates currently point `Get Started` at
`https://wecare.digital/selfservice`, which is the 404 in §0. **Neither is wired to
anything** — a real call still sends `wd_menu` and `rcsmenu`. So nothing customer
facing is broken by them, and both can be deleted or recreated.

## 8. What I need decided

1. **§1 option A or B** for the self-service URL. B is recommended and is the only
   one that also repairs SMS.
2. Whether to **fix `/selfservice`** now — it is a live 404 on the primary CTA,
   independent of this template work.
3. Whether to **recreate** the two templates once the URL is settled, so they ship
   with a terminal, working link rather than the 404.
