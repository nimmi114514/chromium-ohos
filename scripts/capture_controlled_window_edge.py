#!/usr/bin/env python3
"""Retain only the lower edge of a window containing our generated render page."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HDC = '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--marker', default='CHROMIUM_TEST_RENDER')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.label):
        parser.error('Use a simple label')
    prefix = [HDC, '-t', '6YT0226706000164']
    def run(*cmd):
        r = subprocess.run([*prefix, *cmd], capture_output=True, timeout=35)
        if r.returncode or b'[Fail]' in r.stdout:
            raise RuntimeError('Device capture failed: ' + cmd[0])
        return r
    def win(p):
        return subprocess.check_output(['wslpath', '-w', str(p.resolve())], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='controlled-edge-', dir=ROOT / 'reports') as temp:
        temp = Path(temp)
        remote = '/data/local/tmp/chromium158-edge-' + args.label
        try:
            run('shell', 'uitest', 'dumpLayout', '-b', 'com.example.ohos.chromium',
                '-p', remote + '.json', '-m', 'false')
            run('file', 'recv', remote + '.json', win(temp / 'layout.json'))
            tree = json.loads((temp / 'layout.json').read_text())
            found = []
            def visit(n, ancestors):
                if isinstance(n, list):
                    for child in n: visit(child, ancestors)
                elif isinstance(n, dict):
                    a = n.get('attributes', {})
                    path = ancestors + [a]
                    if a.get('type','').lower() == 'rootwebarea' and a.get('visible') != 'false' and any(args.marker in str(a.get(k, ''))
                           for k in ('text', 'description', 'title')):
                        roots = [x for x in path if x.get('type') == 'root' and
                                 x.get('bundleName') == 'com.example.ohos.chromium']
                        if roots: found.append(roots[-1])
                    for child in n.get('children', []): visit(child, path)
            visit(tree, [])
            if not found:
                raise RuntimeError('Our generated render window is not visible')
            bounds = tuple(map(int, re.findall(r'-?\d+', found[0]['bounds'])))
            if len(bounds) != 4 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                raise RuntimeError('Invalid controlled window bounds')
            run('shell', 'uitest', 'screenCap', '-p', remote + '.png')
            run('file', 'recv', remote + '.png', win(temp / 'screen.png'))
            with Image.open(temp / 'screen.png') as full:
                if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > full.width or bounds[3] > full.height:
                    raise RuntimeError('Window bounds outside captured screen')
                box = (bounds[0], max(bounds[1], bounds[3]-96), bounds[2], bounds[3])
                edge = full.crop(box).convert('RGB')
                destination = ROOT / 'reports' / (args.label + '-bottom-edge.png')
                edge.save(destination)
                rows = []
                for y in range(edge.height):
                    pixels = [edge.getpixel((x, y)) for x in range(edge.width)]
                    rows.append({'distanceFromBottom': edge.height-1-y,
                                 'pureBluePixels': sum(r < 8 and g < 8 and b > 247 for r,g,b in pixels),
                                 'saturatedBluePixels': sum(r < 60 and g < 100 and b > 180 for r,g,b in pixels)})
                report = {'controlledWindowVerified': True, 'windowBounds': bounds,
                          'cropBounds': box, 'image': str(destination.relative_to(ROOT)),
                          'fullScreenRetained': False, 'rows': rows,
                          'pureBluePixels': sum(x['pureBluePixels'] for x in rows)}
                (ROOT / 'reports' / (args.label + '-edge.json')).write_text(json.dumps(report, indent=2)+'\n')
                print(json.dumps({k:v for k,v in report.items() if k != 'rows'}))
        finally:
            run('shell', 'rm', '-f', remote + '.json', remote + '.png')

if __name__ == '__main__':
    main()
