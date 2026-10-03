# make_demo_video.mjs — demo .mp4 generator

Turns a JSON "scene spec" into an H.264 `.mp4` by rendering each scene in
headless Chrome and stitching the frames with ffmpeg. This is the tool that
produced the Meta App Review walkthrough videos in
`s3://wecare-digital-get/o/app-review/`.

## ⚠️ Read first: what these videos are (and are not)

A rendered **walkthrough**, not a capture of a real logged-in session. The data
in a scene may be real (pull it from the backend first), but the frames are
drawn by this tool, not recorded from the live app behind Cognito login.

Meta App Review wants a genuine screen recording that **incorporates the OAuth
authorization flow** and shows the real end-to-end experience. Use this tool for
internal review and storyboards, or to show a flow the owner will then record
for real. Do **not** pass a rendered walkthrough off as a live recording.

## Prerequisites (present on this Mac)
- Google Chrome (`/Applications/Google Chrome.app`)
- `ffmpeg` on PATH
- Node 24+ (no npm packages needed)

## Run
```
node scripts/make_demo_video.mjs <spec.json> [--out path.mp4] [--fps 10] [--keep-frames]
```
Default output: `.scratch/demo-video/<title>.mp4` (gitignored). Prints
`{ out, frames, fps, seconds }` as JSON.

## Spec format
```json
{
  "title": "catalog_management",
  "width": 1280, "height": 860,
  "scenes": [
    { "html": "<div>...full page HTML for state 1...</div>", "holdMs": 2500 },
    { "html": "<div>...state 2...</div>",                     "holdMs": 2000 }
  ]
}
```
Each scene's `html` becomes `document.body` innerHTML and is held for `holdMs`.
Build the HTML with inline styles that mirror the real component so the frames
look like the actual UI. Seed real values (catalog ids, ad-account names) that
you fetched from the backend beforehand.

## Publish to S3 for App Review
```
aws s3 cp .scratch/demo-video/<name>.mp4 \
  s3://wecare-digital-get/o/app-review/<name>.mp4 \
  --content-type video/mp4 --region us-east-1
# public link: https://wecare.digital/get/o/app-review/<name>.mp4
```

## Security
- Never put a token, secret, OTP, or full phone number in a scene.
- Fetch real data server-side first; pass only display-safe values in.
- The tool makes no network calls of its own beyond driving local Chrome.

## Current App Review videos (regenerate by rebuilding the spec)
| Permission | S3 key | Honest scope of the video |
|---|---|---|
| catalog_management | `o/app-review/catalog_management-ui-walkthrough.mp4` | list → create → edit price → delete; real catalog data |
| ads_management | `o/app-review/ads_management-ui-walkthrough.mp4` | real ad accounts + Page → fill CTWA form → stops before create |
| ads_mcp_management | `o/app-review/ads_mcp_management-ui-walkthrough.mp4` | Connect → OAuth consent (config_id 1718783392517600) → authenticated; stops before a live MCP read (not enabled yet) |

The ad-hoc generator scripts under `.scratch/record_*_video.mjs` are superseded
by this tool; keep new specs in version control if a video needs to be
reproducible.
