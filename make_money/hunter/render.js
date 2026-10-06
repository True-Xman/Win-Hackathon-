// Read-only page renderer (GET only). usage: node render.js <url>  -> prints document.body.innerText
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
  const pg = await b.newPage();
  try { await pg.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 40000 }); await pg.waitForTimeout(4000);
        console.log(await pg.evaluate(() => document.body.innerText)); } catch (e) { console.log('[[RENDER FAILED ' + e.message.slice(0, 100) + ']]'); }
  await b.close();
})();
