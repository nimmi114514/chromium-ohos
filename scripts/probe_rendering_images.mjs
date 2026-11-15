// Owned image/alpha fixtures and full-browser screenshots for native UI review.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..'),label=process.argv[2]||'rendering-images';
if(!/^[a-z0-9-]+$/.test(label))throw Error('Invalid label');
const output=path.join(root,'reports',label+'.json');
const html=`<!doctype html><meta charset="utf-8"><title>图像与透明度检查</title><style>body{background:#eee;color:#222;font:20px sans-serif;margin:24px}.cards{display:flex;gap:24px;flex-wrap:wrap}.card{padding:16px;background:white;border-radius:16px;box-shadow:0 2px 6px #0003}.card img,.card canvas{display:block;width:128px;height:128px;background:repeating-conic-gradient(#eee 0 25%,white 0 50%) 0/16px 16px}pre{font:16px monospace;white-space:pre-wrap}</style><h2>图像、透明度和缓存复用</h2><div class="cards" id="cards"></div><pre id="result"></pre><script>
window.imageReport={done:false,passed:false,cases:[],errors:[]};addEventListener('error',e=>imageReport.errors.push(e.message));
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function image(src){const i=new Image;i.src=src;await i.decode();return i;}
function card(title,node){const c=document.createElement('div');c.className='card';const p=document.createElement('p');p.textContent=title;c.append(p,node);cards.append(c);}
function sample(i,x,y){const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d');g.fillStyle='white';g.fillRect(0,0,128,128);g.drawImage(i,0,0,128,128);return [...g.getImageData(x,y,1,1).data];}
function check(name,actual,expected,tolerance=3){const passed=actual.every((v,i)=>Math.abs(v-expected[i])<=tolerance);imageReport.cases.push({name,passed,actual,expected});}
(async()=>{try{
 const source=document.createElement('canvas');source.width=source.height=128;const g=source.getContext('2d');g.fillStyle='rgba(255,0,0,.5)';g.fillRect(32,32,64,64);
 const png=await image(source.toDataURL('image/png'));card('PNG 半透明',png);check('png-transparent-corner',sample(png,4,4),[255,255,255,255]);check('png-half-alpha',sample(png,64,64),[255,127,127,255]);
 const svg=await image('data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><circle cx="64" cy="64" r="50" fill="rgb(20,180,70)"/></svg>'));card('SVG 透明圆形',svg);check('svg-corner',sample(svg,4,4),[255,255,255,255]);check('svg-color',sample(svg,64,64),[20,180,70,255]);
 g.clearRect(0,0,128,128);g.fillStyle='rgb(51,153,204)';g.fillRect(0,0,128,128);
 for(const type of ['image/jpeg','image/webp']){const i=await image(source.toDataURL(type,.95));card(type,i);check(type,sample(i,64,64),[51,153,204,255],6);}
 const bitmap=await createImageBitmap(png);const c=document.createElement('canvas');c.width=c.height=128;c.getContext('2d').drawImage(bitmap,0,0);card('ImageBitmap 透明',c);check('imagebitmap-alpha',sample(c,64,64),[255,127,127,255]);bitmap.close();
 const glCanvas=document.createElement('canvas');glCanvas.width=glCanvas.height=128;const gl=glCanvas.getContext('webgl2',{alpha:true,premultipliedAlpha:true,preserveDrawingBuffer:true});if(!gl)throw Error('WebGL2 unavailable');gl.clearColor(.25,0,.25,.5);gl.clear(gl.COLOR_BUFFER_BIT);card('WebGL2 透明',glCanvas);check('webgl-alpha',sample(glCanvas,64,64),[191,127,191,255],4);
 const favicon=document.createElement('canvas');favicon.width=favicon.height=32;const f=favicon.getContext('2d');f.fillStyle='#8b4acf';f.beginPath();f.arc(16,16,15,0,Math.PI*2);f.fill();f.fillStyle='white';f.fillRect(8,13,16,6);const link=document.createElement('link');link.rel='icon';link.type='image/png';link.href=favicon.toDataURL();document.head.append(link);
 for(let n=0;n<5;n++){cards.style.transform='translateX('+(n%2)+'px)';await new Promise(requestAnimationFrame);}check('png-after-repaint',sample(png,64,64),[255,127,127,255]);const cached=await image(png.src);card('PNG 缓存复用',cached);check('png-cache-alpha',sample(cached,64,64),[255,127,127,255]);
 imageReport.passed=imageReport.cases.every(x=>x.passed)&&!imageReport.errors.length;
}catch(e){imageReport.error=String(e);}finally{imageReport.done=true;result.textContent=JSON.stringify(imageReport,null,2);}})();
</script>`;
const server=http.createServer((_,r)=>{r.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});r.end(html);});await new Promise(r=>server.listen(19235,'127.0.0.1',r));
const report={label,passed:false};let c,targetId;
const hdc='C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
function systemShot(suffix){const remote='/data/local/tmp/'+label+suffix+'.jpeg';execFileSync(hdc,['-t','6YT0226706000164','shell','snapshot_display','-f',remote],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','file','recv',remote,path.join(root,'reports',label+suffix+'.jpeg')],{timeout:15000});execFileSync(hdc,['-t','6YT0226706000164','shell','rm',remote],{timeout:15000});}
try{c=await connect();report.browserPid=c.ownPid;systemShot('-cold-ui');({targetId}=await c.send('Target.createTarget',{url:'http://127.0.0.1:19235/images'}));const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});await c.send('Runtime.enable',{},sessionId);await c.send('Page.enable',{},sessionId);await c.send('Target.activateTarget',{targetId});for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,250));const r=await c.send('Runtime.evaluate',{expression:'window.imageReport',returnByValue:true},sessionId);report.images=r.result.value;if(report.images?.done)break;}await new Promise(r=>setTimeout(r,1500));systemShot('-images-ui');const shot=await c.send('Page.captureScreenshot',{format:'png'},sessionId);fs.writeFileSync(output.replace(/\.json$/,'.png'),Buffer.from(shot.data,'base64'));report.passed=!!report.images?.passed;}catch(e){report.error=String(e);}finally{if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});}catch{}c.close();}server.closeAllConnections();await new Promise(r=>server.close(r));fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));}
