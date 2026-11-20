// Real-device regression for OHOS unsafe shared memory and WebGPU buffer mapping.
// Uses an owned loopback page and closes it without modifying the user's tabs.
import {connect} from './local_cdp.mjs';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const label = process.argv[2];
if (!/^[a-z0-9-]+$/.test(label || '')) throw Error('Expected report label');
const pressure = process.argv.includes('--pressure');
const server = http.createServer((request, response) => {
  response.writeHead(200, {'Content-Type': 'text/html'});
  response.end('<!doctype html><title>GPU buffer verification</title><p>GPU buffer mapping verification</p>');
});
await new Promise(resolve => server.listen(19235, '127.0.0.1', resolve));

let connection, targetId, stopEvents;
let tracing = false;
const report = {label, startedAt: new Date().toISOString(), passed: false};
try {
  connection = await connect();
  report.browserPid = connection.ownPid;
  ({targetId} = await connection.send('Target.createTarget', {
    url: 'http://127.0.0.1:19235/buffers',
  }));
  const {sessionId} = await connection.send('Target.attachToTarget', {targetId, flatten: true});
  await connection.send('Target.activateTarget', {targetId});
  await new Promise(resolve => setTimeout(resolve, 500));

  const traceEvents = [];
  let traceResolve;
  const traceDone = new Promise(resolve => traceResolve = resolve);
  stopEvents = connection.onEvent(event => {
    if (event.method === 'Tracing.dataCollected') traceEvents.push(...event.params.value);
    if (event.method === 'Tracing.tracingComplete') traceResolve();
  });
  await connection.send('Tracing.start', {categories: 'ipc', transferMode: 'ReportEvents'});
  tracing = true;
  const expression = `(${async function run(withPressure) {
    const result = {devices: 0, buffers: 0, bytes: 0, errors: [], passed: false};
    const arrays = [];
    try {
      if (withPressure) {
        for (let i = 0; i < 6; i++) {
          const array = new Uint8Array(128 * 1024 * 1024);
          for (let offset = 0; offset < array.length; offset += 4096) array[offset] = 1;
          arrays.push(array);
        }
        result.pressureBytes = arrays.reduce((total, array) => total + array.byteLength, 0);
      }
      for (let round = 0; round < 8; round++) {
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) throw Error('No hardware adapter, round ' + round);
        const device = await adapter.requestDevice();
        result.devices++;
        device.onuncapturederror = event => result.errors.push(event.error.message);
        try {
          for (let batch = 0; batch < 8; batch++) {
            const buffers = [];
            try {
              for (let i = 0; i < 8; i++) {
                const size = [4096, 65536, 1048576, 4194304][i % 4];
                buffers.push(device.createBuffer({size, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST}));
              }
              await Promise.all(buffers.map(buffer => buffer.mapAsync(GPUMapMode.READ)));
              for (const buffer of buffers) {
                result.bytes += buffer.getMappedRange().byteLength;
                buffer.unmap();
                result.buffers++;
              }
            } finally {
              buffers.forEach(buffer => buffer.destroy());
            }
          }
        } finally {
          device.destroy();
        }
      }
      result.passed = result.errors.length === 0;
    } catch (error) {
      result.error = String(error);
    }
    return result;
  }})(${pressure})`;
  const evaluation = await connection.send('Runtime.evaluate', {
    expression, awaitPromise: true, returnByValue: true,
  }, sessionId);
  report.result = evaluation.result?.value;
  report.exception = evaluation.exceptionDetails;
  await connection.send('Tracing.end');
  tracing = false;
  let timer;
  try {
    await Promise.race([traceDone, new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(Error('Trace timeout')), 15000);
    })]);
  } finally {
    clearTimeout(timer);
  }
  const direct = traceEvents.filter(event => event.name === 'OHOS.SharedMemory.CreateUnsafeDirect');
  const {processInfo} = await connection.send('SystemInfo.getProcessInfo');
  report.directUnsafeAllocationEvents = direct.length;
  report.directAllocationProcesses = [...new Set(direct.map(event => event.pid))].map(pid => ({
    pid, type: processInfo.find(process => process.id === pid)?.type || 'unknown',
  }));
  report.passed = !!report.result?.passed && direct.length > 0;
} catch (error) {
  report.error = String(error);
} finally {
  stopEvents?.();
  if (connection) {
    if (tracing) await connection.send('Tracing.end').catch(() => {});
    if (targetId) await connection.send('Target.closeTarget', {targetId}).catch(() => {});
    connection.close();
  }
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
  report.finishedAt = new Date().toISOString();
  fs.writeFileSync(path.join(root, 'reports', label + '.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
}
if (!report.passed) process.exitCode = 1;
