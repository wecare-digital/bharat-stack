# Provider, runtime and SDK version inventory — deprecated / EOL / approaching EOL

**Nothing in this document was upgraded.** It is an inventory and a recommended order. No code,
no configuration and no tracked file other than this one was changed. No AWS mutation was made;
every AWS fact below comes from a read (`ListFunctions`, `GetFunction`, `GetLayerVersionByArn`,
`GetApis`, `GetRestApis`, `ListUserPools`, `GetAccount`). No credential was placed on a command
line and `get-secret-value` / `batch-get-secret-value` were not called in any spelling.

**Filename is `…20261001` as instructed.** The measurements were taken **2026-10-02T01:42Z**
(local evening of 2026-10-01). Where a value could not be confirmed it says **UNVERIFIED**
rather than guessing.

**Scope.** Everything *except* the two migrations already owned by other workstreams: the Meta
Graph bump to `v26.0` (`docs/execution/meta-graph-version-audit-20261001.md`) and Wix eCommerce
Cart/Checkout V1 → V2 (`docs/execution/wix-cart-v2-migration-20261001.md`). Both are
cross-referenced in §6 because they compete for the same migration slots, not re-litigated.

Tree state at measurement: `HEAD = 089ba325` on `stack`; the working tree carries uncommitted
work belonging to other sessions, which this document did not touch.

---

## 1. Verdict in one table

Ordered by how soon the clock runs out, not by size.

