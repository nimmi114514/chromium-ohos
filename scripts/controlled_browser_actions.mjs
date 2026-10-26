// Download/PDF/network checks use generated fixtures and an isolated profile.
import fs from 'node:fs';
import http from 'node:http';
import {connect} from './local_cdp.mjs';
const [reportPath,pdfPath] = process.argv.slice(2);
const origin='http://127.0.0.1:19234';
const server=http.createServer((req,res)=>{
  if(req.url==='/probe.pdf'){res.writeHead(200,{'Content-Type':'application/pdf'});res.end(fs.readFileSync(pdfPath));}
  else if(req.url==='/download'){res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Disposition':'attachment; filename="chromium158-regression.txt"'});res.end('CHROMIUM_TEST_DOWNLOAD\n');}
  else {res.writeHead(200,{'Content-Type':'text/html'});res.end('<title>CHROMIUM_TEST_ACTIONS</title><h1>CHROMIUM_TEST_ACTIONS</h1>');}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(19234,'127.0.0.1',resolve);});
let c,targetId,sessionId,browserContextId;
const report={complete:false,results:{}};
async function check(name,fn){try{report.results[name]=await fn();}catch(error){report.results[name]={passed:false,error:error.message};}fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify({name,...report.results[name]}));}
try {
  c=await connect();report.browser=c.version;report.browserPid=c.ownPid;
  ({browserContextId}=await c.send('Target.createBrowserContext',{disposeOnDetach:true}));
  report.isolatedProfile=true;
  ({targetId}=await c.send('Target.createTarget',{url:'about:blank',browserContextId,newWindow:true}));
  ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
  await c.send('Page.enable',{},sessionId);
  await check('https_navigation',async()=>{
    const navigation=await c.send('Page.navigate',{url:'https://example.com/'},sessionId);
    await new Promise(r=>setTimeout(r,2500));
    const state=await c.send('Runtime.evaluate',{expression:'({expectedOrigin:location.origin==="https://example.com",bodyLoaded:!!document.body?.childElementCount})',returnByValue:true},sessionId);
    return {passed:!navigation.errorText && state.result.value.expectedOrigin && state.result.value.bodyLoaded,navigationError:navigation.errorText || null};
  });
  await check('file_download',async()=>{
    await c.send('Browser.setDownloadBehavior',{behavior:'allow',browserContextId,downloadPath:'/data/storage/el2/base/cache/chromium158-regression',eventsEnabled:true});
    let guid,completed=false;
    const unsubscribe=c.onEvent(e=>{
      if(e.method==='Browser.downloadWillBegin' && e.params.url===origin+'/download')guid=e.params.guid;
      if(e.method==='Browser.downloadProgress' && e.params.guid===guid && e.params.state==='completed')completed=true;
    });
    try {
      await c.send('Page.navigate',{url:origin+'/download'},sessionId);
      for(let i=0;i<100 && !completed;i++)await new Promise(r=>setTimeout(r,100));
      return {passed:completed,downloadStarted:!!guid,isolatedProfile:true,fixtureBytes:23};
    } finally {unsubscribe();}
  });
  await check('pdf_viewer',async()=>{
    const navigation=await c.send('Page.navigate',{url:origin+'/probe.pdf'},sessionId);
    await new Promise(r=>setTimeout(r,4000));
    const tree=await c.send('Page.getFrameTree',{},sessionId);
    const state=await c.send('Runtime.evaluate',{expression:`(()=>{
      const all=[];function scan(root){for(const e of root.querySelectorAll('*')){all.push(e);if(e.shadowRoot)scan(e.shadowRoot);}}scan(document);
      return {pdfEmbed:all.some(e=>e.matches('embed[type="application/pdf"]')),pdfViewer:all.some(e=>e.localName==='pdf-viewer'),errorPage:location.protocol==='chrome-error:',elementCount:all.length,customTags:[...new Set(all.map(e=>e.localName).filter(t=>t.includes('-')))]};
    })()`,returnByValue:true},sessionId);
    const screenshot=await c.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);
    report.pdfScreenshot=reportPath.replace(/\.json$/,'.png');fs.writeFileSync(report.pdfScreenshot,Buffer.from(screenshot.data,'base64'));
    const viewerFrame=(tree.frameTree.childFrames || []).some(f=>f.frame.url.startsWith('chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/'));
    return {passed:!navigation.errorText && !state.result.value.errorPage && (state.result.value.pdfEmbed || state.result.value.pdfViewer || viewerFrame),mimeType:tree.frameTree.frame.mimeType,...state.result.value,viewerFrame};
  });
  report.complete=true;report.allPassed=Object.values(report.results).every(r=>r.passed===true);
} catch(error){report.error=error.message;process.exitCode=1;}
finally {
  if(browserContextId)await c?.send('Target.disposeBrowserContext',{browserContextId}).catch(()=>{});
  c?.close();server.close();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
}
