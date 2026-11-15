#!/usr/bin/env python3
"""Regenerate patches/0011-ohos-hwc-background.patch from the worktree.

0011 is not part of export_port.py's groups: it holds the hardware composition
surface-background port on top of 0001-0010. This script replays 0001-0010 for
the files that 0011 touches and diffs the result against the worktree, so the
patch can be replayed on a pristine tree.
"""

import os
import subprocess
import sys
import tempfile

SRC = "/home/cnoim/chromium-build/158.0.8116.0/src"
ROOT = "/mnt/d/chromium/chromium-ohos"
REV = "566635fe3ce2912169a6ca76a00a7ee1d8e400e9"
OUT = os.path.join(ROOT, "patches/0011-ohos-hwc-background.patch")

BASE_PATCHES = [
    "0001-ohos-arm64-build-support.patch",
    "0002-ohos-sdk-abi-probe.patch",
    "0003-ohos-platform-buildflags.patch",
    "0004-ohos-rust-target.patch",
    "0005-ohos-base-platform.patch",
    "0006-ohos-native-adapter.patch",
    "0007-ohos-ui-and-ozone.patch",
    "0008-ohos-third-party-platforms.patch",
    "0009-ohos-chrome-platform.patch",
    "0010-ohos-shared-components.patch",
]

FILES = [
    "ohos/adapter/window/window_common.h",
    "ohos/adapter/window/window_common.cc",
    "ohos/adapter/xcomponent/xcomponent_manager.h",
    "ohos/adapter/xcomponent/xcomponent_manager.cc",
    "ui/views/widget/desktop_aura/desktop_window_tree_host_ohos.h",
    "ui/views/widget/desktop_aura/desktop_window_tree_host_ohos.cc",
    "ui/ozone/platform/ohos/host/ohos_toplevel_window.h",
    "ui/ozone/platform/ohos/host/ohos_toplevel_window.cc",
    "chrome/browser/ui/views/frame/browser_view.cc",
]


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, capture_output=True, **kwargs)


def main():
    work = tempfile.mkdtemp(prefix="hwc-base-")
    run(["git", "init", "-q"], cwd=work)

    for rel in FILES:
        blob = subprocess.run(["git", "show", "%s:%s" % (REV, rel)],
                              cwd=SRC, capture_output=True)
        if blob.returncode != 0:
            continue
        path = os.path.join(work, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(blob.stdout)

    for name in BASE_PATCHES:
        patch = os.path.join(ROOT, "patches", name)
        cmd = ["git", "apply", "--whitespace=nowarn", patch]
        for rel in FILES:
            cmd.append("--include=%s" % rel)
        result = subprocess.run(cmd, cwd=work, capture_output=True)
        if result.returncode != 0:
            print("FAILED applying %s:\n%s" % (name, result.stderr.decode()))
            return 1

    chunks = []
    for rel in FILES:
        base = os.path.join(work, rel)
        now = os.path.join(SRC, rel)
        if not os.path.exists(base):
            print("MISSING base for %s" % rel)
            return 1
        with open(base, "rb") as handle:
            base_bytes = handle.read()
        with open(now, "rb") as handle:
            now_bytes = handle.read()
        if base_bytes == now_bytes:
            print("unchanged %s" % rel)
            continue
        diff = subprocess.run(
            ["diff", "-u", "--label", "a/" + rel, "--label", "b/" + rel,
             base, now], capture_output=True)
        if diff.returncode != 1:
            print("diff failed for %s: %s" % (rel, diff.stderr.decode()))
            return 1
        chunks.append(b"diff --git a/%s b/%s\n" % (rel.encode(), rel.encode()))
        chunks.append(diff.stdout)
        print("changed   %s" % rel)

    with open(OUT, "wb") as handle:
        handle.write(b"".join(chunks))

    # Verify the patch applies on top of 0001-0010 and reproduces the worktree.
    check = subprocess.run(["git", "apply", "--check", "--whitespace=nowarn",
                            OUT], cwd=work, capture_output=True)
    if check.returncode != 0:
        print("new 0011 does not apply:\n%s" % check.stderr.decode())
        return 1
    run(["git", "apply", "--whitespace=nowarn", OUT], cwd=work)
    for rel in FILES:
        with open(os.path.join(work, rel), "rb") as handle:
            replayed = handle.read()
        with open(os.path.join(SRC, rel), "rb") as handle:
            actual = handle.read()
        if replayed != actual:
            print("replay differs: %s" % rel)
            return 1

    print("Wrote %s (%d files)" % (OUT, len(FILES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
