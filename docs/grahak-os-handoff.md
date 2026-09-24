# Grahak OS frontend handoff

Rewritten 2026-09-24. The previous version was stale in a way worth naming, because it
keeps happening: it opened by describing **PR #5** as the most recent merge when PRs up to
**#35** had already landed, it quoted a test count of 33 when the suite runs 73, a lint
count of 237 when it is 230, and it cited a browser harness (`animcheck.js`) that existed
in **no** file on disk. The revision before that one opened by asking for PR #3 to be
merged, long after it was.

**So: treat every number, hash and PR reference below as a claim to re-verify, not as
fact.** Each section now says how to re-measure it. The one structural fix made for this
is that the harness now lives in `tools/browser/` inside the repo, so "re-run the harness"
is an instruction that survives a sandbox reset.

## Position

- Repo `wecare-digital/bharat-stack`. Default branch is **`stack`**, not `main`.
- All work is on the single long-lived branch **`feat/grahak-os-trust-a-i`**.
- **THE BRANCH AUTO-DELETES ON MERGE.** It is squash-merged into `stack` and the remote
  branch is then removed, so at the start of a session it usually **does not exist** —
  `git ls-remote --heads origin` showed only `stack`. Recreate it from the default
  branch:
  ```bash
  git fetch origin --prune
  git checkout stack && git reset --hard origin/stack
  git checkout -b feat/grahak-os-trust-a-i
  ```
  **Never trust a local copy of this branch after a merge.** A squash merge leaves the
  old local branch looking "ahead" of `stack` by commits whose content is already
  merged, so `git log` reads like unshipped work that is in fact live.
- **Do not trust any commit hash, PR number or count written in this file.** Every
  previous revision named something stale by the time it was read — the revision before
  this one opened by describing PR **#5** as the latest merge when PRs up to **#35** had
  landed. Read the real state: `gh api "repos/wecare-digital/bharat-stack/pulls?state=all&per_page=10"`
  and `git log --oneline -1`.
- Merges from this branch so far include PRs #26, #28, #32 and #35, all squash-merged
  into `stack`. Anything described in earlier revisions of this file as "shipped on this
  branch" is therefore already on `stack` and live.
- No PR is open **now**. Owner's standing instruction: push to this one branch, open
  a PR only when explicitly asked, and the **owner merges** — never the agent.

## Shipped in the latest session (branch recreated from `stack` at `e4cfbe0e`)

Deliberately no commit hashes: they are squash-merged away, and hashes in this file have
misled every reader so far.

| What | Where |
|---|---|
| **`climate` → `climate tech`** in the Home rotation. Measured 178px → 298px, which cuts the pill's tail travel from a 183px spread to 83px, and puts the word on the same axis as `frontier tech` | `src/pages/index.tsx` |
| **Contact card no longer hides behind the fixed header.** `scroll-margin-top:128px` / `112px` on `.cl`, `.cl-h2`, `.cl-map`, matching `.lgd-section`. Was 90px of a 151px card hidden at 768px | `src/components/ContactLocation.tsx` |
| **The `X-Frame-Options` meta tag is gone.** It was the console error on every page load of the site; `amplify.yml` already sets the real header | `src/pages/_document.tsx` |
| **The browser harness now lives in the repo** and `animcheck.js` actually exists | `tools/browser/` |
| **Corrected the false "controls are inert" claim** on the contact map, and the `mapprobe.js` citation | `src/components/ContactLocation.tsx` |
| Replaced 53 lines of self-contradicting comment above `CYCLE_WORDS` (it described nine words, then four, while the array held five) | `src/pages/index.tsx` |

## Needs the owner, not an agent

1. **Merge.** Nothing above reaches production until this branch lands in `stack`.
2. **Dependency vulnerabilities are not code-fixable today.** `/store`'s seven findings
   all come from `@wix/cli`, and **`1.1.247` is the latest published version** — there
   is nothing to upgrade to. The root critical `tar` comes only from `tar@6.2.1` nested
   under `plivo-browser-sdk → wasm-pack → binary-install`, all `fixAvailable: false`;
   the copy we control (`@capacitor/cli`) is already on `7.5.22`, above the whole
   `<=7.5.20` vulnerable range. The only lever is `overrides`, which means forcing
   tar 7 under packages written for tar 6 — that risks the Plivo softphone's install,
   so it is a judgement call, not a patch. Dependabot's alerts API returns 403 to the
   sandbox token (`security_events` scope), so work from `npm audit`.
