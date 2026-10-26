// Executes the real ArkTS adapter with simulated OS authentication results.
// No passwords, credentials, biometric data, or device identity are accessed.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const root=path.resolve(import.meta.dirname,'..');
const ts=require('/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/ets/build-tools/ets-loader/node_modules/typescript/lib/typescript.js');
const source=fs.readFileSync(path.resolve(root,'../chromium-2in1-hap/web_engine/src/main/ets/adapter/DeviceUserAuthAdapter.ets'),'utf8').replace(/^import .*;\s*$/gm,'');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,experimentalDecorators:true}}).outputText;
const enumValues={SUCCESS:12500000,FAIL:12500001,CANCELED:12500003,TIMEOUT:12500004,NOT_ENROLLED:12500010};
function adapter({available=true,result=enumValues.SUCCESS,throwStart=false}={}){
 const userAuth={UserAuthType:{PIN:1,FACE:2,FINGERPRINT:4},AuthTrustLevel:{ATL3:30000},UserAuthResultCode:enumValues,
  getAvailableStatus(){if(!available)throw {code:12500010};},
  getUserAuthInstance(){let listener;return {on(_event,value){listener=value;},off(){},start(){if(throwStart)throw {code:12500002};listener.onResult({result});}};}};
 const exports={};
 new Function('exports','BaseAdapter','userAuth','cryptoFramework','injectable','LogMethod','LogUtil',code)(
  exports,class{},userAuth,{createRandom:()=>({generateRandomSync:()=>({data:new Uint8Array(24)})})},()=>value=>value,()=>{}, {error(){}});
 return new exports.DeviceUserAuthAdapter();
}
const results=[];
for(const available of [true,false]){
 let actual,calls=0;adapter({available}).checkScreenLockAvailable(value=>{actual=value;calls++;});
 assert.equal(actual,available);assert.equal(calls,1);results.push({name:available?'PIN available':'PIN not enrolled',passed:true});
}
for(const [name,result] of Object.entries(enumValues)){
 const callbacks=[];adapter({result}).startUserAuth('Controlled test',value=>callbacks.push(value),false,-1);
 assert.deepEqual(callbacks,[name==='SUCCESS']);results.push({name,passed:true});
}
const callbacks=[];adapter({throwStart:true}).startUserAuth('Controlled test',value=>callbacks.push(value),false,-1);
assert.deepEqual(callbacks,[false]);results.push({name:'OS start exception',passed:true});
const report={scope:'Real ArkTS adapter with simulated OS; actual user verification not performed',passed:true,results};
fs.writeFileSync(path.join(root,'reports/native105-screen-lock-adapter-tests.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
