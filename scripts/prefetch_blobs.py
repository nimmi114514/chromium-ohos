#!/usr/bin/env python3
"""Batch missing Git blobs to avoid quadratic giant partial-clone requests."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DATA = (
    "third_party/blink/web_tests/", "third_party/blink/perf_tests/",
    "third_party/blink/manual_tests/", "chrome/test/data/", "content/test/data/",
    "components/test/data/", "tools/perf/page_sets/data/", "docs/",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--paths-json", type=Path)
    parser.add_argument("--metadata", action="store_true")
    parser.add_argument("--build-sources", action="store_true",
                        help="Fetch source except large test-only data trees")
    parser.add_argument("--prefix", action="append", default=[])
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=1500)
    args = parser.parse_args()
    source = args.source.resolve()
    existing = set(subprocess.check_output([
        "git", "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"
    ], cwd=source, text=True).splitlines())
    paths = None
    if args.paths_json:
        paths = {f["path"] for f in json.loads(args.paths_json.read_text())["files"]}
    listing = subprocess.check_output(["git", "ls-tree", "-rz", "HEAD"], cwd=source)
    wanted = set()
    for row in listing.split(b"\0"):
        if not row:
            continue
        meta, raw_path = row.split(b"\t", 1)
        _, kind, oid = meta.decode().split()
        path = raw_path.decode()
        if kind != "blob" or oid in existing:
            continue
        selected = paths is not None and path in paths
        selected |= args.metadata and path.endswith((".gn", ".gni"))
        selected |= args.build_sources and not path.startswith(EXCLUDED_DATA)
        selected |= any(path.startswith(prefix) for prefix in args.prefix)
        if selected:
            wanted.add(oid)
    wanted = sorted(wanted)
    batches = [wanted[i:i + args.batch_size]
               for i in range(0, len(wanted), args.batch_size)]
    print(f"Missing {len(wanted)} blobs in {len(batches)} batches", flush=True)

    def fetch(item):
        index, batch = item
        for attempt in range(4):
            proc = subprocess.run([
                "git", "-c", "fetch.negotiationAlgorithm=noop", "-c",
                "http.version=HTTP/1.1", "-c", "http.lowSpeedLimit=1024",
                "-c", "http.lowSpeedTime=120", "fetch", "origin", "--no-tags",
                "--no-write-fetch-head", "--recurse-submodules=no",
                "--filter=blob:none", "--stdin"
            ], cwd=source, input="\n".join(batch) + "\n", text=True,
                capture_output=True)
            if proc.returncode == 0:
                print(f"Fetched batch {index + 1}/{len(batches)} "
                      f"({len(batch)} blobs)", flush=True)
                return
            print(f"Retry {attempt + 1}: {proc.stderr[-600:]}", flush=True)
            time.sleep(attempt + 1)
        raise RuntimeError(f"Could not fetch batch {index + 1}")

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        list(executor.map(fetch, enumerate(batches)))


if __name__ == "__main__":
    main()
