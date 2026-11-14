// Run production ArkTS window methods with simulated Window Kit callbacks.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '..');
const project = process.env.HAP_PROJECT_DIR || path.join(root, '../chromium-2in1-hap');
const ts = require('/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/ets/build-tools/ets-loader/node_modules/typescript/lib/typescript.js');
const status = {UNDEFINED:0, FULL_SCREEN:1, MAXIMIZE:2, MINIMIZE:3, FLOATING:4, SPLIT_SCREEN:5};
const results = [];
function load(file, extra = {}) {
  const source = fs.readFileSync(path.join(project, 'web_engine/src/main/ets', file), 'utf8')
    .replace(/^import[\s\S]*?;\s*$/gm, '');
  const code = ts.transpileModule(source, {compilerOptions: {
    target:ts.ScriptTarget.ES2020, module:ts.ModuleKind.CommonJS, experimentalDecorators:true,
  }}).outputText;
  const context = {
    exports:{}, window:{WindowStatusType:status, MaximizePresentation:{EXIT_IMMERSIVE:0}, AvoidAreaType:{TYPE_SYSTEM:0}},
    LogUtil:{info(){},warn(){},error(){}}, LogMethod(){},
    injectable:() => value => value, inject:() => () => {},
    BaseAdapter:class {}, AbilityManager:class {}, ContextAdapter:class {}, DeviceInfoAdapter:class {},
    NativeThemeAdapter:class {}, NodeHandleManager:class {},
    WebBaseAbility:class {onWindowStageCreate(){}},
    LocalStorage:class {}, getContext:() => ({}),
    deviceInfo:{deviceType:'tablet',sdkApiVersion:26},
    settings:{domainName:{USER_PROPERTY:0},getValueSync:()=>'false'}, WindowStatus:status,
    ...extra,
  };
  vm.runInNewContext(code, context, {filename:file});
  return context;
}
const adapterContext = load('adapter/AppWindowAdapter.ets');
for (const initial of [status.FULL_SCREEN, status.MAXIMIZE, status.SPLIT_SCREEN, status.FLOATING]) {
  let current = initial, moves = 0, resizes = 0;
  const mock = {getWindowStatus:()=>current, getWindowProperties:()=>({drawableRect:{left:0,top:0}}),
    moveWindowToAsync(){moves++;return Promise.resolve();}, resizeAsync(){resizes++;return Promise.resolve();}};
  const adapter = Object.create(adapterContext.exports.AppWindowAdapter.prototype);
  adapter.abilityManager = {getProxy:()=>({getWindow:()=>mock})};
  adapter.setBounds(1, {left:10,top:10,width:800,height:600});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(moves, initial===status.FLOATING?1:0);
  assert.equal(resizes, initial===status.FLOATING?1:0);
  results.push({case:`bounds in mode ${initial}`,passed:true});
}
{
  let current = status.FLOATING, resizes = 0;
  const mock = {getWindowStatus:()=>current,getWindowProperties:()=>({drawableRect:{left:0,top:0}}),
    moveWindowToAsync(){current=status.SPLIT_SCREEN;return Promise.resolve();},
    resizeAsync(){resizes++;return Promise.resolve();}};
  const adapter = Object.create(adapterContext.exports.AppWindowAdapter.prototype);
  adapter.abilityManager = {getProxy:()=>({getWindow:()=>mock})};
  adapter.setBounds(1,{left:0,top:0,width:800,height:600});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(resizes,0);
  results.push({case:'split transition while move is pending',passed:true});
}
function fixture(mode, deviceType='tablet', pc=false) {
  const ctx = load('ability/WebAbility.ets', {deviceInfo:{deviceType,sdkApiVersion:26},
    settings:{domainName:{USER_PROPERTY:0},getValueSync:()=>String(pc)}});
  let maximizes=0;const listeners={}, rects=[], immersion=[];
  const mock = {on:(name,cb)=>listeners[name]=cb,getWindowStatus:()=>mode,
    maximize(){maximizes++;return Promise.resolve();},getWindowAvoidArea:()=>({topRect:{height:30}}),
    getWindowProperties:()=>({drawableRect:{left:4,top:24,width:792,height:572},windowRect:{left:0,top:0}})};
  const ability=Object.create(ctx.exports.WebAbility.prototype);
  Object.assign(ability,{checkSingleInstance:()=>false,abilityManager:{addProxy(){}},
    context:{},getWebappInfo:()=>Promise.resolve(),needDarkMode:()=>false,getContentPath:()=>'',
    initStatus:status.MAXIMIZE,deviceInfoAdapter:{isNormalWindowMode:()=>true,registerDeviceModeChange(){}},
    nativeContext:{OnWindowRectChange:(_id,rect)=>rects.push(rect),OnAvoidAreaChangeCallback(){}},
    displayAdapter:{setStatusBarHeight(){},availableAreaUpdateByStatusBar(){}},updateAvoidAreaStatus(value){immersion.push(value);}});
  ability.onWindowStageCreate({setWindowRectAutoSave(){},getMainWindow:cb=>cb({code:0},mock),
    on(){},getMainWindowSync:()=>mock,loadContent(){}});
  return {ability,mock,listeners,rects,immersion,maximizes:()=>maximizes};
}
for (const [mode,type,pc,expected] of [
  [status.SPLIT_SCREEN,'tablet',false,0], [status.FLOATING,'tablet',false,0],
  [status.FLOATING,'tablet',true,1], [status.FLOATING,'2in1',true,1],
  [status.SPLIT_SCREEN,'2in1',true,0], [status.MAXIMIZE,'tablet',false,0],
]) {
  const f=fixture(mode,type,pc);assert.equal(f.maximizes(),expected);
  results.push({case:`launch mode ${mode}, ${type}, PC=${pc}`,passed:true});
}
for (const mode of [status.FLOATING,status.SPLIT_SCREEN]) {
  const f=fixture(mode);
  f.listeners.windowRectChange({rect:{left:100,top:200,width:800,height:600},reason:0});
  assert.equal(f.rects.at(-1).top,224,'retain the system-provided caption inset');
  assert.equal(f.rects.at(-1).height,572);
  f.rects.length=0;
  f.ability.onPadWindowStageCreate(f.mock,{setOrCreate(){}});
  f.listeners.avoidAreaChange({type:0,area:{topRect:{height:30}}});
  assert.equal(f.rects.length,0,'do not replace system window bounds with fullscreen calculations');
  results.push({case:`caption and avoid-area callbacks in mode ${mode}`,passed:true});
}
for (const module of ['chromium','web_engine']) {
  const source=fs.readFileSync(path.join(project,module,'src/main/module.json5'),'utf8');
  const types=source.match(/"deviceTypes":\s*\[([^\]]+)\]/)[1];
  assert(!types.includes('"phone"'));
  for(const type of ['tablet','2in1']) assert(types.includes(`"${type}"`));
}
{
  const source=fs.readFileSync(path.join(project,'chromium/build-profile.json5'),'utf8');
  const target=source.match(/"name":\s*"default"([\s\S]*?)\}/)[1];
  assert(!target.includes('"deviceType"'),'default target must retain both declared devices');
  results.push({case:'one tablet+2in1 package, no phone declaration',passed:true});
}
const report={passed:true,scope:'Production ArkTS with simulated Window Kit; physical mode switching is separate',results};
fs.writeFileSync(path.join(root,'reports/tablet-window-modes-tests.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
