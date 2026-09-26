/**
 * The single source of truth for every vendor, API and runtime version.
 *
 * Why this file exists
 * --------------------
 * Before it, the Meta Graph version reached the runtime three different ways:
 *
 *   1. an env var with a default        `os.environ.get('META_API_VERSION', 'v25.0')`   9 files
 *   2. a hard-coded module constant     `META_API_VERSION = 'v25.0'`                    7 files
 *   3. a literal inside a URL string    `f'https://graph.facebook.com/v25.0/{id}/...'`  3 files
 *
 * Shape 3 is the dangerous one, because a grep for the constant name does not find it.
 * It includes the payment-lookup call in `inbound-whatsapp-handler`, so a version bump
 * could silently leave payment reconciliation on an older API than everything else.
 *
 * This module is canonical for TypeScript. `config/vendor-versions.json` is generated
 * from it for the Python fleet, and `scripts/check-versions.ts` fails when the two drift.
 * Nothing should read a version from anywhere else.
 *
 * The three columns, and why all three are needed
 * -----------------------------------------------
 * `configured`     what this system actually uses. Changing it is a deployment.
 * `verifiedLatest` what the vendor published, as measured on `verifiedOn`.
 * `verifiedOn`     when that measurement was taken.
 *
 * Recording only `configured` hides that we are behind. Recording only `verifiedLatest`
 * invents a fact that rots the day after it is written. Recording the date is what makes
 * the other two auditable — a `verifiedLatest` with no date is a rumour.
 *
 * `configured !== verifiedLatest` is NOT automatically a defect. `v26.0` is newer than
 * `v25.0` and is deliberately not adopted; see `upgradeBlockedReason`.
 */

/** How a version was established. Mirrors the evidence classes in `docs/compatibility.md`. */
export type Evidence = 'LIVE' | 'DOC' | 'REPO' | 'BLOCKED';

/** Whether drift between `configured` and `verifiedLatest` is acceptable. */
export type DriftPolicy =
  /** Must match `verifiedLatest`. Any drift fails the check. */
  | 'must-be-latest'
  /** May lag, but only while `upgradeBlockedReason` explains why. */
  | 'lag-allowed-with-reason'
  /** Deliberately pinned. Drift is expected and is not reported as a problem. */
  | 'pinned'
  /** Cannot be measured automatically; needs a human reading vendor docs. */
  | 'manual-review';

export interface VendorVersion {
  /** Human name, as the vendor writes it. */
  readonly name: string;
  /** What this system uses today. */
  readonly configured: string;
  /** Latest the vendor offered, as measured on `verifiedOn`. `null` when unmeasurable. */
  readonly verifiedLatest: string | null;
  /** ISO date of the `verifiedLatest` measurement. */
  readonly verifiedOn: string;
  readonly evidence: Evidence;
  readonly drift: DriftPolicy;
  /**
   * Why `configured` lags, when it does. Required by `checkVersions` whenever
   * `drift === 'lag-allowed-with-reason'` and the two values differ — a lag with no
   * stated reason is indistinguishable from neglect.
   */
  readonly upgradeBlockedReason?: string;
  /**
   * ISO date after which the reason above stops being accepted.
   *
   * Exists because a *false* reason is worse than a missing one, and a true reason can
   * expire. The v26.0 pin is the case that motivated this: its recorded justification
   * turned out to be unsubstantiated, and the surfaces it claimed to protect are removed
   * from every remaining Graph version on a fixed date anyway — after which the pin
   * protects nothing while still reading as deliberate.
   *
   * Once this date passes, `checkVersions` escalates the finding from `warn` to `error`,
   * so the gate fails rather than a stale justification carrying indefinitely.
   */
  readonly lagExpiresOn?: string;
  /** How to re-measure `verifiedLatest`. Kept next to the number it produces. */
  readonly rederive: string;
}

