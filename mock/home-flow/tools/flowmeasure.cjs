// In two columns the copy sits in a 380px track - a proper typographic measure.
// At <=1024 it inherits the full page width with no max-width. Count the actual
// characters per line to see where that lands against the 45-75 CPL convention,
// and check what the rest of the site does about it.
const { launch, gotoStable } = require('../../../tools/browser/lib/browser');
const { target } = require('../../../tools/browser/lib/serve');
const fs = require('fs');
fs.mkdirSync('./out-shots', { recursive: true });

const WIDTHS = [ 320, 390, 768, 820, 1024, 1025, 1280, 1440, 1920 ];

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
    await page.waitForTimeout(700);

    const m = await page.evaluate(() => {
      // Characters per line = measure the rendered width of one line of this
      // element's own text, then divide the box width by the mean glyph advance.
      function cpl(el) {
        if (!el) return null;
        const text = (el.textContent || '').trim();
        if (!text) return null;
        const cs = getComputedStyle(el);
        const probe = document.createElement('span');
        probe.style.cssText = `position:absolute;visibility:hidden;white-space:nowrap;` +
          `font:${cs.font};letter-spacing:${cs.letterSpacing}`;
        probe.textContent = text;
        document.body.appendChild(probe);
        const advance = probe.getBoundingClientRect().width / text.length;
        probe.remove();
        const box = el.getBoundingClientRect().width;
        // Lines the paragraph actually occupies
        const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4;
        const lines = Math.round(el.getBoundingClientRect().height / lh);
        return { boxW: +box.toFixed(0), cpl: Math.round(box / advance), lines, chars: text.length };
      }
      const copy = document.querySelector('.home-flow-copy');
      const cs = getComputedStyle(copy);
      // Does anything on the page cap prose width? Sample every public prose block.
      const caps = [ ...document.querySelectorAll('p, li span, h2') ]
        .map(el => getComputedStyle(el).maxWidth)
        .filter(v => v && v !== 'none');
      return {
        copyW: +copy.getBoundingClientRect().width.toFixed(0),
        copyMaxW: cs.maxWidth,
        lead: cpl(document.querySelector('.home-flow-lead')),
        beat1: cpl(document.querySelector('.home-flow-list li span')),
        title: cpl(document.querySelector('.home-flow-title')),
        closeLeadMaxW: (() => { const e = document.querySelector('.home-close-lead');
          return e ? getComputedStyle(e).maxWidth : null; })(),
        closeTitleMaxW: (() => { const e = document.querySelector('.home-close-title');
          return e ? getComputedStyle(e).maxWidth : null; })(),
        heroSubMaxW: (() => { const e = document.querySelector('.home-sub');
          return e ? getComputedStyle(e).maxWidth : null; })(),
        cappedProseBlocks: caps.length,
      };
    });
    m.w = w;
    rows.push(m);
    await ctx.close();
  }
  await browser.close();
  await t.close();

  const verdict = c => c === null ? '' : c.cpl > 90 ? '  WAY OVER' : c.cpl > 75 ? '  over' : c.cpl < 40 ? '  tight' : '  ok';
  console.log('\n  w   copy box  copy max-width   lead CPL        beat CPL        title CPL');
  for (const r of rows) {
    console.log(
      String(r.w).padStart(5),
      String(r.copyW + 'px').padEnd(9),
      String(r.copyMaxW).padEnd(16),
      `${r.lead.cpl} (${r.lead.lines}ln)${verdict(r.lead)}`.padEnd(16),
      `${r.beat1.cpl} (${r.beat1.lines}ln)${verdict(r.beat1)}`.padEnd(16),
      `${r.title.cpl} (${r.title.lines}ln)`
    );
  }
  const r0 = rows[0];
  console.log('\nWhat the neighbours cap themselves at:');
  console.log('  .home-sub          max-width:', r0.heroSubMaxW);
  console.log('  .home-close-title  max-width:', r0.closeTitleMaxW);
  console.log('  .home-close-lead   max-width:', r0.closeLeadMaxW);
  fs.writeFileSync('./out-shots/cpl.json', JSON.stringify(rows, null, 2));
})();
