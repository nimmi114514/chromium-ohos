// Exercise the actual ArkTS helper, transpiled unchanged, with real Inversify.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const project = path.resolve(root, '../chromium-2in1-hap');
const typescript = require(path.join(root,'src/third_party/node/node_modules/typescript/lib/typescript.js'));
require(path.join(project,'web_engine/oh_modules/reflect-metadata/Reflect.js'));
const inversify = require(path.join(project,'web_engine/oh_modules/inversify/lib/inversify.js'));
const source = fs.readFileSync(path.join(project,'web_engine/src/main/ets/common/InjectModule.ets'),'utf8');
const output = typescript.transpileModule(source, {compilerOptions:{target:typescript.ScriptTarget.ES2022,module:typescript.ModuleKind.CommonJS}}).outputText;
const moduleObject = {exports:{}};
vm.runInNewContext(output, {exports:moduleObject.exports,require(name){
  if(name==='inversify') return inversify;
  if(name==='./ModuleType') return {MODULE_TYPE:{Context:Symbol('test-context')}};
  throw new Error('Unexpected runtime dependency: '+name);
},Reflect,Symbol,console});
const Inject = moduleObject.exports.default;
let constructions = 0;
class Ordinary {constructor(){constructions++;}}
inversify.decorate(inversify.injectable(), Ordinary);
const ordinary = Inject.getOrCreate(Ordinary);
assert.equal(Inject.getOrCreate(Ordinary),ordinary);
assert.equal(constructions,1,'Unbound class must be created as a singleton');
let attempts=0;
const token=Symbol('transient-dependency');
Inject.container.bind(token).toDynamicValue(()=>{
  attempts++;
  if(attempts===1) throw new Error('original dependency failure');
  return {ready:true};
}).inSingletonScope();
assert.throws(()=>Inject.getOrCreate(token),/original dependency failure/,'Preserve dependency failures without replacing or duplicating an existing binding');
assert.equal(attempts,1,'A failed constructor must not be invoked again by a finally block');
assert.equal(Inject.getOrCreate(token).ready,true,'The original binding must recover when its dependency becomes ready');
assert.equal(attempts,2);
console.log(JSON.stringify({passed:true,singletonPreserved:true,constructorFailurePreserved:true,failedLookupDoesNotDuplicateBindings:true,retryRecovers:true}));