/**
 * Meta Graph API version.
 *
 * `v26.0` is not adopted yet, but NOT for the reason this repo previously recorded.
 *
 * `meta-business-agent/handler.py:231-234` pins away from v26.0 on the grounds that it
 * "blocked a batch of commerce endpoints" and that `_tool_product_lookup` reads
 * `/{catalog_id}/products`. Checked against Meta's v26.0 changelog, that does not hold:
 * v26.0 deprecates the **Commerce Order Management API** — 47 endpoints shaped
 * `/{commerce-order-id}/…`, `/{page-id}/commerce_orders`, `/{commerce-merchant-settings-id}/…`
 * — because checkout on Facebook and Instagram Shops was sunset. `/{catalog_id}/products` is
 * the Product Catalog API and is not among them. This repository calls none of the 47, and
 * none of the five legacy protocol features v26.0 removes.
 *
 * So the documented blocker is **unsubstantiated**. That is grounds to test, not clearance:
 * whether `/{catalog_id}/products` actually answers on v26.0 still needs one live Graph
 * call, which has not been made.
 *
 * `lagExpiresOn` is 2026-10-27, the date the changelog gives for those surfaces being
 * removed from *all* remaining Graph versions. Past that date the pin protects nothing,
 * so the gate stops accepting it as a reason.
 *
 * v25.0 itself is supported until 2028-07-29, so there is no urgency from its own lifecycle.
 */
export const META_GRAPH: VendorVersion = {
  name: 'Meta Graph API / WhatsApp Cloud API',
  configured: 'v25.0',
  verifiedLatest: 'v26.0',
  verifiedOn: '2026-09-26',
  evidence: 'DOC',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    'Upgrade gated on a Meta contract test covering order_details, payment lookup and the ' +
    'AUTHENTICATION template round trip. NOTE the previously recorded blocker — "v26.0 ' +
    'blocked a batch of commerce calls" — is unsubstantiated: v26.0 deprecates the Commerce ' +
    'Order Management API, which this repo does not call. The pin also protects nothing ' +
    'after 2026-10-27, when those surfaces are removed from every remaining version.',
  lagExpiresOn: '2026-10-27',
  rederive: 'https://developers.facebook.com/docs/graph-api/changelog/versions/',
} as const;

/**
 * The approved AUTHENTICATION template used for phone OTP.
 *
 * Not a version in the semver sense, but it is a vendor-side artifact that can be
 * rejected, paused or re-categorised without any code change here, so it belongs in the
 * same register. Verified live: APPROVED, category AUTHENTICATION, language en.
 *
 * The OTP is delivered as a `url` button parameter, not `copy_code`. Meta materialises an
 * AUTHENTICATION template's copy affordance as a real URL button, and sending `copy_code`
 * is rejected with `(#132018) buttons: Button at index 0 must be of type Url`.
 */
export const META_AUTH_TEMPLATE: VendorVersion = {
  name: 'Meta AUTHENTICATION template (wecare_otp)',
  configured: 'wecare_otp/en',
  verifiedLatest: 'wecare_otp/en',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'must-be-latest',
  rederive:
    'aws lambda invoke --function-name wecare-whatsapp-templates:live ' +
    "--payload '{\"httpMethod\":\"GET\",\"path\":\"/wa-business/templates\"," +
    '"queryStringParameters":{"wabaId":"2094615664435155"}}\'',
} as const;

/**
 * Wix Stores catalog family.
 *
 * Was `BLOCKED` on the theory that confirming the site's catalog version needed the admin
 * credential. It did not, and the distinction is worth keeping: the code calling
 * `/stores/v3/*` proves what the code intends and nothing about the site, but Wix states the
 * site's version itself in an error. `POST /stores/v1/products/query` returns **HTTP 428**
 * with `applicationError.code = CATALOG_V3_CALLING_CATALOG_V1_API`. A visitor token minted
 * from the public `WIX_CLIENT_ID` is enough to elicit that — no secret involved.
 * Corroborated by 7 products returned through `/stores/v3/products/query`.
 */
export const WIX_CATALOG: VendorVersion = {
  name: 'Wix Stores Catalog',
  configured: 'V3',
  verifiedLatest: 'V3',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'must-be-latest',
  rederive: '.venv/bin/python scripts/probe_wix_capabilities.py',
} as const;

export const WIX_ECOM: VendorVersion = {
  name: 'Wix eCommerce (orders, transactions, fulfillments, cart, checkout)',
  configured: 'V1',
  verifiedLatest: 'V1',
  verifiedOn: '2026-09-26',
  evidence: 'DOC',
  drift: 'must-be-latest',
  rederive: 'https://dev.wix.com/docs/api-reference/business-solutions/e-commerce',
} as const;

