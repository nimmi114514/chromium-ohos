// Execute the production ArkTS adapter against delayed/failed system picker calls.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const root=path.resolve(import.meta.dirname,'..');
const ts=require('/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/ets/build-tools/ets-loader/node_modules/typescript/lib/typescript.js');
const source=fs.readFileSync(path.resolve(root,'../chromium-2in1-hap/web_engine/src/main/ets/adapter/ContextPathAdapter.ets'),'utf8').replace(/^import .*;\s*$/gm,'');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,experimentalDecorators:true}}).outputText;
function fixture(save, context={getActiveContext:()=>undefined,getContext:()=>({kind:'application'})}) {
 let calls=0;
 const picker={DocumentPickerMode:{DOWNLOAD:1},DocumentSaveOptions:class{},DocumentViewPicker:class{
  constructor(ctx){assert.ok(ctx);}
  save(options){assert.equal(options.pickerMode,1);return save(++calls);}
 }};
 const exports={};
 new Function('exports','BaseAdapter','picker','fileUri','injectable','inject','ContextAdapter','LogMethod','LogUtil',code)(
  exports,class{},picker,{FileUri:class{constructor(uri){if(uri==='invalid')throw Error('Invalid URI');this.path=uri.replace('file://','');}}},
  ()=>value=>value,()=>()=>{},class{},()=>{}, {error(){}});
 return {adapter:new exports.ContextPathAdapter(context),calls:()=>calls};
}
const request=a=>new Promise(resolve=>a.getAppDownloadDir(resolve));
const expected='/storage/Users/currentUser/Download/com.example.ohos.chromium';
const uri='file://'+expected;
const results=[];
{
 let complete;
 const f=fixture(()=>new Promise(resolve=>{complete=resolve;}));
 const first=request(f.adapter);
 // The native bridge stops waiting after one second; the OS may finish later.
 await new Promise(resolve=>setTimeout(resolve,1100));
 const second=request(f.adapter);
 assert.equal(f.calls(),1,'share a still-pending system request');
 complete([uri]);assert.deepEqual(await Promise.all([first,second]),[expected,expected]);
 let cached;
 f.adapter.getAppDownloadDir(value=>{cached=value;});
 assert.equal(cached,expected,'late success must be available synchronously on retry');
 assert.equal(f.calls(),1);results.push('late success survives native timeout; concurrent request sharing');
}
for(const [name,fail] of [
 ['rejection',()=>Promise.reject(Error('Permission unavailable'))],
 ['synchronous picker exception',()=>{throw Error('Unavailable');}],
 ['empty result',()=>Promise.resolve([])],
 ['invalid URI',()=>Promise.resolve(['invalid'])],
]){
 const f=fixture(n=>n===1?fail():Promise.resolve([uri]));
 assert.equal(await request(f.adapter),'');
 assert.equal(await request(f.adapter),expected);
 assert.equal(f.calls(),2);results.push(name+' then recovery');
}
{
 let unavailable=true;
 const f=fixture(()=>Promise.resolve([uri]),{getActiveContext(){if(unavailable)throw Error('Not initialized');return undefined;},getContext:()=>({})});
 assert.equal(await request(f.adapter),'');unavailable=false;
 assert.equal(await request(f.adapter),expected);assert.equal(f.calls(),1);
 results.push('context not initialized then recovery');
}
console.log(JSON.stringify({passed:true,scope:'production adapter with mocked system picker',results}));
