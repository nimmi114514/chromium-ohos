import {connect} from './local_cdp.mjs';
const c = await connect();let targetId;
try {
 ({targetId}=await c.send('Target.createTarget',{url:'chrome://version/'}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await new Promise(r=>setTimeout(r,1000));
 const result=await c.send('Runtime.evaluate',{expression:`(() => {
 const args=document.querySelector('#command_line')?.textContent || '';
 return {hasCommandLine:!!args,logLevel:args.match(/--log-level=(\\d+)/)?.[1] || null,disableLogging:args.includes('--disable-logging'),verbose:args.includes('--v=1'),logging:args.includes('--enable-logging')};
 })()`,returnByValue:true},sessionId);
 console.log(JSON.stringify({ownPid:c.ownPid,...result.result.value}));
} finally {if(targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();}
