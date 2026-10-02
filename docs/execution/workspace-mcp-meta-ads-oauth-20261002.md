# Meta Ads existing-app OAuth retry - 2026-10-02

User requested a new connection attempt through the AWS-backed MCP and a full
sign-in URL to try personally. The version 2 dynamic-client registration retry
failed for Ads, Social and WhatsApp before producing any sign-in URL.

The official Ads authorization-server metadata at
https://mcp.facebook.com/.well-known/oauth-authorization-server/ads advertises
https://www.facebook.com/v26.0/dialog/oauth,
https://graph.facebook.com/v26.0/oauth/access_token, token endpoint auth method
none, S256 PKCE, and ads_mcp_management among supported scopes. Meta's official
2026-07-16 Ads MCP announcement supports an existing app after adding the Ads
MCP use case. That use case was already added to app 2238810740192680.

Policy version 3 changes only Ads to existing-meta-app mode using that app ID.
Social and WhatsApp continue requiring supported MCP client registration.
Saved Ads tokens must bind to the configured OAuth client. No system-user
token fallback or new secret/IAM permission was added. The initial Ads check
performs authenticated MCP initialize, negotiated session handling and tools/list.
It records authenticated, accountReadVerified=false and toolExecutionEnabled=false;
the UI distinguishes that status from a verified account read. No ad tool is
executed. An empty/failed inventory is refused.

63 focused Python passed, 10 focused frontend passed, full frontend 756 passed,
typecheck and production export passed. Bundle SHA256
1320ff4fdf60ada103863bfcbf6614c04057b1c8368c82dcbf3fd904dcc17ef3.
CloudFormation change set workspace-mcp-ads-app-20261002 modified only Function,
Version and Alias; replacement was ReplaceAndRetain. Stack UPDATE_COMPLETE.
Live version 3 Active/Successful, exact CodeSha256 matched the bundle.
Rollback: retained version 2, code artifact
62b28cc8a25d67e09edebdd8877e17fcefb716a1ba62758d87aaaec39b3a02b0.

Live connection_authorize(meta-ads) now succeeded and produced a ten-minute
one-use state/PKCE flow for the configured cloud callback. The user was given
the complete URL to approve personally. The URL/state/verifier/token are not
recorded here. Consent and authenticated tools-list remain unverified until
the owner completes that flow. Staff dashboard and IAM bridge grants are
separate; this URL was generated for the IAM bridge principal.

Fresh native Codex Meta Social app-list succeeded for WECARE.DIGITAL with admin
role. This is a desktop connection, not evidence of a Social cloud grant.
Code jobs remain false; no ad spending, publishing, WhatsApp send, payment or
provider credential rotation took place.
