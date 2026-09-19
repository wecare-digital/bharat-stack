# Deployed security headers are not being served — verified 2026-09-19

`DECISION_REQUIRED`. Editing `amplify.yml` does **not** fix this. The repository
file is overridden, and the overriding configuration does not work either.

## What was measured

```
$ curl -sSI https://stack.wecare.digital/
HTTP/2 200
server: AmazonS3
last-modified: Sat, 19 Sep 2026 11:20:19 GMT
via: 1.1 ...cloudfront.net (CloudFront)
```

No `Permissions-Policy`. No `X-Content-Type-Options`. No `Referrer-Policy`. No
`X-Frame-Options`. Same result on the Amplify default domain
`stack.d22dm4b0jn71jw.amplifyapp.com`.

The content is current — `last-modified` matches Amplify job **696**, commit
`6680a9fa`, `SUCCEED` — so this is not a stale-deployment artifact. The build is
deploying; the headers are simply absent.

## Three separate problems, in the order they bite

### 1. `next.config.js` headers are inert

The app is a static export (`artifacts.baseDirectory: out`). Next.js only serves
its `headers()` block when running as a server. So the `Permissions-Policy` in
`next.config.js` has never applied in production, despite being the file that
looks like it configures this.

### 2. The repository `amplify.yml` is overridden by an app-level build spec

`aws amplify get-app --app-id d22dm4b0jn71jw` returns a stored `buildSpec`, and it
is **not** the repository file — it runs `rm -f package-lock.json` where the repo
file runs `rm -rf node_modules/.cache`. When a build spec is stored on the app,
Amplify uses it and ignores `amplify.yml` in the repository.

Its `customHeaders` block declares only three headers:

| Header | In stored build spec | In repo `amplify.yml` |
|---|---|---|
| `Cache-Control` | yes | yes |
| `X-Frame-Options` | yes | yes |
| `X-Content-Type-Options` | yes | yes |
| `Referrer-Policy` | **no** | yes |
| `Permissions-Policy` | **no** | yes |

So the repo's `Permissions-Policy` was never in the configuration that actually
ran, regardless of its value.

### 3. Even the stored build spec's headers are not served

This is the part that makes the first two insufficient to explain the outcome.
`X-Content-Type-Options: nosniff` **is** in the stored build spec and is still
absent from the live response. `app.customHeaders` on the Amplify app is the empty
string.

So custom headers are not being applied by this app at all. Fixing the build spec
alone is therefore unlikely to be sufficient.

## Consequence for the browser softphone — smaller than it looks

With **no** `Permissions-Policy` header, the browser applies its default
allowlist, and the default for `microphone` is `self`. Same-origin
`getUserMedia()` is therefore permitted today, so the Plivo Browser SDK is **not**
currently blocked.

The real exposure is the opposite of the one in the original brief: `camera` and
`geolocation` are also defaulting to `self` rather than being denied. The intent
was to deny both.

This corrects the framing that the deployment "currently deploys
`microphone=()`". It does not deploy `microphone=()`; it deploys no such header at
all. Both statements imply a fix to `amplify.yml`, but only one of them is true,
and the difference decides whether the softphone is blocked.

## What has been changed in this repository

`amplify.yml` now declares `camera=(), microphone=(self), geolocation=()`, so the
repository is correct and self-consistent whenever the override is removed. This
is necessary but, per problem 3, not yet sufficient.

`scripts/verify_deployed_headers.py` asserts the **live response**, not the
config, and reports the config/live disagreement explicitly. A config assertion
could not have caught this, because the config was already right.

```
python scripts/verify_deployed_headers.py --url https://stack.wecare.digital/
```

Exit `0` compliant, `1` header missing or wrong, `2` request failed (not a pass).

## What is required to actually fix it — needs approval

All three are changes to a live Amplify app, not to this repository:

1. Remove the app-level build spec so the repository `amplify.yml` governs, or
   update the stored spec to include both missing headers.
2. Set the app's `customHeaders` attribute, which is currently empty.
3. Re-verify with the script above and invalidate the CloudFront cache.

`aws amplify update-app` on a production app is an infrastructure change with a
site-wide blast radius: a malformed spec breaks every subsequent build. Per
`.kiro/steering/maintenance-reporting.md` this needs pointwise confirmation, so it
has not been applied.

## Also found: `app.wecare.digital` is a different, stale deployment

| Host | Served by | Content date |
|---|---|---|
| `stack.wecare.digital` | Amplify app `d22dm4b0jn71jw`, branch `stack`, autoBuild on | 2026-09-19 (current) |
| `app.wecare.digital` | separate S3 + CloudFront | **2026-03-05** |

`app.wecare.digital` is six months stale and is **not** updated by a push to
`stack`. It matters because application code points at it as a live origin —
`IVR_MEDIA_BASE` in `plivo-answer`, the IVR audio asset the Plivo answer XML
plays, the WhatsApp template video, and the CORS origin several handlers send.

Those assets may well still be present and correct on that origin; this has not
been checked file by file. But any *new* asset published by a `stack` build will
not appear there, so a future IVR or template asset added to this repository would
404 at the URL the Lambda serves. Flagged, not fixed: repointing a live media
origin is outside this program's authorised scope.
