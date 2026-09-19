# Credential rotation runbook — 2026-09-19 leak

Four live credentials were found in cleartext in Kiro's workspace permissions
file. This is the rotation procedure, ordered by blast radius.

**Contains no secret values.** Only names, locations, and consumers.

## Why rotation is mandatory, not optional

The values were written to disk in cleartext in **6 files, 141 occurrences**,
including an IDE log (99) and a session transcript (10). Scrubbing files without
rotating achieves nothing: treat every value as compromised.

Verified clean, so no history rewrite is required:

- **git history** — all 19,128 objects across every ref: **0 occurrences**
- **shell history** — `.zsh_history`, `.bash_history`: **0 occurrences**
- **repo working tree** — **0 occurrences**

## Order of work

Rotate **Razorpay first**. It is the only credential that can move money, and it
is a `rzp_live_` pair, not test.

---

### 1. Razorpay — LIVE API key id + secret · CRITICAL

| | |
|---|---|
| Secrets Manager | `wecare/razorpay-webhook` → fields `key_id`, `key_secret` |
| Read by | `wecare-partner-onboarding` (`_razorpay_creds()`, handler.py:542) |
| Used for | self-service wallet top-up — creates payment links |
| Also in that secret | `webhook_secret`, read by `wecare-razorpay-webhook` for signature verification |

**Do not rotate `webhook_secret` at the same time** unless you also update the
endpoint config in the Razorpay dashboard — that would break inbound payment
webhooks, which is the authoritative payment path.

1. Razorpay Dashboard → Account & Settings → API Keys → **Regenerate Live Key**.
   Capture the new id and secret once; Razorpay shows the secret a single time.
2. Update **only** `key_id` and `key_secret` in `wecare/razorpay-webhook`,
   preserving `webhook_secret`. Use the console or `asm-exec`; do not echo values.
3. Verify: `POST /partner/topup` should stop returning
   `501 Razorpay API keys not configured` and create a live payment link.
4. Revoke the old key in the dashboard **after** step 3 passes.

Failure mode if skipped: top-up returns 501. Payment *capture* keeps working,
because that path uses `webhook_secret`, not the API pair.

---

### 2. Google API key · HIGH

| | |
|---|---|
| Secrets Manager | `wecare/google-maps` → field `api_key` |
| Read by | `wecare-whatsapp-templates` (Google Maps Places proxy, handler.py:113-124) |
| Used for | location-template address lookup; cached in `_gmaps_key_cache` |

1. Google Cloud Console → APIs & Services → Credentials → create a **new** API
   key, restricted to the Places API and to your server IPs/referrers.
2. Update `api_key` in `wecare/google-maps`.
3. The Lambda caches the key in module scope, so **publish a new version and move
   the `live` alias** or the old key stays in the SnapStart snapshot:
   `python scripts/deploy_all_lambdas.py wecare-whatsapp-templates`
4. Verify a location template resolves an address, then delete the old key.

Note: this key was also the `ORIGINAL_KEY`/`CANONICAL_GOOGLE_KEY` in the leaked
command strings, so confirm whether anything outside this repo uses it before
deleting.

---

### 3. OpenAI service-account key · HIGH, zero production risk

| | |
|---|---|
| Secrets Manager | **none — no entry exists** |
| Read by | **no Lambda.** Verified: no `OPENAI_API_KEY` / `openai.` reference anywhere under `amplify/functions/` |
| Used for | ad-hoc local scripts only (`OPENAI_ADS_KEY=... python3`) |

This is exactly why it leaked: with no Secrets Manager home, it was passed inline.

1. platform.openai.com → Settings → API keys → revoke the service-account key.
2. Create a replacement **only if something still needs it**.
3. If it is needed, give it a proper home rather than an inline env var: create
   `wecare/openai-ads` and read it by name.

Nothing in production breaks. Revoke freely.

---

### 4. Plivo auth id + token · HIGH, zero production risk

| | |
|---|---|
| Secrets Manager | **none — no entry exists** |
| Read by | **no Lambda.** `wecare-plivo-answer` only reads `PLIVO_ANSWER_TOKEN` (an unrelated shared token for its answer URL) and returns static XML |
| Used for | ad-hoc local provisioning/testing calls |

1. Plivo Console → Account → Keys & Credentials → rotate the auth token.
2. Create `wecare/plivo-api` if ongoing programmatic use is needed.

Note: `PLIVO_ANSWER_TOKEN` on `wecare-plivo-answer` is a **different** secret and
was not leaked. Leave it alone.

---

## After rotating

1. Install the hardened permissions file (removes the six credential-bearing
   allow-patterns). Kiro hard-denies agent writes to this path, so run it yourself:
   ```
   cp ~/.local/share/kiro-maintenance-backup/20260919-063734/STAGED-workspace-permissions.yaml \
      ~/.kiro/workspace-roots/df7bb16a63efe7f7/permissions.yaml
   ```