| # | Item | Pinned here | Latest | Published EOL / deprecation | Verdict |
|---|---|---|---|---|---|
| 1 | **ESLint** | `9.39.5` | `10.11.0` | **EOL 2026-08-06** ([version-support](https://eslint.org/version-support)) | ❌ **PAST EOL**, and currently **not upgradable** — see §2.1 |
| 2 | macOS system `python3` | `3.9.6` | 3.15 line | **EOL 2025-10-31** ([devguide](https://devguide.python.org/versions/)) | ➖ past EOL but **not used** — `.venv` is 3.12.14 and `conftest.py` refuses 3.9 |
| 3 | **Playwright container base OS** | `v1.63.0-jammy` → Ubuntu 22.04 | `v1.63.0-noble` / `-resolute` exist at the same Playwright version | **standard support ends April 2027** ([22.04 release notes](https://documentation.ubuntu.com/release-notes/22.04/)) | ⚠️ ~6 months — earliest real deadline |
| 4 | **Google Places** | legacy web service | Places API (New) | deprecated by Google; no date published → **UNVERIFIED date** | ⚠️ already tracked in the register; credential blocker closed |
| 5 | **Lambda `python3.12`** | 68 of 69 functions | `python3.15` offered; `3.13`/`3.14` deprecate 2029-06-30 | **deprecation 2028-10-31**, block create 2028-11-30, block update 2029-01-10 ([Lambda Python runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)) | ⚠️ 2 years; biggest blast radius |
| 6 | **CPython 3.12** (venv + runtime) | `3.12.14` | 3.15.x | **EOL 2028-10**, security-only since 2025-04 ([devguide](https://devguide.python.org/versions/)) | ⚠️ same clock as #5 |
| 7 | **Node.js** | `.nvmrc` = `24` | 26 Current; 24 "Krypton" is LTS | **LTS to end of April 2028** ([v22→v24](https://nodejs.org/en/blog/migrations/v22-to-v24), [previous releases](https://nodejs.org/en/about/previous-releases)) | ✅ supported — but see the §2.4 config defect |
| 8 | **Amazon SES v1 API** | `boto3.client('ses')`, `send_email` | SESv2 | **no EOL published**; new capabilities land only in v2 ([AWS blog](https://aws.amazon.com/blogs/messaging-and-targeting/upgrade-your-email-tech-stack-with-amazon-sesv2-api/)) | ⚠️ soft lock-in, one function |
| 9 | **TypeScript** | `6.0.3` | `7.0.2` | no published EOL (**UNVERIFIED**) | ⚠️ a full major behind; entangled with #1 |
| 10 | **Google Cloud Translation v2** | `…/language/translate/v2` | v3 "Advanced" | **not deprecated** — v2 is the "Basic" edition, no EOL ([API overview](https://docs.cloud.google.com/translate/docs/reference/api-overview)) | ➖ capability gap, not an EOL |
| 11 | **Razorpay** | `api.razorpay.com/v1` | v1 is the gateway for most APIs; some on v2 | none | ✅ **current** ([API reference](https://razorpay.com/docs/api/)) |
| 12 | **Wix `/site-media/v1`** | `POST /site-media/v1/files/import` | same | none on this method | ✅ **current** ([Import File](https://dev.wix.com/docs/api-reference/assets/media/media-manager/files/import-file)) |
| 13 | **Wix `/members/v1`** | `POST /members/v1/members/query` | same | none | ✅ **current** ([Query Members](https://dev.wix.com/docs/rest/crm/members-contacts/members/members/query-members)) |
| 14 | **vendor/material** | commit `e9324f46`, v3.3.4 | v3.3.4 — the pinned commit **is** `main` HEAD | n/a | ✅ **at upstream tip**; one naming hazard, §2.9 |
| 15 | **boto3 / botocore** | `1.43.103` (dev file) | `1.43.107` | n/a | ✅ dev-only lag; production copy is runtime-supplied and **UNVERIFIED** |
| 16 | **`awslambdaric`** | `4.0.0` (Dockerfile) | `4.1.0` | n/a | ✅ **do not bump** — 4.1.0 is sdist-only; the pin is the fix |
| 17 | Cognito / API Gateway shapes | `cognito-idp`, `apigatewayv2` | unversioned / v2 | n/a | ✅ no legacy shape in use, §2.10 |
| 18 | Sinch RCS India, Truecaller, Plivo | `convapi/v1`, `access-api/v2`, `profile4-noneu/v1`, `api.plivo.com/v1` | — | — | ❓ **UNVERIFIED** — no public version-lifecycle page found, §4 |

Counting only items with a published date against them: **1 past EOL and actionable**
(ESLint), **1 past EOL and inert** (system python3.9), **4 with dated deadlines** (Ubuntu 22.04
base image, Lambda python3.12, CPython 3.12, Node 24), **2 deprecated-without-a-date** (Google
Places legacy, SES v1 as soft lock-in).

---

## 2. The items, in detail

### 2.1 ESLint 9 — past EOL, and the interesting part is *why it cannot be fixed today*

| | |
|---|---|
| Pinned | `package.json` devDependencies `"eslint": "^9.39.5"`; installed `9.39.5` |
| Latest | `10.11.0` (`npm view eslint version`, 2026-10-02) |
| EOL | **2026-08-06.** `v9.0.0–v9.39.5` is listed EOL, last release `9.39.5`, v10.x Current since 2026-02-06 — [eslint.org/version-support](https://eslint.org/version-support) |
| Consumed by | `npm run lint` (`eslint .`), `eslint.config.mjs`, `eslint-config-next@16.3.6`, and whichever CI job runs lint |
| Blast radius | Lint-only. No runtime artefact. But it is the **whole** lint signal for 127 pages |

The pin is literally the final v9 release, so there is no patch left to take. The honest finding
is that the upgrade is **blocked by Next.js's own lint plugins**, measured from the registry:

| Package | Latest | `peerDependencies.eslint` | Accepts v10? |
|---|---|---|---|
| `typescript-eslint` | 8.71.0 | `^8.57.0 \|\| ^9.0.0 \|\| ^10.0.0` | **yes** |
| `eslint-plugin-react-hooks` | 7.1.1 | `… \|\| ^9.0.0 \|\| ^10.0.0` | **yes** |
| `eslint-plugin-react` | 7.37.5 | `… \|\| ^9.7` | **no** |
| `eslint-plugin-import` | 2.32.0 | `… \|\| ^9` | **no** |
| `eslint-plugin-jsx-a11y` | 6.10.2 | `… \|\| ^9` | **no** |

All five arrive as dependencies of `eslint-config-next`, whose own peer range is
`eslint: >=9.0.0` — permissive, which is why `npm outdated` reports eslint as simply "latest
10.11.0" and gives no hint that three of its transitive plugins cap at 9. Forcing v10 today
means peer overrides on three plugins that have not declared support, i.e. trading a *known* EOL
for *unknown* lint behaviour on the only automated review gate the frontend has.

There is a second coupling worth seeing before planning: `typescript-eslint@8.71.0` pins
`typescript: >=4.8.4 <6.1.0`. The repo is on TypeScript `6.0.3`, inside that range by one minor.
So **item #9 (TypeScript 6 → 7) also waits on the same toolchain**, and doing TS first would
break lint instead.

**Recommended now:** record it in `packages/config/vendorVersions.ts` as a deliberate pin with
`upgradeBlockedReason` and a `lagExpiresOn`, which is exactly the mechanism that file exists for,
and watch the three plugins. Do not override peers.

### 2.2 The Playwright container base image — the nearest real deadline

| | |
|---|---|
| Pinned | `amplify/functions/operations/docs-scraper/Dockerfile:` `FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy` |
| Pinned alongside | `playwright==1.63.0` in that function's `requirements.txt`; `awslambdaric==4.0.0` |
| Latest | Playwright `1.63.0` is **already latest** on both PyPI and npm. The registry publishes `v1.63.0-jammy`, `v1.63.0-noble` and `v1.63.0-resolute` at that same version (MCR tag list, 994 tags) |
| EOL | `jammy` = **Ubuntu 22.04**, standard support to **April 2027** — [release notes](https://documentation.ubuntu.com/release-notes/22.04/). ESM extends security cover but is a paid, separate thing |
| Consumed by | exactly one function: `wecare-docs-scraper`, `PackageType=Image`, `x86_64`, image `…/wecare-docs-scraper:580ec1c`, digest `sha256:3f893702…`, last modified 2026-10-01T07:20Z |
| Deploy path | `.github/workflows/docs-scraper-deploy.yml` only. No `live` alias, `update-function-code` takes effect immediately (`docs/execution/runtime-inventory.md` records this as an expected exception) |
| Blast radius | **One function, one tag character-string.** Rollback is re-pushing the previous tag/digest. Nothing else in the fleet imports from this image |

This is the cheapest migration in the document and has the earliest date. Note that Playwright
itself is **not** the problem — the pin is current — so this is purely a base-OS move, and the
same Playwright version already ships a `noble` (24.04) variant.

Do **not** touch `awslambdaric==4.0.0` while in there. The Dockerfile records, in detail, that
`4.1.0` shipped as an sdist with no wheels on 2026-09-28 and turned an unpinned dependency into a
red deploy requiring `cmake`. PyPI still reports `4.1.0` as latest. The pin is the remedy, not
debt.

### 2.3 Lambda `python3.12` — biggest blast radius, latest deadline

Live read, 2026-10-02, `us-east-1`, account 775261844268: **69 functions**, 68 on `python3.12`
(Zip), 1 `PackageType=Image` (`wecare-docs-scraper`). Architectures: 68 `x86_64` and **one
`arm64`** — `wecare-workspace-mcp`.

| | |
|---|---|
| Pinned | `config/vendor-versions.json` `lambdaPythonRuntime: "python3.12"`; `packages/config/vendorVersions.ts` `LAMBDA_PYTHON_RUNTIME` |
| Latest | AWS now offers **`python3.15`** (deprecation "Not scheduled"); `python3.13` and `python3.14` both deprecate 2029-06-30 |
| EOL | `python3.12`: **deprecation 2028-10-31**, block function create **2028-11-30**, block function update **2029-01-10** — [Building Lambda functions with Python](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html) |
| Upstream | CPython 3.12 is in **security-only** phase; **EOL 2028-10** ([devguide](https://devguide.python.org/versions/)) |

**The register is stale here and it understates the lag.** `vendorVersions.ts` records
`verifiedLatest: 'python3.13'` as of 2026-09-26; AWS now lists 3.14 and 3.15 as well. The
`lag-allowed-with-reason` verdict still holds, but the number next to it is two releases out of
date.

**Blast radius, measured rather than assumed — three Lambda layers are the real cost:**

| Layer | Consumers | `CompatibleRuntimes` |
|---|---|---|
| `…:layer:pillow-python312:2` (ours, "Pillow 12.1.1 … manylinux2014_x86_64") | `wecare-invoice-engine` | **`python3.12` only** |
| `…:layer:cryptography-python312:1` (ours, WhatsApp Flows encryption) | `wecare-partner-onboarding`, `wecare-whatsapp-business-api`, `wecare-partner-token-refresh`, `wecare-marketing-ads` | **`python3.12` only** |
| `arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-Pillow:10` (**third-party community layer**) | `wecare-product-image-gen` | **`python3.12`**, `x86_64` |

So a runtime move is not "edit one constant and redeploy". It is: rebuild two of our own layers
for the target runtime, find or replace a third-party `p312` layer we do not control, then move
68 functions through `update-function-code` → publish → move the `live` alias (58 functions carry
that alias per `lambda-snapstart-deploy.md`, and the count drifts upward as aliases are
provisioned, so re-derive it). WhatsApp Flows encryption and invoice rendering are both on that
list, which means a runtime slip breaks money-adjacent paths.

`REJECTED_RUNTIMES` in `vendorVersions.ts` already refuses `python3.9`, `nodejs18.x`,
`nodejs20.x` and preview `nodejs26.x` — consistent with AWS's deprecated-runtime table (Python
3.9 deprecated 2025-12-15, Node.js 20 2026-04-30, Node.js 18 2025-09-01;
[Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)). No
function runs a rejected runtime.

### 2.4 Node.js — the version is fine; the *configuration* has three sources of truth

| | |
|---|---|
| Pinned | `.nvmrc` = `24`; `package.json` + `amplify/package.json` `engines.node = ">=24.0.0"`; `packageManager: npm@11.6.2` |
| Local | `node v24.21.0`, `npm 11.19.0` |
| Latest | Node **26** is Current; **24 "Krypton" is LTS**, maintained to **end of April 2028**. Node 22 "Jod" is still LTS, Node 20/25 are EOL ([previous releases](https://nodejs.org/en/about/previous-releases), [v22→v24](https://nodejs.org/en/blog/migrations/v22-to-v24)) |

So there is **no Node EOL exposure**. The defect is drift between declarations:

1. `amplify.yml` preBuild runs `nvm install 24 || true` then `nvm use 24 || true`. It does not
   read `.nvmrc`, it is not pinned to a minor, and `|| true` means a failed install **silently
   falls through to the image default**. The build then proceeds with whatever Node the Amplify
   image shipped, and `npm ci` emits only an `EBADENGINE` *warning* — `engines` is advisory, so
   nothing fails.
2. `.github/workflows/build-test.yml` does it correctly: `setup-node` with
   `node-version-file: .nvmrc`.
3. `.github/workflows/deps-upgrade.yml` hard-codes `node-version: 24`, a third place to edit.

**The recorded EBADENGINE observation is explained and is not a version problem.**
`.agents/tasks/checkout-audit-2026-10-01/findings.md` logged `npm ci` warning that the package
wants `>=24.0.0` while the sandbox had `v22.23.3`, and `context.json` calls it "non-fatal on node
v22". That was a **cloud-sandbox environment**, not CI and not Amplify: CI pins from `.nvmrc`,
and this Mac is on v24.21.0. Node 22 is a supported LTS, which is why it only warned. The
residual risk is #1 above — Amplify could build on the image default without failing — not Node
22 itself.

Hygiene, not a migration: make `amplify.yml` read `.nvmrc` (or at minimum drop `|| true` so a
failed `nvm install` is loud), and have `deps-upgrade.yml` use `node-version-file`.

### 2.5 boto3 / botocore — the pin that does not reach production

| | |
|---|---|
| Pinned | `requirements-dev.txt`: `boto3==1.43.103`, `botocore==1.43.103`, `awscrt==0.37.0`, `s3transfer==0.19.2` |
| Also | `amplify/functions/operations/docs-scraper/requirements.txt`: `boto3>=1.43.103` (floating floor — the only place boto3 is actually *installed into* a deployment artefact, the container image) |
| Latest | `boto3` / `botocore` **1.43.107** (PyPI, 2026-10-02) |
| EOL | None. boto3 is the current major; the EOL'd generation is AWS SDK for Python's predecessor, not in use |

`requirements-dev.txt` says so itself, in a header worth trusting: the deploy scripts bundle only
`handler.py`, `lambda_utils/`, `static_knowledge_base.py` and a function's own modules. **No
third-party package is bundled.** So the 68 Zip functions use the boto3 that the `python3.12`
runtime supplies, and AWS documents that Lambda updates it periodically and does not publish a
table — the only way to read it is to print `boto3.__version__` from inside a function
([runtime-included SDK versions](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)).

**Production boto3/botocore version: UNVERIFIED.** Establishing it requires invoking a function,
which is beyond "reads only" for this task. AWS's own recommendation is to bundle or layer the
SDK for control; this repo deliberately does not, which is a conscious trade of control for
package size and is noted here rather than argued with.

Two drift findings in the dev environment, both reproducibility rather than security:

- **`.venv` does not match `requirements-dev.txt`.** Installed: `boto3`/`botocore` **1.43.98**
  (pinned 1.43.103), `awscrt` 0.36.4 (pinned 0.37.0), `cryptography` 50.0.1 (pinned 50.0.1,
  latest 50.0.2), plus older `google-ads` 32.0.0 against the pinned 33.0.0. The venv predates the
  current file; `pip install -r requirements-dev.txt` reconciles it.
- **Two packages are installed but unpinned:** `codespell` and `elevenlabs`. `elevenlabs` is
  referenced only by `scripts/retire_orphan_integrations.py` and
  `scripts/check_provider_policy_live.py`. A freeze file that claims "so a rebuilt venv matches
  byte for byte" cannot omit installed packages.
- **A comment in `requirements-dev.txt` is wrong.** It says `pydantic==2.13.5` hard-pins
  `pydantic-core==2.49.0`, making a `2.49.0` report a false positive. PyPI metadata for
  pydantic 2.13.5 declares `pydantic-core==2.46.5` — which is exactly what the file pins. The
  **pin is correct and the explanation is not**; `2.49.0` is simply the newer standalone release.
  Severity INFORMATIONAL, but a wrong reason invites someone to "fix" a correct pin.

Also unused-but-pinned, costing nothing at runtime and worth knowing before anyone bumps them:
`razorpay==2.0.1` (latest; **no handler imports it** — every Razorpay call is raw `urllib` in
`lambda_utils/integrations/razorpay_*`) and `facebook_business==26.0.2` (latest; the file already
documents it as unused).

### 2.6 Razorpay API — current, and the `/v1` path is correct

| | |
|---|---|
| Pinned | `API_BASE = "https://api.razorpay.com/v1"` in `lambda_utils/integrations/razorpay_orders.py` and `razorpay_verify.py`; same literal in `core/secure-files/razorpay_orders.py`, `messaging/partner-onboarding/handler.py` (`/v1/payment_links`), and the scripts `razorpay_add_webhook_events.py`, `webhook_inventory.py`, `check_secrets_live.py`, `update_razorpay_secret.py` |
| Latest | **`/v1` is current.** Razorpay documents `https://api.razorpay.com/v1` as the gateway URL for most APIs, and notes certain APIs sit on V2 so the gateway URL differs for those — [API reference](https://razorpay.com/docs/api/) |
| EOL | **None published.** No deprecation notice found for `/v1` |
| Consumed by | `wecare-razorpay-webhook`, `wecare-secure-files`, `wecare-partner-onboarding`, plus four operator scripts |
| Blast radius if changed | **Do not change it.** This is the money path: payment capture, refund and payment-configuration mutation are standing prohibitions, and `whatsapp-payments-india-reference.md` requires the authoritative readback through `razorpay_verify` |

The repo already shows awareness of the split: `src/pages/workspace/dashboard/index.tsx` displays
both base URLs, labelling v2 as Route / Linked Accounts. Nothing in this repo calls a v2 surface.
**No action.**

### 2.7 Wix `/site-media/v1` and `/members/v1` — both current

| Endpoint in repo | Call sites | Wix status |
|---|---|---|
| `POST https://www.wixapis.com/site-media/v1/files/import` | `ecommerce/wix-store/handler.py:1215`, `ecommerce/product-image-gen/handler.py:453` | **Current.** The Media Manager "Import File" reference publishes exactly this endpoint — [Import File](https://dev.wix.com/docs/api-reference/assets/media/media-manager/files/import-file) |
| `POST /members/v1/members/query` | `operations/seo-tools/blog_publish.py:265` | **Current.** The Members "Query Members" reference publishes exactly this endpoint — [Query Members](https://dev.wix.com/docs/rest/crm/members-contacts/members/members/query-members) |
| `GET /members/v1/members…` (list, get, create) | `scripts/wix_blog_migrate.py:378,389,396` | same family, same version |
| `GET /members/v1/members/my` | `scripts/probe_wix_capabilities.py:187` | capability probe |
| `GET /site-properties/v4/properties` | `scripts/probe_wix_capabilities.py:188`, `scripts/resolve_wix_site_id.py:63` | **UNVERIFIED** — v4 is what the probe uses; no lifecycle page was checked |

What *is* deprecated nearby, and deliberately not used: Wix's **Bulk** Import Files method is
marked deprecated and replaced ([Bulk Import Files
(Deprecated)](https://dev.wix.com/docs/api-reference/assets/media/media-manager/files/bulk-import-files)).
This repo imports **one file per call**, so it is on the current method. Recorded so a future
"let's batch the imports" change does not walk into the deprecated one.

**No action** on either, beyond adding them to the register (§5), since today neither appears in
`vendorVersions.ts` at all.

### 2.8 Amazon SES — v1 and v2 in the same codebase

| | |
|---|---|
v1 | `amplify/functions/messaging/outbound-email/handler.py:26` — `boto3.client('ses')`, `send_email` |
| v2 | `amplify/functions/auth/email-verification/handler.py:124` — `boto3.client("sesv2")`; `lambda_utils/comms/verification_email.py` takes an injected `sesv2` client, which is also what makes it testable |
| Latest | SESv2 |
| EOL | **None published for v1.** AWS states v1 continues to be supported while new capabilities arrive only in v2 — [Upgrade your email tech stack with the SESv2 API](https://aws.amazon.com/blogs/messaging-and-targeting/upgrade-your-email-tech-stack-with-amazon-sesv2-api/) |
| Live account state | `sesv2:GetAccount` → `ProductionAccessEnabled: true`, `SendingEnabled: true`, `EnforcementStatus: HEALTHY` |
| Blast radius | One handler, one call, one `live` alias move. `verification_email.py` already documents the v1/v2 split, so the intended target is not in doubt |

This is not an EOL item. It is a **single remaining v1 caller** in a codebase that has already
adopted v2 elsewhere, with a proven in-repo pattern to copy. That combination is what makes it
cheap, which is why it ranks early in §7 despite having no deadline.

### 2.9 vendor/material — pinned at upstream tip, with one naming hazard

| | |
|---|---|
| Pinned | `vendor/material/UPSTREAM.json`: commit `e9324f469a95433575e274b0402334076dd02324`, `upstreamVersion 3.3.4`, Apache-2.0, plus SHA256 for all 109 files |
| Upstream | tag **`v3.3.4` is that exact commit**, and GitHub's compare API reports `pinned…HEAD` as **`status: identical, ahead_by: 0`** (checked 2026-10-02). The vendored copy is at `main` HEAD, dated 2026-09-30 |
| Dependency | `lit: ^3.3.1` declared; `lit@3.3.3` installed, which **is** latest |
| EOL | n/a — not a versioned API |
| Consumed by | `package.json` `"material": "file:vendor/material"`. `VENDORING.md` records the 2026-10-01 verification: TypeScript check passed, three components bundled under esbuild, all 109 checksums matched. **No checkout control has been migrated to it yet** |

Nothing to upgrade. Two things to carry forward:

- **A public package is called `material` too, at version `1.0.4`** (`npm view material version`),
  unrelated to `material-esm/material`. The local dependency is `file:vendor/material`, so today
  resolution is by path — but any tool or lockfile regeneration that resolves that bare name
  against the registry would silently fetch a stranger's package. Low likelihood, high
  consequence; worth a note in `VENDORING.md` rather than a code change.
- `VENDORING.md` already records an unresolved upstream observation (`buttons/button.js`
  `handleSlotChange` early bare return, ASI warning). That is an adoption blocker for buttons, not
  a version problem.

### 2.10 Cognito, API Gateway and SMS/voice shapes — verified clean

Live read, 2026-10-02:

| Surface | Measured | Verdict |
|---|---|---|
| HTTP API | **1** — `zllr9lrg7j` `wecare-digital-api`, `ProtocolType: HTTP` | API Gateway **v2** only |
| REST API | **`GetRestApis` → 0 items** | the API Gateway **v1 (REST)** shape is not in use anywhere |
| Cognito | `cognito-idp`, 10 call sites; pools `us-east-1_cSx0RHCIR` (staff) and `us-east-1_46ULYuukt` (customers) | `cognito-idp` is unversioned; nothing to migrate |
| SMS / voice | `boto3.client('pinpoint-sms-voice-v2')` in `lambda_utils/comms/sms.py`, `messaging/sms-aws`, `messaging/voice-aws`, `scripts/aws_sms_check.py` | the **v2** API, i.e. AWS End User Messaging. The rename from Amazon Pinpoint SMS changed no API, CLI, IAM or endpoint ([Introducing AWS End User Messaging](https://aws.amazon.com/about-aws/whats-new/2024/07/aws-end-user-messaging/)) |
| Amazon Pinpoint proper | `boto3.client('pinpoint')` — **zero occurrences**; no `ApplicationId`/project usage | not exposed to the Pinpoint console service's lifecycle, whatever its date (**UNVERIFIED**, and moot) |

For Cognito there is a sharper risk than versioning, already documented in `aws-agent-rules.md`
and restated because it would be easy to trip during any "modernisation" pass: `UpdateUserPool`
is a **full replace**, and a partial argument set silently cleared three Lambda triggers and
opened self-signup on 2026-09-28. Use `scripts/cognito_pool_safe_update.py`.

### 2.11 Frontend / tooling patch lag — hygiene, not EOL

`npm outdated`, 2026-10-02, plus installed versions read from `node_modules`:

| Package | Installed | Latest | Note |
|---|---|---|---|
| `next` | 16.3.6 | 16.3.8 | patch; register still says `configured: '16.2.9'` vs the manifest's `^16.2.9` — the **register is stale**, the installed tree is ahead of it |
| `eslint-config-next` | 16.3.6 | 16.3.8 | moves with `next` |
| `vite` | 8.3.1 | 8.3.2 | patch |
| `vitest` | 5.0.2 | 5.0.3 | patch |
| `@types/node` | 26.6.3 | 26.6.4 | patch |
| `@aws-sdk/client-bedrock-runtime` | 3.1142.0 | 3.1145.0 | AWS SDK for JS **v3** — the EOL'd generation is v2, not in use |
| `typescript` | 6.0.3 | **7.0.2** | **major**, and gated by `typescript-eslint`'s `<6.1.0` peer — §2.1 |
| `react` / `react-dom` | 19.3.0 | 19.3.0 | current |
| `aws-amplify` | 6.22.1 | 6.22.1 | current |
| `@aws-amplify/ui-react` | 6.15.6 | 6.15.6 | current |
| `@capacitor/core` | 8.5.2 | 8.5.2 | current; native packaging is POST-PROJECT per `00-current-owner-overrides.md` |
| `lit` (via vendor/material) | 3.3.3 | 3.3.3 | current |
| `esbuild` | 0.28.2 | 0.28.2 | current |
| `jsdom` | 30.1.1 | 30.1.1 | current |
| `aws-cdk-lib` (`amplify/package.json`) | **2.270.0 exact** | 2.272.0 | deliberate exact pin, reason recorded in the register |
| `constructs` | 10.8.1 exact | 10.8.1 | current |
| `@aws-amplify/backend` | `^1.23.0` | 1.25.1 | caret; resolves forward |
| `@aws-amplify/backend-cli` | `^1.8.3` | 1.10.0 | caret; resolves forward |

None of these has a published EOL. They matter here only because a patch sweep must not be
confused with a migration, and because two register rows (`next`, `typescript`) no longer match
the tree.

---

## 3. What each change would actually break — blast radius, ranked

| Item | Artefacts touched | Verification available | Rollback |
|---|---|---|---|
| Playwright base OS tag | 1 line, 1 Dockerfile, 1 function | its own GitHub Actions workflow; function has no `live` alias so the deploy is immediate and observable | re-push previous image tag / digest `sha256:3f893702…` |
| SES v1 → v2 | 1 handler, 1 function | existing `verification_email.py` injection pattern + pytest; IAM action names unchanged | revert the handler, re-publish, move alias back |
| ESLint 9 → 10 | `package.json`, `package-lock.json`, `eslint.config.mjs`, potentially every lint finding | `npm run lint`; no runtime artefact | lockfile revert |
| TypeScript 6 → 7 | typecheck across 127 pages, `tsconfig.json`, possibly `vitest`/`next` types | `npm run typecheck`, `npx vitest run`, `npm run build` | lockfile revert |
| Google Translate v2 → v3 | `core/site-language/handler.py` | handler tests; note this is the file CodeQL has already failed twice on, so **do not add any log line touching the key** | revert + alias move |
| Google Places legacy → New | `whatsapp-templates/handler.py` + a new AddressService | server key `wecare/google-maps-server` already proven live | revert + alias move |
| Lambda `python3.12` → 3.13+ | 68 functions, **3 layers**, 58+ `live` aliases, `vendor-versions.json`, `vendorVersions.ts`, `REJECTED_RUNTIMES` | full pytest suite per function package; `deploy_all_lambdas.py --dry-run` validates that every top-level import resolves in the package or an attached layer | per-function alias revert to the prior version; layers must be rebuilt **before** any function moves |

---

## 4. UNVERIFIED — stated as unknown rather than guessed

1. **Production boto3/botocore version in the 68 Zip functions.** Runtime-supplied; AWS publishes
   no table. Needs a function invocation.
2. **Sinch RCS India (ACL) versions.** The send path is Conversation API **v1**
   (`https://convapi.aclwhatsapp.com/v1/projects/{projectId}/messages:send`,
   `lambda_utils/sinch_rcs.py:45`); template management uses **access-api v2**
   (`https://api.aclwhatsapp.com/access-api/v2/rcs/{username}/templates`,
   `messaging/rcs-send/handler.py:640,673`) with an explicit **v1 fallback candidate** at
   `:780`. No public version-lifecycle or deprecation page was found for either. The v1/v2
   fallback ladder is itself evidence that the vendor's versioning is not firmly documented.
3. **Truecaller** `https://profile4-noneu.truecaller.com/v1/default` — no public lifecycle page.
4. **Plivo** `https://api.plivo.com/v1/Account/` — v1 appears to be the only version; no
   published EOL found. (Plivo SMS is a standing prohibition; this is the voice path.)
5. **Wix `site-properties/v4`** — used by two scripts; version lifecycle not checked.
6. **Google Places legacy deprecation date.** The register records the surface as deprecated and
   the credential blocker as closed; Google publishes no retirement date that was confirmed here.
7. **TypeScript / Next.js / React published EOL dates.** None of the three publishes a dated EOL
   table comparable to Node or Python; "latest" is verified, "EOL" is not applicable rather than
   unknown-but-existing.
8. **Amazon Pinpoint (the console service) lifecycle.** Searched and not confirmed. Moot: there is
   no `boto3.client('pinpoint')` anywhere, only `pinpoint-sms-voice-v2`.
9. **Whether `eslint-plugin-react` / `-import` / `-jsx-a11y` have eslint-10 work in flight.** Only
   their published peer ranges were read, not their issue trackers.

---

## 5. Register gaps — things this inventory found that `vendorVersions.ts` does not track

`packages/config/vendorVersions.ts` is the stated single source of truth and is the right place
for all of this. It currently has **no entry** for:

| Missing entry | Why it belongs there |
|---|---|
| **ESLint** | the only past-EOL item in the tree; precisely the "pinned with a reason and an expiry" case the file models |
| **Container base image** (`playwright/python:…-jammy`) | has the nearest dated deadline of anything measured |
| **Lambda layers** (`pillow-python312`, `cryptography-python312`, third-party `Klayers-p312-Pillow`) | they gate the runtime migration, and one is not ours |
| **boto3 / botocore** | so the "runtime-supplied, deliberately unbundled" decision is recorded rather than inferred |
| **Razorpay API** | the money path's version should be explicit, not implicit in six string literals |
| **Amazon SES v1 vs v2** | a two-version-in-one-codebase state should be visible |
| **Wix `site-media` / `members` / `site-properties`** | three more Wix families beyond catalog, ecom and blog |
| **Google Cloud Translation** | v2 Basic vs v3 Advanced is a live choice in `site-language` |
| **vendor/material + lit** | a vendored copy with a commit pin is exactly a version |

Two existing rows are **stale** against the tree measured today: `FRONTEND_FRAMEWORK`
(`configured: '16.2.9'`, installed 16.3.6, latest 16.3.8) and `LAMBDA_PYTHON_RUNTIME`
(`verifiedLatest: 'python3.13'`, while AWS now offers 3.14 and 3.15).

Adding rows is a code change and therefore **out of scope for this task** — recorded as the
recommendation, not performed.

---

## 6. Deliberately excluded, because another workstream owns them

| Item | Owner | Status, for sequencing only |
|---|---|---|
| Meta Graph `v25.0` → `v26.0` | `docs/execution/meta-graph-version-audit-20261001.md` | repo constant already moved to `v26.0`; the live fleet still pins `v25.0` on five functions, so production has not moved. `v25.0` is callable until 2028-07-29 |
| Wix eCommerce Cart / Checkout V1 → V2 | `docs/execution/wix-cart-v2-migration-20261001.md` | code complete, opt-in behind `WIX_CART_V2_ENABLED` (absent fleet-wide). **V1 Cart and Checkout are removed 2027-02-01** — the hardest external deadline anywhere in this repo, earlier than every item in §1 |

Both consume the same scarce resource as everything below: an authorized deploy plus a live
round trip. §7 assumes they go first.

---

## 7. Recommended order — one migration at a time

The ordering rule is: **earliest deadline first, except where a cheap change with a near deadline
can be finished before a distant one needs to start, and except where one change is a
precondition of another.** Patch-level lag is not a migration and is excluded from the sequence.

**0. (Pre-existing, not mine to schedule) Wix Cart V2 switch-on.**
Deadline 2027-02-01 is the earliest in the repo and it is a money path. Everything below assumes
this and the Meta `v26.0` deploy gate are cleared first, because they contend for the same
authorized-deploy slot.

**1. Playwright container base OS: `v1.63.0-jammy` → `v1.63.0-noble`.**
Earliest deadline among the items in this document (Ubuntu 22.04 standard support ends April
2027, roughly six months out), **and** the smallest change in it: one `FROM` line, one function,
one dedicated workflow, no `live` alias, rollback by image digest. Playwright itself does not
move — the same version already publishes a `noble` tag — so the change is isolated to the base
OS. Doing it first also costs nothing from the deploy budget the bigger items need. Leave
`awslambdaric==4.0.0` alone for the recorded reason.

**2. Amazon SES v1 → SESv2 in `messaging/outbound-email`.**
No deadline, so it is here on *cost and consistency* rather than urgency: one handler, one call,
and the target pattern already exists and is already under test in
`lambda_utils/comms/verification_email.py` + `auth/email-verification`. It removes the last v1
caller, which converts a "two shapes, unclear which is canonical" state into one answer, and it
is the last point at which that is a five-line change rather than an archaeology exercise. It
must go **after** 1 only because one migration at a time is the rule, not because it depends on
it.

**3. ESLint 9 → 10 — opened now, landed when unblocked.**
This is the only item past EOL, so it ranks above everything with a future date; it is **third**
because it is currently impossible to do correctly. `eslint-plugin-react`, `eslint-plugin-import`
and `eslint-plugin-jsx-a11y` cap at eslint 9 in their *latest* releases, and forcing peers would
replace a dated, understood risk with an undated, unmeasured one on the frontend's only
automated review gate. The action in this slot is therefore: record the pin in the register with
`upgradeBlockedReason` and a `lagExpiresOn`, and watch those three plugins — then take the
upgrade the moment any two of them declare `^10`. Treat the register entry as the deliverable, not
the version bump.

**4. TypeScript 6 → 7.**
Strictly after 3, and for a concrete reason rather than caution: `typescript-eslint@8.71.0` pins
`typescript >=4.8.4 <6.1.0`. Moving TypeScript first would break lint for the whole repo while
lint is already on an EOL line, i.e. two broken gates instead of one. Once the lint toolchain
accepts eslint 10 it will also have moved its TypeScript ceiling, and TS 7 becomes a
typecheck-wide change with a working gate to prove it — `npm run typecheck`, `npx vitest run`,
`npm run build`, in that order.

**5. Google Places legacy → Places API (New).**
A genuine vendor deprecation with no date, credential blocker already closed (server key
`wecare/google-maps-server` verified live). It ranks below 1-4 because it is a *feature* migration
— porting `whatsapp-templates/handler.py` off legacy endpoints plus building AddressService — not
a pin change, so it needs its own design and its own tests. It ranks above 6 and 7 because it is
the only item in this group where the vendor has actually said the current surface is deprecated.

**6. Google Cloud Translation v2 (Basic) → v3 (Advanced), or consolidate on Amazon Translate.**
Lowest priority of the provider moves, because **v2 is not deprecated** — it is a lower-capability
edition Google still offers, and Google's own guidance is only that new projects should prefer
Advanced. `core/site-language/handler.py` already holds an `boto3.client("translate")` alongside
the Google endpoint, so "pick one" is a real option and may be cheaper than the v3 port. Two
constraints to carry in: the referrer-restricted browser key cannot be used server-side (the
lesson already recorded for Places), and this exact file has failed CodeQL twice on
`py/clear-text-logging-sensitive-data` — any change here must not put the key into a logging
expression, even reduced to a boolean.

**7. Lambda `python3.12` → `python3.14` (not 3.13) — last, and as its own project.**
Last because it has the latest deadline (block-update 2029-01-10) and by far the largest blast
radius: 68 functions, 58+ `live` aliases to move, and **three layers that declare
`python3.12` only** — two of ours to rebuild and one third-party `Klayers-p312-Pillow` we do not
control, consumed by `wecare-product-image-gen`. Target 3.14 rather than 3.13 because both
deprecate on the same day (2029-06-30), so 3.13 buys nothing over 3.14 while costing the same
migration; re-check against the runtime table at the time, since `python3.15` is already offered
with no scheduled deprecation and may be the better target by then. Sequence inside the slot:
rebuild layers → verify the four cryptography consumers and the two Pillow consumers → resolve
the third-party layer → then move functions in waves, publishing and moving each alias, with
`deploy_all_lambdas.py --dry-run` proving import resolution before any upload. Starting this
before items 1-6 would consume the entire window on the one item whose window is longest.

**Continuous, outside the sequence (hygiene, no slot needed).**
Rebuild `.venv` from `requirements-dev.txt`; add `codespell` and `elevenlabs` to it or uninstall
them; fix the `pydantic-core` comment; sweep the five patch-level npm lags; make `amplify.yml`
read `.nvmrc` and drop `|| true`; point `deps-upgrade.yml` at `node-version-file`; refresh the two
stale register rows and add the nine missing ones from §5.

---

## 8. Measurement log

| What | How | When |
|---|---|---|
| Lambda fleet, layers, image digest | `ListFunctions`, `GetFunction`, `GetLayerVersionByArn` via AWS MCP, `us-east-1` | 2026-10-02T01:42Z |
| API Gateway v1 vs v2, Cognito pools, SES account | `GetApis`, `GetRestApis`, `ListUserPools`, `sesv2:GetAccount` | 2026-10-02T01:42Z |
| npm latest versions | `npm view <pkg> version` / `peerDependencies`, `npm outdated` | 2026-10-02 |
| Installed npm versions | read from `node_modules/<pkg>/package.json` | 2026-10-02 |
| PyPI latest versions | `pypi.org/pypi/<pkg>/json` | 2026-10-02 |
| venv drift | `.venv/bin/python -m pip list --outdated`, `pip freeze` vs `requirements-dev.txt` | 2026-10-02 |
| material upstream | GitHub tags + `compare/<pinned>...HEAD` → `identical` | 2026-10-02 |
| Playwright image tags | `mcr.microsoft.com/v2/playwright/python/tags/list` | 2026-10-02 |
| Lambda runtime dates, SES guidance, End User Messaging rename | AWS documentation (URLs cited inline) | 2026-10-02 |
| ESLint, Node, Python, Ubuntu, Razorpay, Wix, Google dates | vendor documentation (URLs cited inline) | 2026-10-02 |

Content from external sources was rephrased for compliance with licensing restrictions; every
EOL and latest-version claim carries its source URL inline.

## Related

- `packages/config/vendorVersions.ts` — the register these findings belong in
- `config/vendor-versions.json` — its generated Python-side mirror
- `docs/execution/runtime-inventory.md` — fleet anomalies, including the three documented
  deploy-path exceptions
- `.kiro/steering/lambda-snapstart-deploy.md` — why a code change is not live until the `live`
  alias moves
- `docs/execution/meta-graph-version-audit-20261001.md`,
  `docs/execution/wix-cart-v2-migration-20261001.md` — the two excluded migrations
