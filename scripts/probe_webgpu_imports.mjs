// Owned loopback fixtures. Trace imports separately from explicit pixel readback
// and preserve whole-browser UI screenshots to catch shared GL state damage.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..'),label=process.argv[2]||'webgpu-imports';
if(!/^[a-z0-9-]+$/.test(label))throw Error('Invalid report label');
const output=path.join(root,'reports',label+'.json');
const report={label,startedAt:new Date().toISOString(),passed:false,cases:[]};
const save=()=>fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
function shot(suffix){const remote='/data/local/tmp/'+label+suffix+'.jpeg';execFileSync(hdc,['-t','6YT0226706000164','shell','snapshot_display','-f',remote],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','file','recv',remote,path.join(root,'reports',label+suffix+'.jpeg')],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','shell','rm',remote],{timeout:15000});}
const server=http.createServer((req,res)=>{
 const name=String(req.url).slice(1);
 if(['drdc-avc-1080p60.mp4','drdc-hevc-1080p60.mp4'].includes(name)){
  const bytes=fs.readFileSync(path.join(root,'artifacts/drdc-fixtures',name));
  const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
  const a=range?Number(range[1]):0,b=range&&range[2]?Math.min(Number(range[2]),bytes.length-1):bytes.length-1;
  res.writeHead(range?206:200,{'Content-Type':'video/mp4','Accept-Ranges':'bytes','Content-Length':b-a+1,...(range?{'Content-Range':`bytes ${a}-${b}/${bytes.length}`}:{})});res.end(bytes.subarray(a,b+1));return;
 }
 res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync(path.join(root,'tests/webgpu/import-interop.html')));
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
let c,targetId,sessionId,off,awake;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/import-interop'}));
 ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);await c.send('Media.enable',{},sessionId);await c.send('Target.activateTarget',{targetId});
 const evaluate=async(expression,awaitPromise=false)=>{const r=await c.send('Runtime.evaluate',{expression,awaitPromise,returnByValue:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<40;i++){if(await evaluate("typeof initialize==='function'"))break;await delay(200);}
 report.adapter=await evaluate('initialize()',true);report.rendererCrashed=false;report.media=[];
 off=c.onEvent(e=>{if(e.method==='Target.targetCrashed'&&e.params.targetId===targetId)report.rendererCrashed=true;if(e.sessionId===sessionId&&e.method.startsWith('Media.'))report.media.push({method:e.method,params:e.params});});
 shot('-ui-before');
 awake=setInterval(()=>{try{execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','click','2850','600'],{timeout:10000});}catch{}},15000);
 const benchmark=process.argv.includes('--benchmark')||process.argv.includes('--benchmark-video');
 const names=process.argv.includes('--benchmark-video')?['bench-video-avc-1','bench-video-hevc-1','bench-video-avc-2','bench-video-hevc-2']:benchmark?['bench-canvas2d-1','bench-webgl2-1','bench-canvas2d-2','bench-webgl2-2','bench-canvas2d-3','bench-webgl2-3']:(process.argv.includes('--present-only')?['present-rgba8unorm','present-bgra8unorm']:['canvas2d','canvas2d-alpha','webgl2','imagebitmap','video-avc','video-hevc','present-rgba8unorm','present-bgra8unorm','present-rgba16float']);
 for(const name of names){
  const result={name,passed:false};report.cases.push(result);let tracing=false,stopTrace;
  try{
   await c.send('Target.activateTarget',{targetId});if(!benchmark)result.source=await evaluate(`prepare(${JSON.stringify(name)})`,true);
   const events=[];let complete;const done=new Promise(r=>complete=r);
   stopTrace=c.onEvent(e=>{if(e.method==='Tracing.dataCollected')events.push(...e.params.value);if(e.method==='Tracing.tracingComplete')complete();});
   await c.send('Tracing.start',{categories:'gpu,viz,blink,blink.user_timing',transferMode:'ReportEvents'});tracing=true;
   await evaluate(benchmark?`benchmarkImports(${JSON.stringify(name.replace(/^bench-/,'').replace(/-\d+$/,''))});true`:`runCase(${JSON.stringify(name)});true`);
   for(let i=0;i<80;i++){await delay(500);result.pixels=await evaluate(benchmark?'benchmarkResult':'caseResult');save();if(result.pixels?.done)break;}
   shot('-'+name+'-ui');
   await c.send('Tracing.end');tracing=false;let timer;try{await Promise.race([done,new Promise((_,j)=>timer=setTimeout(()=>j(Error('Trace completion timeout')),30000))]);}finally{clearTimeout(timer);}
   fs.writeFileSync(output.replace(/\.json$/,'-'+name+'.trace.json'),JSON.stringify({traceEvents:events}));
   const boundary=events.filter(e=>e.name==='interop-work-complete').at(-1);result.workBoundaryFound=!!boundary;
   result.nativeBufferImports=events.filter(e=>e.name==='OHOSWebGPU.NativeBuffer.BeginAccess'&&(!boundary||e.ts<boundary.ts)).length;
   result.nativeBufferResourceLabels=[...new Set(events.filter(e=>e.name==='OHOSWebGPU.NativeBuffer.BeginAccess').map(e=>e.args?.resource))];
   result.cpuStagingDuringWork=events.filter(e=>e.name?.startsWith('WebGPU.CPUStaging')&&(!boundary||e.ts<boundary.ts)).length;
   result.cpuStagingAfterWork=events.filter(e=>e.name?.startsWith('WebGPU.CPUStaging')&&boundary&&e.ts>=boundary.ts).length;
   result.functional=!!result.pixels?.passed;
   result.noCpuStaging=result.workBoundaryFound&&result.cpuStagingDuringWork===0&&result.nativeBufferImports>0;
   result.passed=result.functional&&(benchmark||result.noCpuStaging)&&!report.rendererCrashed;
   // BGRA GPU conversion was tried but reverted after A/B measurements showed
   // no stable performance gain. RGBA16F is also a compatibility diagnostic.
   // Preserve both real results rather than claiming zero-copy support.
   result.required=!['present-rgba16float','present-bgra8unorm'].includes(name);
  }catch(e){result.error=String(e);result.required=!['present-rgba16float','present-bgra8unorm'].includes(name);}
  finally{if(tracing)try{await c.send('Tracing.end');}catch{}stopTrace?.();try{await evaluate('finishCase();true');}catch{}save();console.log(name,result.passed,result.cpuStagingDuringWork??result.error);}
 }
 report.passed=report.cases.filter(x=>x.required).every(x=>x.passed)&&!report.rendererCrashed;shot('-ui-after');
}catch(e){report.error=String(e);}
finally{clearInterval(awake);off?.();if(c){if(sessionId)try{await c.send('Runtime.evaluate',{expression:'finish();true'},sessionId);}catch{}if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));report.finishedAt=new Date().toISOString();save();console.log('Result',report.passed,'Report',output);}
