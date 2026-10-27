#!/usr/bin/env python3
"""Resume the pinned Chromium OHOS build using the real upstream GN graph."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("base", "v8", "chrome"), default="chrome")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--keep-going", type=int, default=1, metavar="N",
                        help="Stop after N failed tasks; 0 builds all independent tasks")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--v8-logging-level", type=int, choices=(0, 1, 2),
                        help="Override V8 fatal diagnostics without changing the release/DCHECK profile")
    parser.add_argument("--diagnostic-build", action="store_true",
                        help="Enable DCHECKs for local diagnosis; release defaults to the 132 official-build profile")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.keep_going < 0:
        parser.error("--keep-going must not be negative")
    source = (ROOT / "src").resolve()
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source,
                                     text=True).strip()
    if actual != lock["revision"]:
        raise SystemExit("Chromium source revision differs from versions.json")
    native = (ROOT / "sdk/openharmony/native").resolve()
    sdk_metadata = json.loads((native / "oh-uni-package.json").read_text())
    if str(sdk_metadata.get("apiVersion")) != "26":
        raise SystemExit("The selected SDK must be API 26")
    resource = (ROOT / "toolchain-resources/clang24-ohos-api26").resolve()
    if not (resource / "include/stddef.h").is_file():
        raise SystemExit("Prepare the OHOS toolchain resource overlay first")
    # Reuse cross-compiled base, libc++, Rust and snapshot tools at each stage.
    out = source / "out/OHOS"
    out.mkdir(parents=True, exist_ok=True)
    profile = [
        'target_os = "ohos"', 'target_cpu = "arm64"',
        # The mature OHOS 132 release uses the official profile. Merely setting
        # is_debug=false still enables expensive DCHECKs in current Chromium,
        # including Viz's blue diagnostic clear of opaque render passes.
        "is_official_build = " + ("false" if args.diagnostic_build else "true"),
        "is_debug = false", "is_component_build = false", "symbol_level = 0",
        "use_thin_lto = false", "use_remoteexec = false",
        "clang_use_chrome_plugins = false", "treat_warnings_as_errors = false",
        "ohos_clang_resource_dir = " + json.dumps(str(resource)),
        "ohos_sdk_native = " + json.dumps(str(native)),
    ]
    if args.stage == "chrome":
        profile += ["use_kerberos = false", "enable_supervised_users = true",
                    "use_crash_key_stubs = false",
                    # Match the OHOS 132 release media profile. Chromium's
                    # unbranded defaults exclude H.264/AAC MIME support and
                    # FFmpeg decoders, regardless of available OHOS hardware.
                    "proprietary_codecs = true", 'ffmpeg_branding = "Chrome"',
                    "media_use_ffmpeg = true", "media_use_openh264 = true"]
    if args.v8_logging_level is not None:
        profile.append(f"v8_logging_level = {args.v8_logging_level}")
    (out / "args.gn").write_text("\n".join(profile) + "\n")
    commands = [[ROOT / "tools/gn", "gen", out,
                 "--root-target=//" + args.stage]]
    if not args.generate_only:
        target = "chrome_main_web" if args.stage == "chrome" else args.stage
        commands.append([ROOT / "tools/ninja", "-C", out,
                         "-j" + str(args.jobs), "-k", str(args.keep_going), target])
    for command in commands:
        print("+", " ".join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), cwd=source, check=True)


if __name__ == "__main__":
    main()
