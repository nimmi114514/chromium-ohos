import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath] = process.argv.slice(2);
const c = await connect();
const report = {browser:c.version,browserPid:c.ownPid,managed:null};
let targetId;
try {
 ({targetId} = await c.send('Target.createTarget',{url:'about:blank'}));
 const {sessionId} = await c.send('Target.attachToTarget',{targetId,flatten:true});
 await c.send('Page.enable',{},sessionId);
 report.managementNavigation = await c.send('Page.navigate',{url:'chrome://management/'},sessionId);
 await new Promise(r=>setTimeout(r,2000));
 const data = await c.send('Runtime.evaluate',{expression:`(async () => {
  if (!location.href.startsWith('chrome://management')) return {controlled:false,isErrorPage:location.protocol==='chrome-error:'};
  const {sendWithPromise}=await import('chrome://resources/js/cr.js');
  const d=await sendWithPromise('getContextualManagedData');
  return {controlled:true,managed:d.managed,hasExtensionManager:!!d.extensionReportingSubtitle};
 })()`,awaitPromise:true,returnByValue:true},sessionId);
 report.management = data.result.value;
 report.managementEvaluationFailed = !!data.exceptionDetails;
 if (data.exceptionDetails) report.managementEvaluationError = data.exceptionDetails.exception?.description || data.exceptionDetails.text;
 if (report.management?.controlled) report.managed=report.management.managed;
 await c.send('Page.navigate',{url:'chrome://policy/'},sessionId);
 await new Promise(r=>setTimeout(r,2000));
 const rows = await c.send('Runtime.evaluate',{expression:`(() => {
  if (location.origin !== 'chrome://policy') return {controlled:false};
  const all=[];function walk(root){for(const e of root.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}}walk(document);
  const names=all.filter(e=>e.localName==='policy-row' && e.policy?.value !== undefined).map(e=>e.policy?.name || e.policyName || e.name || '').filter(Boolean);
  return {controlled:true,policyNames:names,rowCount:all.filter(e=>e.localName==='policy-row').length};
 })()`,returnByValue:true},sessionId);
 report.policy = rows.result.value;
 fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
} finally {if(targetId) await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();}
