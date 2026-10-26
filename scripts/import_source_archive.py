#!/usr/bin/env python3
"""Hydrate pinned Git blobs from an official mirror archive, preserving edits.

Every imported file must match the pinned Git tree's blob SHA-1. A truncated
download can be salvaged with --allow-truncated; this never marks it complete.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--allow-truncated", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    pin = json.loads((ROOT / "versions.json").read_text())["chromium"]["revision"]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                                   text=True).strip()
    if head != pin:
        raise SystemExit("Source is not at the pinned revision")
    tree = {}
    listing = subprocess.check_output(["git", "ls-tree", "-rz", pin], cwd=source)
    for row in listing.split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            if kind == "blob":
                tree[os.fsdecode(path)] = (mode, oid)
    count = 0
    pending = []
    result = {"revision": pin, "archive": str(args.archive.resolve()),
              "complete": False, "imported": 0, "preserved_edits": []}

    def flush():
        if pending:
            subprocess.run(["git", "hash-object", "-w", "--no-filters",
                            "--stdin-paths"], cwd=source,
                           input="\n".join(pending) + "\n", text=True,
                           stdout=subprocess.DEVNULL, check=True)
            pending.clear()

    try:
        with tarfile.open(args.archive.resolve(), "r|gz") as archive:
            for member in archive:
                prefix, sep, path = member.name.partition("/")
                if prefix != "chromium-" + pin or not sep or path not in tree:
                    continue
                mode, expected = tree[path]
                if mode == "120000" and member.issym():
                    data = os.fsencode(member.linkname)
                elif member.isfile() and mode in ("100644", "100755"):
                    with archive.extractfile(member) as stream:
                        data = stream.read()
                else:
                    raise ValueError(f"Unexpected archive type: {member.name}")
                actual = hashlib.sha1(b"blob " + str(len(data)).encode() +
                                      b"\0" + data).hexdigest()
                if actual != expected:
                    raise ValueError(f"Archive blob differs from pinned tree: {path}")
                dest = source / path
                # Don't follow an existing symlink when deciding what to save.
                if dest.is_symlink():
                    existing = os.fsencode(os.readlink(dest))
                elif dest.exists():
                    existing = dest.read_bytes()
                else:
                    existing = None
                if existing is not None and existing != data:
                    result["preserved_edits"].append(path)
                    continue
                if existing is None:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if mode == "120000":
                        dest.symlink_to(os.fsdecode(data))
                    else:
                        dest.write_bytes(data)
                        dest.chmod(0o755 if mode == "100755" else 0o644)
                if mode == "120000":
                    subprocess.run(["git", "hash-object", "-w", "--stdin"],
                                   cwd=source, input=data, check=True,
                                   stdout=subprocess.DEVNULL)
                else:
                    pending.append(path)
                count += 1
                if count % 2000 == 0:
                    flush()
                    print(f"Verified/imported {count} pinned source blobs", flush=True)
        result["complete"] = True
    except (EOFError, tarfile.ReadError) as error:
        if not args.allow_truncated:
            raise
        result["truncation"] = str(error)
    finally:
        flush()
        result["imported"] = count
        report = ROOT / "reports/source-archive-import.json"
        report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "preserved_edits"}),
          flush=True)


if __name__ == "__main__":
    main()
