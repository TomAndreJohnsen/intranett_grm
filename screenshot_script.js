const puppeteer = require('puppeteer');

(async () => {
  // Launch the browser
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // Navigate to VG.no
  await page.goto('https://www.vg.no', { waitUntil: 'networkidle0' });

  // Take a screenshot
  await page.screenshot({ path: 'test.png', fullPage: true });

  console.log('Screenshot saved as test.png');

  // Close the browser
  await browser.close();
})();