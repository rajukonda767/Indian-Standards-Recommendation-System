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

  // 1. Initial State: Recommend Page
  console.log('Navigating to http://localhost:3000/recommend...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 800));

  // 2. Query "pvc"
  console.log('Submitting "pvc" query...');
  const textarea = await page.$('textarea');
  await textarea.click();
  await textarea.type('pvc');
  await page.keyboard.press('Enter');

  // Wait for ambiguous modal
  console.log('Waiting for disambiguation modal...');
  await page.waitForSelector('h2', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 1: Disambiguation modal on "pvc" (Full page screenshot)
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_1_pvc_modal.png'), fullPage: true });
  console.log('Saved screenshot_1_pvc_modal.png');

  // 3. Click first modal option
  console.log('Clicking first disambiguation option...');
  const optionButtons = await page.$$('button.group');
  if (optionButtons.length > 0) {
    await optionButtons[0].click();
  }

  // Wait for resolved recommendation
  console.log('Waiting for resolved recommendation...');
  await new Promise(r => setTimeout(r, 3500));
  await page.waitForFunction(() => !document.querySelector('div[style*="fixed"]'), { timeout: 10000 });
  await new Promise(r => setTimeout(r, 1000));

  // Screenshot 2: Resolved query, modal gone, ONE result card, greeting gone
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_2_after_option_selected.png'), fullPage: true });
  console.log('Saved screenshot_2_after_option_selected.png');

  // 4. Query fully-specified cable query: "PVC insulated copper cable 1.5 sq mm for house wiring 1100V"
  console.log('Navigating with preload query for fully specified cable...');
  const cableQuery = 'PVC insulated copper cable 1.5 sq mm for house wiring 1100V';
  await page.goto(`http://localhost:3000/recommend?query=${encodeURIComponent(cableQuery)}`, { waitUntil: 'networkidle2' });
  
  console.log('Waiting for cable recommendation to load...');
  await new Promise(r => setTimeout(r, 4500));

  // Screenshot 4a: ONE primary card + collapsed other specifications
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_4_fully_specified_cable.png'), fullPage: true });
  console.log('Saved screenshot_4_fully_specified_cable.png');

  // Expand "Other specifications this could match"
  console.log('Expanding Other specifications this could match...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && x.textContent.includes('Other specifications this could match'));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 600));

  // Screenshot 4b: Expanded other specifications showing "If X instead of Y"
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_4b_cable_other_specs_expanded.png'), fullPage: true });
  console.log('Saved screenshot_4b_cable_other_specs_expanded.png');

  // 5. Check Allied Standards tab and NOT_IN_INDEX badge
  console.log('Switching to Allied Standards tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && (x.textContent.includes('Allied') || x.textContent.includes('Aligned')));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 1200));

  // Expand "Installation & Workmanship" section (which has IEC standards with NOT_IN_INDEX)
  console.log('Expanding Installation & Workmanship section...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && x.textContent.includes('Installation'));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 800));

  // Screenshot 5: NOT_IN_INDEX badge ("International reference (IEC/ISO)")
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_5_allied_badges.png'), fullPage: true });
  console.log('Saved screenshot_5_allied_badges.png');

  // 6. Check Certifications & QCO tab
  console.log('Switching to Certifications tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && x.textContent.includes('Certification'));
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 6: Certifications tab with scheme heading
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_6_cert_cards.png'), fullPage: true });
  console.log('Saved screenshot_6_cert_cards.png');

  // 7. Check Standards page Committee Dropdown
  console.log('Navigating to Standards page...');
  await page.goto('http://localhost:3000/standards', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 1500));

  // Click CED department tab
  console.log('Selecting CED department...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent && x.textContent.trim() === 'CED');
    if (b) b.click();
  });
  await new Promise(r => setTimeout(r, 800));

  // Screenshot 7: Standards page with CED department and committee select
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_7_standards_ced_committees.png'), fullPage: true });
  console.log('Saved screenshot_7_standards_ced_committees.png');

  await browser.close();
  console.log('All verification screenshots captured successfully!');
}

run().catch(err => {
  console.error('Error during capture:', err);
  process.exit(1);
});
