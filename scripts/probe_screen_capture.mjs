// Compare OS capture and Chromium capture using generated, unencrypted content.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'reports',label+'.json');
const html='<!doctype html><title>Screen capture verification</title><style>body{margin:0;background:#fafafa;font:28px sans-serif;color:#101010}h1{padding:20px}.colors{display:flex;height:200px}.colors div{flex:1}video{width:60vw;max-height:45vh;display:block;margin:12px auto}</style><h1>Generated screen capture reference</h1><div class="colors"><div style="background:red"></div><div style="background:lime"></div><div style="background:blue"></div><div style="background:yellow"></div></div><video id="v" muted controls loop></video>';
const server=http.createServer((req,res)=>{
 if(['/pq.mp4','/encrypted.mp4'].includes(req.url)){const file=path.join(root,'tests/hdr/assets',req.url==='/pq.mp4'?'hevc-main10-pq.mp4':'avc-clearkey-capture.mp4');const bytes=fs.readFileSync(file);res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':bytes.length});res.end(bytes);}
 else{res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);}
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,anonymousContext:true,generatedContent:true,productionLicensesOrAccountsUsed:false,cases:[]};let c,targetId,browserContextId;
const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
const remote='/data/local/tmp/'+label+'.jpeg';
const run=(...args)=>execFileSync(hdc,['-t','6YT0226706000164',...args],{encoding:'utf8',timeout:20000});
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/capture',browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);
 const {windowId}=await c.send('Browser.getWindowForTarget',{targetId});
 const evaluate=async expression=>{const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 const screen=await evaluate('({width:screen.availWidth,height:screen.availHeight})');
 await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});await c.send('Browser.setWindowBounds',{windowId,bounds:{left:0,top:0,width:screen.width,height:screen.height}});await c.send('Page.bringToFront',{},sessionId);
 for(let i=0;i<30;i++){if(await evaluate("!!document.querySelector('#v')"))break;await new Promise(r=>setTimeout(r,200));}
 const cases=process.argv.includes('--clearkey')?['sdr','clearkey-video','sdr-after-clearkey']:['sdr','hdr-video','sdr-after-hdr'];
 for(const name of cases){
  if(name==='hdr-video')await evaluate("(async()=>{const v=document.querySelector('#v');v.src='/pq.mp4';await v.play();return true;})()");
  if(name==='sdr-after-hdr')await evaluate("(()=>{const v=document.querySelector('#v');v.pause();v.removeAttribute('src');v.load();return true;})()");
  if(name==='clearkey-video'){
   report.clearkeyPreparation=await evaluate(`(async()=>{const v=document.querySelector('#v');const access=await navigator.requestMediaKeySystemAccess('org.w3.clearkey',[{initDataTypes:['keyids'],videoCapabilities:[{contentType:'video/mp4; codecs="avc1.640028"'}]}]);const keys=await access.createMediaKeys();await v.setMediaKeys(keys);const s=keys.createSession();const done=new Promise((resolve,reject)=>s.addEventListener('message',async()=>{try{await s.update(new TextEncoder().encode(JSON.stringify({keys:[{kty:'oct',kid:'ECEyQ1RldoeYqbrL3O3-Dw',k:'ABEiM0RVZneImaq7zN3u_w'}],type:'temporary'})));resolve();}catch(e){reject(e);}},{once:true}));await s.generateRequest('keyids',new TextEncoder().encode(JSON.stringify({kids:['ECEyQ1RldoeYqbrL3O3-Dw']})));await done;v.src='/encrypted.mp4';await Promise.race([v.play(),new Promise((_,j)=>setTimeout(()=>j(Error('encrypted play timeout')),8000))]);return {sessionReady:true};})()`);
  }
  if(name==='sdr-after-clearkey'){
   await c.send('Page.navigate',{url:'http://127.0.0.1:19235/capture-after-clearkey'},sessionId);
   for(let i=0;i<30;i++){if(await evaluate("!!document.querySelector('#v')"))break;await new Promise(r=>setTimeout(r,200));}
  }
  await new Promise(r=>setTimeout(r,3000));
  const entry={name,state:await evaluate("({visibility:document.visibilityState,videoTime:document.querySelector('#v').currentTime,videoWidth:document.querySelector('#v').videoWidth,hdr:matchMedia('(dynamic-range:high)').matches})")};report.cases.push(entry);
  const shot=await c.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);entry.browserScreenshot=label+'-'+name+'-browser.png';fs.writeFileSync(path.join(root,'reports',entry.browserScreenshot),Buffer.from(shot.data,'base64'));
  if(entry.state.visibility!=='visible'){entry.systemCaptureSkipped='Test window is hidden; do not capture another window.';fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');continue;}
  entry.systemCaptureResult=run('shell','snapshot_display','-f',remote);
  entry.systemScreenshot=label+'-'+name+'-system.jpeg';entry.receiveResult=run('file','recv',remote,path.join(root,'reports',entry.systemScreenshot));
  run('shell','rm',remote);
  fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
 }
 report.complete=true;
}catch(e){report.error=String(e);}
finally{
 try{run('shell','rm',remote);}catch{}
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 await new Promise(r=>server.close(r));fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
