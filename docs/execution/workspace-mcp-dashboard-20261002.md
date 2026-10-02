# Dashboard MCP connections

Owner asked to add a connection option inside the dashboard, support multiple MCP
connections, build and push. Added /workspace/dashboard/mcp-connections/ with a
dashboard overview link and Platform settings/command palette entry. The page uses
the existing staff Layout and noindex metadata, responsive cards, lime status/error
notices and shared buttons.

The existing protected /api/workspace/mcp endpoint receives current staff access
tokens through authFetch. Only the Admin group is offered controls; Operators are
excluded even though the general app role helper also labels them internal admins.
The deployed backend remains the authorization authority and rechecks access.

The eleven-provider registry supplies each card. Meta Social and WhatsApp have
independent Connect and Verify controls. OAuth links are held only in React state,
expire after at most ten minutes, and must match the approved Meta host, app,
callback and PKCE method before being offered in a new tab. Sign-in completes in
that tab; the administrator returns and selects Verify. AWS and GitHub have account
checks. Multiple supported providers can be selected and checked in one action;
one failure does not stop later providers. The activity panel renders text, never
provider HTML or scripts. Pending adapters and documentation-only providers are
labelled clearly and have no misleading Connect controls.

No arbitrary endpoint registration, model inference, credential input, provider
writes or code-job dispatch was added. Desktop and staff-browser authorizations
remain independent. Meta cloud consent is still required; building the page does
not authenticate those providers. The existing callback must be registered for the
Meta app before completing its browser flow.

Validation: seven new focused transport/role/UI tests passed; typecheck passed;
705 frontend tests passed. Production build passed and exported the new page.
The public-page manifest remains at 24 pages, excluding this staff page, and the
export credential gate passed across 3451 text files. No staff sign-in was performed by the
agent, so real browser Admin consent remains a human-session verification step.

Rollback: normal revert of this frontend-only commit. Existing MCP backend, provider
credentials, customer pages and other sessions' working files remain untouched.
