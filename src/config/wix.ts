/**
 * Wix Headless — non-secret identifiers only.
 *
 * WIX IS THE COMMERCE BACKEND, HEADLESS. The owner has confirmed the architecture: the old
 * Wix *site* is retired and this repo owns every page, but Wix stays as a headless service
 * for catalog, inventory, cart and orders, reached over its REST APIs. There is no Wix
 * Editor or Velo runtime in this project - that CLI/Velo project is already deleted.
 *
 * NOTHING SECRET IS IN THIS FILE, and nothing secret may be added to it. The API key is a
 * bearer credential: anything holding it can read and write this account's commerce data.
 * It lives in AWS Secrets Manager and reaches the runtime through the environment. See
 * docs/wix-headless.md for the exact commands and the rotation note.
 *
 * The values below are safe to commit for the same reason a GA4 measurement ID is: they
 * identify which account and site to talk to, and grant nothing on their own.
 *
 * HOW THESE WERE OBTAINED, so they can be re-derived rather than trusted:
 *   - ACCOUNT_ID came out of the API key itself. A Wix API key is an "IST."-prefixed JWT
 *     whose payload carries { tenant: { type: "account", id } }. Decoding the payload is
 *     base64, needs no network and no secret handling, and is why the account ID did not
 *     have to be looked up anywhere. The owner has since confirmed the same value
 *     independently, so two sources agree on it.
 *   - SITE_ID was supplied directly by the owner as the "Headless Site ID". See the note on
 *     the constant below for why the value it replaced is not simply an older spelling of
 *     the same thing.
 */

/** Wix account that owns the site and the API key. */
export const WIX_ACCOUNT_ID = '15f02319-40ff-4288-b8e6-69c791adae5e';

/**
 * The headless site this repo talks to, supplied by the owner.
 *
 * THIS REPLACED A DIFFERENT SITE, NOT A TYPO OF THIS ONE. The previous value was
 * c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5, and the comment above used to justify it like this:
 * it came from POST /site-list/v2/sites/query, which returned exactly one site, and it
 * matched the siteId in the since-deleted store/wix.config.json. Those two sources did
 * agree - but they agreed about the OLD Wix site, the editor site that has been retired.
 * That is precisely the site this project no longer uses, so a confident derivation pointed
 * at the wrong place. Worth remembering: "two independent sources agree" establishes that a
 * value is real, not that it is the one you want.
 *
 * NOT INDEPENDENTLY VERIFIED HERE. Confirming it would mean calling the Wix API with the
 * admin key, and that key is a bearer credential held in Secrets Manager - it is not
 * something to pull into a sandbox to check an id. So this is taken on the owner's word.
 * To verify it yourself, from an environment that legitimately holds the key:
 *
 *   curl -X POST https://www.wixapis.com/site-list/v2/sites/query \
 *     -H "Authorization: $WIX_API_KEY" \
 *     -H "wix-account-id: 15f02319-40ff-4288-b8e6-69c791adae5e" \
 *     -H 'Content-Type: application/json' -d '{}'
 *
 * and check this id appears with the expected display name.
 *
 * IT IS SENT ON EVERY ADMIN CALL by wixAdminHeaders() below, so if it is wrong, catalog,
 * inventory, cart and order calls all address the wrong site rather than failing loudly.
 */
export const WIX_SITE_ID = 'fcd82f0c-9572-49c7-acfb-88fb05042ece';

/**
 * OAuth app / client id for Wix Headless visitor sessions.
 *
 * This is the PUBLIC half of the headless client and is designed to ship in a browser
 * bundle - it is what identifies the app when minting a visitor token. It is not the API
 * key and confers no admin access.
 */
export const WIX_CLIENT_ID = '197cd718-e4ec-4e2e-b380-46c297eb18a2';

/**
 * The application identity the API key acts as, from the key's own payload. Recorded for
 * audit - useful when reading Wix activity logs - and not used to authenticate.
 */
export const WIX_APP_ID = '35d5f45b-ccc3-433b-886e-ca73a9379935';

/** Base URL for every Wix REST call. */
export const WIX_API_BASE = 'https://www.wixapis.com';

/**
 * Secrets Manager name the API key is stored under. Referenced by name so the Lambda that
 * needs it and the documentation cannot drift apart.
 */
export const WIX_API_KEY_SECRET = 'wecare/wix/headless-api-key';

/** Environment variable the key is read from at runtime. Never a literal. */
export const WIX_API_KEY_ENV = 'WIX_API_KEY';

/**
 * Headers every authenticated Wix admin call needs.
 *
 * Takes the key as an argument rather than reading it here, so this module stays free of
 * credential handling and can be imported from client-side code without dragging a secret
 * into the bundle.
 */
export const wixAdminHeaders = ( apiKey: string ): Record<string, string> => ( {
  Authorization: apiKey,
  'wix-account-id': WIX_ACCOUNT_ID,
  'wix-site-id': WIX_SITE_ID,
  'Content-Type': 'application/json',
} );
