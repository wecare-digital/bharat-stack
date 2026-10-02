# Design tokens — extracted from the home page, not from v28

Source of truth: `src/pages/index.tsx` (the `styled-jsx` block, lines 588–1229).
Secondary: `.kiro/steering/grahak-os-design.md`. Where they disagree the code wins,
and it does disagree in one place (see "Contract gaps" below).

Everything below is a literal value read out of the files named, with a
`file:line` citation. Nothing is inferred and nothing is carried over from the
owner's v28 HTML.

## Surfaces

| Token | Value | Cite |
| --- | --- | --- |
| Page ground | `#fff` | `index.tsx:1013` `.home-shell{background:#fff}` |
| Alternate section ground | `#fafafa` | `grahak-os-design.md:344` — `#touchpoint,#capabilities` sit on `#fafafa` full-bleed with `.pp-inner` carrying the 1300px measure |
| Own-surface lime tint panel | `rgba(209,244,112,.22)` + `2px solid #d1f470` + `border-radius:14px` | `index.tsx:750` `.home-close-panel` |
| Card / field ground | `#fff` | `BlogSubscribe.tsx` `.blog-subscribe-cell>input{background:#fff}` |

## Brand pair — verified by count

`#d1f470` appears **8** times in `index.tsx`; `#1a3a2a` appears **13** times.
The pairing is lime fill + `#1a3a2a` type, and on a control the border is
`#1a3a2a` (NOT lime): `index.tsx:909` `.home-close-cta{border:2px solid #1a3a2a;background:#d1f470;color:#1a3a2a}`.
The comment above that rule records why — lime-on-lime measured 1.18:1 and
carried no boundary at all.

## Text colours

| Role | Value | Cite |
| --- | --- | --- |
| Heading ink | `rgba(0,0,0,.95)` | `index.tsx` `.home-head`, `.home-flow-title`, `.home-close-title` |
| **Body ink (the one body level)** | `rgba(0,0,0,.898)` | `.home-sub`, `.home-flow-lead`, `.home-flow-list span`, `.home-close-lead`, `.home-close-points li` — five elements |
| Strongest ink | `#000` | `.home-flow-list strong` |
| Base ink | `#1a1a1a` | `.home-shell{color:#1a1a1a}` |
| Muted / eyebrow-grey | `rgba(0,0,0,.54)` | `BlogContribution.tsx` `.bc-title`, `.bc-legend`, `.bc-custom-help` |
| Status line | `rgba(0,0,0,.7)` | `BlogContribution.tsx` `.bc-status`; `BlogSubscribe.tsx` `.blog-subscribe-status` |
| Secondary lead | `rgba(0,0,0,.66)` | `BlogSubscribe.tsx` `.blog-subscribe-head>p` |

## Hairline

`1px solid #e5e7eb` static, `2px solid #e5e7eb` where the surface is hoverable.
`grahak-os-design.md:166` states the rule outright: 2px means hoverable, 1px
means static, and the colour is always `#e5e7eb`. Confirmed in shipped
components — `BlogContribution.tsx` `.bc{border-top:1px solid #e5e7eb}` and
`.bc-choice-face{border:2px solid #e5e7eb}`.

Note `index.tsx:658` mentions `#e5e7eb` only in a comment, recording that the
flow list's separator was DELIBERATELY moved off the hairline to a 3px lime
accent bar. That is a typographic accent, not a surface border.

## Radii — only these three exist

| Value | Cite | Use |
| --- | --- | --- |
| `14px` | `index.tsx:750` | panels |
| `50px` / `999px` | `index.tsx:910`, `BlogContribution.tsx` `.bc-choice-face` | pills, CTAs, chips |
| `9999px` / `50%` | `index.tsx:1107,1127,1139` | the hero pill and its dot |
| `10px`, `12px` | `BlogSubscribe.tsx` inputs, `BlogContribution.tsx` `.bc-custom-row` | form fields only |

There is **no** blanket `13px`. v28's `13px` everything is a v28 artifact.

## Shadows — exactly one value on the home page

`0 4px 12px rgba(26,58,42,.12)` — `index.tsx:940` `.home-close-cta:hover`, and
reused verbatim at `BlogContribution.tsx` `.bc-radio:hover + .bc-choice-face`.
It is a **hover** shadow. Nothing on this site sits on a resting shadow, so
cards are separated by the `#e5e7eb` hairline instead.

## Type ladder

| Rung | Declaration | Cite |
| --- | --- | --- |
| Hero h1 | `clamp(36px,4.3vw,60px)/600`, lh `1.04`, ls `-0.04em`, `rgba(0,0,0,.95)`, `max-width:900px` | `.home-head` |
| **Section h2** | `clamp(28px,3.2vw,40px)/700`, lh `1.08`, ls `-1.2px`, `rgba(0,0,0,.95)` | `.home-flow-title`, `.home-close-title` — the comment records this as the de-facto site rung, 12 headings across 10 public pages |
| Panel h2 (quieter) | `clamp(24px,3vw,32px)`, lh `1.08`, ls `-.8px` | `BlogSubscribe.tsx` `h2` |
| Card heading | `22px/700`, lh `1.27`, ls `-.25px`, `#000` | `.home-flow-list strong` |
| CTA label | `17px/600` (`700` in PillButton) | `.home-close-cta`, `PillButton.tsx` |
| **Body — the only body level** | `20px/400`, lh `1.4`, ls `-.125px`, `rgba(0,0,0,.898)`, measure `62ch` | `.home-sub` (560px), `.home-close-lead` (62ch), `.home-flow-lead` |
| Eyebrow | `12px/700`, ls `.08em`, `text-transform:uppercase`, `#1a3a2a` | `.home-close-eyebrow` |
| Field label | `12px/700`, ls `.01em`, `#1a3a2a` | `BlogSubscribe.tsx` `.blog-subscribe-cell>span` |
| Small print | `13px`/lh `1.4` and `15px`/lh `1.5` | `BlogContribution.tsx` `.bc-custom-help`, `.bc-status` |

