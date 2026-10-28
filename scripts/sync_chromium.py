#!/usr/bin/env python3
"""Fetch pinned Google Chromium; optionally sync its official DEPS with gclient."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True,
                   env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1",
                        "DEPOT_TOOLS_UPDATE": "0"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", action="store_true", help="Sync official DEPS with gclient")
    parser.add_argument("--full", action="store_true", help="Expand the full Chromium source checkout")
    parser.add_argument("--mirror", action="store_true", help="Use Google's official GitHub mirror")
    args = parser.parse_args()
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    source = (ROOT / "src").resolve()
    checkout_root = source.parent
    if not (source / ".git").exists():
        run("git", "init", source)
    remote = "github" if args.mirror else "origin"
    remotes = subprocess.check_output(["git", "-C", str(source), "remote"], text=True).splitlines()
    url = lock["mirror"] if args.mirror else lock["url"]
    if remote not in remotes:
        run("git", "-C", source, "remote", "add", remote, url)
    else:
        actual = subprocess.check_output(["git", "-C", str(source), "remote", "get-url", remote], text=True).strip()
        if actual != url:
            raise SystemExit(f"Unexpected {remote} URL: {actual}")
    changes = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    pinned = head.returncode == 0 and head.stdout.strip() == lock["revision"]
    if changes and not pinned:
        raise SystemExit("Source has local changes at a different revision; refusing to switch it.")
    if pinned:
        print("Source already pinned; preserving local port changes.", flush=True)
    else:
        run("git", "-C", source, "-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=60",
            "fetch", "--depth=1", "--filter=tree:0", remote, lock["revision"])
        # Keep the first checkout small while porting the build system.
        run("git", "-C", source, "sparse-checkout", "set", "--cone", "build", "build_overrides",
            "tools/clang", "tools/rust", "chrome/build", "ui/ozone")
        run("git", "-C", source, "checkout", "--detach", lock["revision"])
    if args.deps:
        if changes:
            raise SystemExit("Do not synchronize dependencies over port changes. "
                             "Use a pristine checkout before apply_port.py.")
        if not shutil.which("gclient"):
            raise SystemExit("Put Google depot_tools on PATH before --deps.")
        sparse = subprocess.run(["git", "-C", str(source), "sparse-checkout", "list"],
                                text=True, capture_output=True)
        if sparse.returncode == 0:
            # gclient reads CIPD version_file entries even for disabled
            # platforms. Include the real pinned metadata, never dummy files.
            entries = re.findall(r"['\"]version_file['\"]\s*:\s*['\"]([^'\"]+)['\"]",
                                 (source / "DEPS").read_text())
            directories = sorted({str(Path(path).parent) for path in entries})
            if directories:
                run("git", "-C", source, "sparse-checkout", "add", *directories)
        config = "solutions = " + repr([{"name": "src", "url": url,
                    "managed": False, "custom_deps": {}, "custom_vars": {}}]) + "\n"
        path = checkout_root / ".gclient"
        if path.exists() and path.read_text() != config:
            raise SystemExit("Existing .gclient differs; refusing to overwrite it.")
        path.write_text(config)
        # managed=False preserves the pinned source and local patches. Passing
        # --revision would override that mode and make gclient reject the dirty
        # source checkout. Every dependency is still pinned by this source DEPS.
        run("gclient", "sync", "--nohooks", "--no-history", "--jobs=2", cwd=checkout_root)
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != lock["revision"]:
            raise SystemExit("Source revision changed during dependency synchronization.")
    if args.full:
        run("git", "-C", source, "sparse-checkout", "disable")


if __name__ == "__main__":
    main()
