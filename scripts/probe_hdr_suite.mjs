// One disposable, anonymous calibration window; only locally generated video.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..'),label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const assets=path.join(root,'tests/hdr/assets');
const cases=process.argv[3]==='remaining'?['hevc-main10-ramp.mp4','avc-sdr.mp4']:['hevc-main10-pq.mp4','hevc-main10-hlg.mp4','hevc-main10-colors.mp4','hevc-main10-ramp.mp4','avc-sdr.mp4'];
const html='<!doctype html><title>Chromium HDR calibration</title><style>body{background:#222;color:white;margin:0}video{width:100%;max-height:85vh}</style><video id="v" muted controls></video><p>Generated HDR / SDR calibration sequence</p>';
const server=http.createServer((req,res)=>{
 const name=decodeURIComponent((req.url||'').slice(1));
 if(!cases.includes(name)){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);return;}
 const file=path.join(assets,name),size=fs.statSync(file).size,range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
 if(range){const start=Number(range[1]),end=Math.min(range[2]?Number(range[2]):size-1,size-1);if(start>=size){res.writeHead(416);res.end();return;}res.writeHead(206,{'Content-Type':'video/mp4','Content-Length':end-start+1,'Content-Range':`bytes ${start}-${end}/${size}`,'Accept-Ranges':'bytes'});fs.createReadStream(file,{start,end}).pipe(res);}
 else{res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':size,'Accept-Ranges':'bytes'});fs.createReadStream(file).pipe(res);}
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,passed:false,physicalLuminanceMeasured:false,cases:[],mediaEvents:[]};
let c,browserContextId,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/hdr',browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 c.onEvent(e=>{if(e.sessionId===sessionId&&e.method.startsWith('Media.'))report.mediaEvents.push(e);});
 await c.send('Runtime.enable',{},sessionId);await c.send('Media.enable',{},sessionId);await c.send('Page.bringToFront',{},sessionId);
 const evaluate=async expression=>{const r=await c.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<30;i++){if(await evaluate("!!document.querySelector('#v')"))break;await new Promise(r=>setTimeout(r,100));}
 report.capabilities=await evaluate("({hdr:matchMedia('(dynamic-range: high)').matches,p3:matchMedia('(color-gamut: p3)').matches,rec2020:matchMedia('(color-gamut: rec2020)').matches,colorDepth:screen.colorDepth})");
 for(const asset of cases){
  const result={asset};report.cases.push(result);
  await evaluate(`(async()=>{const v=document.querySelector('#v');v.pause();v.src=${JSON.stringify('/'+asset)};v.load();await Promise.race([v.play(),new Promise((_,r)=>setTimeout(()=>r(Error('play timeout')),8000))]);return true;})()`);
  await new Promise(r=>setTimeout(r,3600));
  result.frame=await evaluate("(()=>{const v=document.querySelector('#v'),q=v.getVideoPlaybackQuality();return {time:v.currentTime,width:v.videoWidth,height:v.videoHeight,frames:q.totalVideoFrames,drops:q.droppedVideoFrames,error:v.error?.code||0,visibility:document.visibilityState};})()");
  result.raw=await evaluate(`(()=>{const v=document.querySelector('#v'),c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;const g=c.getContext('webgl2',{premultipliedAlpha:false});if(!g)return {available:false};const floating=${asset.includes('ramp')};if(floating&&!g.getExtension('EXT_color_buffer_float'))return {available:false,reason:'no EXT_color_buffer_float'};g.pixelStorei(g.UNPACK_COLORSPACE_CONVERSION_WEBGL,g.NONE);const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.NEAREST);g.texImage2D(g.TEXTURE_2D,0,floating?g.RGBA16F:g.RGBA,g.RGBA,floating?g.FLOAT:g.UNSIGNED_BYTE,v);const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0);const p=floating?new Float32Array(c.width*4):new Uint8Array(c.width*4);g.readPixels(0,Math.floor(c.height/2),c.width,1,g.RGBA,floating?g.FLOAT:g.UNSIGNED_BYTE,p);return {available:true,floating,error:g.getError(),status:g.checkFramebufferStatus(g.FRAMEBUFFER),uniqueRed:new Set(Array.from({length:c.width},(_,i)=>Math.round(p[i*4]*1000000))).size,bars:Array.from({length:8},(_,i)=>Array.from(p.slice((Math.floor((i+.5)*c.width/8))*4,(Math.floor((i+.5)*c.width/8))*4+3)))};})()`);
  result.seek=await evaluate("(async()=>{const v=document.querySelector('#v');const done=new Promise((r,j)=>{v.addEventListener('seeked',r,{once:true});setTimeout(()=>j(Error('seek timeout')),8000);});v.currentTime=1;await done;await v.play();return {ok:true,time:v.currentTime};})()");
  result.passed=result.frame.time>2&&result.frame.frames>45&&!result.frame.error&&result.raw.error===0&&result.seek.ok;
  if(process.argv.includes('--background')&&asset==='hevc-main10-pq.mp4'){
   await evaluate("document.querySelector('#v').loop=true");
   const {windowId,bounds}=await c.send('Browser.getWindowForTarget',{targetId});
   await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'minimized'}});
   await new Promise(r=>setTimeout(r,30000));
   result.background=await evaluate("(()=>{const v=document.querySelector('#v');return {visibility:document.visibilityState,paused:v.paused,time:v.currentTime,frames:v.getVideoPlaybackQuality().totalVideoFrames,error:v.error?.code||0};})()");
   const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
   execFileSync(hdc,['-t','6YT0226706000164','shell','aa','start','-a','EntryAbility','-b','com.example.ohos.chromium'],{timeout:10000,encoding:'utf8'});
   await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
   if(bounds.windowState==='maximized')await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'maximized'}});
   await c.send('Target.activateTarget',{targetId});
   await new Promise(r=>setTimeout(r,1000));
   await evaluate("document.querySelector('#v').play().then(()=>true)");
   await new Promise(r=>setTimeout(r,2000));
   result.resumed=await evaluate("(()=>{const v=document.querySelector('#v');return {visibility:document.visibilityState,frames:v.getVideoPlaybackQuality().totalVideoFrames,error:v.error?.code||0};})()");
   result.passed&&=!result.background.error&&!result.resumed.error&&result.resumed.frames>result.background.frames;
  }
  fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');
 }
 const colors=report.cases.find(x=>x.asset.includes('colors'));
 const expected=JSON.parse(fs.readFileSync(path.join(root,'reports/native081-color-matrix-reference.json'))).samples.map(x=>x.expectedBT2020);
 if(colors){colors.maxRawColorError=Math.max(...expected.flatMap((p,i)=>p.map((v,k)=>Math.abs(v-colors.raw.bars[i][k]))));colors.passed&&=colors.maxRawColorError<=4;}
 const ramp=report.cases.find(x=>x.asset.includes('ramp'));ramp.moreThan8BitLevels=ramp.raw.floating&&ramp.raw.uniqueRed>512;ramp.passed&&=ramp.moreThan8BitLevels;
 report.passed=report.capabilities.hdr&&report.cases.every(x=>x.passed);
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 await new Promise(r=>server.close(r));fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,mediaEvents:report.mediaEvents.length}));
}
