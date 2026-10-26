#!/usr/bin/env python3
"""Carry explicitly OHOS-related reference changes onto pinned Chromium.

Only clean three-way merges may be applied. Conflicts are written outside src
for manual porting; they are never introduced into the compilation tree.
"""
import argparse
import collections
import difflib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MARKER = re.compile(r"ohos|__MUSL__|use_musl|wiseplay", re.IGNORECASE)


def platform_delta(baseline, reference):
    old, new = baseline.splitlines(keepends=True), reference.splitlines(keepends=True)
    result = []
    cursor = 0
    kept = skipped = 0
    for group in difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(3):
        start, stop = group[0][1], group[-1][2]
        new_start, new_stop = group[0][3], group[-1][4]
        result.extend(old[cursor:start])
        context = "".join(old[start:stop] + new[new_start:new_stop])
        if MARKER.search(context):
            result.extend(new[new_start:new_stop])
            kept += 1
        else:
            result.extend(old[start:stop])
            skipped += 1
        cursor = stop
    result.extend(old[cursor:])
    return "".join(result), kept, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--component", choices=("src", "chrome"), default="src")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--extension", action="append",
                        help="Limit migration to a named text suffix (repeatable)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    reference = (args.reference or ROOT.parent / ("ohos132-" + args.component)).resolve()
    lock = json.loads((ROOT / "versions.json").read_text())
    for path, pin in ((source, lock["chromium"]["revision"]),
                      (reference, lock["ohos_reference"][args.component + "_revision"])):
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path,
                                         text=True).strip()
        if actual != pin:
            raise SystemExit(f"Unexpected revision at {path}: {actual}")
    inventory_name = "ohos132-port-candidates.json"
    if args.component == "chrome":
        inventory_name = "ohos132-chrome-port-candidates.json"
    candidates = json.loads((ROOT / "references" / inventory_name).read_text())["files"]
    output = (ROOT / "migration" / args.prefix.strip("/").replace("/", "-")).resolve()
    if args.extension:
        output = output.with_name(output.name + "-formats-" +
                                  "-".join(x.lstrip(".") for x in args.extension))
    output.mkdir(parents=True, exist_ok=True)
    records = []
    changed_tracked_paths = []
    for entry in candidates:
        path = entry["path"]
        if not path.startswith(args.prefix):
            continue
        donor_path = path.removeprefix("chrome/") if args.component == "chrome" else path
        donor = reference / donor_path
        extensions = args.extension or (".gn", ".gni", ".cc", ".h", ".c", ".cpp", ".mm")
        if not donor.is_file() or donor.suffix not in extensions:
            continue
        record = {"path": path}
        records.append(record)
        if entry["kind"] == "added":
            if not MARKER.search(path):
                record["status"] = "unclassified_addition"
                continue
            merged = donor.read_bytes()
            dest = source / path
            if dest.exists() and dest.read_bytes() != merged:
                record["status"] = "existing_file_requires_review"
                continue
            record["status"] = "platform_addition"
        else:
            baseline = subprocess.check_output(["git", "cat-file", "blob", entry["upstream_blob"]],
                                               cwd=source).decode()
            selected, kept, skipped = platform_delta(baseline, donor.read_text())
            record.update(platform_hunks=kept, other_hunks=skipped)
            if not kept:
                record["status"] = "no_platform_hunks"
                continue
            current = subprocess.run(["git", "show", "HEAD:" + path], cwd=source,
                                     capture_output=True)
            if current.returncode:
                record["status"] = "upstream_removed_or_moved"
                continue
            with tempfile.TemporaryDirectory() as directory:
                temp = Path(directory)
                (temp / "current").write_bytes(current.stdout)
                (temp / "baseline").write_text(baseline)
                (temp / "platform").write_text(selected)
                proc = subprocess.run(["git", "merge-file", "-p", "--diff3",
                                       "-L", "Chromium158", "-L", "Google132",
                                       "-L", "OHOS132", str(temp / "current"),
                                       str(temp / "baseline"), str(temp / "platform")],
                                      capture_output=True)
            merged = proc.stdout
            if proc.returncode:
                conflict = output / "conflicts" / path
                conflict.parent.mkdir(parents=True, exist_ok=True)
                conflict.write_bytes(merged)
                record["status"] = "conflict"
                continue
            dest = source / path
            if dest.exists() and dest.read_bytes() not in (current.stdout, merged):
                record["status"] = "local_edits_require_review"
                continue
            record["status"] = "clean_merge"
        staged = output / "clean" / path
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(merged)
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(merged)
            if entry["kind"] != "added":
                changed_tracked_paths.append(path)
    if changed_tracked_paths:
        subprocess.run(["git", "update-index", "--no-skip-worktree", "--stdin"],
                       input="\n".join(changed_tracked_paths) + "\n", text=True,
                       cwd=source, check=True)
    report = {"source_revision": lock["chromium"]["revision"],
              "reference_revision": lock["ohos_reference"][args.component + "_revision"],
              "applied_clean_changes": args.apply,
              "summary": dict(collections.Counter(r["status"] for r in records)),
              "files": records}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
