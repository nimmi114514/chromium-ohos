// This server and browser target contain only generated test content.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {connect} from './local_cdp.mjs';
const [reportPath, videoPath] = process.argv.slice(2);
const html = `<!doctype html><meta charset="utf-8"><title>CHROMIUM_TEST_WEB</title>
<h1>Chromium 158 自动功能测试</h1><input id="input"><button id="button">CHROMIUM_TEST_BUTTON</button>
<pre id="result"></pre><canvas id="canvas" width="100" height="60"></canvas>
<script>
window.testResults = {};
async function test(name, body){try{const v=await body();testResults[name]={passed:v===true};}catch(e){testResults[name]={passed:false,error:e.name+': '+e.message};}}
window.runTests = async () => {
 await test('javascript_dom',()=>document.querySelector('h1').textContent.includes('自动'));
 await test('canvas_pixels',()=>{const c=canvas.getContext('2d');c.fillStyle='#00ff00';c.fillRect(0,0,20,20);return c.getImageData(2,2,1,1).data[1]===255;});
 await test('webgl_pixels',()=>{const c=document.createElement('canvas');c.width=16;c.height=16;const gl=c.getContext('webgl');if(!gl)throw new Error('WebGL context unavailable');gl.clearColor(0,1,0,1);gl.clear(gl.COLOR_BUFFER_BIT);const p=new Uint8Array(4);gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);return p[1]===255 && p[3]===255;});
 await test('webgl2_context',()=>!!document.createElement('canvas').getContext('webgl2'));
 await test('web_crypto',async()=>{const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode('abc'));return Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('')==='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';});
 await test('battery_status',async()=>{if(!navigator.getBattery)throw new Error('Battery API unavailable');const b=await Promise.race([navigator.getBattery(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Battery API timed out')),5000))]);return typeof b.charging==='boolean' && b.level>=0 && b.level<=1;});
 await test('local_storage',()=>{localStorage.setItem('chromium158-test','ok');const ok=localStorage.getItem('chromium158-test')==='ok';localStorage.removeItem('chromium158-test');return ok;});
 await test('session_storage',()=>{sessionStorage.setItem('chromium158-test','ok');const ok=sessionStorage.getItem('chromium158-test')==='ok';sessionStorage.removeItem('chromium158-test');return ok;});
 await test('indexed_db',()=>new Promise((resolve,reject)=>{const o=indexedDB.open('chromium158-test',1);o.onupgradeneeded=()=>o.result.createObjectStore('items');o.onerror=()=>reject(o.error);o.onsuccess=()=>{const db=o.result,t=db.transaction('items','readwrite');t.objectStore('items').put('ok','key');t.oncomplete=()=>{const q=db.transaction('items').objectStore('items').get('key');q.onsuccess=()=>{const ok=q.result==='ok';db.close();const d=indexedDB.deleteDatabase('chromium158-test');d.onsuccess=()=>resolve(ok);d.onerror=()=>reject(d.error);};q.onerror=()=>reject(q.error);};t.onerror=()=>reject(t.error);};}));
 await test('worker',()=>new Promise((resolve,reject)=>{const u=URL.createObjectURL(new Blob(['onmessage=e=>postMessage(e.data+1)'],{type:'text/javascript'}));const w=new Worker(u);w.onmessage=e=>{w.terminate();URL.revokeObjectURL(u);resolve(e.data===42);};w.onerror=reject;w.postMessage(41);}));
 await test('fetch',async()=>{const r=await fetch('/api');return r.ok && (await r.json()).controlled===true;});
 await test('cache_storage',async()=>{const c=await caches.open('chromium158-test');await c.put('/cache-test',new Response('ok'));const r=await c.match('/cache-test');const ok=await r.text()==='ok';await caches.delete('chromium158-test');return ok;});
 await test('service_worker',async()=>{const r=await navigator.serviceWorker.register('/sw.js',{scope:'/test-scope/'});await r.unregister();return true;});
 await test('webassembly',async()=>{if(typeof WebAssembly==='undefined')throw new Error('WebAssembly API unavailable');const b=new Uint8Array([0,97,115,109,1,0,0,0]);return (await WebAssembly.instantiate(b)).instance instanceof WebAssembly.Instance;});
 await test('video_decode',()=>new Promise((resolve,reject)=>{const v=document.createElement('video');v.muted=true;v.src='/bear.webm';document.body.append(v);let timer=setTimeout(()=>{v.remove();reject(new Error('Video playback timed out'));},10000);v.onerror=()=>{clearTimeout(timer);reject(new Error('Video decode error '+v.error.code));};v.ontimeupdate=()=>{if(v.currentTime>0.2){clearTimeout(timer);v.pause();const c=document.createElement('canvas');c.width=16;c.height=16;c.getContext('2d').drawImage(v,0,0,16,16);const pixels=c.getContext('2d').getImageData(0,0,16,16).data;v.remove();resolve(v.videoWidth>0 && pixels.some((x,i)=>i%4!==3 && x>0));}};v.play().catch(reject);}));
 document.querySelector('#button').onclick=()=>{testResults.pointer_event={passed:true};};
 return testResults;
};
</script>`;
const server = http.createServer((req,res)=>{
 if(req.url==='/bear.webm'){res.writeHead(200,{'Content-Type':'video/webm','Content-Length':fs.statSync(videoPath).size});fs.createReadStream(videoPath).pipe(res);}
 else if(req.url==='/api'){res.writeHead(200,{'Content-Type':'application/json'});res.end('{"controlled":true}');}
 else if(req.url==='/sw.js'){res.writeHead(200,{'Content-Type':'application/javascript'});res.end('self.addEventListener("install",()=>self.skipWaiting());');}
 else {res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(19233,'127.0.0.1',resolve);});
let c,targetId;
const report={browser:null,origin:'http://127.0.0.1:19233',complete:false,results:{}};
try {
 c=await connect();report.browser=c.version;report.browserPid=c.ownPid;
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Page.enable',{},sessionId);
 await c.send('Page.navigate',{url:report.origin+'/test'},sessionId);
 await new Promise(r=>setTimeout(r,1500));
 const result=await c.send('Runtime.evaluate',{expression:'window.runTests()',awaitPromise:true,returnByValue:true},sessionId);
 if(result.exceptionDetails)throw new Error(result.exceptionDetails.text);
 report.results=result.result.value;
 await c.send('Runtime.evaluate',{expression:'document.querySelector("#input").focus()'},sessionId);
 await c.send('Input.insertText',{text:'CHROMIUM_TEST_INPUT'},sessionId);
 const input=await c.send('Runtime.evaluate',{expression:'document.querySelector("#input").value === "CHROMIUM_TEST_INPUT"',returnByValue:true},sessionId);
 report.results.renderer_text_input={passed:input.result.value===true,nativeImeVerified:false};
 await c.send('Page.navigate',{url:report.origin+'/second'},sessionId);
 await new Promise(r=>setTimeout(r,700));
 const history=await c.send('Page.getNavigationHistory',{},sessionId);
 const first=history.entries.find(x=>x.url===report.origin+'/test');
 await c.send('Page.navigateToHistoryEntry',{entryId:first.id},sessionId);
 await new Promise(r=>setTimeout(r,700));
 const back=await c.send('Runtime.evaluate',{expression:'location.pathname === "/test"',returnByValue:true},sessionId);
 report.results.navigation_back={passed:back.result.value===true};
 report.complete=true;report.allPassed=Object.values(report.results).every(r=>r.passed===true);fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
} catch(error){report.error=error.message;fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));process.exitCode=1;}
finally {if(c&&targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c?.close();server.close();}
