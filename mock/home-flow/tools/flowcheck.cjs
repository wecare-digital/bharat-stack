// Measure and photograph .home-flow on the built site, and prove or disprove
// the three flaws recorded for it. Run from mock/home-flow/tools/ with the repo built.
const { launch, gotoStable } = require('../../../tools/browser/lib/browser');
const { target } = require('../../../tools/browser/lib/serve');
const fs = require('fs');
const path = require('path');

const OUT = './out-shots';

const WIDTHS = [
  { w: 1920, h: 1200, tag: '1920' },
  { w: 1440, h: 900, tag: '1440' },
  { w: 1280, h: 860, tag: '1280' },
  { w: 1024, h: 860, tag: '1024' },
  { w: 768,  h: 1024, tag: '768'  },
  { w: 390,  h: 844, tag: '390'  },
  { w: 320,  h: 800, tag: '320'  },
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const t = await target();
  const browser = await launch();
  const rows = [];

  for (const d of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width: d.w, height: d.h },
      deviceScaleFactor: 1,
      serviceWorkers: 'block',
      reducedMotion: 'reduce',           // freeze the terminal so shots are comparable
    });
    const page = await ctx.newPage();
    await gotoStable(page, `${t.base}/`);
    await page.waitForTimeout(1000);

    const m = await page.evaluate(() => {
      const q = s => document.querySelector(s);
      const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
        return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
      const cs = el => el ? getComputedStyle(el) : null;
      const flow = q('.home-flow'), panel = q('.home-flow-panel'),
            copy = q('.home-flow-copy'), title = q('.home-flow-title'),
            lead = q('.home-flow-lead'),
            wt = q('.wt-panel') || (panel && panel.firstElementChild);
      const tcs = cs(title);
      const fsz = parseFloat(tcs.fontSize), ls = parseFloat(tcs.letterSpacing);
      const pb = box(panel), cb = box(copy);
      return {
        cols: cs(flow).gridTemplateColumns,
        gap: cs(flow).gap,
        flow: box(flow), panel: pb, copy: cb, wt: box(wt),
        wtHeight: wt ? cs(wt).height : null,
        copyOrder: cs(copy).order, copyPos: cs(copy).position,
        titleFont: +fsz.toFixed(2), titleLs: +ls.toFixed(3),
        titlePct: +((ls / fsz) * 100).toFixed(3),
        leadFont: cs(lead).fontSize,
        sideBySide: !!(pb && cb && Math.abs(pb.y - cb.y) < 40 && cb.x > pb.x + 50),
        docW: document.documentElement.scrollWidth,
        winW: window.innerWidth,
      };
    });
    m.tag = d.tag;
    m.overflow = m.docW > m.winW ? `OVERFLOW +${m.docW - m.winW}px` : 'none';
    m.heightGap = m.panel && m.copy ? +(m.panel.h - m.copy.h).toFixed(1) : null;
    m.panelShareOfMeasure = m.flow ? +((m.panel.w / m.flow.w) * 100).toFixed(1) : null;
    rows.push(m);

    const el = await page.$('.home-flow');
    await el.screenshot({ path: path.join(OUT, `live-${d.tag}.png`) });
    await ctx.close();
  }

  await browser.close();
  await t.close();

  console.log('\nw      cols                              gap  panel(wxh)      copy(wxh)       dH     pnl%  ord pos      h2px  h2ls   h2%     side  overflow');
  for (const r of rows) {
    console.log(
      String(r.tag).padEnd(6),
      r.cols.padEnd(33).slice(0, 33),
      String(r.gap).padEnd(4),
      `${r.panel.w}x${r.panel.h}`.padEnd(15),
      `${r.copy.w}x${r.copy.h}`.padEnd(15),
      String(r.heightGap).padEnd(6),
      String(r.panelShareOfMeasure).padEnd(5),
      String(r.copyOrder).padEnd(3),
      String(r.copyPos).padEnd(8),
      String(r.titleFont).padEnd(5),
      String(r.titleLs).padEnd(6),
      String(r.titlePct).padEnd(7),
      String(r.sideBySide).padEnd(5),
      r.overflow
    );
  }
  fs.writeFileSync(path.join(OUT, 'measurements.json'), JSON.stringify(rows, null, 2));
  console.log(`\nshots + measurements.json -> ${OUT}`);
})();
