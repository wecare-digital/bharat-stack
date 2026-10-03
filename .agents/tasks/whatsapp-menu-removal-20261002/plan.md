# PHASE 2 / OPTION B — scorched-earth removal of the remaining WhatsApp menu and interactive surface

Planned 2026-10-02 against working tree at `fa9516b9` (`stack`, == `origin/stack`).
Every line number below was read out of the file on that commit. **Re-check each
anchor before editing** — nine of the ten targets are in files other sessions also
touch, and line numbers drift.

Nothing in this plan changes code. It is the instruction set for the coder step.

---

## 0. Measured baseline, before any edit

| Measurement | Value |
|---|---|
| Python suite, `.venv/bin/python -m pytest -q` | **13 failed, 6854 passed, 1 skipped, 2 xfailed** in 58s |
| Pre-existing failures | `test_blog_ledger` (1), `test_checkout_website_handler` (1), `test_coupons_iam_and_table` (3), `test_email_verification_handler` (1), `test_gift_card_amounts_and_gst` (2), `test_gift_cards_iam_and_table` (4), `test_provision_checkout_contract` (1) |
| `npx vitest run src/test/PerksPage.test.tsx` | 9 passed |

**The brief said "~9 pre-existing failures". The real number is 13**, and all 13 are
coupons / gift-card / checkout / blog-ledger work belonging to other sessions. None
touches menus. The success bar is therefore: **13 failures, same 13 names**, plus
whatever this plan deliberately rewrites.

Capture the baseline again before starting, because another session may land work:

```
.venv/bin/python -m pytest -q 2>&1 | tail -20
```

---

## 1. Decisions I made, and why (read these before touching target 7 or 8)

The brief is internally inconsistent on two targets. Both are resolved here rather
than left for the implementer.

### D1 — `_handle_interactive_send` is NOT deleted wholesale (target 8)

The brief says "DELETE the generic interactive send path `_handle_interactive_send`"
and, four lines later, "Keep text, media, template, and checkout/order_details send
paths fully intact". Those cannot both happen, because that one function carries
**nine** interactive types, and four of them are load-bearing for non-menu features:

| type | line | live producers | menu? |
|---|---|---|---|
| `list` | 1492 | nothing left (menus deleted in phase 1) | **yes** |
| `button` | 1534 | `inbound._send_followup_buttons` (5 call sites) | **yes** — "What next? 👇 / Explore More / All Set" |
| `location_request` | 1587 | `src/pages/workspace/engage/whatsapp/inbox.tsx:770` | no |
| `cta_url` | 1599 | `inbound._send_cta_button` → 8 call sites (store, gift card, FAQ, about, help) | no |
| `flow` | 1645 | `payments/razorpay-webhook:1553`, `inbound:4746 / 4812 / 4948` | no |
| `product` | 1696 | dashboard only | **yes** |
| `address_message` | 1715 | `inbound:5403` (India Address Message, checkout) | no |
| `catalog_message` | 1742 | `src/pages/workspace/engage/commerce/index.tsx:65` | borderline |
| `product_list` | 1759 | dashboard only | **yes** |

Deleting the whole function would break the post-payment flow send in the Razorpay
webhook, the submit-request and track-request flows, India address collection in
checkout, and every CTA button in the inbound handler. That is far outside "no menus",
and the payments/checkout paths are protected by the project's own steering.

**Decision:** keep `_handle_interactive_send` as the single entry point and delete
only the menu-shaped branches — `list`, `button`, `product`, `product_list`. Keep
`location_request`, `cta_url`, `flow`, `address_message`, `catalog_message`. A removed
or unknown type returns a clear JSON error through the file's existing
`_error_response` helper (defined line 4140).

`catalog_message` is kept deliberately: the owner's own enumeration said
"(list/button/product)", a catalog message is a pointer to the Meta product catalogue
rather than a row list, and it is the live path for the commerce dashboard page.
Removing it would take a commerce feature away under a menu-removal mandate. If the
owner wants it gone it is a one-branch follow-up.

`button` IS removed, with its producer, because "What next? 👇" with Explore More /
All Set is a navigation chooser — exactly the thing the owner said goes.

### D2 — target 7's generic senders DO go, in full

`whatsapp-business-api._send_interactive_msg` and `_send_interactive_list` are
staff/dashboard-only raw pass-throughs. No Python caller. One frontend caller
(`src/api/client.ts:4497` → `/wa-business/interactive-list`) and no caller at all for
`/wa-business/messages/send/interactive`. `_send_product_msg` builds its own payload
and calls `_send_message` directly — it does **not** depend on the deleted plumbing,
so per the brief it stays. Delete both senders; both routes return a JSON error via
the file's `_resp` helper (line 252).

### D3 — `_detect_language_selection`, not `_detect_language`

The brief points at `_detect_language` (~3263). That symbol is actually at line
**4503** and is plain-text language *detection* used by AI response generation — leave
it completely alone. The function the brief means is `_detect_language_selection` at
**3259**. Its `region_*` / `lang_*` id branches and its
`message_type == 'interactive'` title-matching branch only ever receive input from the
deleted language-picker list, so they go; the text-command patterns (`language hindi`,
`change language to tamil`) stay.

### D4 — two welcome rows, not one, and they are NOT read by nobody

The brief says the `welcome_message` row is "now read by nobody". That is wrong.
`inbound-whatsapp-handler._load_welcome_text` (line 326) reads it through
`_get_welcome_config_key` (line 124), and `ai-generate-response._get_welcome_config`
(line 3381) reads it too. There are also **two** rows, not one — `welcome_message`
(phone 1) and `welcome_message_2` (phone 2) — and both still say "Tap *Menu* to get
started". Changing them is a real customer-facing change, which is why the
before-values are recorded in §11 and the write is a two-step GET-then-PUT.

### D5 — `WA_TEMPLATE_NAME` default becomes `""` plus two guards

