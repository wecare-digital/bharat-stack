# Handover prompt — paste this into the new session

Repo `wecare-digital/bharat-stack`, default branch **`stack`**. We are redesigning the
**public** site section by section. Keep the rhythm we have been using and do not deviate:

> **deep-check → mock → I approve → apply → test → PR → merge**

Never apply a change to `src/` before I have seen a mock and said yes.
Standing rule: **we do not change the basic design — find flaws and improve them.**

## Where we are

Ten PRs merged (#48–#55, #57; #56 was closed empty). `stack` is green: vitest 249/249,
`tsc --noEmit` clean, uicheck 96/96, animcheck 18/18, seocheck 11/11, typecheck 3/3,
chromecheck green, pytest 3413 passed. No open PRs.

Done so far: header/menu, footer, public-route guard, combined WhatsApp+translate widget,
one scroll container, widget slimmed and parked above the footer on phones, language search
box (71 languages, English labels), chrome on every page, no 404 page (mismatches redirect
to `/`), the `/translate` open proxy closed with an Origin gate, hero corrected.

## The task in front of you

`.home-flow` — the home page section **below the hero** (`src/pages/index.tsx`, section at
line 352; all CSS is in the one styled-jsx block in the same file).

The deep-check is **done** and the mock is **pushed and awaiting my decision**:
https://github.com/wecare-digital/bharat-stack/tree/mock-device-audit/mock/home-flow

Read `mock/home-flow/README.md` on that branch first — it has the three flaws, the
recommended options, what was checked and found fine, and four `.cjs` harnesses in
`mock/home-flow/tools/` that reproduce every number. **Do not re-measure from scratch.**

Ask me which options I picked, then apply, test, PR, merge. Recommended were:

1. `.home-flow-copy{max-width:680px}` inside the existing `@media(max-width:1024px)` block
   — the column has no measure at ≤1024 and runs 120 chars/line at 1024px.
2. `767px` → `1024px` on the terminal height media query in `WorkflowTerminal.tsx:466`
   — 768–1024 currently gets one column *and* the 650px desktop panel.
3. **Needs my answer, do not apply unasked:** h2 `letter-spacing:-1.2px` → `-0.03em`.
   That rule is byte-identical to `.home-close-title`, `.cl-h2`, `.mo-h2`, `.brx-h2`,
   `.pdp-h2` — 12 headings on 10 pages. Run `node tools/browser/typecheck.js` first.

After this section, the next one down is `.home-close` (index.tsx:467).

## Environment traps — these will cost you an hour each if you rediscover them

- **node is not on PATH.** Prefix every bash call:
  `export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"`
- `/tmp` does not persist between bash calls. Write to `/projects/sandbox/`.
- Use `npm install`, not `npm ci`. Build: `NODE_ENV=production npm run build` → `out/`.
- Repo root `package.json` is `"type": "module"` — standalone scripts must be `.cjs`.
- Chrome: use `tools/browser/lib/browser.js`'s `launch()`; do not hardcode a path
  (the binary is `chrome-linux64`, not `chrome-linux`).
- Static serving for measurement: `tools/browser/lib/serve.js`'s `target()`.
- Playwright contexts need `serviceWorkers: 'block'` or `public/sw.js` intercepts requests.
- **No backticks inside styled-jsx CSS comments.** One stray backtick ends the template
  literal; the error points at the comment, not the cause. This has bitten three times.
- **No JSX comment inside `cond && ( ... )`** — two expressions where one is allowed.
- Squash-merge only. `merge_method=merge` returns HTTP 405.
- `gh pr create` and all `gh pr`/`gh issue` subcommands fail here (GraphQL). Use
  `gh api repos/wecare-digital/bharat-stack/pulls -f title=... -f head=... -f base=stack`.
- **Check `git branch --show-current` before every push.** Pushing `origin <branch>` while
  standing elsewhere silently pushes that name's *local* ref — it produced an empty PR once.
- Known-failing and **not ours**: 5 tests in `tests/test_wix_blog_migrate.py`
  (`TypeError: unsupported operand type(s) for |`) — local Python is 3.9, CI is 3.12. They
  fail identically on pristine `stack`.
- Negative test assertions will fire on your own explanatory code comments. Strip comments
  from the source before asserting absence.

## Still outstanding, cannot be done in the repo

- Wrong subdomain → home: needs Route 53 / Amplify domain config.
- Revoke the Polly IAM grant (Amplify backend + deploy).
- Delete the retired `/site-language/tts` and `/voices` routes from API Gateway by hand.

## Two reversible decisions to keep in mind

- The hero's lime badge was **removed** (#55) — one line to restore.
- Language choice is **not persisted**. Restoring localStorage also restores a
  per-page-load translation bill.
