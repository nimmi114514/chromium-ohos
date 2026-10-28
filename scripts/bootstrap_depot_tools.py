#!/usr/bin/env python3
"""Fetch the reviewed depot_tools revision without updating an existing checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "tools/depot_tools")
    args = parser.parse_args()
    lock = json.loads((ROOT / "versions.json").read_text())["depot_tools"]
    destination = args.destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DEPOT_TOOLS_UPDATE": "0"}
    if not destination.exists():
        subprocess.run(["git", "init", str(destination)], check=True, env=env)
        subprocess.run(["git", "-C", str(destination), "remote", "add", "origin",
                        lock["url"]], check=True, env=env)
        subprocess.run(["git", "-C", str(destination), "fetch", "--depth=1",
                        "origin", lock["revision"]], check=True, env=env)
        subprocess.run(["git", "-C", str(destination), "checkout", "--detach",
                        lock["revision"]], check=True, env=env)
    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse",
                                      "HEAD"], text=True).strip()
    if actual != lock["revision"]:
        raise SystemExit("Existing depot_tools has a different revision. Use a separate "
                         "--destination; this script will not reset your checkout.")
    print("Pinned depot_tools: " + actual)
    print("Add this directory to PATH and set DEPOT_TOOLS_UPDATE=0: " + str(destination))


if __name__ == "__main__":
    main()
