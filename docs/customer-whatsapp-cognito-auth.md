# Customer Cognito authentication over WhatsApp

## Decision

Create a **separate customer Cognito user pool**. Do not modify the existing
WECARE.DIGITAL admin pool `us-east-1_cSx0RHCIR`.

The customer pool uses Cognito `CUSTOM_AUTH` with a six-digit challenge sent
through the existing production WhatsApp Business API Lambda. Cognito owns the
authentication session and token issuance; the challenge Lambda owns OTP
generation, expiry and comparison.

## Verified production Meta mapping

Verified against the live Meta-facing backend on 2026-09-23:

| Item | Value |
|---|---|
| Customer WABA | `2094615664435155` |
| WABA name | `WECARE.DIGITAL` |
| WhatsApp sender | `+91 93309 94400` |
| Meta phone-number ID | `1016149501586345` |
| OTP template | `wecare_otp` |
| Template ID | `1292079089453029` |
| Category | `AUTHENTICATION` |
| Status | `APPROVED` |
| Language | `en` |

A second WABA also has an approved template named `wecare_otp`; do not infer
the sender from the template name. Customer authentication for this tenant is
pinned to the WABA and phone-number ID above.

No new Meta template is required.

## Delivery path

```text
customer app
  -> Cognito InitiateAuth(CUSTOM_AUTH)
  -> DefineAuthChallenge
  -> CreateAuthChallenge
  -> wecare-customer-whatsapp-auth:live
  -> wecare-whatsapp-business-api:live
  -> Meta Graph API / wecare_otp
  -> customer WhatsApp
  -> RespondToAuthChallenge(CUSTOM_CHALLENGE)
  -> VerifyAuthChallengeResponse
  -> Cognito tokens
```

The challenge Lambda invokes `wecare-whatsapp-business-api:live` directly.
It does not use `wecare-outbound-whatsapp`, because that path performs normal
CRM/message side effects that authentication traffic does not need.

## Security properties

- Public self-sign-up is disabled. Customer users are created administratively.
- `PreventUserExistenceErrors=ENABLED` on the app client.
- Unknown-user challenge events do not send WhatsApp messages.
- OTPs are six digits, expire after 10 minutes, and allow at most three attempts.
- OTP comparison uses `secrets.compare_digest`.
- OTPs and complete phone numbers are never logged.
- The user's `custom:partner_waba_id` must equal `2094615664435155` before
  any OTP is sent. This is the cross-WABA isolation gate.
- The auth Lambda has no Meta token. Its IAM role can invoke only the existing
  WhatsApp sender Lambda and write its own CloudWatch logs.
- Cognito points to the auth Lambda's `live` alias so normal version/alias
  rollback practices continue to apply.

## Provision

Use the repo-supported authenticated deployment environment.

```bash
python scripts/provision_customer_whatsapp_auth.py --dry-run
python scripts/provision_customer_whatsapp_auth.py
python scripts/provision_customer_whatsapp_auth.py --verify
```

The provisioner creates:

- IAM role `wecare-customer-whatsapp-auth-role`
- Lambda `wecare-customer-whatsapp-auth`
- Lambda `live` alias
- 30-day CloudWatch log retention
- Cognito pool `WECARE.DIGITAL-CUSTOMERS`
- public app client `wecare-customer-whatsapp-otp`
- Cognito group `Partner`
- the three Cognito custom-challenge triggers
- a scoped Cognito-to-Lambda invoke permission

The existing admin pool is read back during `--verify` and is expected to
remain without these custom-auth triggers.

## Subsequent Lambda code deployments

Once the function exists, use the fleet's normal deployment path:

```bash
python scripts/deploy_all_lambdas.py --dry-run wecare-customer-whatsapp-auth
python scripts/deploy_all_lambdas.py wecare-customer-whatsapp-auth
```

The deploy script publishes a version and moves `live`; Cognito continues to
invoke the alias rather than `$LATEST`.

## Create a customer user

Do not use the WhatsApp **sender** number as the customer's login identity
unless that is explicitly the customer's own login number.

For each customer login, provision an E.164 phone number, set
`phone_number_verified=true`, set
`custom:partner_waba_id=2513394156072604`, confirm the user, and add it to the
`Partner` group. Keep user provisioning administrative; do not expose
`SignUp` for this pool.

The current branch intentionally does not create a customer user because the
customer's login/recipient phone number was not supplied with the implementation
request.

## Client integration

The existing admin frontend still points to the admin Cognito pool and should
stay that way. A customer login surface must initialize Cognito against the
new customer pool/app-client IDs and perform:

1. `InitiateAuth(AuthFlow=CUSTOM_AUTH)` with the customer's phone-number
   username.
2. Receive `CUSTOM_CHALLENGE`.
3. Ask for the WhatsApp code.
4. `RespondToAuthChallenge(ChallengeName=CUSTOM_CHALLENGE)` with
   `ANSWER=<otp>` and the returned session.
5. Use the resulting Cognito tokens.

Before exposing customer tokens to existing protected APIs, update those API
authorizers/middleware to trust the customer pool as a separate issuer. Do not
replace the admin pool issuer globally.