3. **`npm ci` IS BROKEN AGAIN, and the usual fix provably does not work.** Earlier
   revisions of this file said "`package-lock.json` resynced — `npm ci` works again".
   That is no longer true. On `stack` at `e4cfbe0e`:
   ```
   npm error `npm ci` can only install packages when your package.json and
   npm error package-lock.json ... are in sync.
   npm error Missing: @opentelemetry/core@2.0.0 from lock file   (x4)
   ```
   **`npm install` exits 0 and leaves `package-lock.json` byte-identical** — `git diff`
   is empty afterwards — so "update your lock file with `npm install`", which is what the
   error message and the previous fix both say, cannot resolve it. `npm ci
   --legacy-peer-deps` (what `deps-upgrade.yml` actually runs) fails identically.

   The drift is **inside upstream tarballs, not in this repo.**
   `@aws-amplify/data-construct` and `@aws-amplify/graphql-api-construct` each *bundle*
   (`inBundle: true`) their own OpenTelemetry copies. Their bundled
   `@opentelemetry/resources@2.0.0` and `sdk-trace-base@2.0.0` both declare an **exact**
   dependency on `@opentelemetry/core@2.0.0`, while the `@opentelemetry/core` bundled
   beside them is **2.8.0**. Two packages x two dependents = the four errors. `npm
   install` succeeds because it trusts bundled deps rather than resolving them; `npm ci`
   validates those edges and refuses.

   Consequences: use `npm install` in the sandbox, not `npm ci`. `deps-upgrade.yml` is
   `workflow_dispatch`-only so nothing fails per-push, but that workflow's `npm ci` gate
   **will** fail if run — though since it deletes the lockfile and regenerates from
   scratch on a networked runner first, it is also the most likely thing to fix this.
   Worth a manual run at `mode=lock-only`.
4. **`amplify.yml` still deploys with `npm install`.** Switching to `npm ci` would make
   deploys reproducible, but it is blocked outright by the item above — and `npm install`
   is currently the only command that works, so the status quo is load-bearing rather
   than lazy.
5. **Real-device pass.** Everything has been verified in headless Chromium only. iOS
   Safari and the Android WebView shells have not been checked.
6. **The contact map's three Google controls are LIVE, not inert — pick a fix.** The
   code claimed the interaction overlay made them inert. Measured, it does not: all three
   sit in the 26px bottom strip the overlay deliberately leaves uncovered for attribution,
   and a click hit-test lands on the iframe, so `Show satellite imagery` will actually
   change the map. They cannot be safely patched with geometry, because the attribution
   links sit in the same strip at coordinates Google does not document — a pixel-tuned
   cut-out risks covering attribution, which is a licence breach worse than the defect.
   Three options, all needing a decision: set `NEXT_PUBLIC_GOOGLE_MAPS_KEY` (the keyed
   Maps JS path already passes `disableDefaultUI` and removes them outright), move to
   Static Maps, or set `pointer-events:none` on the iframe and render our own attribution
   links outside it. Full measurements are in the comment above `.cl-lock`.
