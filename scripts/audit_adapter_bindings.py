#!/usr/bin/env python3
"""Inventory literal bridge names and unresolved dynamic lookups for review."""
import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src'
HAP = ROOT.parent / 'chromium-2in1-hap'
bindings = {}
for path in (HAP / 'web_engine/src/main/ets').rglob('*'):
    if path.is_file() and path.suffix in ('.ts', '.ets'):
        for match in re.finditer(r'JsBindingUtils\.bindFunction\(\s*[\'\"]([^\'\"]+)', path.read_text()):
            bindings.setdefault(match.group(1), []).append(str(path.relative_to(HAP)))
uses, dynamic, files = {}, [], []
prefixes = {name.split('.')[0] for name in bindings}
for path in (SOURCE / 'ohos/adapter').rglob('*'):
    if not path.is_file() or path.suffix not in ('.cc', '.cpp', '.h', '.cxx'):
        continue
    text = path.read_text()
    files.append(str(path.relative_to(SOURCE)))
    for match in re.finditer(r'(?:GetJSFunction|GetJSBindFunction)\(\s*([^\s])', text):
        if match.group(1) not in ('"', "'"):
            dynamic.append({'file':str(path.relative_to(SOURCE)), 'line':text[:match.start()].count('\n')+1})
    # Include constant names passed through helpers such as GetDir(name).
    for match in re.finditer(r'"([A-Za-z_][A-Za-z_0-9]*\.[A-Za-z_][A-Za-z_0-9]*)"', text):
        name = match.group(1)
        if name.split('.')[0] in prefixes or 'Adapter.' in name:
            row = {'file':str(path.relative_to(SOURCE)), 'line':text[:match.start()].count('\n')+1}
            uses.setdefault(name, []).append(row)
missing = [{'function':name, 'nativeSites':sites} for name,sites in sorted(uses.items()) if name not in bindings]
report = {'createdAt':datetime.datetime.now().astimezone().isoformat(), 'scope':'Static literal-name comparison including helper constants. Dynamic lookups and native/ArkTS signatures still require semantic and runtime review.', 'nativeFilesScanned':len(files), 'nativeLiteralNames':len(uses), 'arktsLiteralBindings':len(bindings), 'missingBindingCandidates':missing, 'dynamicLookups':dynamic, 'complete':False}
(ROOT / 'reports/adapter-binding-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'nativeFilesScanned':len(files),'nativeLiteralNames':len(uses),'arktsLiteralBindings':len(bindings),'missingCandidates':len(missing),'dynamicLookups':len(dynamic)}))
for row in missing:
    print(json.dumps(row))
