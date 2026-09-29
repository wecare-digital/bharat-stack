# `npm ci` works again, because the backend is its own install root

`npm ci` could not install this repo. It failed with four identical errors:

```
npm error `npm ci` can only install packages when your package.json and
npm error package-lock.json ... are in sync.
npm error Missing: @opentelemetry/core@2.0.0 from lock file   (x4)
```

It now exits 0. This records why, and — more usefully — the seven things that did **not** work,
so nobody spends that time again.

## The defect, which is upstream and still live

`@aws-amplify/data-construct` and `@aws-amplify/graphql-api-construct` each *bundle*
(`inBundle: true`) their own OpenTelemetry copies. The bundled
`@opentelemetry/resources@2.0.0` and `@opentelemetry/sdk-trace-base@2.0.0` both declare an
**exact** dependency on `@opentelemetry/core@2.0.0`, while the `@opentelemetry/core` bundled
beside them is **2.8.0**. Two packages x two dependents = the four errors.

`npm install` succeeds because it trusts bundled dependencies rather than resolving them.
`npm ci` validates those edges and refuses. Neither command is wrong; the bundle is
internally inconsistent.

## What did not work

| # | Approach | Result |
|---|---|---|
| 1 | `rm package-lock.json && npm install` — full regeneration | Identical four errors. 12,404 lines removed, 7,302 added, for nothing. |
| 2 | `overrides: { "@opentelemetry/core": "2.8.0" }` — blanket | `npm install` aborts with a V8 stack trace, exit **134**; the follow-up `npm ci` hangs. |
| 3 | `overrides: { "@opentelemetry/resources@2.0.0": { "@opentelemetry/core": "2.8.0" } }` — package-scoped, exact | `npm ci` **passes** and the installed tree is byte-identical to `npm install`'s. But `npm install --package-lock-only` adds two nested entries that a full `npm install` then strips, so the committed lockfile cannot satisfy both commands. An unstable equilibrium. |
| 4 | The same, nested under `@aws-amplify/data-construct` — parent-scoped | Fails. Reduces four errors to one, then asks for `@opentelemetry/core@2.8.0` as a new node that `npm install` will not record. |
| 5 | The same with a **range**, `^2.0.0` | Fails, and instructively: npm then wants `core@2.11.0`, because a range resolves to the highest satisfying version rather than reusing the adjacent bundled copy. Only an exact match equal to the bundled version is accepted. |
| 6 | `npm@11.6.2`, the version `packageManager` pins, instead of the 11.4.2 on the box | Identical four errors. Not a version-specific bug. |
| 7 | Downgrading `@aws-amplify/backend` — 1.24, 1.22, 1.20, 1.16 | All five versions resolve `data-construct` to the same 1.17.7, because the range is `^1.x` and npm takes the newest. The bundle, not the wrapper, is the problem. |

`patch-package` is also documented elsewhere as the remaining option. **It cannot work.**
`npm ci` fails during install, before any lifecycle script runs, so a `postinstall` patch never
executes. That suggestion should not be revived.

## What did work

The four packages are **backend-only**. Verified rather than assumed:

- `tsconfig.json` excludes `amplify/**/*`, so `tsc --noEmit` never typechecks them.
- Nothing under `src/`, `scripts/`, `tools/`, `config/` or `shared/` imports any of them. The
  only textual hit is a dependency name printed on an internal dashboard page.
- `amplify.yml` has no `backend:` phase. Amplify Hosting builds the web app only.
- `vitest` includes `src/**` alone.

So they were in the web app's lockfile without the web app ever needing them. They now live in
`amplify/package.json` as a separate install root:

| | before | after |
|---|---|---|
| root lockfile | 1922 packages, 993 kB | **783 packages, 403 kB** |
| root `npm ci` | 4 errors | **exit 0** |
| `amplify/package-lock.json` | — | 1291 packages, 639 kB |

A side benefit worth keeping: `@aws-amplify/backend` is no longer resolvable from `src/`, so the
web app cannot import backend code by accident. That was previously only a convention.

### Verified stable, not just passing

Both commands now agree, and the lockfile does not move:

```
after npm ci        : 71925eaa3ea1  exit=0
after npm install   : 71925eaa3ea1  exit=0
after npm install#2 : 71925eaa3ea1  exit=0
after npm ci  again : 71925eaa3ea1  exit=0  Missing=0
```

That is the property approach 3 lacked, and it is the reason this one is the fix.

## Running the backend

The CLI lives under `amplify/node_modules` now, so install it once:

```sh
npm run amplify:install     # npm install --prefix amplify
npm run amplify             # ampx sandbox
npm run amplify:deploy      # ampx pipeline-deploy
```

**Use the npm scripts, not the binary directly.** `ampx` reads `npm_config_user_agent` and exits
with `NoPackageManagerError` when it is launched outside a package manager — its own resolution
text says to run it through npm. The scripts invoke
`amplify/node_modules/.bin/ampx` while leaving the working directory at the repo root, which is
where `ampx` looks for `amplify/backend.ts`.

