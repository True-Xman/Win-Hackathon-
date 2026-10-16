// Render frames of index.html with headless Chromium.
// usage: node render.js <outDir> <fps>            -> all frames
//        node render.js <outDir> preview t1 t2 .. -> selected times only
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [outDir, mode, ...rest] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => { console.error('[pageerror]', e.message); process.exitCode = 1; });
  await page.goto('file://' + path.resolve(__dirname, 'index.html'));
  await page.evaluate(() => window.READY);
  const grab = async t => {
    const url = await page.evaluate(t => { window.renderFrame(t); return document.getElementById('c').toDataURL('image/png'); }, t);
    return Buffer.from(url.split(',')[1], 'base64');
  };
  if (mode === 'preview') {
    for (const s of rest) fs.writeFileSync(path.join(outDir, `t_${s}.png`), await grab(parseFloat(s)));
  } else {
    const fps = parseInt(mode || '30', 10);
    const dur = await page.evaluate(() => window.DUR);
    const n = Math.round(dur * fps);
    for (let f = 0; f < n; f++) {
      fs.writeFileSync(path.join(outDir, `f_${String(f).padStart(5, '0')}.png`), await grab(f / fps));
      if (f % 60 === 0) console.log(`frame ${f}/${n}`);
    }
  }
  await browser.close();
})();
