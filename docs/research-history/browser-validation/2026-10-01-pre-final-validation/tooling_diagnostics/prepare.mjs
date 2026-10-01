import { chromium, firefox, webkit } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import os from 'node:os';
import playwrightPackage from '@playwright/test/package.json' with { type: 'json' };
import lighthousePackage from 'lighthouse/package.json' with { type: 'json' };

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
const phase = process.argv[2];
if (!root || !runId || !['start', 'end'].includes(phase)) throw new Error('Usage: EVIDENCE_DIR=... RUN_ID=... node prepare.mjs start|end');
const command = (name, args = []) => {
  try { return execFileSync(name, args, { encoding: 'utf8', timeout: 60000 }).trim(); }
  catch (error) { return `UNAVAILABLE: ${error.message}`; }
};
const now = () => new Date().toISOString();
await mkdir(join(root, 'logs'), { recursive: true });
if (phase === 'start') {
  const versions = {};
  const launchErrors = {};
  for (const [name, type] of Object.entries({ chromium, firefox, webkit })) {
    try {
      const browser = await type.launch();
      versions[name] = browser.version();
      await browser.close();
    } catch (error) {
      versions[name] = null;
      launchErrors[name] = error.message;
    }
  }
  const env = {
    run_id: runId,
    repository_url: command('git', ['remote', 'get-url', 'origin']),
    repository_sha: command('git', ['rev-parse', 'HEAD']),
    branch: command('git', ['branch', '--show-current']),
    production_url: 'https://pse-pulse.vercel.app/',
    test_start_timestamp: now(),
    timezone: 'Asia/Manila',
    operating_system: os.type(),
    macos_version: command('sw_vers', ['-productVersion']),
    cpu_architecture: os.arch(),
    machine_model: command('sysctl', ['-n', 'hw.model']),
    node_version: process.version,
    npm_version: command('npm', ['--version']),
    playwright_version: playwrightPackage.version,
    ...Object.fromEntries(Object.entries(versions).map(([key, value]) => [`${key}_version`, value])),
    browser_launch_errors: launchErrors,
    lighthouse_version: lighthousePackage.version,
    network_test_mode: 'Live production site over the current Mac network connection',
    network_throttling_used_for_primary_threshold: false,
    lighthouse_throttling: 'Lighthouse default simulation; supplementary only',
    website_authentication_required: false,
    screen_capture_method: 'Playwright page.screenshot (engine-rendered)',
    tester_environment: 'Local macOS arm64 laptop; Playwright headless engines',
    deployment_sha_status: 'Not independently resolved from public response',
  };
  await writeFile(join(root, 'test_environment.json'), JSON.stringify(env, null, 2) + '\n');
  const network = command('networkQuality', ['-c']);
  await writeFile(join(root, 'logs', 'environment.log'), [
    `$ sw_vers\n${command('sw_vers')}`,
    `$ uname -a\n${command('uname', ['-a'])}`,
    `$ node --version\n${command('node', ['--version'])}`,
    `$ npm --version\n${command('npm', ['--version'])}`,
    `$ networkQuality -c\n${network}`,
  ].join('\n\n') + '\n');
}
const response = await fetch('https://pse-pulse.vercel.app/', { redirect: 'follow' });
const html = await response.text();
const hash = createHash('sha256').update(html).digest('hex');
const identity = {
  timestamp: now(),
  request_url: 'https://pse-pulse.vercel.app/',
  final_url: response.url,
  http_status: response.status,
  headers: Object.fromEntries(response.headers),
  html_sha256: hash,
  html_bytes: Buffer.byteLength(html),
  deployment_sha_note: 'Public response does not independently identify a Git deployment SHA',
};
await writeFile(join(root, 'logs', `live_site_identity_${phase}.log`), JSON.stringify(identity, null, 2) + '\n');
console.log(`[identity ${phase}] HTTP ${response.status}, HTML SHA-256 ${hash}`);
