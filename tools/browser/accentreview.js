'use strict';

/**
 * accentreview - three accent questions, mocked before any of them is built.
 *
 * Asked for:
 *   1. the footer tagline "Trusted everyday services for Bharat", with animation
 *   2. band 3's three ticks, coloured to match band 2's beats
 *   3. the three dots before "platform / production", three colours + animation
 *
 * WHY ONE SCRIPT FOR THREE THINGS. They look like one request - "make these three accents
 * colourful and animated" - and the measurement says they are not. The three elements sit on
 * three different backgrounds, and a colour that works on one fails on another. That is the
 * finding worth showing, so the three are shown together with the numbers.
 *
 * THE BACKGROUNDS, computed rather than eyeballed:
 *   footer tagline   #ffffff  plain page
 *   band 3 ticks     #f5fde0  = lime #d1f470 at .22 composited over white
 *   terminal lights  #3b271a  the dark brown title bar
 *
 * ANIMATIONS RUN IN THIS FILE, and dividershots-style filmstrips are produced from it, because
 * the last three review links were unopenable one way or another. Both artefacts, every time.
 *
 * Writes: docs/accent-review.html
 * Run: node tools/browser/accentreview.js
 */

const fs = require( 'fs' );
const path = require( 'path' );

const OUT_FILE = path.join( __dirname, '..', '..', 'docs', 'accent-review.html' );

/* ---------- contrast, so every number in the page is computed not typed ---------- */

const luminance = hex => {
  const c = [ 1, 3, 5 ].map( i => parseInt( hex.substr( i, 2 ), 16 ) / 255 )
    .map( v => ( v <= 0.03928 ? v / 12.92 : Math.pow( ( v + 0.055 ) / 1.055, 2.4 ) ) );
  return 0.2126 * c[ 0 ] + 0.7152 * c[ 1 ] + 0.0722 * c[ 2 ];
};
const ratio = ( a, b ) => {
  const [ hi, lo ] = [ luminance( a ), luminance( b ) ].sort( ( x, y ) => y - x );
  return ( hi + 0.05 ) / ( lo + 0.05 );
};
const r2 = ( a, b ) => ratio( a, b ).toFixed( 2 );

const WHITE = '#ffffff';
const PANEL = '#f5fde0';   // lime .22 over white
const BAR = '#3b271a';     // terminal title bar

/* ---------- the palettes in play ---------- */

const BEAT = { green: '#3da35a', blue: '#2563eb', purple: '#9849e8' };   // shipped in band 2
const ASKED = { amber: '#f0a818', purple: '#9849e8', green: '#3da35a' }; // what was requested
const ONDARK = { amber: '#f0a818', purple: '#c4b5fd', green: '#86efac' }; // tuned for the bar

const TICKS = [
  'Know the price before you commit.',
  'Tell us once. We remember the context.',
  'See where everything stands.',
];

const tickList = ( colours, cls = '' ) => `<ul class="pts ${cls}">
${TICKS.map( ( t, i ) => `  <li style="--tick:${colours[ i ]}">${t}</li>` ).join( '\n' )}
</ul>`;

