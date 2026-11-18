// Execute production ArkTS with simulated Window Kit; no device operations.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const ts=createRequire(import.meta.url)('/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/ets/build-tools/ets-loader/node_modules/typescript/lib/typescript.js');
const project=process.env.HAP_PROJECT_DIR || new URL('../../chromium-2in1-hap/',import.meta.url).pathname;
const source=fs.readFileSync(project+'/web_engine/src/main/ets/ability/WebBaseAbility.ets','utf8').replace(/^import[\s\S]*?;\s*$/gm,'');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
const statuses={FULL_SCREEN:1,MAXIMIZE:2,FLOATING:3,SPLIT_SCREEN:4};
const cases=[];
function fixture({device='tablet',pc=false,state=statuses.FLOATING,failOnce=false}={}){
 const ctx={exports:{},UIAbility:class{},window:{WindowStatusType:statuses},deviceInfo:{deviceType:device},settings:{domainName:{USER_PROPERTY:0},getValueSync:()=>String(pc)},LogUtil:{info(){},warn(){},error(){}}};
 vm.runInNewContext(code,ctx);
 const a=Object.create(ctx.exports.WebBaseAbility.prototype),calls=[];let active=0,overlap=false;
 const op=async x=>{active++;if(active>1)overlap=true;calls.push(x);await new Promise(r=>setImmediate(r));active--;if(failOnce&&x==='navigationIndicator:false'){failOnce=false;throw Error('OS failure');}};
 const w={getWindowStatus:()=>state,setWindowLayoutFullScreen:v=>op('layout:'+v),setSpecificSystemBarEnabled:(n,v)=>op(n+':'+v)};
 Object.assign(a,{context:{},systemBarUpdateRunning:false,pendingSystemBarImmersive:undefined,getWindow:()=>w});
 return {a,calls,get overlap(){return overlap;},setState(v){state=v;}};
}
async function drain(f){for(let i=0;i<100&&f.a.systemBarUpdateRunning;i++)await new Promise(r=>setImmediate(r));assert.equal(f.a.systemBarUpdateRunning,false);assert.equal(f.overlap,false);}
for(const state of Object.values(statuses)){
 const f=fixture({state});f.a.syncSystemBarWithWindowStatus();await drain(f);
 const immersive=[statuses.FULL_SCREEN,statuses.MAXIMIZE].includes(state);
 assert.deepEqual(f.calls,immersive?['layout:true','navigationIndicator:false','status:false']:['navigationIndicator:true','status:true','layout:false']);cases.push('window state '+state);
}
{
 const f=fixture();f.a.updateAvoidAreaStatus(true);f.a.updateAvoidAreaStatus(false);await drain(f);
 assert.deepEqual(f.calls,['layout:true','navigationIndicator:false','status:false','navigationIndicator:true','status:true','layout:false']);cases.push('hide then restore while pending');
}
{
 const f=fixture();f.a.updateAvoidAreaStatus(true);f.a.updateAvoidAreaStatus(false);f.a.updateAvoidAreaStatus(true);await drain(f);
 assert.equal(f.calls.at(-1),'status:false');assert(!f.calls.includes('navigationIndicator:true'));cases.push('rapid transition retains latest state');
}
for(const config of [{device:'2in1'},{device:'tablet',pc:true}]){
 const f=fixture(config);f.a.updateAvoidAreaStatus(true);await drain(f);assert.deepEqual(f.calls,[]);cases.push('PC excluded '+JSON.stringify(config));
}
{
 const f=fixture({failOnce:true});f.a.updateAvoidAreaStatus(true);f.a.updateAvoidAreaStatus(false);await drain(f);assert.equal(f.calls.at(-1),'layout:false');cases.push('OS rejection does not block subsequent restore');
}
{
 const f=fixture();f.a.getWindow=()=>undefined;f.a.updateAvoidAreaStatus(true);await drain(f);assert.deepEqual(f.calls,[]);cases.push('window gone');
}
console.log(JSON.stringify({passed:true,scope:'Production ArkTS methods with simulated Window Kit, no device operations',cases},null,2));
