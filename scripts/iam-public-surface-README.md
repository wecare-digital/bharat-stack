# The `public-surface-deploy` role

Two documents and four commands. They create the OIDC role
`GitHubActions-wecare-digital-public-surface`, which is the only thing standing between
`.github/workflows/public-surface-deploy.yml` and a working `Run workflow` button.

- `iam-public-surface-trust.json` — who may assume it
- `iam-public-surface-permissions.json` — what it may then do

## Why a file and not an inline `--policy-document`

A trust policy pasted into a terminal is not reviewable, not diffable, and not something
the next person can check against what is live. Both documents are committed, and
`tests/test_github_oidc_trust_policy.py` asserts the trust file is byte-identical to the
document `scripts/fix_github_oidc_trust.py` enforces — because two copies of one policy is
a thing that drifts, and the drift only shows up as an outage on the next repository
rename.

## Why the subject is a wildcard

Read `scripts/fix_github_oidc_trust.py` before changing the trust document. Short version:
this repository was renamed `bharat-stack` → `wecare-digital` on 2026-09-27 and two deploy
roles went dark for 22 hours with `Not authorized to perform sts:AssumeRoleWithWebIdentity`,
because their trust policies pinned the repository NAME with `StringEquals`. GitHub's
immutable subject format still contains the name segments, and those do not survive a
rename. So the name segments are wildcarded and the two immutable ids are pinned twice —
inside `sub` and again as their own condition keys. The grant is unchanged and strictly
tighter: ids cannot be recycled by a namespace grab, names can.

Pinning the *current* name would be the same bug one rename later. Do not "fix" it.

`aws accessanalyzer validate-policy` will tell you to. It reports
`WILDCARD_USAGE_TOO_PERMISSIVE` on the `sub` condition and asks for six literal characters
before the `*`; there are five, and the only way to add a sixth is to start spelling out
the owner name. The heuristic cannot see that `repository_id` and `repository_owner_id` are
pinned with `StringEquals` right beside the pattern, so the wildcard can only match names
belonging to those two immutable ids. The `MISSING_RESOURCE` error in the same report is
the analyzer applying resource-policy rules to a trust policy, which has no `Resource`
element. The permissions document validates with zero findings.

## The commands

Run from the repository root, with credentials that can write IAM.

```sh
# 0. The OIDC provider should already exist - the other three roles use it. Confirm:
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::775261844268:oidc-provider/token.actions.githubusercontent.com \
  --query 'ClientIDList' --output text

# Only if that 404s (it should not):
# aws iam create-open-id-connect-provider \
#   --url https://token.actions.githubusercontent.com \
#   --client-id-list sts.amazonaws.com

# 1. Create the role with the committed trust document.
aws iam create-role \
  --role-name GitHubActions-wecare-digital-public-surface \
  --assume-role-policy-document file://scripts/iam-public-surface-trust.json \
  --description "Write role for public-surface-deploy.yml: Amplify customRules and the wecare-mcp Lambda. Branch stack only."

# 2. Attach the least-privilege inline policy.
aws iam put-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface \
  --policy-name PublicSurfaceDeploy \
  --policy-document file://scripts/iam-public-surface-permissions.json

# 3. Tell the workflow where the role is.
gh variable set PUBLIC_SURFACE_ROLE_ARN \
  --body arn:aws:iam::775261844268:role/GitHubActions-wecare-digital-public-surface

# 4. Read-only first. This changes nothing and should report the stale MCP catalogue.
gh workflow run public-surface-deploy.yml -f action=verify -f target=both
```

Then, once `verify` has told you what it finds:

```sh
gh workflow run public-surface-deploy.yml -f action=apply -f target=both
```

## If the role already exists

`create-role` fails with `EntityAlreadyExists`. Update in place instead — and prefer the
script, which snapshots the old document to `docs/execution/snapshots/` before writing:

```sh
python scripts/fix_github_oidc_trust.py --status
python scripts/fix_github_oidc_trust.py --apply
```

`fix_github_oidc_trust.py` lists this role, so `--status` reports it as absent until step 1
has run and `--apply` skips it. That is deliberate: a role created later and never
registered there is one that keeps whatever document its creator pasted, and this is the
only one of the five that can write to production.

Being listed is no longer taken on trust. `--status` also compares its list against every
live `GitHubActions-*` role and exits non-zero on one it does not manage, because the list
is a literal and a literal cannot notice a role someone else creates — which is not
theoretical: `GitHubActions-wecare-digital-plivo-drift` was created on 2026-09-28 and sat
unregistered for a day while a test asserted the list was complete.

## Checking it worked

