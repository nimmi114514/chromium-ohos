#!/usr/bin/env python3
"""Open a browser window through its menu and navigate only that new window."""
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
def attrs(n):return n.get('attributes',{})
def label(n):return ' '.join(str(attrs(n).get(k,'')) for k in ['text','description','title'])
def rect(n):return tuple(map(int,re.findall(r'-?\d+',attrs(n).get('bounds',''))))
def click(n):
 b=rect(n)
 if len(b)!=4 or b[2]<=b[0] or b[3]<=b[1]:raise RuntimeError('Invalid native control bounds')
 run('shell','uitest','uiInput','click',str((b[0]+b[2])//2),str((b[1]+b[3])//2))
def marked(n):return any(attrs(x).get('type','').lower()=='rootwebarea' and attrs(x).get('visible')!='false' and 'CHROMIUM_TEST_RENDER' in label(x) for x in nodes(n))
with tempfile.TemporaryDirectory(dir=ROOT/'reports') as d:
 p=Path(d)/'layout.json';remote='/data/local/tmp/chromium158-menu-new-window.json'
 def layout():
  run('shell','uitest','dumpLayout','-b','com.example.chromium','-p',remote,'-m','false');win=subprocess.check_output(['wslpath','-w',str(p)],text=True).strip();run('file','recv',remote,win);return json.loads(p.read_text())
 try:
  before=layout();parents=[n for n in nodes(before) if attrs(n).get('type')=='root' and attrs(n).get('bundleName')=='com.example.chromium' and marked(n)]
  if len(parents)!=1:raise RuntimeError('Expected one visible generated parent')
  buttons=[n for n in nodes(parents[0]) if 'button' in attrs(n).get('type','').lower() and re.search(r'自定义|Customize',label(n),re.I)]
  if not buttons:raise RuntimeError('Native app menu control unavailable')
  run('shell','uitest','uiInput','keyEvent','2070');time.sleep(.2);click(buttons[-1]);time.sleep(.5);menu=layout()
  items=[n for n in nodes(menu) if re.search(r'^(打开新的窗口|新建窗口|新窗口|New window)',label(n).strip(),re.I)]
  if not items:raise RuntimeError('New window menu item unavailable')
  click(items[0]);time.sleep(1.8);after=layout()
  roots=[n for n in nodes(after) if attrs(n).get('type')=='root' and attrs(n).get('bundleName')=='com.example.chromium' and not marked(n) and sum(attrs(x).get('type','').lower()=='tab' for x in nodes(n))==1]
  if len(roots)!=1:raise RuntimeError('Separate single-tab test window not proven')
  inputs=[n for n in nodes(roots[0]) if re.search(r'地址栏|Address and search|Address bar',label(n),re.I)]
  if not inputs:raise RuntimeError('Address field unavailable in the new test window')
  click(inputs[0]);uri=json.loads((ROOT/'reports/native073-release-render-window.json').read_text())['url'];run('shell','uitest','uiInput','text',uri);run('shell','uitest','uiInput','keyEvent','2054');time.sleep(1.2)
  final=layout();controlled=[n for n in nodes(final) if attrs(n).get('type')=='root' and marked(n)]
  single=[n for n in controlled if sum(attrs(x).get('type','').lower()=='tab' for x in nodes(n))==1]
  if len(single)!=1:raise RuntimeError('Generated page did not reach the new single-tab window')
  report={'separateWindowVerified':True,'nativeMenuUsed':True,'tabCount':1,'windowBounds':attrs(single[0]).get('bounds')};(ROOT/'reports/native073-native-created-window.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 finally:run('shell','rm','-f',remote)