Empty is safe only because it is guarded. See §10.

---

## 2. Target 1 — `amplify/functions/messaging/whatsapp-calling/handler.py` (2616 lines)

### Already done in phase 1 — confirmed by reading, not assumed

* `wd_menu` appears **nowhere** in this file.
* `_send_ivr_menu` is **gone**.
* The post-call and post-call-SIP paths already send plain text via
  `_send_menu_placeholder_text` (defined line 1011, called at 1113, 1118, 2541, 2546).
* `MENU_PLACEHOLDER_TEXT` is defined at line 1486 and is byte-identical to the inbound
  handler's copy.

### What is still present

| Symbol | Lines |
|---|---|
| `# ─── IVR Menu System ───` comment header | 1909-1913 |
| `_SHARED_IVR_MENU` | 1915-1927 |
| `IVR_MENUS` | 1928-1932 |
| `IVR_DEFAULT_MENU` | 1934-1946 |
| `IVR_RESPONSES` | 1948-1997 |
| `_get_ivr_menu` | 2000-2018 |
| the only `_get_ivr_menu` call site | 2109-2110, inside `_generate_ivr_tts_audio` |

### Edit

1. **Delete lines 1909-2018 inclusive** — the comment header through the end of
   `_get_ivr_menu`. Nothing else in the file references any of those six names
   (verified: the only `IVR_*` survivors are `IVR_SMS_CONTENT`,
   `IVR_SMS_DLT_TEMPLATE_KEY`, `DEFAULT_IVR_URL` — all SMS/audio, all keep).
2. Add a module-level greeting constant beside the other IVR constants, after
   `DEFAULT_IVR_URL` (line 1443) or immediately where the deleted block was:

   ```python
   # The IVR audio greeting text. Was read from the deleted IVR button menu's
   # 'greeting' key; it is a plain constant now because there is no menu to
   # configure. Markdown-free on purpose: the caller below strips formatting for
   # Polly anyway, and there are no buttons for it to introduce.
   IVR_GREETING_TEXT = "Thanks for calling WECARE.DIGITAL. How can we help you today?"
   ```
3. In `_generate_ivr_tts_audio`, replace lines 2108-2110:

   ```python
   # before
   # Get IVR greeting text for this phone number
   menu = _get_ivr_menu(phone_number_id)
   greeting_text = menu.get('greeting', 'Thanks for calling! Please check the menu below for options.')
   # after
   greeting_text = IVR_GREETING_TEXT
   ```
   Leave the `clean_text = greeting_text.replace(...)` line at 2112 as-is — it still
   works on a plain string. Keep the `phone_number_id` parameter in the signature.

### Call-lifecycle risk: nil, and here is the evidence

* **`_generate_ivr_tts_audio` has no callers anywhere in the repo.** The live greeting
  comes from `_get_auto_pickup_audio_url()` (line 1639) — a pre-recorded OGG at
  `DEFAULT_IVR_URL` — sent by `_send_audio_to_caller` at line 1806. So this edit cannot
  affect what a caller hears.
* `_auto_pickup_and_play` (1711-1824) keeps `pre_accept` → `accept` → audio →
  `time.sleep(3)` → `terminate` → `_update_call_status(call_id, 'ivr_completed')`
  untouched. Do not reorder or remove any of it.

### Stale prose to correct in the same edit (it now describes a menu that is gone)

* docstring lines 1713-1722: "send interactive IVR menu" and step 4 "Send interactive
  IVR menu buttons via WhatsApp message" — step 4 is now "Terminate".
* line 1773 comment: "Still send IVR menu even if pre_accept fails — caller gets chat
  buttons".
* line 1809-1810 comment: "3s is enough for caller to hear connection tone + see IVR
  menu in chat".
* line 1722 numbering so the five steps match the four that exist.

---

## 3. Target 2 — `amplify/functions/messaging/inbound-whatsapp-handler/handler.py` (7301 lines)

### What is present

| Thing | Lines |
|---|---|
| interactive dispatch block | 1424-1461 (`button_reply` 1431-1449, `list_reply` 1450-1461) |
| `_handle_ivr_response` (contains a function-local `IVR_RESPONSES` at 4512) | 4504-4622 |
| `_handle_list_reply` | 6585-6600 — already a thin wrapper that logs `list_reply_received` and calls `_send_menu_placeholder` |
| `_send_menu_placeholder` (the phase-1 placeholder helper the brief asked me to find) | **4980-4991** |
| `MENU_PLACEHOLDER_TEXT` | 139 |

### Edit

1. **Delete `_handle_ivr_response`, lines 4504-4622 inclusive.** The `IVR_RESPONSES`
   dict goes with it (it is local to the function, not module scope). Note the
   SystemEvent `ivr_selection` write at 4600-4619 goes too — nothing reads that event
   type (grep `ivr_selection` finds only this writer).
2. **Delete `_handle_list_reply`, lines 6585-6600 inclusive.**
3. Rewrite the dispatch, lines 1430-1461, to:

   ```python
   # Button reply. The IVR button menu and the follow-up button chooser are both
   # deleted, so there is no id left to route - a tap on a button still sitting in
   # a customer's history gets the plain-text placeholder rather than silence.
   elif interactive_type == 'button_reply':
       button_id = interactive.get('button_reply', {}).get('id', '')
       logger.info(json.dumps({
           'event': 'button_reply_received',
           'buttonId': button_id,
           'contactId': mask_contact_id(contact_id),
           'requestId': request_id,
       }))
       _send_menu_placeholder(contact_id, aws_phone_number_id, request_id)
       return
   # List reply - a tap on a row from a deleted menu still in chat history.
   elif interactive_type == 'list_reply':
       list_id = interactive.get('list_reply', {}).get('id', '')
       logger.info(json.dumps({
           'event': 'list_reply_received',
           'listId': list_id,
           'contactId': mask_contact_id(contact_id),
           'requestId': request_id,
       }))
       _send_menu_placeholder(contact_id, aws_phone_number_id, request_id)
       return
   ```

   Keep the `list_reply_received` event name verbatim — `test_menus_are_deleted`
   asserts on it and it is the only correlation handle on a tapped row id.
   `followup_done`'s bespoke reply (lines 1445-1449) is dropped: its producer is being
   deleted in §9 and a stale tap now gets the same placeholder as every other stale
   tap. The `call_permission_reply` discard at 1427-1429 and the `nfm_reply` branch at
   1464 onward are **untouched** — `nfm_reply` carries India address submissions and
   post-payment flow completions.

