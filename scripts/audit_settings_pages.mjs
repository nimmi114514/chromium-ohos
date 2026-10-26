import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath,statePath] = process.argv.slice(2);
const c = await connect();
let current, sessionId;
const report = {browser:c.version, browserPid:c.ownPid, createdTargetOnly:true, pages:[], complete:false, interactionCoverage:false};
const unsubscribe = c.onEvent(message => {
  if (!current || message.sessionId !== sessionId) return;
  if (message.method === 'Runtime.exceptionThrown') {
    const detail = message.params.exceptionDetails;
    current.exceptions.push((detail.exception?.description || detail.text || '').split('\n').slice(0,5));
  }
  if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') {
    const e = message.params.entry;
    current.errors.push({source:e.source, text:e.text.slice(0,700)});
  }
});
try {
  const {targetId} = await c.send('Target.createTarget',{url:'about:blank',newWindow:true});
  fs.writeFileSync(statePath,JSON.stringify({targetId}));
  ({sessionId} = await c.send('Target.attachToTarget',{targetId,flatten:true}));
  await c.send('Runtime.enable',{},sessionId);
  await c.send('Log.enable',{},sessionId);
  await c.send('Page.enable',{},sessionId);
  await c.send('Page.navigate',{url:'chrome://settings/'},sessionId);
  await new Promise(r=>setTimeout(r,2000));
  const discovery = await c.send('Runtime.evaluate',{expression:`(async () => {
    if (location.origin !== 'chrome://settings') throw new Error('Unexpected test origin');
    const {routes} = await import('./settings.js');
    return Object.entries(routes).map(([name,r])=>({name,path:r.path,dialog:!!r.isNavigableDialog}));
  })()`,awaitPromise:true,returnByValue:true},sessionId);
  if (discovery.exceptionDetails || !Array.isArray(discovery.result.value)) throw new Error('Settings route discovery failed: '+(discovery.exceptionDetails?.exception?.description || discovery.exceptionDetails?.text || 'No routes'));
  // Dialogs and routes requiring a user-selected account/site are checked separately.
  const excluded = /signOut|importData|resetProfileSettings|triggeredReset|clearBrowserData|siteDetails/i;
  const skip = r=>r.name==='ADVANCED' || r.dialog || excluded.test(r.path);
  report.skippedRoutes = discovery.result.value.filter(skip).map(r=>({name:r.name,path:r.path,reason:r.name==='ADVANCED'?'Structural route container':'Dialog or site-specific interaction'}));
  const routePaths = [...new Set(discovery.result.value.filter(r=>!skip(r)).map(r=>r.path))];
  const tags = {appearance:'settings-appearance-page-index',languages:'settings-languages-page-index',downloads:'settings-downloads-page',accessibility:'settings-a11y-page-index',system:'settings-system-page',reset:'settings-reset-page'};
  for (const routePath of routePaths) {
    const path = routePath.replace(/^\//,'');
    const tag = tags[path] || null;
    current = {path,tag,exceptions:[],errors:[]};
    report.pages.push(current);
    await c.send('Page.navigate',{url:`chrome://settings/${path}`},sessionId);
    await new Promise(r=>setTimeout(r,2500));
    const expression = `(() => {
      if (location.origin !== 'chrome://settings') return {controlled:false};
      const all=[];
      function walk(root) {for(const e of root.querySelectorAll('*')) {all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}}
      walk(document);
      const visible=e=>{
        if(!e.isConnected || !e.getClientRects().length)return false;
        for(let p=e;p;p=p.parentElement || p.getRootNode()?.host){const s=getComputedStyle(p);if(p.hidden || s.display==='none' || s.visibility==='hidden' || s.visibility==='collapse')return false;}
        const r=e.getBoundingClientRect();return r.width>0 && r.height>0;
      };
      const tag=${JSON.stringify(tag)};
      const candidates=all.filter(e=>tag ? e.localName===tag : e.localName==='settings-main');
      const descendants=e=>{const a=[];function scan(root){for(const n of root.querySelectorAll('*')){a.push(n);if(n.shadowRoot)scan(n.shadowRoot);}}if(e.shadowRoot)scan(e.shadowRoot);scan(e);return a;};
      return {controlled:true,routeMatches:location.pathname===${JSON.stringify(routePath)},readyState:document.readyState,registered:tag?!!customElements.get(tag):null,totalElements:all.length,instances:candidates.map(e=>({connected:e.isConnected,children:e.shadowRoot?.childElementCount||0,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,display:getComputedStyle(e).display,visibleDescendants:descendants(e).filter(visible).length,visibleControls:descendants(e).filter(n=>visible(n) && (n.matches('button,input,select,[role=button],[role=switch]') || n.localName.startsWith('cr-'))).length})),lazyModuleRegistered:!!customElements.get('settings-reset-page')};
    })()`;
    const evaluated = await c.send('Runtime.evaluate',{expression,returnByValue:true},sessionId);
    current.dom = evaluated.result.value;
    if (evaluated.exceptionDetails) current.evaluationException = evaluated.exceptionDetails.text;
    fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
    current.rendered = current.dom?.controlled===true && current.dom.routeMatches && current.dom.instances.some(e=>e.visibleDescendants>0);
    console.log(JSON.stringify({path,rendered:current.rendered,exceptionCount:current.exceptions.length,errorCount:current.errors.length}));
  }
  report.complete = true;
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
  await c.send('Target.detachFromTarget',{sessionId});
} finally {unsubscribe();c.close();}
