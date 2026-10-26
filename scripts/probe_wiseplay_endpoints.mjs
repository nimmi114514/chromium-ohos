// Read-only connectivity check from the actual browser network stack.
// Only an owned blank target and vendor-published demo URLs are accessed.
import fs from 'node:fs';
import path from 'node:path';
import {connect} from './local_cdp.mjs';
const label=process.argv[2];if(!/^native\d+-[a-z0-9-]+$/.test(label||''))throw Error('Invalid label');
const out=path.resolve(import.meta.dirname,'../reports',label+'.json');
const urls=[
 'https://wiseplay.ezdrm.com/',
 'https://drmkit.hwcloudtest.cn:8082/wpmedia/LaunchEvent/cenc_DASH_H264_1.4M_30fps_720P/dash.mpd',
 'https://wiseplay.hwcloudtest.cn:9091/playdemo/chinaDrm/getLicense?contentId=sfasRAeuyHJFSJA&useDrmProxy=1'
];
let c,targetId;const report={label,readOnly:true,licenseRequestsSent:false,results:[]};
try{
 c=await connect();report.browserPid=c.ownPid;
 ({targetId}=await c.send('Target.createTarget',{url:'about:blank',background:true}));
 const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
 const {frameTree}=await c.send('Page.getFrameTree',{},sessionId);
 for(const url of urls){
  try{const {resource}=await c.send('Network.loadNetworkResource',{frameId:frameTree.frame.id,url,options:{disableCache:true,includeCredentials:false}},sessionId);
   report.results.push({url,success:resource.success,status:resource.httpStatusCode,netError:resource.netError,netErrorName:resource.netErrorName});
   if(resource.stream)await c.send('IO.close',{handle:resource.stream},sessionId);
  }catch(e){report.results.push({url,error:String(e)});}
  fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
 }
 report.complete=true;
}catch(e){report.error=String(e);}
finally{if(c){if(targetId)try{await c.send('Target.closeTarget',{targetId});report.ownedTargetClosed=true;}catch{}c.close();}fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));}
