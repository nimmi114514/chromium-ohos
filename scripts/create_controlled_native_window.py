#!/usr/bin/env python3
"""Create a separate native test window from an already visible generated tab."""
import json,re,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HDC=['/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe','-t','6YT0226706000164']
def run(*args):
 p=subprocess.run(HDC+list(args),capture_output=True,text=True,timeout=25)
 if p.returncode or '[Fail]' in p.stdout:raise RuntimeError('Native UI operation failed')
 return p.stdout
def nodes(n):
 if isinstance(n,list):
  for x in n:yield from nodes(x)
 elif isinstance(n,dict):
  yield n
  for c in n.get('children',[]):yield from nodes(c)
def marked_root(tree):
 for n in nodes(tree):
  a=n.get('attributes',{})
  if a.get('type')=='root' and a.get('bundleName')=='com.example.chromium':
   for child in nodes(n):
    b=child.get('attributes',{})
    if b.get('type','').lower()=='rootwebarea' and b.get('visible')!='false' and any('CHROMIUM_TEST_RENDER' in str(b.get(k,'')) for k in ['text','description','title']):return n
 raise RuntimeError('Visible generated tab not found')
with tempfile.TemporaryDirectory(dir=ROOT/'reports') as d:
 p=Path(d)/'layout.json';remote='/data/local/tmp/chromium158-native-create-window.json'
 def layout():
  run('shell','uitest','dumpLayout','-b','com.example.chromium','-p',remote,'-m','false')
  win=subprocess.check_output(['wslpath','-w',str(p)],text=True).strip();run('file','recv',remote,win);return json.loads(p.read_text())
 try:
  marked_root(layout())
  run('shell','uitest','uiInput','keyEvent','2072','2030')
  time.sleep(1.5)
  uri=json.loads((ROOT/'reports/native073-release-render-window.json').read_text())['url']
  run('shell','aa','start','-a','EntryAbility','-b','com.example.chromium','-U',uri)
  time.sleep(1.5)
  root=marked_root(layout());tabs=sum(n.get('attributes',{}).get('type','').lower()=='tab' for n in nodes(root));close_buttons=sum(n.get('attributes',{}).get('type','').lower()=='button' and n.get('attributes',{}).get('text')=='关闭' for n in nodes(root))
  report={'generatedWindowVisible':True,'windowBounds':root['attributes'].get('bounds'),'tabCount':tabs,'closeButtonCount':close_buttons,'separateWindowVerified':0<tabs<=2}
  (ROOT/'reports/native073-native-created-window.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 finally:run('shell','rm','-f',remote)
