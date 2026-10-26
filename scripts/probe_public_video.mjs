// Anonymous, disposable context: do not inspect the user's existing tabs/account.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath,url] = process.argv.slice(2);
const hdrTest = process.argv.includes('--hdr');
const allowed = new URL(url);
if(!['www.bilibili.com','www.youtube.com'].includes(allowed.hostname)||allowed.protocol!=='https:')throw new Error('Expected a public video URL');
const c=await connect(),report={url,browserPid:c.ownPid,anonymousContext:true,playbackVerified:false,observations:[],mediaProperties:[],scriptErrors:[]};
let browserContextId,targetId;
try{
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true,browserContextId}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Page.enable',{},sessionId);await c.send('Runtime.enable',{},sessionId);await c.send('Media.enable',{},sessionId);
 c.onEvent(m=>{
  if(m.sessionId!==sessionId)return;
  if(m.method==='Media.playerPropertiesChanged')for(const p of m.params.properties)if(/decoder|codec|platform|videoTracks|color|hdr/i.test(p.name))report.mediaProperties.push({playerId:m.params.playerId,name:p.name,value:p.value});
  if(m.method==='Runtime.exceptionThrown'){const d=m.params.exceptionDetails;report.scriptErrors.push((d.exception?.description||d.text||'').split('\n')[0].slice(0,180));}
 });
 await c.send('Target.activateTarget',{targetId});await c.send('Page.navigate',{url},sessionId);
 const expression=`(() => {
 const player=document.querySelector('#movie_player');
 const hdrTest=${hdrTest};
 const qualityData=player?.getAvailableQualityData?.()||[];
 if(hdrTest&&player?.setPlaybackQualityRange){const q=qualityData.find(x=>/HDR/i.test(x.qualityLabel||x.label||'')&&/1080|720/.test(x.qualityLabel||x.label||''));if(q)player.setPlaybackQualityRange(q.quality,q.quality);}
 const videos=[...document.querySelectorAll('video')];
 for(const v of videos){v.muted=true;if(v.paused)v.play().catch(()=>{});}
 const text=document.body?.innerText||'';
 const safeText=text.replace(/[0-9]{1,3}(?:[.][0-9]{1,3}){3}/g,'[redacted IP]');
 return {readyState:document.readyState,title:document.title,location:location.origin+location.pathname,bodyPreview:safeText.slice(0,500),wasmAvailable:typeof WebAssembly!=='undefined',hdr:matchMedia('(dynamic-range:high)').matches,qualityData,selectedQuality:player?.getPlaybackQuality?.(),mp4:document.createElement('video').canPlayType('video/mp4;codecs="avc1.64001F,mp4a.40.2"'),mse:MediaSource.isTypeSupported('video/mp4;codecs="avc1.64001F"'),unsupportedPlayerMessage:/当前浏览器不支持.{0,30}(?:html5|HTML5)|(?:html5|HTML5).{0,15}播放器.{0,15}无法播放/.test(text),bwpVideoCount:document.querySelectorAll('bwp-video').length,loginGate:/登录后继续观看|登录即可观看|Sign in to confirm you.re not a bot/.test(text),verificationGate:/请完成安全验证|验证后继续访问|网络环境存在风险/.test(text),videos:videos.map(v=>({currentTime:v.currentTime,width:v.videoWidth,height:v.videoHeight,paused:v.paused,readyState:v.readyState,errorCode:v.error?.code||0,totalFrames:v.getVideoPlaybackQuality().totalVideoFrames,droppedFrames:v.getVideoPlaybackQuality().droppedVideoFrames}))};
 })()`;
 for(let i=0;i<45;i++){
  await new Promise(r=>setTimeout(r,1000));
  const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,userGesture:true},sessionId);
  if(r.exceptionDetails){report.evaluateError=r.exceptionDetails.text;continue;}
  const state=r.result.value;report.observations.push({seconds:i+1,...state});
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
  if(state.videos.some(v=>v.currentTime>2&&v.width>0&&v.totalFrames>10)){
   report.playbackVerified=true;if(!hdrTest||i>20)break;
  }
  if(i===8)await c.send('Runtime.evaluate',{expression:`document.querySelector('.bpx-player-ctrl-play, .ytp-large-play-button')?.click()`,userGesture:true},sessionId);
  if(i>15&&(state.unsupportedPlayerMessage||state.verificationGate||state.loginGate||state.location?.includes('www.google.com/sorry/')))break;
 }
 report.complete=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
 if(browserContextId)await c.send('Target.disposeBrowserContext',{browserContextId}).catch(()=>{});
 c.close();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
 console.log(JSON.stringify({...report,observations:report.observations.slice(-2)}));
}
