// Drive the interactive mock the way the owner will: every width, every toggle
// combination, and assert the readouts are telling the truth rather than just
// rendering. Catches a mock that looks right but reports wrong numbers.
const { launch } = require('../../../tools/browser/lib/browser');
const fs = require('fs');

const SRC = 'file://' + require('path').resolve(__dirname, '../mock.html') + '';
const OUT = require('path').resolve(__dirname, '..');

(async () => {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text()); });

  await page.goto(SRC, { waitUntil: 'load' });
  await page.waitForTimeout 
    ? await page.waitForTimeout(2200) : null;

  async function state() {
    return page.evaluate(() => {
      const t = s => { const e = document.querySelector(s); return e ? e.textContent.trim() : null; };
      const chips = [...document.querySelectorAll('#readout .chip')].map(c => ({
        text: c.textContent.trim(),
        cls: c.className.replace('chip', '').trim(),
      }));
      const dev = document.getElementById('device');
      const wt = document.getElementById('wt');
      const copy = document.getElementById('copy');
      const title = document.getElementById('title');
      const cs = getComputedStyle(title);
      return {
        frame: t('#frameLabel'),
        verdict: t('#stateLabel'),
        chips,
        deviceW: Math.round(dev.getBoundingClientRect().width),
        copyW: Math.round(copy.getBoundingClientRect().width),
        wtH: Math.round(wt.getBoundingClientRect().height),
        titlePx: +parseFloat(cs.fontSize).toFixed(2),
        titleLs: +parseFloat(cs.letterSpacing).toFixed(3),
        titlePct: +((parseFloat(cs.letterSpacing) / parseFloat(cs.fontSize)) * 100).toFixed(2),
        guideOn: document.querySelector('.view').classList.contains('show-guide'),
      };
    });
  }

  async function setW(w) {
    await page.click(`#wsel button[data-w="${w}"]`);
    await page.waitForTimeout(420);
  }
  async function setFixes(a, b, c) {
    for (const [id, want] of [['#f1', a], ['#f2', b], ['#f3', c]]) {
      const is = await page.isChecked(id);
      if (is !== want) await page.click(id);
    }
    await page.waitForTimeout(420);
  }

  const results = [];
  const WIDTHS = [390, 768, 820, 1024, 1280, 1440];

  // ---- Pass 1: ship-as-is at every width. Expect the flaws to be reported. ----
  for (const w of WIDTHS) {
    await setW(w); await setFixes(false, false, false);
    const s = await state();
    results.push({ phase: 'as-is', w, ...s });
  }
  // ---- Pass 2: all three fixes on. Expect every width clean. ----
  for (const w of WIDTHS) {
    await setW(w); await setFixes(true, true, true);
    const s = await state();
    results.push({ phase: 'all-3', w, ...s });
  }

  console.log('\n=== PASS 1: ship as-is ===');
  console.log('  w   device  copy   panelH  h2px   h2%     guide  verdict');
  for (const r of results.filter(r => r.phase === 'as-is')) {
    console.log(String(r.w).padStart(5), String(r.deviceW).padEnd(7),
      String(r.copyW).padEnd(6), String(r.wtH).padEnd(7),
      String(r.titlePx).padEnd(6), String(r.titlePct).padEnd(7),
      String(r.guideOn).padEnd(6), r.verdict);
  }
  console.log('\n=== PASS 2: all three fixes on ===');
  console.log('  w   device  copy   panelH  h2px   h2%     guide  verdict');
  for (const r of results.filter(r => r.phase === 'all-3')) {
    console.log(String(r.w).padStart(5), String(r.deviceW).padEnd(7),
      String(r.copyW).padEnd(6), String(r.wtH).padEnd(7),
      String(r.titlePx).padEnd(6), String(r.titlePct).padEnd(7),
      String(r.guideOn).padEnd(6), r.verdict);
  }

  // ---- Assertions: does the mock tell the truth? ----
  const fail = [];
  const asis = w => results.find(r => r.phase === 'as-is' && r.w === w);
  const all3 = w => results.find(r => r.phase === 'all-3' && r.w === w);

  // clamp must resolve off the FRAME, not the real 1400px viewport
  if (asis(768).titlePx !== 28) fail.push(`clamp not tracking frame: 768 gave ${asis(768).titlePx}px, want 28`);
  if (asis(1440).titlePx !== 40) fail.push(`clamp at 1440 gave ${asis(1440).titlePx}px, want 40`);
  if (Math.abs(asis(1024).titlePx - 32.77) > 0.3) fail.push(`clamp at 1024 gave ${asis(1024).titlePx}px, want ~32.77`);

  // fix 3 must produce a flat -3.00% everywhere
  for (const w of WIDTHS) {
    if (Math.abs(all3(w).titlePct + 3) > 0.06) fail.push(`fix3 at ${w} gave ${all3(w).titlePct}%, want -3.00`);
  }
  // as-is must drift
  if (Math.abs(asis(768).titlePct + 4.29) > 0.06) fail.push(`as-is 768 pct ${asis(768).titlePct}, want -4.29`);
  if (Math.abs(asis(1440).titlePct + 3.00) > 0.06) fail.push(`as-is 1440 pct ${asis(1440).titlePct}, want -3.00`);

  // fix 1 must cap the copy at 680 in the narrow band, and not touch desktop
  for (const w of [768, 820, 1024]) {
    if (all3(w).copyW > 681) fail.push(`fix1 at ${w} left copy ${all3(w).copyW}px, want <=680`);
    if (asis(w).copyW <= 681) fail.push(`as-is ${w} copy ${asis(w).copyW}px - flaw not reproduced`);
  }
  for (const w of [1280, 1440]) {
    if (asis(w).copyW !== 380) fail.push(`as-is ${w} copy ${asis(w).copyW}px, want 380 (the 380px track)`);
    if (all3(w).copyW !== 380) fail.push(`fix1 changed ${w} copy to ${all3(w).copyW}, want 380`);
  }
  if (all3(390).copyW !== asis(390).copyW) fail.push('fix1 changed the 390px column, should be a no-op there');

  // fix 2 must shorten the panel only in the narrow band
  for (const w of [768, 820, 1024]) {
    if (asis(w).wtH !== 650) fail.push(`as-is ${w} panel ${asis(w).wtH}px, want 650 (flaw not reproduced)`);
    if (all3(w).wtH !== 560) fail.push(`fix2 at ${w} panel ${all3(w).wtH}px, want 560`);
  }
  // 390 already ships at 560 - it must be 560 in BOTH passes, fix or no fix.
  if (asis(390).wtH !== 560) fail.push(`as-is 390 panel ${asis(390).wtH}px, want 560 (ships today)`);
  if (all3(390).wtH !== 560) fail.push(`all-3 390 panel ${all3(390).wtH}px, want 560`);
  if (all3(1440).wtH !== 650) fail.push(`fix2 shortened desktop panel to ${all3(1440).wtH}, want 650`);

  // the guide line must appear only where it means something
  if (!asis(1024).guideOn) fail.push('guide missing at 1024 as-is');
  if (all3(1024).guideOn) fail.push('guide still on at 1024 with fix1');
  if (asis(390).guideOn) fail.push('guide on at 390 - copy is under 680 there');
  if (asis(1440).guideOn) fail.push('guide on at desktop - two columns, not applicable');

  // verdicts must actually flip
  for (const w of WIDTHS) {
    if (!all3(w).verdict.includes('no flaw')) fail.push(`all-3 at ${w} still reports: ${all3(w).verdict}`);
  }
  for (const w of [768, 820, 1024]) {
    if (asis(w).verdict.includes('no flaw')) fail.push(`as-is at ${w} reports clean, should not`);
  }

  console.log('\n=== JS errors ===');
  console.log(errs.length ? errs.join('\n') : 'none');
  console.log('\n=== assertions ===');
  if (fail.length) { console.log('FAILED:\n - ' + fail.join('\n - ')); }
  else { console.log(`all ${WIDTHS.length * 2} states behave correctly`); }

  // Screenshots of the two extremes for the record
  await setW(1024); await setFixes(false, false, false);
  await page.locator('.stage').screenshot({ path: OUT + '/live-1024-as-is.png' });
  await setFixes(true, true, true);
  await page.locator('.stage').screenshot({ path: OUT + '/live-1024-fixed.png' });
  await page.screenshot({ path: OUT + '/interactive-mock-full.png', fullPage: true });

  fs.writeFileSync('./out-shots/drive-results.json', JSON.stringify(results, null, 2));
  await ctx.close(); await browser.close();
  process.exit(fail.length || errs.length ? 1 : 0);
})();
