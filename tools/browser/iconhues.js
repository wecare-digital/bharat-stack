const { target } = require('/projects/sandbox/wecare-digital/tools/browser/lib/serve');
const { launch, gotoStable } = require('/projects/sandbox/wecare-digital/tools/browser/lib/browser');
(async () => {
  const t = await target(); const b = await launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 3 });
  await gotoStable(p, t.base + '/');

  // rest colour, hover colour, label, ratios
  const OPTS = [
    ['#1a3a2a','#d1f470','A · dark green &rarr; lime','11.52 / 10.04','current'],
    ['#1a3a2a','#f0a818','B · dark green &rarr; amber','11.52 / 6.13',''],
    ['#1a3a2a','#3da35a','C · dark green &rarr; green','11.52 / 3.91',''],
    ['#9849e8','#d1f470','D · purple &rarr; lime','4.35 / 10.04',''],
    ['#9849e8','#f0a818','E · purple &rarr; amber','4.35 / 6.13',''],
  ];
  const shots = [];
  for (const [rest, hover] of OPTS) {
    await p.addStyleTag({ content: `.nav-arrow{border-right-color:${rest}!important;border-bottom-color:${rest}!important}
      .nav-trigger:hover .nav-arrow{border-right-color:${hover}!important;border-bottom-color:${hover}!important;opacity:1!important}` });
    await p.mouse.move(0,0); await p.waitForTimeout(320);
    const el = await p.$('.nav-trigger');
    const r = (await el.screenshot()).toString('base64');
    await p.hover('.nav-trigger'); await p.waitForTimeout(420);
    const h = (await el.screenshot()).toString('base64');
    shots.push([r, h]);
  }
  await p.setContent(`<body style="margin:0;background:#fff;font:13px Inter,system-ui,sans-serif;padding:24px">
    <div style="font:700 15px Inter;margin-bottom:6px">Chevron colour pairs that actually pass on both chip states</div>
    <div style="color:#666;margin-bottom:20px">left = at rest (pale chip) &middot; right = hovered (dark chip) &middot; ratios shown rest / hover</div>
    <div style="display:flex;gap:26px;flex-wrap:wrap">
    ${OPTS.map(([rc,hc,label,ratios,tag],i)=>`<div style="text-align:center;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;${tag?'background:#f8fbf0;border-color:#cfe0a6':''}">
      <div style="font-weight:700;margin-bottom:10px">${label}${tag?' <span style="font:700 10px Inter;background:#d1f470;color:#1a3a2a;padding:2px 7px;border-radius:99px;vertical-align:2px">'+tag+'</span>':''}</div>
      <div style="display:flex;gap:10px;justify-content:center">
        <img src="data:image/png;base64,${shots[i][0]}" style="width:72px">
        <img src="data:image/png;base64,${shots[i][1]}" style="width:72px">
      </div>
      <div style="margin-top:10px;color:#555;font-variant-numeric:tabular-nums">${ratios}</div>
    </div>`).join('')}
    </div></body>`);
  await p.waitForTimeout(400);
  await p.screenshot({ path: '/projects/sandbox/hue-options.png', fullPage: true });
  console.log('  wrote hue-options.png');
  await b.close(); await t.close();
})();
