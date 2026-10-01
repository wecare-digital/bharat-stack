# Material components in WECARE

Runtime source vendored from material-esm/material at the commit in UPSTREAM.json. LICENSE is retained. The application uses file:vendor/material; there is no submodule or embedded Git repository.

Review upstream changes and licenses, replace runtime files from an inspected immutable commit, regenerate SHA256 provenance, refresh the application npm lockfile, then run import checks, typecheck, production build and component/browser checks before updating. Keep React adapters and WECARE theme mappings in application source. Do not import all.js globally.

## Initial verification

2026-10-01: npm installation completed; application TypeScript check passed; button, text-field and dialog runtime imports bundled with esbuild (46 modules, 309920 bytes unminified; this is a smoke-check bundle, not production page transfer size). All 109 vendored source checksums matched the pinned archive.

Upstream observation: buttons/button.js handleSlotChange has an early bare return before icon state assignment. The bundler warns about automatic semicolon insertion. Source is preserved unchanged; verify icon-slot behavior before adoption and document any necessary local fix. No checkout controls have been migrated and browser behavior/production export have not been verified for component use.
