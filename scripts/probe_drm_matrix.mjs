// Compare EME capabilities in owned regular and off-the-record test targets.
// Do not inspect existing tabs, cookies, certificates, or account information.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'reports',label+'.json');
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>DRM capability verification</title><p>DRM capability verification</p>');});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,capabilityQueriesOnly:true,productionLicensesOrAccountsUsed:false,contexts:[]};let c,targetId,browserContextId;
try{
 c=await connect();report.browserPid=c.ownPid;
 for(const mode of ['regular','off-the-record']){
  if(mode==='off-the-record')({browserContextId}=await c.send('Target.createBrowserContext'));
  ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/drm',background:true,...(browserContextId?{browserContextId}:{})}));
  const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
  await c.send('Runtime.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);
  const context={mode,results:[],rendererCrashed:false};report.contexts.push(context);
  const unsubscribe=c.onEvent(e=>{if(e.sessionId===sessionId&&e.method==='Inspector.targetCrashed')context.rendererCrashed=true;});
  let ready=false;
  for(let i=0;i<50;i++){
   const state=await c.send('Runtime.evaluate',{expression:"location.href==='http://127.0.0.1:19235/drm' && document.readyState==='complete' && document.title==='DRM capability verification'",returnByValue:true},sessionId);
   if(state.result.value===true){ready=true;break;}
   await new Promise(r=>setTimeout(r,200));
  }
  if(!ready)throw Error('Owned DRM matrix document did not finish navigation');
  const result=await c.send('Runtime.evaluate',{expression:`(async()=>{
   const result=[];
   const media=[{name:'aac',audioCapabilities:[{contentType:'audio/mp4; codecs="mp4a.40.2"'}]},{name:'avc',videoCapabilities:[{contentType:'video/mp4; codecs="avc1.42E01E"'}]},{name:'hevc',videoCapabilities:[{contentType:'video/mp4; codecs="hvc1.1.6.L93.B0"'}]}];
   for(const keySystem of ['org.w3.clearkey','com.wiseplay.drm','com.widevine.alpha','com.microsoft.playready','com.apple.fps'])for(const type of media){
    const {name,...capabilities}=type;
    try{const access=await Promise.race([navigator.requestMediaKeySystemAccess(keySystem,[{initDataTypes:['cenc'],...capabilities,sessionTypes:['temporary'],persistentState:'optional',distinctiveIdentifier:'optional'}]),new Promise((_,j)=>setTimeout(()=>j(Error('Capability timeout')),5000))]);result.push({keySystem,media:name,supported:true,configuration:access.getConfiguration()});}
    catch(e){result.push({keySystem,media:name,supported:false,error:e.name,message:e.message});}
   }
   return {secureContext:isSecureContext,results:result};
  })()`,awaitPromise:true,returnByValue:true},sessionId);
  if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);
  Object.assign(context,result.result.value);unsubscribe();
  await c.send('Target.closeTarget',{targetId});targetId=undefined;
  if(browserContextId){await c.send('Target.disposeBrowserContext',{browserContextId});browserContextId=undefined;}
  fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
 }
 if(process.argv.includes('--histograms'))report.histograms=await c.send('Browser.getHistograms',{query:'Media.EME',delta:false});
 report.complete=true;
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 server.closeAllConnections();await new Promise(r=>server.close(r));fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
