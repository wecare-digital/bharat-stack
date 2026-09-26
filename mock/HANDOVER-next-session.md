# Prompt for the next session

Repo `wecare-digital/bharat-stack`, default branch **`stack`**, currently green at `933d5d73`.

We are improving the **public** site one section at a time. Keep this rhythm and do not skip a
step: **deep-check → mock → owner approves → apply → test → PR → merge.** Never edit `src/`
before the owner has seen a mock and said yes. Standing rule: **do not redesign anything —
find flaws and correct them.**

## First: the owner could not read the last mock. Fix that before anything else.

An interactive HTML mock was produced at `mock/home-flow/mock.html` on the
`mock-device-audit` branch. The owner could not use it, for two separate reasons:

1. **They cannot open a rendered HTML file.** They work in a browser with no filesystem
   access. GitHub serves `.html` as `content-type: text/plain`, so a GitHub link shows source
   code, not a page. A third-party renderer was offered and correctly rejected as an unknown
   domain. GitHub Pages is not enabled on this repo.
2. **The mock was too dense.** Toggles, tables, percentages and a live readout. The owner
   asked plainly: "i am not understanding from your mock".

**What has actually worked in this project, every time:** render the mock in a headless
browser and post the **PNG inline in the chat reply**. That is how the header, footer, widget,
language search and device-audit mocks were all approved. Do that. Two images, before and
after, is enough. Do not send a link and do not send a wall of numbers.

## The decision that is blocking everything

