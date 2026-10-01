import { startSystemFirefox } from './firefox_session.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const logs = join(root, 'retest', 'logs');
await mkdir(logs, { recursive: true });
let session;
const lines = [`Timestamp: ${new Date().toISOString()}`];
try {
  session = await startSystemFirefox(logs, 'geckodriver_bidi_probe.log');
  lines.push(`Browser version: ${session.version}`);
  lines.push(`Temporary profile: ${session.profile}`);
  lines.push(`Isolated Firefox PID: ${session.pid}`);
  lines.push(`BiDi URL available: ${!!session.bidiUrl}`);
  const bidi = await session.driver.getBidi();
  await bidi.subscribe('log.entryAdded');
  const socket = await bidi.socket;
  const observed = [];
  socket.on('message', (message) => {
    const item = JSON.parse(message.toString());
    if (item.method === 'log.entryAdded') observed.push(item.params);
  });
  await session.driver.get('https://pse-pulse.vercel.app/');
  lines.push(`Title: ${await session.driver.getTitle()}`);
  lines.push(`BiDi log entries observed: ${observed.length}`);
  lines.push('BiDi probe: PASS');
} catch (error) {
  lines.push(`BiDi probe: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (session) await session.close();
  await writeFile(join(logs, 'firefox_bidi_probe.log'), lines.join('\n') + '\n');
  console.log(lines.at(-1));
}