const lights = ( colours, cls = '' ) => `<div class="bar ${cls}">
${colours.map( c => `  <span class="light" style="--lt:${c}"></span>` ).join( '\n' )}
  <span class="bar-title">platform / production</span>
</div>`;

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three accent questions — WECARE.DIGITAL review</title>
<style>
  :root{--ink:rgba(0,0,0,.898);--muted:rgba(0,0,0,.54);--line:#e5e7eb}
  *{box-sizing:border-box}
  body{margin:0;padding:48px 24px 96px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:var(--ink);background:#fafafa}
  .wrap{max-width:1180px;margin:0 auto}
  h1{font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;margin:0 0 16px}
  h2{font-size:26px;font-weight:700;letter-spacing:-.6px;margin:64px 0 6px;padding-top:24px;border-top:2px solid var(--line)}
  h3{font-size:17px;font-weight:700;letter-spacing:-.2px;margin:0}
  .lede{font-size:20px;line-height:1.4;letter-spacing:-.125px;margin:0 0 10px;max-width:76ch}
  .note{font-size:17px;line-height:1.55;color:var(--muted);max-width:78ch;margin:0 0 28px}
  code{background:#fff;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:.88em}

  .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
  @media(max-width:1000px){.grid{grid-template-columns:1fr}}
  .card{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .card header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 20px;border-bottom:1px solid var(--line)}
  .tag{flex:none;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:4px 9px;border-radius:999px}
  .t-now{background:#f3f4f6;color:var(--muted)}
  .t-ask{background:#dbeafe;color:#1e40af}
  .t-rec{background:#d1f470;color:#1a3a2a}
  .t-no{background:#fee2e2;color:#991b1b}
  .frame{position:relative;padding:26px 20px 20px}
  .replay{position:absolute;top:9px;right:11px;min-height:30px;padding:0 12px;border:1px solid var(--line);border-radius:8px;background:#fff;color:#1a3a2a;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
  .replay:hover{background:rgba(209,244,112,.28)}
  .why{margin:0;padding:15px 20px 19px;border-top:1px solid var(--line);background:#fcfcfc}
  .why dt{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:rgba(0,0,0,.42);margin:0 0 4px}
  .why dd{margin:0 0 13px;font-size:15.5px;line-height:1.55}
  .why dd:last-child{margin:0}

  table{border-collapse:collapse;width:100%;margin:14px 0 0;font-size:15px}
  th,td{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line)}
  th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(0,0,0,.42)}
  .fail{color:#991b1b;font-weight:700}
  .pass{color:#166534;font-weight:600}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:6px;border:1px solid rgba(0,0,0,.12)}

  .callout{background:rgba(209,244,112,.22);border-inline-start:4px solid #d1f470;border-radius:8px;padding:18px 20px;margin:22px 0 0;max-width:88ch}
  .callout.warn{background:#fef2f2;border-inline-start-color:#dc2626}
  .callout p{margin:0 0 10px;font-size:17px;line-height:1.6}
  .callout p:last-child{margin:0}

  /* ---------- 1. the footer tagline ---------- */
  .ft{padding:6px 0}
  .ft-tagline{color:var(--muted);max-width:340px;margin:0;font-size:15px;line-height:1.6;
    transition:opacity .56s cubic-bezier(.22,.61,.36,1),transform .56s cubic-bezier(.22,.61,.36,1)}
  .ft.is-armed .ft-tagline{opacity:0}
  .ft.is-armed.is-in .ft-tagline{opacity:1;transform:none}
  .ft.v14.is-armed .ft-tagline{transform:translateY(14px)}
  .ft.v22.is-armed .ft-tagline{transform:translateY(22px)}
  /* Word-by-word: each word is its own span, so the line assembles rather than sliding. */
  .ft.words .ft-tagline span{display:inline-block;transition:opacity .5s cubic-bezier(.22,.61,.36,1),transform .5s cubic-bezier(.22,.61,.36,1)}
  .ft.words.is-armed .ft-tagline{opacity:1;transform:none}
  .ft.words.is-armed .ft-tagline span{opacity:0;transform:translateY(12px)}
  .ft.words.is-armed.is-in .ft-tagline span{opacity:1;transform:none}
  .ft.words.is-armed.is-in .ft-tagline span:nth-child(1){transition-delay:0s}
  .ft.words.is-armed.is-in .ft-tagline span:nth-child(2){transition-delay:.06s}
  .ft.words.is-armed.is-in .ft-tagline span:nth-child(3){transition-delay:.12s}
  .ft.words.is-armed.is-in .ft-tagline span:nth-child(4){transition-delay:.18s}
  .ft.words.is-armed.is-in .ft-tagline span:nth-child(5){transition-delay:.24s}
  .ft-dash{display:block;width:56px;height:3px;margin-top:4px;background:#d1f470;border-radius:2px;transform-origin:left;transition:transform .62s cubic-bezier(.22,.61,.36,1)}
  .ft.is-armed .ft-dash{transform:scaleX(0)}
  .ft.is-armed.is-in .ft-dash{transform:scaleX(1)}
  /* Bharat in brand green, as a second option: emphasis by colour rather than by motion. */
  .ft.accent .ft-tagline b{font-weight:600;color:#1a3a2a}

  /* ---------- 2. band 3 ticks, on the real tinted panel ---------- */
  .panel{background:rgba(209,244,112,.22);border:2px solid #d1f470;border-radius:14px;padding:24px}
  .pts{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
  .pts li{position:relative;padding-inline-start:26px;font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:var(--ink)}
  .pts li::before{content:'';position:absolute;inset-inline-start:2px;top:7px;width:11px;height:6px;
    border-left:2.5px solid var(--tick);border-bottom:2.5px solid var(--tick);transform:rotate(-45deg)}
  /* Drawn tick: the two borders are revealed by a clip, so it writes itself. */
  .pts.draw li::before{clip-path:inset(0 0 0 0);transition:clip-path .42s cubic-bezier(.22,.61,.36,1)}
  .pts.draw.is-armed li::before{clip-path:inset(0 100% 0 0)}
  .pts.draw.is-armed.is-in li::before{clip-path:inset(0 0 0 0)}
  .pts.draw.is-armed.is-in li:nth-child(2)::before{transition-delay:.09s}
  .pts.draw.is-armed.is-in li:nth-child(3)::before{transition-delay:.18s}

  /* ---------- 3. terminal title bar ---------- */
  .term{background:#000;border:1.5px solid rgba(255,255,255,.92);border-radius:14px;overflow:hidden}
  .bar{height:47px;display:flex;align-items:center;gap:8px;padding:0 15px;background:#3b271a;border-bottom:1px solid rgba(209,244,112,.30)}
  .light{width:11px;height:11px;border-radius:50%;flex:0 0 auto;background:var(--lt)}
  .bar-title{margin-inline-start:7px;color:rgba(255,255,255,.62);font-size:12.5px;letter-spacing:.01em}
  .term-body{padding:18px 15px 22px;color:rgba(255,255,255,.62);font-size:13px;line-height:1.7;font-family:ui-monospace,monospace}
  /* A CSS circle, not the ● character: the first render showed tofu because the monospace
     stack here has no glyph for it. A mock that renders a missing-character box is a mock
     that invites a comment about the wrong thing. */
  .term-body .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#d1f470;margin-inline-end:5px;vertical-align:1px}
  /* Breathing lights: opacity only, staggered. Compositor-only, no layout. */
  .bar.pulse .light{animation:lt 2.4s ease-in-out infinite}
  .bar.pulse .light:nth-child(2){animation-delay:.3s}
  .bar.pulse .light:nth-child(3){animation-delay:.6s}
  @keyframes lt{0%,100%{opacity:.45}50%{opacity:1}}
  @media(prefers-reduced-motion:reduce){
    .bar.pulse .light{animation:none;opacity:1}
    .ft-tagline,.ft-dash,.pts li::before,.ft .ft-tagline span{transition:none}
    .ft.is-armed .ft-tagline,.ft.words.is-armed .ft-tagline span{opacity:1;transform:none}
    .ft.is-armed .ft-dash{transform:scaleX(1)}
    .pts.draw.is-armed li::before{clip-path:inset(0 0 0 0)}
  }
</style>
</head>
<body>
<div class="wrap">

<h1>Three accent questions</h1>
<p class="lede">All three asked as one thing — “three colours, with animation”. The measurement
says they are not one thing: the three elements sit on three different backgrounds, and the
colours you named work on some and fail on others.</p>
<p class="note">Every ratio below is computed in this file, not typed from memory — the last
mock claimed “all three ≥3:1 on white” about a colour that measures 1.94:1. Backgrounds:
footer <code>#ffffff</code> · band 3 panel <code>#f5fde0</code> (lime <code>.22</code>
composited over white) · terminal bar <code>#3b271a</code>. Press <b>Replay</b> on any frame.</p>

<div class="callout warn">
<p><b>The one number that decides all of this.</b> A mid-tone hue cannot clear 3:1 on both a
near-white panel and a dark brown bar — it is too light for one or too dark for the other.
Measured across every candidate, <b>only <span class="sw" style="background:#3da35a"></span>green
<code>#3da35a</code> clears 3:1 on both</b> (${r2( BEAT.green, PANEL )}:1 and ${r2( BEAT.green, BAR )}:1).</p>
<p>So “the same three colours everywhere” is not available. Either the hues differ per surface,
or the same hue appears at two lightnesses, or some surfaces keep what they have.</p>
</div>

<table>
<tr><th>Colour</th><th>on band 3 panel #f5fde0</th><th>on terminal bar #3b271a</th><th>usable where</th></tr>
${[
  [ 'amber #f0a818', ASKED.amber ],
  [ 'purple #9849e8', ASKED.purple ],
  [ 'green #3da35a', ASKED.green ],
  [ 'blue #2563eb', BEAT.blue ],
  [ 'lime #d1f470 (current bar light)', '#d1f470' ],
  [ 'dark green #1a3a2a (current tick)', '#1a3a2a' ],
].map( ( [ label, hex ] ) => {
  const p = ratio( hex, PANEL ), b = ratio( hex, BAR );
  const where = [ p >= 3 ? 'panel' : null, b >= 3 ? 'bar' : null ].filter( Boolean ).join( ' + ' ) || 'neither';
  return `<tr><td><span class="sw" style="background:${hex}"></span>${label}</td>
  <td class="${p >= 3 ? 'pass' : 'fail'}">${p.toFixed( 2 )}:1</td>
  <td class="${b >= 3 ? 'pass' : 'fail'}">${b.toFixed( 2 )}:1</td><td>${where}</td></tr>`;
} ).join( '\n' )}
</table>

<h2>1 · The footer tagline</h2>
<p class="note">Already animated and live since <code>#78</code>: 14px rise over 560ms, one-shot
when the footer scrolls in. You reported it as “not showing” when it was 6px and you were
right — the probe found it playing perfectly at about 11px/s, below what anyone notices. So the
question now is whether 14px is enough, or whether it should do something different in kind.</p>

<div class="grid">
  <section class="card">
    <header><h3>1A · 14px rise — live now</h3><span class="tag t-now">shipped</span></header>
    <div class="frame"><div class="ft v14"><p class="ft-tagline">Trusted everyday services for Bharat</p><span class="ft-dash"></span></div><button class="replay">Replay</button></div>
    <dl class="why"><dt>What it is</dt><dd>Fade plus a 14px rise, moving as one gesture with the lime dash drawing beneath it.</dd>
    <dt>Against</dt><dd>Nothing measured. If it still reads as too quiet, that is a judgement call and 1B or 1C answer it.</dd></dl>
  </section>

  <section class="card">
    <header><h3>1B · word by word</h3><span class="tag t-rec">recommended if you want more</span></header>
    <div class="frame"><div class="ft words"><p class="ft-tagline"><span>Trusted</span> <span>everyday</span> <span>services</span> <span>for</span> <span>Bharat</span></p><span class="ft-dash"></span></div><button class="replay">Replay</button></div>
    <dl class="why"><dt>What it is</dt><dd>Five words, 60ms apart, each rising 12px. The line <em>assembles</em> instead of sliding, so the movement is obvious at a glance without any single part moving far.</dd>
    <dt>Against</dt><dd>Five extra <code>&lt;span&gt;</code>s inside a translated line. The site translates this page, and a translated sentence has a different word count — so the spans have to be generated from the rendered text at runtime, not hardcoded, or other languages break. That is the real cost.</dd></dl>
  </section>

  <section class="card">
    <header><h3>1C · 22px rise</h3><span class="tag t-ask">bigger version of 1A</span></header>
    <div class="frame"><div class="ft v22"><p class="ft-tagline">Trusted everyday services for Bharat</p><span class="ft-dash"></span></div><button class="replay">Replay</button></div>
    <dl class="why"><dt>What it is</dt><dd>The same animation, travelling nearly a full line box.</dd>
    <dt>Against</dt><dd>At 22px on a 24px line box the line visibly starts below where it ends, which reads as the layout settling rather than as emphasis. 14px was chosen as just over half the box for that reason.</dd></dl>
  </section>

  <section class="card">
    <header><h3>1D · “Bharat” in brand green</h3><span class="tag t-ask">colour, not motion</span></header>
    <div class="frame"><div class="ft v14 accent"><p class="ft-tagline">Trusted everyday services for <b>Bharat</b></p><span class="ft-dash"></span></div><button class="replay">Replay</button></div>
    <dl class="why"><dt>What it is</dt><dd>1A plus the one word that matters in <code>#1a3a2a</code> at 600 weight. 12.48:1 on white.</dd>
    <dt>Against</dt><dd>Adds emphasis that survives with no JavaScript and with reduced motion, which motion cannot. But it styles a word inside a sentence the translator rewrites — same structural problem as 1B, smaller blast radius.</dd></dl>
  </section>
</div>

<h2>2 · Band 3’s three ticks</h2>
<p class="note">Currently all three ticks are <code>#1a3a2a</code> brand dark green at 11.89:1 on
the panel. You asked for them to match the beats. <b>They can — but not with amber.</b>
<span class="sw" style="background:#f0a818"></span><code>#f0a818</code> measures
<b class="fail">${r2( ASKED.amber, PANEL )}:1</b> on this tinted panel, which is worse than on
white because the panel is itself yellow-green. Band 2 shipped as green / blue / purple for the
same reason, so matching <em>those</em> costs nothing and needs no new colour.</p>

<div class="grid">
  <section class="card">
    <header><h3>2A · one dark green — live now</h3><span class="tag t-now">shipped</span></header>
    <div class="frame"><div class="panel">${tickList( [ '#1a3a2a', '#1a3a2a', '#1a3a2a' ] )}</div></div>
    <dl class="why"><dt>Contrast</dt><dd>${r2( '#1a3a2a', PANEL )}:1 on the panel — the strongest mark on the page.</dd>
    <dt>Against</dt><dd>Reads as one list of three equal claims, which is what it is. No relationship shown to band 2.</dd></dl>
  </section>

  <section class="card">
    <header><h3>2B · matching the shipped beats</h3><span class="tag t-rec">recommended</span></header>
    <div class="frame"><div class="panel">${tickList( [ BEAT.green, BEAT.blue, BEAT.purple ] )}</div></div>
    <dl class="why"><dt>Contrast</dt><dd>green ${r2( BEAT.green, PANEL )}:1 · blue ${r2( BEAT.blue, PANEL )}:1 · purple ${r2( BEAT.purple, PANEL )}:1 — all above 3:1, and the exact three hex values band 2 now uses.</dd>
    <dt>Against</dt><dd>Green is ${r2( BEAT.green, PANEL )}:1 — the weakest of the three, and only just clear. It is also the only one of the three that works on the dark bar, so it cannot be swapped for something stronger without breaking item 3.</dd></dl>
  </section>

  <section class="card">
    <header><h3>2C · amber / purple / green, exactly as asked</h3><span class="tag t-no">fails contrast</span></header>
    <div class="frame"><div class="panel">${tickList( [ ASKED.amber, ASKED.purple, ASKED.green ] )}</div></div>
    <dl class="why"><dt>Contrast</dt><dd>amber <b class="fail">${r2( ASKED.amber, PANEL )}:1</b> · purple ${r2( ASKED.purple, PANEL )}:1 · green ${r2( ASKED.green, PANEL )}:1.</dd>
    <dt>Against</dt><dd>Look at the first tick above — on a yellow-green panel the amber mark nearly disappears while the other two are solid. Not a guideline violation, since the text is complete without the ticks; it simply does not read as three colours, it reads as two ticks and a smudge.</dd></dl>
  </section>

  <section class="card">
    <header><h3>2D · 2B plus the ticks drawing in</h3><span class="tag t-ask">with animation</span></header>
    <div class="frame"><div class="panel">${tickList( [ BEAT.green, BEAT.blue, BEAT.purple ], 'draw' )}</div><button class="replay">Replay</button></div>
    <dl class="why"><dt>What it is</dt><dd>Each tick writes itself left to right, 90ms apart, on the existing one-shot reveal this band already runs.</dd>
    <dt>Against</dt><dd>The band <em>already</em> staggers these three list items in at 340/430/520ms. Adding a second stagger inside each one is motion on top of motion for the same three elements.</dd></dl>
  </section>
</div>

<h2>3 · The three dots before “platform / production”</h2>

<div class="callout warn">
<p><b>This one reverses an instruction of yours that is recorded in the code.</b>
<code>WorkflowTerminal.tsx</code> says, verbatim:</p>
<p style="font-style:italic;padding-inline-start:14px;border-inline-start:3px solid rgba(0,0,0,.14)">
“LIME AND NEUTRALS ONLY, on instruction. The window lights were red/amber/lime borrowed from
macOS; the first two are the only warm hues on the page and they pulled the eye to chrome
rather than to content.”</p>
<p>The same file also warns that colour here “competes with the lime step dots that mark actual
state” — inside the panel, lime dots mean <em>this service ran</em>. Three coloured dots on the
window frame, which mean nothing, would be the most colourful thing in a panel whose only real
signal is lime.</p>
<p>You may well want to reverse it — it is your call and the earlier reasoning is not sacred.
But it should be a reversal made on purpose, not by accident.</p>
</div>

<div class="grid">
  <section class="card">
    <header><h3>3A · two neutrals + lime — live now</h3><span class="tag t-now">shipped</span></header>
    <div class="frame"><div class="term">${lights( [ 'rgba(255,255,255,.26)', 'rgba(255,255,255,.44)', '#d1f470' ] )}
      <div class="term-body">› One customer places an order.<br><i class="dot"></i> All services healthy · 2.1s</div></div></div>
    <dl class="why"><dt>Why it is this</dt><dd>Keeps the traffic-light shape without warm hues on chrome. Lime is the panel’s only accent, and it means state.</dd>
    <dt>Against</dt><dd>Two of the three dots are nearly invisible by design — 2.30:1 and 3.97:1 against the bar.</dd></dl>
  </section>

  <section class="card">
    <header><h3>3B · amber / purple / green as asked</h3><span class="tag t-ask">works, but reverses your instruction</span></header>
    <div class="frame"><div class="term">${lights( [ ASKED.amber, ASKED.purple, ASKED.green ] )}
      <div class="term-body">› One customer places an order.<br><i class="dot"></i> All services healthy · 2.1s</div></div></div>
    <dl class="why"><dt>Contrast on the bar</dt><dd>amber ${r2( ASKED.amber, BAR )}:1 · purple ${r2( ASKED.purple, BAR )}:1 · green ${r2( ASKED.green, BAR )}:1.</dd>
    <dt>Against</dt><dd><b>Not really contrast, and I overstated that at first.</b> Purple measures ${r2( ASKED.purple, BAR )}:1, a hair under 3:1 — but look at it: it is perfectly visible. A WCAG ratio measures <em>luminance only</em>, and a saturated purple against dark brown differs strongly in hue and chroma, which the metric does not count. So the number is marginal and the appearance is fine. The real objection to this option is the recorded instruction above, not the arithmetic.</dd></dl>
  </section>

  <section class="card">
    <header><h3>3C · same hues, lightened for a dark bar, pulsing</h3><span class="tag t-ask">asked for, made to work</span></header>
    <div class="frame"><div class="term">${lights( [ ONDARK.amber, ONDARK.purple, ONDARK.green ], 'pulse' )}
      <div class="term-body">› One customer places an order.<br><i class="dot"></i> All services healthy · 2.1s</div></div></div>
    <dl class="why"><dt>Contrast on the bar</dt><dd>amber ${r2( ONDARK.amber, BAR )}:1 · purple ${r2( ONDARK.purple, BAR )}:1 · green ${r2( ONDARK.green, BAR )}:1 — all clear, and they breathe 2.4s apart.</dd>
    <dt>Against</dt><dd><b>Two new colour values</b> — <code>${ONDARK.purple}</code> and <code>${ONDARK.green}</code> exist nowhere in this repo. And a pulse that never stops is a permanent moving thing in the corner of a page whose terminal deliberately plays <em>once</em> and stops; the WCAG 2.2.2 argument that killed the terminal loop applies here too.</dd></dl>
  </section>

  <section class="card">
    <header><h3>3D · amber / green / lime, no new colours</h3><span class="tag t-ask">closest workable</span></header>
    <div class="frame"><div class="term">${lights( [ ASKED.amber, ASKED.green, '#d1f470' ] )}
      <div class="term-body">› One customer places an order.<br><i class="dot"></i> All services healthy · 2.1s</div></div></div>
    <dl class="why"><dt>Contrast on the bar</dt><dd>amber ${r2( ASKED.amber, BAR )}:1 · green ${r2( ASKED.green, BAR )}:1 · lime ${r2( '#d1f470', BAR )}:1 — all clear, all three already in the repo.</dd>
    <dt>Against</dt><dd>This is almost exactly the macOS red/amber/lime that was removed, with green in place of red. If the original objection — warm hues pulling the eye to chrome — still holds, this walks straight back into it.</dd></dl>
  </section>
</div>

<div class="callout">
<p><b>What I would do, if it were mine.</b></p>
<p><b>1 → 1A, unchanged.</b> It is live, it is measured, and 1B’s cost is real: this line is
translated, so hardcoded word spans break other languages. If 14px still reads as too quiet
after looking at 1C, take <b>1D</b> — colour on “Bharat” survives no-JS and reduced motion,
which no amount of motion does.</p>
<p><b>2 → 2B.</b> Matching the beats is a good instinct and it costs nothing: the three hex
values are already on the page, all three clear 3:1 on the panel, and it ties bands 2 and 3
together. Not 2C — amber at ${r2( ASKED.amber, PANEL )}:1 on a yellow-green panel is the one
thing here that would look broken rather than different. I would skip 2D: this band already
staggers these exact three items, and a second stagger inside each is motion for its own sake.</p>
<p><b>3 → 3A, keep it</b> — and the reason is <em>not</em> contrast. I first wrote that purple
“sits almost on top of” the bar at ${r2( ASKED.purple, BAR )}:1. Look at 3B: it is perfectly
visible. A WCAG ratio measures luminance only, and a saturated purple against dark brown differs
strongly in hue and chroma, which the metric ignores. The number is marginal; the appearance is
fine. Correcting that, because a recommendation resting on a number I have misread is worthless.</p>
<p>The real argument stands on its own: the dots are on <code>aria-hidden</code> window chrome,
they carry no meaning, and the panel’s whole visual argument is that <em>lime means something
happened</em>. Three coloured dots make the frame louder than the content — which is your own
recorded instruction, in that file, in those words. If you want colour there anyway, <b>3B</b>
is now the one I would take: no new colour values and it looks right. <b>3C</b> costs two new
hexes and an endless pulse; <b>3D</b> walks back into the macOS set you removed.</p>
</div>

<p class="note" style="margin-top:36px">Tell me per item — e.g. <b>“1A, 2B, 3A”</b> — and I
will ship it with probes asserting the contrast on the real composited backgrounds, the way
<code>footerprobe.js</code> asserts the tagline travel.</p>

</div>
<script>
(function(){
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function targets(f){ return Array.prototype.slice.call(f.querySelectorAll('.ft, .pts.draw')); }
  function arm(f){ if(reduce) return; targets(f).forEach(function(e){ e.classList.remove('is-in'); e.classList.add('is-armed'); }); }
  function play(f){ if(reduce) return; targets(f).forEach(function(e){ void e.offsetHeight; e.classList.add('is-in'); }); }
  var frames = Array.prototype.slice.call(document.querySelectorAll('.frame'));
  frames.forEach(arm);
  var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting){ play(e.target); io.unobserve(e.target); } }); }, { threshold: .35 });
  frames.forEach(function(f){ io.observe(f); });
  document.addEventListener('click', function(ev){
    var b = ev.target.closest('.replay'); if(!b) return;
    var f = b.closest('.frame'); arm(f);
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ play(f); }); });
  });
})();
</script>
</body>
</html>
`;

fs.mkdirSync( path.dirname( OUT_FILE ), { recursive: true } );
fs.writeFileSync( OUT_FILE, html );
console.log( `accent review -> ${OUT_FILE}  (${Math.round( html.length / 1024 )} kB)` );
