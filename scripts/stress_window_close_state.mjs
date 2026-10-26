// Close only our generated windows while native minimize notifications are pending.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath]=process.argv.slice(2),c=await connect();
const report={browserPid:c.ownPid,iterations:[],passed:false};
const owned=new Set();let anchor;
try{
 ({targetId:anchor}=await c.send('Target.createTarget',{url:'data:text/html,<title>CHROMIUM_TEST_WINDOW_ANCHOR</title><h1>CHROMIUM_TEST_WINDOW_ANCHOR</h1>',newWindow:true}));owned.add(anchor);
 for(let i=0;i<6;i++){
  const {targetId}=await c.send('Target.createTarget',{url:'data:text/html,<title>CHROMIUM_TEST_WINDOW_CLOSE</title><h1>CHROMIUM_TEST_WINDOW_CLOSE</h1>',newWindow:true});owned.add(targetId);
  const {windowId}=await c.send('Browser.getWindowForTarget',{targetId});
  await c.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'minimized'}});
  const closed=await c.send('Target.closeTarget',{targetId});owned.delete(targetId);
  await new Promise(r=>setTimeout(r,900));
  const {processInfo}=await c.send('SystemInfo.getProcessInfo');
  const alive=processInfo.some(p=>p.type==='browser'&&p.id===c.ownPid);
  report.iterations.push({index:i,minimizeRequested:true,closed:closed.success,browserAlive:alive});
  if(!alive||!closed.success)throw new Error('Window close regression failed');
 }
 report.passed=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
 for(const targetId of owned)await c.send('Target.closeTarget',{targetId}).catch(()=>{});
 await new Promise(r=>setTimeout(r,2000));
 c.close();fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