4. **Per D1, also delete the follow-up button chooser** (this is the inbound half of
   target 8):
   * `_send_reply_buttons`, lines 5046-5090
   * `_send_followup_buttons`, lines 5093-5107
   * its five call sites: lines **1851, 1960, 4905, 5138** (and the definition). Delete
     the call line only; leave the surrounding reply intact so the customer still gets
     the text answer, just without the two buttons under it.

### Out of scope, recorded so it is a decision rather than an oversight

* `modules/content.py` id passthrough — stays, per brief (forwards ids as strings).
* `DEFAULT_FALLBACK_MESSAGE` (line 133) still reads "Type 'menu' to see available
  options", and `MENU_PLACEHOLDER_TEXT` (139) still says "please type *menu*". Both are
  phase-1 copy, pinned character-for-character by
  `test_menus_are_deleted.py::test_the_placeholder_copy_is_exact` and
  `test_calling_menu_template_is_gone.py::test_both_lambdas_hold_the_same_string`.
  Changing them is a copy decision for the owner, not part of this removal. **Do not
  touch them** — if you do, both tests and both Lambdas must change together.
* `_send_cta_button` (4994) and `_send_help_about` (5110) stay: `cta_url` survives.

---

## 4. Target 3 — `amplify/functions/messaging/voice-in/c2c/handler.py` (673 lines)

### What is present

The `wd_menu` send is live and will fail at Meta the next time a C2C call completes:
the template was deleted on Meta's side on 2026-10-02.

| Thing | Lines |
|---|---|
| docstring claiming a WhatsApp channel | 353, 356 |
| `wa_message_id = ''` initialiser | 376 |
| the whole send block, `# ── 2. WhatsApp wd_menu template from WABA1 ──` through both `except` handlers | **439-501** |
| CDR `if wa_message_id:` write block | **523-531** (plus blank 532) |
| `'whatsapp': bool(wa_message_id)` in the success log | 553 |

### Edit

1. Delete lines **439-501** inclusive (block plus its two `except` handlers; stop
   before the blank line at 502 so `# ── 3.` keeps its spacing).
2. Delete line **376** (`wa_message_id = ''`).
3. Delete lines **523-532** (the `if wa_message_id:` block and its trailing blank).
4. Delete line **553** (`'whatsapp': bool(wa_message_id),`) from the
   `c2c_cdr_trigger_metadata_updated` log.
5. Fix the docstring: line 353 → `"""Send RCS + SMS notifications on C2C CDR events.`
   and line 356 → `Channel priority: SMS (AWS End User Messaging) → RCS (Sinch rcsmenu template)`.
   (The existing "Airtel IQ" in that line is also stale — the SMS send at 390-394 goes
   through `lambda_utils.comms.notify`, i.e. AWS End User Messaging. Correct it while
   you are there.)

### Now-unused module scope — deliberate, non-obvious call

After the deletion, `secrets_client` (line 55), `urllib.request` / `urllib.error`
(34-35) and `META_API_VERSION` (46) have **no remaining reference in the file**
(verified by grep). There is no Python linter in CI (no ruff/flake8/pylint config, and
none of the 20 workflows runs one), so none of these is a build failure.

* **Delete** `import urllib.request`, `import urllib.error` (34-35) and the
  `secrets_client = boto3.client('secretsmanager', ...)` line (55).
* **Keep** the `META_API_VERSION` import and add a one-line comment saying why: the
  import comment already says "validated at import", so it has a side effect that
  removing would silently drop.

SMS (lines 378-414) and RCS (416-437) are untouched.

---

## 5. Target 4 — `amplify/functions/messaging/voice-in/obd/handler.py` (1049 lines)

Structurally identical to §4. Same five edits, same two decisions, different anchors:

| Thing | Lines |
|---|---|
| docstring | 829, 832 |
| `wa_message_id = ''` | 865 |
| send block | **928-990** |
| CDR `if wa_message_id:` | **1012-1021** |
| `'whatsapp': bool(wa_message_id)` | 1041 |
| now-unused `urllib` imports / `secrets_client` | 44-45 / 64 |
| `META_API_VERSION` import to KEEP | 55 |

Log event name in the except handlers is `OBD CDR WhatsApp wd_menu FAILED`; success log
event is `obd_cdr_trigger_metadata_updated`. SMS and RCS untouched.

No test anywhere covers `_send_c2c_cdr_notifications` or `_send_obd_cdr_notifications`
(grep across `tests/` finds zero hits), so verification for §4 and §5 is `py_compile`
plus import-smoke plus the repo-wide `wd_menu` grep.

---

## 6. Target 5 — `amplify/functions/ai/ai-generate-response/handler.py` (6003 lines)

### What is present

| Thing | Lines |
|---|---|
| `'menuResponses': {` … closing `},` | **317-429** |
| `send_whatsapp_list` toolSpec | **971-996** (the `{` at 970 through the `},` at 997 — delete the whole list element) |
| dispatch `elif tool_name == 'send_whatsapp_list': return _tool_send_whatsapp_list(...)` | **2046-2047** |
| `_tool_send_whatsapp_list` | **4763-4828** |
| `_handle_bot_flow` `show_language_picker` branch | 3571-3580 |
| `show_sub_menu` branch | **3581-3594** |
| `show_main_menu` branch | **3595-3601** |
| `_detect_language_selection` | 3259-3313 |
| other `flowAction: 'showMainMenu'` emits | 3424, 3545, 3670 |

