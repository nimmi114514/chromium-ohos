#!/usr/bin/env python3
"""Continue a running native build through packaging and device startup checks.

The JSON report records each stage. A failed stage stops the queue; startup
success alone does not establish that web pages render correctly.
"""

import argparse
import datetime
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def process_identity(pid):
    try:
        # starttime disambiguates a PID that the OS has subsequently reused.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--duration", type=int, default=180,
                        help="Device observation time, including delayed crashes")
    parser.add_argument("--wait-for-lock", action="store_true",
                        help="Queue behind the existing validation process")
    parser.add_argument("--device-key", help="Select the authorized tablet explicitly")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("Use a simple filename label")
    if args.wait_pid <= 1:
        parser.error("Expected the existing Ninja process PID")
    if not 1 <= args.jobs <= 12:
        parser.error("Use between 1 and 12 compile jobs on this machine")
    if args.duration < 45:
        parser.error("Observe the device for at least 45 seconds")

    with (ROOT / "logs/continue-validation.lock").open("a") as lock:
        try:
            if args.wait_for_lock:
                print("Waiting for the existing validation queue to finish.",
                      flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX |
                        (0 if args.wait_for_lock else fcntl.LOCK_NB))
        except BlockingIOError:
            raise SystemExit("A validation queue is already running")

        report_path = ROOT / "reports" / f"validation-queue-{args.label}.json"
        report = {"label": args.label, "startedAt": now(),
                  "state": "waiting_for_existing_ninja",
                  "waitPid": args.wait_pid, "stages": [],
                  "compileJobs": args.jobs,
                  "renderingVerified": False, "complete": False}

        def save():
            report["updatedAt"] = now()
            report_path.write_text(json.dumps(report, indent=2) + "\n")

        save()
        identity = process_identity(args.wait_pid)
        while identity is not None and process_identity(args.wait_pid) == identity:
            time.sleep(10)

        source = (ROOT / "src").resolve()
        stages = [
            ("gn", [str(ROOT / "tools/gn"), "gen", "out/OHOS",
                    "--root-target=//chrome"], source),
            ("native", [str(ROOT / "tools/ninja"), "-C", "out/OHOS",
                        f"-j{args.jobs}", "-k", "0", "chrome_main_web"], source),
            ("export", [sys.executable, "scripts/export_port.py"], ROOT),
            ("hap", [sys.executable, "scripts/build_hap.py", "--stage", "hap",
                     "--build-mode", "release"], ROOT),
            ("device_startup", [sys.executable, "scripts/verify_device_startup.py",
                                "--label", args.label, "--install",
                                "--duration", str(args.duration)], ROOT),
        ]
        if args.device_key:
            stages[-1][1].extend(["--device-key", args.device_key])
        for name, command, cwd in stages:
            log = ROOT / "logs" / f"queue-{args.label}-{name}.log"
            stage = {"name": name, "startedAt": now(),
                     "log": str(log.relative_to(ROOT))}
            report["stages"].append(stage)
            report["state"] = name
            save()
            print(f"Starting {name}; log: {log}", flush=True)
            with log.open("w") as output:
                result = subprocess.run(command, cwd=cwd, stdout=output,
                                        stderr=subprocess.STDOUT)
            stage.update({"exitCode": result.returncode, "finishedAt": now()})
            if result.returncode:
                report["state"] = "stopped_at_" + name
                save()
                raise SystemExit(result.returncode)
            save()
        report["state"] = "startup_checks_passed_rendering_pending"
        save()
        print("Startup checks passed; rendering still requires verification.",
              flush=True)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


if __name__ == "__main__":
    main()
