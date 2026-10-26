// Exercise only generated content in an isolated context owned by this test.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const root=path.resolve(import.meta.dirname,'..'),output=path.join(root,'reports',label+'.json');
const html=fs.readFileSync(path.join(root,'tests/webgpu/functional.html'));
const server=http.createServer((req,res)=>{
 if(req.url==='/video.mp4'){const bytes=fs.readFileSync(path.join(root,'tests/hdr/assets/avc-sdr.mp4'));res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':bytes.length});res.end(bytes);return;}
 res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);
});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,anonymousContext:true,complete:false,rendererCrashed:false,console:[]};
let c,targetId,browserContextId;
try{
 c=await connect();report.browserPid=c.ownPid;
 const {gpu}=await c.send('SystemInfo.getInfo');report.gpu={devices:gpu.devices,featureStatus:gpu.featureStatus};
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/webgpu'+(process.argv.includes('--rgba')?'?format=rgba8unorm':''),browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 c.onEvent(e=>{
  if((e.method==='Target.targetCrashed'&&e.params.targetId===targetId)||(e.method==='Inspector.targetCrashed'&&e.sessionId===sessionId))report.rendererCrashed=true;
  if(e.sessionId===sessionId&&e.method==='Runtime.consoleAPICalled')report.console.push({type:e.params.type,args:e.params.args.map(x=>x.value??x.description)});
  if(e.sessionId===sessionId&&e.method==='Log.entryAdded')report.console.push(e.params.entry);
 });
 await c.send('Runtime.enable',{},sessionId);await c.send('Log.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Target.activateTarget',{targetId});
 const evaluate=async expression=>{const result=await c.send('Runtime.evaluate',{expression,returnByValue:true},sessionId);if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
 for(let i=0;i<30;i++){if(await evaluate("typeof window.runWebGPUVerification==='function'"))break;await new Promise(r=>setTimeout(r,200));}
 await evaluate('runWebGPUVerification();true');
 for(let i=0;i<100;i++){
  await new Promise(r=>setTimeout(r,1000));report.results=await evaluate('webgpuReport');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
  if(report.results.done||report.rendererCrashed)break;
 }
 if(report.results?.done){const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);fs.writeFileSync(output.replace(/\.json$/,'.png'),Buffer.from(shot.data,'base64'));}
 await evaluate('window.finishWebGPUVerification?.();true');
 report.complete=!!report.results?.done;report.passed=report.complete&&!report.rendererCrashed&&report.results.passed;
}catch(e){report.error=String(e);report.passed=false;}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 await new Promise(r=>server.close(r));fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
