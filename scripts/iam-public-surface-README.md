# The `public-surface-deploy` roles

Three documents and six commands. They create the two OIDC roles that
`.github/workflows/public-surface-deploy.yml` needs, which are the only thing standing
between it and a working `Run workflow` button.

| Role | Document | Used by |
| --- | --- | --- |
| `GitHubActions-wecare-digital-public-surface` | `iam-public-surface-permissions.json` | the `apply` job, and nothing else |
| `GitHubActions-wecare-digital-public-surface-read` | `iam-public-surface-read-permissions.json` | the `verify` and `confirm` jobs |

Both share one trust document, `iam-public-surface-trust.json` — the difference between them
is entirely in what they may do once assumed, not in who may assume them.

## Why two roles

The first version ran everything on one role that could write, because one job was simpler
than three. The cost is that a read-only check carried `amplify:UpdateApp`,
`lambda:UpdateFunctionCode` and `iam:PassRole` for its whole duration — so a mistake in a
verify path, or anything compromised between checkout and the verify command, held
production write access it never needed.

The split also buys something better than least privilege: `confirm` runs **after** the
apply, on the read role. A deploy that verifies itself with its own write credential is
checking its work with the same hand that did it; confirming on a principal that could not
have produced the result makes the evidence worth something.
`tests/test_github_oidc_trust_policy.py` asserts the read document contains nothing but
`Get` actions, so "read-only" is a property rather than a filename.

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

# 1. The write role.
aws iam create-role \
  --role-name GitHubActions-wecare-digital-public-surface \
  --assume-role-policy-document file://scripts/iam-public-surface-trust.json \
  --description "Write role for public-surface-deploy.yml: Amplify customRules and the wecare-mcp Lambda. Branch stack only."

aws iam put-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface \
  --policy-name PublicSurfaceDeploy \
  --policy-document file://scripts/iam-public-surface-permissions.json

# 2. The read-only role. Same trust document, Get-only permissions.
aws iam create-role \
  --role-name GitHubActions-wecare-digital-public-surface-read \
  --assume-role-policy-document file://scripts/iam-public-surface-trust.json \
  --description "Read-only role for public-surface-deploy.yml's verify and confirm jobs. Branch stack only."

aws iam put-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface-read \
  --policy-name PublicSurfaceRead \
  --policy-document file://scripts/iam-public-surface-read-permissions.json

# 3. Tell the workflow where both roles are.
gh variable set PUBLIC_SURFACE_ROLE_ARN \
  --body arn:aws:iam::775261844268:role/GitHubActions-wecare-digital-public-surface
gh variable set PUBLIC_SURFACE_READ_ROLE_ARN \
  --body arn:aws:iam::775261844268:role/GitHubActions-wecare-digital-public-surface-read

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
for role in GitHubActions-wecare-digital-public-surface \
            GitHubActions-wecare-digital-public-surface-read; do
  echo "== $role"
  aws iam get-role --role-name "$role" --query 'Role.AssumeRolePolicyDocument'
  aws iam list-role-policies --role-name "$role" --query 'PolicyNames'
done
gh variable list
```

## Rollback

```sh
aws iam delete-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface --policy-name PublicSurfaceDeploy
aws iam delete-role --role-name GitHubActions-wecare-digital-public-surface
aws iam delete-role-policy \
  --role-name GitHubActions-wecare-digital-public-surface-read --policy-name PublicSurfaceRead
aws iam delete-role --role-name GitHubActions-wecare-digital-public-surface-read
gh variable delete PUBLIC_SURFACE_ROLE_ARN
gh variable delete PUBLIC_SURFACE_READ_ROLE_ARN
```

Deleting the variables alone is enough to disable the workflow: each job fails at its
"Check the … role variable is set" step with a message pointing back at this file.

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

### The read-only document

`iam-public-surface-read-permissions.json` is what the `verify` and `confirm` jobs get, and
it is three statements:

| Action | Why |
| --- | --- |
| `amplify:GetApp` | Read the current `customRules` to report which retired URLs are wired and which are missing. |
| `lambda:GetFunctionConfiguration` | State, memory and timeout of the `live` alias. |
| `lambda:GetFunction` | **This is the one that is easy to leave out.** The stale-catalogue check downloads the deployed bundle and compares its page list against `config/public-pages.json`. `GetFunctionConfiguration` alone cannot see the code, so without `GetFunction` the check that exists to catch a stale `/orders` entry silently cannot run. |
| `apigateway:GET` | `get_routes` and `get_stage`, for the `/mcp` route and its throttle. |

No `PassRole`, no `POST`, no `PATCH`, no `Update*`. The retired-URL probes in
`provision_legacy_redirects.py --verify` are plain HTTPS requests and need no AWS grant at
all.
