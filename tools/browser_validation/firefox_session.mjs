import { Builder } from 'selenium-webdriver';
import firefox from 'selenium-webdriver/firefox.js';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, open, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

const geckodriver = process.env.GECKODRIVER_PATH ?? join(homedir(), '.cache/selenium/geckodriver/mac-arm64/0.37.1/geckodriver');
const application = process.env.FIREFOX_APP_PATH ?? '/Applications/Firefox.app';
const port = 2828;
const listeningPid = () => {
  try {
    const output = execFileSync('lsof', ['-nP', `-tiTCP:${port}`, '-sTCP:LISTEN'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    return /^\d+$/.test(output) ? Number(output) : null;
  } catch { return null; }
};

export async function startSystemFirefox(logDirectory, serviceLogName = 'geckodriver.log') {
  if (listeningPid()) throw new Error(`Marionette port ${port} is occupied; refusing to attach to an existing session`);
  await mkdir(logDirectory, { recursive: true });
  const profile = await mkdtemp('/private/tmp/pse-pulse-firefox-profile-');
  const serviceLog = await open(join(logDirectory, serviceLogName), 'w');
  let pid = null;
  let driver = null;
  try {
    execFileSync('open', ['-n', '-a', application, '--args', '-headless', '-no-remote', '-profile', profile, '--marionette', '--remote-debugging-port'], { encoding: 'utf8', timeout: 30000 });
    for (let attempt = 0; attempt < 100; attempt++) {
      pid = listeningPid();
      if (pid) break;
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    if (!pid) throw new Error('Isolated Firefox did not open Marionette port within 20 seconds');
    const service = new firefox.ServiceBuilder(geckodriver)
      .addArguments('--connect-existing', '--marionette-port', String(port))
      .enableVerboseLogging()
      .setStdio(['ignore', serviceLog.fd, serviceLog.fd]);
    const options = new firefox.Options().setBinary(join(application, 'Contents', 'MacOS', 'firefox'));
    // Usability is determined by the route landmark, not Firefox's later load event.
    options.setPageLoadStrategy('none');
    options.enableBidi();
    driver = await new Builder().forBrowser('firefox').setFirefoxOptions(options).setFirefoxService(service).build();
    await driver.manage().setTimeouts({ pageLoad: 30000, script: 15000 });
    const capabilities = await driver.getCapabilities();
    return {
      driver, profile, pid,
      version: capabilities.get('browserVersion'),
      bidiUrl: capabilities.get('webSocketUrl'),
      async close() {
        await driver.quit().catch(() => {});
        try { process.kill(pid, 'SIGTERM'); } catch { /* already stopped */ }
        for (let attempt = 0; attempt < 50 && listeningPid() === pid; attempt++) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        await serviceLog.close();
        if (listeningPid() !== pid) await rm(profile, { recursive: true, force: true });
      },
    };
  } catch (error) {
    if (driver) await driver.quit().catch(() => {});
    if (pid) try { process.kill(pid, 'SIGTERM'); } catch { /* already stopped */ }
    await serviceLog.close();
    if (!pid || listeningPid() !== pid) await rm(profile, { recursive: true, force: true });
    throw error;
  }
}
