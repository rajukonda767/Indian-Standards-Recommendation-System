const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const ARTIFACT_DIR = 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c';

async function run() {
  console.log('Launching browser for doubt check verification...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,950']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 950 });

  // ── TEST A: cement conforming to IS 269:1989 ──
  console.log('Navigating to http://localhost:3000/recommend?query=cement%20conforming%20to%20IS%20269:1989...');
  await page.goto('http://localhost:3000/recommend?query=' + encodeURIComponent('cement conforming to IS 269:1989'), { waitUntil: 'networkidle2' });

  console.log('Waiting for IS 269 recommendation result...');
  await page.waitForFunction(() => {
    return document.body.innerText.includes('IS 269:2015') || document.body.innerText.includes('Ordinary portland cement');
  }, { timeout: 25000 });
  await new Promise(r => setTimeout(r, 1200));

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_4_outdated_is_upgraded_to_current.png'), fullPage: true });
  console.log('Saved screenshot_v3_4_outdated_is_upgraded_to_current.png');

  // ── TEST B: IS 3935 cross-standard supersession ──
  console.log('Navigating to http://localhost:3000/recommend?query=IS%203935...');
  await page.goto('http://localhost:3000/recommend?query=' + encodeURIComponent('IS 3935'), { waitUntil: 'networkidle2' });

  console.log('Waiting for IS 3935 replacement result...');
  await page.waitForFunction(() => {
    return document.body.innerText.includes('IS 11384:2022') || document.body.innerText.includes('Superseded');
  }, { timeout: 25000 });
  await new Promise(r => setTimeout(r, 1200));

  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_5_cross_standard_superseded.png'), fullPage: true });
  console.log('Saved screenshot_v3_5_cross_standard_superseded.png');

  await browser.close();
  console.log('Doubt check screenshots captured successfully!');
}

run().catch(err => {
  console.error('Doubt check error:', err);
  process.exit(1);
});
