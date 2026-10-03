# PHASE 2 / OPTION B — verification record

Executed 2026-10-03 against `stack` at `fa9516b9`, following
`plan.md` in this directory. First iteration: no `review.json` existed.

Nothing was committed, pushed or deployed by this step. No `update-function-code`,
no version publish, no alias move.

---

## 1. Baseline, re-measured before any edit

```
.venv/bin/python -m pytest -q
13 failed, 6854 passed, 1 skipped, 2 xfailed in 59.52s
```

The same 13 names the plan recorded in §0 — blog-ledger, checkout-website,
coupons IAM (3), email-verification, gift-card amounts (2), gift-cards IAM (4),
provision-checkout. All belong to other sessions; none touches a menu.

**The brief said "~9 pre-existing failures". The real number is 13**, which the
plan had already corrected.

## 2. End state

```
.venv/bin/python -m pytest -q
13 failed, 6861 passed, 1 skipped, 2 xfailed in 58.39s
```

**Same 13 failures, same 13 names. Zero new failures.** Passing count rose by 7
(tests added net of tests deleted — see §6).

```
npx vitest run src/test/PerksPage.test.tsx    9 passed
npm run typecheck                             clean, no output
```

## 3. `py_compile` — every edited Python file

```
.venv/bin/python -m py_compile \
  amplify/functions/messaging/whatsapp-calling/handler.py \
  amplify/functions/messaging/inbound-whatsapp-handler/handler.py \
  amplify/functions/messaging/voice-in/c2c/handler.py \
  amplify/functions/messaging/voice-in/obd/handler.py \
  amplify/functions/ai/ai-generate-response/handler.py \
  amplify/functions/shared/lambda_utils/agent/governance.py \
  amplify/functions/shared/lambda_utils/notifications/policy.py \
  amplify/functions/shared/lambda_utils/notifications/worker.py \
  amplify/functions/messaging/whatsapp-business-api/handler.py \
  amplify/functions/messaging/outbound-whatsapp/handler.py \
  scripts/update_welcome_message_config.py
→ ALL COMPILED CLEAN
```

The `elif` → `if` promotion the plan flagged as "the single most likely mistake"
was made: `location_request` is now the first test in `_handle_interactive_send`.
Surviving branch order, read back from the file:

```
1496  if   interactive_type == 'location_request'
1508  elif interactive_type == 'cta_url'
1554  elif interactive_type == 'flow'
1605  elif interactive_type == 'address_message'
1632  elif interactive_type == 'catalog_message'
```

## 4. Import smoke — every edited handler module

Loaded by explicit path under a unique module name with
`amplify/functions/shared` on `sys.path`, `boto3` patched. Each module asserts the
deleted names are absent AND the kept names are present, so a passing import is
not just "it loaded".

| Module | Result | Names asserted gone | Names asserted kept |
|---|---|---:|---:|
| `whatsapp-calling` | OK | 5 | 5 |
| `inbound-whatsapp-handler` | OK | 4 | 4 |
| `voice-in/c2c` | OK | 0 | 1 |
| `voice-in/obd` | OK | 0 | 1 |
| `ai-generate-response` | OK | 1 | 4 |
| `whatsapp-business-api` | OK | 2 | 6 |
| `outbound-whatsapp` | OK | 0 | 4 |
| `lambda_utils.agent.governance` | OK | — | — |
| `lambda_utils.notifications.policy` | OK | — | — |
| `lambda_utils.notifications.worker` | OK | — | — |

Plus:

```
send_whatsapp_list      no longer resolves in the governance catalog
send_whatsapp_flow      still resolves
WA_TEMPLATE_NAME        '' (was 'wd_menu')
```

No `ImportError` and no `NameError` at module load anywhere.

## 5. Behaviour check — the error returns actually happen

Not inferred from the source; the functions were called.

