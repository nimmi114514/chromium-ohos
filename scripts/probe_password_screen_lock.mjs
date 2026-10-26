// Reads only the screen-lock setting in an owned, temporary browser context.
// Never lists, reads, creates, exports, or submits saved passwords.
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {connect} from './local_cdp.mjs';
const root=path.resolve(import.meta.dirname,'..');
const label=process.argv[2];if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const report={scope:'Temporary context; password data not accessed',passed:false,exceptions:[]};
let c,contextId,targetId;
try{
 c=await connect();report.browserPid=c.ownPid;
 ({browserContextId:contextId}=await c.send('Target.createBrowserContext'));
 ({targetId}=await c.send('Target.createTarget',{url:'chrome://password-manager/settings',browserContextId:contextId}));report.ownedTargetId=targetId;
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Runtime.enable',{},sessionId);await c.send('Page.bringToFront',{},sessionId);
 c.onEvent(e=>{if(e.sessionId===sessionId&&e.method==='Runtime.exceptionThrown')report.exceptions.push(e.params.exceptionDetails.text);});
 const evaluate=async expression=>{const r=await c.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value;};
 const read=`(()=>{const all=[];function scan(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)scan(e.shadowRoot);}}scan(document);const s=all.find(e=>e.localName==='settings-section');const t=all.find(e=>e.id==='biometricAuthenticationToggle');return {ready:!!s,visible:!!t&&t.getBoundingClientRect().height>0,label:t?.label||'',checked:t?.checked??null,prefValue:s?.prefs?.password_manager?.biometric_authentication_filling?.value??null};})()`;
 for(let i=0;i<35;i++){report.setting=await evaluate(read);if(report.setting.visible)break;await new Promise(r=>setTimeout(r,300));}
 if(!report.setting.visible)throw Error('Screen-lock toggle missing');
 if(process.argv.includes('--cancel-auth')){
  await evaluate(`(()=>{window.screenLockVerification={pending:true};import('chrome://password-manager/password_manager_proxy.js').then(m=>m.PasswordManagerImpl.getInstance().switchBiometricAuthBeforeFillingState()).then(success=>{window.screenLockVerification={pending:false,success};},()=>{window.screenLockVerification={pending:false,rejected:true};});return true;})()`);
  await new Promise(r=>setTimeout(r,1800));
  const hdc=process.platform==='win32'?'C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe':'/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
  execFileSync(hdc,['-t','6YT0226706000164','shell','uitest','uiInput','keyEvent','Back'],{timeout:10000,stdio:'pipe'});
  for(let i=0;i<30;i++){report.authentication=await evaluate('window.screenLockVerification');if(!report.authentication.pending)break;await new Promise(r=>setTimeout(r,300));}
  report.after=await evaluate(read);
  if(report.authentication.pending||report.authentication.success!==false||report.after.prefValue!==report.setting.prefValue)throw Error('Canceled authentication did not preserve setting');
 }
 report.passed=!report.exceptions.length;
}catch(e){report.error=String(e);}
finally{
 if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});report.ownedTargetClosed=true;}catch{}if(contextId)try{await c.send('Target.disposeBrowserContext',{browserContextId:contextId});report.temporaryContextClosed=true;}catch{}c.close();}
 fs.writeFileSync(path.join(root,'reports',label+'.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
