// Check actual system-font fallback and color rasterization on the connected tablet.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..');
const label=process.argv[2]||'ohos-emoji';
if(!/^[a-z0-9-]+$/.test(label))throw Error('Invalid report label');
// The system panda artwork is almost entirely black/white; validate its glyph
// coverage and visible raster pixels rather than requiring chromatic pixels.
const samples=[['face','😀'],['animal','🐼'],['rocket','🚀'],['heart','❤️'],
 ['skin-tone','👍🏽'],['family','👨‍👩‍👧‍👦'],['flag-cn','🇨🇳'],['flag-us','🇺🇸']];
const html='<!doctype html><meta charset="utf-8"><title>Emoji 字体检查 😀</title>'+
 '<style>body{background:white;color:black;font:20px sans-serif}.sample{font:56px sans-serif;margin:12px}</style>'+
 '<h1>Emoji 字体检查</h1>'+samples.map(([id,text])=>`<div><span>${id}: </span><span class="sample" id="${id}">${text}</span></div>`).join('')+
 '<p id="text">中文字体与 English 123</p><canvas id="probe" width="300" height="110"></canvas>';
const server=http.createServer((q,r)=>{r.writeHead(200,{'Content-Type':'text/html;charset=utf-8'});r.end(html);});
await new Promise(r=>server.listen(19235,'127.0.0.1',r));
let c,target;
const report={label,passed:false,cases:[]};
try{
 c=await connect();report.browserPid=c.ownPid;
 ({targetId:target}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/emoji'}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId:target,flatten:true});
 await c.send('Target.activateTarget',{targetId:target});
 await new Promise(r=>setTimeout(r,2000));
 const {result,exceptionDetails}=await c.send('Runtime.evaluate',{expression:`(async()=>{
 await document.fonts.ready;
 const samples=${JSON.stringify(samples)};const c=document.querySelector('canvas'),g=c.getContext('2d',{willReadFrequently:true});
 return samples.flatMap(([id,text])=>['sans-serif','"HMOS Color Emoji", "HMOS Color Emoji Flags"'].map(font=>{
  g.clearRect(0,0,c.width,c.height);g.font='64px '+font;g.fillStyle='#000';g.fillText(text,10,80);
  const d=g.getImageData(0,0,c.width,c.height).data;let visible=0,color=0;
  for(let i=0;i<d.length;i+=4)if(d[i+3]>40){visible++;if(Math.max(d[i],d[i+1],d[i+2])-Math.min(d[i],d[i+1],d[i+2])>25)color++;}
  return {id,font,visiblePixels:visible,colorPixels:color,passed:visible>50&&(id==='animal'||color>20)};
 }));})()`,awaitPromise:true,returnByValue:true},sessionId);
 if(exceptionDetails)throw Error('Canvas probe failed');
 report.cases=result.value;
 await c.send('DOM.enable',{},sessionId);
 await c.send('CSS.enable',{},sessionId);
 const {root:doc}=await c.send('DOM.getDocument',{},sessionId);
 report.domFonts=[];
 for(const [id] of samples){
  const {nodeId}=await c.send('DOM.querySelector',{nodeId:doc.nodeId,selector:'#'+id},sessionId);
  const {fonts}=await c.send('CSS.getPlatformFontsForNode',{nodeId},sessionId);
  report.domFonts.push({id,fonts});
 }
 const {data}=await c.send('Page.captureScreenshot',{format:'png'},sessionId);
 fs.writeFileSync(path.join(root,'reports',label+'.png'),Buffer.from(data,'base64'));
 report.passed=report.cases.every(t=>t.passed)&&report.domFonts.every(t=>t.fonts.some(f=>f.familyName.includes('HMOS Color Emoji')&&f.glyphCount>0));
 console.log(JSON.stringify(report));
}finally{
 if(c){if(target)try{await c.send('Target.closeTarget',{targetId:target});}catch{}c.close();}
 server.closeAllConnections();
 await new Promise(r=>server.close(r));
 fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');
}
if(!report.passed)process.exitCode=1;
