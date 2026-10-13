import puppeteer from 'puppeteer-core';

async function main() {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  console.log('Navigating to http://localhost:3000/recommend ...');
  await page.goto('http://localhost:3000/recommend', { waitUntil: 'networkidle0' });

  // Type pvc using page.evaluate to ensure React state updates
  console.log("Setting input to 'pvc'...");
  await page.evaluate(() => {
    const textarea = document.querySelector('textarea');
    if (textarea) {
      // Use native value setter for React 16+
      const prototype = Object.getPrototypeOf(textarea);
      const nativeSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
      nativeSetter.call(textarea, 'pvc');
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });

  await new Promise(r => setTimeout(r, 500));

  // Click submit button
  console.log('Clicking submit button...');
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const submitBtn = buttons.find(b => b.innerText.includes('Submit') || b.querySelector('svg.lucide-arrow-up'));
    if (submitBtn) {
      submitBtn.click();
    }
  });

  console.log('Waiting 3s for API response...');
  await new Promise(r => setTimeout(r, 3500));

  await page.screenshot({ path: 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c/screenshot_reloaded_pvc_modal.png' });
  console.log('Saved screenshot_reloaded_pvc_modal.png');

  // Check if modal text is present
  const bodyText = await page.evaluate(() => document.body.innerText);
  console.log('Body contains "Specification Refinement Needed":', bodyText.includes('Specification Refinement Needed'));
  console.log('Body contains "IS 14735:1999":', bodyText.includes('IS 14735:1999'));

  // Click IS 14735:1999
  console.log('Clicking IS 14735:1999 option...');
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const opt = buttons.find(b => b.innerText.includes('IS 14735:1999'));
    if (opt) opt.click();
  });

  console.log('Waiting 4s for recommendation to resolve...');
  await new Promise(r => setTimeout(r, 4000));

  await page.screenshot({ path: 'C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c/screenshot_reloaded_pvc_result.png' });
  console.log('Saved screenshot_reloaded_pvc_result.png');

  const afterText = await page.evaluate(() => document.body.innerText);
  console.log('After selection, body contains "Recommended Standard":', afterText.includes('Recommended Standard'));

  await browser.close();
  console.log('Finished successfully!');
}

main().catch(console.error);
