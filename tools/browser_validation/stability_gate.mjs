import { spawn } from 'node:child_process';
import { readFile, mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const evidence=process.env.HISTORY_EVIDENCE_DIR ?? process.env.EVIDENCE_DIR;
const preflight=process.env.PREFLIGHT_ROOT;
if(!evidence||!preflight)throw new Error('HISTORY_EVIDENCE_DIR and PREFLIGHT_ROOT are required');
await mkdir(preflight,{recursive:true});
const output=await mkdtemp(join(preflight,'stability_gate_'));
const parse=(line)=>[...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)].map((x)=>x[1].replaceAll('""','"'));
const inventory=(await readFile(join(evidence,'retest','original_timeout_inventory.csv'),'utf8')).trim().split('\n');
const names=inventory.shift().split(',');
const cases=[];
for(const line of inventory){const values=parse(line);const row=Object.fromEntries(names.map((name,index)=>[name,values[index]]));cases.push({browser:row.browser,route:row.route,width:Number(row.viewport_width),height:Number(row.viewport_height),source:row.timeout_id});}
const final=JSON.parse(await readFile(join(evidence,'final_run','raw_results.json'),'utf8'));
const historicalEnvironment=JSON.parse(await readFile(join(evidence,'test_environment.json'),'utf8'));
for(const [category,rows] of [['responsive',final.responsive],['cross',final.cross],['performance',final.perf]]){
  for(const row of rows.filter((item)=>item.status==='FAIL'&&/timeout|timed out/i.test(item.notes))){
    const [w,h]=row.viewport?.split('x').map(Number)??[Number(row.viewport_width),Number(row.viewport_height)];
    cases.push({browser:row.browser_engine??row.browser,route:row.route,width:w,height:h,source:`pre-final ${category}`});
  }
}
const unique=[...new Map(cases.map((item)=>[[item.browser,item.route,item.width,item.height].join('|'),item])).values()].sort((a,b)=>a.browser.localeCompare(b.browser)||a.route.localeCompare(b.route)||a.width-b.width);
const run=(args,env)=>new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,args,{env:{...process.env,...env},stdio:'inherit'});
  child.on('error',reject);child.on('exit',(code)=>resolve(code));
});
const results=[];
for(const item of unique){
  const slug=`${item.browser}_${item.route==='/'?'home':item.route.slice(1).replaceAll('/','_')}_${item.width}x${item.height}`;
  console.log(`[stability gate] ${slug}: 10 fresh attempts`);
  let file,rows;
  if(item.browser==='firefox'){
    const folder=join(output,slug);
    const code=await run(['tools/browser_validation/firefox_matrix.mjs','preflight'],{EVIDENCE_DIR:evidence,OUTPUT_DIR:folder,RUN_ID:slug,FIREFOX_ROUTE:item.route,FIREFOX_VIEWPORT:item.width<768?'mobile':'desktop',REPEAT:'10'});
    file=join(folder,'firefox_cross_browser_results.raw.json');
    rows=(await readFile(file,'utf8').then(JSON.parse)).map((item)=>item.row);
    if(code!==0)throw new Error(`Firefox process failed for ${slug}`);
  }else{
    file=join(output,`${slug}.json`);
    const code=await run(['tools/browser_validation/navigation_probe.mjs',item.browser,item.route,String(item.width),String(item.height),'10'],{OUTPUT_FILE:file});
    rows=await readFile(file,'utf8').then(JSON.parse);
    if(code!==0)throw new Error(`Probe process failed for ${slug}`);
  }
  const pass=rows.filter((row)=>row.status==='PASS').length;
  results.push({...item,attempts:rows.length,passed:pass,status:rows.length===10&&pass===10?'PASS':'FAIL',evidence:file});
  await writeFile(join(output,'stability_gate_summary.json'),JSON.stringify({created_at:new Date().toISOString(),source_repository_sha:historicalEnvironment.repository_sha,required_attempts_per_configuration:10,results},null,2)+'\n');
}
const allPass=results.length===unique.length&&results.every((row)=>row.status==='PASS');
console.log(`[stability gate] ${results.filter((row)=>row.status==='PASS').length}/${results.length} configurations passed; output=${output}`);
if(!allPass)process.exitCode=1;
