import { firefox } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const executable = '/Applications/Firefox.app/Contents/MacOS/firefox';
const lines = [`Timestamp: ${new Date().toISOString()}`, `Executable: ${executable}`, 'Method: Playwright firefox.launch({ executablePath }); isolated temporary context/profile'];
let browser;
try {
  browser = await firefox.launch({ executablePath: executable, headless: true, timeout: 30000 });
  lines.push(`Browser version: ${browser.version()}`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const response = await page.goto('https://pse-pulse.vercel.app/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.locator('main h1').first().waitFor({ state: 'visible', timeout: 15000 });
  lines.push(`HTTP status: ${response?.status()}`);
  lines.push(`Page title: ${await page.title()}`);
  lines.push(`Final URL: ${page.url()}`);
  lines.push(`Primary content visible: ${await page.locator('main').isVisible()}`);
  if (response?.status() !== 200) throw new Error('Non-200 response');
  lines.push('Smoke result: PASS');
  await context.close();
} catch (error) {
  lines.push(`Smoke result: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  await mkdir(join(root, 'retest', 'logs'), { recursive: true });
  await writeFile(join(root, 'retest', 'logs', 'system_firefox_smoke_test.log'), lines.join('\n') + '\n');
  console.log(lines.at(-1));
}
