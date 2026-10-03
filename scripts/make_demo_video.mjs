#!/usr/bin/env node
/**
 * make_demo_video.mjs — generate an .mp4 UI-walkthrough demo from a scene spec.
 *
 * ====================================================================
 * WHAT THIS IS (read before using for Meta App Review)
 * ====================================================================
 * This renders a scripted sequence of HTML "scenes" in headless Chrome,
 * captures one screenshot per frame on a fixed timer, and stitches them into
 * an H.264 .mp4 with ffmpeg. It is how the catalog_management /
 * ads_management / ads_mcp_management walkthrough videos under
 * s3://wecare-digital-get/o/app-review/ were produced.
 *
 * HONESTY NOTE — this is a *rendered walkthrough*, NOT a capture of a real
 * logged-in browser session. The data baked into a scene can be real (e.g.
 * live catalog/ad-account values pulled from the backend first), but the
 * frames are drawn by this tool, not recorded from the live app behind its
 * Cognito login. Meta reviewers can tell the difference and their guidance
 * ("incorporate the OAuth authorization flow", show the real end-to-end
 * experience) expects a genuine screen recording. Use this tool for:
 *   - internal review / storyboards
 *   - showing a flow the owner will then record for real
 * Do NOT present a rendered walkthrough as a live session recording.
 *
 * ====================================================================
 * REQUIREMENTS (already present on this Mac, verified 2026-10-03)
 * ====================================================================
 *   - Google Chrome at /Applications/Google Chrome.app  (headless via CDP)
 *   - ffmpeg on PATH (brew: /opt/homebrew/bin/ffmpeg)
 *   - Node 24+ (global WebSocket + fetch; no npm packages needed)
 *
 * ====================================================================
 * USAGE
 * ====================================================================
 *   node scripts/make_demo_video.mjs <spec.json> [--out <path.mp4>] [--fps 10] [--keep-frames]
 *
 * The spec is JSON:
 *   {
 *     "title": "catalog_management",         // used for default output name
 *     "width": 1280, "height": 860,
 *     "scenes": [
 *       { "html": "<div>...full page HTML...</div>", "holdMs": 2500 },
 *       { "html": "<div>...next state...</div>",      "holdMs": 2000 }
 *     ]
 *   }
 * Each scene's "html" is injected as document.body.innerHTML and held for
 * holdMs milliseconds (captured at the chosen fps). Scenes play in order.
 *
 * Build the scene HTML however you like — the app-review videos used inline
 * styles mirroring the real component markup, seeded with real values fetched
 * from the backend beforehand. Keep claims truthful: only show states the app
 * actually produces.
 *
 * ====================================================================
 * OUTPUT
 * ====================================================================
 *   - default: .scratch/demo-video/<title>.mp4  (gitignored scratch area)
 *   - override with --out
 *   - prints the final path + duration as JSON on stdout
 *
 * To publish for App Review (public, unlisted-but-reachable via CloudFront):
 *   aws s3 cp <path.mp4> s3://wecare-digital-get/o/app-review/<name>.mp4 \
 *       --content-type video/mp4 --region us-east-1
 *   # then the link is https://wecare.digital/get/o/app-review/<name>.mp4
 *
 * ====================================================================
 * SECURITY
 * ====================================================================
 *   - Never bake a token, secret, OTP, or full phone number into a scene.
 *   - Fetch any real data server-side first; pass only display-safe values in.
 *   - This tool makes NO network calls of its own beyond driving local Chrome.
 */

import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { join, resolve, basename } from 'node:path';
import http from 'node:http';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

function parseArgs(argv) {
  const a = { spec: null, out: null, fps: 10, keepFrames: false };
  const rest = argv.slice(2);
  for (let i = 0; i < rest.length; i++) {
    const t = rest[i];
    if (t === '--out') a.out = rest[++i];
    else if (t === '--fps') a.fps = Number(rest[++i]);
    else if (t === '--keep-frames') a.keepFrames = true;
    else if (!a.spec) a.spec = t;
  }
  return a;
}

function fail(msg) { console.error('make_demo_video: ' + msg); process.exit(1); }

