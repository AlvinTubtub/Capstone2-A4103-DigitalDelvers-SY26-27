import { chromium, webkit } from '@playwright/test';
import { performance } from 'node:perf_hooks';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { startSystemFirefox } from './firefox_session.mjs';

const [engine, route, widthText, heightText, countText] = process.argv.slice(2);
const width=Number(widthText), height=Number(heightText), count=Number(countText);
const output=process.env.OUTPUT_FILE;
if (!['chromium','webkit','firefox'].includes(engine) || !route?.startsWith('/') || !Number.isInteger(width) || !Number.isInteger(height) || !Number.isInteger(count) || count<1 || !output) throw new Error('Usage: OUTPUT_FILE=... node navigation_probe.mjs chromium|webkit|firefox /route width height count');
const base='https://pse-pulse.vercel.app';
const url=new URL(route,base).href;
const rows=[];
await mkdir(dirname(output),{recursive:true});
const launcher={chromium,webkit}[engine];
const browser=launcher?await launcher.launch({headless:true}):null;

for(let attempt=1;attempt<=count;attempt++) {
  let context,page,session;
  const row={timestamp:new Date().toISOString(),engine,route,viewport:`${width}x${height}`,attempt,navigation_start:null,response_received:null,http_status:null,domcontentloaded_time:null,document_ready_state:null,primary_landmark_visible_time:null,usable_page_load_ms:null,window_load_time:null,pageerror_count:0,console_error_count:0,critical_request_failure_count:0,browser_navigation_error:null,status:'FAIL'};
  let start=performance.now();
  try {
    if(browser) {
      context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
      page=await context.newPage();
      page.on('domcontentloaded',()=>{row.domcontentloaded_time??=performance.now()-start});
      page.on('load',()=>{row.window_load_time??=performance.now()-start});
      page.on('pageerror',()=>row.pageerror_count++);
      page.on('console',(message)=>{if(message.type()==='error')row.console_error_count++});
      page.on('response',(response)=>{
        if(response.url()===url){row.response_received??=performance.now()-start;row.http_status??=response.status()}
        if(response.status()>=400&&new URL(response.url()).origin===base&&['document','script','stylesheet','fetch','xhr'].includes(response.request().resourceType()))row.critical_request_failure_count++;
      });
      page.on('requestfailed',(request)=>{if(new URL(request.url()).origin===base && ['document','script','stylesheet','fetch','xhr'].includes(request.resourceType()))row.critical_request_failure_count++});
      start=performance.now();row.navigation_start=new Date().toISOString();
      const response=await page.goto(url,{waitUntil:'commit',timeout:30000});
      row.http_status??=response?.status()??null;
      const remaining=()=>Math.max(1,30000-(performance.now()-start));
      await page.locator('main h1').first().waitFor({state:'visible',timeout:remaining()});
      if(route==='/compare'||route.startsWith('/companies/'))await page.locator('main .recharts-surface').first().waitFor({state:'visible',timeout:remaining()});
      row.primary_landmark_visible_time=performance.now()-start;
      row.usable_page_load_ms=row.primary_landmark_visible_time;
      row.document_ready_state=await page.evaluate(()=>document.readyState);
      const facts=await page.evaluate(({route,width})=>{
        const main=document.querySelector('main'),h=main?.querySelector('h1'),rect=h?.getBoundingClientRect();
        const visible=(el)=>!!el&&getComputedStyle(el).visibility!=='hidden'&&el.getBoundingClientRect().height>0;
        const headings=[...(main?.querySelectorAll('h1,h2')??[])].map((el)=>el.textContent?.trim());
        const nav=document.querySelector('body > nav');
        const navRect=nav?.getBoundingClientRect();
        const mobile=document.querySelector('nav[aria-label="Mobile Navigation"]');
        const links=(el)=>[...(el?.querySelectorAll('a')??[])].filter(visible).map((el)=>el.textContent?.trim());
        const navUsable=width<768?visible(mobile)&&links(mobile).some((x)=>x?.includes('Companies'))&&links(mobile).some((x)=>x?.includes('About')):links(nav).includes('Companies');
        let core=true;
        if(route==='/compare')core=headings.includes('Model Leaderboard')&&!!main?.querySelector('.recharts-surface');
        else if(route.startsWith('/companies/'))core=headings.includes(route.split('/').at(-1))&&headings.includes('Next-Day Prediction')&&!!main?.querySelector('.recharts-surface');
        else if(route==='/companies')core=headings.includes('Company List');
        else if(route==='/watchlist')core=headings.includes('My Watchlist');
        else if(route==='/learn-stocks')core=headings.some((x)=>x?.includes('4-Step Learning Path'));
        else if(route==='/about')core=headings.includes('About PSE Pulse');
        const fixedCover=[...document.querySelectorAll('*')].filter((el)=>{
          if(getComputedStyle(el).position!=='fixed')return false;
          const r=el.getBoundingClientRect();
          return rect&&r.width>innerWidth*.7&&r.height>innerHeight*.25&&r.top<rect.bottom&&r.bottom>rect.top;
        }).length;
        return {primary:visible(main)&&visible(h),core,navUsable,overflow:document.documentElement.scrollWidth>width+2||document.body.scrollWidth>width+2,headingClipped:!rect||rect.left< -2||rect.right>width+2,navOverflow:!!navRect&&(navRect.left< -2||navRect.right>width+2),fixedCover};
      },{route,width});
      row.checks=facts;
      await page.waitForTimeout(250);
      row.status=row.http_status===200&&facts.primary&&facts.core&&facts.navUsable&&!facts.overflow&&!facts.headingClipped&&!facts.navOverflow&&!facts.fixedCover&&row.pageerror_count===0&&row.console_error_count===0&&row.critical_request_failure_count===0&&row.usable_page_load_ms<=30000?'PASS':'FAIL';
      if(process.env.SCREENSHOT_DIR&&attempt===1){await mkdir(process.env.SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:join(process.env.SCREENSHOT_DIR,`${engine}_${route==='/'?'home':route.slice(1).replaceAll('/','_')}_${width}x${height}.png`),fullPage:true});}
    } else {
      session=await startSystemFirefox(dirname(output),`probe_${route.replaceAll('/','_')}_${width}x${height}_${attempt}_geckodriver.log`);
      const driver=session.driver;
      await driver.manage().window().setRect({width,height,x:0,y:0});
      start=performance.now();row.navigation_start=new Date().toISOString();
      try {await driver.get(url)} catch(error){row.browser_navigation_error=String(error.message)}
      const state=await driver.wait(async()=>{
        const current=await driver.executeScript('return {url:location.href,ready:document.readyState,heading:!!document.querySelector("main h1")&&document.querySelector("main h1").getBoundingClientRect().height>0,chart:!!document.querySelector("main .recharts-surface")};').catch(()=>null);
        return current?.url===url&&current.heading&&(!(route==='/compare'||route.startsWith('/companies/'))||current.chart)?current:false;
      },Math.max(1,30000-(performance.now()-start))).catch(()=>null);
      row.document_ready_state=state?.ready??null;
      if(state?.url===url&&state.heading&&(!(route==='/compare'||route.startsWith('/companies/'))||state.chart)){
        row.primary_landmark_visible_time=performance.now()-start;
        row.usable_page_load_ms=row.primary_landmark_visible_time;
        row.status=row.usable_page_load_ms<=30000?'LANDMARK_VISIBLE_HTTP_UNVERIFIED':'FAIL';
      }
    }
  }catch(error){row.browser_navigation_error??=String(error.message)}
  finally {if(context)await context.close();if(session)await session.close();}
  rows.push(row);
  await writeFile(output,JSON.stringify(rows,null,2)+'\n');
  console.log(`[probe] ${engine} ${route} ${width}x${height} ${attempt}/${count}: ${row.status} ${row.usable_page_load_ms?.toFixed(1)??'unusable'} ms ${row.browser_navigation_error??''}`);
}
if(browser)await browser.close();
