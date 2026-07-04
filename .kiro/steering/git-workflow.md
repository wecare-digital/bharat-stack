---
inclusion: always
---

# Git workflow — single branch only

This repository uses a **single-branch workflow**. The one and only long-lived
branch is **`stack`** (it is the default branch and `origin/HEAD`).

## Rules

1. **Commit directly to `stack`.** Do NOT create feature/fix/chore branches
   (no `feature/*`, `fix/*`, `chore/*`, etc.) unless the user explicitly asks
   for a branch by name.
2. **Push to `stack`** with `git push origin stack`. Never push to `main`
   (there is no `main` branch) or create new remote branches.
3. **No throwaway branches** for experiments — work on `stack` and rely on
   commits for history. If isolation is truly needed, ask the user first.
4. **Dependabot / bot branches** may appear automatically; delete them once
   their change is merged or superseded, to keep the branch list clean.
5. Keep commit messages descriptive (what + why). Group related changes.

## Rationale

The team deliberately consolidated to one branch to avoid branch sprawl.
Historical branches (`main` with the old SAM deployment, `feature/initial-deployment`,
old `fix/*` and `dependabot/*` branches) were audited and removed. Do not
recreate that sprawl.
