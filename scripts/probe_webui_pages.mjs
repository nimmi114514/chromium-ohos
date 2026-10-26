// Inspect rendering and errors in newly created internal-page targets only.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath] = process.argv.slice(2);
const requested = new Set(process.argv.slice(3));
const c = await connect();
const report={browser:c.version,browserPid:c.ownPid,pages:[],complete:false};
let targetId,sessionId,current;
const unsubscribe=c.onEvent(e=>{
  if(!current || e.sessionId!==sessionId)return;
  if(e.method==='Runtime.exceptionThrown')current.exceptions.push(e.params.exceptionDetails.exception?.description || e.params.exceptionDetails.text);
});
try {
  ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true}));
  ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
  await c.send('Page.enable',{},sessionId);await c.send('Runtime.enable',{},sessionId);
  for(const [page,tags] of [
    ['newtab',['ntp-app','ntp-third-party-app']],
    ['downloads',['downloads-manager']],['history',['history-app']],
    ['bookmarks',['bookmarks-app']],['extensions',['extensions-manager']],
    ['management',['management-ui']],['policy',['policy-table']],
    ['discards',['discards-main']],
  ]) {
    if(requested.size && !requested.has(page))continue;
    current={page,exceptions:[]};report.pages.push(current);
    current.navigation=await c.send('Page.navigate',{url:'chrome://'+page+'/'},sessionId);
    await new Promise(r=>setTimeout(r,2500));
    const result=await c.send('Runtime.evaluate',{expression:`(()=>{
      const all=[];function scan(root){for(const e of root.querySelectorAll('*')){all.push(e);if(e.shadowRoot)scan(e.shadowRoot);}}scan(document);
      const tags=${JSON.stringify(tags)};
      return {isErrorPage:location.protocol==='chrome-error:',internalDebugGate:location.hostname==='internal-debug-pages-disabled',internalPage:location.protocol==='chrome:',readyState:document.readyState,bodyChildren:document.body?.childElementCount||0,expectedComponents:tags.map(tag=>({tag,registered:!!customElements.get(tag),instances:all.filter(e=>e.localName===tag).map(e=>({children:e.shadowRoot?.childElementCount || e.childElementCount,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))}))};
    })()`,returnByValue:true},sessionId);
    current.dom=result.result.value;
    current.componentPresent=current.dom?.expectedComponents.some(e=>e.registered && e.instances.length>0) || false;
    current.passed=!current.navigation.errorText && !current.dom?.isErrorPage && current.componentPresent && !current.exceptions.length;
    if(current.dom?.internalDebugGate){current.passed=null;current.status='Requires enabling internal debug pages in Chromium158';}
    fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
    console.log(JSON.stringify({page,passed:current.passed,componentPresent:current.componentPresent,exceptionCount:current.exceptions.length}));
  }
  report.complete=true;
} catch(error){report.error=error.message;process.exitCode=1;}
finally {fs.writeFileSync(reportPath,JSON.stringify(report,null,2));unsubscribe();if(targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();}
