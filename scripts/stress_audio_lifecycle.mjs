// Silent WebAudio lifecycle regression, including the five-second native close delay.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath]=process.argv.slice(2);
const c=await connect();
const report={browser:c.version,browserPid:c.ownPid,batches:[],passed:false,nativeCloseDelaySeconds:5};
let targetId,sessionId;
try {
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true}));
 ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
 await c.send('Page.enable',{},sessionId);
 await c.send('Page.navigate',{url:'data:text/html,<title>CHROMIUM_TEST_AUDIO_LIFECYCLE</title><h1>Audio lifecycle regression</h1>'},sessionId);
 for(let batch=0;batch<8;batch++) {
  const result=await c.send('Runtime.evaluate',{expression:`(async()=>{
   let closed=0;
   for(let i=0;i<5;i++) {
    const context=new AudioContext();
    const gain=context.createGain();gain.gain.value=0;gain.connect(context.destination);
    const oscillator=context.createOscillator();oscillator.connect(gain);oscillator.start();
    await context.resume();await new Promise(r=>setTimeout(r,100));
    oscillator.stop();oscillator.disconnect();gain.disconnect();await context.close();closed++;
   }
   return {closed};
  })()`,awaitPromise:true,userGesture:true,returnByValue:true},sessionId);
  if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  // Wait past AudioManagerBase's five-second idle output-stream destruction.
  await new Promise(r=>setTimeout(r,7000));
  const {processInfo}=await c.send('SystemInfo.getProcessInfo');
  const sameBrowser=processInfo.some(p=>p.type==='browser' && p.id===report.browserPid);
  if(!sameBrowser)throw new Error('Browser process changed during audio teardown');
  report.batches.push({batch,contextsClosed:result.result.value.closed,waitedAfterCloseMs:7000,browserAlive:true});
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report.batches.at(-1)));
 }
 await c.send('Target.closeTarget',{targetId});targetId=null;
 await new Promise(r=>setTimeout(r,15000));
 const {processInfo}=await c.send('SystemInfo.getProcessInfo');
 report.passed=processInfo.some(p=>p.type==='browser' && p.id===report.browserPid);
 report.waitAfterTabCloseMs=15000;
} catch(error){report.error=error.message;process.exitCode=1;}
finally {
 fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 if(targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();
}