/**
 * Wix Blog.
 *
 * The API is still not called anywhere in this repo — the adapter is new work — but
 * availability is no longer unknown. `/blog/v3/posts/query` answers with
 * `metaData.total = 571` and `/blog/v3/categories` returns 200, both against a visitor
 * token. So `configured` describes the target *and* the site's actual version.
 *
 * "Absent by grep" was the right statement about this repository and the wrong statement
 * about the site. Worth keeping the two apart.
 */
export const WIX_BLOG: VendorVersion = {
  name: 'Wix Blog',
  configured: 'V3',
  verifiedLatest: 'V3',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'must-be-latest',
  rederive: '.venv/bin/python scripts/probe_wix_capabilities.py',
} as const;

/**
 * Google Places.
 *
 * `configured` is the LEGACY web service (`maps/api/place/autocomplete/json`), which
 * Google has deprecated. The migration target is Places API (New). Note the key
 * restriction problem recorded in `docs/current-environment.md` §6: the unified API key's
 * apiTargets include `places-backend.googleapis.com` but NOT `places.googleapis.com`, so
 * changing this value alone will fail with a key-restriction error until that target is
 * added to the key.
 */
export const GOOGLE_PLACES: VendorVersion = {
  name: 'Google Places',
  configured: 'legacy-web-service',
  verifiedLatest: 'places-api-new',
  verifiedOn: '2026-09-26',
  evidence: 'DOC',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    'Migration blocked on the API key: places.googleapis.com is enabled on project ' +
    'wecaredigitalbw but is absent from the unified key apiTargets. Adding it is a ' +
    'prerequisite. Legacy is deprecated, so this lag has an expiry, not an indefinite pass.',
  rederive:
    "gcloud services api-keys list --format='json(displayName,restrictions)' and " +
    'https://developers.google.com/maps/documentation/places/web-service/op-overview',
} as const;

/** Address Validation, enabled on the project and on the key. Used to verify addresses. */
export const GOOGLE_ADDRESS_VALIDATION: VendorVersion = {
  name: 'Google Address Validation API',
  configured: 'v1',
  verifiedLatest: 'v1',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'must-be-latest',
  rederive: 'gcloud services list --enabled --filter=config.name:addressvalidation.googleapis.com',
} as const;

/**
 * Lambda runtime for the existing fleet.
 *
 * `python3.13` is GA and newer. Moving 64 functions is a fleet migration, not a config
 * change, and `python3.12` is fully supported, so the lag is deliberate.
 */
export const LAMBDA_PYTHON_RUNTIME: VendorVersion = {
  name: 'AWS Lambda Python runtime',
  configured: 'python3.12',
  verifiedLatest: 'python3.13',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    '64 of 65 functions run python3.12 and it remains supported. A fleet-wide runtime ' +
    'move is its own change with its own verification, not a side effect of this build.',
  rederive: "aws lambda list-functions --query 'Functions[].Runtime' | sort -u",
} as const;

/** Node.js. `.nvmrc` pins the major; the local toolchain and CI must agree. */
export const NODE_RUNTIME: VendorVersion = {
  name: 'Node.js',
  configured: '24',
  verifiedLatest: '24',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'must-be-latest',
  upgradeBlockedReason: undefined,
  rederive: 'node -v against .nvmrc and package.json engines.node',
} as const;

/**
 * Frontend framework.
 *
 * The brief names Astro. This repo is Next.js with 127 pages and a static export, and a
 * second framework would split the build for no gain. Recorded as a pin so the check does
 * not report it as drift every run.
 */
export const FRONTEND_FRAMEWORK: VendorVersion = {
  name: 'Next.js (storefront and admin shell)',
  configured: '16.2.9',
  verifiedLatest: '16.3.6',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    'Patch-level lag only. Bump with the normal dependency gate; not on the critical path.',
  rederive: 'npm view next version',
} as const;

/** TypeScript. A full major behind, which is worth surfacing rather than burying. */
export const TYPESCRIPT: VendorVersion = {
  name: 'TypeScript',
  configured: '6.0.3',
  verifiedLatest: '7.0.2',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    'A major version behind. Upgrading is a typecheck-wide change across 127 pages and ' +
    'must land as its own commit with `npm run typecheck` green, not inside a feature.',
  rederive: 'npm view typescript version',
} as const;

