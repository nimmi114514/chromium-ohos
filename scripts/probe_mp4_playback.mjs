// Exercise generated H.264/AAC media, including separate MSE audio/video tracks.
// Only creates and closes its own diagnostic target and local HTTP server.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';

const [reportPath, assetsPath, requestedTests, windowMode, probeMode] = process.argv.slice(2);
const assets = path.resolve(assetsPath);
const manifest = JSON.parse(fs.readFileSync(path.join(assets,'manifest.json'),'utf8'));
const videoMime = `video/mp4; codecs="${manifest.videoCodec}"`;
const audioMime = `audio/mp4; codecs="${manifest.audioCodec}"`;
const minimumPlaybackSeconds=manifest.minimumPlaybackSeconds||3;
const backgroundSeconds=manifest.backgroundSeconds||30;
const html = `<!doctype html><meta charset="utf-8"><title>CHROMIUM_TEST_MP4</title>
<style>body{background:#eee;color:#222;font:18px sans-serif}video{width:640px;max-width:90vw;background:#111}</style>
<h1>CHROMIUM_TEST_MP4</h1><div id="stage"></div><pre id="result"></pre><script>
const videoMime=${JSON.stringify(videoMime)},audioMime=${JSON.stringify(audioMime)},expectedWidth=${manifest.width||320},expectedHeight=${manifest.height||180},minimumPlaybackSeconds=${minimumPlaybackSeconds};
const within=(p,ms=Math.max(9000,(minimumPlaybackSeconds+8)*1000))=>Promise.race([p,new Promise((_,r)=>setTimeout(()=>r(new Error('Media test timed out')),ms))]);
const once=(target,event)=>new Promise((resolve,reject)=>{target.addEventListener(event,resolve,{once:true});target.addEventListener('error',()=>reject(new Error('Media error '+(target.error?.code||'event'))),{once:true});});
function mediaPhase(value){window.mseProgress=value;console.log('CHROMIUM_TEST_MEDIA_PHASE:'+value);}
async function observePlayback(video,readback=true){
 let playbackPhase='play';try{await within(video.play());playbackPhase='time';
 await within(new Promise((resolve,reject)=>{const timer=setInterval(()=>{if(video.error){clearInterval(timer);reject(new Error('Video error '+video.error.code));}else if(video.currentTime>minimumPlaybackSeconds){clearInterval(timer);resolve();}},40);}));}catch(error){const q=video.getVideoPlaybackQuality();throw new Error(error.message+' '+JSON.stringify({phase:playbackPhase,time:video.currentTime,paused:video.paused,readyState:video.readyState,width:video.videoWidth,frames:q.totalVideoFrames,dropped:q.droppedVideoFrames,buffered:Array.from({length:video.buffered.length},(_,i)=>[video.buffered.start(i),video.buffered.end(i)])}));}
 mediaPhase('pausing_after_playback');video.pause();const q=video.getVideoPlaybackQuality();
 if(!readback)return {passed:video.currentTime>minimumPlaybackSeconds&&video.videoWidth===expectedWidth&&video.videoHeight===expectedHeight&&q.totalVideoFrames>minimumPlaybackSeconds*10,currentTime:video.currentTime,width:video.videoWidth,height:video.videoHeight,frames:q.totalVideoFrames,droppedFrames:q.droppedVideoFrames,canvasReadbackVerified:false};
 const canvas=document.createElement('canvas');canvas.width=32;canvas.height=18;const ctx=canvas.getContext('2d');mediaPhase('canvas_draw');ctx.drawImage(video,0,0,32,18);
 mediaPhase('canvas_pixels');const pixels=ctx.getImageData(0,0,32,18).data;let minimum=255,maximum=0;
 for(let i=0;i<pixels.length;i++)if(i%4!==3){minimum=Math.min(minimum,pixels[i]);maximum=Math.max(maximum,pixels[i]);}
 return {passed:video.currentTime>minimumPlaybackSeconds&&video.videoWidth===expectedWidth&&video.videoHeight===expectedHeight&&q.totalVideoFrames>minimumPlaybackSeconds*10&&maximum-minimum>30,currentTime:video.currentTime,width:video.videoWidth,height:video.videoHeight,frames:q.totalVideoFrames,droppedFrames:q.droppedVideoFrames,pixelRange:maximum-minimum};
}
window.tests={
 formats:async()=>{
  const v=document.createElement('video'),a=document.createElement('audio');
  const d={videoCanPlay:v.canPlayType(videoMime),audioCanPlay:a.canPlayType(audioMime),muxedCanPlay:v.canPlayType('video/mp4; codecs="${manifest.videoCodec}, ${manifest.audioCodec}"'),mseVideo:MediaSource.isTypeSupported(videoMime),mseAudio:MediaSource.isTypeSupported(audioMime),hevcCanPlay:v.canPlayType('video/mp4; codecs="hvc1.1.6.L93.B0"')};
  return {passed:!!d.videoCanPlay&&!!d.audioCanPlay&&!!d.muxedCanPlay&&d.mseVideo&&d.mseAudio,...d};
 },
 html5_video:async()=>{
  const v=document.createElement('video');v.muted=true;v.controls=true;v.src='/avc-aac.mp4';stage.replaceChildren(v);
  try{return await observePlayback(v);}finally{v.pause();v.removeAttribute('src');v.load();v.remove();}
 },
 aac_decode:async()=>{
  const c=new AudioContext();try{const r=await fetch('/audio-aac.m4a');const b=await within(c.decodeAudioData(await r.arrayBuffer()));return {passed:b.duration>3&&b.numberOfChannels===1&&b.getChannelData(0).some(x=>Math.abs(x)>.01),duration:b.duration,sampleRate:b.sampleRate,channels:b.numberOfChannels};}finally{await c.close();}
 },
 mse_separate_tracks:async()=>{
  if(!MediaSource.isTypeSupported(videoMime)||!MediaSource.isTypeSupported(audioMime))return {passed:false,error:'Required MSE codecs unsupported'};
  const v=document.createElement('video');v.muted=${!probeMode?.startsWith("background")};v.volume=.05;v.controls=true;stage.replaceChildren(v);
  window.mseProgress='opening';const ms=new MediaSource(),url=URL.createObjectURL(ms);v.src=url;
  try{
   await within(once(ms,'sourceopen'));window.mseProgress='sourceopen';
   const append=async(mime,src)=>{const sb=ms.addSourceBuffer(mime);const bytes=await (await fetch(src)).arrayBuffer();const done=once(sb,'updateend');sb.appendBuffer(bytes);await within(done);return {start:sb.buffered.start(0),end:sb.buffered.end(0)};};
   window.mseProgress='appending';const buffered=await Promise.all([append(videoMime,'/video-fragmented.mp4'),append(audioMime,'/audio-fragmented.mp4')]);ms.endOfStream();window.mseProgress='playing';
   const played=await observePlayback(v,${probeMode!=="no-readback"});
   if(!played.passed)return {...played,sourceBufferCount:ms.sourceBuffers.length,buffered};
   const seeked=once(v,'seeked');v.currentTime=.4;await within(seeked);
   const framesBeforeSeekPlayback=v.getVideoPlaybackQuality().totalVideoFrames;
   await within(v.play());await within(new Promise((resolve,reject)=>{const timer=setInterval(()=>{if(v.error){clearInterval(timer);reject(new Error('Video error after seek'));}else if(v.currentTime>1.4){clearInterval(timer);resolve();}},40);}));v.pause();
   const framesAfterSeekPlayback=v.getVideoPlaybackQuality().totalVideoFrames;
   return {...played,passed:played.passed&&framesAfterSeekPlayback>framesBeforeSeekPlayback+10,sourceBufferCount:ms.sourceBuffers.length,buffered,seekVerified:framesAfterSeekPlayback>framesBeforeSeekPlayback+10,seekTime:v.currentTime,framesBeforeSeekPlayback,framesAfterSeekPlayback};
  }finally{v.pause();v.removeAttribute('src');v.load();v.remove();URL.revokeObjectURL(url);}
 },
 media_capabilities:async()=>{
  const cfg={type:'media-source',video:{contentType:videoMime,width:320,height:180,bitrate:250000,framerate:30},audio:{contentType:audioMime,channels:'1',bitrate:64000,samplerate:48000}};
  const r=await within(navigator.mediaCapabilities.decodingInfo(cfg));return {passed:r.supported,supported:r.supported,smooth:r.smooth,powerEfficient:r.powerEfficient};
 }
};
</script>`;
const files = new Map(manifest.files.map(f=>['/'+f.name,f.name]));
const server = http.createServer((req,res)=>{
 const name=files.get(req.url);
 if(!name){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(html);return;}
 const file=path.join(assets,name),size=fs.statSync(file).size;
 const contentType=name.endsWith('.m4a')?'audio/mp4':'video/mp4';
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
 if(range){const start=Number(range[1]),end=Math.min(range[2]?Number(range[2]):size-1,size-1);if(start>=size||end<start){res.writeHead(416,{'Content-Range':`bytes */${size}`});res.end();return;}res.writeHead(206,{'Content-Type':contentType,'Content-Length':end-start+1,'Content-Range':`bytes ${start}-${end}/${size}`,'Accept-Ranges':'bytes'});fs.createReadStream(file,{start,end}).pipe(res);}
 else{res.writeHead(200,{'Content-Type':contentType,'Content-Length':size,'Accept-Ranges':'bytes'});fs.createReadStream(file).pipe(res);}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(19235,'127.0.0.1',resolve);});
