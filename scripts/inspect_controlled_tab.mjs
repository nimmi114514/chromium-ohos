import fs from 'node:fs';
import {connect} from './local_cdp.mjs';
const [statePath, imagePath] = process.argv.slice(2);
const state = JSON.parse(fs.readFileSync(statePath,'utf8'));
const c = await connect();
try {
  await c.send('Target.activateTarget', {targetId:state.targetId});
  const window = await c.send('Browser.getWindowForTarget', {targetId:state.targetId});
  const {sessionId} = await c.send('Target.attachToTarget',{targetId:state.targetId,flatten:true});
  const result = await c.send('Runtime.evaluate',{expression:`(() => {
    if (!location.href.startsWith('data:text/html;base64,')) return {controlled:false};
    const r = document.querySelector('button').getBoundingClientRect();
    return {controlled:true,buttonBounds:{x:r.x,y:r.y,width:r.width,height:r.height},hasFocus:document.hasFocus(),visibility:document.visibilityState};
  })()`,returnByValue:true},sessionId);
  if (!result.result.value.controlled) throw new Error('Target is no longer the controlled page');
  if (imagePath) {
    const screenshot = await c.send('Page.captureScreenshot',{format:'png'},sessionId);
    fs.writeFileSync(imagePath,Buffer.from(screenshot.data,'base64'));
  }
  console.log(JSON.stringify({window,...result.result.value}));
  await c.send('Target.detachFromTarget',{sessionId});
} finally {c.close();}