### Reachability, measured

`_handle_bot_flow` IS reachable (called at 2430 from the main response path). But every
`flowAction` it emits is inert: the only renderer was
`inbound._process_ai_automation`, which is now a no-op stub returning `None` as its
first statement (`inbound/handler.py:6744-6749`). The handler's own comment block at
284-315 already records this. So the `showMainMenu` / `showSubMenu` strings reach no
customer today — they are dead signals, which is why removing them is safe.

### Edit

1. **Delete lines 317-429** — the whole `'menuResponses'` block. Every key is a
   `menu_*` or `store_*` row id that can only arrive from a menu tap, and after §3 a
   list/button reply never reaches this function at all. ⚠️ **See §6a — this one has a
   test consequence outside Python.**
2. **Delete the `send_whatsapp_list` toolSpec, lines 970-997.** This is the "removed
   tool must also leave the list the model is given" requirement; the toolSpec list IS
   that list.
3. **Delete lines 2046-2047** (dispatch branch).
4. **Delete `_tool_send_whatsapp_list`, lines 4763-4828** (plus the two blank lines at
   4761-4762 so spacing stays at two).
5. **Delete the `show_sub_menu` branch (3581-3594) and the `show_main_menu` branch
   (3595-3601).** With `menuResponses` gone, the enclosing
   `if content_lower.startswith('menu_') or content_lower.startswith('store_'):` block
   at 3565 can never find an `item`, so the whole block 3565-3665 collapses to
   `return None`. Prefer deleting the entire block over leaving a lookup against a dict
   that no longer exists. **But first move the three still-wanted actions out of it** —
   `start_subscribe_flow`, `start_pay_flow`, `toggle_audio`, `toggle_notifications`,
   `human_handoff` are reachable only through this block today and only via `menu_*`
   ids, so they die with it. That is correct: each is also reachable by typed keyword
   (`PAY_KEYWORDS` at 3550, the `toggle_*` flow states at 3506-3535, and the subscribe
   flow state at 3432). Confirm each by reading before deleting, and record in the
   commit message that nothing became unreachable.
6. **`_detect_language_selection` (3259-3313):** delete the `region_` id branch
   (3279-3283), the `lang_` id branch (3285-3288) and the
   `if message_type == 'interactive':` title-matching branch (3290-3296). **Keep** the
   `lang_patterns` text-command block (3298-3311) and the `return None`. Per D3, do not
   touch `_detect_language` at 4503.
7. The caller at **2362-2415** has two arms: the `isinstance(lang_selection, dict) and
   'region' in lang_selection` arm (2365-2393) can no longer be reached once the
   `region_` branch is gone — delete it. The language-save arm (2395-2415) still fires
   from the text path — keep it, but drop `'flowAction': 'showOptions'` (2413) only if
   you also drop the other inert flowActions; otherwise leave it.
8. The three remaining `flowAction: 'showMainMenu'` emits at **3424, 3545, 3670** plus
   the "Here's the menu 📋" / "Back to the main menu" copy that goes with them: delete
   the `flowAction` key and replace the copy with menu-free wording. 3545 is the
   `content_lower in ('menu', 'main menu', 'show menu', 'hi', 'hello')` branch — the
   one a customer can actually type — so its `suggestedResponse` must become a neutral
   greeting, not "Here's the menu".
9. Update the `# ── DELETED ...` narrative comment at 284-315 so it describes the end
   state rather than "those three signals are still emitted below".

### 6a. ⚠️ Deleting `menuResponses` breaks a vitest test

`src/test/PerksPage.test.tsx:122-126` asserts the AI handler **contains**
`https://wecare.digital/perks/`. That string occurs in the AI handler exactly once —
line 427, the `store_gift_card` CTA inside `menuResponses`. Deleting the block makes
that assertion fail.

**Fix:** in `src/test/PerksPage.test.tsx`, in the
`it( 'points the whatsapp and AI gift-card CTAs at the real /perks page …' )` block,
delete these three lines:

```ts
const ai = read( 'amplify/functions/ai/ai-generate-response/handler.py' );
expect( ai ).toContain( 'https://wecare.digital/perks/' );
expect( ai ).not.toContain( 'wecare.digital/perks/#gift-cards' );
```

Keep the two `whatsapp` assertions (inbound still has the CTA at line 2021) and keep
the AI handler in the dead-`/gift-card`-URL list in the first `it` block — that
assertion is still a valid guard. Add a one-line comment saying the AI gift-card CTA
was removed with the menu it lived in.

---

## 7. Target 6 — `amplify/functions/shared/lambda_utils/agent/governance.py` (508 lines)

### What is present

```
320:    "send_whatsapp_list": _apply("send_whatsapp_list",
321:                                 "Send an interactive list message.",
322:                                 _SEND, _SEND_DETAIL),
```

### Edit

Delete lines **320-322**. Nothing else changes — `send_whatsapp_flow`,
`send_whatsapp_buttons` and every other entry stay.

### Three files must change in the same commit, or tests fail

`tests/test_agent_surfaces.py` and `tests/test_agent_ui_truth.py` pin the catalog
against the dispatch table and against the dashboard UI mirror:

1. `tests/test_agent_surfaces.py:65` — `test_the_dispatch_table_was_actually_found`
   asserts `len(DISPATCHED) == 30`. `DISPATCHED` is regex-extracted from the AI
   handler's `tool_name == '...'` branches, so §6 step 3 drops it to **29**. Change the
   literal to `29`.
2. `tests/test_agent_surfaces.py:66-68` — remove `"send_whatsapp_list"` from the
   `SENDERS` tuple, or `test_every_send_write_and_delete_is_refused` fails on
   `gov.resolve('send_whatsapp_list')`.
   `test_the_internal_surface_matches_the_dispatch_table_exactly` then passes because
   both sides lost the same name — that is the test that forces governance and the
   handler to change together.
