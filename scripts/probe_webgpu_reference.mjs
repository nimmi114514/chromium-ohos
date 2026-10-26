// Reference run in a fresh, disposable Edge profile; never use a user's profile.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'chromium158-webgpu-reference-'));
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end(fs.readFileSync(path.join(root,'tests/webgpu/functional.html')));});
await new Promise(r=>server.listen(19236,'127.0.0.1',r));
const report={freshDisposableProfile:true};let child,socket;
try{
 try{await fetch('http://127.0.0.1:19224/json/version',{signal:AbortSignal.timeout(300)});throw Error('Reference port already in use');}catch(e){if(e.message==='Reference port already in use')throw e;}
 child=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--no-first-run','--no-default-browser-check','--user-data-dir='+profile,'--remote-debugging-address=127.0.0.1','--remote-debugging-port=19224','about:blank'],{stdio:'ignore'});
 let version;
 for(let i=0;i<50;i++){try{version=await(await fetch('http://127.0.0.1:19224/json/version',{signal:AbortSignal.timeout(500)})).json();break;}catch{await new Promise(r=>setTimeout(r,200));}}
 if(!version)throw Error('Reference browser endpoint unavailable');report.version=version.Browser;
 socket=new WebSocket(version.webSocketDebuggerUrl);const pending=new Map();let id=0;
 socket.addEventListener('message',({data})=>{const r=JSON.parse(data),p=pending.get(r.id);if(p){clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result);}});
 await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true});});
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject,timer:setTimeout(()=>{pending.delete(n);reject(Error('Timeout: '+method));},20000)});socket.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));});
 const {targetId}=await send('Target.createTarget',{url:'http://127.0.0.1:19236/webgpu'}),{sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 const evaluate=async expression=>(await send('Runtime.evaluate',{expression,returnByValue:true},sessionId)).result.value;
 for(let i=0;i<30;i++){if(await evaluate("typeof runWebGPUVerification==='function'"))break;await new Promise(r=>setTimeout(r,100));}
 await evaluate('runWebGPUVerification();true');
 for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,1000));report.results=await evaluate('webgpuReport');if(report.results?.done)break;}
 await send('Browser.close');
}catch(e){report.error=String(e);}
finally{
 socket?.close();if(child&&child.exitCode===null){await new Promise(r=>setTimeout(r,2000));if(child.exitCode===null)child.kill();}
 await new Promise(r=>server.close(r));try{fs.rmSync(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});report.profileRemoved=true;}catch{report.profileRemoved=false;}
 fs.writeFileSync(path.join(root,'reports/native089-webgpu-reference-edge.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
