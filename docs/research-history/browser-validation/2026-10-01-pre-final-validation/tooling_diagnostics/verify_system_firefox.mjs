import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { firefox } from '@playwright/test';
import playwrightPackage from '@playwright/test/package.json' with { type: 'json' };

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const executable = '/Applications/Firefox.app/Contents/MacOS/firefox';
const bundled = firefox.executablePath();
const commands = [
  ['ls', ['-ld', '/Applications/Firefox.app']],
  ['ls', ['-l', '/Applications/Firefox.app/Contents/MacOS/']],
  [executable, ['--version']],
  ['file', [executable]],
  ['sw_vers', []],
  ['mdls', ['/Applications/Firefox.app']],
];
const lines = [`Timestamp: ${new Date().toISOString()}`, `Playwright version: ${playwrightPackage.version}`, `Installed Mozilla Firefox executable: ${executable}`, `Bundled Playwright Firefox executable: ${bundled}`];
for (const [name, args] of commands) {
  try { lines.push(`$ ${name} ${args.join(' ')}\n${execFileSync(name, args, { encoding: 'utf8', timeout: 30000 })}`); }
  catch (error) { lines.push(`$ ${name} ${args.join(' ')}\nEXIT ${error.status}: ${error.stdout ?? ''}${error.stderr ?? error.message}`); }
}
await mkdir(join(root, 'retest', 'logs'), { recursive: true });
await writeFile(join(root, 'retest', 'logs', 'system_firefox_verification.log'), lines.join('\n\n') + '\n');
console.log(`Installed Mozilla Firefox: ${executable}; Playwright bundled Firefox: ${bundled}`);
