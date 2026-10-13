const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  await page.goto('http://localhost:3000/recommend');
  const ta = await page.$('textarea');
  await ta.type('pvc');
  await page.keyboard.press('Enter');
  await page.waitForSelector('h2');
  console.log('Modal opened!');
  const input = await page.$('div[style*="fixed"] input[type="text"]');
  await input.type('Unplasticized PVC pipes for potable water supply IS 4985');
  console.log('Typed into modal input!');
  const btn = await page.$('div[style*="fixed"] button[type="submit"]');
  console.log('Button found?', !!btn);
  await btn.click();
  console.log('Clicked recommend button in modal!');
  await new Promise(r => setTimeout(r, 6000));
  const text = await page.evaluate(() => document.body.innerText);
  console.log('Body text snippet after 6s:', text.slice(0, 400));
  await browser.close();
})();
