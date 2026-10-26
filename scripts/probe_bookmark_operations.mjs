// Create/update/move/read/remove only a temporary folder created by this test.
import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [reportPath]=process.argv.slice(2);
const c=await connect();
const report={browser:c.version,browserPid:c.ownPid,passed:false};
let targetId,sessionId;
try {
  ({targetId}=await c.send('Target.createTarget',{url:'about:blank',newWindow:true}));
  ({sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true}));
  await c.send('Page.enable',{},sessionId);
  await c.send('Page.navigate',{url:'chrome://bookmarks/'},sessionId);
  await new Promise(r=>setTimeout(r,2000));
  const result=await c.send('Runtime.evaluate',{expression:`(async()=>{
    if(location.origin!=='chrome://bookmarks')throw new Error('Unexpected test origin');
    const call=(method,...args)=>new Promise((resolve,reject)=>chrome.bookmarks[method](...args,result=>{const error=chrome.runtime?.lastError;if(error)reject(new Error(error.message));else resolve(result);}));
    let root;
    try {
      root=await call('create',{title:'CHROMIUM_TEST_BOOKMARK_'+Date.now()});
      window.__chromiumTestBookmarkRoot={id:root.id,title:root.title};
      const a=await call('create',{parentId:root.id,title:'CHROMIUM_TEST_A'});
      const b=await call('create',{parentId:root.id,title:'CHROMIUM_TEST_B'});
      const item=await call('create',{parentId:a.id,title:'CHROMIUM_TEST_ITEM',url:'https://example.com/#chromium158-regression'});
      await call('update',item.id,{title:'CHROMIUM_TEST_UPDATED'});
      await call('move',item.id,{parentId:b.id});
      const [read]=await call('get',item.id);
      return {passed:read.title==='CHROMIUM_TEST_UPDATED' && read.parentId===b.id && read.url==='https://example.com/#chromium158-regression',created:true,updated:true,moved:true,read:true};
    } finally {if(root){await call('removeTree',root.id);window.__chromiumTestBookmarkRoot=null;}}
  })()`,awaitPromise:true,returnByValue:true},sessionId);
  if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  Object.assign(report,result.result.value);
  const cleanup=await c.send('Runtime.evaluate',{expression:'window.__chromiumTestBookmarkRoot===null',returnByValue:true},sessionId);
  report.cleanupVerified=cleanup.result.value===true;report.passed=report.passed && report.cleanupVerified;
} catch(error){report.error=error.message;process.exitCode=1;}
finally {
  if(sessionId)await c.send('Runtime.evaluate',{expression:`(async()=>{
    const root=window.__chromiumTestBookmarkRoot;if(!root)return;
    const [current]=await chrome.bookmarks.get(root.id);
    if(current.title===root.title && current.title.startsWith('CHROMIUM_TEST_BOOKMARK_'))await chrome.bookmarks.removeTree(root.id);
  })()`,awaitPromise:true},sessionId).catch(()=>{});
  if(targetId)await c.send('Target.closeTarget',{targetId}).catch(()=>{});c.close();
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