7. **Type ladder: the section-h2 rung in the design contract is the site's minority
   spelling — pick one.** Measured on all 15 public routes at 1280px with
   `node tools/browser/typecheck.js`. Six distinct h2 treatments, each traceable to a
   different authored `clamp()`, so **none of this is a browser rendering difference** —
   every browser computes the same numbers.

   | Declaration | @1280 | Owners |
   |---|---|---|
   | `clamp(32px,4.2vw,54px)`/700/1.04/-1.875px | 53.76px | `/grahak-os/` only — 3 headings. **This is what the contract says.** |
   | `clamp(28px,3.2vw,40px)`/700/1.08/-1.2px | 40px | **12 headings on 10 pages** — `.home-close-title`, `.home-flow-title`, `.cl-h2`, `.mo-h2`, `.brx-h2`, `.pdp-h2` (×7) |
   | `clamp(22px,2.4vw,28px)`/700/1.2/-0.6px | 28px | `.lgd-h2` ×69 on `/terms/` + `/privacy/` |
   | `clamp(36px,4.3vw,60px)`/**600** | 55.04px | `/grahak-os/` `.gos-closer-head` — the **hero h1 clamp**, on an h2 |
   | `14px`/600/uppercase/.04em | 14px | `.lgd-toc-title` "Contents" ×2 — an **eyebrow**, not a heading |

   **Recommendation: adopt `clamp(28px,3.2vw,40px)`/700/1.08/-1.2px** as the marketing
   section-h2 rung and amend the contract to match, rather than raising 12 headings to
   meet 3. Two reasons beyond the head count. It is already one *byte-identical*
   declaration under five class names in five files, so it was clearly deliberate. And the
   contract's own rung barely reads as subordinate: the hero h1 is
   `clamp(36px,4.3vw,60px)` = 55.04px at 1280, so a 53.76px h2 sits **1.28px** below its
   own h1 — the size hierarchy collapses and only the 700/600 weight inversion separates
   them. Every page authored after `/grahak-os/` quietly chose the smaller rung.

   Then keep two rungs as deliberate exceptions, written into the contract so they stop
   reading as drift: `.lgd-h2` at 28px (a legal document with 45 numbered sections cannot
   carry 54px headings), and `.lgd-toc-title`, which should become a `<p>` or move onto the
   12px/700/.08em eyebrow rung.

   Already fixed, because it needed no decision: `/` carried **two** section-h2 sizes,
   `.home-flow-title` at 33.28px beside `.home-close-title` at 40px, under a comment
   claiming it was "the contract's rung … the same on every page". It is now on the 40px
   rung and the home page is internally consistent. Still open on `/grahak-os/`:
   `.gos-closer-head` at 55.04px/600 both exceeds the contract's 54px cap and inverts its
   one hard rule that a section h2 is 700 and heavier than the h1. Either it is a
   hero-scale closer by design — in which case the contract should name it and it probably
   should not be an `<h2>` — or it is drift.
8. **`/grahak-os/` and `/vayulok/` heroes reflow at narrow widths — needs a design call.**
   This is the "page jumps every 2400ms" defect the code believes it fixed. It was fixed
   on Home and in `RotatingHero` by putting the pill on its own line, but the two inline
   copies still set it mid-sentence (`Bharat <pill> Intelligence`, `across <pill>`), so
   their h1 line count depends on the active word. Measured with `animcheck.js`:
   Grahak OS at 320px is **168px on `WhatsApp` against 128px** on the other three, and at
   360px 128 vs 87; VayuLok at 320px is **126px on `Weather`/`Forecast`/`Heatmap` against
   87px** on `Air`/`Pollen`/`Solar`, and at 480px 87 vs 47. The fix is to move those two
   onto `RotatingHero`, or to force the pill onto its own line at narrow widths — either
   changes the hero's line structure on two product pages, which is why it was not done
   unasked.

## Open work an agent can pick up

- ~~`_document.tsx` sets an `X-Frame-Options` meta tag.~~ **Deleted.** It gave zero
  protection, since browsers honour XFO only as a header, and it logged an error on every
  page load of the site — `animcheck.js` now reports **zero** console errors on `/`,
  `/grahak-os/`, `/vayulok/` and `/contact/`. `amplify.yml` still sets the real
  `SAMEORIGIN` header. A comment marks the spot so it is not re-added.
- **`npm run lint` is red repo-wide**: **230 errors / 63 warnings**, including ~115
  `react-hooks/set-state-in-effect` errors. Only the `LanguageBar` one was fixed.
  Measured baseline, so it can be used as one: `git stash`-ing the latest session's
  changes produced the identical 230/63, i.e. that work added no lint debt. Earlier
  revisions of this file claimed 236/63 and 237/63; re-count rather than trusting a
  number here.
- ~~Home page is a scaffold, DEFERRED.~~ **Home now has a hero.** Owner asked for the
  rotating headline from Grahak OS and VayuLok, so `src/pages/index.tsx` carries the
  same pill on the same constants — 2400ms, `cubic-bezier(.16,1,.3,1)` for the wipe
  and width glide, `(.34,1.56,.64,1)` for the dot pop. **There are FOUR rotating
  surfaces, not three** — `home-` on `/`, `hero-` on `/grahak-os/`, `vl-` on
  `/vayulok/`, and `rh-` in `RotatingHero` (used by `/contact/`, `/terms/`, `/privacy/`,
  `/bharat-rx/`, `/my-order/`). They are one animation family: retune one and you must
  retune all four. `animcheck.js` compares the computed transitions across all four and
  currently measures them identical; `HomePage.test.tsx` fails if Home drifts.
  - Copy is **provisional** and carries owner positioning (lower cost, less
    complexity, utility over scale). The rotation itself is the "across every domain"
    claim, enacted rather than asserted. Reword via `CYCLE_WORDS` and `.home-sub`.
  - **No service names in the rotation.** travel, rituals, documents, reflection and
    disputes were each in it at some point; a service can be discontinued, and on that
    day the headline is false. Channel names (WhatsApp, SMS, email, phone) are fine,
    which is why the Grahak OS hero may rotate them. Note `/contact/` still rotates
    **`drop documents`** — it reads as an action rather than a service, but it is worth
    an owner ruling given "documents" is on the banned list.
  - **Rotating word length is a layout constraint.** The pill animates to each word's
    *measured* width, so the spread is how far the headline's tail travels per tick.
    Measured at 1280px: `consumers` 278, `enterprises` 280, `climate tech` 298,
    `frontier tech` 300, `AI applications` 361 — spread 83px. The real failure mode is
    the h1 reflowing on the longest word only, which would shift the page every 2400ms;
    `.home-head-line` is `display:block` so the pill owns its line and this cannot
    happen. `node tools/browser/animcheck.js` measures h1 height for every word at 21
    viewports from 320 to 1920 **and** through a live rotation: constant, 131px at
    1280px.
  - Below the hero there are now two sections — `.home-flow` (the `WorkflowTerminal`)
    and the `.home-close` band, which reveals on scroll via `IntersectionObserver`
    rather than a timer. `.home-layout`'s `gap:96px` is the section rhythm.
- ~~`/faq` and `/partners` are now in the nav but are visually off-system.~~
  **Both pages are deleted.** The nav entries are absolute, same-tab links to
  `www.wecare.digital/selfservice` (relabelled **Selfservice**) and
  `www.wecare.digital/product-page/referral-partner`, and both routes are out of the
  `isPublic` allowlist. Consequence worth knowing: `/partners` was the only **public**
  WhatsApp Embedded Signup entry point. `EmbeddedSignupPanel` survives because
  `dm/whatsapp/connected-accounts` and `dm/whatsapp/embedded-signup` still use it, but
  it is now reachable only behind auth. Two backend WhatsApp replies still send
  customers to `https://wecare.digital/faq`
  (`inbound-whatsapp-handler/handler.py:1887` and `:6414`) — **owner call**, since
  that is marketing-site content, not a route in this app.
- **VayuLok's rotation promises Pollen and Heatmap**, which have no endpoint wired.
- **`trust-subtext` restates the channel list a third time** on `/grahak-os`.

## Traps that have already cost real time

- **styled-jsx drops a `className` passed via spread.** `{...props}` then styled-jsx
  appends its *own* `className` attribute, which wins — the element ships with only
  `class="jsx-hash"` and no styling at all. Write `className` **inline** on the
  element. This broke the whole nav menu and **all 33 tests still passed**, because
  they assert role/name/href and never look at classes.
- **styled-jsx does not scope composite components.** A parent's `<style jsx>` cannot
  reach into `<BrandBadge />`. Such components style themselves — see `BrandBadge`,
  `BrandLockup`, `AuthBrand`.
- **`src/styles/*.css` is imported globally by `_app.tsx` and declares unscoped rules
  for generic names** — `.page`, `.tab`, `.code-block`, `.nav-item`, `.badge`,
  `.section-header`. Several "my change didn't apply" bugs were this. Prefix new
  classes (`pp-`, `ft-`, `ag-`, `acp-`).
- **A stray backtick inside `<style jsx>{`…`}</style>` breaks the build** (once for 520
  tsc errors). Check with:
  ```bash
  python -c "s=open('src/pages/grahak-os/index.tsx').read();i=s.find('<style jsx>{\`');j=s.rfind('\`}</style>');print(s[i+13:j].count('\`'))"
  ```
- **`npx tsc --noEmit` must run *after* `npm run build`** — it needs generated
  `next-env.d.ts`.
- **`cmd | tail; echo $?` reports `tail`'s exit code, not the command's.** Redirect to
  a file and check `$?`, or use `PIPESTATUS`.
- **`trailingSlash: true`.** Links to exported pages need the trailing slash
  (`/vayulok/`), or they redirect. `/access` is deliberately bare.
- **The Amplify `Authenticator` renders client-side only** — the static export contains
  none of its markup, so anything in that tree must be verified in a browser.
- **`hideSignUp` means the Authenticator renders no tabs at all.** The
  `components.tabs.item` tokens in `authTheme` are therefore **inert** — measured in a
  browser, `[role="tab"]` matches zero elements on `/access`. A whole block of theme
  config had drifted off-palette (`#6b7280`) with nothing on screen to reveal it. Do
  not tune those tokens expecting a visible change.
- **The public pages' typeface came from an auth library.** `/` and `/vayulok/`
  rendered in Inter only because `@aws-amplify/ui-react/styles.css` sets a
  `font-family` on `body` beginning with Inter; neither shell declared one, and
  `--font-sans` in `Pages.css` contains **no Inter** to fall back to. Both shells now
  declare the stack explicitly. Measuring `getComputedStyle().fontFamily` alone will
  not catch this class of bug — compare the **rendered advance width** of a fixed
  string against the same string forced to Inter, which is what `verify.js` does.
- **Its `components.Header` slot is typed `() => JSX.Element | null`.** `React.FC` is
  `(props, context?)` and is **not assignable**; tsc fails with "Target signature
  provides too few arguments."
- **`Header.test.tsx` asserts literal CSS substrings**, including
  `"@media(max-width:767px){.hdr-in{height:96px"`. `.hdr-in` must stay the first rule
  in that media query, and `container.querySelector('button')` must return the nav
  trigger — so no `<button>` may precede it.
- **Node 24 is required** (`engines: >=24.0.0`). In the sandbox:
  `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24`.
- **jsdom does not implement `window.matchMedia`**, and calling it *throws* rather
  than returning undefined. Any component gating animation on
  `prefers-reduced-motion` therefore crashes on mount under vitest — it surfaced as
  all 8 Home tests failing at once with a green build and clean lint. `src/test/setup.ts`
  now stubs it, defaulting to `matches:false` so tests exercise the animated path.
  VayuLok has gated its rotation this way from the start and never hit this only
  because **it has no test of its own**.
- **`/tmp` does not persist between tool calls in this sandbox.** Writing a log there
  and reading it in the next command gets "No such file or directory", which looks
  like the command failed when it did not. Keep the write and the read in one call,
  or put the file under `/projects`.
- **A JSX comment cannot contain `*/`, and a glob will put one there.** Writing
  `customHeaders` pattern `"**/*"` inside a `{/* … */}` block closes the comment early
  and the build fails with `Expression expected` / `Unterminated string constant`
  pointing at a *prose* line, which reads like a mangled file rather than a comment
  delimiter. Cost one build cycle in `_document.tsx`.
- **`elementFromPoint` takes VIEWPORT coordinates and returns `null` off-screen.**
  Hit-testing the contact map's controls without scrolling the map into view returned
  `null` for all five, which the harness then scored as "the click was blocked" — so the
  check **passed while three controls were live**. Scroll the target into view first, and
  treat "could not determine" as a failure rather than a pass. This is the same shape as
  the `[role="tab"]`-matches-nothing trap above: an assertion that cannot see its subject
  reports success.
- **`cmd | grep -c …` in an `&&` chain aborts the chain when the count is zero**, because
  `grep` exits 1 on no matches. A diagnostic command then silently never runs and the log
  it was supposed to write does not exist, which looks like the tool failed. Related to
  the `PIPESTATUS` note above and bites just as often.
- **`npm ci` cannot install this repo** — see "Needs the owner". Use `npm install`. The
  error tells you to run `npm install` to fix the lockfile; doing so exits 0 and changes
  nothing, because the inconsistency is inside bundled upstream tarballs.

## Verification gate

Measured at the head of the latest session's work:

```bash
npx vitest run                       # 73 passed / 8 files
npm run build                        # exit 0; then:
npx tsc --noEmit                     # 0 errors
./scripts/check-provider-policy.sh   # 8/8 ok
npx eslint .                         # 230e/63w — red, pre-existing, unchanged by this work
node tools/browser/animcheck.js      # 16/20 — 4 known failures, see below
node tools/browser/contactcheck.js   # 12/13 — 1 known failure, see below
node tools/browser/typecheck.js      # 1/3   — 2 known failures, the type-ladder decision
```

Two things to know about that list. **`npm ci` is not in it** — it is broken, see
"Needs the owner". And `.venv/bin/python -m pytest -q` is not in it either: there is no
`.venv` in a fresh sandbox, and the latest session changed no Python, so it was not run.
Earlier revisions quoted `33 passed / 7 files` and `237e/63w`; both were stale. Re-count.

Browser harnesses now live **inside the repo**, at **`tools/browser/`**. They used to
live in `/projects/pwtest`, and a sandbox reset destroys that whole directory — which is
how `animcheck.js` came to be cited in four files while existing nowhere on disk, and
`mapprobe.js` in a fifth. Under version control that cannot recur. See
`tools/browser/README.md`.

```bash
cd tools/browser && npm install   # one package: playwright-core, no browser download
cd ../.. && npm run build         # produces out/
node tools/browser/animcheck.js
node tools/browser/contactcheck.js
```

`playwright-core` rather than `playwright` is deliberate: it never downloads a browser,
so the app's own dependency tree and its already-fragile lockfile stay untouched, and
nothing runs a browser-download postinstall on an Amplify deploy.

**Never hardcode the Chromium path.** In this sandbox it lands in
`/opt/playwright/chromium-<rev>/chrome-linux64/chrome`, not `~/.cache/ms-playwright`
— but **the revision changes across resets**, and harnesses pinned to
`chromium-1243` all died with `executable doesn't exist` on a box that had
`chromium-1232` sitting right there. That reads like a broken harness, not a missing
browser, and it cost a debugging round. `lib/browser.js` resolves it: `CHROME` env
var, then Playwright's own lookup, then the highest `chromium-*` under
`/opt/playwright`, then `~/.cache/ms-playwright`; it throws naming every path it
searched rather than returning undefined.

