import { chromium } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { performance } from 'node:perf_hooks';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const output = join(root, 'retest');
const source = await readFile(join(output, 'original_timeout_inventory.csv'), 'utf8');
const [header, ...lines] = source.trim().split('\n');
const names = header.split(',');
const inventory = lines.map((line) => {
  const values = [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)].map((match)=>match[1].replaceAll('""','"'));
  if (values.length !== names.length) throw new Error(`Malformed inventory row: ${line}`);
  return Object.fromEntries(names.map((name,index)=>[name,values[index]]));
});
const fields = ['timeout_id','retest_attempt','timestamp','browser','route','viewport','navigation_ms','usable_page_load_ms','http_status','pageerror_count','console_error_count','critical_request_failure_count','status','error','screenshot'];
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"','""').replaceAll('\n',' ')}"`;
const csv = (rows) => [fields.join(','),...rows.map((row)=>fields.map((field)=>csvEscape(row[field])).join(','))].join('\n')+'\n';
const rows = [];
const sameOrigin = (address) => { try { return new URL(address).origin === 'https://pse-pulse.vercel.app'; } catch { return false; } };
const critical = (request) => sameOrigin(request.url()) && ['document','script','stylesheet','fetch','xhr'].includes(request.resourceType());

async function checks(page, route, width) {
  await page.locator('main h1').first().waitFor({ state: 'visible', timeout: 15000 });
  if (route === '/compare' || route.startsWith('/companies/')) await page.locator('main .recharts-surface').first().waitFor({ state: 'visible', timeout: 15000 });
  const facts = await page.evaluate(({route,width}) => {
    const main = document.querySelector('main');
    const h = main?.querySelector('h1');
    const rect = h?.getBoundingClientRect();
    const nav = document.querySelector('body > nav');
    const navRect = nav?.getBoundingClientRect();
    const visible = (el)=>!!el && getComputedStyle(el).visibility!=='hidden' && el.getBoundingClientRect().height>0;
    const titles = [...(main?.querySelectorAll('h1,h2') ?? [])].map((el)=>el.textContent?.trim());
    const mobile = document.querySelector('nav[aria-label="Mobile Navigation"]');
    const navLinks = (el)=>[...(el?.querySelectorAll('a') ?? [])].filter(visible).map((x)=>x.textContent?.trim());
    const navUsable = width<768 ? visible(mobile)&&navLinks(mobile).some((x)=>x?.includes('Companies'))&&navLinks(mobile).some((x)=>x?.includes('About')) : navLinks(nav).some((x)=>x==='Companies');
    let core = true;
    if (route==='/compare') core=titles.includes('Model Leaderboard')&&!!main?.querySelector('.recharts-surface');
    else if (route.startsWith('/companies/')) core=titles.includes(route.split('/').at(-1))&&titles.includes('Next-Day Prediction')&&!!main?.querySelector('.recharts-surface');
    else if (route==='/watchlist') core=titles.includes('My Watchlist');
    else if (route==='/companies') core=titles.includes('Company List');
    else if (route==='/learn-stocks') core=titles.some((x)=>x?.includes('4-Step Learning Path'));
    else if (route==='/about') core=titles.includes('About PSE Pulse');
    const fixedCover=[...document.querySelectorAll('*')].filter((el)=>{
      if(getComputedStyle(el).position!=='fixed')return false;
      const r=el.getBoundingClientRect();return rect&&r.width>innerWidth*.7&&r.height>innerHeight*.25&&r.top<rect.bottom&&r.bottom>rect.top;
    }).length;
    return { primary:visible(main)&&visible(h),core,navUsable,overflow:document.documentElement.scrollWidth>width+2||document.body.scrollWidth>width+2,headingClipped:!rect||rect.left< -2||rect.right>width+2,navOverflow:!!navRect&&(navRect.left< -2||navRect.right>width+2),fixedCover };
  },{route,width});
  return facts;
}

const browser = await chromium.launch();
try {
  for (const item of inventory) {
    if (item.browser !== 'chromium') throw new Error(`Unsupported original browser ${item.browser}`);
    const width=Number(item.viewport_width), height=Number(item.viewport_height);
    for(let attempt=1;attempt<=5;attempt++){
      console.log(`[timeout retest] ${item.timeout_id} ${item.route} ${width}x${height} ${attempt}/5`);
      const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
      const page=await context.newPage();
      const observed={pageerrors:[],consoleErrors:[],criticalFailures:[]};
      page.on('pageerror',(error)=>observed.pageerrors.push(error.message));
      page.on('console',(message)=>{if(message.type()==='error')observed.consoleErrors.push(message.text());});
      page.on('requestfailed',(request)=>{if(critical(request))observed.criticalFailures.push(`${request.url()} ${request.failure()?.errorText}`);});
      page.on('response',(response)=>{if(response.status()>=400&&critical(response.request()))observed.criticalFailures.push(`${response.status()} ${response.url()}`);});
      const timestamp=new Date().toISOString();
      const started=performance.now();
      let navMs=null,usableMs=null,response=null,status='FAIL',message='',screenshot='';
      try{
        response=await page.goto(new URL(item.route,'https://pse-pulse.vercel.app').href,{waitUntil:'domcontentloaded',timeout:30000});
        navMs=performance.now()-started;
        const facts=await checks(page,item.route,width);
        await page.waitForTimeout(250);
        usableMs=performance.now()-started;
        const errors=[];
        if(response?.status()!==200)errors.push(`HTTP ${response?.status()??'none'}`);
        if(!facts.primary)errors.push('primary hidden');
        if(!facts.core)errors.push('core content missing');
        if(!facts.navUsable)errors.push('navigation unusable');
        if(facts.overflow)errors.push('horizontal overflow');
        if(facts.headingClipped)errors.push('heading clipped');
        if(facts.navOverflow)errors.push('navigation overflow');
        if(facts.fixedCover)errors.push('major fixed element obscures heading');
        if(observed.pageerrors.length)errors.push(`${observed.pageerrors.length} pageerror(s)`);
        if(observed.consoleErrors.length)errors.push(`${observed.consoleErrors.length} console error(s)`);
        if(observed.criticalFailures.length)errors.push(`${observed.criticalFailures.length} critical failure(s)`);
        if(item.test_category==='performance'&&usableMs>5000)errors.push(`usable load ${usableMs.toFixed(2)} ms exceeds 5000 ms`);
        message=errors.join(' | ');
        status=errors.length?'FAIL':'PASS';
      }catch(error){
        const elapsed=performance.now()-started;
        if(navMs===null)navMs=elapsed;
        message=error.stack??error.message;
      }
      if(status!=='PASS'){
        const path=join(output,'screenshots','timeout_retests_valid',`${item.timeout_id}_attempt${attempt}_FAIL.png`);
        await mkdir(join(output,'screenshots','timeout_retests_valid'),{recursive:true});
        await page.screenshot({path,fullPage:true}).catch(()=>{});
        screenshot=relative(root,path);
        await writeFile(path.replace(/\.png$/,'.html'),await page.content().catch(()=>''));
      }
      rows.push({timeout_id:item.timeout_id,retest_attempt:attempt,timestamp,browser:'chromium',route:item.route,viewport:`${width}x${height}`,navigation_ms:navMs?.toFixed(2)??'',usable_page_load_ms:usableMs?.toFixed(2)??'',http_status:response?.status()??'',pageerror_count:observed.pageerrors.length,console_error_count:observed.consoleErrors.length,critical_request_failure_count:observed.criticalFailures.length,status,error:[message,...observed.pageerrors,...observed.consoleErrors,...observed.criticalFailures].filter(Boolean).join(' | '),screenshot});
      await writeFile(join(output,'timeout_retest_results.csv'),csv(rows));
      await context.close();
    }
  }
}finally{await browser.close();}
console.log(`[timeout retest complete] ${rows.filter((row)=>row.status==='PASS').length}/${rows.length} PASS`);
