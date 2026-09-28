# CodeQL triage: `py/clear-text-logging-sensitive-data`

Rule 28 accepts an open high-severity finding as closed when it is **either remediated or
formally triaged with evidence**. This repository carried **223 open alerts with zero
triaged**, which is a failing release gate, and the size of the pile was itself the
problem: it was large enough that nobody read it, and the things worth reading were inside
it.

This document records what was found, what was fixed, and what each remaining dismissal
rests on. It exists because a dismissal without a reason is indistinguishable from a
dismissal without a thought.

---

## 1. What was in the pile

Of ~203 alerts on this one rule, roughly 155 were `phoneNumberId`, `metaPhoneId` and
`phoneHash` — Meta business identifiers this repository's own documentation publishes, and
SHA-256 digests. Genuinely safe, genuinely noise.

Buried in that noise, and found by reading rather than by grepping:

| Finding | Sites | Why it was invisible |
|---|---:|---|
| Full E.164 numbers in logger dicts | ~30 | Under keys like `senderPhone`, so *findable* — but drowned in 155 safe alerts |
| Customer names and WhatsApp usernames | 5 | Same |
| **WhatsApp Flow tokens** | 4 | The key is `flowToken`. A Flow token is `{prefix}-{uuid4}-waba-{n}-ph-{phone}` and `flows/common.get_phone_from_token` splits on `-ph-`, so the token **is** the phone number. No phone-shaped-field-name check could see it |
| **`contactId`** | 85 | The field that looked safest in the tree. `_deterministic_contact_id` mints it as `f'wa{digits}'`, so a WhatsApp-originated contact id is the customer's digits behind a two-character prefix. Confirmed against the live table without reading a value: all 6 rows match the character-class pattern `Ax999999999999` |
| Whole Meta request bodies | 5 | `'payload': message_payload` carries an unmasked `to` and the message content. One dict masked `recipientPhone` **and** `normalizedPhone` on consecutive lines and then dumped the entire payload two lines later |
| The customer's inbound message text | 1 | `'content': content_lower` on `pay_keyword_triggered` |
| The flow response echoed back to Meta | 1 | Truncated strings to 200 chars, which does not remove a name or an address. Its own `except` branch already logged keys only |
| A customer-written request subject | 1 | Free text |
| Raw `str(e)` where taint reaches it | 14 | Steering: log `type(e).__name__` unless our own code built the message |

**About 146 real disclosures, all remediated — not dismissed.** Three gates in
`tests/test_log_phone_masking.py` now fail the build if any class returns, and the
`mask_flow_token` / `mask_contact_id` helpers mask exactly the disclosing form and pass
the opaque form through untouched.

## 2. The mistakes made while fixing it, because they are the reusable part

**A dict entry plays three different roles.** `'to': phone` is a log line, the Meta request
body, or the stored CRM record, and only the first should be masked. Masking the second
breaks sending; masking the third destroys the record the CRM exists to keep.

Two regex heuristics got this wrong before an AST pass got it right:

1. *"Wrap any line matching the pattern"* — hit **11** payload and item dicts.
2. *"Walk back to the nearest `logger.`"* — hit **20** more, including
   `_store_call_log({...})` sitting a few lines below an unrelated `logger.info`. That
   masked the call log's own numbers and dropped the caller's name from it.
   `tests/test_calling.py::test_bsuid_extraction_from_contacts` is what caught it.

All 31 were reverted. The classifier now walks the AST and asks which call actually
consumes each dict, seeing through `json.dumps` because `json.dumps` into
`lambda_client.invoke` is a payload and into `logger.info` is a log.

**A slice is not an index.** `_is_sanitised` treated every `ast.Subscript` as safe, because
`phone[-4:]` truncates. But `contact['id']` is a dict lookup returning the whole value, and
conflating the two hid exactly two raw contact ids.

**An error message can contain the thing you are testing for.** Checking whether an API
existed by grepping command output reported three deleted HTTP APIs as present, because
`NotFoundException: Invalid API identifier specified 775261844268:ppq3shpmbd` contains the
id. Exit codes, not output matching.

## 3. What each dismissal rests on

`scripts/triage_codeql_logging.py --report` reproduces the classification; `--apply`
performs the dismissals.

The alert location points at the whole `json.dumps({...})` call, not at the element CodeQL
considers sensitive, and the REST API does not expose the code flow. So rather than
guessing which element was meant, the script enumerates **every** key/value pair and
classifies each one. **An alert is dismissed only when no element can carry identifying
data** — which is a stronger claim than matching CodeQL's choice would have been.

