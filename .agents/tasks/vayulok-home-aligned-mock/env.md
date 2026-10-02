# Environment — vayulok home-aligned mock

Date: 2026-10-02
Branch: feat/vayulok-update
HEAD: 77fd967b453e43a8853e6412fd3f8e8da7779077

## Headless browser availability

| Probe | Result |
| --- | --- |
| `npx playwright --version` | Version 1.63.0 (CLI available) |
| `which chromium` | not found |
| `which google-chrome` | not found |
| `which chromium-browser` | not found |
| `/root/.cache/ms-playwright`, `/ms-playwright` | missing — no browser binaries downloaded |

**Conclusion:** the Playwright CLI/package resolves, but no browser binary is
installed. Screenshot capture requires `npx playwright install chromium` first
(needs network). If that fails, the mock must be delivered as HTML only, with no
PNG renders.

## Partial-work cleanup

- Deleted untracked partial file `docs/mocks/vayulok-live-mock.html` so the mock
  is rebuilt from scratch.
- Left untouched: `docs/mocks/vayulok-mock.html`, `docs/mocks/vayulok-app-mock.html`
  and their PNGs.
- Stale task folder `.agents/tasks/vayulok-live-mock-feat-vayulok-update-2026-10-02/`
  left in place (untracked, not in scope).
---

## CORRECTION — appended by the orchestrator, 2026-10-02

**The conclusion above is WRONG. A headless browser IS available and verified
working. Do NOT deliver HTML-only, and do NOT skip the screenshots.**

The probes above looked in the wrong place. This sandbox sets
`PLAYWRIGHT_BROWSERS_PATH=/opt/playwright`, so browsers do not live under
`~/.cache/ms-playwright`. Installed and present:

```
/opt/playwright/chromium-1232
/opt/playwright/chromium-1243
/opt/playwright/chromium_headless_shell-1232
/opt/playwright/chromium_headless_shell-1243
/opt/playwright/ffmpeg-1011
```

The `playwright` node module is not in the repo (`node_modules` is not installed)
and is not a global package. It resolves from the npx cache instead:

```
/root/.npm/_npx/e41f203b7505f1fb/node_modules/playwright
```

### Verified launch recipe — use exactly this

Set `NODE_PATH` to the npx cache and `require('playwright')` normally:

```bash
NODE_PATH=/root/.npm/_npx/e41f203b7505f1fb/node_modules node /tmp/your-script.js
```

```js
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto('file:///projects/sandbox/wecare-digital/docs/mocks/vayulok-live-mock.html');
  await p.screenshot({ path: '/abs/path/out.png', fullPage: true });
  await b.close();
})();
```

This exact recipe was smoke-tested by the orchestrator and returned
`LAUNCH OK — fullPage screenshot written`, producing a valid PNG. Chromium
headless shell 153.0.8010.12 (playwright v1243) was additionally downloaded
during that check, so the install is current.

### Requirements that therefore still stand in full

- Capture **full-page** screenshots (`fullPage: true`), not viewport-only — the
  Subscribe and Contribute sections sit far down a long scrolling page and the
  owner must be able to see them.
- Save as `docs/mocks/vayulok-live-mock-1280.png` and
  `docs/mocks/vayulok-live-mock-390.png`, and commit both.
- Measure the outbound network request count in the no-key state and confirm it
  is zero (use `page.on('request', ...)`).
- Capture and confirm zero console errors (`page.on('console', ...)`).
- Verify the rendered DOM section order against the 11-section list.

If any of this still fails, report the actual error text rather than concluding
the browser is unavailable.
