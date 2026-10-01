import { Builder } from 'selenium-webdriver';
import firefox from 'selenium-webdriver/firefox.js';
import { open, mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const logs = join(root, 'retest', 'logs');
await mkdir(logs, { recursive: true });
const handle = await open(join(logs, 'geckodriver_verbose.log'), 'w');
let driver;
let errorText = '';
try {
  const service = new firefox.ServiceBuilder('/Users/alvintubtub/.cache/selenium/geckodriver/mac-arm64/0.37.1/geckodriver')
    .enableVerboseLogging(true)
    .setStdio(['ignore', handle.fd, handle.fd]);
  const options = new firefox.Options()
    .setBinary('/Applications/Firefox.app/Contents/MacOS/firefox')
    .addArguments('-headless');
  options.setPageLoadStrategy('eager');
  driver = await new Builder().forBrowser('firefox').setFirefoxOptions(options).setFirefoxService(service).build();
  console.log('WebDriver launch: PASS');
} catch (error) {
  errorText = error.stack ?? error.message;
  console.log(`WebDriver launch: FAIL\n${errorText}`);
  process.exitCode = 1;
} finally {
  if (driver) await driver.quit();
  await handle.close();
  await writeFile(join(logs, 'geckodriver_diagnostic_result.log'), `Timestamp: ${new Date().toISOString()}\n${errorText || 'PASS'}\n`);
}
