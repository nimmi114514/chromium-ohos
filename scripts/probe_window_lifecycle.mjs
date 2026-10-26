import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath]=process.argv.slice(2);
const c=await connect();
const report={browser:c.version,browserPid:c.ownPid,created:[],closed:[],browserAlive:false};
const targets=[];
try {
 for(let i=0;i<2;i++) {
  const {targetId}=await c.send('Target.createTarget',{url:'data:text/html,<title>CHROMIUM_TEST_WINDOW_'+i+'</title><h1>CHROMIUM_TEST_WINDOW</h1>',newWindow:true});
  targets.push(targetId);
  const {windowId}=await c.send('Browser.getWindowForTarget',{targetId});report.created.push({targetId,windowId});
 }
 await c.send('Target.closeTarget',{targetId:targets.pop()});report.closed.push('secondary');
 await new Promise(r=>setTimeout(r,1500));
 await c.send('Target.getTargetInfo',{targetId:targets[0]});report.anchorStillExists=true;
 const {processInfo}=await c.send('SystemInfo.getProcessInfo');report.browserAlive=processInfo.some(p=>p.type==='browser' && p.id===report.browserPid);
 await c.send('Target.closeTarget',{targetId:targets.pop()});report.closed.push('anchor');
 await new Promise(r=>setTimeout(r,1500));
 await c.send('SystemInfo.getProcessInfo');report.browserAliveAfterTestWindowsClosed=true;
} catch(error){report.error=error.message;process.exitCode=1;}
finally {fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));c.close();}
