// Local test connection. Callers must operate only on their own target IDs.
import {execFileSync} from 'node:child_process';
export async function connect(port = 19222) {
  const response = await fetch(`http://127.0.0.1:${port}/json/version`, {signal: AbortSignal.timeout(5000)});
  if (!response.ok) throw new Error('Local diagnostic endpoint unavailable');
  const version = await response.json();
  const endpoint = new URL(version.webSocketDebuggerUrl);
  if (!['127.0.0.1', 'localhost'].includes(endpoint.hostname)) throw new Error('Expected loopback endpoint');
  const socket = new WebSocket(endpoint);
  const pending = new Map();
  const listeners = new Set();
  let nextId = 1;
  socket.addEventListener('message', ({data}) => {
    const message = JSON.parse(data);
    if (!message.id) {for (const listener of listeners) listener(message); return;}
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    clearTimeout(request.timer);
    if (message.error) request.reject(new Error(`${request.method}: ${message.error.code} ${message.error.message}`));
    else request.resolve(message.result);
  });
  await new Promise((resolve,reject) => {
    socket.addEventListener('open', resolve, {once:true});
    socket.addEventListener('error', () => reject(new Error('Local socket failed')), {once:true});
  });
  const connection = {
    version: version.Browser,
    onEvent(listener) {listeners.add(listener);return () => listeners.delete(listener);},
    send(method, params = {}, sessionId) {
      const id = nextId++;
      return new Promise((resolve,reject) => {
        const timer = setTimeout(() => {pending.delete(id);reject(new Error(`Timed out: ${method}`));},20000);
        pending.set(id,{resolve,reject,timer,method});
        socket.send(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})}));
      });
    },
    close() {socket.close();}
  };
  const hdc = process.platform === 'win32'
    ? 'C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe'
    : '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe';
  const expectedPid = Number(execFileSync(hdc, ['-t','6YT0226706000164','shell','pidof','com.example.ohos.chromium'], {encoding:'utf8',timeout:10000}).trim());
  const {processInfo} = await connection.send('SystemInfo.getProcessInfo');
  if (!Number.isInteger(expectedPid) || expectedPid <= 0 || !processInfo.some(p => p.type === 'browser' && p.id === expectedPid)) {
    socket.close();throw new Error('Diagnostic endpoint does not belong to the intended application process');
  }
  connection.ownPid = expectedPid;
  return connection;
}
