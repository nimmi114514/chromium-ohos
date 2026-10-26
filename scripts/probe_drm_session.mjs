// Test native EME lifecycle and invalid-license rejection. No license service
// is contacted; no private CDM request/response contents are recorded.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'reports',label+'.json');
const xml=fs.readFileSync(path.join(root,'tests/drm/wiseplay-sample.mpd'),'utf8');
const pssh=xml.match(/<cenc:pssh>([^<]+)<\/cenc:pssh>/)[1].trim();
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>DRM session verification</title><p>DRM session verification</p>');});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,licenseServiceContacted:false,payloadsRecorded:false,rendererCrashed:false};let c,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/session',background:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});await c.send('Runtime.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);
 c.onEvent(e=>{if(e.sessionId===sessionId&&e.method==='Inspector.targetCrashed')report.rendererCrashed=true;});
 const expression=`(async()=>{
  const report={done:false,passed:false,robustness:[],cycles:[]};window.drmSessionReport=report;
  const timeout=(p,name)=>Promise.race([p,new Promise((_,j)=>setTimeout(()=>j(Error(name+' timeout')),7000))]);
  const access=robustness=>navigator.requestMediaKeySystemAccess('com.wiseplay.drm',[{initDataTypes:['cenc'],videoCapabilities:[{contentType:'video/mp4; codecs="avc1.42E01E"',robustness}],sessionTypes:['temporary'],persistentState:'optional',distinctiveIdentifier:'optional'}]);
  try{
   for(const robustness of ['','SW_SECURE_CRYPTO','SW_SECURE_DECODE','HW_SECURE_CRYPTO','HW_SECURE_DECODE','HW_SECURE_ALL']){try{await timeout(access(robustness),'access');report.robustness.push({robustness,supported:true});}catch(e){report.robustness.push({robustness,supported:false,error:e.name});}}
   for(let i=0;i<3;i++){
    const result={cycle:i};report.cycles.push(result);const a=await timeout(access(''),'access');const keys=await timeout(a.createMediaKeys(),'createMediaKeys');result.keysCreated=true;const session=keys.createSession();
    const message=new Promise(r=>session.addEventListener('message',e=>r({type:e.messageType,bytes:e.message.byteLength}),{once:true}));
    await timeout(session.generateRequest('cenc',Uint8Array.from(atob(${JSON.stringify(pssh)}),x=>x.charCodeAt(0))),'generateRequest');result.request=await timeout(message,'message');
    try{await timeout(session.update(new Uint8Array([0,1,2,3])),'invalid license');result.invalidLicenseRejected=false;}catch(e){result.invalidLicenseRejected=e.message!=='invalid license timeout';result.rejection={name:e.name,message:e.message};}
    const closeOrder=[];session.closed.then(()=>closeOrder.push('closed'));
    await timeout(session.close().then(()=>closeOrder.push('close')),'close');result.closedReason=await timeout(session.closed,'closed event');result.closed=true;result.closeOrder=closeOrder;
    await timeout(session.close(),'repeated close');result.repeatedCloseResolved=true;
    try{await timeout(session.update(new Uint8Array([0,1,2,3])),'update after close');result.updateAfterCloseRejected=false;}catch(e){result.updateAfterCloseRejected=e.name==='InvalidStateError';}
    result.passed=result.request.type==='license-request'&&result.request.bytes>0&&result.invalidLicenseRejected&&result.closed&&closeOrder.join(',')==='closed,close'&&result.repeatedCloseResolved&&result.updateAfterCloseRejected;
   }
   report.passed=report.cycles.length===3&&report.cycles.every(x=>x.passed);
  }catch(e){report.error=String(e);}finally{report.done=true;}
 })();true`;
 let ready=false;
 for(let i=0;i<50;i++){
  const state=await c.send('Runtime.evaluate',{expression:"location.href==='http://127.0.0.1:19235/session' && document.readyState==='complete' && document.title==='DRM session verification'",returnByValue:true},sessionId);
  if(state.result.value===true){ready=true;break;}
  await new Promise(r=>setTimeout(r,200));
 }
 if(!ready)throw Error('Owned DRM test document did not finish navigation');
 const started=await c.send('Runtime.evaluate',{expression},sessionId);
 if(started.exceptionDetails)throw Error(started.exceptionDetails.exception?.description||started.exceptionDetails.text);
 for(let i=0;i<80;i++){await new Promise(r=>setTimeout(r,1000));const result=await c.send('Runtime.evaluate',{expression:'drmSessionReport',returnByValue:true},sessionId);report.results=result.result.value;fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');if(report.results?.done||report.rendererCrashed)break;}
 report.complete=!!report.results?.done;report.passed=report.complete&&report.results.passed&&!report.rendererCrashed;
}catch(e){report.error=String(e);report.passed=false;}
finally{if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});report.ownedTargetClosed=true;}catch(e){report.cleanupError=String(e);}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));}