The section is `.home-flow` — the home page block **below the hero** (`src/pages/index.tsx`,
markup at line 352, all CSS in the same file's single styled-jsx block).

The deep-check is **finished**. Three flaws, measured on the built export at eleven widths.
Ask the owner for **`1+2`** or **`1+2+3`** and then apply. In plain terms:

**Fix 1 — text lines are more than twice as long as they should be, on iPads and small
laptops.** The copy column sits in a 380px track on desktop, which is 47 characters per line.
At 1024px and below the grid collapses to one column and the column has no width limit at all,
so the same paragraph runs 120 characters. 45–75 is the convention. Two other blocks on this
very page already cap themselves (`.home-sub` at 560px, `.home-close-lead` at 782px).
*The change:* `.home-flow-copy{max-width:680px}` inside the existing
`@media(max-width:1024px)` block. **One line, this section only, desktop untouched.**

**Fix 2 — on iPads the black panel is tall and spans the whole width, because two
breakpoints were set to different numbers and never met.** The layout collapses to one column
at `max-width:1024px` (index.tsx:763). The panel's height only steps 650px → 560px at
`max-width:767px` (WorkflowTerminal.tsx:466). So every width from 768 to 1024 gets the narrow
layout *and* the tall panel — a 650px black slab at 100% width with nothing beside it, which
is exactly the condition the code comment says the two-column layout was built to remove. Six
of eleven sampled widths are in that band, including every iPad in portrait (768, 820, 834).
*The change:* `767px` → `1024px` on that height media query. **One number** — but
`WorkflowTerminal` is a shared component, so confirm nothing else renders it at 768–1024.

**Fix 3 — NEEDS THE OWNER'S ANSWER, DO NOT APPLY UNASKED.** The h2 letter-spacing is
`-1.2px` against `font-size:clamp(28px,3.2vw,40px)`, so it is −3.00% at 40px, −3.66% at
32.8px and −4.29% at 28px. PR #55 fixed the h1 the same way (`-2.2px` → `-0.04em`), so the
page's two biggest headings now track differently on desktop. The proposed value is
`-0.03em`, chosen so **desktop does not move at all** (−0.03 × 40px = exactly −1.2px); only
the narrow end changes. **The catch:** that declaration is byte-for-byte identical to
`.home-close-title`, `.cl-h2`, `.mo-h2`, `.brx-h2` and `.pdp-h2` — 12 headings across 10
public pages — and the comment above it says to run `node tools/browser/typecheck.js` first.
Offer three choices: this section only, all 12 headings, or leave it and log it.

**Flaw 4 was found and deliberately not fixed:** the two columns end 136px apart on desktop
(panel is a hard 650px, copy is 514px). `align-items:start` is correct, so this is the honest
cost of a fixed-height panel beside fluid prose. Mention it, do not change it.

## Already checked — do not re-investigate these

- 390px is **already correct**. The panel ships at 560px below 767px, so the phone is the one
  narrow width with no panel problem. Only the tracking affects it.
- The squeezed panel does **not** clip. `.wt-cmd` is `nowrap` + `overflow-x:auto`, the obvious
  candidate; 0 of 1 command lines overflow down to 553px of panel width.
- No horizontal overflow at any of the eleven widths.
- The list's 22px/20px rungs are the documented card-heading contract.
- The panel is never partly empty; content reaches full height at every timestamp.
- The 96px section rhythm comes from the parent's `gap` — there is no double margin.

All numbers reproduce from `mock/home-flow/tools/` on the `mock-device-audit` branch:
`flowcheck.cjs`, `flowband.cjs`, `flowmeasure.cjs`, `flowcmd.cjs`, `drivemock.cjs`.
**Read `mock/home-flow/README.md` there first. Do not re-measure from scratch.**

## After this section

Next one down is `.home-close` (index.tsx:467). Same rhythm.

## Where the project stands

Ten PRs merged (#48–#55, #57; #56 was closed empty after a wrong-ref push). Verified on
`stack`: vitest 249/249, `tsc --noEmit` clean, uicheck 96/96, animcheck 18/18, seocheck 11/11,
typecheck 3/3, chromecheck green, pytest 3413 passed. **No open PRs.**

Shipped so far: header and mega-menu, footer, public-route guard, combined WhatsApp +
translate widget, one scroll container, widget slimmed and parked above the footer on phones,
language search box (71 languages, English labels), chrome on every public page, no 404 page
(mismatched URLs redirect to `/`), and the `/translate` open proxy closed with an Origin gate.

`git` will report ten branches as "ahead of stack" — that is a squash-merge artefact, not
pending work. Squashing writes a new commit, so old branch tips never become ancestors. The
only branch with genuinely unmerged content is `mock-device-audit`, which is deliberate: it
contains mocks and measurement scripts and touches **zero** files in `src/` or `amplify/`.

## Environment traps — each of these has already cost an hour once

- **node is not on PATH.** Prefix every bash call:
  `export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"`
- `/tmp` does not persist between bash calls. Write to `/projects/sandbox/`.
- Use `npm install`, not `npm ci`. Build with `NODE_ENV=production npm run build` → `out/`.
- Repo root `package.json` is `"type":"module"` — standalone scripts must be `.cjs`.
- For Chrome, use `tools/browser/lib/browser.js`'s `launch()`. Do not hardcode a path; the
  binary is `chrome-linux64`, not `chrome-linux`.
- To serve the export for measurement, use `tools/browser/lib/serve.js`'s `target()`.
- Playwright contexts need `serviceWorkers:'block'` or `public/sw.js` intercepts requests.
- **Never put a backtick in a styled-jsx CSS comment.** It ends the template literal, and the
  error points at the comment rather than the cause. This has happened three times.
- **No JSX comment inside `cond && ( ... )`** — that is two expressions where one is allowed.
- Negative test assertions will fire on your own explanatory code comments. Strip comments
  from the source before asserting that something is absent.
- Do not animate anything a measurement harness reads. A `transition:width` made a mock's own
  readout report mid-animation values.
- Squash-merge only; `merge_method=merge` returns HTTP 405.
- `gh pr create` and every `gh pr` / `gh issue` subcommand fail here (GraphQL). Use
  `gh api repos/wecare-digital/bharat-stack/pulls -f title=... -f head=... -f base=stack`.
- **Check `git branch --show-current` before every push.** Pushing `origin <branch>` while
  standing on a different branch silently pushes that name's local ref — it produced an empty
  PR once.
- Known-failing and **not ours**: 5 tests in `tests/test_wix_blog_migrate.py`
  (`TypeError: unsupported operand type(s) for |`). Local Python is 3.9, CI is 3.12. They fail
  identically on pristine `stack`. Do not try to fix them.

## Three things that cannot be done from this repo

- Wrong subdomain → home page: Route 53 / Amplify domain configuration.
- Revoking the Polly IAM grant: Amplify backend change plus a deploy.
- Deleting the retired `/site-language/tts` and `/voices` routes from API Gateway by hand.

## Two reversible decisions worth remembering

- The hero's lime badge was **removed** in #55 — one line to restore.
- Language choice is **not persisted**. Restoring localStorage also restores a
  per-page-load translation bill (measured at roughly $32,400/hour at the rate limit).
