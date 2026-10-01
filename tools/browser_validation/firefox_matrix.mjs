import { writeFile, mkdir } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { performance } from 'node:perf_hooks';
import { startSystemFirefox } from './firefox_session.mjs';
import { runBoundedTransportCase } from './transport_retry.mjs';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
const mode = process.argv[2];
if (!root || !runId || !['retest', 'final_run', 'preflight'].includes(mode)) throw new Error('Usage: EVIDENCE_DIR=... RUN_ID=... node firefox_matrix.mjs retest|final_run|preflight');
const output = process.env.OUTPUT_DIR ?? join(root, mode);
const routes = ['/', '/companies', '/companies/ALI', '/companies/GLO', '/watchlist', '/compare', '/learn-stocks', '/about'];
const viewports = [['mobile',390,844], ['desktop',1440,900]];
const routeFilter = process.env.FIREFOX_ROUTE;
const viewportFilter = process.env.FIREFOX_VIEWPORT;
const repeats = Number(process.env.REPEAT ?? 1);
const resultFile = process.env.RESULT_FILE ?? 'firefox_cross_browser_results.csv';
if (!Number.isInteger(repeats) || repeats < 1) throw new Error('REPEAT must be a positive integer');
const fields = ['run_id','timestamp','browser','browser_engine','browser_version','route','viewport','navigation_start','response_received_ms','http_status','domcontentloaded_time_ms','document_ready_state','primary_landmark_visible_ms','usable_page_load_ms','window_load_time_ms','browser_navigation_error','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','status','notes','logical_case_id','transport_attempt_count','transport_retry_used','first_attempt_transport_status','final_document_http_status','usable_state_ms','assertion_status','final_status'];
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"','""').replaceAll('\n',' ')}"`;
const csv = (rows) => [fields.join(','), ...rows.map((row) => fields.map((field)=>csvEscape(row[field])).join(','))].join('\n') + '\n';
const slug = (route) => route === '/' ? 'home' : route.slice(1).replaceAll('/','_');
const sameOrigin = (address) => { try { return new URL(address).origin === 'https://pse-pulse.vercel.app'; } catch { return false; } };
const critical = (address) => sameOrigin(address) && (address.endsWith('.js') || address.endsWith('.css') || address.includes('/forecasts/') || routes.some((route)=>new URL(route,'https://pse-pulse.vercel.app').href===address));
const rows = [];
const raw = [];
const transportAttempts = [];
await mkdir(join(output,'logs'), { recursive: true });

async function setViewport(driver, bidi, width, height) {
  const context = await driver.getWindowHandle();
  const result = await bidi.send({ method: 'browsingContext.setViewport', params: { context, viewport: { width, height }, devicePixelRatio: 1 } });
  if (result.type !== 'success') throw new Error(`Firefox BiDi viewport override failed: ${JSON.stringify(result)}`);
  return driver.executeScript('return {width: innerWidth, height: innerHeight}');
}

async function inspect(driver, route, width, deadline) {
  const remaining = () => Math.max(1, deadline - Date.now());
  await driver.wait(async () => driver.executeScript('return !!document.querySelector("main h1") && !!document.querySelector("main h1").getBoundingClientRect().height'), remaining());
  if (route === '/compare' || route.startsWith('/companies/')) await driver.wait(async () => driver.executeScript('return !!document.querySelector("main .recharts-surface")'), remaining());
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
      documentReadyState: document.readyState,
      domcontentloadedMs: performance.getEntriesByType('navigation')[0]?.domContentLoadedEventEnd || null,
      windowLoadMs: performance.getEntriesByType('navigation')[0]?.loadEventEnd || null,
    };
  }, route, width);
}

async function inspectAttempt(category,width,height,route,logicalNumber,attempt) {
    const timestamp = new Date().toISOString();
    const label = `firefox_${category}_${width}x${height}_${slug(route)}${repeats > 1 ? `_case${logicalNumber}` : ''}_attempt${attempt}`;
    console.log(`[Firefox ${mode}] ${route} ${width}x${height} logical ${logicalNumber}/${repeats} transport attempt ${attempt}/2`);
    let session, state, httpStatus = null, status = 'FAIL', appDomAvailable = null;
    let navigationStarted = null;
    const navigation = { navigation_start: '', response_received_ms: null, domcontentloaded_time_ms: null, document_ready_state: '', primary_landmark_visible_ms: null, usable_page_load_ms: null, window_load_time_ms: null, browser_navigation_error: '' };
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
          if (address === new URL(route,'https://pse-pulse.vercel.app').href && navigationStarted !== null) navigation.response_received_ms ??= performance.now() - navigationStarted;
          if (address && code >= 400 && critical(address)) observed.criticalFailures.push(`${code} ${address}`);
        }
        if (event.method === 'network.fetchError' && critical(p?.request?.url ?? '')) observed.criticalFailures.push(`${p.errorText} ${p.request.url}`);
      });
      const deadline = Date.now() + 30000;
      navigationStarted = performance.now();
      navigation.navigation_start = new Date().toISOString();
      const targetUrl = new URL(route,'https://pse-pulse.vercel.app').href;
      await driver.get(targetUrl);
      await driver.wait(async () => (await driver.executeScript('return location.href').catch(() => '')) === targetUrl, Math.max(1,deadline-Date.now()));
      const actualViewport = await setViewport(driver,bidi,width,height);
      if (actualViewport.width !== width || actualViewport.height !== height) notes.push(`inner viewport ${actualViewport.width}x${actualViewport.height}, expected ${width}x${height}`);
      state = await inspect(driver,route,width,deadline);
      navigation.primary_landmark_visible_ms = performance.now() - navigationStarted;
      navigation.usable_page_load_ms = navigation.primary_landmark_visible_ms;
      navigation.domcontentloaded_time_ms = state.domcontentloadedMs;
      navigation.window_load_time_ms = state.windowLoadMs;
      navigation.document_ready_state = state.documentReadyState;
      if (navigation.usable_page_load_ms > 30000) notes.push('usable landmark exceeded 30-second navigation ceiling');
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
      navigation.browser_navigation_error = error.message;
      notes.push(error.stack ?? error.message);
      if (session) {
        const screenshot = join(output,'screenshots','firefox',`${label}_FAIL.png`);
        await mkdir(join(output,'screenshots','firefox'), { recursive: true });
        try { await writeFile(screenshot,Buffer.from(await session.driver.takeScreenshot(),'base64')); } catch { /* navigation may have destroyed the window */ }
        try { const html = await session.driver.getPageSource(); appDomAvailable = /<main(?:\s|>)/i.test(html); await writeFile(screenshot.replace(/\.png$/,'.html'),html); } catch { /* unknown DOM state forbids a retry */ }
      }
    }
    finally { if (session) await session.close(); }
    httpStatus ??= observed.responses.find((item)=>item.address===new URL(route,'https://pse-pulse.vercel.app').href)?.code ?? null;
    const row = { run_id: runId, timestamp, browser: 'firefox', browser_engine: 'firefox', browser_version: session?.version ?? '157.0', route, viewport: `${width}x${height}`, ...navigation, http_status: httpStatus ?? '', primary_content_visible: !!state?.primary, horizontal_overflow: state ? state.documentWidth > width+2 || state.bodyWidth > width+2 : '', pageerror_count: observed.pageerrors.length, console_error_count: observed.consoleErrors.length, critical_request_failure_count: observed.criticalFailures.length, status, notes: `${repeats > 1 ? `logical ${logicalNumber}/${repeats} | ` : ''}${[...notes,...observed.pageerrors,...observed.consoleErrors,...observed.criticalFailures].join(' | ')}` };
    const mainDocumentResponseReceived = httpStatus !== null;
    let transportStatus = 'DOCUMENT_DELIVERED';
    if (!mainDocumentResponseReceived && appDomAvailable === false && !state && navigation.browser_navigation_error) transportStatus = 'TRANSPORT_NO_DOCUMENT';
    else if (httpStatus !== null && httpStatus >= 400) transportStatus = 'HTTP_APPLICATION_FAILURE';
    else if (navigation.browser_navigation_error && appDomAvailable) transportStatus = 'NAVIGATION_API_ONLY';
    else if (navigation.browser_navigation_error) transportStatus = 'APPLICATION_RUNTIME_FAILURE';
    else if (status !== 'PASS') transportStatus = 'UI_ASSERTION_FAILURE';
    return { row, state, observed, main_document_response_received: mainDocumentResponseReceived, app_dom_available: appDomAvailable === null ? (state ? !!state.primary : null) : appDomAvailable, assertions_executed: !!state, http_status: httpStatus, browser_navigation_error: navigation.browser_navigation_error, transport_status: transportStatus, status };
}

for (const [category,width,height] of viewports.filter(([name])=>!viewportFilter || name===viewportFilter)) {
  for (const route of routes.filter((name)=>!routeFilter || name===routeFilter)) {
    for (let logicalNumber = 1; logicalNumber <= repeats; logicalNumber++) {
      const logicalCaseId = `firefox_${category}_${width}x${height}_${slug(route)}${repeats > 1 ? `_case${logicalNumber}` : ''}`;
      const result = await runBoundedTransportCase((attempt)=>inspectAttempt(category,width,height,route,logicalNumber,attempt));
      const final = result.final;
      const row = { ...final.row, logical_case_id: logicalCaseId, transport_attempt_count: result.transport_attempt_count, transport_retry_used: result.transport_retry_used, first_attempt_transport_status: result.first_attempt_transport_status, final_document_http_status: final.http_status ?? '', usable_state_ms: final.row.usable_page_load_ms ?? '', assertion_status: final.assertions_executed ? final.status : 'NOT_RUN', final_status: final.status };
      rows.push(row);
      raw.push({ row, state: final.state, observed: final.observed });
      transportAttempts.push({ logical_case_id: logicalCaseId, attempts: result.attempts });
      await writeFile(join(output,resultFile),csv(rows));
      await writeFile(join(output,resultFile.replace(/\.csv$/,'.raw.json')),JSON.stringify(raw,null,2)+'\n');
      await writeFile(join(output,'firefox_transport_attempts.raw.json'),JSON.stringify(transportAttempts,null,2)+'\n');
    }
  }
}
console.log(`[Firefox ${mode} complete] ${rows.filter((row)=>row.status==='PASS').length}/${rows.length} PASS`);
