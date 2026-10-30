// Exercise the real ArkTS USB adapter against deterministic system-event mocks.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '..');
const sdkRoot = process.platform === 'win32'
  ? 'C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony'
  : '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony';
const ts = require(process.env.OHOS_TYPESCRIPT_JS ||
  path.join(sdkRoot, 'ets/build-tools/ets-loader/node_modules/typescript/lib/typescript.js'));
const source = fs.readFileSync(path.join(process.env.HAP_PROJECT_DIR || path.join(root, '../chromium-2in1-hap'), 'web_engine/src/main/ets/adapter/DeviceAdapter.ets'), 'utf8').replace(/^import .*;\s*$/gm, '');
const code = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, experimentalDecorators: true}}).outputText;
const created = [], listeners = new Map(), removed = [];
const events = {
 Support: {COMMON_EVENT_USB_DEVICE_ATTACHED: 'attach', COMMON_EVENT_USB_DEVICE_DETACHED: 'detach'},
 createSubscriber(info, done) {created.push(done);},
 subscribe(subscriber, listener) {listeners.set(subscriber, listener);},
 unsubscribe(subscriber, done) {removed.push(subscriber); done(null);},
};
const usb = {getDevices() {return [{name:'test-usb', configs:[{interfaces:[{clazz:3}]}]}];}};
const exports = {};
new Function('exports', 'BaseAdapter', 'CommonEventManager', 'usb', 'injectable', 'LogMethod', 'LogUtil', code)(
 exports, class {}, events, usb, () => value => value, () => {}, {error(){},warn(){}});
const adapter = new exports.DeviceAdapter();
usb.hasRight = () => {throw {code:801, message:'System capability unavailable'};};
assert.equal(adapter.hasRight('test-usb'), false);
usb.hasRight = () => true;
assert.equal(adapter.hasRight('test-usb'), true);
let descriptorReturned = false;
usb.getRawDescriptor = () => new Uint8Array([18, 1, 0, 2, 0, 0, 0, 64]);
adapter.getRawDescriptor({}, (bytes, length) => {
  assert.equal(Array.isArray(bytes), true, 'AKI std::vector requires a JS array');
  assert.deepEqual(bytes, [18, 1, 0, 2, 0, 0, 0, 64]);
  assert.equal(length, bytes.length);
  descriptorReturned = true;
});
assert.equal(descriptorReturned, true);
descriptorReturned = false;
usb.getRawDescriptor = () => {throw {code:801, message:'Read failed'};};
adapter.getRawDescriptor({}, (bytes, length) => {
  assert.deepEqual(bytes, []);
  assert.equal(length, 0);
  descriptorReturned = true;
});
assert.equal(descriptorReturned, true);
const calls = [];
adapter.registerHotplugCallback(1, (...v) => calls.push([1, ...v]));
adapter.registerHotplugCallback(2, (...v) => calls.push([2, ...v]));
created[0](null, 'first'); created[1](null, 'second');
const attach = {event:'usual.event.hardware.usb.action.USB_DEVICE_ATTACHED',data:JSON.stringify({name:'test-usb'})};
listeners.get('first')(null, attach); listeners.get('second')(null, attach);
assert.equal(calls.length, 2); assert.equal(calls[0][2][0].configs[0].interfaces[0].clazz, 3);
adapter.unregisterHotplugCallback(1);
listeners.get('first')(null, attach); listeners.get('second')(null, attach);
assert.equal(calls.length, 3); assert.deepEqual(removed, ['first']);
listeners.get('second')(null, {event:attach.event,data:'malformed'});
assert.equal(calls.length, 3);
listeners.get('second')(null, {event:'usual.event.hardware.usb.action.USB_DEVICE_DETACHED',data:JSON.stringify({name:'test-usb'})});
assert.equal(calls.at(-1)[1], 2);
adapter.registerHotplugCallback(3, () => {throw new Error('late callback');});
adapter.unregisterHotplugCallback(3); created[2](null, 'late');
assert.equal(listeners.has('late'), false);
adapter.unregisterHotplugCallback(2); adapter.unregisterHotplugCallback(2);
const report = {passed:true, scope:'Real ArkTS methods with simulated USB system events', cases:['independent USB and HID observers','attach payload hydration','unsubscribe isolation','late event ignored','malformed event rejected','partial detach accepted','late subscriber cancelled','duplicate teardown safe','system access exceptions return a result','typed USB descriptors become a JS array','descriptor failure always returns a result']};
fs.mkdirSync(path.join(root, 'reports'), {recursive:true});
fs.writeFileSync(path.join(root, 'reports/webhid-hotplug-tests.json'), JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
