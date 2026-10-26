#!/usr/bin/env python3
"""Finish navigating the single-tab window just created by our native menu test."""
import json,re,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
H=['/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe','-t','6YT0226706000164']
def run(*a):
 r=subprocess.run(H+list(a),capture_output=True,text=True,timeout=25)
 if r.returncode or '[Fail]' in r.stdout:raise RuntimeError('Native UI operation failed')
 return r.stdout
def nodes(n):
 if isinstance(n,list):
  for c in n:yield from nodes(c)
 elif isinstance(n,dict):
  yield n
  for c in n.get('children',[]):yield from nodes(c)
def a(n):return n.get('attributes',{})
def b(n):return tuple(map(int,re.findall(r'-?\d+',a(n).get('bounds',''))))
with tempfile.TemporaryDirectory(dir=ROOT/'reports') as d:
 p=Path(d)/'layout.json';remote='/data/local/tmp/chromium158-own-single-tab.json'
 def layout():
  run('shell','uitest','dumpLayout','-b','com.example.ohos.chromium','-p',remote,'-m','false');w=subprocess.check_output(['wslpath','-w',str(p)],text=True).strip();run('file','recv',remote,w);return json.loads(p.read_text())
 try:
  tree=layout();roots=[n for n in nodes(tree) if a(n).get('type')=='root' and a(n).get('bundleName')=='com.example.ohos.chromium' and sum(a(x).get('type','').lower()=='tab' for x in nodes(n))==1]
  if len(roots)!=1:raise RuntimeError('Expected the newly created single-tab test window')
  fields=[n for n in nodes(roots[0]) if re.search(r'input|edit|combo|field',a(n).get('type',''),re.I) and len(b(n))==4 and b(n)[1]<250 and b(n)[2]-b(n)[0]>500]
  if not fields:
   print('Header roles:',sorted(set(a(n).get('type','') for n in nodes(roots[0]) if len(b(n))==4 and b(n)[1]<250)))
   raise RuntimeError('Unique native address field not proven')
  field=max(fields,key=lambda n:b(n)[2]-b(n)[0]);r=b(field);print('Native address field:',a(field).get('type'),r)
  run('shell','uitest','uiInput','longClick',str((r[0]+r[2])//2),str((r[1]+r[3])//2));time.sleep(.4)
  context=layout();select_all=[n for n in nodes(context) if re.match(r'^(全选|Select all)',str(a(n).get('text','')).strip(),re.I)]
  if not select_all:raise RuntimeError('Native Select all action unavailable')
  sel=b(select_all[0]);run('shell','uitest','uiInput','click',str((sel[0]+sel[2])//2),str((sel[1]+sel[3])//2))
  # Injected shortcuts do not update the hardware key-state API used by 132.
  # Use the native Select all action and a URL with no shifted punctuation.
  from urllib.parse import urlsplit
  parsed=urlsplit(json.loads((ROOT/'reports/native073-release-render-window.json').read_text())['url']);uri='127.0.0.1'+parsed.path
  run('shell','uitest','uiInput','text',uri);run('shell','uitest','uiInput','keyEvent','2054');time.sleep(1.5)
  final=layout();own=[n for n in nodes(final) if a(n).get('type')=='root' and sum(a(x).get('type','').lower()=='tab' for x in nodes(n))==1 and any(a(x).get('type','').lower()=='rootwebarea' and 'CHROMIUM_TEST_RENDER' in ' '.join(str(a(x).get(k,'')) for k in ['text','description','title']) for x in nodes(n))]
  if len(own)!=1:raise RuntimeError('Generated content did not reach our new window')
  report={'separateWindowVerified':True,'nativeMenuUsed':True,'tabCount':1,'windowBounds':a(own[0]).get('bounds')};(ROOT/'reports/native073-native-created-window.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 finally:run('shell','rm','-f',remote)
