import puppeteer from 'puppeteer-core';

async function main() {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  console.log('Navigating to http://localhost:3000/recommend?query=cable ...');
  await page.goto('http://localhost:3000/recommend?query=cable', { waitUntil: 'networkidle0' });

  console.log('Waiting for recommendation card...');
  await page.waitForSelector('text/RECOMMENDED STANDARD', { timeout: 20000 });

  // Expand the collapsible accordion
  console.log('Expanding accordion...');
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('OTHER SPECIFICATIONS THIS COULD MATCH'));
    if (btn) btn.click();
  });

  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c/screenshot_reloaded_cable_expanded.png' });
  console.log('Saved screenshot_reloaded_cable_expanded.png');

  await browser.close();
}

main().catch(console.error);
