// Measure generated content in our own window. Never enumerate user tabs.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';

const [reportPath, statePath] = process.argv.slice(2);
const c = await connect();
const report = {browser:c.version,browserPid:c.ownPid,complete:false,samples:[],resizes:[]};
let targetId;
const html = `<!doctype html><meta charset="utf-8"><title>CHROMIUM_TEST_RENDER</title>
<style>html,body{margin:0;background:#f4f4f4;color:#202020;font:18px sans-serif}
#stage{position:relative;height:500px;overflow:hidden}i{position:absolute;width:22px;height:22px;background:#37a65a;border-radius:5px}
canvas{position:absolute;top:0;left:0}#marker{position:fixed;bottom:0;width:100%;height:8px;background:#37a65a}</style>
<h1>CHROMIUM_TEST_RENDER</h1><div id="stage"></div><div id="marker"></div>
<script>
const stage=document.querySelector('#stage');
const items=Array.from({length:120},(_,i)=>{const e=document.createElement('i');e.style.left=(i%20)*38+'px';e.style.top=Math.floor(i/20)*38+'px';stage.append(e);return e;});
window.measure=async(mode,duration=4000)=>{
 const canvas=document.createElement('canvas');canvas.width=768;canvas.height=384;
 const gl=mode==='webgl'?canvas.getContext('webgl'):null;
 const ctx=mode==='canvas'?canvas.getContext('2d'):null;
 if(mode!=='dom')stage.append(canvas);
 if(mode==='webgl'&&!gl)throw new Error('WebGL unavailable');
 const intervals=[],cpu=[];let start,previous;
 const visibility=document.visibilityState;
 await new Promise((resolve,reject)=>{
  let request;const timer=setTimeout(()=>{cancelAnimationFrame(request);reject(new Error('Animation sample timed out; visibility='+document.visibilityState));},duration+6000);
  function finish(){clearTimeout(timer);resolve();}
  function frame(t){if(document.visibilityState!=='visible'){clearTimeout(timer);reject(new Error('Animation sample became hidden'));return;}if(start===undefined){start=previous=t;request=requestAnimationFrame(frame);return;}
   intervals.push(t-previous);previous=t;const before=performance.now();
   if(mode==='dom')items.forEach((e,i)=>e.style.transform='translateY('+Math.sin(t/400+i)*90+'px)');
   if(ctx){ctx.fillStyle='#f4f4f4';ctx.fillRect(0,0,768,384);ctx.fillStyle='#37a65a';for(let i=0;i<120;i++)ctx.fillRect((i%20)*38,Math.floor(i/20)*38+Math.sin(t/400+i)*90,22,22);}
   if(gl){gl.clearColor(0.1+(Math.sin(t/400)+1)/8,0.7,0.2,1);gl.clear(gl.COLOR_BUFFER_BIT);}
   cpu.push(performance.now()-before);
   if(t-start>=duration)finish();else request=requestAnimationFrame(frame);
  }request=requestAnimationFrame(frame);
 });
 canvas.remove();const sorted=[...intervals].sort((a,b)=>a-b),times=[...cpu].sort((a,b)=>a-b);
 return {mode,visibility,frames:intervals.length,elapsedMs:intervals.reduce((a,b)=>a+b,0),fps:1000*intervals.length/intervals.reduce((a,b)=>a+b,0),p50FrameMs:sorted[Math.floor(sorted.length*.5)],p95FrameMs:sorted[Math.floor(sorted.length*.95)],over25ms:intervals.filter(x=>x>25).length,p95CallbackMs:times[Math.floor(times.length*.95)]};
};
</script>`;
try {
 const info=await c.send('SystemInfo.getInfo');
 report.gpu={devices:info.gpu.devices.map(d=>({vendorString:d.vendorString,deviceString:d.deviceString,driverVendor:d.driverVendor,driverVersion:d.driverVersion})),featureStatus:info.gpu.featureStatus,auxAttributes:Object.fromEntries(Object.entries(info.gpu.auxAttributes||{}).filter(([k])=>/^(gl_renderer|gl_vendor|gl_version|gl_implementation_parts|display_type|skia_backend_type|passthrough_cmd_decoder|sandboxed|in_process_gpu|initialization_time)$/.test(k)))};
 ({targetId}=await c.send('Target.createTarget',{url:'data:text/html;base64,'+Buffer.from(html).toString('base64'),newWindow:true}));
 await c.send('Target.activateTarget',{targetId});
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 const {windowId}=await c.send('Browser.getWindowForTarget',{targetId});
 report.windowId=windowId;
 await new Promise(r=>setTimeout(r,1500));
 const evaluate=async(expression)=>{
  const r=await c.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sessionId);
  if(r.exceptionDetails)throw new Error(r.exceptionDetails.text);return r.result.value;
 };
 await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
 await c.send('Browser.setWindowBounds',{windowId,bounds:{width:1080,height:780}});
 await new Promise(r=>setTimeout(r,700));
 report.initialViewport=await evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,visible:document.visibilityState})');
 if(report.initialViewport.visible!=='visible')throw new Error('Controlled test window is not visible');
 for(let round=0;round<3;round++)for(const mode of ['dom','canvas','webgl']){
  await c.send('Target.activateTarget',{targetId});
  const sample=await evaluate('measure('+JSON.stringify(mode)+')');report.samples.push({round,...sample});fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
 }
 await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
 for(const [width,height] of [[1080,780],[1280,900],[1100,800],[1400,960],[1080,780]]){
  const before=performance.now();
  await c.send('Browser.setWindowBounds',{windowId,bounds:{width,height}});
  await new Promise(r=>setTimeout(r,500));
  const bounds=await c.send('Browser.getWindowBounds',{windowId});
  const viewport=await evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})');
  report.resizes.push({requested:{width,height},bounds:bounds.bounds,viewport,observationMs:performance.now()-before});
 }
 report.complete=true;
 if(statePath){fs.writeFileSync(statePath,JSON.stringify({targetId,windowId,browserPid:c.ownPid}));report.controlledWindowLeftOpen=true;}
} catch(error){report.error=error.message;process.exitCode=1;}
finally {
 if(targetId&&(!statePath||!report.complete))await c.send('Target.closeTarget',{targetId}).catch(()=>{});
 fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));c.close();
}