```sh
aws iam get-role --role-name GitHubActions-wecare-digital-public-surface \
  --query 'Role.AssumeRolePolicyDocument'
aws iam get-role-policy --role-name GitHubActions-wecare-digital-public-surface \
  --policy-name PublicSurfaceDeploy --query 'PolicyDocument'
gh variable list
```

## Rollback

```sh
aws iam delete-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface --policy-name PublicSurfaceDeploy
aws iam delete-role --role-name GitHubActions-wecare-digital-public-surface
gh variable delete PUBLIC_SURFACE_ROLE_ARN
```

Deleting the variable alone is enough to disable the workflow: it fails at the
"Check the role variable is set" step with a message naming what to create.

## Where each permission comes from

Every action below is a call one of the two scripts actually makes. Nothing is
speculative, and nothing is `"Resource": "*"`.

| Action | Called by | Why |
| --- | --- | --- |
| `amplify:GetApp`, `amplify:UpdateApp` | both scripts | The `customRules` array holds the 301s and the `/mcp` rewrite. Both scripts write this same list, which is why the workflow runs them sequentially. |
| `lambda:GetFunction`, `GetFunctionConfiguration` | `deploy_mcp_server.py` | Decide create-vs-update, both waiters, and `--verify` downloading the artifact to compare the deployed catalogue. |
| `lambda:CreateFunction` | `deploy_mcp_server.py` | First deploy only. |
| `lambda:UpdateFunctionCode`, `UpdateFunctionConfiguration` | `deploy_mcp_server.py` | Every later deploy. |
| `lambda:PublishVersion`, `CreateAlias`, `UpdateAlias` | `deploy_mcp_server.py` | The API integration points at the `live` alias, so publishing is not optional. |
| `lambda:AddPermission` | `deploy_mcp_server.py` | Lets API Gateway invoke the alias. Re-running is idempotent because the call is wrapped in `except ResourceConflictException` — **not** because anything reads the policy first. `lambda:GetPolicy` was granted on that mistaken account and has been removed; so has `lambda:GetAlias`, which nothing calls either. |
| `iam:PassRole` on `wecare-digital-lambda-role` | `deploy_mcp_server.py` | `create_function` and `update_function_configuration` pass the execution role. Conditioned to `lambda.amazonaws.com` so it cannot be passed anywhere else. |
| `apigateway:GET` on `/apis/zllr9lrg7j*` | `deploy_mcp_server.py` | `get_integrations`, `get_routes` (paginated), `get_stage`. |
| `apigateway:POST`, `PATCH` on `routes*` and `integrations*` | `deploy_mcp_server.py` | `create_integration`, `create_route`, `update_route`. Narrowed to those two sub-resources so the role cannot `PATCH` the API itself. |
| `apigateway:PATCH` on `stages*` | `deploy_mcp_server.py` | `update_stage`, which is how `ANY /mcp` gets its own throttle instead of spending the stage's shared allowance. |
| `apigateway:DELETE` on `stages/*/routesettings/*` | `deploy_mcp_server.py` | `delete_route_settings`. `UpdateStage` validates the whole merged `RouteSettings` map, so one throttle entry left behind by a deleted route makes the map unwritable by anyone — removing it is the only fix. Scoped to route settings alone: the same wildcard the other statements use would have let this role delete every route and the API. |

The `apigateway:` prefix with HTTP verbs is not a shorthand — it is how API Gateway
authorises its control plane for both REST and HTTP APIs. There is no `apigatewayv2:` IAM
prefix, and a policy naming `apigatewayv2:GetRoutes` is rejected as malformed rather than
being tighter.

`tests/test_public_surface_role_permissions.py` derives this list from the boto3 calls in
the two scripts and asserts the document grants exactly that, in both directions. It was
written because this table was checked by hand and the hand-check was wrong twice over:
`apigateway:DELETE` was missing, which would have failed an `apply` run with AccessDenied
*after* the live redirect rules had been rewritten, and two lambda read grants were present
for a reason that did not exist.

## Why `verify` uses the same role

Resolved 2026-09-29. The safe mode carries no write grant, and it does not need a second
role to get there: `verify` assumes the same role with a read-only **inline session
policy**, which STS intersects with the role's own policy. An intersection can only
subtract, so the verify session cannot call `UpdateApp`, `UpdateFunctionCode` or
`UpdateStage` even if a script grows a write call, or someone adds a write step to the
verify path by mistake.

The alternative — a second read-only role — would have forced the verify steps into their
own job to use a different credential, and both scripts write the same Amplify
`customRules` array. Serialising those two writers in one job is worth more than splitting
the credential, and the session policy gives the safe mode its read-only guarantee without
giving that up. The policy is in `.github/workflows/public-surface-deploy.yml` and is
asserted against this document by the test above, so it cannot drift into naming an action
the role does not hold.
