#!/usr/bin/env python3
"""Import the installed DevEco API 26 native SDK for Linux cross compilation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from prepare_toolchain import prepare

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path("openharmony/native")
PARTS = [NATIVE / "sysroot", NATIVE / "build",
         NATIVE / "llvm/lib/clang/15.0.4/lib/aarch64-linux-ohos",
         NATIVE / "llvm/lib/aarch64-linux-ohos"]
KEY_FILES = ["sysroot/usr/lib/aarch64-linux-ohos/libc.so",
             "sysroot/usr/lib/aarch64-linux-ohos/libnative_window.so",
             "sysroot/usr/lib/aarch64-linux-ohos/libEGL.so",
             "llvm/lib/clang/15.0.4/lib/aarch64-linux-ohos/libclang_rt.builtins.a",
             "llvm/lib/clang/15.0.4/lib/aarch64-linux-ohos/clang_rt.crtbegin.o"]


def activate_link(link, target):
    if link.exists() and not link.is_symlink():
        raise RuntimeError(f"Refusing to replace a real directory: {link}")
    temporary = link.with_name(link.name + ".api26-new")
    if temporary.exists() or temporary.is_symlink():
        raise RuntimeError(f"Temporary link already exists: {temporary}")
    temporary.symlink_to(target, target_is_directory=True)
    os.replace(temporary, link)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, default=Path(
        "/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default"))
    parser.add_argument("--output", type=Path,
                        default=(ROOT / "src").resolve().parent / "sdk-api26")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "toolchain-resources").mkdir(exist_ok=True)
    source, destination = args.sdk_root.resolve(), args.output.resolve()
    metadata = json.loads((source / "sdk-pkg.json").read_text())
    if str(metadata["data"]["apiVersion"]) != "26":
        raise SystemExit("The installed SDK must be API 26")
    marker = destination / "sdk-source.json"
    record = json.loads(marker.read_text()) if marker.exists() else {}
    ready = (record.get("sdk") == metadata["data"] and
             all((destination / part).is_dir() for part in PARTS) and
             all((destination / NATIVE / f).is_file() for f in KEY_FILES))
    if not ready or args.refresh:
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "sdk-pkg.json", destination / "sdk-pkg.json")
        for part in PARTS:
            print(f"Copying {part}", flush=True)
            shutil.copytree(source / part, destination / part,
                            dirs_exist_ok=True, symlinks=True)
        for name in ["oh-uni-package.json", "compatible_config.json",
                     "nativeapi_syscap_config.json", "ndk_system_capability.json",
                     "NOTICE.txt"]:
            shutil.copy2(source / NATIVE / name, destination / NATIVE / name)
        record = {"source": str(source), "sdk": metadata["data"],
                  "copied_parts": list(map(str, PARTS)), "native_files": {}}
        for name in KEY_FILES:
            file = destination / NATIVE / name
            record["native_files"][name] = {
                "size": file.stat().st_size,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        record["scope"] = "API 26 native files for the Linux Google Clang build"
        marker.write_text(json.dumps(record, indent=2) + "\n")
    resource = ROOT / "toolchain-resources/clang24-ohos-api26"
    prepare(destination / NATIVE, ROOT / "src/third_party/llvm-build/Release+Asserts",
            resource, destination / NATIVE / "llvm/lib/clang/15.0.4")
    activate_link(ROOT / "sdk", destination)
    activate_link(ROOT / "src/ohos_sdk", destination)
    versions = ROOT / "versions.json"
    lock = json.loads(versions.read_text())
    lock["active_sdk"] = {"api_version": 26,
                          "platform_version": metadata["data"]["platformVersion"],
                          "version": metadata["data"]["version"],
                          "release_type": metadata["data"]["releaseType"],
                          "source": str(source), "native_mirror": str(destination),
                          "resource_overlay": "toolchain-resources/clang24-ohos-api26"}
    versions.write_text(json.dumps(lock, indent=2) + "\n")
    (ROOT / "reports/sdk-api26.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Selected API 26 SDK {metadata['data']['version']}", flush=True)


if __name__ == "__main__":
    main()
