#!/usr/bin/env python3
"""Prepare DEPS-pinned GN/Ninja and the required nohooks version headers."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    args = parser.parse_args()
    source = args.source.resolve()
    for name in ("logs", "reports", "artifacts", "toolchain-resources", "tools"):
        (ROOT / name).mkdir(exist_ok=True)
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    subprocess.run(["git", "merge-base", "--is-ancestor", lock["revision"], "HEAD"],
                   cwd=source, check=True)
    required = [
        "buildtools/linux64/gn", "third_party/ninja/ninja",
        "third_party/llvm-build/Release+Asserts/bin/clang",
        "third_party/rust-toolchain/bin/rustc",
        "third_party/node/linux/node-linux-x64/bin/node",
        "third_party/node/node_modules/typescript/package.json",
        "build/linux/debian_bullseye_amd64-sysroot/usr/include/stdio.h",
        "build/config/gclient_args.gni",
    ]
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise SystemExit("Incomplete DEPS synchronization; run sync_chromium.py --mirror "
                         "--full --deps first. Missing:\n" + "\n".join(missing))
    for name, binary in (("gn", source / "buildtools/linux64/gn"),
                         ("ninja", source / "third_party/ninja/ninja")):
        if not os.access(binary, os.X_OK):
            raise SystemExit("DEPS binary is not executable: " + str(binary))
        destination = ROOT / "tools" / name
        if not destination.exists() and not destination.is_symlink():
            destination.symlink_to(binary)
        # Existing tools are intentionally preserved for active workspaces.
        print(name + ": " + subprocess.check_output(
            [str(destination), "--version"], text=True).strip())
    script = source / "build/util/lastchange.py"
    commands = [
        ["-o", "build/util/LASTCHANGE"],
        ["--minibranch-out", "build/util/MINIBRANCH"],
        ["-m", "GPU_LISTS_VERSION", "--revision-id-only", "--header",
         "gpu/config/gpu_lists_version.h"],
        ["-m", "SKIA_COMMIT_HASH", "-s", "third_party/skia", "--header",
         "skia/ext/skia_commit_hash.h"],
        ["-m", "DAWN_COMMIT_HASH", "-s", "third_party/dawn", "--revision",
         "gpu/webgpu/DAWN_VERSION", "--header", "gpu/webgpu/dawn_commit_hash.h"],
    ]
    for command in commands:
        subprocess.run(["python3", str(script), *command], cwd=source, check=True)
    print("DEPS build tools and required version files are ready.")


if __name__ == "__main__":
    main()
