// Reproduce the reported page termination in one anonymous, owned window.
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';

const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const output=path.resolve(import.meta.dirname,'../reports',label+'.json');
const clickLogin=process.argv.includes('--login-entry');
const report={label,anonymousContext:true,url:'https://music.apple.com/cn/new',observations:[],media:[],scriptErrors:[],openedWindowOrigins:[],crashed:false};
let c,browserContextId,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 const save=()=>fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 c.onEvent(e=>{
  if((e.method==='Target.targetCrashed'&&e.params.targetId===targetId)||
     (e.sessionId===sessionId&&e.method==='Inspector.targetCrashed')){
   report.crashed=true;report.crashEvent={method:e.method,...e.params};save();
  }
  if(e.sessionId!==sessionId)return;
  if(e.method==='Runtime.exceptionThrown')report.scriptErrors.push(e.params.exceptionDetails.exception?.className||e.params.exceptionDetails.text);
  if(e.method==='Page.windowOpen')try{report.openedWindowOrigins.push(new URL(e.params.url).origin);}catch{}
  if(e.method==='Media.playerPropertiesChanged')for(const p of e.params.properties){
   if(/decoder|codec|platform|videoTracks|keySystem/i.test(p.name))report.media.push(p);
  }
 });
 await c.send('Runtime.enable',{},sessionId);
 await c.send('Page.enable',{},sessionId);
 await c.send('Inspector.enable',{},sessionId);
 await c.send('Media.enable',{},sessionId);
 await c.send('Target.activateTarget',{targetId});
 report.navigation=await c.send('Page.navigate',{url:report.url},sessionId);
 for(let i=0;i<60&&!report.crashed;i++){
  await new Promise(r=>setTimeout(r,1000));
  try{
   const result=await c.send('Runtime.evaluate',{expression:`({title:document.title,readyState:document.readyState,location:location.origin+location.pathname,bodyTextLength:document.body?.innerText.length||0,videoCount:document.querySelectorAll('video').length,audioCount:document.querySelectorAll('audio').length,wasmAvailable:typeof WebAssembly!=='undefined',encryptedMediaAvailable:typeof navigator.requestMediaKeySystemAccess==='function'})`,returnByValue:true},sessionId);
   report.observations.push({seconds:i+1,...result.result.value});
   if(clickLogin&&i===14){
    const action=await c.send('Runtime.evaluate',{expression:`(()=>{const b=[...document.querySelectorAll('button')].find(b=>/^(登录|登入|Sign In)$/i.test(b.innerText.trim()));if(!b)return {clicked:false};b.click();return {clicked:true,label:b.innerText.trim()};})()`,returnByValue:true,userGesture:true},sessionId);
    report.loginEntry=action.result.value;
   }
  }catch(e){report.observations.push({seconds:i+1,error:String(e)});if(report.crashed)break;}
  save();
 }
 if(!report.crashed){const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);fs.writeFileSync(output.replace(/\.json$/,'.png'),Buffer.from(shot.data,'base64'));report.screenshot=path.basename(output.replace(/\.json$/,'.png'));}
 report.complete=true;
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({...report,observations:report.observations.slice(-2)}));
}
