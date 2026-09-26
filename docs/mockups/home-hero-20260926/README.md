# Home hero — CTA mockups, 2026-09-26

Six variants for the one open item on the home page: **nothing above the fold is
actionable** (`docs/home-design-audit-20260926.md` M5). **No source file was changed to
produce these.** `tools/browser/homemock.js` loads the real static export, injects one
block plus a stylesheet at runtime, measures, and screenshots. What you see is the
shipping page with one element added — real fonts, real `clamp()` headline, real 108px
header offset, real fold.

Re-render at any time: `node tools/browser/homemock.js`

## The variants

| | Variant | Desktop | Phone |
|---|---|---|---|
| **A** | control, exactly as shipped | [1280×900](A-control__desktop-1280x900.png) | [390×844](A-control__phone-390x844.png) |
| **B** | one primary CTA → `/contact/` | [1280×900](B-single-contact__desktop-1280x900.png) | [390×844](B-single-contact__phone-390x844.png) |
| **C** | primary + derived price `₹599` | [1280×900](C-single-price__desktop-1280x900.png) | [390×844](C-single-price__phone-390x844.png) |
| **D** | primary → `/contact/` + secondary → `/access` | [1280×900](D-two-actions__desktop-1280x900.png) | [390×844](D-two-actions__phone-390x844.png) |
| **E** | both actions + price | [1280×900](E-everything__desktop-1280x900.png) | [390×844](E-everything__phone-390x844.png) |
| **F** | the duplication shortcut, for rejection | [1280×900](F-duplication-trap__desktop-1280x900.png) | [390×844](F-duplication-trap__phone-390x844.png) |

Plus two "before" shots of defects that need no decision, only a go-ahead:
[H2 — the h1 with JavaScript off](defect-H2__js-disabled-1280x900.png) ·
[H3 — the word clipped after a resize under reduced motion](defect-H3__reduced-motion-resize-clip-1280x900.png)

## What the copy is, and is not

Every label is **borrowed from the site, not invented**. "Submit a request" is already the
header nav item and one of the five rotating phrases on `/contact/`; "Sign in" describes
`/access`, which is the login entry that redirects to `/dashboard`. The handoff records
that this page's wording is yours, so these are placeholders that propose **placement,
geometry and destination** — the parts that can be measured — while leaving the sentence to
you.

**F is not a candidate.** It reuses the closing band's exact string *and* its exact
destination, putting one sentence on the page twice. It is rendered so the defect is
visible rather than described.

## The price, if it goes in

`₹599` is **read from `src/content/wix-catalog.json` at render time**, never typed — 7
products, floor Viveka ₹599, next Referral Partner ₹999. When the ₹49 tier lands the
number changes itself. Implemented the same way, it cannot go stale.

**Where it sits is the real argument.** `index.tsx` holds that the page has one body level
(20px/400/1.4/-.125px) and that the hero sub-line is deliberately a single sentence,
because "a second would put two body blocks on a page that has no section rhythm yet". So
a price set as body copy is either a second body block — against that note — or a new 17px
rung, which is the drift that file has already corrected twice. C and E therefore put it on
the **control row at the CTA's own 17px**, beside the button: a control label, not body
copy. That is the choice to accept or reject.

## Measured, at both viewports

`measurements.json` holds the raw output. The two numbers that matter:

**The h1 does not move.** 131px at 1280 and 90px at 390 — *identical in all six variants,
including the control.* The CTA sits below the headline, so it cannot affect the height
`animcheck.js` pins across 21 viewports and a live rotation. The 2400ms page-jump guard is
untouched, and this was measured rather than assumed.

**The hero grows, and everything still clears the fold.**

| Variant | desktop hero | flow section top | phone hero | phone flow top |
|---|---:|---:|---:|---:|
| A control | 211px | 495 | 198px | 406 |
| B | 295px | 579 | 278px | 486 |
| C | 295px | 579 | **316px** | 524 |
| D | 295px | 579 | **342px** | 550 |
| E | 295px | 579 | **380px** | 588 |
| F | 295px | 579 | 278px | 486 |

Desktop is identical for B–F because the row never wraps at 1280. **The phone column is
where the variants separate**: at 390px the row is full-width and stacks, so each added
element costs another ~38px. E stacks to three rows and the left-aligned price under a
centred full-width button reads as a loose end — visible in the phone render.

CTA box is **52px** tall in every variant (the closing CTA's own value, clearing the 44px
target with margin), at y=431 desktop / y=370 phone, comfortably above both folds.

## Focus order lands right on its own

Measured Tab walk. The hero CTA takes position 3 naturally, because it is appended after
`.home-sub` inside `.home-hero` — no `tabindex` needed:

```
A (control)  logo > nav-trigger > home-close-cta(INVISIBLE) > footer
B / C / F    logo > nav-trigger > hero CTA > home-close-cta(INVISIBLE)
D / E        logo > nav-trigger > hero CTA > secondary CTA
```

Note the control's third stop is already the *invisible* bottom CTA — that is M4, a
separate defect the hero CTA does not fix and does not worsen.

## What I need from you

1. **Which variant** — B, C, D or E.
2. **The sentence on the button**, if "Submit a request" is not it.
3. **Price above the fold** — yes (C/E) or no (B/D).

Say the word on the defect shots too: H2 and H3 need no decision, and fixing them takes
`homeprobe.js` from 5/11 to 9/11.
