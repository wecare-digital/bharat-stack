---
inclusion: always
---

# Lambda SnapStart + deploy model

All ~49 Python functions behind the main HTTP API (`zllr9lrg7j`) use **Lambda
SnapStart** to cut cold-start latency. This changes how deploys must work.

## Key facts

- Runtime: python3.12, `SnapStart.ApplyOn = PublishedVersions`.
- The API integrations invoke the **`live` alias** (e.g.
  `...:function:wecare-contacts:live`), **not** `$LATEST`.
- SnapStart only accelerates **published versions**, and the snapshot is taken
  at publish time — so `$LATEST` changes do NOT reach the API until a new
  version is published and the `live` alias is moved to it.

## Deploy rule (must follow)

After changing a function's code you MUST:
1. `aws lambda update-function-code ...` (updates `$LATEST`), then
2. publish a new version, wait for `State=Active`, and move the `live` alias.

Step 2 is automated by `scripts/snapstart_publish.py`:
```
python scripts/snapstart_publish.py                 # all SnapStart functions
python scripts/snapstart_publish.py wecare-contacts # specific ones
```
The deploy scripts (`_deploy_all.ps1`, `_deploy_changed.ps1`,
`_deploy_meta_agent.ps1`) already call it at the end. If you deploy a function
by hand, run the publisher yourself or the API will keep serving old code.

## Gotchas

- **Randomness:** SnapStart snapshots the `random` module's PRNG state. Use
  `secrets` / `os.urandom` for anything that must be unique per call (e.g.
  url-shortener short codes) — never `random` for uniqueness.
- **Init-time secrets:** fetch secrets lazily (on first request), not at import,
  or a rotated secret will be frozen in the snapshot until republished.
- **Cost:** SnapStart for Python bills for snapshot cache + restore. It's modest
  at this fleet size but not zero.
- SnapStart is incompatible with provisioned concurrency.