```
outbound _handle_interactive_send:
  list         -> 400 'interactive messaging removed'
  button       -> 400 'interactive messaging removed'
  product      -> 400 'interactive messaging removed'
  product_list -> 400 'interactive messaging removed'
  nonsense     -> 400 'interactive messaging removed'
  cta_url          -> 200, interactive payload type 'cta_url'      (reached _send_message)
  address_message  ->      interactive payload type 'address_message'

whatsapp-business-api:
  /messages/send/interactive -> 410 'interactive messaging removed'
  /messages/send/unknown     -> 404   (still 404 — the withdrawn route and the
                                       unknown route stay distinguishable)
```

## 6. Repo-wide grep — every remaining hit, declared

Scoped to `amplify/functions tests src scripts`, `__pycache__` excluded.
`.worktrees/` deliberately NOT walked (another session's checkout).

Searched: `wd_menu`, `_send_interactive_list`, `_send_interactive_msg`,
`_handle_interactive_send`, `_handle_ivr_response`, `_handle_list_reply`,
`IVR_RESPONSES`, `_SHARED_IVR_MENU`, `IVR_MENUS`, `IVR_DEFAULT_MENU`,
`_get_ivr_menu`, `send_whatsapp_list`, `_tool_send_whatsapp_list`,
`menuResponses`, `show_sub_menu`, `show_main_menu`, `showSubMenu`,
`showMainMenu`, `_send_reply_buttons`, `_send_followup_buttons`.

**Zero hits** for `_tool_send_whatsapp_list`.

Every other hit, with its justification:

| Hit | Verdict |
|---|---|
| `notifications/policy.py:50,178` — `wd_menu` | **comment + refusal reason.** Names the deleted template as the reason the default is empty. Intentional. |
| `outbound-whatsapp/handler.py:625` — `wd_menu` | **comment.** Documents that the template was deleted at Meta. The plan explicitly says to keep and declare this one. |
| `voice-in/c2c:45`, `voice-in/obd:54` — `wd_menu` | **comment** explaining why `META_API_VERSION` is still imported after the send was removed. |
| `outbound-whatsapp:854,1457` — `_handle_interactive_send` | **kept by decision D1.** Reduced from nine interactive types to five. Deleting it wholesale would break the Razorpay post-payment flow send, the submit/track-request flows, India address collection in checkout, and every inbound CTA button. |
| `ai-generate-response:295,306,308,311,312,313` | **narrative comment block** rewritten to describe the end state. It necessarily quotes the names it says are gone. |
| `tests/test_menus_are_deleted.py` (DELETED_NAMES, prose, assertions) | **the tests that forbid the names.** `_send_interactive_list`, `_handle_ivr_response`, `_handle_list_reply`, `_send_reply_buttons`, `_send_followup_buttons` are all asserted ABSENT. |
| `tests/test_calling_menu_template_is_gone.py:48,63-67` | **same**, now in `IVR_DELETED_NAMES` asserting `not hasattr`. |
| `tests/test_calling.py:429-430` | **same**, the new deleted-symbol parametrisation. |
| `tests/test_business_api.py:373,377` | **same**, asserts `not hasattr(h, '_send_interactive_msg')` and the 410. |
| `tests/test_agent_surfaces.py:66` | **comment** recording why `send_whatsapp_list` left `SENDERS`. |
| `tests/test_notifications_*` (3 sites) | **comments** explaining why a template name must now be patched. |
| `src/test/PerksPage.test.tsx:121` | **comment** recording that the AI gift-card CTA went with `menuResponses`. |

### Three hits the plan's expected-hits table missed, and what was done

All three were stale **descriptions** of a send that phase 1 had already removed —
the post-call path has sent plain text since then. The copy was corrected; no
behaviour changed, and the toggle itself (`_is_postcall_wa_enabled`) is untouched
and still live.

| File | Before | After |
|---|---|---|
| `src/components/dashboard/tabs/SystemTab.tsx:50-51` | `'Send WhatsApp wd_menu template (...)'` / `'IVR: pre_accept → accept → send audio → send menu → terminate'` | `'Send post-call WhatsApp text (...)'` / `'IVR: pre_accept → accept → send audio → terminate'` |
| `src/pages/workspace/engage/whatsapp/calling.tsx:197` | comment `Post-call WhatsApp wd_menu notification toggle` | comment saying it sends plain text since 2026-10-02 |
| `src/pages/workspace/engage/whatsapp/calling.tsx:1291-1292` | heading `Post-call WhatsApp message (wd_menu)`, body `send the wd_menu video template ... with quick-reply options` | heading `Post-call WhatsApp message`, body `send a short WhatsApp follow-up message` |

`tests/test_outbound_whatsapp.py:218` used `wd_menu` as an arbitrary template name
in a `_send_direct_api` pass-through fixture. Renamed to `some_template` so a
repo-wide grep stops producing a false positive in a test that does not care.

### Declared NOT removed, so it is a decision rather than an oversight

`DEFAULT_BOT_FLOW['options']` and `['rating']` in the AI handler are still
list-shaped config (`sections` / `rows` / `buttonText`). They are not in the
plan's scope and nothing renders them (`_process_ai_automation` returns `None`
first). Removing `'rating'` would also take the rating flow, which is not a menu.
Left in place; flagged here for the owner.

