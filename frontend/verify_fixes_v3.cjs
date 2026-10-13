const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const ARTIFACT_DIR = 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c';

async function run() {
  console.log('Launching browser for automated verification...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,950']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 950 });

  // ── TEST 1: Cable query (Verifying Collapsible Accordion & Text Sanitation) ──
  console.log('Navigating to http://localhost:3000/recommend...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 600));

  console.log('Submitting cable query...');
  const textarea = await page.$('textarea');
  await textarea.click();
  await textarea.type('PVC insulated copper cable 1.5 sq mm for house wiring 1100V');
  await page.keyboard.press('Enter');

  // Wait for results
  console.log('Waiting for recommendation result...');
  await page.waitForFunction(() => {
    return document.body.innerText.includes('IS 694') || document.body.innerText.includes('Recommended Standard');
  }, { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1200));

  // Screenshot 1: Primary standard shown prominently, "Other specifications" collapsed
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_1_cable_primary_collapsed.png'), fullPage: true });
  console.log('Saved screenshot_v3_1_cable_primary_collapsed.png');

  // Click the collapsible accordion to expand it
  console.log('Clicking collapsible accordion to expand alternatives...');
  const accordionBtn = await page.evaluateHandle(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    return btns.find(b => b.innerText.includes('Other specifications this could match') || b.innerText.includes('Tap to expand'));
  });
  if (accordionBtn) {
    await accordionBtn.click();
    await new Promise(r => setTimeout(r, 800));
  }

  // Screenshot 2: Accordion expanded, bold conditions, NO "Indian Standards", single card presentation
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_2_cable_expanded_alternatives.png'), fullPage: true });
  console.log('Saved screenshot_v3_2_cable_expanded_alternatives.png');

  // ── TEST 2: Click on alternative specification box ──
  console.log('Clicking on an alternative specification card...');
  const altCard = await page.evaluateHandle(() => {
    const cards = Array.from(document.querySelectorAll('div[role="button"]'));
    return cards.find(c => c.innerText.includes('IS 7098') || c.innerText.includes('XLPE') || c.innerText.includes('cross-linked'));
  });

  if (altCard) {
    await altCard.click();
    console.log('Clicked alternative card. Waiting for query update and re-recommendation...');
    await new Promise(r => setTimeout(r, 3500));
    await page.waitForFunction(() => {
      return document.body.innerText.includes('IS 7098');
    }, { timeout: 20000 });
    await new Promise(r => setTimeout(r, 1000));

    // Screenshot 3: Query box updated to clean Groq condition heading, new standard recommended
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_3_alternative_clicked_re_recommended.png'), fullPage: true });
    console.log('Saved screenshot_v3_3_alternative_clicked_re_recommended.png');
  }

  // ── TEST 3: Outdated IS Query Verification ("cement conforming to IS 269:1989") ──
  console.log('Navigating for outdated IS test: cement conforming to IS 269:1989...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 600));

  const ta2 = await page.$('textarea');
  await ta2.click();
  await ta2.type('cement conforming to IS 269:1989');
  await page.keyboard.press('Enter');

  await page.waitForFunction(() => {
    return document.body.innerText.includes('IS 269:2015') || document.body.innerText.includes('Ordinary portland cement');
  }, { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1000));

  // Screenshot 4: Outdated IS 269:1989 upgraded to IS 269:2015 (Current)
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_4_outdated_is_upgraded_to_current.png'), fullPage: true });
  console.log('Saved screenshot_v3_4_outdated_is_upgraded_to_current.png');

  // ── TEST 4: Cross-Standard Lineage Replacement Verification ("IS 3935") ──
  console.log('Navigating for cross-standard replacement test: IS 3935...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 600));

  const ta3 = await page.$('textarea');
  await ta3.click();
  await ta3.type('IS 3935');
  await page.keyboard.press('Enter');

  await page.waitForFunction(() => {
    return document.body.innerText.includes('IS 11384:2022') || document.body.innerText.includes('Superseded');
  }, { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1000));

  // Screenshot 5: IS 3935 superseded by IS 11384:2022
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_v3_5_cross_standard_superseded.png'), fullPage: true });
  console.log('Saved screenshot_v3_5_cross_standard_superseded.png');

  await browser.close();
  console.log('All verification screenshots captured successfully!');
}

run().catch(err => {
  console.error('Verification error:', err);
  process.exit(1);
});