**Harnesses are dual-mode.** `lib/serve.js` exports `target()`: with no `BASE` it
boots its own static server against `out/` (background servers are blocked, so each
run owns one) and handles `trailingSlash` resolution; with `BASE` set it points at
that origin instead and starts nothing. So the same assertions run against either
render:

```bash
node tools/browser/animcheck.js                              # against out/
BASE=http://localhost:3000 node tools/browser/animcheck.js   # against next dev
```

That distinction is load-bearing: `next.config.js` only sets `output:'export'` when
`NODE_ENV` is production, so `out/` is pre-generated HTML and dev is a live server.
A suite that only ever ran against `out/` has not tested what you see locally.

**State of that claim, stated precisely.** The `BASE` branch is verified: `animcheck.js`
returns an identical 16/20 pointed at a separate origin as it does booting its own server.
It has **not** been run against `next dev` in this sandbox, because a dev server started in
one tool call is killed before the next one runs (`curl` then gets `000`, which reads as a
broken harness rather than a dead server). To cover dev, start the server and run the
harness **in a single command**, and **warm every route first** — dev compiles per route on
first request, and an uncompiled route answers slowly enough that a harness measures a blank
page and reports a false failure. The old `rundev.sh` that did this was lost with
`/projects/pwtest`; rewriting it under `tools/browser/` is worth doing.

