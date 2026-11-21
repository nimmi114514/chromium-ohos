"""Build patches in path order, independently of additions' index state."""
import os
import re
import subprocess


def git_paths(repo, *args):
    """Read Git's NUL-separated paths without interpreting quoted filenames."""
    output = subprocess.check_output(["git", *args, "-z"], cwd=repo)
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def path_order(paths):
    # Git sorts path bytes, not locale-dependent display names.
    return sorted(set(paths), key=os.fsencode)


def diff_blocks(patch):
    """Split complete file diffs; hunk contents retain their original order."""
    if not patch:
        return []
    starts = [match.start() for match in re.finditer(rb"(?m)^diff --git ", patch)]
    if not starts or starts[0] != 0:
        raise RuntimeError("Unexpected data before a Git file diff")
    return [patch[start:end] for start, end in zip(starts, starts[1:] + [len(patch)])]


def export_patch(repo, revision, paths, untracked):
    """Merge tracked and untracked file diffs into one canonical sequence.

    Read only the source repository. No git add, checkpoint commit, or real
    index changes are needed. Disable custom diff ordering and external/text
    conversion helpers so both routes emit applicable Git patches.
    """
    paths = path_order(paths)
    untracked = set(untracked)
    tracked = [path for path in paths if path not in untracked]
    blocks = {}
    if tracked:
        patch = subprocess.check_output([
            "git", "diff", "--binary", "--no-renames", "--no-ext-diff",
            "--no-textconv", "-O/dev/null", revision, "--", *tracked,
        ], cwd=repo)
        sections = diff_blocks(patch)
        if len(sections) != len(tracked):
            raise RuntimeError("Git file diff count differs from changed paths")
        blocks.update(zip(tracked, sections))
    for path in paths:
        if path not in untracked:
            continue
        diff = subprocess.run([
            "git", "diff", "--no-index", "--binary", "--no-ext-diff",
            "--no-textconv", "--", "/dev/null", path,
        ], cwd=repo, capture_output=True)
        if diff.returncode != 1:
            raise RuntimeError(f"Cannot export {path}: {os.fsdecode(diff.stderr)}")
        sections = diff_blocks(diff.stdout)
        if len(sections) != 1:
            raise RuntimeError(f"Expected one new-file diff: {path}")
        blocks[path] = sections[0]
    return b"".join(blocks[path] for path in paths)


def change_counts(patches):
    """Count changes relative to the pin, rather than the developer's index."""
    sections = [block for patch in patches for block in diff_blocks(patch)]
    added = sum(b"\nnew file mode " in block for block in sections)
    deleted = sum(b"\ndeleted file mode " in block for block in sections)
    return {"modified_files": len(sections) - added - deleted,
            "added_files": added, "deleted_files": deleted}