3. `src/components/dashboard/tabs/InternalChatTab.tsx:106` — delete the
   `{ id: 'send_whatsapp_list', … }` row. `test_agent_ui_truth.py`'s
   `test_same_set_of_tools_on_both_sides` asserts the TSX row set equals the internal
   catalog set, so leaving it is a **Python** test failure.
4. `src/pages/workspace/settings/internal-agent.tsx:56` — delete the
   `{ id: 'send_whatsapp_list', … }` entry. No test pins this one; remove it for
   consistency so the settings page does not advertise a tool that no longer exists.

`send_whatsapp_list` was already classified APPLY / refused, so `assert_executable`
blocked it before dispatch. This is cleanup, not a behaviour change.

---

## 8. Target 7 — `amplify/functions/messaging/whatsapp-business-api/handler.py` (6380 lines)

### What is present

| Thing | Lines |
|---|---|
| `_send_interactive_msg` | **2049-2055** |
| `/interactive` dispatch in `_route_send_message` | **2187-2188** |
| `_send_interactive_list` (+ its section banner) | **2524-2571** (banner 2524-2526, def 2527-2571) |
| `/interactive-list` dispatch in the main router | **6086-6091** |
| route-manifest entry | `_routes.json:291` `"POST /wa-business/interactive-list"` |
| `_resp` helper to use | 252 |
| the one frontend caller | `src/api/client.ts:4497` |

### Edit

1. Delete `_send_interactive_msg`, lines **2049-2055**.
2. Replace the `/interactive` dispatch at 2187-2188 with an explicit error so the path
   does not fall through to the `404 Unknown send path` at 2199 (which would be a
   misleading "unknown route" for a route that exists):

   ```python
   if path.rstrip('/').endswith('/interactive'):
       return _resp(410, {'error': 'interactive messaging removed',
                          'detail': 'generic interactive sends were deleted on '
                                    '2026-10-02; use /text, /template, /media or /flow'})
   ```
   410 Gone is the honest code for a route that existed and was withdrawn; if the
   frontend only branches on `res.error`, 400 is equally fine — pick 410 and keep it
   consistent with step 4.
3. Delete `_send_interactive_list` and its banner, lines **2524-2571**.
4. Replace the `/interactive-list` branch at 6086-6091 with the same shaped error:

   ```python
   elif '/interactive-list' in path:
       return _resp(410, {'error': 'interactive messaging removed',
                          'detail': 'the interactive-list sender was deleted on 2026-10-02'})
   ```
   Keep the `elif` chain position so `/calling-settings` below is still reached.
5. Update the route comment at line 1979 (`POST .../send/interactive → list/button/
   product/catalog (pass-through)`) and the file header at line 25.

### Explicitly keep

`_send_product_msg` (2134-2176) — it is independent, builds its own `interactive`
payload and calls `_send_message`; `tests/test_business_api.py:465` pins its
`product_list` payload. `_send_request_contact_info` (2057-2066), `_send_flow_msg`
(2069-2109), `_send_text`, `_send_template_msg`, `_send_media_msg`,
`_send_contacts_msg`, `_send_location_msg` — all keep.

### Test and surface consequences

* `tests/test_business_api.py:372-373` — `test_interactive_requires_object` calls
  `self.h._send_interactive_msg(...)`. **Delete this test method**; the function is
  gone. Optionally replace it with one asserting
  `_route_send_message('/messages/send/interactive', {})['statusCode'] == 410`.
* `tests/test_business_api.py:396-400` — `test_route_send_dispatch` asserts an unknown
  path gives 404. Still true; leave it.
* `_routes.json:291` stays accurate — the route still exists, it just answers with an
  error. Do not touch API Gateway.
* `src/pages/workspace/engage/whatsapp/interactive-lists.tsx` and its nav entry
  (`src/config/navigation.ts:212`) will now surface the API error. **Left in place on
  purpose** — removing dashboard pages is not in this brief, and the page already
  renders API errors. Record it as a known consequence.

---

## 9. Target 8 — `amplify/functions/messaging/outbound-whatsapp/handler.py` (4277 lines)

Scope per **D1**.

### What is present

| Thing | Lines |
|---|---|
| `is_interactive` / `interactive_type` / `interactive_data` reads | 647-649 |
| dispatch `if is_interactive and interactive_type:` | **852-857** |
| `_handle_interactive_send` def + docstring | 1457-1472 |
| `list` branch | **1492-1533** |
| `button` branch | **1534-1586** |
| `location_request` branch | 1587-1598 — KEEP |
| `cta_url` branch | 1599-1644 — KEEP |
| `flow` branch | 1645-1695 — KEEP |
| `product` branch | **1696-1714** |
| `address_message` branch | 1715-1741 — KEEP |
| `catalog_message` branch | 1742-1758 — KEEP (D1) |
| `product_list` branch | **1759-1792** |
| `else: return _error_response(400, f'Invalid interactive type: …')` | 1793-1794 |
| `_error_response` helper | 4140 |

### Edit

1. **Delete the `list` (1492-1533), `button` (1534-1586), `product` (1696-1714) and
   `product_list` (1759-1792) branches.**
2. ⚠️ **The first surviving branch must become `if`, not `elif`.** Deleting the `list`
   branch removes the `if` at 1492, so `location_request` at 1587 becomes the first
   test and must be rewritten from `elif` to `if`. Missing this is a `SyntaxError`, and
   it is the single most likely mistake in this whole plan.
3. Change the `else` at 1793-1794 to name the removal explicitly:

   ```python
   else:
       return _error_response(
           400, 'interactive messaging removed',
           f"'{interactive_type}' interactive sends were deleted on 2026-10-02; "
           "list, button, product and product_list are no longer supported")
   ```
   `_error_response(status_code, error, message=None)` — check the signature at 4140 and
   match it.
