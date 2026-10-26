// Exercise only generated SVG images and frames in a target created by this test.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';

const [reportPath] = process.argv.slice(2);
const c = await connect();
const report = {browser:c.version,browserPid:c.ownPid,iterations:0,svgImages:0,frames:0,passed:false};
let targetId, sessionId;
const unsubscribe = c.onEvent(e=>{
  if(e.sessionId===sessionId && e.method==='Inspector.targetCrashed') report.targetCrashed=true;
});
try {
  ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true}));
  ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
  await c.send('Page.enable',{},sessionId);
  await c.send('Inspector.enable',{},sessionId);
  await c.send('Page.navigate',{url:'data:text/html,<title>CHROMIUM_TEST_SVG_GC</title><h1>SVG finalization regression</h1>'},sessionId);
  for(let iteration=0;iteration<30;iteration++) {
    const result=await c.send('Runtime.evaluate',{expression:`(async()=>{
      const images=[];
      for(let i=0;i<64;i++) {
        const svg='<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><defs><linearGradient id="g"><stop stop-color="red"/><stop offset="1" stop-color="blue"/></linearGradient></defs><rect width="32" height="32" fill="url(#g)"/><text y="16">'+${iteration}+'-'+i+'</text></svg>';
        const image=new Image();image.src=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));
        document.body.append(image);images.push(image);
      }
      await Promise.all(images.map(i=>i.decode()));
      const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;
      for(const image of images){canvas.getContext('2d').drawImage(image,0,0);URL.revokeObjectURL(image.src);image.remove();}
      const frames=[];
      for(let i=0;i<8;i++){const f=document.createElement('iframe');f.srcdoc='<p>CHROMIUM_TEST_FRAME</p>';document.body.append(f);frames.push(f);}
      await new Promise(r=>setTimeout(r,30));
      for(const frame of frames)frame.remove();
      return {images:images.length,frames:frames.length};
    })()`,awaitPromise:true,returnByValue:true},sessionId);
    if(result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    await c.send('HeapProfiler.collectGarbage',{},sessionId);
    report.iterations++;report.svgImages+=result.result.value.images;report.frames+=result.result.value.frames;
    fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
  }
  const result=await c.send('Runtime.evaluate',{expression:'document.title === "CHROMIUM_TEST_SVG_GC"',returnByValue:true},sessionId);
  report.passed=result.result.value===true && !report.targetCrashed;
} catch(error) {report.error=error.message;process.exitCode=1;}
finally {
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  unsubscribe();if(targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();
}
