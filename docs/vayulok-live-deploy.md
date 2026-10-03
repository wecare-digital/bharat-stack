# VayuLok live page: deploy note

This note is for the owner. It explains exactly what has to be set, and where, for the live map
and the Air Quality, Weather, Solar and Pollen panels on `/vayulok/` to render on a deployed
environment. None of it lives in the repository, and none of it is a code change. The page is
already wired; it only needs the one environment variable set on the branch you deploy.

## 1. Set the environment variable on the target Amplify branch

The page reads its Google key from a single build-time environment variable:

```
NEXT_PUBLIC_GOOGLE_MAPS_KEY
```

Set it in the **Amplify branch environment** for the branch you are deploying, in the Amplify
console for app `d22dm4b0jn71jw`
([AWS Amplify console](https://console.aws.amazon.com/amplify/)). Set it to the
referrer-restricted Google **browser** key named **"WECARE Unified Google API Key"** in the Google
Cloud console. The owner enters the value in the Amplify console; it is **never** committed to the
repository, never printed to a log, and never passed on a command line. The value is not reproduced
anywhere in this document on purpose. The page reads the key only inside a client effect, so with
`output: 'export'` it is placed into a JavaScript chunk at build time and never into the
pre-rendered HTML.

## 2. The build has a credential gate, and a browser key passes it

The production build runs `scripts/verify_public_bundle_secrets.py` (wired into `amplify.yml`).
That gate **fails the build** if a server-side key fingerprint is found inlined in the exported
bundle. A genuine referrer-restricted browser key is public by design and **passes** the gate: it
is meant to ship to the browser, and Google enforces it by HTTP referrer rather than by secrecy.
Do not weaken or bypass the gate to get a key through. If the gate fails, the key you set is the
wrong kind of key.

## 3. The key's referrer allow-list and API restrictions

The browser key is restricted two ways in the Google Cloud console, and both must be correct:

- **Allowed referrers** must include `https://wecare.digital/*` and `https://*.wecare.digital/*`.
  These are already set per [docs/CREDENTIAL-ROTATION-RUNBOOK.md](./CREDENTIAL-ROTATION-RUNBOOK.md).
- **API restrictions** must enable all of: **Maps JavaScript API**, **Air Quality API**,
  **Weather API**, **Solar API**, **Pollen API**, and **Places API / Geocoding API**. The owner
  confirms these are enabled on the key in the
  [Google Cloud console](https://console.cloud.google.com/google/maps-apis/credentials). A missing
  API restriction shows as that one panel silently not rendering while the rest of the page works.

## 4. Which branch to deploy for a preview

Point Amplify at the branch you want to preview and make sure **that branch carries the
`NEXT_PUBLIC_GOOGLE_MAPS_KEY` variable** (Amplify branch environments are per branch; a variable
set on one branch is not inherited by another). The production branch for app `d22dm4b0jn71jw` is
`stack`. For a preview of this work, deploy the feature branch `feat/vayulok-live-page` (or merge
it to `stack`) and set the variable on whichever branch Amplify builds. The deployed URL must be a
`*.wecare.digital` origin for the key to be accepted (see the next section).

## 5. Live panels only render on a `*.wecare.digital` origin

Because the key is referrer-restricted, Google only honours requests from `https://wecare.digital`
and its subdomains. This means:

- The map, the AQI/PM2.5 heatmap, Weather, Solar and Pollen render **only** on a deployed
  `*.wecare.digital` Amplify origin.
- A local `htmlpreview`, `localhost`, or CI run will **not** show the map, and that is **expected,
  not a bug**. There is no key in CI, the origin is not `*.wecare.digital`, and the referrer
  restriction would reject the calls even if there were. CI verifies degradation and wiring, not a
  live map; the owner verifies the live map on a deployed `*.wecare.digital` preview.

## 6. Honest degradation when the variable is unset

If `NEXT_PUBLIC_GOOGLE_MAPS_KEY` is unset, the page renders the rotating-word hero and the content
shell (Subscribe, Contribute, Share) **without** the map and without the live panels, and makes
**zero** Google network calls. There is no spinner and no `--` placeholder: a value only appears
once it has actually arrived from the API, and absent data simply omits its field. This is what
lets the production build pass with the variable unset, which is how the build proves no key is
inlined.

## 7. India SKUs in use, and the cost note

The page is scoped to India for pricing. The India-SKU Google services it calls are:

- **Maps JavaScript API** - the base map, scoped to an India `latLngBounds` restriction so it
  cannot be panned off the product's area, with Places/Geocoding search restricted to
  `country: in` / `region: in`.
- **Air Quality API** - current conditions (India CPCB local AQI preferred), and the heatmap tiles.
- **Weather API** - current conditions.
- **Solar API** - Building Insights for the selected address.
- **Pollen API** - the one-day forecast.

Cost controls built into the page:

- **The AQI/PM2.5 heatmap loads on user action only.** The tile overlay is created and its tiles
  requested **only** when the reader presses an AQI or PM2.5 layer button. It is never requested on
  page load, so a visitor who never touches the control is never billed for heatmap tiles.
- **Calls are debounced and cached.** Place search is debounced (~300 ms) so typing does not fire a
  request per keystroke, and the Air/Weather/Solar/Pollen results are cached per location, so
  re-selecting a place already viewed costs nothing.
