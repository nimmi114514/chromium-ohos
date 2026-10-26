#!/usr/bin/env python3
"""Stage clean original132 platform hunks against the current port for review.

Never writes to Chromium's working tree. Conflicted merges remain outside src.
"""
import collections
import difflib
import json
import subprocess
import tempfile
from pathlib import Path

from audit_reference_132 import ROOT, SOURCE, REFERENCE_ROOT, MARKER, blobs


def platform_only(baseline, reference):
    old = baseline.splitlines(keepends=True)
    new = reference.splitlines(keepends=True)
    result = []
    cursor = 0
    selected = 0
    for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(3):
        start, end = group[0][1], group[-1][2]
        changed = "".join("".join(old[a:b] + new[c:d])
                          for tag, a, b, c, d in group if tag != "equal")
        result.extend(old[cursor:start])
        if MARKER.search(changed):
            result.extend(new[group[0][3]:group[-1][4]])
            selected += 1
        else:
            result.extend(old[start:end])
        cursor = end
    result.extend(old[cursor:])
    return "".join(result), selected


def main():
    audit = json.loads((ROOT / "reports/api26-original132-coverage-audit.json").read_text())
    pending = {e["path"] for e in audit["files"]
               if e["status"] == "review_missing_statements"}
    output = ROOT / "migration/original132-audit"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    inventories = [("src", "ohos132-port-candidates.json"),
                   ("chrome", "ohos132-chrome-port-candidates.json")]
    for component, name in inventories:
        entries = json.loads((ROOT / "references" / name).read_text())["files"]
        entries = [e for e in entries if e["path"] in pending]
        references = blobs(REFERENCE_ROOT / ("ohos132-" + component),
                           [e["reference_blob"] for e in entries])
        baselines = blobs(SOURCE, [e.get("upstream_blob") for e in entries])
        for entry in entries:
            path = entry["path"]
            current = (SOURCE / path).read_bytes()
            record = {"path": path}
            records.append(record)
            if not baselines.get(entry.get("upstream_blob")) or not references.get(entry["reference_blob"]):
                record["status"] = "missing_blob"
                continue
            baseline = baselines[entry["upstream_blob"]].decode()
            reference = references[entry["reference_blob"]].decode()
            if reference.startswith("version https://git-lfs.github.com/spec/"):
                record["status"] = "lfs_data_pointer_not_port_code"
                continue
            selected, count = platform_only(baseline, reference)
            if not count:
                record["status"] = "no_platform_changes_in_changed_lines"
                continue
            with tempfile.TemporaryDirectory(prefix="ohos132-platform-merge-") as temp:
                temp = Path(temp)
                (temp / "current").write_bytes(current)
                (temp / "baseline").write_text(baseline)
                (temp / "reference").write_text(selected)
                result = subprocess.run([
                    "git", "merge-file", "-p", "--diff3", "-L", "Current158",
                    "-L", "Google132", "-L", "OHOS132", str(temp / "current"),
                    str(temp / "baseline"), str(temp / "reference")], capture_output=True)
            if result.returncode:
                dest = output / "conflicts" / path
                record["status"] = "manual_review_conflict"
            elif result.stdout == current:
                record["status"] = "no_remaining_clean_delta"
                continue
            else:
                dest = output / "clean" / path
                record["status"] = "clean_staged_for_review"
                diff = list(difflib.unified_diff(current.decode().splitlines(),
                                               result.stdout.decode().splitlines(), n=3))
                record["diff"] = "\n".join(diff)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(result.stdout)
    report = {"applied": False,
              "summary": dict(collections.Counter(r["status"] for r in records)),
              "files": records}
    (ROOT / "reports/api26-original132-staged-review.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
