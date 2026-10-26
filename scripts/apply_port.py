#!/usr/bin/env python3
"""Apply the reviewed patch series to the pinned Chromium checkout."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(source, *args, check=True):
    return subprocess.run(["git", "-C", str(source), *args], check=check,
                          text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--check", action="store_true", help="Validate without editing")
    args = parser.parse_args()
    source = args.source.resolve()
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    actual = git(source, "rev-parse", "HEAD").stdout.strip()
    if actual != lock["revision"]:
        raise SystemExit(f"Wrong Chromium revision: {actual}; expected {lock['revision']}")
    version = dict(line.split("=", 1) for line in
                   (source / "chrome/VERSION").read_text().splitlines())
    actual_version = ".".join(version[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    if actual_version != lock["version"]:
        raise SystemExit(f"Wrong Chromium version: {actual_version}")
    series = (ROOT / "patches/series").read_text().splitlines()
    entries = [(source, ROOT / "patches" / name) for name in series
               if name.strip() and not name.startswith("#")]
    manifest = ROOT / "dependency-patches/series.json"
    if manifest.is_file():
        for entry in json.loads(manifest.read_text()):
            repo = source / entry["path"]
            pin = git(repo, "rev-parse", "HEAD").stdout.strip()
            if pin != entry["revision"]:
                raise SystemExit(f"Wrong dependency revision: {entry['path']}")
            entries.append((repo, ROOT / "dependency-patches" / entry["patch"]))
    for repo, patch_path in entries:
        name = patch_path.name
        if not name.strip() or name.startswith("#"):
            continue
        patch = str(patch_path)
        if git(repo, "apply", "--reverse", "--check", patch, check=False).returncode == 0:
            print(f"Already applied: {name}", flush=True)
            continue
        check = git(repo, "apply", "--check", patch, check=False)
        if check.returncode:
            raise SystemExit(f"Cannot apply {name}:\n{check.stderr}")
        if args.check:
            print(f"Applicable: {name}", flush=True)
        else:
            git(repo, "apply", patch)
            print(f"Applied: {name}", flush=True)


if __name__ == "__main__":
    main()
