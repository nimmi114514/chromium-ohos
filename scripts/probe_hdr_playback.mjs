// Operates only on the HDR target and anonymous context created below.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..');
const label=process.argv[2];
const selected=process.argv[3]||'hevc-main10-pq.mp4';
if(!['hevc-main10-pq.mp4','hevc-main10-hlg.mp4','hevc-main10-colors.mp4','avc-sdr.mp4'].includes(selected))throw Error('Uncontrolled asset');
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Expected a report label');
const assets=path.join(root,'tests/hdr/assets');
const html=`<!doctype html><title>Chromium HDR calibration</title><style>body{margin:0;background:#222;color:white}video{width:100%;max-height:85vh}</style><video id="v" muted controls loop src="/pq.mp4"></video><p>HDR calibration — generated BT.2020 / PQ reference bars</p>`;
const server=http.createServer((req,res)=>{
 if(req.url!=='/pq.mp4'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(html);return;}
 const file=path.join(assets,selected),size=fs.statSync(file).size;
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
 if(range){const start=Number(range[1]),end=Math.min(range[2]?Number(range[2]):size-1,size-1);if(start>=size){res.writeHead(416);res.end();return;}res.writeHead(206,{'Content-Type':'video/mp4','Content-Length':end-start+1,'Content-Range':`bytes ${start}-${end}/${size}`,'Accept-Ranges':'bytes'});fs.createReadStream(file,{start,end}).pipe(res);}
 else{res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':size,'Accept-Ranges':'bytes'});fs.createReadStream(file).pipe(res);}
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,asset:selected,passed:false,physicalLuminanceMeasured:false,mediaEvents:[]};
let c,browserContextId,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/hdr',browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 c.onEvent(e=>{if(e.sessionId===sessionId&&e.method.startsWith('Media.'))report.mediaEvents.push({method:e.method,params:e.params});});
 await c.send('Runtime.enable',{},sessionId);await c.send('Media.enable',{},sessionId);
 await c.send('Page.bringToFront',{},sessionId);
 const evaluate=async expression=>{const r=await c.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<30;i++){if(await evaluate("!!document.querySelector('#v')"))break;await new Promise(r=>setTimeout(r,100));}
 report.capabilities=await evaluate(`(async()=>({hdr:matchMedia('(dynamic-range: high)').matches,videoHdr:matchMedia('(video-dynamic-range: high)').matches,colorDepth:screen.colorDepth,gamut:matchMedia('(color-gamut: rec2020)').matches,hevc:document.querySelector('#v').canPlayType('video/mp4; codecs="hvc1.2.4.L93.B0"'),decoding:await navigator.mediaCapabilities.decodingInfo({type:'file',video:{contentType:'video/mp4; codecs="hvc1.2.4.L93.B0"',width:640,height:360,bitrate:100000,framerate:30,colorGamut:'rec2020',transferFunction:'pq',hdrMetadataType:'smpteSt2086'}})}))()`);
 report.play=await evaluate(`(async()=>{const v=document.querySelector('#v');await Promise.race([v.play(),new Promise((_,reject)=>setTimeout(()=>reject(Error('play timeout')),10000))]);return {started:true,visibility:document.visibilityState};})()`);
 await new Promise(r=>setTimeout(r,6500));
 report.frame=await evaluate(`(()=>{const v=document.querySelector('#v'),q=v.getVideoPlaybackQuality();const c=document.createElement('canvas');c.width=640;c.height=360;const x=c.getContext('2d');x.drawImage(v,0,0,640,360);const p=x.getImageData(0,180,640,1).data;return {time:v.currentTime,width:v.videoWidth,height:v.videoHeight,frames:q.totalVideoFrames,drops:q.droppedVideoFrames,error:v.error?.code||0,visibility:document.visibilityState,bars:Array.from({length:8},(_,i)=>Array.from(p.slice((i*80+40)*4,(i*80+40)*4+3)))};})()`);
 report.rawTexture=await evaluate(`(()=>{const v=document.querySelector('#v'),c=document.createElement('canvas');c.width=640;c.height=360;const g=c.getContext('webgl2',{premultipliedAlpha:false});if(!g)return {available:false};g.pixelStorei(g.UNPACK_COLORSPACE_CONVERSION_WEBGL,g.NONE);const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,v);const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0);const p=new Uint8Array(640*4);g.readPixels(0,180,640,1,g.RGBA,g.UNSIGNED_BYTE,p);return {available:true,error:g.getError(),status:g.checkFramebufferStatus(g.FRAMEBUFFER),bars:Array.from({length:8},(_,i)=>Array.from(p.slice((i*80+40)*4,(i*80+40)*4+3)))};})()`);
 report.passed=report.frame.time>3&&report.frame.frames>60&&!report.frame.error;
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 await new Promise(r=>server.close(r));
 fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({...report,mediaEvents:report.mediaEvents.map(e=>e.method)}));
}
