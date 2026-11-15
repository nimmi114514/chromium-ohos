// Real-device interop proof: render on Vulkan, consume on GLES/DrDc, and
// distinguish NativeBuffer imports from the CPU staging implementation.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..');
const label=process.argv[2]||'webgpu-zero-copy';
if(!/^[a-z0-9-]+$/.test(label))throw Error('Invalid label');
const report={label,startedAt:new Date().toISOString(),passed:false,cases:[]};
const output=path.join(root,'reports',label+'.json');
const save=()=>fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
// BGRA is an explicit compatibility diagnostic: this GPU cannot import it.
const formats=process.argv.includes('--all-formats')?['bgra8unorm','rgba8unorm']:['rgba8unorm'];
const fixture=`<!doctype html><meta charset="utf-8"><title>WebGPU NativeBuffer verification</title><style>body{background:#eee}canvas{width:640px;height:360px}</style><canvas id="gpu"></canvas><canvas id="reference"></canvas><script>
window.initialize=async(format)=>{window.device?.destroy();const a=await navigator.gpu.requestAdapter();if(!a)throw Error('No hardware adapter');window.device=await a.requestDevice();window.errors=[];device.addEventListener('uncapturederror',e=>errors.push(e.error.message));window.canvas=document.querySelector('#gpu');window.context=canvas.getContext('webgpu');context.configure({device,format,alphaMode:'opaque'});return true;};
window.frame=()=>{const e=device.createCommandEncoder(),p=e.beginRenderPass({colorAttachments:[{view:context.getCurrentTexture().createView(),clearValue:{r:.2,g:.6,b:.8,a:1},loadOp:'clear',storeOp:'store'}]});p.end();device.queue.submit([e.finish()]);};
window.run=async()=>{window.result={done:false,passed:false,formats:[]};try{for(const format of ${JSON.stringify(formats)}){await initialize(format);for(const [width,height]of [[256,256],[1280,720],[1920,1080]]){canvas.width=width;canvas.height=height;for(let i=0;i<90;i++){await new Promise(requestAnimationFrame);frame();}await device.queue.onSubmittedWorkDone();}frame();performance.mark('WebGPU.presentation-complete');const c=document.querySelector('#reference');c.width=16;c.height=16;const x=c.getContext('2d');x.drawImage(canvas,0,0,16,16);const pixel=[...x.getImageData(8,8,1,1).data];if(!pixel.every((v,i)=>Math.abs(v-[51,153,204,255][i])<4))throw Error('Pixel mismatch '+format+' '+pixel);result.formats.push({format,pixel});if(errors.length)throw Error(errors.join(';'));}result.passed=true;}catch(e){result.error=String(e);}finally{result.done=true;}return result;};
</script>`;
const server=http.createServer((_,res)=>{res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fixture);});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
let c,targetId,sessionId,off,awakeTimer;
const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
// Page readback alone cannot catch damage to the browser's shared raster cache.
// Preserve full-system UI frames for review around the exact interop reproducer.
function systemShot(suffix){const remote='/data/local/tmp/'+label+suffix+'.jpeg';execFileSync(hdc,['-t','6YT0226706000164','shell','snapshot_display','-f',remote],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','file','recv',remote,path.join(root,'reports',label+suffix+'.jpeg')],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','shell','rm',remote],{timeout:15000});}

try{
 c=await connect();report.browserPid=c.ownPid;
 const {gpu}=await c.send('SystemInfo.getInfo');report.featureStatus=gpu.featureStatus;
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/zero-copy'}));
 ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);await c.send('Target.activateTarget',{targetId});
 const evaluate=async(expr)=>{const r=await c.send('Runtime.evaluate',{expression:expr,returnByValue:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<40;i++){if(await evaluate("typeof run==='function'"))break;await delay(200);}
 systemShot('-ui-before');
 report.rendererCrashed=false;const events=[];let traceResolve;
 const traceDone=new Promise(r=>traceResolve=r);
 off=c.onEvent(e=>{if(e.method==='Tracing.dataCollected')events.push(...e.params.value);if(e.method==='Tracing.tracingComplete')traceResolve(e.params);if(e.method==='Target.targetCrashed'&&e.params.targetId===targetId)report.rendererCrashed=true;});
 awakeTimer=setInterval(()=>{try{execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','click','2850','600'],{timeout:10000});}catch{}},15000);
 await c.send('Tracing.start',{categories:'gpu,viz,blink.user_timing',transferMode:'ReportEvents'});
 await evaluate('run();true');for(let i=0;i<90;i++){await delay(1000);report.render=await evaluate('result');save();if(report.render?.done)break;}
 systemShot('-ui-after');
 const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);fs.writeFileSync(output.replace(/\.json$/,'.png'),Buffer.from(shot.data,'base64'));
 await c.send('Tracing.end');let timeout;try{await Promise.race([traceDone,new Promise((_,reject)=>timeout=setTimeout(()=>reject(Error('Trace completion timed out')),60000))]);}finally{clearTimeout(timeout);}
 fs.writeFileSync(output.replace(/\.json$/,'.trace.json'),JSON.stringify({traceEvents:events}));
 report.nativeBufferImports=events.filter(e=>e.name==='OHOSWebGPU.NativeBuffer.BeginAccess').length;
 report.nativeBufferReleases=events.filter(e=>e.name==='OHOSWebGPU.NativeBuffer.EndAccess').length;
 const staging=events.filter(e=>e.name?.startsWith('WebGPU.CPUStaging'));
 report.cpuStagingAccesses=staging.length;
 const boundary=events.find(e=>e.name==='WebGPU.presentation-complete');
 report.presentationBoundaryFound=!!boundary;
 report.cpuStagingPresentationAccesses=staging.filter(e=>!boundary||e.ts<boundary.ts).length;
 report.cpuStagingReadbackAccesses=staging.filter(e=>boundary&&e.ts>=boundary.ts).length;
 const threads=events.filter(e=>e.ph==='M'&&e.name==='thread_name'&&String(e.args?.name).includes('CompositorGpu'));
 const tids=new Set(threads.map(e=>e.pid+':'+e.tid));report.drdcThreads=threads;report.drdcDrawEvents=events.filter(e=>tids.has(e.pid+':'+e.tid)&&/Swap|Paint|Draw/.test(e.name)).length;
 report.cases=[{name:'formats-pixel-correct',passed:!!report.render?.passed},{name:'nativebuffer-used',passed:report.nativeBufferImports>100&&report.nativeBufferReleases>100},{name:'no-cpu-staging-during-presentation',passed:report.presentationBoundaryFound&&report.cpuStagingPresentationAccesses===0},{name:'drdc-executes-composition',passed:report.drdcDrawEvents>0},{name:'renderer-alive',passed:!report.rendererCrashed}];
 report.passed=report.cases.every(x=>x.passed);
}catch(e){report.error=String(e);console.error(report.error);}
finally{clearInterval(awakeTimer);off?.();if(c){if(sessionId)try{await c.send('Runtime.evaluate',{expression:'context?.unconfigure();device?.destroy();true'},sessionId);}catch{}if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));report.finishedAt=new Date().toISOString();save();console.log(JSON.stringify(report));}
