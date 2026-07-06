# Amplify Gen2 Major Upgrade — Remediation Plan

Status: **planned (not started)** · Owner: platform · Risk: high (touches data/graphql transformer stack)

## Why
`npm audit` reports 95 advisories (2 critical, 14 high, 77 moderate). **All** are inside
**bundled dependencies of Amplify Gen2 build tooling** (`@aws-amplify/backend`,
`@aws-amplify/data-construct`, `@aws-amplify/graphql-*`, bundled `@aws-sdk/*`,
`fast-xml-parser`, `handlebars`, `lodash`, etc.).

Important scoping:
- These packages run **only during `ampx` / Amplify Hosting build** on the CI box.
- They are **not** in the shipped browser bundle and **not** in the Python Lambda runtime.
- `npm audit fix` (non-breaking) is a **no-op** — the vulnerable versions are bundled and pinned by the Amplify majors.
- `npm audit fix --force` is **forbidden**: it would downgrade **Next 16 → 9.3.3** and `aws-amplify` 6 → older, breaking the app.

Therefore runtime exploitability is effectively nil; this is a hygiene/compliance upgrade, done deliberately.

## Target versions
- `@aws-amplify/backend` → **^1.8+** (from current), `@aws-amplify/backend-cli` latest
- `aws-amplify` (client) → **^6.16+**
- Keep **Next 16** and **React 19** (do NOT accept the audit's downgrade suggestions)

## Pre-req
- Do this on a throwaway sandbox first (`ampx sandbox`), never straight to `stack`.
- Full backup of `amplify/` + `package-lock.json`.

## Steps
1. Branch/worktree off `stack` locally (temporary local only — delete after; do not push a long-lived branch).
2. Bump versions:
   ```
   npm i -D @aws-amplify/backend@latest @aws-amplify/backend-cli@latest
   npm i aws-amplify@latest
   ```
3. `npm ci` clean install; resolve peer-dep conflicts (React 19 vs codegen-ui peers — may need overrides in package.json).
4. `npx ampx sandbox` — confirm the data/auth/storage stacks synth + deploy cleanly.
5. Fix any breaking changes:
   - `defineData` / `defineFunction` signature changes.
   - GraphQL transformer schema changes (the `Message`, `Contact`, etc. models in `amplify/data/resource.ts`).
   - `defineBackend` custom CDK (`backend-resources.ts`, `link-resources.ts`, `push-resources.ts`).
6. `npm run build` (Next static export) — must pass.
7. Run the app against the sandbox; smoke-test auth (Cognito), data reads, storage.
8. `npm audit` again — confirm criticals/highs cleared (or documented as still-bundled).
9. Merge the version bumps into `stack` in a **single dedicated commit**; let Amplify build 552+ deploy.
10. Watch the Amplify Hosting build; if it fails, the previous successful deploy stays live — revert the commit.

## Rollback
- Revert the version-bump commit → Amplify redeploys the last-good build. No data migration involved (pure dependency bump).

## Do NOT
- Do not run `npm audit fix --force`.
- Do not bump only sub-dependencies via `overrides` for the bundled Amplify deps — they're bundled and will be ignored / cause resolution drift.
- Do not attempt this in the same PR as feature work.