`animcheck.js` allows **three** console-error patterns and nothing else. Two appear only
under dev and are dev-server infrastructure, not regressions: `_clientMiddlewareManifest.js`
is served with a MIME type Chromium refuses, and the `_next/hmr` websocket cannot complete
a handshake through this sandbox's networking. The third applies in **both** modes and is
a local-origin artifact: `LanguageBar` fetches `api.wecare.digital/site-language`, which
sends no `Access-Control-Allow-Origin` for `127.0.0.1`, so the request is refused by CORS.
On the deployed site the page origin *is* `wecare.digital` and it succeeds. That entry is
scoped to the one host, and the generic `Failed to load resource` line it also produces is
matched by **request URL** rather than by text, so the exemption cannot swallow every
failed request on the page.

Keep that list narrow. A broad `/error/i` filter would have permanently hidden the
`X-Frame-Options` error these checks exist to surface — it sat in that channel on every
page load until it was found by exactly this assertion.

| Script | Checks | In repo |
|---|---|---|
| `lib/browser.js` | Chromium resolution; throws naming every path searched | yes |
| `lib/serve.js` | Static server for `out/`, resolves `trailingSlash`, or honours `BASE` | yes |
| `animcheck.js` | Rotation reflow at 21 viewports on all four surfaces, animation-family transition parity, word widths, console errors — 20 assertions | yes |
| `contactcheck.js` | Card and `#cl-title` vs the fixed header at 4 viewports, in-frame Google controls with a click hit-test, keyless-embed tile canary — 13 assertions | yes |
| `typecheck.js` | Every visible h1/h2/h3 on all 15 public routes at 2 widths; per-page consistency, the de-facto 40px rung, the contract gap — 3 assertions | yes |
| `verify.js`, `fontcheck.js`, `signprobe.js`, `navprobe.js` | Nav labels/hrefs, type ladder, Authenticator tree, nav row colours | **lost with `/projects/pwtest`** |
| `check.js`, `langbar.js`, `authcheck.js`, `ordercheck.js` | Viewport overflow, language restore, sign-in badge order | **lost** |

