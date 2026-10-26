#!/usr/bin/env python3
"""Inventory original132 platform changes and flag statements needing review.

This is a coverage aid, not proof of semantic equivalence or runtime correctness.
It reads Git blobs without applying changes or fetching missing objects.
"""

import collections
import datetime
import difflib
import io
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src").resolve()
REFERENCE_ROOT = Path("/home/wton5889/chromium-workspaces")
TEXT = {".cc", ".cpp", ".c", ".h", ".gn", ".gni", ".mm", ".rs",
        ".py", ".json", ".json5", ".ets", ".ts", ".xml", ".grd",
        ".grdp", ".mojom", ".typemap", ".sh", ".inc", ".S"}
MARKER = re.compile(r"ohos|__MUSL__|use_musl|wiseplay", re.I)


def blobs(repo, ids):
    ids = sorted(set(x for x in ids if x))
    if not ids:
        return {}
    objects = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "objects"], cwd=repo,
        text=True).strip()
    objects = (Path(repo) / objects).resolve()
    # Git 2.43 can still lazy-fetch from a partial clone while reading blobs.
    # A temporary reader with only an object alternate has no remote at all.
    with tempfile.TemporaryDirectory(prefix="ohos132-object-reader-") as temp:
        subprocess.run(["git", "init", "--bare", "--quiet", temp], check=True)
        (Path(temp) / "objects/info/alternates").write_text(str(objects) + "\n")
        result = subprocess.run(
            ["git", "--git-dir=" + temp, "cat-file", "--batch"],
            input=("\n".join(ids) + "\n").encode(),
            capture_output=True, check=True)
    stream = io.BytesIO(result.stdout)
    data = {}
    for key in ids:
        header = stream.readline().decode().strip().split()
        if header[-1] == "missing":
            data[key] = None
            continue
        data[key] = stream.read(int(header[2]))
        assert stream.read(1) == b"\n"
    return data


def normalize(line):
    return re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", line))


def significant(line):
    s = line.strip()
    if s.startswith(("#if", "#elif", "#include")) and MARKER.search(s):
        return True
    return bool(s and not s.startswith(("//", "/*", "*", "#if", "#elif",
                                        "#else", "#endif", "#include")) and
                normalize(s) not in {"{", "}", "};", "else{", "return;",
                                     "returntrue;", "returnfalse;", "break;"})


def main():
    # Include allocator edits excluded from the earlier migration candidate
    # filter. Bundled sysroots, SDK prebuilts and fuzzer data are not port code.
    source_entries = json.loads((ROOT / "references/ohos132-port-candidates.json")
                                .read_text())["files"]
    delta = json.loads((ROOT / "references/ohos132-source-delta.json")
                       .read_text())["files"]
    source_entries += [e for e in delta if e["path"].startswith(
        "base/allocator/partition_allocator/")]
    chrome_entries = json.loads((ROOT / "references/ohos132-chrome-port-candidates.json")
                                .read_text())["files"]
    groups = [("src", source_entries), ("chrome", chrome_entries)]
    inputs = subprocess.check_output(
        [str(ROOT / "tools/ninja"), "-C", "out/OHOS", "-t", "inputs",
         "chrome_main_web"], cwd=SOURCE, text=True).splitlines()
    built = {line.removeprefix("../../") for line in inputs
             if line.startswith("../../")}
    records = []
    for component, entries in groups:
        entries = [e for e in entries if Path(e["path"]).suffix in TEXT]
        donor = REFERENCE_ROOT / ("ohos132-" + component)
        references = blobs(donor, [e["reference_blob"] for e in entries])
        baselines = blobs(SOURCE, [e.get("upstream_blob") for e in entries])
        for entry in entries:
            path = entry["path"]
            record = {"component": component, "path": path,
                      "kind": entry["kind"], "productionInput": path in built}
            records.append(record)
            raw = references[entry["reference_blob"]]
            if raw is None:
                record["status"] = "reference_blob_missing"
                continue
            try:
                reference = raw.decode()
                current = (SOURCE / path).read_text() if (SOURCE / path).is_file() else None
            except (UnicodeDecodeError, OSError):
                record["status"] = "nontext_or_unreadable"
                continue
            if entry["kind"] == "added":
                record["status"] = (
                    "missing_reference_addition" if current is None else
                    "reference_addition_exact" if current == reference else
                    "reference_addition_adapted_review")
                record["platformNamed"] = bool(MARKER.search(path))
                if current is not None and current != reference:
                    record["changedLines"] = sum(
                        1 for line in difflib.unified_diff(reference.splitlines(),
                                                          current.splitlines())
                        if line.startswith(("+", "-")) and
                        not line.startswith(("+++", "---")))
                continue
            baseline_raw = baselines.get(entry.get("upstream_blob"))
            if baseline_raw is None:
                record["status"] = "baseline_blob_missing"
                continue
            baseline = baseline_raw.decode(errors="replace").splitlines()
            reference_lines = reference.splitlines()
            blocks = []
            for group in difflib.SequenceMatcher(None, baseline, reference_lines,
                                                  autojunk=False).get_grouped_opcodes(3):
                context = "\n".join(
                    baseline[group[0][1]:group[-1][2]] +
                    reference_lines[group[0][3]:group[-1][4]])
                if not MARKER.search(context):
                    continue
                additions = []
                for tag, _, _, start, end in group:
                    if tag in ("replace", "insert"):
                        additions.extend((i + 1, reference_lines[i])
                                         for i in range(start, end)
                                         if significant(reference_lines[i]))
                blocks.extend(additions)
            record["platformStatements"] = len(blocks)
            if not blocks:
                record["status"] = "no_platform_statements"
                continue
            if current is None:
                record["status"] = "upstream_path_removed_or_missing"
                continue
            normalized_current = normalize(current)
            missing = [{"referenceLine": line, "statement": statement.strip()}
                       for line, statement in blocks
                       if normalize(statement) not in normalized_current]
            record["missingStatements"] = missing
            record["status"] = "platform_statements_present" if not missing else "review_missing_statements"
    report = {"generatedAt": datetime.datetime.now().astimezone().isoformat(),
              "method": "Original132 changed platform statements, exact new-file comparison, current native target input reachability",
              "semanticReviewComplete": False,
              "runtimeVerified": False,
              "summary": dict(collections.Counter(r["status"] for r in records)),
              "files": records}
    destination = ROOT / "reports/api26-original132-coverage-audit.json"
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for status, count in sorted(report["summary"].items()):
        print(f"{status}: {count}")
    print(f"Coverage inventory (semantic review pending): {destination}")


if __name__ == "__main__":
    main()
