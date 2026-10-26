// Exercise the actual ArkTS lifecycle methods with a settings-service mock.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const ts=require(path.join(root,'src/third_party/node/node_modules/typescript/lib/typescript.js'));
const file=path.join(root,'../chromium-2in1-hap/web_engine/src/main/ets/ability/WebAbility.ets');
const source=fs.readFileSync(file,'utf8').replace(/import lazy /g,'import ');
const output=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
let registered=0,unregistered=0,observer;
const context={};
class Base {constructor(){this.context=context;this.nativeContext={};}}
const settings={display:{SCREEN_BRIGHTNESS_STATUS:'brightness'},domainName:{DEVICE_SHARED:'device'},registerKeyObserver(c,key,domain,cb){assert.equal(c,context);registered++;observer=cb;return true;},unregisterKeyObserver(c){assert.equal(c,context);unregistered++;return true;},getValueSync(){return '42';}};
const logger={info(){},warn(){},error(){}};
const m={exports:{}};
vm.runInNewContext(output,{exports:m.exports,getContext:a=>a.context,require(name){
 if(name==='./WebBaseAbility')return {WebBaseAbility:Base};
 if(name==='@kit.BasicServicesKit')return {settings,deviceInfo:{sdkApiVersion:26}};
 if(name==='../utils/LogUtil')return {default:logger};
 return new Proxy({},{get:()=>undefined});
}});
const Ability=m.exports.WebAbility;
const missing=new Ability();missing.registerDisplayBrightnessObserver();assert.equal(registered,0,'Missing native callback must not register an observer');missing.unregisterDisplayBrightnessObserver();assert.equal(unregistered,0);
const supported=new Ability();let calls=0;supported.nativeContext={UpdateDisplayBrightnessCB(value){assert.equal(this,supported.nativeContext);assert.equal(value,'42');calls++;}};
supported.registerDisplayBrightnessObserver();assert.equal(registered,1);const callback=observer;callback();assert.equal(calls,1);
supported.nativeContext.UpdateDisplayBrightnessCB=undefined;assert.doesNotThrow(()=>callback(),'Changed native capability must not throw TypeError');
supported.unregisterDisplayBrightnessObserver();assert.equal(unregistered,1);assert.doesNotThrow(()=>callback(),'Late observer callback after destruction must be harmless');supported.unregisterDisplayBrightnessObserver();assert.equal(unregistered,1,'Cleanup must be idempotent');
console.log(JSON.stringify({missingNativeCallbackPassed:true,supportedCallbackPassed:true,changedCapabilityPassed:true,lateCallbackPassed:true,idempotentCleanupPassed:true}));
