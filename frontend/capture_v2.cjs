const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const ARTIFACT_DIR = 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c';

async function run() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,950']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 950 });

  // 1. Navigate to Recommend page and query "pvc"
  console.log('Navigating to http://localhost:3000/recommend...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 800));

  console.log('Submitting "pvc" query...');
  const textarea = await page.$('textarea');
  await textarea.click();
  await textarea.type('pvc');
  await page.keyboard.press('Enter');

  // Wait for ambiguous modal
  console.log('Waiting for disambiguation modal...');
  await page.waitForSelector('h2', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 1: Disambiguation modal showing direct typing input in 4th option
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_1_modal_inline_typing.png'), fullPage: true });
  console.log('Saved screenshot_v2_1_modal_inline_typing.png');

  // 2. Type directly in the 4th option input inside the modal!
  console.log('Typing in 4th option input inside modal...');
  const modalInput = await page.$('div[style*="fixed"] input[type="text"]');
  if (modalInput) {
    await modalInput.click();
    await modalInput.type('Unplasticized PVC pipes for potable water supply IS 4985');
    await new Promise(r => setTimeout(r, 400));
    // Screenshot 1b: Showing text typed inside modal's 4th option
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_1b_modal_typed.png'), fullPage: true });
    console.log('Saved screenshot_v2_1b_modal_typed.png');

    // Click submit button in modal
    const recommendBtn = await page.$('div[style*="fixed"] button[type="submit"]');
    if (recommendBtn) {
      await recommendBtn.click();
    } else {
      await modalInput.press('Enter');
    }
  }

  // Wait for recommendation to resolve
  console.log('Waiting for resolved recommendation from modal submission...');
  await page.waitForFunction(() => !document.querySelector('div[style*="fixed"]'), { timeout: 15000 });
  await page.waitForFunction(() => document.body.innerText.toUpperCase().includes('RECOMMENDED STANDARD'), { timeout: 25000 });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 2: Result of modal 4th option submission (ONE primary standard + unboxed other specs with bold subheadings)
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_2_custom_typed_result.png'), fullPage: true });
  console.log('Saved screenshot_v2_2_custom_typed_result.png');

  // 3. Test fully specified query: "PVC insulated copper cable 1.5 sq mm for house wiring 1100V"
  console.log('Navigating with preload query for cable...');
  const cableQuery = 'PVC insulated copper cable 1.5 sq mm for house wiring 1100V';
  await page.goto(`http://localhost:3000/recommend?query=${encodeURIComponent(cableQuery)}`, { waitUntil: 'networkidle2' });
  await page.waitForFunction(() => document.body.innerText.toUpperCase().includes('RECOMMENDED STANDARD'), { timeout: 25000 });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 3: One primary standard + open unboxed "Other specifications this could match" with bold subheadings
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_3_cable_open_alternatives.png'), fullPage: true });
  console.log('Saved screenshot_v2_3_cable_open_alternatives.png');

  // 4. Check Certifications tab (verify only ONE card for recommended standard)
  console.log('Switching to Certifications tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && x.textContent.includes('Certification'));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 4: Certifications tab showing ONLY ONE card for the recommended standard
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_4_single_cert_card.png'), fullPage: true });
  console.log('Saved screenshot_v2_4_single_cert_card.png');

  // 5. Check Allied Standards tab
  console.log('Switching to Allied Standards tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && (x.textContent.includes('Allied') || x.textContent.includes('Aligned')));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 5: Allied standards header specifically indicating the recommended standard
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v2_5_allied_single_standard.png'), fullPage: true });
  console.log('Saved screenshot_v2_5_allied_single_standard.png');

  await browser.close();
  console.log('All v2 verification screenshots captured successfully!');
}

run().catch(err => {
  console.error('Error during capture:', err);
  process.exit(1);
});
