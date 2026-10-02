# Mock landed, but two button languages are live at once — one owner decision outstanding

Date: 2026-10-02 ~13:33 UTC
Branch: `feat/vayulok-update`

| | SHA |
| --- | --- |
| Local HEAD | `72ec4411a2cdb440299e0cd0c465b9f752be0ec9` |
| Remote (`gh api .../branches/feat/vayulok-update`) | `72ec4411a2cdb440299e0cd0c465b9f752be0ec9` |

They match — the work is on GitHub.

## What happened

My brief said the branch sat at `77fd967b`, that `docs/mocks/vayulok-live-mock.html`
did not exist, and that I was the only step. None of those held. A parallel
writer was working the same file and committed twice while I was verifying:

```
72ec4411 docs: adopt the home page hero language in the VayuLok mock
d4f1fe5f docs: add stacked VayuLok mock with runtime-key live map
77fd967b chore: track the VayuLok app-shell mock plan and its verification harness
```

`d4f1fe5f` is my own file captured at an intermediate save — I never ran
`git commit`. `72ec4411` then swept in my later corrections and added the other
writer's hero work on top. So my build and my three bug fixes **are** on the
remote; they just went up under someone else's commits.

## The three bugs I found and fixed (all now on the remote)

| Defect | Cause | Visible effect |
| --- | --- | --- |
| Container gutter collapsed | `.vl-section{padding:48px 0}` sits on the same element as `.vl-wrap{padding:0 24px}`, and the shorthand reset the 24px gutter to zero | every heading and rail flush to the viewport edge at 1280 |
| `Clear key` shown in the no-key state | `[hidden]` and `.vl-cta-quiet{display:inline-flex}` are the same specificity, so source order won | a Clear key control offered when there is no key |
| Mobile overlays invisible, key card clipped | `position:static` put the legend and preview into the flow inside a 340px `overflow:hidden` stage, behind the map layer | legend and place-preview gone at 390px; "Load the live map" heading cut off |

Fixed as `padding-block:48px`, `[hidden]{display:none !important}`, and
keeping the overlays absolute but smaller at `max-width:767px`. Confirmed present
in `72ec4411`.

## THE OUTSTANDING DECISION — two control languages on one page

`72ec4411` leaves **both** button families live in the markup:

| Family | Geometry | Cited to | Used by |
| --- | --- | --- | --- |
| `.vl-btn` / `.vl-btn-primary` / `.vl-btn-secondary` | `border-radius:13px`, `16px/500`, 52px, `0 24px` | `src/styles/button.css:31` and `.btn-lg` 52-56 | a NEW hero pair, "See the forecast" + "How we measure" (lines 823-824) |
| `.vl-cta` / `.vl-cta-quiet` | `border-radius:999px`, `17px/700`, 52px, `0 28px` | `index.tsx` `.home-close-cta` | `Load map`, `Send code` ×2, `Subscribe`, `Contribute` |

So one page shows 13px-radius 16px/500 buttons in the hero and 999px-radius
17px/700 pills from the map band downward. Two issues follow, and neither is mine
to settle:

1. **Which radius.** My brief lists a blanket `13px` radius as a FORBIDDEN v28
   token and names `index.tsx` as the single source of truth. The other writer's
   citation is *also* genuine — `src/styles/button.css:31` really does say
   `border-radius: 13px`, and that really is the repo's button rung. So 13px is
   not a v28 artifact after all; it is simply not the radius `index.tsx` uses on
   its one CTA. Picking one changes the shape of five visible controls.
2. **The new hero CTA pair is outside the spec.** The brief fixes 11 sections and
   says not to invent copy. "See the forecast" and "How we measure" are invented
   product copy in a twelfth element, and neither button does anything.

Three ways forward, for the owner to choose:

- **A — index.tsx wins.** Delete `.vl-btn*` and the hero pair; every control is
  the lime pill. Matches my brief exactly and removes the 13px radius.