export const AWS_CDK: VendorVersion = {
  name: 'aws-cdk-lib',
  configured: '2.270.0',
  verifiedLatest: '2.271.0',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'pinned',
  upgradeBlockedReason:
    'Pinned exactly (no caret) on purpose: Amplify Gen 2 resolves CDK transitively and a ' +
    'floating range has produced construct-version conflicts here before.',
  rederive: 'npm view aws-cdk-lib version',
} as const;

/** Browser automation, required by the brief for cross-browser tests. Not yet installed. */
export const PLAYWRIGHT: VendorVersion = {
  name: '@playwright/test',
  configured: 'not-installed',
  verifiedLatest: '1.63.0',
  verifiedOn: '2026-09-26',
  evidence: 'LIVE',
  drift: 'lag-allowed-with-reason',
  upgradeBlockedReason:
    'Not a dependency yet. tools/browser/ vendors playwright-core as a measurement ' +
    'harness, deliberately outside the app package. The E2E suite introduces the runner.',
  rederive: 'npm view @playwright/test version',
} as const;

/** Every tracked version, keyed by a stable id used in reports and in the JSON mirror. */
export const VENDOR_VERSIONS = {
  metaGraph: META_GRAPH,
  metaAuthTemplate: META_AUTH_TEMPLATE,
  wixCatalog: WIX_CATALOG,
  wixEcom: WIX_ECOM,
  wixBlog: WIX_BLOG,
  googlePlaces: GOOGLE_PLACES,
  googleAddressValidation: GOOGLE_ADDRESS_VALIDATION,
  lambdaPythonRuntime: LAMBDA_PYTHON_RUNTIME,
  nodeRuntime: NODE_RUNTIME,
  frontendFramework: FRONTEND_FRAMEWORK,
  typescript: TYPESCRIPT,
  awsCdk: AWS_CDK,
  playwright: PLAYWRIGHT,
} as const;

export type VendorKey = keyof typeof VENDOR_VERSIONS;

/**
 * Runtimes this project refuses in production, and why.
 *
 * Brief §51 requires preview and deprecated runtimes to be rejected. Encoding the refusal
 * as data means the check enforces it instead of a reviewer remembering it.
 */
export const REJECTED_RUNTIMES: ReadonlyArray<{ readonly id: string; readonly reason: string }> = [
  { id: 'nodejs26.x', reason: 'preview; not GA' },
  { id: 'python3.9', reason: 'the local interpreter is 3.9 but the fleet is 3.12; never deploy 3.9' },
  { id: 'nodejs18.x', reason: 'end of support' },
  { id: 'nodejs20.x', reason: 'superseded by 22/24 for new functions' },
] as const;

/** `v<major>.<minor>`, which is the only shape Meta accepts in a Graph URL. */
const GRAPH_VERSION_PATTERN = /^v\d+\.\d+$/;

/**
 * The Graph version, validated.
 *
 * Every Meta call must route through this rather than reading the constant directly, so a
 * malformed value fails loudly at the first call instead of producing a 404 from Meta that
 * looks like a missing resource. Brief §47 / requirements R1.3.
 */
export function graphApiVersion(): string {
  const value = META_GRAPH.configured;
  if (!GRAPH_VERSION_PATTERN.test(value)) {
    throw new Error(
      `Meta Graph version must look like v<major>.<minor>; got ${JSON.stringify(value)}`,
    );
  }
  return value;
}

/** Base URL for a Meta Graph call. The only place a Graph URL is assembled. */
export function graphApiBase(): string {
  return `https://graph.facebook.com/${graphApiVersion()}`;
}

/** Whether a Lambda runtime id is refused in production, with the reason. */
export function runtimeRejection(runtimeId: string): string | null {
  const hit = REJECTED_RUNTIMES.find((entry) => entry.id === runtimeId);
  return hit ? hit.reason : null;
}

export interface DriftFinding {
  readonly key: VendorKey;
  readonly name: string;
  readonly configured: string;
  readonly verifiedLatest: string | null;
  /** `error` fails the check; `warn` reports without failing; `ok` is silent. */
  readonly severity: 'error' | 'warn' | 'ok';
  readonly message: string;
}

