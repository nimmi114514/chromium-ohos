#!/usr/bin/env python3
"""Combine Google Clang headers with the SDK's OHOS compiler-rt resources.

This is a bootstrap resource overlay, not a rebuild of compiler-rt 24.
The downloaded Google compiler and SDK remain untouched.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TRIPLE = "aarch64-linux-ohos"


def link(source, destination):
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"Refusing to replace {destination}")
    destination.symlink_to(source.resolve(), target_is_directory=source.is_dir())


def prepare(native, compiler, destination, sdk_resource=None):
    native, compiler, destination = native.resolve(), compiler.resolve(), destination.resolve()
    query = lambda clang: Path(subprocess.check_output(
        [str(clang), "--print-resource-dir"], text=True).strip()).resolve()
    google_resource = query(compiler / "bin/clang")
    # Installed Windows SDKs provide the same target runtime but their Clang
    # executable cannot serve as the Linux build compiler.
    sdk_resource = (sdk_resource.resolve() if sdk_resource is not None
                    else query(native / "llvm/bin/clang"))
    runtime = sdk_resource / "lib" / TRIPLE
    if not (runtime / "libclang_rt.builtins.a").is_file():
        raise RuntimeError(f"Missing OHOS compiler-rt builtins in {runtime}")
    destination.mkdir(parents=True, exist_ok=True)
    for child in google_resource.iterdir():
        if child.name != "lib":
            link(child, destination / child.name)
    (destination / "lib").mkdir(exist_ok=True)
    if (google_resource / "lib").is_dir():
        for child in (google_resource / "lib").iterdir():
            if child.name != TRIPLE:
                link(child, destination / "lib" / child.name)
    target = destination / "lib" / TRIPLE
    target.mkdir(exist_ok=True)
    for child in runtime.iterdir():
        link(child, target / child.name)
    # The old OHOS driver used compiler-rt names. Upstream's current driver
    # searches these conventional CRT names; retain the real SDK objects.
    aliases = {"crtbeginS.o": "clang_rt.crtbegin.o", "crtendS.o": "clang_rt.crtend.o",
               "crtbegin.o": "clang_rt.crtbegin.o", "crtend.o": "clang_rt.crtend.o"}
    for name, old in aliases.items():
        if not (target / name).exists():
            if not (runtime / old).is_file():
                raise RuntimeError(f"SDK does not provide {old}")
            link(runtime / old, target / name)
    provenance = {"google_resource": str(google_resource), "sdk_runtime": str(runtime),
                  "scope": "Bootstrap with SDK runtime objects; compiler-rt 24 not rebuilt"}
    metadata = native / "oh-uni-package.json"
    if metadata.is_file():
        provenance["sdk"] = json.loads(metadata.read_text())
    (destination / "resource-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-sdk", required=True, type=Path)
    parser.add_argument("--sdk-resource-dir", type=Path,
                        help="Clang resource directory from an installed SDK")
    parser.add_argument("--compiler-root", type=Path,
                        default=ROOT / "src/third_party/llvm-build/Release+Asserts")
    parser.add_argument("--output", type=Path, default=ROOT / "toolchain-resources/clang24-ohos")
    args = parser.parse_args()
    print(prepare(args.native_sdk, args.compiler_root, args.output,
                  args.sdk_resource_dir), flush=True)


if __name__ == "__main__":
    main()