const report={complete:false,allPassed:false,generatedContent:true,videoCodec:manifest.videoCodec,audioCodec:manifest.audioCodec,results:{},bilibiliPlaybackVerified:false};
let c,targetId,browserContextId;
try{
 c=await connect();report.browserPid=c.ownPid;report.browser=c.version;
 if(windowMode==='anonymous'){({browserContextId}=await c.send('Target.createBrowserContext'));report.anonymousContext=true;}
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/test',newWindow:windowMode!=='existing',...(browserContextId?{browserContextId}:{})}));
 await c.send('Target.activateTarget',{targetId});
 const {windowId}=await c.send('Browser.getWindowForTarget',{targetId});
 if(windowMode!=='existing')await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
 let {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Target.setDiscoverTargets',{discover:true});
 await c.send('Media.enable',{},sessionId);
 await c.send('Runtime.enable',{},sessionId);
 c.onEvent(m=>{if(m.sessionId===sessionId&&m.method==='Runtime.consoleAPICalled')for(const a of m.params.args)if(typeof a.value==='string'&&a.value.startsWith('CHROMIUM_TEST_MEDIA_PHASE:')){report.lastNativeProbePhase=a.value.split(':')[1];fs.writeFileSync(reportPath,JSON.stringify(report,null,2));}});
 await c.send('Inspector.enable',{},sessionId);
 c.onEvent(m=>{if((m.sessionId===sessionId&&m.method==='Inspector.targetCrashed')||(m.method==='Target.targetCrashed'&&m.params.targetId===targetId)){report.rendererCrashed=true;report.crashStatus=m.params.status||m.method;fs.writeFileSync(reportPath,JSON.stringify(report,null,2));}});
 report.mediaProperties=[];c.onEvent(m=>{if(m.sessionId===sessionId&&m.method==='Media.playerPropertiesChanged')for(const p of m.params.properties)if(/decoder|codec|platform/i.test(p.name))report.mediaProperties.push({playerId:m.params.playerId,name:p.name,value:p.value});});
 await new Promise(r=>setTimeout(r,1200));
 const selected=requestedTests?requestedTests.split(','):['formats','html5_video','aac_decode','mse_separate_tracks','media_capabilities'];report.selectedTests=selected;
 for(const name of selected){
  if(!['formats','html5_video','aac_decode','mse_separate_tracks','media_capabilities'].includes(name))throw new Error('Unknown controlled test');
  await c.send('Target.activateTarget',{targetId});
  if(windowMode!=='existing')await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
  await new Promise(r=>setTimeout(r,500));
  await c.send('Runtime.evaluate',{expression:`window.probeRun={done:false};(async()=>{try{probeRun.result=await tests[${JSON.stringify(name)}]();}catch(e){probeRun.result={passed:false,error:e.name+': '+e.message};}finally{probeRun.done=true;}})();true`,returnByValue:true,userGesture:true},sessionId);
  const deadline=Date.now()+Math.max(35000,(minimumPlaybackSeconds+25)*1000);let state;
  while(Date.now()<deadline){await new Promise(r=>setTimeout(r,250));const r=await c.send('Runtime.evaluate',{expression:'({done:probeRun.done,result:probeRun.result,phase:window.mseProgress,visibility:document.visibilityState,focused:document.hasFocus(),video:[...document.querySelectorAll("video")].map(v=>({time:v.currentTime,readyState:v.readyState,networkState:v.networkState,paused:v.paused}))})',returnByValue:true},sessionId);if(r.exceptionDetails)throw new Error(r.exceptionDetails.text);state=r.result.value;report.lastProgress={test:name,...state};report.testProgress??={};report.testProgress[name]=state;fs.writeFileSync(reportPath,JSON.stringify(report,null,2));if(state.done)break;
   if(probeMode?.startsWith('background')&&name==='mse_separate_tracks'&&!report.backgroundCycle&&state.video?.some(v=>v.time>5)){
    const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
    report.backgroundCycle={secondsRequested:backgroundSeconds,before:state,enteredAt:new Date().toISOString()};fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
    await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'minimized'}});
    execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','keyEvent','1'],{timeout:10000,encoding:'utf8'});
    if(probeMode==='background-detached'){await c.send('Target.detachFromTarget',{sessionId});report.detachedWhileBackgrounded=true;}
    await new Promise(r=>setTimeout(r,backgroundSeconds*1000));
    execFileSync(hdc,['-t','6YT0226706000164','shell','aa','start','-a','EntryAbility','-b','com.example.ohos.chromium'],{timeout:10000,encoding:'utf8'});
    await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
    await c.send('Target.activateTarget',{targetId});
    if(probeMode==='background-detached'){({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));await c.send('Runtime.enable',{},sessionId);await c.send('Media.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);const after=await c.send('Runtime.evaluate',{expression:'({wasDiscarded:document.wasDiscarded,probePresent:!!window.probeRun,visibility:document.visibilityState})',returnByValue:true},sessionId);report.backgroundCycle.after=after.result.value;}
    report.backgroundCycle.returnedAt=new Date().toISOString();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
   }
  }
  if(!state?.done)throw new Error('Controlled media test timed out: '+name+' phase='+state?.phase);
  report.results[name]=state.result;
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
  console.log(JSON.stringify({test:name,...state.result}));
 }
 report.complete=true;report.allPassed=Object.values(report.results).every(x=>x.passed===true);
 if(!report.allPassed)process.exitCode=1;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
 if(c&&browserContextId)await c.send('Target.disposeBrowserContext',{browserContextId}).catch(()=>{});
 else if(c&&targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});
 c?.close();server.closeAllConnections();await new Promise(r=>server.close(r));
 fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