Also unchanged, per plan §3: `DEFAULT_FALLBACK_MESSAGE` and
`MENU_PLACEHOLDER_TEXT` copy (pinned character-for-character by two phase-1
tests), and `modules/content.py` id passthrough.

## 7. Tests deleted vs updated

**Nothing was deleted outright.** Every failing menu test was rewritten into its
opposite assertion, because a deleted feature with no test is a feature that can
come back silently. Four individual test methods were replaced.

| File | Change |
|---|---|
| `tests/test_calling.py` | `TestIVRMenuParity` → `TestTheIvrButtonMenuIsGone`. **Dropped 4** menu tests (`test_phone1_and_phone2_ivr_menus_match`, `test_ivr_menu_has_required_buttons`, `test_default_ivr_menu_has_buttons`, `test_all_ivr_response_handlers_exist`). **Added** a 5-way `not hasattr` parametrisation and `test_the_audio_greeting_is_a_plain_constant`. **Carried over verbatim**: `test_all_phones_use_direct_api` (never about a menu). `TestIVRAutoPickup` untouched and passing — that is the calling lifecycle. |
| `tests/test_calling_menu_template_is_gone.py` | `IVR_KEEP_NAMES` trimmed from 8 to the 3 non-menu names; the 5 menu names moved to a new `IVR_DELETED_NAMES`. `TestTheIvrMenuIsNotCollateral` split into `TestTheCallSideBehavioursAreNotCollateral` (keep guard) and `TestTheIvrButtonMenuIsGone` (deletion guard, plus the greeting constant and the SMS/audio constants). **Dropped 3**: `test_every_ivr_button_still_has_a_reply[ivr_callback/ivr_support/ivr_ai]`. `TestTheDeletedTemplateIsGone`, `TestThePlaceholderCopyIsShared`, `TestThePlaceholderSendStaysOnMetaApi` untouched and passing. |
| `tests/test_menus_are_deleted.py` | `DELETED_NAMES` +4 (`_handle_ivr_response`, `_handle_list_reply`, `_send_reply_buttons`, `_send_followup_buttons`). `TestATappedRowStillAnswers` rewritten: **dropped 2** tests that required `_handle_list_reply` to exist, **added 5** asserting the inline dispatch sends `_send_menu_placeholder` for both `button_reply` and `list_reply`, keeps both correlation log events, and leaves `nfm_reply` routing intact. `TestEveryMenuIsGone`, `TestNobodyGetsSilence`, `TestNothingBecameUnreachable`, `TestTheRivalMenuIsGone` pass unchanged. |
| `tests/test_agent_surfaces.py` | `DISPATCHED` count `30` → `29`; `send_whatsapp_list` removed from `SENDERS`. |
| `tests/test_business_api.py` | `test_interactive_requires_object` → `test_the_interactive_route_is_gone_and_says_so` (asserts `not hasattr` + 410 + error text). Product-list test and `test_route_send_dispatch` untouched. |
| `tests/test_notifications_domain.py` | `test_unverified_template_is_skipped_not_sent` restated (now patches the module attribute, since `WA_TEMPLATE_NAME` is read once at import). **Added 2**: `test_no_template_configured_is_skipped_not_sent` (pins the shipped empty default and the `TEMPLATE_UNCONFIGURED` reason) and `test_a_configured_name_cannot_be_bypassed_by_verification` (pins the guard's ordering ahead of the verified check). `test_verified_sender_becomes_eligible` and `test_secondary_number_uses_its_own_object_not_waba1s` now configure a template name. |
| `tests/test_notifications_outbox.py` | Added a `whatsapp_eligible(monkeypatch)` helper; 5 call sites now use it. WhatsApp eligibility needs two conditions, not one. |
| `tests/test_notifications_worker.py` | `_env` fixture configures a template name. |
| `tests/test_outbound_whatsapp.py` | Fixture template name renamed. Location-request and address-message tests pass unchanged. |
| `src/test/PerksPage.test.tsx` | Dropped the 3 lines asserting the AI handler contains a `/perks/` CTA — that CTA lived inside `menuResponses`. Both WhatsApp assertions kept; the AI handler stays in the dead-URL guard. 9 passed. |
| `tests/test_agent_ui_truth.py` | No edit. Passes once `InternalChatTab.tsx` lost its row. |

## 8. The live `welcome_message` rows

No existing updater (`grep -rl SystemConfigTable scripts/` found only two
read-only auditors), so `scripts/update_welcome_message_config.py` was written.
Dry run by default; `--apply` writes; `update_item` on `configValue` + `updatedAt`
only, under `ConditionExpression=Attr('id').exists()`; parsed dict round-tripped
so unknown fields survive; `ensure_ascii=False`; re-reads and refuses to finish if
the text still contains "menu". No credential on any command line, nothing read
from Secrets Manager, no value printed.

```
Table : stack-wecare-digital-SystemConfigTable   (us-east-1, acct 775261844268)
Rows  : id = 'welcome_message'   and   id = 'welcome_message_2'
Field : configValue (JSON string) → textMessage, sendMenu
```

**BEFORE (both rows, byte-identical `textMessage`):**

```
Hi there! 👋 Welcome to WECARE.DIGITAL

Shop, pay, track requests, or get support — all right here.

Tap *Menu* to get started 👇
```
`sendMenu: true`

**AFTER (both rows):**

```
Hi there! 👋 Welcome to WECARE.DIGITAL

Shop, pay, track requests, or get support — all right here.

Just tell us what you need, or send a voice note.
```
`sendMenu: false`

Preserved verbatim on row 1: `enabled`, `delaySeconds`, `phoneNumberId`,
`welcomeBackMessage`. On row 2: `enabled`. Inner and top-level `updatedAt` set to
the write time. Re-read after the write confirmed both rows and that neither
mentions a menu.

This IS a customer-facing copy change. The plan's D4 is confirmed correct and the
brief's "read by nobody" is wrong: both rows are read at runtime, by
`inbound-whatsapp-handler._load_welcome_text` and
`ai-generate-response._get_welcome_config`.

## 9. One finding the plan asserted that measurement contradicts

Plan §6 step 5 says the actions inside the AI handler's `menu_*`/`store_*` block
are "also reachable by typed keyword" and lists five. Measured:

* `start_pay_flow` — **yes**, `PAY_KEYWORDS` in the same function.
* `start_subscribe_flow` — the flow's *continuation* states are reachable; its
  *entry* was the menu row.
* `toggle_audio`, `toggle_notifications`, `human_handoff` — **no**. Grepping
  `awaiting_toggle` / `toggle_audio` across `amplify/**/*.py` found the only
  entry points at the two menu branches that were deleted. No keyword anywhere
  starts a toggle flow or requests a handoff.

This does not change the verdict, and nothing became unreachable *as a result of
this step*: a `menu_*` id can only arrive from a menu tap, every menu was deleted
in phase 1, and after target 2 an interactive reply never reaches the AI handler
at all — it is answered by the placeholder and returns. So those three were
already unreachable before this edit. The block was deleted per plan, and the
loss is recorded here rather than left implicit.

**If the owner wants an audio toggle, a notifications toggle or a "talk to a
human" request back, each needs a typed keyword, which is new work rather than a
restoration.**
