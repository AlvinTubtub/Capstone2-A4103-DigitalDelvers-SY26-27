import test from 'node:test';
import assert from 'node:assert/strict';
import { isTransportNoDocument, runBoundedTransportCase, TRANSPORT_DELAY_MS } from '../transport_retry.mjs';

const noDocument = () => ({ main_document_response_received:false,app_dom_available:false,assertions_executed:false,http_status:null,browser_navigation_error:'timeout',transport_status:'TRANSPORT_NO_DOCUMENT',status:'FAIL' });
const delivered = (status='PASS') => ({ main_document_response_received:true,app_dom_available:true,assertions_executed:true,http_status:200,browser_navigation_error:'',transport_status:'DOCUMENT_DELIVERED',status });

test('one no-document failure permits exactly one delayed clean attempt',async()=>{
  const calls=[],delays=[];
  const result=await runBoundedTransportCase(async(number)=>{calls.push(number);return number===1?noDocument():delivered()},async(ms)=>delays.push(ms));
  assert.deepEqual(calls,[1,2]);
  assert.deepEqual(delays,[TRANSPORT_DELAY_MS]);
  assert.equal(result.transport_retry_used,true);
  assert.equal(result.final.status,'PASS');
  assert.equal(result.attempts[0].status,'FAIL');
});

test('two no-document failures stop after two attempts',async()=>{
  let calls=0;
  const result=await runBoundedTransportCase(async()=>{calls++;return noDocument()},async()=>{});
  assert.equal(calls,2);
  assert.equal(result.final.status,'FAIL');
});

test('no retry after any document, runtime, assertion, or slow-result failure',async()=>{
  for(const first of [
    delivered('FAIL'),
    {...delivered('FAIL'),http_status:500,transport_status:'HTTP_APPLICATION_FAILURE'},
    {...delivered('FAIL'),browser_navigation_error:'late API timeout'},
    {...noDocument(),app_dom_available:true},
    {...noDocument(),app_dom_available:null},
    {...noDocument(),assertions_executed:true},
  ]){
    let calls=0;
    const result=await runBoundedTransportCase(async()=>{calls++;return first},async()=>{});
    assert.equal(calls,1);
    assert.equal(result.transport_retry_used,false);
  }
  assert.equal(isTransportNoDocument(noDocument()),true);
});
