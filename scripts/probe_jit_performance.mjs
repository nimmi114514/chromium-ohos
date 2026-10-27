// Own temporary context only: no account, saved-password, or existing-tab access.
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
const requireJit=process.argv.includes('--require-jit');
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Expected a diagnostic label');
const root=path.resolve(import.meta.dirname,'..');
const report={label,passed:false,jitVerified:false,requireJit,deviceBenchmark:true,scope:'Owned about:blank temporary context; generated test data only'};
let c,contextId,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId:contextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',browserContextId:contextId,background:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Runtime.enable',{},sessionId);
 const evaluate=async expression=>{
  const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
  if(r.exceptionDetails)throw Error(r.exceptionDetails.text+' '+(r.exceptionDetails.exception?.description||''));
  return r.result.value;
 };
 report.measurements=await evaluate(`(()=>{
 document.title='Chromium JIT diagnosis';
 function integerMix(n,seed){let x=seed|0;for(let i=0;i<n;i++)x=(Math.imul(x^i,1664525)+1013904223)|0;return x;}
 function floatingPoint(n,seed){let x=seed;for(let i=0;i<n;i++)x=Math.sqrt(x+(i%7)+0.25);return x;}
 function arrayOps(n,seed){const a=new Int32Array(1024);for(let i=0;i<n;i++)a[i&1023]=(a[i&1023]+((i*3)^seed))|0;let total=0;for(let i=0;i<a.length;i++)total=(total+a[i])|0;return total;}
 let optimizationStatus=null;try{optimizationStatus=Function('f','return %GetOptimizationStatus(f)');}catch{}
 const cases=[['integer',integerMix,2000000,17],['floating-point',floatingPoint,700000,3.5],['array',arrayOps,1000000,29]];
 const results=[];
 for(const [name,fn,count,seed] of cases){
  fn(1000,seed);const samples=[],values=[];
  for(let round=0;round<5;round++){const before=performance.now();values.push(fn(count,seed));samples.push(performance.now()-before);}
  const sorted=[...samples].sort((a,b)=>a-b);
  let status=null;try{status=optimizationStatus?.(fn)??null;}catch{}
  results.push({name,count,medianMs:sorted[2],samplesMs:samples,checksum:values[0],consistent:values.every(v=>Object.is(v,values[0])),optimizationStatus:status,optimized:status!==null&&!!(status&8),maglev:status!==null&&!!(status&16),turboFan:status!==null&&!!(status&32),liteMode:status!==null&&!!(status&4096)});
 }
 const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;
 const ctx=canvas.getContext('2d');ctx.fillStyle='rgb(20,80,160)';ctx.fillRect(0,0,32,32);
 const pixel=Array.from(ctx.getImageData(16,16,1,1).data);
 const container=document.createElement('div');for(let i=0;i<500;i++){const e=document.createElement('span');e.textContent=String(i);container.appendChild(e);}document.body.appendChild(container);
 const domCount=container.childElementCount;container.remove();
 let wasmResult=null;
 if(typeof WebAssembly==='object'){
  const code=new Uint8Array([0,97,115,109,1,0,0,0,1,7,1,96,2,127,127,1,127,3,2,1,0,7,7,1,3,97,100,100,0,0,10,9,1,7,0,32,0,32,1,106,11]);
  try{wasmResult=new WebAssembly.Instance(new WebAssembly.Module(code)).exports.add(20,22);}catch(e){wasmResult=String(e);}
 }
 return {userAgent:navigator.userAgent,wasmExposed:typeof WebAssembly==='object',wasmResult,results,canvasPixel:pixel,domCount};
})()`);
 const m=report.measurements;
 report.baselineChecksPassed=m.results.every(x=>x.consistent)&&m.domCount===500&&JSON.stringify(m.canvasPixel)==='[20,80,160,255]';
 report.jitVerified=report.baselineChecksPassed&&m.results.every(x=>x.optimizationStatus!==null&&!x.liteMode&&x.optimized&&(x.maglev||x.turboFan))&&m.wasmResult===42;
 report.passed=report.baselineChecksPassed&&(!requireJit||report.jitVerified);
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});report.ownedTargetClosed=true;}catch{}if(contextId)try{await c.send('Target.disposeBrowserContext',{browserContextId:contextId});report.temporaryContextClosed=true;}catch{}c.close();}
 fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report));
 process.exitCode=report.passed?0:1;
}