Confirmed working: `npm run amplify -- --help` prints the sandbox help and exits 0, and
`@aws-amplify/backend`, `aws-cdk-lib` and `constructs` all resolve from `amplify/backend.ts`.

**Not confirmed:** an actual `ampx sandbox` or `ampx pipeline-deploy` run. Module resolution and
CLI startup are verified; a real deploy is the one step left to exercise.

**And the reason it is still unexercised is no longer "no credentials".** On this machine
`AWS_PROFILE=wecare-prod` is a long-term key and `aws amplify get-app` answers, so the CLI could
run. It has not been run deliberately, and the reason is written at the top of `amplify.yml`: this
account's Gen2 backend resources and the Python Lambdas were created by boto3 scripts and are not
owned by `ampx`, so `pipeline-deploy` would attempt to create resources that already exist.
`ampx sandbox` is safer in that it builds its own isolated stack, but it is still a new
CloudFormation stack with real resources in the production account. Neither is a step to take as a
side effect of a dependency change. Treat "needs credentials" as retired: what it needs is a
decision about stack ownership.

## Two consequences to know about

**`npm ci` in `amplify/` is still broken**, and always will be while the upstream bundle is
inconsistent — the defect moved with the packages. Use `npm install` there. That is fine: it is
an occasional, manual, credentialled operation, not a per-push gate. The point of the split is
that the web app's install, which runs on every push and every deploy, is now reproducible.

**`deps-upgrade.yml` no longer upgrades the backend packages**, because it operates on the root
manifest and they are not in it. Upgrading them is now a deliberate `npm install --prefix amplify`
plus a review of `amplify/package-lock.json`.

## Done: `amplify.yml` now deploys with `npm ci` (2026-09-29)

The production deploy path was the last consumer still on `npm install`, and it is the one that
mattered most: `npm install` could resolve a newer satisfying version at deploy time, so the tree
that shipped was free to differ from the tree CI had just proved, with nothing recording the
difference. `amplify.yml` preBuild is now `npm ci --no-audit --no-fund` — byte-identical to the
command `build-test.yml` gates on every push, which is the actual reproducibility claim.

Measured on this machine before the edit (Node 24.21.0, **npm 11.19.0** — note that is not the
11.6.2 `packageManager` pins):

| Check | Result |
|---|---|
| `npm ci --dry-run` with and without `--legacy-peer-deps` | exit 0 both |
| `npm ci --no-audit --no-fund`, twice | exit 0; `package-lock.json` **unchanged** |
| `npm run build` on the clean tree | exit 0; 935 sitemap URLs, 1089 blog posts, `out/` complete |
| `scripts/verify_public_bundle_secrets.py` on that export | PASS, 2457 files scanned |
| `amplify.yml` parsed back | all 7 `customHeaders` and both build-phase gates intact |

`--legacy-peer-deps` was dropped rather than carried over, matching `build-test.yml`: the committed
lockfile is generated with plain `npm install`, so the flag has nothing to resolve.

Rollback is `git revert` of that commit. Nothing in AWS changed — but see the shadow spec below,
because the rollback target is not the only build spec in play.

### The console build spec is stale and shadowed, not gone

`amplify.yml` in the repository root **overrides** the spec saved on the app
([AWS build settings](https://docs.aws.amazon.com/amplify/latest/userguide/build-settings.html)),
so the repo file is what runs. App `d22dm4b0jn71jw` nonetheless still carries an inline
`buildSpec` (app-level `environmentVariables` is empty, so nothing was withheld), and it is a much
older revision — committed verbatim at
`docs/execution/snapshots/amplify-d22dm4b0jn71jw-console-buildspec-20260929.yml` — that:

- runs `rm -f package-lock.json` and then `npm install --legacy-peer-deps` — the exact opposite of
  a reproducible install,
- has **no** `python3 scripts/verify_public_bundle_secrets.py` build gate, and
- has only three `customHeaders`, so no `Permissions-Policy` (the softphone microphone grant) and
  neither CSP header.

It is inert while `amplify.yml` exists. It becomes live the moment that file is renamed, moved
under a monorepo `appRoot`, or dropped — and the failure would be silent, publishing an export
that was never checked for a server-side credential. Deleting it is a separate decision and was
not taken here.

### Version sensitivity, kept because it will bite again

On **npm 11.6.2**, the
version `packageManager` pins, both `npm ci` and `npm ci --legacy-peer-deps` exit 0 against the
committed lockfile and leave it unchanged. On **npm 11.4.2** they did not:
`npm ci --legacy-peer-deps` failed on an unrelated optional dependency (`@emnapi/runtime`) against
a lock generated without the flag. So peer-mode consistency between generating and consuming a
lockfile can matter, and it is version-dependent — if a `npm ci` failure ever appears with no
obvious drift, check the npm version against `packageManager` before anything else.

