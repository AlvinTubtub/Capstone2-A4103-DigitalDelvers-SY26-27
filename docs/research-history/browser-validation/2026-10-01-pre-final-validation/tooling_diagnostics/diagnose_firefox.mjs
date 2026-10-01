import { firefox } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const log = [];
const command = (name, args = []) => {
  try {
    const output = execFileSync(name, args, { encoding: 'utf8', timeout: 60000, stdio: ['ignore', 'pipe', 'pipe'] });
    log.push(`$ ${name} ${args.join(' ')}\n${output}`);
  } catch (error) {
    log.push(`$ ${name} ${args.join(' ')}\nEXIT ${error.status}: ${error.stdout ?? ''}${error.stderr ?? ''}`);
  }
};
command('node', ['--version']);
command('npm', ['--version']);
command('npx', ['playwright', '--version']);
command('npx', ['playwright', 'install', '--dry-run']);
command('sw_vers');
command('uname', ['-m']);
const executable = firefox.executablePath();
command('ls', ['-ld', executable, '/Users/alvintubtub/Library/Caches/ms-playwright/firefox-1543']);
command('file', [executable]);
command('xattr', ['-l', executable]);
log.push(`Playwright Firefox executable: ${executable}`);
try {
  const browser = await firefox.launch({ headless: true });
  log.push(`Firefox launch: PASS, version ${browser.version()}`);
  await browser.close();
} catch (error) { log.push(`Firefox launch: FAIL\n${error.stack ?? error.message}`); }
await mkdir(join(root, 'retest', 'logs'), { recursive: true });
await writeFile(join(root, 'retest', 'logs', 'firefox_diagnosis.log'), log.join('\n\n') + '\n');
console.log(log.at(-1).slice(0, 700));
