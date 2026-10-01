import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.DIAGNOSIS_DIR;
if (!root) throw new Error('DIAGNOSIS_DIR is required');
await mkdir(root, { recursive: true });
const routes = ['/about', '/companies', '/learn-stocks'];
const fields = ['route','attempt','timestamp','http_status','dns_ms','connect_ms','tls_ms','ttfb_ms','total_ms','curl_exit_code','effective_url','remote_ip','error'];
const rows = [];
const escape = (value) => `"${String(value ?? '').replaceAll('"','""').replaceAll('\n',' ')}"`;
const csv = () => [fields.join(','), ...rows.map((row) => fields.map((field) => escape(row[field])).join(','))].join('\n') + '\n';
function run(command,args) {
  return new Promise((resolve,reject)=>{
    const child=spawn(command,args,{stdio:['ignore','pipe','pipe']});
    let stdout='',stderr='';
    child.stdout.on('data',(chunk)=>stdout+=chunk);
    child.stderr.on('data',(chunk)=>stderr+=chunk);
    child.on('error',reject);
    child.on('close',(code)=>resolve({code,stdout,stderr}));
  });
}
for (const route of routes) {
  for (let attempt=1;attempt<=20;attempt++) {
    const timestamp=new Date().toISOString();
    const result=await run('curl',['--silent','--show-error','--location','--output','/dev/null','--max-time','30','--write-out','%{http_code},%{time_namelookup},%{time_connect},%{time_appconnect},%{time_starttransfer},%{time_total},%{url_effective},%{remote_ip}',new URL(route,'https://pse-pulse.vercel.app').href]);
    const [http,dns,connect,tls,ttfb,total,effective,remote]=result.stdout.trim().split(',');
    const ms=(value)=>value===''||value===undefined?'':(1000*Number(value)).toFixed(2);
    rows.push({route,attempt,timestamp,http_status:http??'',dns_ms:ms(dns),connect_ms:ms(connect),tls_ms:ms(tls),ttfb_ms:ms(ttfb),total_ms:ms(total),curl_exit_code:result.code,effective_url:effective??'',remote_ip:remote??'',error:result.stderr.trim()});
    await writeFile(join(root,'curl_route_stability.csv'),csv());
    console.log(`[HTTP] ${route} ${attempt}/20 status=${http||'none'} exit=${result.code} total=${ms(total)}ms`);
  }
}
for (const command of ['dig','nslookup']) {
  try {
    const result=await run(command,['pse-pulse.vercel.app']);
    await writeFile(join(root,`${command}_resolution.txt`),`$ ${command} pse-pulse.vercel.app\nexit=${result.code}\n${result.stdout}\n${result.stderr}`);
  } catch (error) {
    await writeFile(join(root,`${command}_resolution.txt`),`$ ${command} pse-pulse.vercel.app\nUNAVAILABLE: ${error.message}\n`);
  }
}
console.log(`[HTTP complete] ${rows.filter((row)=>row.curl_exit_code===0&&row.http_status==='200').length}/${rows.length} HTTP 200`);
