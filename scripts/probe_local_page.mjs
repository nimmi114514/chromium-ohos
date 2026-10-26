// Probe only a newly created, controlled test tab. Never enumerate user tabs.
import fs from 'node:fs';

const [mode, statePath, fixturePath, portArg] = process.argv.slice(2);
const devtoolsPort = Number(portArg || process.env.CHROMIUM158_DEVTOOLS_PORT || 19222);
if (!Number.isInteger(devtoolsPort) || devtoolsPort < 1024 || devtoolsPort > 65535) throw new Error("Invalid diagnostic port");
if (!['open', 'read', 'close'].includes(mode) || !statePath) {
  throw new Error('Usage: node probe_local_page.mjs open|read|close state.json [fixture.html]');
}
const versionResponse = await fetch(`http://127.0.0.1:${devtoolsPort}/json/version`, {
  signal: AbortSignal.timeout(5000),
});
if (!versionResponse.ok) throw new Error('Local diagnostic endpoint unavailable');
const version = await versionResponse.json();
const endpoint = new URL(version.webSocketDebuggerUrl);
if (!['127.0.0.1', 'localhost'].includes(endpoint.hostname)) {
  throw new Error('Expected a localhost diagnostic endpoint');
}
const socket = new WebSocket(endpoint);
const pending = new Map();
let nextId = 1;
socket.addEventListener('message', ({data}) => {
  const message = JSON.parse(data);
  const request = pending.get(message.id);
  if (!request) return;
  pending.delete(message.id);
  clearTimeout(request.timer);
  if (message.error) request.reject(new Error('CDP command failed: ' + message.error.code));
  else request.resolve(message.result);
});
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, {once: true});
  socket.addEventListener('error', () => reject(new Error('Diagnostic socket failed')), {once: true});
});
function send(method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error('Timed out: ' + method));
    }, 15000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));
  });
}
try {
  if (mode === 'close') {
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    await send('Target.closeTarget', {targetId: state.targetId});
    fs.unlinkSync(statePath);
    console.log(JSON.stringify({controlledTabClosed: true}));
  } else {
    let state;
    if (mode === 'open') {
      if (!fixturePath) throw new Error('Controlled HTML fixture required');
      const html = fs.readFileSync(fixturePath);
      const {targetId} = await send('Target.createTarget', {
        url: 'data:text/html;base64,' + html.toString('base64'),
      });
      state = {targetId};
      fs.writeFileSync(statePath, JSON.stringify(state));
    } else {
      state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    }
    const {sessionId} = await send('Target.attachToTarget', {...state, flatten: true});
    await send('Runtime.enable', {}, sessionId);
    const expression = `(() => {
      if (!location.href.startsWith('data:text/html;base64,')) return {controlledPage: false};
      const text = document.body?.innerText || '';
      const input = document.querySelector('input');
      return {
        controlledPage: text.includes('CHROMIUM_INPUT_TEST') || !!document.querySelector('[placeholder="CHROMIUM_INPUT_TEST"]'),
        readyState: document.readyState,
        javascript: text.includes('JAVASCRIPT_OK'),
        canvas: text.includes('CANVAS_PIXELS_OK'),
        frame: text.includes('FRAME_OK'),
        click: text.includes('CLICK_OK'),
        expectedInput: input?.value === 'chromium-native-input-045',
        inputBounds: input ? (() => {const r = input.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})() : null,
        devicePixelRatio,
        innerWidth,
        innerHeight
      };
    })()`;
    let result;
    for (let attempt = 0; attempt < (mode === 'open' ? 20 : 1); attempt++) {
      const response = await send('Runtime.evaluate', {expression, returnByValue: true}, sessionId);
      if (response.exceptionDetails) throw new Error('Controlled page evaluation failed');
      result = response.result.value;
      if (result?.javascript && result?.frame) break;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    console.log(JSON.stringify(result));
    await send('Target.detachFromTarget', {sessionId});
  }
} finally {
  socket.close();
}