4. Update the docstring at 1461-1472 so the "Interactive Types" list matches the five
   that remain.
5. **Keep** lines 647-649 and the dispatch at 852-857 exactly as they are. An
   `isInteractive` request now reaches `_handle_interactive_send` and gets the JSON
   error from step 3 — which is precisely the brief's "return a clear JSON error rather
   than crashing", achieved without a second error path.
6. The inbound-side producers of the removed `button` type are deleted in §3 step 4.
   Nothing produces `list`, `product` or `product_list` from Python; the dashboard
   composer (`src/components/InteractiveMessageComposer.tsx:198` →
   `src/api/client.ts:948 sendWhatsAppInteractive`) can still request them and will now
   receive the 400. Left in place, same reasoning as §8.

### Explicitly keep — these are NOT interactive menus

* `_build_payment_settings`, `order_details`, `isInteractivePayment` (640, 2026, 2066,
  3009), `isCheckoutTemplate` / `_handle_checkout_template_send` (858-864),
  `_handle_order_status_send` (845-851), `_handle_live_send` (1859+), and every
  text/media/template path.
* `template_flow_button` / `flowActionData` handling (636, 3461-3480, 1653) — template
  flow buttons, unrelated to `_handle_interactive_send`.
* The `wd_menu` mention at line 625 is a **comment** explaining that the template was
  deleted at Meta. Keep it; it is documentation of the removal. ⚠️ It will show up in
  the repo-wide `wd_menu` grep in §12 — that hit is intentional and must be declared,
  not deleted.

### Tests

`tests/test_outbound_whatsapp.py:121-138` tests `location_request` and
`address_message`, but through `_build_message_payload` (`self.build`), not through
`_handle_interactive_send`. Both types are kept anyway. No change expected — if either
fails, something was deleted that should not have been.

---

## 10. Target 9 — `amplify/functions/shared/lambda_utils/notifications/policy.py` (265 lines)

### What is present

```
51: WA_TEMPLATE_NAME = os.environ.get("NOTIF_WA_TEMPLATE_NAME", "wd_menu")
```

Consumers, all of them:

| Site | Use |
|---|---|
| `policy.py:166, 168` | `template_name` + reason text on the UNVERIFIED ineligible decision |
| `policy.py:174` | `template_name` on the eligible decision |
| `notifications/worker.py:156` | `template = str(delivery.get("templateName") or policy_mod.WA_TEMPLATE_NAME)` → sent as `templateName` with `isTemplate: True` to `wecare-outbound-whatsapp` |
| `tests/test_notifications_domain.py:616` | `assert d.template_name == "wd_menu"` |

`NOTIF_WA_TEMPLATE_NAME` is **not** set on any function —
`grep NOTIF_ config/lambda-env-manifest.json` finds only `NOTIF_SWEEP_LIMIT`. So the
default is what ships.

### Why an empty default is safe here, measured

`_WA_VERIFIED_DEFAULT = ""` (line 69) and `wa_verified_senders()` reads
`NOTIF_WA_VERIFIED_SENDERS`, which is also unset. So `decide_whatsapp` returns
**ineligible / SKIPPED** for every sender today (line 161-169) and `worker._send_whatsapp`
is never reached. The change cannot send anything now — the guards below are for the
day somebody sets `NOTIF_WA_VERIFIED_SENDERS`.

### Edit

1. Line 51 → `WA_TEMPLATE_NAME = os.environ.get("NOTIF_WA_TEMPLATE_NAME", "")` and
   rewrite the comment at 48-50 to say the previous default named a template Meta
   deleted on 2026-10-02, that there is no approved replacement, and that an empty name
   means the channel is ineligible rather than that a nameless template gets sent.
2. **Guard 1, in `decide_whatsapp`** — insert immediately after the
   `mapping = WA_SENDER_TEMPLATES.get(sender)` check (after line 159), before the
   verified-senders check:

   ```python
   if not WA_TEMPLATE_NAME:
       return ChannelDecision(
           CHANNEL_WHATSAPP, eligible=False, provider=PROVIDER_META,
           template_id=template_id, sender_label=label,
           reason="INELIGIBLE_TEMPLATE_UNCONFIGURED: no WhatsApp notification "
                  "template is configured (NOTIF_WA_TEMPLATE_NAME is unset). "
                  "wd_menu was deleted at Meta on 2026-10-02 and has no "
                  "approved replacement")
   ```
   Placed after `mapping` so the reason can still name the sender and template object,
   and before the verified check so "unconfigured" is reported in preference to
   "unverified" — the more specific truth.
3. **Guard 2, in `worker._send_whatsapp`** (line 156) — refuse rather than invoke with
   an empty template name:

   ```python
   template = str(delivery.get("templateName") or policy_mod.WA_TEMPLATE_NAME)
   if not template:
       return SKIPPED, "", "TEMPLATE_UNCONFIGURED"
   ```
   Check the exact disposition/category constants imported in `worker.py` and use the
   existing vocabulary — do not invent a new one. This matters because
   `outbound-whatsapp` line 3295 is `if is_template and template_name:`, so an empty
   name silently falls through to a content send with empty content.
4. `tests/test_notifications_domain.py:616` — change
   `assert d.template_name == "wd_menu"` to match the new state. Read the enclosing test
   first: if it is asserting the ELIGIBLE decision's template name it will now be
   asserting against an ineligible decision, so the test needs restating (likely
   `assert d.eligible is False` and
   `assert "INELIGIBLE_TEMPLATE_UNCONFIGURED" in d.reason`), not just a string swap.
   Add a sibling test that sets `NOTIF_WA_TEMPLATE_NAME` via monkeypatch and asserts the
   configured name flows through, so the guard itself is pinned.

---

## 11. Target 10 — the live `welcome_message` rows (DynamoDB DATA change)

### Identified with certainty

