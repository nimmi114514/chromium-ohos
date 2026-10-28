#!/usr/bin/env python3
"""Export and replay the current port against the pinned pristine Git blobs."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from export_dependencies import export as export_dependencies

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    1: "0001-ohos-arm64-build-support.patch",
    2: "0002-ohos-sdk-abi-probe.patch",
    3: "0003-ohos-platform-buildflags.patch",
    4: "0004-ohos-rust-target.patch",
    5: "0005-ohos-base-platform.patch",
    6: "0006-ohos-native-adapter.patch",
    7: "0007-ohos-ui-and-ozone.patch",
    8: "0008-ohos-third-party-platforms.patch",
    9: "0009-ohos-chrome-platform.patch",
    10: "0010-ohos-shared-components.patch",
}


def group(path):
    if path == "build/build_config.h":
        return 3
    if path in ("build/config/rust.gni", "build/rust/known-target-triples.txt"):
        return 4
    if path.startswith("base/"):
        return 5
    if path.startswith("ohos/bringup/"):
        return 2
    if path.startswith(("ohos/adapter/", "third_party/aki/", "third_party/ashmem/",
                        "components/crash/ohos/")):
        return 6
    if path in ("build/config/ozone.gni", "build/config/ui.gni") or path.startswith(
            ("ui/", "build/config/ohos/ozone")):
        return 7
    if path.startswith(("build/", "build_overrides/")):
        return 1
    if path.startswith("chrome/"):
        return 9
    if path in ("tools/metrics/histograms/enums.xml",
                "tools/metrics/histograms/metadata/media/enums.xml"):
        return 10
    if path.startswith(("content/", "components/", "media/", "services/", "net/", "gpu/", "headless/",
                        "device/", "mojo/", "ipc/", "extensions/", "cc/", "skia/", "printing/", "pdf/", "gin/", "sandbox/")):
        return 10
    if path.startswith(("tools/grit/", "tools/variations/", "tools/json_schema_compiler/", "tools/perf/chrome_telemetry_build/", "tools/v8_context_snapshot/",
                        "tools/dump_process_memory/", "tools/metrics/histograms/metadata/password/",
                        "third_party/wiseplay/", "third_party/protobuf/",
                        "third_party/blink/", "third_party/crashpad/crashpad/")) or path in (
                        "third_party/cpuinfo/BUILD.gn", "third_party/zlib/BUILD.gn", "third_party/libxml/BUILD.gn",
                        "third_party/libxslt/BUILD.gn",
                        "third_party/dav1d/BUILD.gn",
                        "third_party/crashpad/crashpad/util/misc/address_types.h",
            "buildtools/third_party/libc++/__config_site"):
        return 8
    raise ValueError(f"Unclassified port change: {path}")


def main():
    source = (ROOT / "src").resolve()
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]

    def git(*args, **kwargs):
        return subprocess.check_output(["git", *args], cwd=source, **kwargs)

    revision = lock["revision"]
    subprocess.run(["git", "merge-base", "--is-ancestor", revision, "HEAD"],
                   cwd=source, check=True)
    # Export from the upstream pin, including port changes already committed
    # locally. HEAD is a checkpoint, not necessarily the pristine source.
    tracked = git("diff", "--ignore-submodules=all", "--no-renames",
                  "--name-only", revision, text=True).splitlines()
    added = git("ls-files", "--others", "--exclude-standard", text=True).splitlines()
    buckets = collections.defaultdict(list)
    for path in tracked + added:
        buckets[group(path)].append(path)
    for key, name in GROUPS.items():
        paths = sorted(buckets[key])
        common = [p for p in paths if p in tracked]
        patch = git("diff", "--binary", "--no-renames", revision, "--", *common) if common else b""
        for path in paths:
            if path not in added:
                continue
            diff = subprocess.run(["git", "diff", "--no-index", "--binary", "--",
                                   "/dev/null", path], cwd=source, capture_output=True)
            if diff.returncode != 1:
                raise RuntimeError(f"Cannot export {path}: {diff.stderr.decode()}")
            patch += diff.stdout
        (ROOT / "patches" / name).write_bytes(patch)
    (ROOT / "patches/series").write_text("\n".join(GROUPS.values()) + "\n")
    # Keep the readable overlay aligned with the actual new build files.
    for path in tracked + added:
        if path.startswith(("build/config/ohos/", "build/toolchain/ohos/", "ohos/bringup/")):
            dest = ROOT / "overlay" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((source / path).read_bytes())
    with tempfile.TemporaryDirectory(prefix="chromium158-patch-replay-") as directory:
        clean = Path(directory)
        subprocess.run(["git", "init", "--quiet", clean], check=True)
        for path in tracked:
            dest = clean / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            original = subprocess.run(["git", "show", revision + ":" + path],
                                      cwd=source, capture_output=True)
            if original.returncode == 0:
                dest.write_bytes(original.stdout)
            elif (source / path).exists():
                # A committed addition has no pristine blob to seed.
                subprocess.run(["git", "cat-file", "-e", revision],
                               cwd=source, check=True)
        for name in GROUPS.values():
            patch = ROOT / "patches" / name
            subprocess.run(["git", "apply", "--check", patch], cwd=clean, check=True)
            subprocess.run(["git", "apply", patch], cwd=clean, check=True)
        for path in tracked + added:
            actual, expected = clean / path, source / path
            if actual.exists() != expected.exists() or (
                    actual.exists() and actual.read_bytes() != expected.read_bytes()):
                raise RuntimeError(f"Patch replay differs: {path}")
    report = {"revision": lock["revision"], "tracked_files": len(tracked),
              "added_files": len(added), "replay_matches_worktree": True,
              "patches": [{"name": name, "files": len(buckets[key]),
                           "sha256": hashlib.sha256((ROOT / "patches" / name).read_bytes()).hexdigest()}
                          for key, name in GROUPS.items()]}
    (ROOT / "reports/patch-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Exported/replayed {len(tracked)} modified and {len(added)} new files", flush=True)
    export_dependencies(source)


if __name__ == "__main__":
    main()