## Rhythm and measure

- Container: `max-width:1300px; margin:0 auto; padding:80px 24px 96px` — `.home-layout`
- Section gap: flex column `gap:96px`, dropping to `gap:64px` with `padding:48px 16px 64px` at `max-width:767px` (`index.tsx:1199`)
- Headline block `max-width:900px`; sub-line `max-width:560px`; body measure `62ch`
- Header offset: `padding-top:108px` (96px under 768px, per the `.home-shell` comment)

## Easings — three, all from `index.tsx`

- `cubic-bezier(.16,1,.3,1)` — the pill wipe and width glide
- `cubic-bezier(.22,.61,.36,1)` — the closing rule drawing itself
- `cubic-bezier(.34,1.56,.64,1)` — the dot pop
- plain `.2s` / `.5s ease` for hover and reveal transitions

## Font

`'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif`,
declared **locally** at `.home-shell` and never loaded from a remote host. The
comment there is explicit that the stack is declared rather than inherited. No
`fonts.googleapis.com`, and **no Wix Madefor** — that is a v28 artifact.

## Focus ring

`outline:3px solid #1a3a2a; outline-offset:3px` (`index.tsx` `.home-close-cta:focus-visible`),
`outline-offset:2px` on form controls (`BlogSubscribe.tsx`, `BlogContribution.tsx`).
Always opaque — the comment records that a `rgba(26,58,42,.22)` ring measured
1.51:1 and was a 1.4.11 failure.

## Reused verbatim

`BlogContribution.tsx` selected state, copied byte for byte into the mock:

```css
.bc-radio:checked + .bc-choice-face{border-color:#1a3a2a;background:#d1f470}
```

## Forbidden v28 tokens — all absent from the home page

Grepped `index.tsx`: `#f8f8f8`, `#f4f4f1`, `#5c5c57`, `#e9e9e7`, `#ecece8`,
`#e8e0d8`, `#d0f070`, `#183828`, `#e0f0c8`, Wix Madefor — **zero matches each**.
`#d0f070`/`#183828` are near-misses for the real brand pair and `#e0f0c8` is a
near-miss for `#e0f7c8`, which IS real (`index.tsx` `.home-mark{background:#e0f7c8}`)
— that one-character difference is presumably how the v28 palette drifted.

## Contract gaps worth recording

- `grahak-os-design.md` specifies section h2 at `clamp(32px,4.2vw,54px)`. The
  code uses `clamp(28px,3.2vw,40px)`. The comment at `.home-flow-title` says
  reconciling the two is an owner decision. **The code wins here**, per the brief.
- The contract lists `#dc2626` as an approved fourth accent hue. It is NOT used
  in this mock: the owner's no-red constraint overrides it.

## AQI severity ramp — invented for this mock, recorded here

No red anywhere, so severity is encoded by **darkness and warmth**:

| Category | Swatch |
| --- | --- |
| Good | `#1a3a2a` (brand green) — small dots / short bars only |
| Satisfactory | `#3da35a` — **already in `index.tsx`** (`.home-flow-list li` accent bar, `.home-close-points li::before`) |
| Moderate | `#d1f470` (brand lime) |
| Poor | `#e8c547` |
| Very Poor / Severe | `#c98a2e` |

Worst-case tint `#fdf4e3` (pale amber). Because a yellow/amber ramp is a weak
signal for colour-blind readers and carries none of red's urgency, **colour is
never the only carrier**: every AQI figure in the file prints its category word,
and both ends of the legend are labelled in words.

The satisfactory rung was lightened from `#4b8058` to `#3da35a` on the owner's
"too much dark green" note. `#3da35a` is traceable to `index.tsx` rather than
invented, and it keeps the 24-bar history chart reading as mid-tones instead of a
block of dark green across the overnight hours.

## Owner correction: dark green is an ACCENT, lime is PUNCTUATION

Recorded here because it constrains every rule in the mock:

- **No large `#1a3a2a` fill anywhere on the page.** Dark green appears as type,
  as a 1–2px control border, as a 14px dot and as map label fill. The previous
  mock's full-width dark-green mock banner and its solid dark-green primary
  signal card are both gone.
- **Lime is not a panel colour.** Its only fills are the brand mark, the CTA
  pills, the active tab, the pressed layer button, and 3px accent rules. The one
  lime-tint *panel* is §9 Subscribe, and only because the shipped
  `BlogSubscribe.tsx` genuinely is one.
- `#dc2626` is now explicitly forbidden too — it is on the contract's approved
  accent list (`grahak-os-design.md:114`) but it is a true red, and the previous
  mock was rejected partly for carrying it.
