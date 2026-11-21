#!/usr/bin/env python3
"""Regression coverage for exports from unstaged, staged and committed ports."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import export_dependencies
import export_port
from patch_export import change_counts, export_patch, git_paths, path_order


def git(repo, *args, input=None):
    return subprocess.check_output(["git", *args], cwd=repo, input=input,
                                   stderr=subprocess.PIPE)


def init(repo):
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Patch export regression")
    git(repo, "config", "user.email", "patch-export@example.invalid")
    git(repo, "config", "core.filemode", "true")
    git(repo, "config", "commit.gpgsign", "false")


def write(repo, path, data, mode=None):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)
    if mode is not None:
        file.chmod(mode)


def commit(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def changes(repo, revision):
    tracked = git_paths(repo, "diff", "--ignore-submodules=all", "--no-renames",
                        "--name-only", revision)
    added = git_paths(repo, "ls-files", "--others", "--exclude-standard")
    return path_order(tracked + added), added


class PatchExportTests(unittest.TestCase):
    def test_identical_patch_in_each_index_state(self):
        with tempfile.TemporaryDirectory(prefix="patch-export-states-") as directory:
            repo = Path(directory) / "src"
            init(repo)
            write(repo, "a-modified.txt", b"original\n")
            write(repo, "z-deleted.txt", b"deleted\n")
            write(repo, "binary.bin", bytes(range(256)))
            write(repo, "mode.sh", b"#!/bin/sh\nexit 0\n")
            revision = commit(repo, "pristine pin")
            write(repo, "a-modified.txt", b"modified\n")
            (repo / "z-deleted.txt").unlink()
            write(repo, "binary.bin", bytes(reversed(range(256))))
            (repo / "mode.sh").chmod(0o755)
            write(repo, "a-added.txt", b"added\n")
            write(repo, "empty.txt", b"")
            write(repo, "new binary.bin", b"\x00\xff\x01\x00")
            write(repo, "new script.sh", b"#!/bin/sh\nexit 0\n", 0o755)
            write(repo, "quote\" and \u4e2d\u6587.txt", b"no final newline")
            write(repo, "line\nbreak.txt", b"text\rdiff --git not-a-header\n")
            (repo / "link").symlink_to("a-added.txt")
            # A developer's custom order must not reorder file blocks.
            order = repo / ".git/reversed-order"
            order.write_text("z*\nnew*\na*\n")
            git(repo, "config", "diff.orderFile", str(order))
            expected = None
            for state in ["untracked", "mixed", "intent-to-add", "staged", "checkpoint"]:
                if state == "mixed":
                    git(repo, "add", "--", "a-added.txt")
                elif state == "intent-to-add":
                    git(repo, "add", "--intent-to-add", "--all")
                elif state == "staged":
                    git(repo, "add", "--all")
                elif state == "checkpoint":
                    commit(repo, "local checkpoint")
                with self.subTest(state=state):
                    before_index = (repo / ".git/index").read_bytes()
                    before_head = git(repo, "rev-parse", "HEAD")
                    files, added = changes(repo, revision)
                    exported = export_patch(repo, revision, files, added)
                    self.assertEqual(before_index, (repo / ".git/index").read_bytes())
                    self.assertEqual(before_head, git(repo, "rev-parse", "HEAD"))
                    if expected is None:
                        expected = exported
                    self.assertEqual(expected, exported)
                    self.assertEqual(change_counts([exported]), {
                        "modified_files": 3, "added_files": 7, "deleted_files": 1,
                    })
            self.assertIn(b"GIT binary patch", expected)
            clean = Path(directory) / "replay"
            git(Path(directory), "clone", "--quiet", "--no-hardlinks", str(repo), str(clean))
            git(clean, "checkout", "--quiet", revision)
            git(clean, "apply", "--check", "-", input=expected)
            git(clean, "apply", "-", input=expected)
            for name in files:
                actual, original = clean / name, repo / name
                self.assertEqual(actual.exists(), original.exists(), name)
                self.assertEqual(actual.is_symlink(), original.is_symlink(), name)
                if original.is_symlink():
                    self.assertEqual(os.readlink(actual), os.readlink(original), name)
                elif original.exists():
                    self.assertEqual(actual.read_bytes(), original.read_bytes(), name)
                    self.assertEqual(actual.stat().st_mode & 0o111,
                                     original.stat().st_mode & 0o111, name)

    def test_main_and_dependency_exports_are_reproducible(self):
        with tempfile.TemporaryDirectory(prefix="patch-export-integration-") as directory:
            root = Path(directory)
            source, dep = root / "src", root / "src/third_party/dawn"
            init(source)
            init(dep)
            write(dep, "z-existing.cc", b"original\n")
            commit(dep, "dependency pin")
            write(source, "build/z-existing.gni", b"original\n")
            write(source, "base/z-existing.cc", b"original\n")
            write(source, "components/z-existing.cc", b"original\n")
            revision = commit(source, "Chromium pin with dependency gitlink")
            write(source, "build/z-existing.gni", b"changed\n")
            write(source, "base/z-existing.cc", b"changed\n")
            write(source, "components/z-existing.cc", b"changed\n")
            write(source, "build/config/ohos/a-added.gni", b"added\n")
            write(source, "base/a-added.cc", b"added\n")
            write(source, "components/a-added.cc", b"added\n")
            write(dep, "z-existing.cc", b"changed\n")
            write(dep, "a-added.cc", b"added\n")
            (root / "versions.json").write_text(
                '{"chromium":{"revision":"' + revision + '"}}\n')
            (root / "patches").mkdir()
            (root / "reports").mkdir()
            groups = {1: "0001.patch", 5: "0005.patch", 10: "0010.patch"}
            def run():
                with contextlib.redirect_stdout(io.StringIO()):
                    export_port.main()
                return {str(file.relative_to(root)): file.read_bytes()
                        for folder in ["patches", "overlay", "dependency-patches", "reports"]
                        for file in (root / folder).rglob("*") if file.is_file()}
            with patch.object(export_port, "ROOT", root), \
                    patch.object(export_port, "GROUPS", groups), \
                    patch.object(export_dependencies, "ROOT", root), \
                    patch.object(export_dependencies, "DEPENDENCIES",
                                 {"third_party/dawn": "dawn.patch"}):
                expected = run()
                self.assertEqual(expected, run(), "unchanged export")
                git(source, "add", "--intent-to-add", "--all")
                git(dep, "add", "--intent-to-add", "--all")
                self.assertEqual(expected, run(), "intent-to-add export")
                git(source, "add", "--all")
                git(dep, "add", "--all")
                self.assertEqual(expected, run(), "staged export")
                commit(dep, "dependency checkpoint")
                commit(source, "Chromium checkpoint")
                self.assertEqual(expected, run(), "checkpoint export")


if __name__ == "__main__":
    unittest.main(verbosity=2)
