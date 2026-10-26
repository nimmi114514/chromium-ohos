#!/usr/bin/env python3
"""Capture only the Chromium 158 window's accessibility tree."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HDC = '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe'
BUNDLE = 'com.example.ohos.chromium'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--device-key', default='6YT0226706000164')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.label):
        parser.error('Use a simple report label')
    prefix = [HDC, '-t', args.device_key]
    remote = '/data/local/tmp/chromium158-ui-' + args.label + '.json'
    destination = ROOT / 'reports' / (args.label + '-ui.json')
    windows_path = subprocess.check_output(['wslpath', '-w', str(destination)], text=True).strip()
    def run(*command):
        result = subprocess.run([*prefix, *command], capture_output=True, timeout=40)
        if result.returncode or b'[Fail]' in result.stdout:
            raise SystemExit('UI capture failed: ' + command[0])
        return result
    run('shell', 'uitest', 'dumpLayout', '-b', BUNDLE, '-p', remote, '-m', 'false')
    try:
        run('file', 'recv', remote, windows_path)
    finally:
        run('shell', 'rm', remote)
    tree = json.loads(destination.read_text())
    rows = []
    def visit(node):
        if isinstance(node, dict):
            if 'attributes' in node:
                rows.append(node['attributes'])
            for child in node.get('children', []):
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(tree)
    controls = [{k: row.get(k) for k in ('type','text','description','bounds','enabled','selected','visible')}
                for row in rows if any(word in row.get('type','').lower()
                                      for word in ('tab','button','textfield','rootwebarea'))]
    safe_labels = {'打开新的标签页', '新标签页', '重新加载', '恢复', '取消', '关闭', '返回', '前进',
                   'CHROMIUM_INPUT_TEST', 'CHROMIUM_CLICK_TEST'}
    for control in controls:
        for key in ('text', 'description'):
            value = control.get(key) or ''
            if value not in safe_labels and not value.startswith('CHROMIUM_TEST_'):
                control[key] = '[redacted]' if value else ''
    print(json.dumps({'report': str(destination), 'nodeCount': len(rows), 'controls': controls}, ensure_ascii=False))

if __name__ == '__main__':
    main()
