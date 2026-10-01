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
  session = await startSystemFirefox(logs, 'geckodriver_viewport_probe2.log');
  const { driver } = session;
  await driver.get('https://pse-pulse.vercel.app/');
  const bidi = await driver.getBidi();
  lines.push(`Window handles: ${JSON.stringify(await driver.getAllWindowHandles())}`);
  lines.push(`Current handle: ${await driver.getWindowHandle()}`);
  const tree = await bidi.send({ method: 'browsingContext.getTree', params: {} });
  lines.push(`BiDi tree: ${JSON.stringify(tree)}`);
  for (const item of tree.result?.contexts ?? []) {
    const result = await bidi.send({ method: 'browsingContext.setViewport', params: { context: item.context, viewport: { width: 390, height: 844 }, devicePixelRatio: 1 } });
    lines.push(`Set viewport on ${item.context}: ${JSON.stringify(result)}`);
  }
  lines.push(`Measured: ${JSON.stringify(await driver.executeScript('return {width:innerWidth,height:innerHeight}'))}`);
} catch (error) {
  lines.push(`Probe error: ${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (session) await session.close();
  await writeFile(join(logs, 'firefox_viewport_probe2.log'), lines.join('\n') + '\n');
  console.log(lines.at(-1));
}
