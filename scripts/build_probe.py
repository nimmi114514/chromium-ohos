#!/usr/bin/env python3
"""Build an actual OHOS ABI probe; this does not build the browser."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from prepare_toolchain import prepare

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    print("+", " ".join(map(str, args)), flush=True)
    result = subprocess.run(list(map(str, args)), check=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-sdk", required=True, type=Path)
    parser.add_argument("--compiler-root", type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    args = parser.parse_args()
    source = args.source.resolve()
    native = args.native_sdk.resolve()
    compiler = (args.compiler_root or native / "llvm").resolve()
    clang = compiler / "bin/clang"
    if not clang.is_file() or not (native / "sysroot/usr/include/unistd.h").is_file():
        raise SystemExit("Linux OHOS compiler and sysroot are required.")
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    revision = run(["git", "-C", source, "rev-parse", "HEAD"]).strip()
    if revision != lock["revision"]:
        raise SystemExit("Source revision does not match versions.json.")
    host_cc = shutil.which("cc")
    if not host_cc:
        raise SystemExit("A Linux host C compiler is required for the regression check.")
    test = ROOT / "tests/platform_buildflags.c"
    run([host_cc, "-std=c11", "-I", source, "-fsyntax-only", test])
    compiler_version = run([clang, "--version"])
    run([clang, "--target=aarch64-linux-ohos", "--sysroot=" + str(native / "sysroot"),
         "-std=c11", "-DTEST_TARGET_OHOS=1", "-I", source, "-fsyntax-only", test])
    build = source / "out/OHOS-ABI"
    gn_args = " ".join([
        'target_os="ohos"', 'target_cpu="arm64"',
        "ohos_sdk_native=" + json.dumps(str(native)),
        "ohos_clang_root=" + json.dumps(str(compiler)),
    ])
    resource = None
    if compiler != (native / "llvm").resolve():
        resource = prepare(native, compiler, ROOT / "toolchain-resources/clang24-ohos")
        gn_args += " ohos_clang_resource_dir=" + json.dumps(str(resource))
    run([ROOT / "tools/gn", "gen", build, "--root=" + str(source),
         "--dotfile=" + str(source / "ohos/bringup/.gn"), "--args=" + gn_args])
    run([ROOT / "tools/ninja", "-C", build, "-j2", "sdk_probe"])
    library = build / "libsdk_probe.so"
    readelf = compiler / "bin/llvm-readelf"
    if not readelf.is_file():
        readelf = shutil.which("readelf")
    if not readelf:
        raise SystemExit("An ELF inspector is required to validate the output.")
    elf = run([readelf, "-h", "-d", library])
    if ("AArch64" not in elf or "[libc.so]" not in elf or "[libc.so.6]" in elf
            or "[libnative_window.so]" not in elf):
        raise SystemExit("Output is not the expected OHOS AArch64/musl shared object.")
    proof = {
        "chromium_revision": revision,
        "compiler": compiler_version,
        "resource_overlay": str(resource) if resource else None,
        "library": str(library),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "elf": elf,
        "host_buildflags": "passed",
        "ohos_buildflags": "passed",
        "scope": "SDK ABI and Chromium platform buildflags only; browser not built",
    }
    (build / "probe-result.json").write_text(json.dumps(proof, indent=2) + "\n")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "abi-probe.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Verified OHOS ABI probe: {library}", flush=True)


if __name__ == "__main__":
    main()
