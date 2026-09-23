"""Contact identity: Google People sync, Truecaller verification, field provenance.

Measured before building, 2026-09-23
------------------------------------
Both credentials already exist in Secrets Manager and **nothing reads either of them**:

    wecare/seo/google-oauth   client_id, client_secret     created 2026-04-18
    wecare/truecaller         app_key, app_name,
                              app_domain, callback_url     created 2026-09-19

`scripts/store_provider_secret.py` records the intent for both. For Google it says
outright: "Reuse this client for People API contact sync rather than minting a second
one." For Truecaller it says the consumer is "POST /auth/truecaller/callback - NOT BUILT
YET, so nothing reads this until that Lambda and route exist".

A grep for `people.googleapis`, `truecaller`, `pkce` and `code_verifier` across
`amplify/`, `src/` and `scripts/` finds no OAuth flow of any kind. So this is greenfield,
and no redirect URI has ever been exercised.

Shape
-----
    provenance.py      which source may overwrite which Contact field
    oauth_pkce.py      PKCE, state, and the token lifecycle
    google_people.py   sync-token lifecycle and person -> Contact mapping
    truecaller.py      nonce issue/claim and the signed-assertion contract

Every module here is pure or store-backed; none performs network I/O. The HTTP calls
belong in the Lambda so that the decisions stay testable without credentials, which
matters because the live consent steps are owner-gated (see below).

The two security properties that drive the design
-------------------------------------------------
**1. Truecaller's callback tells us where to fetch the profile.** The body is

    {"requestId": "...", "accessToken": "...",
     "endpoint": "https://profile4-noneu.truecaller.com/v1/default"}

and that endpoint is attacker-controlled input. A forged callback could point it at any
host, which would then return any phone number, and we would record it as *verified*. That
is a complete authentication bypass dressed as a feature, and it is also an SSRF into
whatever the Lambda can reach. `truecaller.resolve_profile_endpoint` allowlists the host.

**2. Nothing may ask Truecaller who owns an arbitrary number.** The brief requires
consent-based verification of the *current user* only, with no bulk lookup. The structural
guarantee is that a profile fetch is reachable only with an access token Truecaller minted
for a nonce **we** issued, and the nonce is bound to the session that asked for it - so it
cannot verify a third party's number either.

What is owner-gated
-------------------
Neither provider can be exercised end to end from here:

* Google: the OAuth client needs `https://api.wecare.digital/auth/google/callback`
  registered as an authorised redirect URI, and `contacts.readonly` added to the consent
  screen. Both are Google Cloud console actions.
* Truecaller: `callback_url` in the secret must match a callback registered on
  developer.truecaller.com, and the deep link only resolves on a device with the Truecaller
  app installed.

So the contracts, the state machines and the guards are built and tested here against
fixtures, and the live grant is recorded as `WAITING_FOR_OWNER` with the exact action.
"""