The lost ones are a description of what to write, not of what exists. Rewrite them under
`tools/browser/` so they stop evaporating.

**Both in-repo harnesses have known failures, left failing on purpose** rather than tuned
green — the same convention the old `langbar.js` note used:

- `animcheck.js` — **4 failures**, all the `/grahak-os/` and `/vayulok/` hero reflow.
- `contactcheck.js` — **1 failure**, the three live Google map controls.
- `typecheck.js` — **2 failures**, the section-h2 rung decision and `.gos-closer-head`.

Both are owner decisions, described under "Needs the owner". Nothing else is red.
`langbar.js`'s old known failure — "no console errors", caused by the `X-Frame-Options`
meta tag — is **fixed at the source**: that tag is gone and all four public pages now
measure zero console errors.

When writing new browser checks: compare the **rects** returned by
`getBoundingClientRect`, not DOM elements, and **scope selectors**. Both mistakes
produced false failures here — `document.querySelector('input')` matched the header's
new nav search field, not a sign-in field.

## Running it locally (Windows / PowerShell 5.1)

PowerShell 5.1 has no `&&`; run these as separate lines.

```powershell
cd C:\Users\wecar\bharat-stack
git checkout feat/grahak-os-trust-a-i
git checkout -- package-lock.json     # see the trap below
git pull origin feat/grahak-os-trust-a-i
git log --oneline -1                  # MUST print the expected commit
npm ci
Remove-Item -Recurse -Force .next
npm run dev
```