- **B — button.css wins.** Migrate `Load map`, `Send code`, `Subscribe` and
  `Contribute` onto `.vl-btn`, delete `.vl-cta*`. One language, but it keeps the
  13px radius the brief forbids, and `Contribute` then stops matching the shipped
  `BlogContribution.tsx` / `PillButton` shape that §10 is meant to mirror.
- **C — keep the hero pair, unify the radius.** Keep "See the forecast" only if
  the owner wants that copy, and put it on whichever radius wins.

I have not edited the file since `72ec4411`, to avoid a third pass fighting a
second writer on a branch that is already pushed.

## Everything else verified clean on the pushed state

Harness: `verify.cjs`, Chromium **153.0.8010.12**, launched with
`NODE_PATH=/root/.npm/_npx/e41f203b7505f1fb/node_modules` (`.cjs` because the
repo `package.json` is `"type":"module"`).

- **Outbound requests in the no-key state: 0** at both 1280 and 390. The only
  logged request is the `file://` document itself.
- Console errors **0**, page errors **0**, at both widths.
- DOM order: sections 1-11 in sequence, `footer` is section 11, only a `<script>`
  after it. Map band `x=0 w=1280` — full-bleed, directly after section 2. Stage
  520px desktop / 340px mobile. `body` overflow `visible`, so it is a normally
  scrolling document.
- Section 10 label: text `Contribute`, computed `text-transform: none`.
- `AIzaSy` **0**. No Google key in any file, commit, screenshot or log.
- Red: `dc2626` `ff0000` `c00000` `c94d44` `ff6500` `a8333d` `fde9e7` `8a342f`
  `e11d48` `ef4444` `b91c1c` `991b1b` — **0 each**.
- v28 tokens `f8f8f8` `f4f4f1` `5c5c57` `e9e9e7` `ecece8` `e8e0d8` `d0f070`
  `183828` `e0f0c8` and Wix Madefor — **0 each**.
- `d1f470`, `1a3a2a`, `e5e7eb` all present.
- `https://` **0**, `fonts.g` **0** — the Maps URL is assembled from parts at
  runtime, so there is no static remote resource reference.
- No CSS targets `.gm-style-cc`, `a[href*="google"]` or `img[alt="Google"]`, and
  no overlay is anchored to `bottom:0`, so Google's logo and legal notices stay
  visible and uncovered.

### R-dominance audit

Every `#rrggbb` in the file was extracted and tested for `R > 140 && R > G+40 &&
R > B+40`. **One flagged: `#c98a2e`** (r=201 g=138 b=46). Kept deliberately — its
hue is **36 degrees**, i.e. amber/ochre, the same family as the approved
`#f0a818` (hue 39). Red sits at 0-15 degrees. It is the AQI ramp's worst-case
rung and reads as burnt amber. Every other value passes.

## Accessibility consequence of removing red

Red is the strongest danger signal available, and amber-vs-yellow is a weak
distinction for colour-blind readers, so severity is **never** carried by colour
alone:

- every AQI figure prints its category word — the "Now" block, all 24 hours in the
  rail, the map preview, the pollutant rows, the best/peak insight line
- both ends of the legend gradient are labelled `Good` and `Severe` in words, with
  the full six-band list beneath
- the 24-bar history chart is `aria-hidden` and backed by a readable sentence
  naming the low, the high and the current value with their categories
- the AQI dot is 14px with a `#1a3a2a` ring, so it survives greyscale
- the worst-case card uses a left rule plus a pale amber tint, never a red wash

## Footer — UNRESOLVED, awaiting owner input

No footer copy was supplied, so the footer is structure only: the
`WECARE.DIGITAL` wordmark, a labelled "FOOTER COPY PENDING" line, and bracketed
placeholders for product links, legal/privacy, contact and the copyright line.
Nothing invented, and an HTML comment marks it as awaiting owner input. The
Attribution column is the one real line, because Google's credit is a terms
requirement rather than owner copy.