| | |
|---|---|
| Account / profile / region | `775261844268` / `wecare-prod` / `us-east-1` |
| Table | **`stack-wecare-digital-SystemConfigTable`** |
| Rows | **`welcome_message`** and **`welcome_message_2`** (partition key `id`, String) |
| Attribute to change | `configValue` (a JSON **string**), fields `textMessage` and `sendMenu` |
| Readers | `inbound-whatsapp-handler._load_welcome_text` (326, via `_get_welcome_config_key` 124) and `ai-generate-response._get_welcome_config` (3381) — both read `textMessage` only |
| `sendMenu` readers | **none** in Python; only `src/pages/workspace/engage/whatsapp/welcome.tsx` round-trips it |

There is **no** `ivr_menu_<phone_number_id>` row (the override `_get_ivr_menu` read was
never populated), and no `bot_flow_config` or `bot_language_picker_config` row. So §2
and §6 lose no live configuration.

### BEFORE values, read 2026-10-02 (recorded so the coder does not have to guess)

`welcome_message`, `updatedAt` 1776156910, `configValue`:
```json
{"enabled": true,
 "textMessage": "Hi there! 👋 Welcome to WECARE.DIGITAL\n\nShop, pay, track requests, or get support — all right here.\n\nTap *Menu* to get started 👇",
 "welcomeBackMessage": "", "delaySeconds": 2,
 "phoneNumberId": "phone-number-id-waba1-direct-1016149501586345",
 "sendMenu": true, "updatedAt": 1775120969}
```

`welcome_message_2`, `updatedAt` 1775120972, `configValue`:
```json
{"enabled": true,
 "textMessage": "Hi there! 👋 Welcome to WECARE.DIGITAL\n\nShop, pay, track requests, or get support — all right here.\n\nTap *Menu* to get started 👇",
 "sendMenu": true, "updatedAt": 1775120969}
```

Both say "Tap *Menu* to get started 👇". Both are read at runtime. The brief's "read by
nobody" is wrong — see D4.

### AFTER value (proposed, menu-free, same shape)

```
Hi there! 👋 Welcome to WECARE.DIGITAL

Shop, pay, track requests, or get support — all right here.

Just tell us what you need, or send a voice note.
```
and `"sendMenu": false`. Preserve every other field verbatim, including
`phoneNumberId` on row 1, `delaySeconds`, `enabled` and `welcomeBackMessage`. Set the
inner `updatedAt` and the top-level `updatedAt` to the write time.

### No existing tool — write one

`grep -rl SystemConfigTable scripts/` finds only `check_data_model_drift.py` and
`audit_data_model_drift.py`, both read-only auditors. Create
**`scripts/update_welcome_message_config.py`**:

* `.venv/bin/python` only (boto3 lives there); `AWS_PROFILE=wecare-prod` is already
  exported from `~/.zprofile` — do **not** pass credentials on the command line.
* `boto3.resource('dynamodb').Table('stack-wecare-digital-SystemConfigTable')`.
* Default behaviour is **dry run**: `get_item` both rows, parse `configValue`, print the
  before `textMessage` and `sendMenu` and the proposed after, and exit 0 without
  writing. `--apply` performs the write.
* Write with `update_item` on `configValue` and `updatedAt` only, with a
  `ConditionExpression=Attr('id').exists()` so a missing row fails loudly instead of
  creating one.
* Preserve unknown fields by round-tripping the parsed dict rather than rebuilding it.
* Use `json.dumps(..., ensure_ascii=False)` so the emoji stays a character, matching the
  existing rows' encoding. Verify by re-reading after the write.
* Print no credential, no secret, and nothing from Secrets Manager. **Do not call
  `secretsmanager get-secret-value`.**

Then: run dry-run, show the before/after, run `--apply`, re-read both rows and print
the after-values as evidence.

**STOP condition:** if either `get_item` returns no `Item`, or `configValue` does not
parse as JSON, or the table name does not resolve — do not write. Report and stop.
(Both rows were present and parsed cleanly at plan time, so this is a safety net, not
an expectation.)

---

## 12. VERIFICATION the coder must run

### 12.1 Syntax, every edited Python file

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
  amplify/functions/messaging/outbound-whatsapp/handler.py
```
Expect silence. The `elif`→`if` change in §9 step 2 is what this catches.

### 12.2 Import smoke, every edited handler module

Each Lambda entry point is named `handler.py`, so import by explicit path under a
unique name with `amplify/functions/shared` on `sys.path` — copy the `_load` helper
pattern from `tests/test_calling_menu_template_is_gone.py:60`. Assert the module object
exists and that the deleted names are gone, e.g.
`assert not hasattr(calling, 'IVR_RESPONSES')`.

### 12.3 Repo-wide greps — every remaining hit must be deleted or declared

```
for s in wd_menu _send_interactive_list _send_interactive_msg _handle_interactive_send \
         _handle_ivr_response _handle_list_reply IVR_RESPONSES _SHARED_IVR_MENU \
         IVR_MENUS IVR_DEFAULT_MENU _get_ivr_menu send_whatsapp_list \
         _tool_send_whatsapp_list menuResponses show_sub_menu show_main_menu \
         showSubMenu showMainMenu _send_reply_buttons _send_followup_buttons; do
  echo "=== $s ==="
  grep -rn "$s" amplify/functions tests src scripts 2>/dev/null | grep -v __pycache__
