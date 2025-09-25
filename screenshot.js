const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  console.log('🚀 Starting dashboard screenshot capture...');

  let browser;
  try {
    // Launch Puppeteer in headless mode
    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu'
      ]
    });

    console.log('📱 Browser launched successfully');

    // Create a new page
    const page = await browser.newPage();

    // Set viewport size for consistent screenshots
    await page.setViewport({
      width: 1920,
      height: 1080,
      deviceScaleFactor: 1
    });

    console.log('🔧 Viewport configured (1920x1080)');

    // Set screenshot mode headers to bypass authentication
    await page.setExtraHTTPHeaders({
      'X-Screenshot-Mode': 'true'
    });

    console.log('🔑 Screenshot mode headers set');

    // Navigate to the dashboard
    const dashboardUrl = 'http://localhost:5000/dashboard';
    console.log(`🌐 Navigating to ${dashboardUrl}...`);

    await page.goto(dashboardUrl, {
      waitUntil: 'networkidle2',
      timeout: 30000
    });

    console.log('✅ Dashboard loaded successfully');

    // Wait a bit more for any dynamic content (like newsletter cards) to load
    await new Promise(resolve => setTimeout(resolve, 2000));

    console.log('⏳ Waiting for dynamic content...');

    // Take a full-page screenshot
    const screenshotPath = path.resolve(__dirname, 'dashboard_screenshot.png');
    await page.screenshot({
      path: screenshotPath,
      fullPage: true,
      type: 'png'
    });

    console.log(`🎉 Screenshot saved successfully!`);
    console.log(`📁 File path: ${screenshotPath}`);

  } catch (error) {
    console.error('❌ Error capturing screenshot:', error.message);

    if (error.message.includes('ERR_CONNECTION_REFUSED')) {
      console.error('💡 Make sure the Flask app is running on http://localhost:5000');
      console.error('   Run: python3 main.py');
    } else if (error.message.includes('Navigation timeout')) {
      console.error('💡 The page took too long to load. Check if the server is responding.');
    }

    process.exit(1);
  } finally {
    // Close the browser
    if (browser) {
      await browser.close();
      console.log('🔒 Browser closed');
    }
  }
})();