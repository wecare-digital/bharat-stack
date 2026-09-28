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
only one of the four that can write to production.

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
| `lambda:GetFunction`, `GetFunctionConfiguration` | `deploy_mcp_server.py` | Decide create-vs-update, and the `function_active_v2` waiter. |
| `lambda:CreateFunction` | `deploy_mcp_server.py` | First deploy only. |
| `lambda:UpdateFunctionCode`, `UpdateFunctionConfiguration` | `deploy_mcp_server.py` | Every later deploy. |
| `lambda:PublishVersion`, `CreateAlias`, `UpdateAlias`, `GetAlias` | `deploy_mcp_server.py` | The API integration points at the `live` alias, so publishing is not optional. |
| `lambda:AddPermission`, `GetPolicy` | `deploy_mcp_server.py` | Lets API Gateway invoke the alias. `GetPolicy` is what makes re-running idempotent instead of erroring on a duplicate statement id. |
| `iam:PassRole` on `wecare-digital-lambda-role` | `deploy_mcp_server.py` | `create_function` and `update_function_configuration` pass the execution role. Conditioned to `lambda.amazonaws.com` so it cannot be passed anywhere else. |
| `apigateway:GET` | `deploy_mcp_server.py` | `get_integrations`, `get_routes`. |
| `apigateway:POST`, `PATCH` | `deploy_mcp_server.py` | `create_integration`, `create_route`, `update_route`. |

`verify` needs only `amplify:GetApp`, the `lambda:Get*` pair and `apigateway:GET`. If you
would rather the safe mode carry no write grant at all, make a second read-only role and
point a separate variable at it — the workflow's verify steps would need splitting into
their own job to use it.
