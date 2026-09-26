// The two-column band squeezes the terminal to 553px at 1025. The terminal's
// command lines are white-space:nowrap with overflow-x:auto, so check whether
// they actually start scrolling inside the panel - and how far.
const { launch, gotoStable } = require('../../../tools/browser/lib/browser');
const { target } = require('../../../tools/browser/lib/serve');
const fs = require('fs');
fs.mkdirSync('./out-shots', { recursive: true });

const WIDTHS = [ 768, 1024, 1025, 1112, 1180, 1280, 1440, 1920 ];

(async () => {
  const t = await target();
  const browser = await launch();
  const rows = [];

  for (const w of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width: w, height: 900 },
      deviceScaleFactor: 1, serviceWorkers: 'block', reducedMotion: 'reduce',
    });
    const page = await ctx.newPage();
    await gotoStable(page, `${t.base}/`);
    await page.waitForTimeout(900);
    const m = await page.evaluate(() => {
      const panel = document.querySelector('.home-flow-panel');
      const cmds = [ ...document.querySelectorAll('.wt-cmd') ];
      const clipped = cmds
        .map(el => ({
          over: el.scrollWidth - el.clientWidth,
          client: el.clientWidth,
          need: el.scrollWidth,
          text: (el.textContent || '').trim().slice(0, 52),
        }))
        .filter(c => c.over > 1);
      // Anything else nowrap inside the panel that could clip
      const chips = [ ...document.querySelectorAll('.wt-lane, .wt-chip, .wt-head') ]
        .filter(el => el.scrollWidth - el.clientWidth > 1).length;
      return {
        panelW: +panel.getBoundingClientRect().width.toFixed(0),
        cmdCount: cmds.length,
        clippedCount: clipped.length,
        worst: clipped.length ? Math.max(...clipped.map(c => c.over)) : 0,
        sample: clipped.length ? clipped.sort((a, b) => b.over - a.over)[0] : null,
        otherClipped: chips,
      };
    });
    m.w = w;
    rows.push(m);
    await ctx.close();
  }
  await browser.close();
  await t.close();

  console.log('\n  w   panel   cmd lines clipped   worst overflow   widest line needs   other nowrap clipped');
  for (const r of rows) {
    console.log(
      String(r.w).padStart(5),
      String(r.panelW + 'px').padEnd(8),
      `${r.clippedCount} of ${r.cmdCount}`.padEnd(20),
      String(r.worst + 'px').padEnd(17),
      String(r.sample ? r.sample.need + 'px in ' + r.sample.client + 'px' : '-').padEnd(20),
      r.otherClipped
    );
  }
  console.log('\nwidest command line, verbatim start:',
    rows.map(r => r.sample && r.sample.text).find(Boolean) || '(none clipped anywhere)');
  fs.writeFileSync('./out-shots/cmd.json', JSON.stringify(rows, null, 2));
})();