done
```

⚠️ **Scope the grep.** A bare `grep -r .` in this repo walks `out/`, `.next/`,
`node_modules/` and **`.worktrees/`** — the last one holds another session's checkout
(`.worktrees/login-fix-20261002`) which has its own copies of these handlers. A hit
there is not your problem and must not be edited.

Expected surviving hits, all intentional:

| Hit | Why it stays |
|---|---|
| `outbound-whatsapp/handler.py:625` comment | documents that `wd_menu` was deleted at Meta |
| `whatsapp-calling/handler.py` `IVR_SMS_*`, `DEFAULT_IVR_URL`, `_generate_ivr_tts_audio` | SMS and audio, not a menu |
| `_handle_interactive_send` in outbound | kept by D1, reduced to five types |
| `tests/test_calling_menu_template_is_gone.py` prose quoting `wd_menu` | the test that forbids it |
| `tests/test_menus_are_deleted.py` `DELETED_NAMES` listing `_send_interactive_list` | the test that forbids it |
| `docs/` and `.kiro/steering/` references | documentation of the removal |

Anything else is an oversight.

### 12.4 Python suite

```
.venv/bin/python -m pytest -q 2>&1 | tail -30
```

Target end state: **13 failed** — the same 13 names from §0 — and no others.

### 12.5 Test files that touch these features, and what to do with each

| File | Action |
|---|---|
| `tests/test_calling_menu_template_is_gone.py` | **`TestTheIvrMenuIsNotCollateral` (lines 162-169) must go.** It asserts `_SHARED_IVR_MENU`, `IVR_MENUS`, `IVR_DEFAULT_MENU`, `IVR_RESPONSES`, `_get_ivr_menu` SURVIVE, and that every IVR button has a reply. Phase 1 pinned them as out of scope; phase 2 deletes them. Delete the class and trim `IVR_KEEP_NAMES` (lines 49-57) to the four non-menu names that still must survive: `_react_thumbs_up`, `_is_auto_thumb_reaction_enabled`, `_is_postcall_wa_enabled`. Keep `TestTheDeletedTemplateIsGone`, `TestThePlaceholderCopyIsShared`, `TestThePlaceholderSendStaysOnMetaApi` untouched — they are the phase-1 guarantees and must keep passing. Add the five deleted IVR names to a new "deleted" parametrisation asserting `not hasattr`. |
| `tests/test_menus_are_deleted.py` | **`TestATappedRowStillAnswers` (197-211) must be rewritten.** `test_handle_list_reply_keeps_its_signature` and `test_handle_list_reply_sends_the_placeholder` both require `_handle_list_reply` to exist. Replace with assertions on the dispatch block: the `list_reply` branch calls `_send_menu_placeholder`, logs `list_reply_received`, and `_handle_list_reply` / `_handle_ivr_response` are **not** module attributes. Add `_handle_ivr_response`, `_handle_list_reply`, `_send_reply_buttons`, `_send_followup_buttons` to `DELETED_NAMES` (39-56). `TestEveryMenuIsGone`, `TestNobodyGetsSilence`, `TestNothingBecameUnreachable`, `TestTheRivalMenuIsGone` should all still pass unchanged — if `TestNothingBecameUnreachable` fails you deleted a keyword path that was load-bearing. |
| `tests/test_calling.py` | **`TestIVRMenuParity` (408-455) must go** — five tests reading `IVR_MENUS`, `IVR_DEFAULT_MENU`, `IVR_RESPONSES`. Delete the class. **Keep `TestIVRAutoPickup` (328-405)** — it pins pre_accept → accept → audio → terminate, which is the calling feature the owner said must survive. It must pass unchanged. |
| `tests/test_agent_surfaces.py` | `30` → `29` at line 65; drop `"send_whatsapp_list"` from `SENDERS` (66). |
| `tests/test_agent_ui_truth.py` | No edit, but it **fails** until `InternalChatTab.tsx:106` is removed. |
| `tests/test_business_api.py` | Delete `test_interactive_requires_object` (372-373). Keep the product_list test at 465 and `test_route_send_dispatch` (396-400). |
| `tests/test_notifications_domain.py` | Restate line 616 per §10 step 4. |
| `tests/test_outbound_whatsapp.py` | No edit expected. Line 218 mentions `wd_menu` inside a `_send_direct_api` payload fixture — a string, not a send; leave it or rename the fixture template, your call. Lines 121-138 (location_request, address_message) must keep passing. |
| `tests/test_own_prefill_triggers_menu.py` | No edit — read it and confirmed it touches no IVR, list or interactive symbol. |
| `tests/test_rcs_ivr_template_selection.py` | No edit — `rcsmenu` is the Sinch RCS template, a different channel, explicitly kept. |
| `tests/test_inbound_whatsapp.py` | No edit expected; line 301 only mentions IVR in a docstring about auto-👍. |

### 12.6 TypeScript

```
npx vitest run src/test/PerksPage.test.tsx   # 9 passed, after the §6a edit
npm run typecheck                            # InternalChatTab.tsx + internal-agent.tsx edits
```

### 12.7 Not in scope, do not do it

No `update-function-code`, no version publish, no `live` alias move. Deployment is a
separate authorised step (`lambda-snapstart-deploy`), and 58 of 65 functions serve from
the `live` alias, so nothing here reaches production until that happens.

---

## 13. Commit and push

Single-branch workflow: `stack` only, no feature branch.

Per the parallel-sessions rule 3b, the index may already be dirty with another
session's work — it was at plan time (five untracked `.agents/tasks/*` directories from
other sessions). **Use `git commit --only`:**

```
git status --short
git add <any NEW files, e.g. scripts/update_welcome_message_config.py> \
  && git commit --only <every path you edited, named individually> -F <message-file>
```

`--only` bounds the commit to the named paths regardless of what else is staged.
Never `git add .` / `-A` / `-u`. Then `git push origin stack`.

Suggested subject (≤70 chars): `Delete the last WhatsApp menu and interactive surface`
Body should name: the IVR button menu removal with the calling lifecycle intact, the two
voice-in `wd_menu` sends, the AI menu renderer and its tool, the two generic senders now
answering with an error, the `WA_TEMPLATE_NAME` default change with its two guards, the
two SystemConfig rows rewritten, and — explicitly — D1 and D2, so the next reader knows
`cta_url`, `flow`, `address_message` and `catalog_message` were kept on purpose.