2. Restart Kiro. The two logs holding the values belong to the **running** IDE
   session (`~/.kiro/logs/20260918T060951815/kiro.log`,
   `~/Library/Application Support/Kiro/logs/20260918T113948/.../Kiro Logs.log`)
   and rotate on restart. They were deliberately not truncated while live.
3. Handle `~/aws-new-keys-SAVE-THEN-DELETE.txt` — it holds **5 occurrences of the
   above credentials in addition to AWS keys**, so it is a broader dump than its
   name suggests. Move to a password manager, then delete.
4. The session transcript
   `~/.kiro/sessions/df7bb16a63efe7f7/sess_2100c42e-.../messages.jsonl` also
   contains occurrences. It is your conversation history, so it was left
   intact — delete that session if you want the footprint gone.
5. Confirm the guard is active: `python scripts/verify_secret_hook.py` → 18/18.

## Current footprint

Re-measure any time with `python scripts/audit_leak_footprint.py` (prints paths
and counts only, never values). As of 2026-09-19 after remediation:

| Occurrences | Location | Disposition |
|---|---|---|
| 102 | `~/Library/Application Support/Kiro/logs/20260918T113948/.../Kiro Logs.log` | live IDE log — rotates on restart |
| 12 | `~/.kiro/sessions/df7bb16a63efe7f7/sess_2100c42e-.../messages.jsonl` | your conversation history — left intact by choice |
| 9 | `~/.kiro/workspace-roots/df7bb16a63efe7f7/permissions.yaml` | replace with the staged file (step 1) |
| 9 | `~/.kiro/logs/20260918T060951815/kiro.log` | live IDE log — rotates on restart |
| 5 | `~/aws-new-keys-SAVE-THEN-DELETE.txt` | delete after saving (step 3) |
| 2 | `~/Library/Application Support/Kiro/User/globalStorage/state.vscdb` | Kiro's global storage SQLite DB; clears as the IDE ages out old state |
| **139** | **total** | |

Already clean and verified: git history (all objects, every ref), shell history,
the repo working tree, and the maintenance snapshot backup (redacted in place —
values replaced with `<REDACTED:prefix…suffix:len>` fingerprints so the record of
*what* leaked survives without the values).

**None of this matters once the four credentials are rotated.** Rotation is the
fix; file cleanup is hygiene.

---

## DEFERRED — decision recorded 2026-09-19

Rotation is deliberately deferred until the current project milestone completes.
Recorded here so the deferral is a decision with a trigger, not an omission.

**Trigger: rotate at project completion, Razorpay first.**

### What makes the deferral defensible

Exposure was measured as **local disk only**:

- **Time Machine: no destination configured.** No backups exist, so no copy has
  propagated off-machine.
- **iCloud Drive is active**, but every affected path (`$HOME` root, `~/.kiro`,
  `~/Library`) is outside the synced set. Desktop and Documents are empty.
- **git history, shell history and the repo working tree are clean** — verified
  across all objects and every ref, so nothing reached GitHub.

The material risk is therefore: anyone with read access to this machine's disk,
or any future process that ships these logs somewhere.

### Compensating controls to apply while deferring

These reduce risk without rotating anything:

1. **Restart Kiro.** 111 of the 139 occurrences live in two logs owned by the
   running IDE session. A restart rotates them and drops the footprint to ~28.
2. **Install the hardened permissions file** (step 1 above). Worth doing
   independently of rotation: it also removes the blanket `aws *`, `rm *`,
   `dd *`, `chmod *`, `kill *`, `bash *`, `eval *` allow-patterns.
3. **Restrict rather than rotate the Google key.** In GCP → Credentials, scope
   it to the Places API and to server IPs/referrers. A restricted leaked key is
   far less useful to anyone holding it, and restriction causes no downtime.
4. **Delete `~/aws-new-keys-SAVE-THEN-DELETE.txt`** once saved to a password
   manager. 5 occurrences, and it is a broader dump than its name implies.
5. **Switch from prevention to detection for Razorpay.** This is the one
   credential that can move money. Enable payment/settlement alerts and review
   recent activity for links or orders you did not create. If anything
   unexplained appears, rotate immediately and ignore this deferral.
6. **Do not add a Time Machine destination or move these paths into iCloud**
   until after rotation. Doing so would convert a local-only exposure into a
   replicated one.

### Still safe to revoke right now, at zero production risk

`OpenAI` and `Plivo` are consumed by **no Lambda** (verified: no
`OPENAI_API_KEY`, `openai.`, or `PLIVO_AUTH` reference under
`amplify/functions/`). Revoking them cannot break the project, so they need not
wait for the milestone. Only Razorpay and Google have production consumers.

### Re-check before rotating

```
python scripts/audit_leak_footprint.py    # where the values still are
python scripts/verify_secret_hook.py      # guard still active (18/18)
```

## Preventing recurrence

`.kiro/hooks/block-inline-secrets.json` now blocks inline credentials before the
command runs. See `.kiro/steering/secret-handling.md`.

Root cause worth fixing beyond rotation: **two of the four credentials had no
Secrets Manager entry at all.** Until every credential has a home to be
referenced from, inline passing stays the path of least resistance.
