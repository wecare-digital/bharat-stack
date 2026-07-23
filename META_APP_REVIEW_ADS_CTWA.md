# Meta App Review — Ads that Click to WhatsApp (Marketing API)

App: **WECARE.DIGITAL** (App ID `2238810740192680`) · Business Portfolio `382642103987922`
Backend: `wecare-marketing-ads` Lambda → `POST https://api.wecare.digital/marketing-ads`
Console page: **DM → WhatsApp → Ads → WhatsApp (CTWA)** (`/dm/whatsapp/ctwa-ads`)

This app is a **server-to-server business tool**. It authenticates with a Meta
**System User token** (Business Manager admin), not Facebook Login. There is no
consumer login flow. All ads are created **PAUSED**; publishing is an explicit,
separate action that goes to Meta review before any spend.

---

## Permissions requested (advanced access)

| Permission | Why this app needs it |
|---|---|
| `ads_management` | Create and manage Ads that Click to WhatsApp campaigns, ad sets, ad creatives and ads in ad accounts the business owns/admins. |
| `ads_read` | Read campaign/ad set/ad status and delivery so the console can show the business the state of its own CTWA ads. |
| `pages_show_list` | List the Facebook Pages the business admins so the operator can pick the correct Page for the ad creative and ad set `promoted_object.page_id`. |
| `pages_read_engagement` | Read Page metadata (name, WhatsApp connection) needed to build the ad creative `object_story_spec` for the correct Page. |
| `pages_manage_ads` | Create Page-backed ad creatives (`object_story_spec` with the Page) that route the click to the business's WhatsApp number. |

All five are used only against ad accounts and Pages the **business owns or is
granted access to** — never third-party assets without permission.

---

## "How will this app use …" — copy-paste descriptions

### ads_management
> WECARE.DIGITAL is a WhatsApp Business messaging platform. This permission lets
> our operators create and manage "Ads that Click to WhatsApp" for our own
> business from our console. The app calls the Marketing API server-to-server
> with a System User token to create a campaign (`/act_{id}/campaigns`), an ad set
> with `destination_type=WHATSAPP` (`/act_{id}/adsets`), a Page-backed ad creative
> with a `WHATSAPP_MESSAGE` call-to-action (`/act_{id}/adcreatives`), and an ad
> (`/act_{id}/ads`). Ads are created paused; a separate publish action sets status
> ACTIVE and submits the ad to Meta review. The value to the user is being able to
> launch and pause lead-generating WhatsApp ads without leaving our platform.

### ads_read
> Used to read the status and delivery state of the business's own CTWA ads
> (`GET /act_{id}/ads`, `GET /{ad_id}`) so the console can display whether each ad
> is paused, in review, or active. Read-only; no other accounts are accessed.

### pages_show_list
> Used to list the Facebook Pages the business administers (`GET /{business}/owned_pages`)
> so the operator can select the correct Page when building a CTWA ad. Without it we
> cannot present the Page picker required to set the ad's `promoted_object.page_id`.

### pages_read_engagement
> Used to read basic Page metadata (name and whether a WhatsApp Business number is
> connected) needed to construct the ad creative for the correct Page and to warn
> the operator when the Page is not yet linked to WhatsApp.

### pages_manage_ads
> Used to create Page-backed ad creatives (`object_story_spec` referencing the
> business's Page) whose `WHATSAPP_MESSAGE` call-to-action opens a chat with the
> business's WhatsApp number. Necessary because CTWA ads are published on behalf of
> the Page.

### Marketing API Access Tier
> We request the standard Marketing API Access Tier to run the business's own
> Ads that Click to WhatsApp at production volume. We do not manage third-party ad
> accounts. We only read reports and manage ads for ad accounts the business owns
> (WECARE.DIGITAL Ads Account, `act_506155527842845`). The tier is needed for the
> rate limits required to create/manage/measure our CTWA campaigns.

**Marketing API Access Tier gate (≥500 calls, <15% error / ≥85% success):**
Exercise the endpoints from the console (or the backend) repeatedly:
`ad_accounts`, `pages`, `campaigns`, `ads`, `campaign_create` (PAUSED),
`adset_create`, `creative_create`, `ad_create`, `ad_status`. Each console action
is one Marketing API call. Creating and reading a handful of paused test
campaigns, then listing accounts/pages/ads on a loop, accrues the 500 successful
calls with a high success rate. Delete the paused test campaigns afterwards
(`DELETE /{campaign_id}`) — no spend occurs on paused objects.

---

## Screencast shot list (end-to-end user experience)

Record the real console (authenticated) at `https://stack.wecare.digital`:

1. Sign in (Cognito) → navigate **DM → WhatsApp → Ads → WhatsApp (CTWA)**.
2. Show the **ad account** and **Facebook Page** loaded from the Marketing API
   (`ad_accounts`, `pages`) — proves `ads_read` / `pages_show_list`.
3. Fill the create form: WhatsApp number (WABA1/WABA2), objective, daily budget,
   headline, primary text, greeting + autofill, optional image upload.
4. Click **Create ad (paused)** → toast "Ad created (PAUSED)". This runs
   campaign→adset→creative→ad (`ads_management`, `pages_manage_ads`).
5. Show the ad appearing in **Your ads** with status PAUSED (`ads_read`).
6. Click **Publish** → confirmation dialog → status goes to review
   (PENDING_REVIEW). Then **Pause** it again to avoid spend.
7. (Optional) Open Ads Manager in another tab to show the same ad object exists.

Keep it 60–90s. Narrate that this is a server-to-server System User integration
managing the business's own ads — no Facebook Login, no third-party assets.

---

## Prerequisite the reviewer should know
The Facebook Page used for the creative must have a **WhatsApp Business number
connected** (Business Suite → Page → Settings → WhatsApp). If it is not linked,
the Marketing API rejects the ad set with *"Page with WhatsApp Business account
required"*. This is one-time business setup, independent of the permissions above.
