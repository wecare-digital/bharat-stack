const { target } = require('/projects/sandbox/wecare-digital/tools/browser/lib/serve');
const { launch, gotoStable } = require('/projects/sandbox/wecare-digital/tools/browser/lib/browser');
const fs = require('fs');
(async () => {
  const t = await target(); const b = await launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 3 });
  await gotoStable(p, t.base + '/');
  const shots = {};
  const grab = async (key) => {
    const el = await p.$('.nav-trigger');
    shots[key] = (await el.screenshot()).toString('base64');
  };
  // 1. rest
  await p.mouse.move(0, 0); await p.waitForTimeout(400); await grab('rest');
  // 2. NEW hover (what this PR ships)
  await p.hover('.nav-trigger'); await p.waitForTimeout(450); await grab('newHover');
  // 3. OLD hover, reconstructed by forcing the previous declaration
  await p.mouse.move(0,0); await p.waitForTimeout(350);
  await p.addStyleTag({ content: `.nav-trigger:hover{background:rgba(209,244,112,.22)!important;border-color:#e3ecc9!important}
    .nav-trigger:hover .nav-arrow{border-right-color:#1a3a2a!important;border-bottom-color:#1a3a2a!important;opacity:.85!important}` });
  await p.hover('.nav-trigger'); await p.waitForTimeout(450); await grab('oldHover');

  await p.setContent(`<body style="margin:0;background:#fff;font:13px Inter,system-ui,sans-serif;padding:26px">
    <div style="display:flex;gap:34px;align-items:flex-start">
      ${[['rest','At rest','#f4f7ee chip, dark chevron<br>1.08:1 vs the white header'],
         ['oldHover','OLD hover — what shipped','rgba(209,244,112,.22)<br><b style="color:#991b1b">1.03:1 vs rest &middot; RGB move 15</b>'],
         ['newHover','NEW hover — this PR','#1a3a2a chip, lime chevron<br><b style="color:#166534">11.52:1 vs rest &middot; RGB move 349</b>']]
        .map(([k,label,note]) => `<div style="text-align:center">
          <div style="font-weight:700;margin-bottom:12px">${label}</div>
          <div style="display:inline-block;padding:16px 22px;border:1px dashed #d7d7d7;border-radius:10px;background:#fff">
            <img src="data:image/png;base64,${shots[k]}" style="width:92px;image-rendering:-webkit-optimize-contrast">
          </div>
          <div style="margin-top:11px;color:#555;line-height:1.5">${note}</div>
        </div>`).join('')}
    </div></body>`);
  await p.waitForTimeout(400);
  await p.screenshot({ path: '/projects/sandbox/menu-icon-compare.png', fullPage: true });
  console.log('  wrote /projects/sandbox/menu-icon-compare.png');
  await b.close(); await t.close();
})();
