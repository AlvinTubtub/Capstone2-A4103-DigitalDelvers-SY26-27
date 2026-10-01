import { Builder, By, until } from 'selenium-webdriver';
import firefox from 'selenium-webdriver/firefox.js';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const executable = '/Applications/Firefox.app/Contents/MacOS/firefox';
const lines = [`Timestamp: ${new Date().toISOString()}`, `Firefox binary: ${executable}`, 'Method: Selenium WebDriver with anonymous isolated Firefox profile'];
let driver;
try {
  const options = new firefox.Options().setBinary(executable).addArguments('-headless');
  options.setPageLoadStrategy('eager');
  driver = await new Builder().forBrowser('firefox').setFirefoxOptions(options).build();
  await driver.manage().setTimeouts({ pageLoad: 30000, script: 15000 });
  const capabilities = await driver.getCapabilities();
  lines.push(`Browser version: ${capabilities.get('browserVersion')}`);
  lines.push(`Geckodriver version: ${capabilities.get('moz:geckodriverVersion')}`);
  await driver.get('https://pse-pulse.vercel.app/');
  const heading = await driver.wait(until.elementLocated(By.css('main h1')), 15000);
  if (!await heading.isDisplayed()) throw new Error('Primary heading not visible');
  lines.push(`Page title: ${await driver.getTitle()}`);
  lines.push(`Final URL: ${await driver.getCurrentUrl()}`);
  lines.push(`Primary content status: ${await heading.isDisplayed()}`);
  lines.push('Smoke result: PASS');
} catch (error) {
  lines.push(`Smoke result: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (driver) await driver.quit().catch((error) => lines.push(`Driver close error: ${error.message}`));
  await mkdir(join(root, 'retest', 'logs'), { recursive: true });
  await writeFile(join(root, 'retest', 'logs', 'system_firefox_webdriver_smoke_test.log'), lines.join('\n') + '\n');
  console.log(lines.at(-1));
}
