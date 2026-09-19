---
inclusion: always
---

# The plaintext credential source is RETAINED, not a cleanup failure

## Do not delete this file

    ~/aws-new-keys-SAVE-THEN-DELETE.txt

**Status: ✅ AUTHORIZED TEMPORARY PLAINTEXT SOURCE — RETAIN UNTIL PROJECT COMPLETE**

Despite its filename, deletion is **deferred by explicit user decision** until the
entire project reaches PROJECT COMPLETE. It is the temporary local
maintenance/migration source for credential and configuration work.

Do **not** `rm`, `shred`, `truncate`, empty, Trash, or remove it during disk
cleanup, security cleanup, or Kiro log cleanup. **Do not ask about deleting it**
before project close. Earlier instructions requesting its deletion are superseded.

Do not report it as an unresolved cleanup failure. Report two separate numbers:

    AUTHORIZED RETAINED PLAINTEXT SOURCE : 1
    UNEXPECTED PLAINTEXT SECRET COPIES   : <count>

## Four distinct roles — keep these straight in every report

| Role | Location |
|---|---|
| TEMPORARY MAINTENANCE SOURCE | `~/aws-new-keys-SAVE-THEN-DELETE.txt` |
| **APPLICATION RUNTIME SOURCE** | **AWS Secrets Manager** |
| LOCAL DISASTER-RECOVERY BACKUP | `~/.secure-backups/wecare-secrets-backup.txt.enc` |
| CLOUD DISASTER-RECOVERY BACKUP | `s3://wecare-credential-backups-775261844268/credential-backups/current/` (SSE-KMS) |

**No application or Lambda may ever read the TXT file.** Runtime reads come from
Secrets Manager only. The TXT file exists solely on this development Mac.

## Protecting it

Mode `0600`, owned by the current user. Never widen. Never place it in git, Git
LFS, iCloud, Dropbox, OneDrive, Google Drive, a project directory, a Docker image,
a Lambda package, or CI artifacts. **Never upload the plaintext to S3** — only the
encrypted artifact goes there. Never copy it into Kiro permissions or any
maintenance report.

## Never print its contents

`cat` it into chat or a log and you have recreated the original incident. Chat is
persisted into `~/.kiro/logs` and the session transcript. When validating, report
metadata only: provider, credential present YES/NO, field count, fingerprint,
length, Secrets Manager synchronized YES/NO.

Run `python scripts/txt_source_healthcheck.py` — it reports presence, mode, owner,
git/iCloud/project exposure, unexpected duplicate locations, and the
synchronization matrix, without printing a single value.

## If a value must change

No provider rotation is authorized right now, so synchronization should **verify,
not replace**. When an authorized change does happen, update every location or
none:

    secure input → TXT source → Secrets Manager → consumers → build/test
      → deploy → live validation → encrypted local backup → encrypted S3 backup
      → checksum verification

Edit it only with a script that parses in memory, takes input hidden, writes
atomically, preserves `0600`, prints nothing, and leaves no `.bak`/`.swp`/`.tmp`
credential-bearing remnant. Never `echo "KEY=value" >> file`.

## Duplicate cleanup still applies

Redundant plaintext copies elsewhere — stale Kiro logs, obsolete permission
backups, shell-history literals, editor swap files, temp migration files — may be
cleaned after verification. The retained source is exempt.

Secret scanners must keep detecting these fingerprints; do **not** globally
allowlist them. Distinguish *expected location* from *unexpected location*, so a
leak into source, git, Kiro permissions, a Lambda package or a log is still caught.

## Project close

`docs/CREDENTIAL-ROTATION-RUNBOOK.md` holds the PROJECT COMPLETE checklist. Only
once every applicable item is satisfied, present `FINAL PLAINTEXT SOURCE
RETIREMENT [PROJECT-CLOSE-001]` with every field evidenced, and wait for an
explicit `YES PROJECT-CLOSE-001`. Do not delete on any weaker signal.

## Gap wording

**P0 — HISTORICALLY EXPOSED ACTIVE CREDENTIALS**

- ✅ Secrets centralized · ✅ Applications use Secrets Manager
- ✅ Encrypted local backup · ✅ Encrypted S3 backup
- ✅ Main TXT maintenance source intentionally retained
- ⏳ Provider rotation deferred by user
- ⏳ Final TXT retirement deferred until project completion

Intentional retention is **not** a failed task.
