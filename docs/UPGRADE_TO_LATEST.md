# Upgrade to Latest — Dependency & Runtime Pathway

Goal: move the whole stack (frontend npm deps, Amplify/CDK backend, Lambda runtimes) to the
latest versions, accepting breaking changes, with a safe verify/rollback path.

> Why this doc exists: the agent environment has **no npm network access**, so the npm steps
> below must run on your local machine or in CI. Everything here is verified-accurate as of
> 2026-06-30 against the npm registry.

## TL;DR
- There are **no new major versions** for any direct dependency — `next` (16.x), `react` (19.x),
  `react-router-dom` (7.x), `@capacitor/*` (8.x), `aws-amplify` (6.x), `@aws-amplify/backend` (1.x),
  `aws-cdk-lib` (2.x) are all already on their current major. So "latest" = minor/patch; breakage risk is low.
- One real issue was **already fixed in `package.json`**: the `overrides` block was pinning
  `fast-xml-parser` to the vulnerable `5.3.4`. It is now `5.9.3` (patched). This takes effect on the next `npm install`.
- Run `./upgrade-latest.ps1` (Windows) or `./upgrade-latest.sh` (CI/mac/linux) to execute the npm half.

## Current vs latest (verified 2026-06-30)

| Package | Installed | Latest | Major bump? |
|---|---|---|---|
| next | 16.1.6 | 16.2.9 | no |
| react / react-dom | 19.2.4 | 19.2.x | no |
| react-router-dom | 7.13.0 | 7.18.1 | no |
| @capacitor/core (+plugins) | 8.2.0 | 8.4.1 | no |
| aws-amplify | 6.16.2 | 6.18.0 | no |
| @aws-amplify/backend | 1.21.0 | 1.23.0 | no |
| @aws-amplify/backend-cli (ampx) | 1.8.2 | 1.8.3 | no |
| aws-cdk-lib | 2.241.0 | 2.243.0 | no |
| fast-xml-parser (override) | 5.3.4 (pinned, vuln) | 5.9.3 | fixed in manifest |

## Phase 0 — Prereqs (run where npm works)
- Node `>=24` (matches `engines`), npm 11+.
- Clean git working tree. The scripts create branch `chore/deps-latest` and back up `package.json`/`package-lock.json`.

## Phase 1 — Frontend npm upgrade (automated)
```bash
# from stack.wecare.digital/
./upgrade-latest.sh          # or:  pwsh ./upgrade-latest.ps1
# to also force-fix transitive vulns into new majors:
FORCE=1 ./upgrade-latest.sh  # or:  pwsh ./upgrade-latest.ps1 -Force
```
The script: bumps every direct dep to `@latest`, runs `npm audit fix`, dedupes, reinstalls,
then `npm run build` and `npm test`. It does **not** commit/push/deploy.

Manual equivalent if you prefer:
```bash
npm install --save next@latest react@latest react-dom@latest react-router-dom@latest aws-amplify@latest @aws-amplify/ui-react@latest @aws-sdk/client-bedrock@latest @aws-sdk/client-bedrock-runtime@latest @capacitor/core@latest @capacitor/cli@latest @capacitor/android@latest @capacitor/ios@latest @capacitor/app@latest @capacitor/browser@latest @capacitor/haptics@latest @capacitor/keyboard@latest @capacitor/push-notifications@latest @capacitor/splash-screen@latest @capacitor/status-bar@latest flag-icons@latest
npm install --save-dev @aws-amplify/backend-cli@latest @aws-amplify/backend-data@latest @aws-amplify/data-construct@latest @aws-amplify/graphql-schema-generator@latest @testing-library/jest-dom@latest @testing-library/react@latest @types/node@latest @types/react@latest @types/react-dom@latest @vitejs/plugin-react@latest jsdom@latest typescript@latest vitest@latest
npm install --save @aws-amplify/backend@latest
npm audit fix
npm run build && npm test
```

## Phase 2 — Backend (Amplify Gen2 + CDK) redeploy
Bumping `@aws-amplify/backend` / `aws-cdk-lib` only matters once the backend is re-synthesized:
```bash
npx ampx pipeline-deploy --branch stack --app-id d22dm4b0jn71jw   # CI/CD deploy
# or for a sandbox check:  npx ampx sandbox
```
Cross-check (already satisfied): `@aws-amplify/backend@1.23.0` needs `aws-cdk-lib ^2.234.1` + `constructs ^10`.

## Phase 3 — Lambda runtimes (OPTIONAL, breaking-ish)
All 54 `wecare-*` Lambdas are on `python3.12` (supported, not EOL) — upgrading is optional.
To move to `python3.13` and/or `arm64`, edit the runtime/architecture in the function definitions
(`amplify/functions/**/resource.ts` or the CDK stack), then redeploy. Validate each handler against
3.13 before shipping. Ask the agent to make these edits if you want them.

## Phase 4 — Verify
```bash
npm run build      # must pass (static export)
npm test
npm audit          # expect criticals/highs to drop sharply (fast-xml-parser override now 5.9.3)
```
Then deploy frontend (git push to `stack` → Amplify build) and, if backend changed, Phase 2.
Re-run the function deploy if you touched Lambdas: `python ../scripts/_deploy_everything.py`.

## Rollback
```bash
git checkout -- package.json package-lock.json    # or restore the .bak files
git checkout stack && git branch -D chore/deps-latest
rm -f package.json.bak package-lock.json.bak
```
Frontend deploys are static; reverting the commit and re-pushing restores the previous build.

## Caveats (track, not blockers)
- **Next 16 vs Amplify SSR**: Amplify's Next.js SSR adapter officially supports `>=13.5.0 <16.0.0`.
  You are on Next 16 but deploy via `output: export` (static — no SSR adapter at runtime), so this is fine.
  Do **not** switch to Amplify SSR/compute on Next 16 without checking adapter support.
- **Amazon Pinpoint EOL — Oct 30, 2026**: any SMS path on Pinpoint (`scripts/setup_pinpoint_sms_tollfree.py`,
  `_fix_pinpoint_pool.py`) must migrate before then.
- **Amplify Gen1 EOL — May 1, 2027**: N/A, you are Gen2.
