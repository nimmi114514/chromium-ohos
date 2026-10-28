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
    revision_pin = json.loads((ROOT / "versions.json").read_text())["chromium"]["revision"]
    for path, name in DEPENDENCIES.items():
        repo = source / path
        entry = subprocess.check_output(
            ["git", "ls-tree", revision_pin, "--", path], cwd=source, text=True)
        mode, kind, revision, _ = entry.split()
        assert mode == "160000" and kind == "commit", path
        subprocess.run(["git", "merge-base", "--is-ancestor", revision, "HEAD"],
                       cwd=repo, check=True)
        tracked = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", revision],
                                        cwd=repo, text=True).splitlines()
        added = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo,
            text=True).splitlines()
        files = tracked + added
        if not files:
            continue
        patch = subprocess.check_output(["git", "diff", "--binary", "--no-renames", revision], cwd=repo)
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
                original = subprocess.run(["git", "show", revision + ":" + file],
                                          cwd=repo, capture_output=True)
                if original.returncode == 0:
                    dest.write_bytes(original.stdout)
            subprocess.run(["git", "init", "--quiet", clean], check=True)
            subprocess.run(["git", "apply", "--check", output / name], cwd=clean, check=True)
            subprocess.run(["git", "apply", output / name], cwd=clean, check=True)
            for file in files:
                actual, expected = clean / file, repo / file
                if actual.exists() != expected.exists() or (
                        actual.exists() and actual.read_bytes() != expected.read_bytes()):
                    raise RuntimeError(f"Dependency patch replay differs: {path}/{file}")
        records.append({"path": path, "revision": revision, "patch": name,
                        "files": files, "sha256": hashlib.sha256(patch).hexdigest(),
                        "replay_matches_worktree": True})
    (output / "series.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"Exported/replayed {len(records)} dependency patches", flush=True)


if __name__ == "__main__":
    export((ROOT / "src").resolve())