| Classification | Meaning | Example |
|---|---|---|
| `CONST` | A literal in the source | `'event': 'message_stored'` |
| `SANITISED:<fn>` | Through a masking or reducing helper | `mask_phone(...)`, `bool(...)`, `len(...)` |
| `TYPE_NAME` | `type(e).__name__` | exception type, not text |
| `SLICE` | A truncating slice | `phone[-4:]` |
| `OPAQUE_ID` | An identifier we or a provider mint | `requestId`, `wamid`, `phoneNumberId`, `phoneHash` |
| `REVIEWED` | Judged one group at a time, reason in the source | media ids, DLT template ids, outcome flags |
| `AUDIT_RETAINED` | Deliberately kept | the **staff** Cognito username in `middleware.py` — logging who performed an administrative action is an audit requirement, so removing it would be the wrong remediation |
| `NUMERIC` / `ENUM` / `BOOL_KEY` | A count, a closed set, a predicate | `statusCode`, `direction`, `hasMedia` |
| `REDUCED:<fn>` / `DERIVED:<fn>` | For `print()` sites in `scripts/` | `len(v)`, `fingerprint(v)` |

### The 69 alerts in `scripts/`

Developer-run tooling that uses `print()`, so there is no dict. CodeQL flags them because
names like `SECRET_ID` and `args.secret` look sensitive — they hold secret **identifiers**,
and the value-bearing lines emit a length, a label or an irreversible `sha256[:12]`, which
is precisely the by-reference reporting `.kiro/steering/secret-handling.md` prescribes:
*provider, credential present YES/NO, field count, fingerprint, length*.

All 69 were read. Exactly one interpolated something that could have been a value —
`verify_secret_consumption.py`'s JSON `leaks` list — and reading it shows `what` is a label
from the known-credential map and `fp` is `digest(value)`. No value is printed.

### Staleness, and why the guard is per-file

An alert records the `commit_sha` it was analysed on. Line numbers move, and this work
moved thousands of them, so resolving an old `start_line` against the current file can land
on a different dict and "prove" the wrong thing safe.

The first guard required `commit_sha == HEAD`. Correct in principle, unreachable in
practice: three sessions were pushing every few minutes, so CodeQL was always a commit or
two behind and the check never passed. The guard is now per-**file** — the file the alert
points into must be unchanged between the analysed commit and HEAD — and it **fails
closed**, treating an unknown commit or a locally-modified file as stale.

## 4. What is NOT dismissed

53 alerts stay open, and they stay open because the classifier could not prove them, not
because they are known bad. "I could not prove this" and "this is fine" must not produce
the same outcome.

They fall into two groups:

- **~15 in `amplify/` handlers** whose log site is `logger.info(f"...")` — an f-string
  rather than a `json.dumps` dict, which the classifier does not read. Each needs a human
  to look at the interpolations.
- **~38 in `scripts/`** whose interpolated expression is a bare name the classifier cannot
  attribute (`sid`, `p`, `verb`, `name`, `RAZORPAY_SECRET_NAME`, `PASSPHRASE_SECRET`).
  Several are plainly secret *names* and would pass on inspection; they are left open
  rather than pattern-matched into safety.

The other rules are handled separately and none is dismissed on a pattern:

| Rule | Open | Disposition |
|---|---:|---|
| `py/weak-sensitive-data-hashing` | 9 | **Correct as written, remediation would be a defect.** Six are `hmac.new(app_secret, token, hashlib.sha256)` — Meta's mandated `appsecret_proof` algorithm, not password hashing. Three are irreversible fingerprints (`sha256[:8]`, `sha256[:12]`) that confirm a stored credential matches without displaying it. A slow KDF would break the first and be pointless for the second |
| `js/incomplete-multi-character-sanitization` | 3 | `tools/audit/htmlcheck.js`. Partially fixed: the close-tag patterns are now whitespace-tolerant and loop to a fixed point, which took the count from 4 to 3 and matters beyond the alert because that function strips so script bodies are not counted as document text |
| `js/xss-through-dom` | 1 | Remediated in `calling.tsx` — the operator-typed IVR URL is now scheme-gated and a non-`http(s)` value renders as a disabled span. Awaiting re-scan confirmation |
| `js/clear-text-storage-of-sensitive-data` | 1 | `customerAuth.ts` stores a Cognito access token in `sessionStorage`. Deliberate and documented: the customer pool is separate from the staff pool and the token is not an Amplify session. `sessionStorage` clears on tab close and is the standard SPA choice; the alternative is a backend session behind an httpOnly cookie, which is an architectural change and not warranted by this. **Recorded as accepted risk, not dismissed as a false positive** |

## 5. Reproducing this

```bash
python scripts/triage_codeql_logging.py --report   # classification, no changes
python scripts/triage_codeql_logging.py --apply    # dismiss only the provable ones
python -m pytest tests/test_log_phone_masking.py   # the three gates
```

The gates are the durable part. Triage closes a backlog once; a gate stops it coming back.
