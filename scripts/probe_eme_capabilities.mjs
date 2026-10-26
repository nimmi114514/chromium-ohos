// Query capabilities only: no account, CDM instance, media license or playback.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const output=path.resolve(import.meta.dirname,'../reports',label+'.json');
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>Media capability check</title><p>Media capability check</p>');});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,capabilityQueriesOnly:true,passed:false,crashed:false};
let c,targetId,browserContextId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/eme',browserContextId,newWindow:true,background:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 c.onEvent(e=>{if((e.method==='Target.targetCrashed'&&e.params.targetId===targetId)||(e.method==='Inspector.targetCrashed'&&e.sessionId===sessionId))report.crashed=true;});
 await c.send('Runtime.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);
 await new Promise(r=>setTimeout(r,700));
 const expression=`(async()=>{
  const keys=['org.w3.clearkey','com.widevine.alpha','com.wiseplay.drm','com.example.unsupported'];
  const results=[];
  for(let round=0;round<3;round++){
   for(const keySystem of keys){
    try{
     const value=await Promise.race([navigator.requestMediaKeySystemAccess(keySystem,[{initDataTypes:['cenc'],audioCapabilities:[{contentType:'audio/mp4; codecs="mp4a.40.2"'}],sessionTypes:['temporary'],persistentState:'optional',distinctiveIdentifier:'optional'}]),new Promise((_,r)=>setTimeout(()=>r(new Error('capability timeout')),4000))]);
     results.push({round,keySystem,supported:true,returnedKeySystem:value.keySystem});
    }catch(e){results.push({round,keySystem,supported:false,error:e.name,message:e.message});}
   }
  }
  return {secureContext:isSecureContext,results};
 })()`;
 const result=await c.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sessionId);
 if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);
 Object.assign(report,result.result.value);
 const rejected=report.results.filter(x=>x.keySystem==='com.widevine.alpha'||x.keySystem==='com.example.unsupported');
 report.passed=report.secureContext&&!report.crashed&&report.results.length===12&&rejected.every(x=>!x.supported&&x.error==='NotSupportedError')&&report.results.every(x=>x.supported||x.error==='NotSupportedError');
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 await new Promise(r=>server.close(r));fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
