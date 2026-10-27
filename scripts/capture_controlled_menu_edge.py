#!/usr/bin/env python3
"""Open our generated window's app menu and retain only its lower border."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HDC = '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--label', required=True)
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.label): ap.error('Invalid label')
    prefix = [HDC, '-t', '6YT0226706000164']
    def run(*cmd):
        p = subprocess.run([*prefix, *cmd], capture_output=True, timeout=35)
        if p.returncode or b'[Fail]' in p.stdout: raise RuntimeError('UI operation failed: '+cmd[0])
    def win(p): return subprocess.check_output(['wslpath','-w',str(p.resolve())],text=True).strip()
    def rect(a): return tuple(map(int,re.findall(r'-?\d+',a.get('bounds',''))))
    def nodes(n, ancestors=()):
        if isinstance(n,list):
            for c in n: yield from nodes(c,ancestors)
        elif isinstance(n,dict):
            path=ancestors+(n,)
            yield n,path
            for c in n.get('children',[]): yield from nodes(c,path)
    with tempfile.TemporaryDirectory(prefix='controlled-menu-',dir=ROOT/'reports') as tmp:
        tmp=Path(tmp);remote='/data/local/tmp/chromium158-menu-'+args.label
        def layout(suffix):
            run('shell','uitest','dumpLayout','-b','com.example.chromium','-p',remote+'.json','-m','false')
            p=tmp/(suffix+'.json');run('file','recv',remote+'.json',win(p));return json.loads(p.read_text())
        try:
            before=layout('before');owned=None
            for node,trail in nodes(before):
                a=node.get('attributes',{})
                if a.get('type','').lower()=='rootwebarea' and a.get('visible')!='false' and any('CHROMIUM_TEST_RENDER' in str(a.get(k,'')) for k in ('text','description','title')):
                    roots=[n for n in trail if n.get('attributes',{}).get('type')=='root' and n.get('attributes',{}).get('bundleName')=='com.example.chromium']
                    if roots: owned=roots[-1];break
            if owned is None: raise RuntimeError('Generated render window not found')
            window_rect=rect(owned['attributes']);buttons=[]
            for node,_ in nodes(owned):
                a=node.get('attributes',{});label=' '.join(str(a.get(k,'')) for k in ('text','description'))
                if 'button' in a.get('type','').lower() and re.search(r'自定义|Customize',label,re.I):
                    b=rect(a)
                    if len(b)==4 and b[2]>b[0] and b[3]>b[1]: buttons.append(b)
            if buttons:
                b=max(buttons,key=lambda x:x[2]);run('shell','uitest','uiInput','click',str((b[0]+b[2])//2),str((b[1]+b[3])//2))
                trigger='owned_app_menu_button'
            else:
                # SDK key codes: ALT_LEFT=2045, F=2022. Only after proving
                # that the visible RootWebArea is our generated fixture.
                run('shell','uitest','uiInput','keyEvent','2045','2022')
                trigger='owned_window_alt_f'
            time.sleep(.6)
            after=layout('after');menus=[]
            for node,_ in nodes(after):
                a=node.get('attributes',{})
                if a.get('type','').lower()=='menu' and a.get('visible')!='false':
                    b=rect(a)
                    if len(b)==4 and b[2]-b[0]>80 and b[3]-b[1]>40:menus.append(b)
            if not menus: raise RuntimeError('Native app-menu bounds unavailable')
            menu=max(menus,key=lambda b:(b[2]-b[0])*(b[3]-b[1]));run('shell','uitest','screenCap','-p',remote+'.png');run('file','recv',remote+'.png',win(tmp/'screen.png'))
            with Image.open(tmp/'screen.png') as full:
                if min(menu)<0 or menu[2]>full.width or menu[3]>full.height: raise RuntimeError('Menu outside capture')
                box=(menu[0],max(menu[1],menu[3]-12),menu[2],menu[3]);edge=full.crop(box).convert('RGB');out=ROOT/'reports'/(args.label+'-menu-bottom-edge.png');edge.save(out)
                blue=sum(r<8 and g<8 and b>247 for r,g,b in edge.getdata());report={'controlledWindowVerified':True,'trigger':trigger,'menuBounds':menu,'cropBounds':box,'pureBluePixels':blue,'image':str(out.relative_to(ROOT)),'fullScreenRetained':False}
                (ROOT/'reports'/(args.label+'-menu-edge.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
            run('shell','uitest','uiInput','click',str(window_rect[0]+100),str(window_rect[1]+400))
        finally: run('shell','rm','-f',remote+'.json',remote+'.png')

if __name__=='__main__': main()
