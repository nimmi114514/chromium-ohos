#!/usr/bin/env python3
"""Verify the reference archive and extract only the Linux native SDK."""
import argparse
import json
from pathlib import Path
import tarfile

from fetch_sdk import digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    lock = json.loads((ROOT / "versions.json").read_text())["sdk_reference"]
    marker = args.destination / "sdk-source.json"
    if marker.exists() and json.loads(marker.read_text())["sha256"] == lock["sha256"]:
        print(f"SDK already installed: {args.destination}", flush=True)
        return
    if args.destination.exists():
        raise SystemExit("Destination exists without matching provenance; refusing to overwrite.")
    if args.archive.stat().st_size != lock["size"] or digest(args.archive) != lock["sha256"]:
        raise SystemExit("SDK archive does not match the pinned LFS size/SHA-256.")
    staging = args.destination.with_name(args.destination.name + ".installing")
    staging.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with tarfile.open(args.archive, "r|gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if name == "openharmony/native" or name.startswith("openharmony/native/"):
                archive.extract(member, staging, filter="data")
                extracted += 1
    if not (staging / "openharmony/native/llvm/bin/clang").is_file():
        raise SystemExit("Archive does not contain the expected Linux native compiler.")
    (staging / "sdk-source.json").write_text(json.dumps(lock, indent=2) + "\n")
    staging.rename(args.destination)
    print(f"Extracted {extracted} native SDK members to {args.destination}", flush=True)


if __name__ == "__main__":
    main()
