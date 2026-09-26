// The layout collapses to one column at <=1024. The terminal only steps down to
// 560px at <=767. Walk the boundary and record which widths get a FULL-WIDTH
// 650px black panel - the condition the two-column band was built to remove.
const { launch, gotoStable } = require('../../../tools/browser/lib/browser');
const { target } = require('../../../tools/browser/lib/serve');
const fs = require('fs');
fs.mkdirSync('./out-shots', { recursive: true });

// Real tablet portrait/landscape widths, plus the two breakpoint boundaries.
const WIDTHS = [
  { w: 744,  label: 'iPad mini portrait' },
  { w: 767,  label: 'terminal breakpoint, last mobile px' },
  { w: 768,  label: 'iPad 9.7/10.2 portrait' },
  { w: 800,  label: 'common Android tablet' },
  { w: 820,  label: 'iPad Air portrait' },
  { w: 834,  label: 'iPad Pro 11 portrait' },
  { w: 912,  label: 'Surface Pro 7 portrait' },
  { w: 1024, label: 'iPad portrait landscape / layout breakpoint' },
  { w: 1025, label: 'first two-column px' },
  { w: 1112, label: 'iPad Pro 10.5 landscape' },
  { w: 1180, label: 'iPad Air landscape' },
];

(async () => {
  const t = await target();
  const browser = await launch();
  const rows = [];

  for (const d of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width: d.w, height: 900 },
      deviceScaleFactor: 1, serviceWorkers: 'block', reducedMotion: 'reduce',
    });
    const page = await ctx.newPage();
    await gotoStable(page, `${t.base}/`);
    await page.waitForTimeout(700);
    const m = await page.evaluate(() => {
      const q = s => document.querySelector(s);
      const r = el => el ? el.getBoundingClientRect() : null;
      const flow = r(q('.home-flow')), panel = r(q('.home-flow-panel')),
            copy = r(q('.home-flow-copy')), wt = r(q('.wt-window'));
      return {
        flowW: +flow.width.toFixed(0),
        panelW: +panel.width.toFixed(0), panelH: +panel.height.toFixed(0),
        copyW: +copy.width.toFixed(0), copyH: +copy.height.toFixed(0),
        wtH: wt ? +wt.height.toFixed(0) : null,
        oneCol: Math.abs(panel.width - copy.width) < 2,
      };
    });
    m.w = d.w; m.label = d.label;
    m.share = +((m.panelW / m.flowW) * 100).toFixed(0);
    // The defect condition: one column AND the desktop-height terminal.
    m.worstOfBoth = m.oneCol && m.wtH > 600;
    rows.push(m);
    await ctx.close();
  }
  await browser.close();
  await t.close();

  console.log('\n w     layout     terminal  panel(wxh)   copy h   panel% of measure   worst-of-both  device');
  for (const r of rows) {
    console.log(
      String(r.w).padStart(5),
      (r.oneCol ? '1-col' : '2-col').padEnd(10),
      String(r.wtH + 'px').padEnd(9),
      `${r.panelW}x${r.panelH}`.padEnd(12),
      String(r.copyH).padEnd(8),
      String(r.share + '%').padEnd(19),
      (r.worstOfBoth ? 'YES  <-- ' : 'no       ').padEnd(14),
      r.label
    );
  }
  const bad = rows.filter(r => r.worstOfBoth);
  console.log(`\n${bad.length} of ${rows.length} sampled widths get a full-width 650px panel: ${bad.map(r => r.w).join(', ')}`);
  fs.writeFileSync('./out-shots/band.json', JSON.stringify(rows, null, 2));
})();
