import {connect} from './local_cdp.mjs';
const c = await connect();
try {
 const {processInfo} = await c.send('SystemInfo.getProcessInfo');
 console.log(JSON.stringify({browser:c.version,processes:processInfo.map(x=>({type:x.type,pid:x.id}))}));
} finally {c.close();}
