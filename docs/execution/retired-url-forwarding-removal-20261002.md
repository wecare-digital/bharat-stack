# Retired URL forwarding removal - 2026-10-02

Owner explicitly requested removal of forwarding for the 32 former staff/content paths listed in chat, following the /access complaint.

## Sources and resulting behavior

- Live Amplify app `d22dm4b0jn71jw`, Hosting > Rewrites and redirects: removed `/access`, `/access/`, `/access/<*>` 302 rules. Fresh configuration went from 12 rules to nine. Only www host canonicalisation remains an explicit Amplify redirect; internal API/media/MCP rewrites and the missing-page catch-all are retained unchanged.
- `scripts/provision_legacy_redirects.py`: desired configuration no longer recreates access redirects.
- `src/pages/404.tsx`: retired path prefixes stay on the unavailable page instead of calling `router.replace('/')`. Matching includes bare, slash and descendant forms, ignores case, and decodes encoded paths. Unknown paths outside this list retain the owner's home fallback. The CDN retains its real HTTP 404.
- `scripts/probe_url_host_matrix.py`: lists retired URLs as audit expectations, not runtime redirects. Access expectations now require 404.
- Current public pages, including `/get/`, `/vault/`, `/cart/`, and customer sign-in, and staff routes under `/workspace/` are retained. No DNS, subdomain fallback, or certificate changes.

## Validation

53 frontend tests passed, including real component navigation tests for all retired prefixes, descendants, case/encoding, and the remaining unknown-path fallback. Four Python configuration/snapshot tests passed. Full production build passed, including TypeScript and static export.

Live Amplify configuration was read immediately before the update, compared with the saved array, then only the three access rules were removed. Pre-change evidence: `snapshots/retired-url-rules-before-20261002.json`.

Frontend deployment and post-deploy browser verification are recorded in the completion section when finished.

## Recovery evidence

Revert the scoped source commit and deploy only if owner requests recovery. Saved pre-change rules are evidence, not authorization to restore the removed redirects. Restoring DNS or certificates is outside this change.
