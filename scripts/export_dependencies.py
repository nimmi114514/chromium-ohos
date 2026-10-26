#!/usr/bin/env python3
"""Export and replay OHOS edits in official DEPS Git repositories."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {
    "v8": "v8-ohos-metagen.patch",
    "third_party/dawn": "dawn-ohos.patch",
    "third_party/swiftshader": "swiftshader-ohos.patch",
    "third_party/webrtc": "webrtc-ohos.patch",
    "third_party/skia": "skia-ohos-fonts.patch",
    "third_party/angle": "angle-ohos-egl.patch",
    "third_party/ffmpeg": "ffmpeg-ohos-config.patch",
    "third_party/vulkan-loader/src": "vulkan-loader-ohos.patch",
    "third_party/pdfium": "pdfium-ohos-fonts.patch",
}


def export(source):
    output = ROOT / "dependency-patches"
    output.mkdir(exist_ok=True)
    records = []
    for path, name in DEPENDENCIES.items():
        repo = source / path
        entry = subprocess.check_output(
            ["git", "ls-tree", "HEAD", "--", path], cwd=source, text=True)
        mode, kind, revision, _ = entry.split()
        assert mode == "160000" and kind == "commit", path
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=repo, text=True).strip()
        if actual != revision:
            raise RuntimeError(f"Dependency revision differs from Chromium pin: {path}")
        tracked = subprocess.check_output(["git", "diff", "--name-only", "HEAD"],
                                        cwd=repo, text=True).splitlines()
        added = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo,
            text=True).splitlines()
        files = tracked + added
        if not files:
            continue
        patch = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=repo)
        for file in added:
            diff = subprocess.run(["git", "diff", "--no-index", "--binary", "--",
                                   "/dev/null", file], cwd=repo, capture_output=True)
            if diff.returncode != 1:
                raise RuntimeError(f"Cannot export new dependency file: {path}/{file}")
            patch += diff.stdout
        (output / name).write_bytes(patch)
        with tempfile.TemporaryDirectory(prefix="ohos-dependency-replay-") as directory:
            clean = Path(directory)
            for file in tracked:
                dest = clean / file
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(subprocess.check_output(
                    ["git", "show", "HEAD:" + file], cwd=repo))
            subprocess.run(["git", "init", "--quiet", clean], check=True)
            subprocess.run(["git", "apply", "--check", output / name], cwd=clean, check=True)
            subprocess.run(["git", "apply", output / name], cwd=clean, check=True)
            for file in files:
                if (clean / file).read_bytes() != (repo / file).read_bytes():
                    raise RuntimeError(f"Dependency patch replay differs: {path}/{file}")
        records.append({"path": path, "revision": revision, "patch": name,
                        "files": files, "sha256": hashlib.sha256(patch).hexdigest(),
                        "replay_matches_worktree": True})
    (output / "series.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Exported/replayed {len(records)} dependency patches", flush=True)


if __name__ == "__main__":
    export((ROOT / "src").resolve())
