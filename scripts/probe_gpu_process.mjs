// Verify process isolation and recovery using only a target created here.
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';

const label = process.argv[2] || 'gpu-process';
if (!/^[a-z0-9-]+$/.test(label)) throw Error('Invalid report label');
const output = path.resolve(import.meta.dirname, '../reports', label + '.json');
const report = {label, passed: false, cases: []};
const save = () => fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const html = '<!doctype html><meta charset="utf-8"><title>GPU process recovery</title>' +
  '<canvas width="128" height="128"></canvas><script>' +
  'window.framesDrawn=0;const c=document.querySelector("canvas");' +
  'window.gl=c.getContext("webgl2");' +
  'function draw(){if(gl){gl.clearColor(.2,.6,.8,1);gl.clear(gl.COLOR_BUFFER_BIT);}' +
  'framesDrawn++;requestAnimationFrame(draw);}draw();</script>';
const url = 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
let c, targetId;
try {
  c = await connect();
  report.browserPid = c.ownPid;
  const before = await c.send('SystemInfo.getProcessInfo');
  const {gpu} = await c.send('SystemInfo.getInfo');
  report.before = {gpuPids: before.processInfo.filter(p => p.type === 'GPU').map(p => p.id),
    inProcessGpu: gpu.auxAttributes.inProcessGpu};
  report.cases.push({name: 'gpu-is-separate', passed: report.before.inProcessGpu === false &&
    report.before.gpuPids.length > 0 && report.before.gpuPids.every(pid => pid !== c.ownPid)});
  if (!report.cases.at(-1).passed) throw Error('Refusing GPU crash test without process isolation');
  ({targetId} = await c.send('Target.createTarget', {url}));
  const {sessionId} = await c.send('Target.attachToTarget', {targetId, flatten: true});
  await c.send('Page.enable', {}, sessionId);
  await c.send('Target.activateTarget', {targetId});
  const evaluate = async expression => {
    const r = await c.send('Runtime.evaluate', {expression, returnByValue: true}, sessionId);
    if (r.exceptionDetails) throw Error(r.exceptionDetails.text);
    return r.result.value;
  };
  await delay(1000);
  report.initialFrames = await evaluate('framesDrawn');
  await c.send('Browser.crashGpuProcess');
  report.crashRequested = true;
  save();
  for (let i = 0; i < 40; ++i) {
    await delay(500);
    const processes = await c.send('SystemInfo.getProcessInfo');
    const pids = processes.processInfo.filter(p => p.type === 'GPU').map(p => p.id);
    if (pids.some(pid => !report.before.gpuPids.includes(pid))) {
      report.after = {gpuPids: pids, browserAlive: processes.processInfo.some(
        p => p.type === 'browser' && p.id === report.browserPid)};
      break;
    }
  }
  report.cases.push({name: 'gpu-restarted-browser-survived', passed: !!report.after?.browserAlive});
  await c.send('Page.reload', {}, sessionId);
  await delay(2000);
  report.render = await evaluate('(() => {const p=new Uint8Array(4);' +
    'if(gl){gl.clearColor(.2,.6,.8,1);gl.clear(gl.COLOR_BUFFER_BIT);' +
    'gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);}' +
    'return {frames:framesDrawn,webgl:!!gl,pixel:[...p]};})()');
  report.cases.push({name: 'webgl-renders-after-recovery', passed: report.render.webgl &&
    report.render.frames > 10 && report.render.pixel.every((v, i) =>
      Math.abs(v - [51, 153, 204, 255][i]) <= 3)});
  report.passed = report.cases.every(test => test.passed);
} catch (error) {
  report.error = String(error);
} finally {
  if (c) {
    if (targetId) await c.send('Target.closeTarget', {targetId}).catch(() => {});
    c.close();
  }
  save();
  console.log(JSON.stringify(report));
}
if (!report.passed) process.exitCode = 1;
