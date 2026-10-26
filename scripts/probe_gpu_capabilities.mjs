// Read graphics capabilities only; do not enumerate or open browser tabs.
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];
if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const c=await connect();
try{
 const {gpu}=await c.send('SystemInfo.getInfo');
 const report={browserPid:c.ownPid,devices:gpu.devices,featureStatus:gpu.featureStatus,auxAttributes:Object.fromEntries(Object.entries(gpu.auxAttributes||{}).filter(([name])=>/gl|vulkan|dawn|skia|display|process_gpu/i.test(name)))};
 fs.writeFileSync(path.resolve(import.meta.dirname,'../reports',label+'.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({...report,auxAttributes:Object.fromEntries(Object.entries(report.auxAttributes).filter(([name])=>!name.includes('extensions')))}));
}finally{c.close();}
