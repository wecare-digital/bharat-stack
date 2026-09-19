---
inclusion: always
---

# Never put a credential on a command line

## What happened, so the rule makes sense

On 2026-09-19 an audit found **four live credentials in plaintext inside Kiro's
own workspace permissions file**, `~/.kiro/workspace-roots/<hash>/permissions.yaml`:

| Credential | Consumed by | Rotated |
|---|---|---|
| Razorpay **LIVE** key id + secret | `wecare-partner-onboarding` via `wecare/razorpay-webhook` | see runbook |
| Google API key | `wecare-whatsapp-templates` via `wecare/google-maps` | see runbook |
| OpenAI service-account key | **nothing** - ad-hoc local use only | see runbook |
| Plivo auth id + token | **nothing** - ad-hoc local use only | see runbook |

Nobody pasted them into a config. They arrived because commands were run with
the credential inline:

```
RZP_ID='rzp_live_...' RZP_SECRET='...' python3 -c '...'
```

When that was approved with **"Always allow"**, Kiro recorded the *entire
command string* as a shell allow-pattern. The secret became a permission rule,
on disk, in cleartext, permanently.

Blast radius measured at the time: **141 copies across 6 files**, including an
IDE log with 99 occurrences and a session transcript with 10. Git history and
shell history were clean (verified across all 19,128 objects and every ref), so
no history rewrite was needed - but that was luck, not design.

## The rule

**A secret value must never appear in a command, a script argument, an
environment assignment on a command line, or a log line.** Pass secrets *by
reference*.

Correct:

```python
# inside the Lambda, at request time
raw = boto3.client('secretsmanager').get_secret_value(SecretId='wecare/razorpay-webhook')
key_id = json.loads(raw['SecretString'])['key_id']
```

```
# infrastructure
{{resolve:secretsmanager:wecare/razorpay-webhook:SecretString:key_id}}
```

Wrong, in every case:

```
KEY='sk-...' python3 script.py          # recorded by "Always allow"
export TOKEN=abc123 && ./deploy.sh      # lands in shell history
echo "$SECRET"                          # lands in logs
aws secretsmanager get-secret-value ... # pulls the value into context
```

## Enforcement

`.kiro/hooks/block-inline-secrets.json` runs `scripts/block_inline_secrets.py`
as a **PreToolUse** hook on `execute_bash` and `control_bash_process`. It exits 2
and blocks the call when it sees an issuer-shaped token (`rzp_live_`, `sk-`,
`AIza`, `ghp_`, `xoxb-`, `AKIA`/`ASIA`, `sk_live_`, PEM private-key headers) or a
`*SECRET*=`/`*TOKEN*=`/`*API_KEY*=` assignment of a quoted 20+ character literal.

It deliberately allows by-reference forms: `SecretId='wecare/...'`,
`--secret-id wecare/...`, `{{resolve:secretsmanager:...}}`, and
`SECRET_NAME=wecare/...` (a name, not a value).

It is high-precision on purpose. A noisy guard gets switched off, and a
switched-off guard protects nothing. It will not catch an arbitrary
high-entropy string with no issuer prefix - it is a backstop, not a substitute
for the rule above.

Verify it with `python scripts/verify_secret_hook.py` (18 cases; test values are
assembled at runtime so the file contains no literal secret shape).

## If a credential does leak

1. **Rotate first.** Scrubbing files before rotating is theatre - assume any
   value written to disk is compromised.
2. Update the Secrets Manager entry, not the code. See the table above for which
   secret feeds which function.
3. Then measure the on-disk footprint and clean what is safe. Do **not** delete
   session transcripts (user data) or truncate logs belonging to a running IDE;
   those rotate on restart.
4. Check git history explicitly (`git rev-list --objects --all` piped through
   `git cat-file --batch`) before assuming a rewrite is or isn't needed.

## Related

- `.kiro/steering/aws-agent-rules.md` - never call `get-secret-value`; use
  `{{resolve:secretsmanager:...}}` with `asm-exec`.
- `docs/CREDENTIAL-ROTATION-RUNBOOK.md` - the rotation procedure and which
  secret each function reads.
