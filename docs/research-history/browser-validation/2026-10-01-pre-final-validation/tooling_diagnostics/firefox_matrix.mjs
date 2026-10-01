import { writeFile, mkdir } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { startSystemFirefox } from './firefox_session.mjs';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
const mode = process.argv[2];
if (!root || !runId || !['retest', 'final_run'].includes(mode)) throw new Error('Usage: EVIDENCE_DIR=... RUN_ID=... node firefox_matrix.mjs retest|final_run');
const output = join(root, mode);
const routes = ['/', '/companies', '/companies/ALI', '/companies/GLO', '/watchlist', '/compare', '/learn-stocks', '/about'];
const viewports = [['mobile',390,844], ['desktop',1440,900]];
const routeFilter = process.env.FIREFOX_ROUTE;
const viewportFilter = process.env.FIREFOX_VIEWPORT;
const repeats = Number(process.env.REPEAT ?? 1);
const resultFile = process.env.RESULT_FILE ?? 'firefox_cross_browser_results.csv';
if (!Number.isInteger(repeats) || repeats < 1) throw new Error('REPEAT must be a positive integer');
const fields = ['run_id','timestamp','browser_engine','browser_version','route','viewport','http_status','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','status','notes'];
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"','""').replaceAll('\n',' ')}"`;
const csv = (rows) => [fields.join(','), ...rows.map((row) => fields.map((field)=>csvEscape(row[field])).join(','))].join('\n') + '\n';
const slug = (route) => route === '/' ? 'home' : route.slice(1).replaceAll('/','_');
const sameOrigin = (address) => { try { return new URL(address).origin === 'https://pse-pulse.vercel.app'; } catch { return false; } };
const critical = (address) => sameOrigin(address) && (address.endsWith('.js') || address.endsWith('.css') || address.includes('/forecasts/') || routes.some((route)=>new URL(route,'https://pse-pulse.vercel.app').href===address));
const rows = [];
const raw = [];
await mkdir(join(output,'logs'), { recursive: true });

async function setViewport(driver, bidi, width, height) {
  const context = await driver.getWindowHandle();
  const result = await bidi.send({ method: 'browsingContext.setViewport', params: { context, viewport: { width, height }, devicePixelRatio: 1 } });
  if (result.type !== 'success') throw new Error(`Firefox BiDi viewport override failed: ${JSON.stringify(result)}`);
  return driver.executeScript('return {width: innerWidth, height: innerHeight}');
}

async function inspect(driver, route, width) {
  await driver.wait(async () => driver.executeScript('return !!document.querySelector("main h1") && !!document.querySelector("main h1").getBoundingClientRect().height'), 15000);
  if (route === '/compare' || route.startsWith('/companies/')) await driver.wait(async () => driver.executeScript('return !!document.querySelector("main .recharts-surface")'), 15000);
  return driver.executeScript((route, width) => {
    const main = document.querySelector('main');
    const heading = main?.querySelector('h1');
    const h = heading?.getBoundingClientRect();
    const navbar = document.querySelector('body > nav');
    const n = navbar?.getBoundingClientRect();
    const visible = (element) => !!element && getComputedStyle(element).visibility !== 'hidden' && element.getBoundingClientRect().height > 0;
    const headings = [...(main?.querySelectorAll('h1,h2') ?? [])].map((element)=>element.textContent?.trim());
    const links = (element)=>[...(element?.querySelectorAll('a') ?? [])].filter(visible).map((link)=>link.textContent?.trim());
    const mobile = document.querySelector('nav[aria-label="Mobile Navigation"]');
    const navUsable = width < 768 ? visible(mobile) && links(mobile).some((x)=>x?.includes('Companies')) && links(mobile).some((x)=>x?.includes('About')) : links(navbar).some((x)=>x === 'Companies');
    const svg = !!main?.querySelector('.recharts-surface');
    let core = true;
    if (route === '/compare') core = headings.includes('Model Leaderboard') && svg;
    else if (route.startsWith('/companies/')) core = headings.includes(route.split('/').at(-1)) && svg && headings.includes('Next-Day Prediction');
    else if (route === '/watchlist') core = headings.includes('My Watchlist');
    else if (route === '/companies') core = headings.includes('Company List');
    else if (route === '/learn-stocks') core = headings.some((x)=>x?.includes('4-Step Learning Path'));
    else if (route === '/about') core = headings.includes('About PSE Pulse');
    const fixedCover = [...document.querySelectorAll('*')].filter((el)=>{
      if (getComputedStyle(el).position !== 'fixed') return false;
      const r = el.getBoundingClientRect();
      return h && r.width > innerWidth*.7 && r.height > innerHeight*.25 && r.top < h.bottom && r.bottom > h.top;
    }).length;
    return {
      primary: visible(main) && visible(heading), core, navUsable,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      viewportWidth: innerWidth, viewportHeight: innerHeight,
      headingClipped: !h || h.left < -2 || h.right > innerWidth+2,
      navOverflow: !!n && (n.left < -2 || n.right > innerWidth+2), fixedCover,
      navigationStatus: performance.getEntriesByType('navigation')[0]?.responseStatus ?? null,
    };
  }, route, width);
}

for (const [category,width,height] of viewports.filter(([name])=>!viewportFilter || name===viewportFilter)) {
  for (const route of routes.filter((name)=>!routeFilter || name===routeFilter)) {
    for (let attempt = 1; attempt <= repeats; attempt++) {
    const timestamp = new Date().toISOString();
    const label = `firefox_${category}_${width}x${height}_${slug(route)}${repeats > 1 ? `_attempt${attempt}` : ''}`;
    console.log(`[Firefox ${mode}] ${route} ${width}x${height} attempt ${attempt}/${repeats}`);
    let session, state, httpStatus = null, status = 'FAIL';
    const observed = { pageerrors: [], consoleErrors: [], criticalFailures: [], responses: [] };
    const notes = [];
    try {
      session = await startSystemFirefox(join(output,'logs'), `${label}_geckodriver.log`);
      const { driver } = session;
      await driver.manage().window().setRect({ width, height, x: 0, y: 0 });
      const bidi = await driver.getBidi();
      await bidi.subscribe('log.entryAdded');
      await bidi.subscribe('network.responseCompleted');
      await bidi.subscribe('network.fetchError');
      const socket = await bidi.socket;
      socket.on('message', (message) => {
        let event;
        try { event = JSON.parse(message.toString()); } catch { return; }
        const p = event.params;
        if (event.method === 'log.entryAdded') {
          if (p?.type === 'javascript') observed.pageerrors.push(p.text ?? 'JavaScript exception');
          if (p?.type === 'console' && p.level === 'error') observed.consoleErrors.push(p.text ?? 'console error');
        }
        if (event.method === 'network.responseCompleted') {
          const address = p?.request?.url;
          const code = p?.response?.status;
          if (address && sameOrigin(address)) observed.responses.push({ address, code, navigation: p.navigation });
          if (address && code >= 400 && critical(address)) observed.criticalFailures.push(`${code} ${address}`);
        }
        if (event.method === 'network.fetchError' && critical(p?.request?.url ?? '')) observed.criticalFailures.push(`${p.errorText} ${p.request.url}`);
      });
      await driver.get(new URL(route,'https://pse-pulse.vercel.app').href);
      const actualViewport = await setViewport(driver,bidi,width,height);
      if (actualViewport.width !== width || actualViewport.height !== height) notes.push(`inner viewport ${actualViewport.width}x${actualViewport.height}, expected ${width}x${height}`);
      state = await inspect(driver,route,width);
      await new Promise((resolve)=>setTimeout(resolve,250));
      const target = new URL(route,'https://pse-pulse.vercel.app').href;
      httpStatus = observed.responses.find((item)=>item.address===target)?.code ?? state.navigationStatus;
      if (httpStatus !== 200) notes.push(`HTTP status ${httpStatus ?? 'unavailable'}`);
      if (!state.primary) notes.push('primary content hidden');
      if (!state.core) notes.push('route-specific content missing');
      if (!state.navUsable) notes.push('navigation unusable');
      if (state.documentWidth > width+2 || state.bodyWidth > width+2) notes.push(`horizontal overflow doc=${state.documentWidth} body=${state.bodyWidth}`);
      if (state.headingClipped) notes.push('heading clipped');
      if (state.navOverflow) notes.push('navigation overflow');
      if (state.fixedCover) notes.push('major fixed element obscures heading');
      if (observed.pageerrors.length) notes.push(`${observed.pageerrors.length} pageerror(s)`);
      if (observed.consoleErrors.length) notes.push(`${observed.consoleErrors.length} console error(s)`);
      if (observed.criticalFailures.length) notes.push(`${observed.criticalFailures.length} critical request failure(s)`);
      status = notes.length ? 'FAIL' : 'PASS';
      if (status !== 'PASS' || (route === '/compare' && category === 'desktop') || (route === '/companies/ALI' && category === 'mobile')) {
        const screenshot = join(output,'screenshots','firefox',`${label}${status === 'PASS' ? '' : '_FAIL'}.png`);
        await mkdir(join(output,'screenshots','firefox'), { recursive: true });
        const encoded = typeof driver.takeFullPageScreenshot === 'function' ? await driver.takeFullPageScreenshot() : await driver.takeScreenshot();
        await writeFile(screenshot,Buffer.from(encoded,'base64'));
        if (status !== 'PASS') await writeFile(screenshot.replace(/\.png$/,'.html'), await driver.getPageSource());
      }
    } catch (error) {
      notes.push(error.stack ?? error.message);
      if (session) {
        const screenshot = join(output,'screenshots','firefox',`${label}_FAIL.png`);
        await mkdir(join(output,'screenshots','firefox'), { recursive: true });
        try { await writeFile(screenshot,Buffer.from(await session.driver.takeScreenshot(),'base64')); } catch { /* navigation may have destroyed the window */ }
        try { await writeFile(screenshot.replace(/\.png$/,'.html'),await session.driver.getPageSource()); } catch { /* preserve the error row even if HTML is unavailable */ }
      }
    }
    finally { if (session) await session.close(); }
    const row = { run_id: runId, timestamp, browser_engine: 'firefox', browser_version: session?.version ?? '157.0', route, viewport: `${width}x${height}`, http_status: httpStatus ?? '', primary_content_visible: !!state?.primary, horizontal_overflow: state ? state.documentWidth > width+2 || state.bodyWidth > width+2 : '', pageerror_count: observed.pageerrors.length, console_error_count: observed.consoleErrors.length, critical_request_failure_count: observed.criticalFailures.length, status, notes: `${repeats > 1 ? `attempt ${attempt}/${repeats} | ` : ''}${[...notes,...observed.pageerrors,...observed.consoleErrors,...observed.criticalFailures].join(' | ')}` };
    rows.push(row);
    raw.push({ row, state, observed });
    await writeFile(join(output,resultFile),csv(rows));
    await writeFile(join(output,resultFile.replace(/\.csv$/,'.raw.json')),JSON.stringify(raw,null,2)+'\n');
    }
  }
}
console.log(`[Firefox ${mode} complete] ${rows.filter((row)=>row.status==='PASS').length}/${rows.length} PASS`);
