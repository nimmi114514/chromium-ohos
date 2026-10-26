#!/usr/bin/env python3
"""Download the reference SDK in resumable ranges and verify its LFS SHA-256."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--cache", type=Path, default=ROOT / "downloads/sdk-parts")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    lock = json.loads((ROOT / "versions.json").read_text())["sdk_reference"]
    output = args.output or ROOT / "downloads" / lock["name"]
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size == lock["size"]:
        if digest(output) == lock["sha256"]:
            print(f"SDK already verified: {output}", flush=True)
            return
        raise SystemExit("Existing SDK has the expected size but the wrong SHA-256.")
    args.cache.mkdir(parents=True, exist_ok=True)
    chunk_size = 4 * 1024 * 1024
    count = (lock["size"] + chunk_size - 1) // chunk_size

    def fetch(index):
        start = index * chunk_size
        end = min(start + chunk_size, lock["size"]) - 1
        path = args.cache / f"{index:05d}"
        if path.exists() and path.stat().st_size == end - start + 1:
            return
        last_error = None
        for attempt in range(5):
            try:
                request = urllib.request.Request(
                    lock["url"] + f"?range={start}-{end}",
                    headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    expected = f"bytes {start}-{end}/{lock['size']}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise ValueError(f"Server did not honor requested range: {response.headers}")
                    data = response.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise ValueError(f"Truncated range {index}: {len(data)} bytes")
                temporary = path.with_suffix(".part")
                temporary.write_bytes(data)
                os.replace(temporary, path)
                return
            except Exception as error:
                last_error = error
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"Range {index} failed: {last_error}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(fetch, index) for index in range(count)]
        for completed, job in enumerate(as_completed(jobs), 1):
            job.result()
            if completed % 16 == 0 or completed == count:
                print(f"SDK ranges complete: {completed}/{count}", flush=True)
    temporary = output.with_suffix(output.suffix + ".verified-part")
    result = hashlib.sha256()
    with temporary.open("wb") as stream:
        for index in range(count):
            data = (args.cache / f"{index:05d}").read_bytes()
            stream.write(data)
            result.update(data)
    if result.hexdigest() != lock["sha256"]:
        raise SystemExit("SDK SHA-256 mismatch; archive has not been installed.")
    os.replace(temporary, output)
    print(f"SDK verified: {output}\nSHA-256: {result.hexdigest()}", flush=True)


if __name__ == "__main__":
    main()
