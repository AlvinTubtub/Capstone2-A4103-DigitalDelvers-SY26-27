import { startSystemFirefox } from './firefox_session.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const logs = join(root, 'retest', 'logs');
await mkdir(logs, { recursive: true });
let session;
const lines = [`Timestamp: ${new Date().toISOString()}`, 'Requested viewport: 390x844 CSS pixels'];
try {
  session = await startSystemFirefox(logs, 'geckodriver_viewport_probe.log');
  const bidi = await session.driver.getBidi();
  const context = await session.driver.getWindowHandle();
  const result = await bidi.send({ method: 'browsingContext.setViewport', params: { context, viewport: { width: 390, height: 844 }, devicePixelRatio: 1 } });
  lines.push(`BiDi setViewport result: ${JSON.stringify(result)}`);
  await session.driver.get('https://pse-pulse.vercel.app/');
  const measured = await session.driver.executeScript('return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth}');
  lines.push(`Measured: ${JSON.stringify(measured)}`);
  lines.push(measured.width === 390 && measured.height === 844 ? 'Viewport probe: PASS' : 'Viewport probe: FAIL');
  if (measured.width !== 390 || measured.height !== 844) process.exitCode = 1;
} catch (error) {
  lines.push(`Viewport probe: FAIL\n${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  if (session) await session.close();
  await writeFile(join(logs, 'firefox_viewport_probe.log'), lines.join('\n') + '\n');
  console.log(lines.at(-1));
}