Then `http://localhost:3000/grahak-os/` — **trailing slash required**.

Three things that have each wasted a full round trip:

1. **`git pull` aborts if `package-lock.json` is locally modified** (`npm install`
   leaves it that way) and prints `Aborting` in a wall of output. The pull silently
   does nothing and you keep running old code. **Always confirm with
   `git log --oneline -1` after pulling.**
2. **`Remove-Item ... -ErrorAction SilentlyContinue` hides its own failure.** On
   Windows the delete fails while a `node` process holds `.next` open. Stop the dev
   server first (`Ctrl+C`, then `Stop-Process -Name node -Force`).
3. **If an old `next dev` still holds port 3000**, the new one starts on **3001**
   while 3000 keeps serving the old build. Read the port it prints.

Fastest check that you are on this branch: **`http://localhost:3000/vayulok/`**. That
page does not exist on `stack`, so a 404 means the pull did not land.

The dev service worker no longer needs Ctrl+Shift+R — `_app.tsx` unregisters workers
and clears caches outside production. But a worker installed *before* that fix can
still replay a stale bundle, and the code that removes it lives inside the bundle it
is replaying; one hard reload breaks that loop permanently.

## Design contract

`.kiro/steering/grahak-os-design.md`, scoped to `src/pages/grahak-os/**`,
`src/components/**`, `src/styles/**`. Load-bearing points:

- Section `h2` (700) is deliberately **heavier** than the hero `h1` (600).
- Exactly **one** body level: 20px/400.
- Card-heading rung is **22px/700** — `.pp-strip-title`, `.trust-wordmark`.
- Lime `#d1f470` is for **our own surfaces only** — never on a third-party mark, which
  is why the Meta card stays neutral while the brand badge is full lime.
- Hairlines: 2px = hoverable, 1px = static, always `#e5e7eb`.
- Retired, do not reintroduce: `#2f6b52`, `#075e54`, `#f2fbf6`, `#fbfff0`, `#1e293b`.
- Inter is loaded at **400;500;600;700;800**. There is no 300 face — asking for one
  gets a synthesised weight.
