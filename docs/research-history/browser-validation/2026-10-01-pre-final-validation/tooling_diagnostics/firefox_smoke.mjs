import { firefox } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
let browser;
const log = [`Timestamp: ${new Date().toISOString()}`, 'URL: https://pse-pulse.vercel.app/'];
try {
  browser = await firefox.launch({ headless: true });
  log.push(`Firefox version: ${browser.version()}`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const response = await page.goto('https://pse-pulse.vercel.app/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.locator('main h1').first().waitFor({ state: 'visible', timeout: 15000 });
  log.push(`HTTP status: ${response?.status()}`);
  log.push(`Page title: ${await page.title()}`);
  log.push(`Primary landmark: ${await page.locator('main').isVisible()}`);
  if (response?.status() !== 200) throw new Error('Home response was not HTTP 200');
  log.push('Smoke result: PASS');
  await context.close();
} catch (error) {
  log.push(`Smoke result: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  await mkdir(join(root, 'retest', 'logs'), { recursive: true });
  await writeFile(join(root, 'retest', 'logs', 'firefox_smoke_test.log'), log.join('\n') + '\n');
  console.log(log.at(-1));
}
