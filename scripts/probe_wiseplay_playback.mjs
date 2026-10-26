// Use only the DRM vendor's public demonstration stream/license and an owned
// local-origin regular-profile target. Never save license/challenge contents.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const root=path.resolve(import.meta.dirname,'..'),assets=path.join(root,'tests/drm'),out=path.join(root,'reports',label+'.json');
const officialDta=process.argv.includes('--official-dta-license-only');
const source=JSON.parse(fs.readFileSync(path.join(assets,officialDta?'wiseplay-dta-source.json':'wiseplay-sample-source.json')));
const files=new Set(source.tracks.flatMap(x=>[x.init,...x.segments.map(s=>s.file)]));
const report={label,vendorPublicSample:true,provider:source.provider,licensePayloadsRecorded:false,licenseRequestContentType:'application/json',steps:[],transport:[],mediaProperties:[],mediaEvents:[],mediaMessages:[],rendererCrashed:false,testProcessPid:process.pid};
async function forwardLicense(body){
 if(process.argv.includes('--wsl-transport')){
  return await new Promise((resolve,reject)=>{
   const child=spawn('wsl.exe',['--distribution','Ubuntu','--exec','python3','/mnt/d/chromium/chromium158-ohos/scripts/wiseplay_license_transport.py','--size',String(body.length),'--provider',officialDta?'official-dta':'ezdrm'],{stdio:['pipe','pipe','pipe']});const chunks=[];let diagnostic='';
   report.transportProcessPid=child.pid;
   const timer=setTimeout(()=>{child.kill();reject(Error('Public sample transport process timeout'));},30000);
   child.stdout.on('data',b=>chunks.push(b));child.stderr.on('data',b=>diagnostic+=b.toString());child.on('error',reject);
   child.on('close',code=>{clearTimeout(timer);const output=Buffer.concat(chunks);if(code||output.length<4){reject(Error('Public sample transport process failed'));return;}if(diagnostic)report.transportWarningObserved=true;resolve({status:output.readUInt32BE(0),bytes:output.subarray(4)});});child.stdin.end(body);
  });
 }
 const response=await fetch(source.license,{method:'POST',headers:{'Content-Type':'application/json'},body,signal:AbortSignal.timeout(20000)});return {status:response.status,bytes:Buffer.from(await response.arrayBuffer())};
}
const server=http.createServer(async(req,res)=>{
 try{
  if(req.url==='/license'&&req.method==='POST'){
   const transfer={phase:'receiving',declaredBytes:Number(req.headers['content-length']||0)};report.transport.push(transfer);
   const chunks=[];let length=0;for await(const b of req){length+=b.length;if(length>1024*1024)throw Error('Oversized sample request');chunks.push(b);}
   transfer.phase='request-ready';transfer.requestBytes=length;
   const {status,bytes}=await forwardLicense(Buffer.concat(chunks));Object.assign(transfer,{phase:'completed',status,responseBytes:bytes.length});
   // Record only bounded numeric server error codes; never response contents.
   try{
    const data=JSON.parse(bytes.toString());for(const key of ['code','errorCode','resultCode'])if(typeof data[key]==='number')transfer[key]=data[key];transfer.hasCertificateChain=!!data.certificateChain;
    const message=String(data.msg||data.message||data.error||'').toLowerCase();
    if(message)transfer.rejectionCategory=/白名单|whitelist|white list|\bip\b/.test(message)?'network-allowlist':/证书|certificate/.test(message)?'certificate':/权限|授权|auth|permission/.test(message)?'authorization':/参数|parameter|request/.test(message)?'request-validation':'unclassified';
   }catch{}
   res.writeHead(status,{'Content-Type':'application/octet-stream'});res.end(bytes);return;
  }
  const file=req.url.startsWith('/media/')?req.url.slice(7):null;
  if(file&&files.has(file)){const bytes=fs.readFileSync(path.join(assets,file));res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':bytes.length});res.end(bytes);return;}
  if(req.url==='/source.json'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(source));return;}
  if(req.url==='/sample.mpd'){res.writeHead(200,{'Content-Type':'application/dash+xml'});res.end(fs.readFileSync(path.join(assets,'wiseplay-sample.mpd')));return;}
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync(path.join(assets,'player.html')));
 }catch(e){report.transport.push({error:String(e)});res.writeHead(502);res.end('Public sample transport failed');}
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));let c,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 const query=new URLSearchParams();if(process.argv.includes('--audio')||process.argv.includes('--audio-only'))query.set('audio','');if(process.argv.includes('--audio-only'))query.set('audio-only','');if(process.argv.includes('--no-license'))query.set('no-license','');if(process.argv.includes('--exercise-wait'))query.set('exercise-wait','');if(officialDta)query.set('license-only','');
 const targetOptions=(process.argv.includes('--no-license')||officialDta)?{background:!process.argv.includes('--foreground')}:{newWindow:true};
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/wiseplay?'+query,...targetOptions}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 c.onEvent(e=>{if(e.sessionId!==sessionId)return;if(e.method==='Inspector.targetCrashed')report.rendererCrashed=true;
  if(e.method==='Media.playerPropertiesChanged')for(const p of e.params.properties)if(/decoder|encrypt|codec|buffer|track/i.test(p.name))report.mediaProperties.push(p);
  if(e.method==='Media.playerMessagesLogged')for(const p of e.params.messages)if(p.message.includes('WisePlayAudio:'))report.mediaMessages.push(p);
  if(e.method==='Media.playerEventsAdded')for(const p of e.params.events){try{const data=JSON.parse(p.value);if(Object.keys(data).some(k=>/error|pipeline_state|buffering|audio|video/i.test(k)))report.mediaEvents.push(data);}catch{}}
 });
 await c.send('Runtime.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);await c.send('Media.enable',{},sessionId);if(!process.argv.includes('--no-license')||process.argv.includes('--foreground'))await c.send('Page.bringToFront',{},sessionId);
 const evaluate=async expression=>{const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,userGesture:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
 for(let i=0;i<30;i++){if(await evaluate("typeof runDrmVerification==='function'"))break;await new Promise(r=>setTimeout(r,200));}
 await evaluate('runDrmVerification();true');
 for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,1000));report.results=await evaluate('drmReport');fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');if(report.results.done||report.rendererCrashed)break;}
 report.passed=!!report.results?.passed&&!report.rendererCrashed;report.complete=!!report.results?.done;
}catch(e){report.error=String(e);report.passed=false;}
finally{if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});report.ownedTargetClosed=true;}catch(e){report.cleanupError=String(e);}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));}
