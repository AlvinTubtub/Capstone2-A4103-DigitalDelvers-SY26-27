import { Builder, By, until } from 'selenium-webdriver';
import firefox from 'selenium-webdriver/firefox.js';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, open, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import net from 'node:net';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const logs = join(root, 'retest', 'logs');
await mkdir(logs, { recursive: true });
const lines = [`Timestamp: ${new Date().toISOString()}`, 'Method: LaunchServices + isolated temporary Firefox profile + documented geckodriver --connect-existing'];
const port = 2828;
const listener = () => execFileSync('lsof', ['-nP', `-tiTCP:${port}`, '-sTCP:LISTEN'], { encoding: 'utf8' }).trim();
try {
  const prior = listener();
  throw new Error(`Refusing to use occupied Marionette port ${port}: PID ${prior}`);
} catch (error) { if (!/Command failed/.test(error.message)) throw error; }

const profile = await mkdtemp('/private/tmp/pse-pulse-firefox-profile-');
lines.push(`Temporary profile: ${profile}`);
let driver;
let launchedPid = null;
const serviceLog = await open(join(logs, 'geckodriver_connect_existing.log'), 'w');
try {
  const args = ['-n', '-a', '/Applications/Firefox.app', '--args', '-headless', '-no-remote', '-profile', profile, '--marionette'];
  lines.push(`$ open ${args.join(' ')}`);
  lines.push(execFileSync('open', args, { encoding: 'utf8', timeout: 30000 }) || '(open returned no output)');
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      const pid = listener();
      if (/^\d+$/.test(pid)) { launchedPid = Number(pid); break; }
    } catch { /* port not yet listening */ }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  if (!launchedPid) throw new Error('Temporary Firefox did not open Marionette port 2828 within 20 seconds');
  lines.push(`Isolated Firefox Marionette PID: ${launchedPid}`);
  const service = new firefox.ServiceBuilder('/Users/alvintubtub/.cache/selenium/geckodriver/mac-arm64/0.37.1/geckodriver')
    .addArguments('--connect-existing', '--marionette-port', String(port))
    .enableVerboseLogging()
    .setStdio(['ignore', serviceLog.fd, serviceLog.fd]);
  const options = new firefox.Options().setBinary('/Applications/Firefox.app/Contents/MacOS/firefox');
  options.setPageLoadStrategy('eager');
  driver = await new Builder().forBrowser('firefox').setFirefoxOptions(options).setFirefoxService(service).build();
  await driver.manage().setTimeouts({ pageLoad: 30000, script: 15000 });
  const capabilities = await driver.getCapabilities();
  lines.push(`Browser version: ${capabilities.get('browserVersion')}`);
  await driver.get('https://pse-pulse.vercel.app/');
  const heading = await driver.wait(until.elementLocated(By.css('main h1')), 15000);
  if (!await heading.isDisplayed()) throw new Error('Primary heading hidden');
  lines.push(`Page title: ${await driver.getTitle()}`);
  lines.push(`Final URL: ${await driver.getCurrentUrl()}`);
  lines.push('Smoke result: PASS');
} catch (error) {
  lines.push(`Smoke result: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (driver) await driver.quit().catch((error) => lines.push(`WebDriver quit warning: ${error.message}`));
  if (launchedPid) {
    try { process.kill(launchedPid, 'SIGTERM'); lines.push(`Stopped isolated Firefox PID ${launchedPid}`); }
    catch (error) { lines.push(`Isolated Firefox stop warning: ${error.message}`); }
  }
  await serviceLog.close();
  await writeFile(join(logs, 'firefox_launchservices_probe.log'), lines.join('\n') + '\n');
  console.log(lines.filter((line) => line.startsWith('Smoke result:')).at(-1));
}
