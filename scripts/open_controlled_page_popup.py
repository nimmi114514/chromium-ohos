#!/usr/bin/env python3
"""Open only the generated page's popup; retain geometry, not other page content."""
import json,re,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
H=['/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe','-t','6YT0226706000164']
def run(*a):
 r=subprocess.run(H+list(a),capture_output=True,text=True,timeout=25)
 if r.returncode or '[Fail]' in r.stdout:raise RuntimeError('UI operation failed')
 return r.stdout
def nodes(n,parents=()):
 if isinstance(n,list):
  for c in n:yield from nodes(c,parents)
 elif isinstance(n,dict):
  yield n,parents
  for c in n.get('children',[]):yield from nodes(c,parents+(n,))
def attrs(n):return n.get('attributes',{})
def label(n):return ' '.join(str(attrs(n).get(k,'')) for k in ['text','description','title'])
with tempfile.TemporaryDirectory(dir=ROOT/'reports') as d:
 p=Path(d)/'a.json';remote='/data/local/tmp/chromium158-generated-popup.json'
 def layout():
  run('shell','uitest','dumpLayout','-b','com.example.chromium','-p',remote,'-m','false');w=subprocess.check_output(['wslpath','-w',str(p)],text=True).strip();run('file','recv',remote,w);return json.loads(p.read_text())
 try:
  tree=layout();parents=[n for n,_ in nodes(tree) if attrs(n).get('type')=='root' and attrs(n).get('bundleName')=='com.example.chromium' and any(attrs(x).get('type','').lower()=='rootwebarea' and 'CHROMIUM_TEST_RENDER' in label(x) for x,_ in nodes(n))]
  if not parents:raise RuntimeError('Generated parent window unavailable')
  parents=parents[-1:]
  buttons=[n for n,_ in nodes(parents[0]) if 'button' in attrs(n).get('type','').lower() and 'CHROMIUM_TEST_POPUP' in label(n)]
  if len(buttons)!=1:raise RuntimeError('Generated popup trigger unavailable')
  b=tuple(map(int,re.findall(r'-?\d+',attrs(buttons[0]).get('bounds',''))));run('shell','uitest','uiInput','click',str((b[0]+b[2])//2),str((b[1]+b[3])//2));time.sleep(1)
  after=layout();roots=[]
  for n,trail in nodes(after):
   if attrs(n).get('type','').lower()=='rootwebarea' and 'CHROMIUM_TEST_RENDER_POPUP' in label(n):
    roots+=[x for x in trail if attrs(x).get('type')=='root']
  if not roots:raise RuntimeError('Generated native popup unavailable')
  report={'controlledPopupVerified':True,'windowBounds':attrs(roots[-1]).get('bounds'),'tabCount':sum(attrs(x).get('type','').lower()=='tab' for x,_ in nodes(roots[-1]))};(ROOT/'reports/native073-controlled-popup-window.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 finally:run('shell','rm','-f',remote)
