#!/usr/bin/env python3
"""Capture only IPC rejection diagnostics for the current Chromium158 process."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
HDC = '/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe'
DEVICE = '6YT0226706000164'
label = sys.argv[1]
if not re.fullmatch(r'native\d+-[a-z0-9-]+', label):
    raise SystemExit('Invalid label')
duration = int(sys.argv[2]) if len(sys.argv) > 2 else 90
pid = subprocess.check_output([HDC, '-t', DEVICE, 'shell', 'pidof',
                               'com.example.chromium']).decode().strip()
if not pid.isdigit():
    raise SystemExit('Expected exactly one current Chromium158 browser PID')
pattern = re.compile(r'bad[ _-]?message|bad IPC|bad Mojo|VALIDATION_ERROR|'
                     r'Mojo error|RPH_MOJO|Terminating render|killed_bad|'
                     r'ShutdownForBadMessage|error code.*bad', re.I)
seen, lines = set(), []
report = {'browserPid': int(pid), 'durationRequested': duration, 'lines': lines}
destination = ROOT / 'reports' / (label + '-ipc-rejections.json')
deadline = time.monotonic() + duration
while time.monotonic() < deadline:
    result = subprocess.run([HDC, '-t', DEVICE, 'shell', 'hilog', '-x', '-P', pid],
                            capture_output=True, timeout=15)
    for line in result.stdout.decode('utf-8', 'replace').splitlines():
        if not pattern.search(line) or line in seen:
            continue
        if re.search(r'client.secret|api.key|gaia.config.contents', line, re.I):
            continue
        seen.add(line)
        lines.append(line)
        print(line, flush=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    time.sleep(1)
report['complete'] = True
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