async function main() {
  const args = parseArgs(process.argv);
  if (!args.spec) fail('usage: node scripts/make_demo_video.mjs <spec.json> [--out x.mp4] [--fps 10] [--keep-frames]');
  if (!existsSync(CHROME)) fail('Google Chrome not found at ' + CHROME);
  const spec = JSON.parse(readFileSync(resolve(args.spec), 'utf8'));
  const scenes = spec.scenes || [];
  if (!scenes.length) fail('spec has no scenes');
  const W = spec.width || 1280, H = spec.height || 860;
  const FPS = args.fps || 10;
  const title = (spec.title || basename(args.spec).replace(/\.json$/, '')).replace(/[^a-zA-Z0-9._-]/g, '_');

  const outDir = resolve('.scratch/demo-video');
  mkdirSync(outDir, { recursive: true });
  const framesDir = join(outDir, '.frames-' + title);
  rmSync(framesDir, { recursive: true, force: true });
  mkdirSync(framesDir, { recursive: true });
  const outPath = args.out ? resolve(args.out) : join(outDir, title + '.mp4');

  // --- serve the scene host over a real local HTTP server ---------------
  // (a data: URL blocks inline <script>; a real origin does not.)
  const PORT = 3200 + Math.floor(Math.random() * 300);
  const PAGE = `<!doctype html><html><head><meta charset=utf-8>
<style>body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111}</style>
</head><body><div id=root></div></body></html>`;
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end(PAGE);
  });
  await new Promise(r => server.listen(PORT, r));

  // --- launch headless Chrome with remote debugging ---------------------
  const DBG = 9400 + Math.floor(Math.random() * 300);
  const chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${DBG}`, '--disable-gpu',
    `--window-size=${W},${H}`, '--hide-scrollbars', '--no-first-run',
    '--no-default-browser-check', '--force-device-scale-factor=1',
    `--user-data-dir=/tmp/chrome-demo-${Date.now()}`, 'about:blank',
  ], { stdio: 'ignore' });

  async function wsUrl() {
    for (let i = 0; i < 40; i++) {
      try { const r = await fetch(`http://127.0.0.1:${DBG}/json/version`); const j = await r.json(); if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl; } catch {}
      await new Promise(r => setTimeout(r, 250));
    }
    throw new Error('Chrome CDP did not become ready');
  }
  const ws = new WebSocket(await wsUrl());
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const pend = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
  const send = (method, params = {}, sessionId) => { const i = ++id; const pl = { id: i, method, params }; if (sessionId) pl.sessionId = sessionId; ws.send(JSON.stringify(pl)); return new Promise(r => pend.set(i, r)); };

  const { targetInfos } = await send('Target.getTargets');
  const pg = targetInfos.find(t => t.type === 'page');
  const { sessionId: S } = await send('Target.attachToTarget', { targetId: pg.targetId, flatten: true });
  await send('Page.enable', {}, S);
  await send('Runtime.enable', {}, S);
  await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/` }, S);
  await new Promise(r => setTimeout(r, 1200));

  // --- play scenes, capturing one PNG per tick --------------------------
  let frame = 0;
  async function grab() {
    const { data } = await send('Page.captureScreenshot', { format: 'png' }, S);
    writeFileSync(join(framesDir, String(frame).padStart(5, '0') + '.png'), Buffer.from(data, 'base64'));
    frame++;
  }
  for (const sc of scenes) {
    const html = JSON.stringify(sc.html || '');
    await send('Runtime.evaluate', { expression: `document.getElementById('root').innerHTML = ${html};`, returnByValue: true }, S);
    const check = await send('Runtime.evaluate', { expression: `document.getElementById('root').children.length`, returnByValue: true }, S);
    if (!check.result || !check.result.value) console.error('warning: a scene rendered empty (check its html)');
    const end = Date.now() + (sc.holdMs || 2000);
    while (Date.now() < end) { await grab(); await new Promise(r => setTimeout(r, 1000 / FPS)); }
  }

  try { chrome.kill('SIGTERM'); } catch {}
  server.close(); ws.close();

  if (frame < 2) fail('captured too few frames; scenes likely rendered blank');

  // --- stitch with ffmpeg ----------------------------------------------
  await new Promise((res, rej) => {
    const ff = spawn('ffmpeg', ['-y', '-framerate', String(FPS), '-i', join(framesDir, '%05d.png'),
      '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart', outPath], { stdio: 'ignore' });
    ff.on('exit', c => c === 0 ? res() : rej(new Error('ffmpeg exited ' + c)));
    ff.on('error', rej);
  });

  if (!args.keepFrames) rmSync(framesDir, { recursive: true, force: true });
  console.log(JSON.stringify({ out: outPath, frames: frame, fps: FPS, seconds: +(frame / FPS).toFixed(1) }));
  process.exit(0);
}

main().catch(e => fail(e.message || String(e)));
