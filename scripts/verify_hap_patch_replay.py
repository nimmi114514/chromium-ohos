#!/usr/bin/env python3
"""Replay portable HAP patches without exposing local signing settings."""

import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent / "chromium-2in1-hap"
BASELINE = "cc241f6d431c52144afe58f3d4232ca7c9658c43"
EXCLUDED = {
    "build-profile.json5",  # Private local signing settings; checked separately.
    "chromium/oh-package-lock.json5",
    "oh-package-lock.json5",
    "web_engine/oh-package-lock.json5",
    "web_engine/BuildProfile.ets",
}


def main():
    patches = sorted((ROOT / "hap-patches").glob("*.patch"))
    paths = set()
    for patch in patches:
        for match in re.finditer(r"^(?:--- a/|\+\+\+ b/)([^\r\n]+)$",
                                 patch.read_text(), re.M):
            name = match.group(1)
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise SystemExit("Patch contains a nonportable path")
            paths.add(name)
    mismatched, deleted = [], []
    diagnostic_delta = False
    diagnostic_path = "web_engine/src/main/ets/utils/CmdArgsHelper.ets"
    diagnostic_block = (
        b'    // Temporary test instrumentation. Remove before the validated delivery.\n'
        b'    "--v=1",\n'
        b'    "--remote-debugging-address=127.0.0.1",\n'
        b'    "--remote-debugging-port=9222",\n'
    )
    with tempfile.TemporaryDirectory(prefix="hap-port-replay-") as directory:
        replay = Path(directory)
        subprocess.run(["git", "init", "-q", directory], check=True)
        for name in paths:
            result = subprocess.run(
                ["git", "-C", str(PROJECT), "show", f"{BASELINE}:{name}"],
                capture_output=True)
            if result.returncode == 0:
                destination = replay / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(result.stdout)
        for patch in patches:
            result = subprocess.run(
                ["git", "-C", directory, "apply", str(patch)], capture_output=True)
            if result.returncode:
                raise SystemExit("Portable HAP patch replay failed: " + patch.name)
        for name in sorted(paths - EXCLUDED):
            expected, actual = replay / name, PROJECT / name
            if not expected.exists() and not actual.exists():
                deleted.append(name)
            elif not expected.exists() or not actual.exists():
                mismatched.append(name)
            else:
                actual_bytes = actual.read_bytes()
                if name == diagnostic_path and diagnostic_block in actual_bytes:
                    actual_bytes = actual_bytes.replace(diagnostic_block, b"", 1)
                    diagnostic_delta = True
                if expected.read_bytes() != actual_bytes:
                    mismatched.append(name)
    report_path = ROOT / "reports/hap-patch-validation.json"
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    previous.pop("temporaryDiagnosticDelta", None)
    previous.update({
        "baselineRevision": BASELINE,
        "patchCount": len(patches),
        "filesCompared": sorted(paths - EXCLUDED),
        "replayMatchesWorktree": not mismatched,
        "mismatchedPaths": mismatched,
        "verifiedDeletedPaths": deleted,
        "localSigningConfigurationExported": False,
        "temporaryDiagnosticDelta": {
            "present": diagnostic_delta,
            "file": diagnostic_path if diagnostic_delta else None,
            "scope": "Exact four-line local diagnostic block excluded from portable comparison",
            "mustRemoveBeforeFinalDelivery": True,
        },
        "patches": [{"name": p.name,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in patches],
        "updatedAt": datetime.datetime.now().astimezone().isoformat(),
    })
    report_path.write_text(json.dumps(previous, indent=2) + "\n")
    print(json.dumps({"patchCount": len(patches), "matched": not mismatched,
                      "comparedFiles": len(paths - EXCLUDED)}))
    if mismatched:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
