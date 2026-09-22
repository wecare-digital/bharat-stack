# Grahak OS frontend handoff

Rewritten 2026-09-22. The previous version was stale — it opened by asking for PR #3
to be merged, which happened long ago.

## Position

- Repo `wecare-digital/bharat-stack`. Default branch is **`stack`**, not `main`.
- All work is on the single long-lived branch **`feat/grahak-os-trust-a-i`**, currently
  at **`40025a1f`**, working tree clean, **0 behind `stack`**.
- **No PR is open.** Owner's standing instruction: push to this one branch, open a PR
  only when explicitly asked, and the **owner merges** — never the agent.
- `stack.wecare.digital` is built from `stack`, so **none of this is live yet**. The
  deployed `/grahak-os` is still the pre-rewrite page and still ships the
  empty-`<body>` export (~3.2 KB) that `3884070a` fixed on this branch.

## Shipped on this branch, most recent first

| Commit | What |
|---|---|
| `40025a1f` | Sign-in screen branded; AuthGate header offset fixed; `/access` on palette |
| `1fd4dd40` | Nav menu grouped by type + search; FAQ and Partners surfaced |
| `957e9e54` | Meta card held on one type scale; footer hover underline removed |
| `f092ee3b` | Removed the "Everything you need" heading that was approved for deletion and missed |
| `38bd3cc0` | `LanguageBar` `set-state-in-effect` error fixed |
| `0c85e23a` | `dependabot.yml` replaced (was the unedited template, so version updates never ran) |
| `2e64146a` | `npm ci` made a blocking gate in `deps-upgrade.yml` |
| `b6afc684` | `package-lock.json` resynced — `npm ci` works again |

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
3. **`amplify.yml` still deploys with `npm install`.** Now that `npm ci` works,
   switching would make deploys reproducible — untested on Amplify's runner.
4. **Real-device pass.** Everything has been verified in headless Chromium only. iOS
   Safari and the Android WebView shells have not been checked.

## Open work an agent can pick up

- **`src/pages/_document.tsx:60`** sets `<meta httpEquiv="X-Frame-Options" content="DENY" />`.
  Browsers ignore XFO in a meta tag entirely, so it provides **zero** protection and
  logs a console error on every page load. `amplify.yml` already sets the real header
  (`SAMEORIGIN`). One-line deletion.
- **`npm run lint` is red repo-wide**: 237 errors / 63 warnings across ~97 files,
  including **116 more `react-hooks/set-state-in-effect` errors**. Only the
  `LanguageBar` one was fixed. Baseline before this session was 242/64.
- **Home page (`src/pages/index.tsx`) is still a scaffold.**
- **`/faq` and `/partners` are now in the nav but are visually off-system** — inline
  styles, `#f9f9f9`/`#1a1a1a`, not the design contract's palette.
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
- **Its `components.Header` slot is typed `() => JSX.Element | null`.** `React.FC` is
  `(props, context?)` and is **not assignable**; tsc fails with "Target signature
  provides too few arguments."
- **`Header.test.tsx` asserts literal CSS substrings**, including
  `"@media(max-width:767px){.hdr-in{height:96px"`. `.hdr-in` must stay the first rule
  in that media query, and `container.querySelector('button')` must return the nav
  trigger — so no `<button>` may precede it.
- **Node 24 is required** (`engines: >=24.0.0`). In the sandbox:
  `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24`.

## Verification gate

All of these were green at `40025a1f`:

```bash
npx vitest run                       # 33 passed / 7 files
npm run build                        # then:
npx tsc --noEmit                     # 0 errors
./scripts/check-provider-policy.sh   # 8/8 ok
.venv/bin/python -m pytest -q        # 1623 passed, 1 skipped
npx eslint .                         # 237e/63w — red, pre-existing
```

Browser harnesses live **outside** the repo in `/projects/pwtest` (Playwright +
Chromium; reinstall with `npx playwright install chromium` — the binary does not
survive a sandbox reset). Each one boots its own HTTP server against `out/`, because
background servers are blocked:

| Script | Checks |
|---|---|
| `check.js` | 11 viewports: overflow, collisions, hydration errors, edge alignment |
| `typecheck.js` | Meta card type scale vs `.pp-strip-title` at 5 widths |
| `navcheck.js` | Grouped dropdown, filtering, empty state, panel inside viewport |
| `langbar.js` | Saved-language restore against a stubbed API |
| `authcheck.js` / `ordercheck.js` | Sign-in badge renders, and sits above the form |

`langbar.js` has **one known failing assertion** — "no console errors" — caused by the
`X-Frame-Options` meta tag above. It fires on every page load regardless of
translation.

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
