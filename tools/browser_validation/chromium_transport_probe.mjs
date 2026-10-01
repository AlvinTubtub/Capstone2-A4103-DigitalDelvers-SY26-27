import { chromium } from '@playwright/test';
import { performance } from 'node:perf_hooks';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.DIAGNOSIS_DIR;
if (!root) throw new Error('DIAGNOSIS_DIR is required');
await mkdir(join(root,'screenshots'),{recursive:true});
const cases = [
  ['/about',1440,900],
  ['/companies',1440,900],
  ['/learn-stocks',390,844],
  ['/learn-stocks',1440,900],
];
const fields = ['attempt_id','timestamp','browser','route','viewport','navigation_start','request_started','main_document_request_url','main_document_response_received','main_document_http_status','response_headers_received','navigation_commit_seen','domcontentloaded_seen','document_ready_state','primary_landmark_seen','usable_state_seen','browser_navigation_exception','exception_stage','elapsed_ms','failure_stage','request_failure','final_url','pageerror_count','console_error_count','screenshot'];
const escape=(value)=>`"${String(value??'').replaceAll('"','""').replaceAll('\n',' ')}"`;
const rows=[];
const raw=[];
const browser=await chromium.launch({headless:true});
try {
  for(const [route,width,height] of cases) {
    const target=new URL(route,'https://pse-pulse.vercel.app').href;
    for(let attempt=1;attempt<=20;attempt++) {
      const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
      const page=await context.newPage();
      const attemptId=`chromium_${route.slice(1).replaceAll('/','_')}_${width}x${height}_${attempt}`;
      const row={attempt_id:attemptId,timestamp:new Date().toISOString(),browser:'chromium',route,viewport:`${width}x${height}`,navigation_start:'',request_started:'',main_document_request_url:'',main_document_response_received:false,main_document_http_status:'',response_headers_received:false,navigation_commit_seen:false,domcontentloaded_seen:false,document_ready_state:'',primary_landmark_seen:false,usable_state_seen:false,browser_navigation_exception:'',exception_stage:'',elapsed_ms:'',failure_stage:'',request_failure:'',final_url:'',pageerror_count:0,console_error_count:0,screenshot:''};
      const events=[];
      let started=performance.now(),mainRequest=null;
      page.on('request',(request)=>{if(request.isNavigationRequest()&&request.url()===target){mainRequest=request;row.request_started=new Date().toISOString();row.main_document_request_url=request.url();events.push('main_document_request_started')}});
      page.on('response',(response)=>{if(response.url()===target&&response.request().isNavigationRequest()){row.main_document_response_received=true;row.main_document_http_status=response.status();row.response_headers_received=true;events.push(`main_document_response_${response.status()}`)}});
      page.on('requestfailed',(request)=>{if(request===mainRequest){row.request_failure=request.failure()?.errorText??'unknown';events.push(`main_document_request_failed:${row.request_failure}`)}});
      page.on('domcontentloaded',()=>{row.domcontentloaded_seen=true;events.push('domcontentloaded')});
      page.on('pageerror',(error)=>{row.pageerror_count++;events.push(`pageerror:${error.message}`)});
      page.on('console',(message)=>{if(message.type()==='error'){row.console_error_count++;events.push(`console:${message.text()}`)}});
      try {
        started=performance.now();row.navigation_start=new Date().toISOString();
        const response=await page.goto(target,{waitUntil:'commit',timeout:30000});
        row.navigation_commit_seen=true;
        row.main_document_http_status=response?.status()??row.main_document_http_status;
        row.main_document_response_received ||= !!response;
        row.response_headers_received ||= !!response;
      }catch(error){row.browser_navigation_exception=error.message;row.exception_stage=row.main_document_response_received?'after_main_response':'before_main_response'}
      row.elapsed_ms=(performance.now()-started).toFixed(2);
      try {
        const state=await page.evaluate(()=>({ready:document.readyState,heading:!!document.querySelector('main h1')&&document.querySelector('main h1').getBoundingClientRect().height>0,url:location.href}));
        row.document_ready_state=state.ready;row.primary_landmark_seen=state.heading;row.usable_state_seen=state.heading;row.final_url=state.url;
      }catch(error){events.push(`state_probe_failed:${error.message}`)}
      if(!row.main_document_response_received&&!row.usable_state_seen)row.failure_stage='TRANSPORT_NO_DOCUMENT';
      else if(Number(row.main_document_http_status)>=400)row.failure_stage='HTTP_APPLICATION_FAILURE';
      else if(row.browser_navigation_exception&&row.usable_state_seen)row.failure_stage='NAVIGATION_API_ONLY';
      else if(row.browser_navigation_exception)row.failure_stage='POST_RESPONSE_NAVIGATION_ERROR';
      else row.failure_stage='DOCUMENT_DELIVERED';
      if(row.failure_stage!=='DOCUMENT_DELIVERED'){
        const path=join(root,'screenshots',`${attemptId}.png`);
        try{await page.screenshot({path,fullPage:true,timeout:3000});row.screenshot=`screenshots/${attemptId}.png`}catch(error){events.push(`screenshot_failed:${error.message}`)}
      }
      raw.push({row,events,request_timing:mainRequest?.timing()??null});rows.push(row);
      await writeFile(join(root,'chromium_transport_probe.csv'),[fields.join(','),...rows.map((item)=>fields.map((field)=>escape(item[field])).join(','))].join('\n')+'\n');
      await writeFile(join(root,'chromium_transport_probe.raw.json'),JSON.stringify(raw,null,2)+'\n');
      console.log(`[Chromium transport] ${route} ${width}x${height} ${attempt}/20 ${row.failure_stage} ${row.elapsed_ms}ms`);
      await context.close();
    }
  }
}finally{await browser.close()}
console.log(`[Chromium transport complete] ${rows.filter((row)=>row.failure_stage==='DOCUMENT_DELIVERED').length}/${rows.length} documents delivered`);
