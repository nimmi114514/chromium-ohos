// Public WebGPU samples, in one anonymous context owned exclusively by this run.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const output=path.resolve(import.meta.dirname,'../reports',label+'.json');
const report={label,passed:false,anonymousContext:true,cases:[],servedByLocalMirror:process.argv.includes('--mirror')};
let server;
if(report.servedByLocalMirror){
 const cache=new Map();report.mirroredResources=[];
 server=http.createServer(async(req,res)=>{
  try{
   const url=new URL(req.url,'http://127.0.0.1');if(!url.pathname.startsWith('/webgpu-samples/')){res.writeHead(404);res.end();return;}
   const source='https://webgpu.github.io'+url.pathname+url.search;
   if(!cache.has(source)){const response=await fetch(source,{signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('HTTP '+response.status);cache.set(source,{type:response.headers.get('content-type'),bytes:Buffer.from(await response.arrayBuffer())});report.mirroredResources.push(source);}
   const resource=cache.get(source);res.writeHead(200,{'Content-Type':resource.type||'application/octet-stream'});res.end(resource.bytes);
  }catch(e){report.mirrorErrors??=[];report.mirrorErrors.push(String(e));res.writeHead(502);res.end('Sample resource unavailable');}
 });
 await new Promise(r=>server.listen(19235,'127.0.0.1',r));
}
let c,targetId,browserContextId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',browserContextId,newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 let current;
 c.onEvent(e=>{
  if(e.sessionId!==sessionId||!current)return;
  if(e.method==='Runtime.exceptionThrown')current.scriptErrors.push(e.params.exceptionDetails.exception?.description||e.params.exceptionDetails.text);
  if(e.method==='Inspector.targetCrashed')current.rendererCrashed=true;
 });
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Inspector.enable',{},sessionId);
 const evaluate=async expression=>{const result=await c.send('Runtime.evaluate',{expression,returnByValue:true},sessionId);if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
 for(const sample of ['helloTriangle','rotatingCube','computeBoids']){
  current={sample,url:'https://webgpu.github.io/webgpu-samples/sample/'+sample+'/',scriptErrors:[],rendererCrashed:false};report.cases.push(current);
  const testUrl=report.servedByLocalMirror?current.url.replace('https://webgpu.github.io','http://127.0.0.1:19235'):current.url;
  await c.send('Page.navigate',{url:testUrl},sessionId);await c.send('Target.activateTarget',{targetId});
  for(let i=0;i<30;i++){
   await new Promise(r=>setTimeout(r,1000));
   current.page=await evaluate(`(()=>{const source=document.querySelector('canvas');if(!source||source.width<1||source.height<1)return {ready:false,title:document.title};const r=source.getBoundingClientRect();return {ready:true,canvasWidth:source.width,canvasHeight:source.height,rect:{x:r.x,y:r.y,width:r.width,height:r.height},viewport:{width:innerWidth,height:innerHeight},visibility:document.visibilityState,title:document.title};})()`);
   fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
   if(current.page.ready||current.scriptErrors.length||current.rendererCrashed)break;
  }
  if(current.page.ready){
   await new Promise(r=>setTimeout(r,8000));
   current.frames=[];
   for(let frame=0;frame<2;frame++){
    current.page.visibility=await evaluate('document.visibilityState');
    const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);
    const filename=label+'-'+sample+'-'+frame+'.png';
    fs.writeFileSync(path.join(path.dirname(output),filename),Buffer.from(shot.data,'base64'));current.frames.push(filename);
    await new Promise(r=>setTimeout(r,500));
   }
  }
  current.needsCompositorPixelVerification=!!current.frames?.length;
  current.passed=false;
 }
 report.passed=report.cases.length===3&&report.cases.every(x=>x.passed);
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}if(browserContextId)try{await c.send('Target.disposeBrowserContext',{browserContextId});}catch{}c.close();}
 if(server)await new Promise(r=>server.close(r));
 fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
