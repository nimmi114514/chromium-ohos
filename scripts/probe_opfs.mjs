// Exercise the File System Access path used by website storage, without login.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {connect} from './local_cdp.mjs';

const root = path.resolve(import.meta.dirname, '..');
const label = process.argv[2] || 'opfs-regression';
if (!/^[a-z0-9-]+$/.test(label)) throw Error('Invalid report label');
const html = '<!doctype html><meta charset="utf-8"><title>文件存储兼容性检查</title>' +
  '<style>body{font:20px sans-serif;background:#eef3fa;min-height:20000px}</style>' +
  '<h1>文件存储兼容性检查</h1><p>检查网页私有存储和鼠标中键滚动。</p>';
const server = http.createServer((_, response) => {
  response.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
  response.end(html);
});
await new Promise(resolve => server.listen(19235, '127.0.0.1', resolve));
const report = {label, passed:false, cases:[]};
let c;
const targets = [], contexts = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function storageCases() {
  const results = [];
  const check = (name, passed) => {
    results.push({name, passed});
    if (!passed) throw Error(name);
  };
  const storage = await navigator.storage.getDirectory();
  const name = 'ohos-regression-' + crypto.randomUUID();
  const dir = await storage.getDirectoryHandle(name, {create:true});
  try {
    const file = await dir.getFileHandle('data.json', {create:true});
    let writer = await file.createWritable();
    await writer.write('original');
    await writer.close();
    check('create-write-close-read', await (await file.getFile()).text() === 'original');
    writer = await file.createWritable({keepExistingData:true});
    await writer.seek(8);
    await writer.write('-updated');
    await writer.close();
    check('keep-existing-data', await (await file.getFile()).text() === 'original-updated');
    writer = await file.createWritable({keepExistingData:true});
    await writer.truncate(4);
    await writer.close();
    check('truncate', await (await file.getFile()).text() === 'orig');
    writer = await file.createWritable();
    await writer.write('discarded');
    await writer.abort();
    check('abort-preserves-original', await (await file.getFile()).text() === 'orig');
    const first = await file.createWritable();
    const second = await file.createWritable();
    await first.write('first');
    await second.write('second');
    await first.close();
    await second.close();
    check('concurrent-siloed-writers', await (await file.getFile()).text() === 'second');
    const exclusive = await file.createWritable({mode:'exclusive'});
    let rejected = false;
    try {
      const unexpected = await file.createWritable({mode:'exclusive'});
      await unexpected.abort();
    } catch (error) {
      rejected = error.name === 'NoModificationAllowedError';
    } finally {
      await exclusive.abort();
    }
    check('exclusive-lock-contention', rejected);
    for (const child of ['a', 'b']) {
      const subdir = await dir.getDirectoryHandle(child, {create:true});
      const nested = await subdir.getFileHandle('same-name.json', {create:true});
      const stream = await nested.createWritable();
      await stream.write(child);
      await stream.close();
    }
    for (const child of ['a', 'b']) {
      const subdir = await dir.getDirectoryHandle(child);
      const nested = await subdir.getFileHandle('same-name.json');
      check('nested-path-isolation-' + child, await (await nested.getFile()).text() === child);
    }
    for (let i = 0; i < 20; ++i) {
      const stream = await file.createWritable({keepExistingData:i % 2 === 0});
      await stream.write('round-' + i);
      await stream.close();
      check('repeat-write-' + i, await (await file.getFile()).text() === 'round-' + i);
    }
    const workerSource = 'onmessage=async({data})=>{try{' +
      'const root=await navigator.storage.getDirectory();' +
      'const dir=await root.getDirectoryHandle(data);' +
      'const file=await dir.getFileHandle("worker.json",{create:true});' +
      'const writer=await file.createWritable();await writer.write("worker");' +
      'await writer.close();postMessage({passed:await(await file.getFile()).text()==="worker"});' +
      '}catch(e){postMessage({passed:false,error:String(e)})}}';
    const workerUrl = URL.createObjectURL(new Blob([workerSource], {type:'text/javascript'}));
    const worker = new Worker(workerUrl);
    try {
      const result = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(Error('Worker timed out')), 10000);
        worker.onmessage = ({data}) => {clearTimeout(timeout); resolve(data);};
        worker.onerror = event => {clearTimeout(timeout); reject(Error(event.message));};
        worker.postMessage(name);
      });
      check('dedicated-worker-write', result.passed);
    } finally {
      worker.terminate();
      URL.revokeObjectURL(workerUrl);
    }
    return results;
  } finally {
    await storage.removeEntry(name, {recursive:true});
  }
}

try {
  c = await connect();
  report.browserPid = c.ownPid;
  const {browserContextId} = await c.send('Target.createBrowserContext');
  contexts.push(browserContextId);
  for (const mode of ['regular', 'incognito']) {
    const {targetId} = await c.send('Target.createTarget', {
      url:'http://127.0.0.1:19235/opfs',
      ...(mode === 'incognito' ? {browserContextId} : {}),
    });
    targets.push(targetId);
    const {sessionId} = await c.send('Target.attachToTarget', {targetId, flatten:true});
    await c.send('Page.enable', {}, sessionId);
    await c.send('Target.activateTarget', {targetId});
    await delay(1000);
    const evaluated = await c.send('Runtime.evaluate', {
      expression:'(' + storageCases.toString() + ')()',
      awaitPromise:true, returnByValue:true,
    }, sessionId);
    if (evaluated.exceptionDetails) throw Error(mode + ': ' + JSON.stringify(evaluated.exceptionDetails));
    if (!Array.isArray(evaluated.result.value)) throw Error('Missing OPFS result');
    report.cases.push(...evaluated.result.value.map(item => ({mode, ...item})));
    if (mode === 'regular') {
      await c.send('Input.dispatchMouseEvent', {
        type:'mousePressed', x:400, y:250, button:'middle', buttons:4, clickCount:1,
      }, sessionId);
      await c.send('Input.dispatchMouseEvent', {
        type:'mouseReleased', x:400, y:250, button:'middle', buttons:0, clickCount:1,
      }, sessionId);
      await c.send('Input.dispatchMouseEvent', {type:'mouseMoved', x:400, y:450}, sessionId);
      await delay(1500);
      const scrolled = await c.send('Runtime.evaluate', {expression:'scrollY', returnByValue:true}, sessionId);
      await c.send('Input.dispatchKeyEvent', {type:'keyDown', key:'Escape', code:'Escape', windowsVirtualKeyCode:27}, sessionId);
      await c.send('Input.dispatchKeyEvent', {type:'keyUp', key:'Escape', code:'Escape', windowsVirtualKeyCode:27}, sessionId);
      report.cases.push({name:'middle-click-autoscroll', passed:scrolled.result.value > 0,
        scrollY:scrolled.result.value});
    }
  }
  report.passed = report.cases.length > 1 && report.cases.every(item => item.passed);
} catch (error) {
  report.error = String(error);
} finally {
  if (c) {
    for (const targetId of targets) await c.send('Target.closeTarget', {targetId}).catch(() => {});
    for (const browserContextId of contexts) await c.send('Target.disposeBrowserContext', {browserContextId}).catch(() => {});
    c.close();
  }
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
  fs.writeFileSync(path.join(root, 'reports', label + '.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report));
if (!report.passed) process.exitCode = 1;
