// Real-device DrDc regression: owned loopback pages, existing application data.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const label=process.argv[2] || 'drdc';
if(!/^[a-z0-9-]+$/.test(label))throw Error('Invalid report label');
const root=path.resolve(import.meta.dirname,'..');
const report={label,startedAt:new Date().toISOString(),cases:[],passed:false};
const output=path.join(root,'reports',label+'.json');
const assets=path.join(root,'tests/hdr/assets');
const fixture=`<!doctype html><meta charset="utf-8"><title>Chromium GPU verification</title>
<style>body{background:#eee;color:#222;font:18px sans-serif}canvas,video{width:480px;height:270px;margin:8px}video{background:#123}</style>
<h2>Chromium GPU verification</h2><video id="v" muted loop playsinline></video><canvas id="c" width="640" height="360"></canvas><canvas id="g" width="640" height="360"></canvas>
<script>
window.failures=[];addEventListener('error',e=>failures.push(e.message));
const v=document.querySelector('video'),c=document.querySelector('#c'),ctx=c.getContext('2d'),gl=document.querySelector('#g').getContext('webgl2');let count=0;
function frame(t){count++;ctx.fillStyle='#267f32';ctx.fillRect(0,0,c.width,c.height);for(let i=0;i<50;i++){ctx.fillStyle=i%2?'#fc6':'#46f';ctx.fillRect((i*31+t/20)%640,i*7%360,20,20);}if(gl){gl.clearColor(.2,.45+.2*Math.sin(t/500),.8,1);gl.clear(gl.COLOR_BUFFER_BIT);}requestAnimationFrame(frame);}requestAnimationFrame(frame);
window.playSample=async file=>{v.pause();v.src='/'+file;v.load();await v.play();return true;};
window.sample=()=>({time:v.currentTime,paused:v.paused,ready:v.readyState,error:v.error?.code??null,frames:v.getVideoPlaybackQuality().totalVideoFrames,dropped:v.getVideoPlaybackQuality().droppedVideoFrames,animationFrames:count,webgl2:!!gl,failures:[...failures]});
window.readVideo=()=>{const a=document.createElement('canvas');a.width=64;a.height=36;const x=a.getContext('2d');x.drawImage(v,0,0,64,36);const p=x.getImageData(0,0,64,36).data;let min=255,max=0,total=0;for(let i=0;i<p.length;i+=4){for(let j=0;j<3;j++){min=Math.min(min,p[i+j]);max=Math.max(max,p[i+j]);total+=p[i+j];}}return {min,max,mean:total/(64*36*3)};};
</script>`;
const server=http.createServer((req,res)=>{
 if(req.url==='/webgpu'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync(path.join(root,'tests/webgpu/functional.html')));return;}
 const name=String(req.url).slice(1);
 if(['avc-sdr.mp4','hevc-main10-pq.mp4','video.mp4','drdc-avc-1080p60.mp4','drdc-hevc-1080p60.mp4'].includes(name)){
  const bytes=fs.readFileSync(path.join(name.startsWith('drdc-')?path.join(root,'artifacts/drdc-fixtures'):assets,name==='video.mp4'?'avc-sdr.mp4':name));
  const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
  const a=range?Number(range[1]):0,b=range&&range[2]?Math.min(Number(range[2]),bytes.length-1):bytes.length-1;
  res.writeHead(range?206:200,{'Content-Type':'video/mp4','Accept-Ranges':'bytes','Content-Length':b-a+1,...(range?{'Content-Range':`bytes ${a}-${b}/${bytes.length}`}:{})});res.end(bytes.subarray(a,b+1));return;
 }
 res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fixture);
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
let c,targetId,sessionId,off,awakeTimer;
let keepScreenActive=true;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const checkpoint=()=>fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
const record=(name,passed,detail)=>{report.cases.push({name,passed,...detail});checkpoint();console.log(name,passed);};
try{
 c=await connect();report.browserPid=c.ownPid;
 const {gpu}=await c.send('SystemInfo.getInfo');report.featureStatus=gpu.featureStatus;
 record('drdc-reported-enabled',String(gpu.featureStatus.direct_rendering_display_compositor).startsWith('enabled'),{});
 const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
 report.threadList=execFileSync(hdc,['-t','6YT0226706000164','shell','ps','-T','-p',String(c.ownPid)],{encoding:'utf8',timeout:15000});checkpoint();
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/drdc'}));
 ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
 report.rendererCrashed=false;off=c.onEvent(e=>{if((e.method==='Target.targetCrashed'&&e.params.targetId===targetId)||(e.method==='Inspector.targetCrashed'&&e.sessionId===sessionId)){report.rendererCrashed=true;checkpoint();}});
 await c.send('Inspector.enable',{},sessionId);await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Media.enable',{},sessionId);await c.send('Target.activateTarget',{targetId});
 awakeTimer=setInterval(()=>{if(keepScreenActive)try{execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','click','2850','600'],{timeout:10000});}catch{}},15000);
 report.lifecycle=[];c.onEvent(e=>{if(e.sessionId===sessionId&&(['Runtime.executionContextsCleared','Runtime.executionContextDestroyed','Page.frameNavigated','Log.entryAdded'].includes(e.method))){report.lifecycle.push({time:new Date().toISOString(),method:e.method,params:e.params});}});await c.send('Log.enable',{},sessionId);
 report.media=[];const stopMedia=c.onEvent(e=>{if(e.sessionId===sessionId&&e.method.startsWith('Media.')){report.media.push({method:e.method,params:e.params});}});
 const evaluate=async(expression,awaitPromise=false)=>{const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<40;i++){if(await evaluate("typeof window.sample==='function'"))break;await delay(200);}
 if(!process.argv.includes('--webgpu-only')){
 const traceEvents=[];const traceDone=new Promise(resolve=>{const stop=c.onEvent(e=>{if(e.method==='Tracing.dataCollected')traceEvents.push(...e.params.value);if(e.method==='Tracing.tracingComplete'){stop();resolve(e.params);}});});
 if(!process.argv.includes('--no-trace')) await c.send('Tracing.start',{categories:'viz',transferMode:'ReportEvents'});
 for(const [codec,file] of (process.argv.includes('--high-resolution')? [['avc-1080p60','drdc-avc-1080p60.mp4'],['hevc-main10-1080p60','drdc-hevc-1080p60.mp4']] : [['avc','avc-sdr.mp4'],['hevc-main10','hevc-main10-pq.mp4']])){
  await evaluate(`playSample(${JSON.stringify(file)})`,true);await delay(1200);const a=await evaluate('sample()');await delay(6000);const b=await evaluate('sample()');
  const pixels=await evaluate('readVideo()');
  record(codec+'-continuous',b.frames-a.frames>50&&!b.error&&b.animationFrames>a.animationFrames,{before:a,after:b,pixels});
  record(codec+'-canvas-readback',pixels.max-pixels.min>30,{pixels});
  await evaluate('document.querySelector("video").currentTime=6;true');await delay(3000);const seek=await evaluate('sample()');record(codec+'-seek',!seek.error&&seek.ready>=2&&seek.frames>b.frames,{after:seek});
 }
 if(!process.argv.includes('--no-trace')) {
 await c.send('Tracing.end');const trace=await Promise.race([traceDone,delay(20000).then(()=>{throw Error('Trace completion timed out');})]);
 {const events=traceEvents;fs.writeFileSync(output.replace(/\.json$/,'.trace.json'),JSON.stringify({traceEvents:events}));const threads=events.filter(e=>e.ph==='M'&&e.name==='thread_name');const drdc=threads.filter(e=>String(e.args?.name).includes('CompositorGpu'));const tids=new Set(drdc.map(e=>e.pid+':'+e.tid));const work=events.filter(e=>tids.has(e.pid+':'+e.tid)&&e.ph!=='M');report.drdcThreads=drdc;report.drdcWorkEvents=work.length;report.drdcEventNames=[...new Set(work.map(e=>e.name))];record('drdc-thread-executes-work',drdc.length>0&&work.some(e=>/Draw|Paint|Swap/.test(e.name)),{});}
 }
 // An actual background/foreground cycle exercises EGL context lifecycle.
 const beforeBackground=await evaluate('sample()');keepScreenActive=false;execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','keyEvent','Home'],{timeout:15000});await delay(10000);execFileSync(hdc,['-t','6YT0226706000164','shell','aa','start','-a','EntryAbility','-b','com.example.ohos.chromium'],{timeout:15000});await c.send('Target.activateTarget',{targetId});keepScreenActive=true;await delay(3000);const afterBackground=await evaluate('sample()');record('hevc-background-foreground',!afterBackground.error&&afterBackground.frames>beforeBackground.frames&&!report.rendererCrashed,{before:beforeBackground,after:afterBackground});
 const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);fs.writeFileSync(output.replace(/\.json$/,'.png'),Buffer.from(shot.data,'base64'));
 await evaluate('document.querySelector("video").pause();true');const decoderNames=report.media.filter(e=>e.method==='Media.playerPropertiesChanged').flatMap(e=>e.params.properties).filter(p=>p.name==='kVideoDecoderName').map(p=>p.value);record('platform-video-decoders',decoderNames.length>=2&&decoderNames.every(n=>n==='OHOSVideoDecoder'),{decoderNames});stopMedia();
 }
 await c.send('Page.navigate',{url:'http://127.0.0.1:19235/webgpu'},sessionId);for(let i=0;i<40;i++){if(await evaluate("typeof window.runWebGPUVerification==='function'"))break;await delay(200);}
 await evaluate('runWebGPUVerification();true');for(let i=0;i<80;i++){await delay(1000);report.webgpu=await evaluate('webgpuReport');checkpoint();if(report.webgpu?.done)break;}
 record('webgpu-regression',!!report.webgpu?.done&&!!report.webgpu?.passed,{summary:report.webgpu});
 await evaluate('window.finishWebGPUVerification?.();true');
 report.passed=report.cases.every(x=>x.passed)&&!report.rendererCrashed;
}catch(e){report.error=String(e);report.passed=false;console.error(report.error);}
finally{clearInterval(awakeTimer);off?.();if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));report.finishedAt=new Date().toISOString();checkpoint();console.log('Result',report.passed,'Report',output);}