/**
 * Compare `configured` against `verifiedLatest` for every tracked version.
 *
 * Pure and dependency-free so it is unit-testable without network or AWS. The CLI in
 * `scripts/check-versions.ts` is a thin wrapper around this.
 */
export function checkVersions(
  versions: Readonly<Record<string, VendorVersion>> = VENDOR_VERSIONS,
  now: Date = new Date(),
): readonly DriftFinding[] {
  const findings: DriftFinding[] = [];

  for (const [key, entry] of Object.entries(versions)) {
    const base = {
      key: key as VendorKey,
      name: entry.name,
      configured: entry.configured,
      verifiedLatest: entry.verifiedLatest,
    };
    const matches = entry.configured === entry.verifiedLatest;

    if (entry.drift === 'must-be-latest') {
      findings.push(
        matches
          ? { ...base, severity: 'ok', message: 'current' }
          : {
              ...base,
              severity: 'error',
              message: `must be latest but is ${entry.configured}, latest ${String(entry.verifiedLatest)}`,
            },
      );
      continue;
    }

    if (entry.drift === 'lag-allowed-with-reason') {
      if (matches) {
        findings.push({ ...base, severity: 'ok', message: 'current' });
      } else if (!entry.upgradeBlockedReason) {
        // The whole point of this policy is that the reason is mandatory. A lag with no
        // stated reason is indistinguishable from nobody having looked.
        findings.push({
          ...base,
          severity: 'error',
          message: 'lags latest with no upgradeBlockedReason recorded',
        });
      } else if (entry.lagExpiresOn && new Date(entry.lagExpiresOn).getTime() <= now.getTime()) {
        // The reason had a deadline and the deadline passed. Keeping it at `warn` would let
        // an expired justification carry indefinitely, which is the failure this field exists
        // to catch.
        findings.push({
          ...base,
          severity: 'error',
          message: `justification expired on ${entry.lagExpiresOn}: ${entry.upgradeBlockedReason}`,
        });
      } else {
        const suffix = entry.lagExpiresOn ? ` [justification expires ${entry.lagExpiresOn}]` : '';
        findings.push({
          ...base,
          severity: 'warn',
          message: entry.upgradeBlockedReason + suffix,
        });
      }
      continue;
    }

    if (entry.drift === 'manual-review') {
      findings.push({
        ...base,
        severity: 'warn',
        message: entry.upgradeBlockedReason ?? 'needs manual review against vendor docs',
      });
      continue;
    }

    findings.push({ ...base, severity: 'ok', message: 'pinned deliberately' });
  }

  return findings;
}

/** The shape mirrored into `config/vendor-versions.json` for the Python fleet. */
export interface VendorVersionsJson {
  readonly generatedBy: string;
  readonly metaGraphApiVersion: string;
  readonly metaGraphApiBase: string;
  readonly metaAuthTemplateName: string;
  readonly metaAuthTemplateLanguage: string;
  readonly wixCatalogVersion: string;
  readonly wixEcomVersion: string;
  readonly lambdaPythonRuntime: string;
  readonly rejectedRuntimes: readonly string[];
}

/**
 * Build the JSON mirror.
 *
 * Python cannot import a `.ts` module, and duplicating the version by hand in a Python
 * constant is exactly the drift this file exists to remove. So TS stays canonical and the
 * JSON is generated; `check-versions.ts --write` regenerates it and the plain run fails
 * when it is stale.
 */
export function toJsonMirror(): VendorVersionsJson {
  const [templateName, templateLanguage] = META_AUTH_TEMPLATE.configured.split('/');
  return {
    generatedBy: 'packages/config/vendorVersions.ts via scripts/check-versions.ts --write',
    metaGraphApiVersion: graphApiVersion(),
    metaGraphApiBase: graphApiBase(),
    metaAuthTemplateName: templateName ?? 'wecare_otp',
    metaAuthTemplateLanguage: templateLanguage ?? 'en',
    wixCatalogVersion: WIX_CATALOG.configured,
    wixEcomVersion: WIX_ECOM.configured,
    lambdaPythonRuntime: LAMBDA_PYTHON_RUNTIME.configured,
    rejectedRuntimes: REJECTED_RUNTIMES.map((entry) => entry.id),
  };
}
