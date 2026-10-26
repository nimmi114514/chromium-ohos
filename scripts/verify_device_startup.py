#!/usr/bin/env python3
"""Capture a signed HAP's real-device startup without deleting application data."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "com.example.ohos.chromium"


def decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="replace")


def matching_symbol_library(build_ids):
    """Resolve symbols only from a library identified by the fault itself."""
    readelf = ROOT / "src/third_party/llvm-build/Release+Asserts/bin/llvm-readelf"
    candidates = [ROOT / "src/out/OHOS/libchrome_main_web.so",
                  ROOT / "artifacts/native/libchrome_main_web.so"]
    candidates += sorted((ROOT / "artifacts/history").glob(
        "*/native/libchrome_main_web.so"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        result = subprocess.run([str(readelf), "--notes", str(candidate)],
                                capture_output=True, timeout=20)
        note = re.search(r"Build ID:\s*([0-9a-f]+)", decode(result.stdout))
        if note and note.group(1) in build_ids:
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--attach", action="store_true",
                        help="Observe the running app without restarting it")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--hdc", type=Path, default=Path(
        "/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/"
        "toolchains/hdc.exe"))
    parser.add_argument("--device-key", help="Select the authorized tablet explicitly")
    parser.add_argument("--hap", type=Path, default=ROOT.parent /
                        "chromium-2in1-hap/chromium/build/default/outputs/"
                        "default/chromium-default-signed.hap")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("Use a simple filename label")
    if args.duration < 5:
        parser.error("Observe startup for at least five seconds")
    if args.attach and args.install:
        parser.error("Cannot reinstall while observing the running app")

    # Validate the package itself before any device action. Artifact paths may
    # still point at a package produced before the bundle-name migration.
    if args.install:
        with zipfile.ZipFile(args.hap) as package:
            actual_bundle = json.loads(package.read("module.json"))["app"]["bundleName"]
        if actual_bundle != BUNDLE:
            raise SystemExit("Installation refused: expected bundle " + BUNDLE +
                             ", found " + actual_bundle)
        verification_path = ROOT / "reports/api26-latest-hap-signature-verification.json"
        if not verification_path.is_file():
            raise SystemExit("Installation refused: missing signature verification")
        verification = json.loads(verification_path.read_text())
        with args.hap.open("rb") as package:
            package_sha256 = hashlib.file_digest(package, "sha256").hexdigest()
        if not (verification.get("signatureVerified") and
                verification.get("bundleNameMatchesProvisioningProfile") and
                verification.get("hapSha256") == package_sha256):
            raise SystemExit("Installation refused: signature verification does not match this HAP")

    hdc_prefix = [str(args.hdc)]
    if args.device_key:
        hdc_prefix += ["-t", args.device_key]

    def hdc(*command, timeout=30):
        result = subprocess.run([*hdc_prefix, *command],
                                capture_output=True, timeout=timeout)
        return result.returncode, decode(result.stdout + result.stderr).strip()

    if args.device_key:
        _, selected_api = hdc("shell", "param", "get", "const.ohos.apiversion")
        connected = [args.device_key] if selected_api.isdigit() else []
    else:
        _, targets = hdc("list", "targets")
        connected = [t for t in targets.splitlines() if t.strip() and
                     "Empty" not in t]
    if len(connected) != 1:
        destination = ROOT / "reports" / f"api26-device-startup-{args.label}.json"
        destination.write_text(json.dumps({
            "label": args.label,
            "startedAt": datetime.datetime.now().astimezone().isoformat(),
            "connectedDeviceCount": len(connected),
            "appDataDeleted": False,
            "installed": False,
            "runtimeAttempted": False,
            "launchBlocked": True,
            "startupCrashObserved": None,
            "renderingVerified": False,
            "blocker": "No connected device" if not connected else
                       "Multiple devices connected; target selection required",
        }, indent=2) + "\n")
        print(f"Device verification blocked; report: {destination}", flush=True)
        raise SystemExit(2)
    _, api = hdc("shell", "param", "get", "const.ohos.apiversion")
    report = {"label": args.label, "deviceApi": api,
              "appDataDeleted": False, "installed": False,
              "startedAt": datetime.datetime.now().astimezone().isoformat()}
    fault_since = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    if args.install:
        windows_hap = subprocess.check_output(
            ["wslpath", "-w", str(args.hap.resolve())], text=True).strip()
        code, output = hdc("install", "-r", windows_hap, timeout=180)
        if code or "install bundle successfully" not in output.lower():
            raise SystemExit("Signed HAP installation failed: " + output)
        report["installed"] = True
        report["installedHapPath"] = str(args.hap.resolve())
        with args.hap.open("rb") as package:
            report["installedHapSha256"] = hashlib.file_digest(
                package, "sha256").hexdigest()
        identity_path = ROOT / "reports/api26-latest-signed-hap-identity.json"
        if identity_path.exists():
            identity = json.loads(identity_path.read_text())
            if identity.get("sha256") == report["installedHapSha256"]:
                report["expectedNativeBuildIds"] = identity["nativeBuildIds"]
                report["installedPackageContentVerified"] = True
        print("Signed HAP installed with application data preserved.", flush=True)

    log_path = ROOT / "logs" / f"device-startup-{args.label}.log"
    with tempfile.TemporaryFile() as capture_file:
        capture = subprocess.Popen(
            [*hdc_prefix, "shell", "hilog", "-T",
             "[WebEngine],Adapter,chromium"],
            stdout=capture_file, stderr=subprocess.STDOUT)
        try:
            if not args.attach:
                hdc("shell", "aa", "force-stop", BUNDLE)
            # Drain historical buffer before marking the new startup capture.
            time.sleep(2)
            capture_file.seek(0, 2)
            offset = capture_file.tell()
            # Installation can terminate the previous app. Only count faults
            # created after the new package's explicit launch.
            fault_since = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            if args.attach:
                code, pids = hdc("shell", "pidof", BUNDLE)
                launch = ("Attached to running app; start ability successfully"
                          if code == 0 and re.search(r"\b\d+\b", pids)
                          else "No running app found")
                report["observationMode"] = "attach_without_restart"
            else:
                code, launch = hdc("shell", "aa", "start", "-a", "EntryAbility",
                                   "-b", BUNDLE)
            report["launchExitCode"] = code
            report["launchResult"] = launch
            report["launchAccepted"] = (
                code == 0 and "start ability successfully" in launch.lower())
            print(launch, flush=True)
            started = time.monotonic()
            observations = []
            report["requestedObservationSeconds"] = args.duration
            delays = ([0, 1, 3, 5, 15, 30, 60, 120, args.duration]
                      if report["launchAccepted"] else [0])
            for delay in sorted(set(delays)):
                if delay > args.duration:
                    continue
                time.sleep(max(0, started + delay - time.monotonic()))
                _, pid_output = hdc("shell", "pidof", BUNDLE)
                connected_now = not re.search(r"\[Fail\]|Not match target|Device not found|need connect-key", pid_output, re.I)
                pids = re.findall(r"\b\d+\b", pid_output) if connected_now else []
                observations.append({"seconds": delay, "pids": pids,
                                     "deviceConnected": connected_now})
                print(f"At {delay}s: browser PID(s) {','.join(pids) or 'none'}",
                      flush=True)
            report["observations"] = observations
            report["runtimeInterrupted"] = any(not item["deviceConnected"] for item in observations)
            report["aliveAtEnd"] = (bool(observations[-1]["pids"])
                                    if observations[-1]["deviceConnected"] else None)
            _, processes = hdc("shell", "ps", "-A", "-o", "PID,PPID,NAME")
            report["appProcessesAtEnd"] = [
                line.strip() for line in processes.splitlines()
                if re.search(re.escape(BUNDLE) + r"(?::|\s|$)", line)]
        finally:
            capture.terminate()
            try:
                capture.wait(timeout=10)
            except subprocess.TimeoutExpired:
                capture.kill()
                capture.wait(timeout=10)
            capture_file.seek(offset if "offset" in locals() else 0)
            lines = decode(capture_file.read()).splitlines()
            # Crash keys can contain command-line credentials. They are not
            # needed to diagnose the assertion or its native stack.
            # HiLog can truncate the beginning of native child process tags.
            # Match the new bundle suffix without including the older app.
            own_tag = re.compile(r"(?:com\.example\.ohos\.chromium|(?:oh)?os\.chromium)(?::[^/\s]+)?/")
            lines = [line for line in lines if own_tag.search(line) and not re.search(
                r'"[^"\n]+"\s*=\s*"|Crash keys:|--oauth.*(?:secret|id)=|gaia-config|GOOGLE_(?:API_KEY|DEFAULT_CLIENT)',
                line, re.IGNORECASE)]
            log_path.write_text("\n".join(lines) + "\n")

    report["log"] = str(log_path.relative_to(ROOT))
    report["fatalMessages"] = [line for line in lines if ":FATAL:" in line]
    # A service/renderer can crash while the application PID remains alive.
    # Always inspect Faultlogger, including when there is no Chromium FATAL.
    _, listed = hdc("shell", "hidumper", "-s", "1201", "-a",
                    "-p Faultlogger -l")
    names = sorted(set(name for name in re.findall(
        rf"cppcrash-{re.escape(BUNDLE)}(?::[^\s]+)?-\d+-\d{{14}}(?:\.log)?",
        listed) if name.removesuffix(".log").rsplit("-", 1)[-1] >= fault_since))
    report["nativeFaultLogs"] = names
    javascript_names = sorted(set(name for name in re.findall(
        rf"jscrash-{re.escape(BUNDLE)}(?::[^\s]+)?-\d+-\d{{14}}(?:\.log)?",
        listed) if name.removesuffix(".log").rsplit("-", 1)[-1] >= fault_since))
    report["javascriptFaultLogs"] = javascript_names
    report["nativeCrashObserved"] = bool(report["fatalMessages"]) or bool(names)
    report["javascriptCrashObserved"] = bool(javascript_names)
    report["startupCrashObserved"] = (report["nativeCrashObserved"] or
                                      report["javascriptCrashObserved"])
    report["processExitedWithoutNativeFault"] = (
        report["launchAccepted"] and report.get("aliveAtEnd") is False and
        not report["startupCrashObserved"])
    if report.get("runtimeInterrupted") and not report["startupCrashObserved"]:
        report["startupCrashObserved"] = None
    report["launchBlocked"] = not report["launchAccepted"]
    report["renderingVerified"] = False
    if report["nativeCrashObserved"]:
        # App/Chromium tags can miss a low-level trap. Hiview's faultlogger
        # keeps the faulting thread stack, even on a release device without
        # direct access to /data/log/faultlog.
        if names:
            _, fault = hdc("shell", "hidumper", "-s", "1201", "-a",
                           f"-p Faultlogger -f {names[-1]}", timeout=45)
            if "Fault thread info:" not in fault and not names[-1].endswith(".log"):
                _, fault = hdc("shell", "hidumper", "-s", "1201", "-a",
                               f"-p Faultlogger -f {names[-1]}.log", timeout=45)
            process_name = re.search(r"^Process name:([^\r\n]+)", fault, re.M)
            report["nativeFaultProcess"] = (
                process_name.group(1).strip() if process_name else "")
            report["crashNativeBuildIds"] = {
                name: sorted(set(re.findall(
                    re.escape(name) + r"[^\r\n]*\(([0-9a-f]{16,64})\)", fault)))
                for name in ("libchrome_main_web.so", "libadapter.so")}
            expected = report.get("expectedNativeBuildIds", {}).get(
                "libchrome_main_web.so")
            if expected:
                report["crashMainBuildMatchesInstalledPackage"] = expected in (
                    report["crashNativeBuildIds"]["libchrome_main_web.so"])
            fault_thread = fault.partition("Fault thread info:")[2].partition(
                "Other thread info:")[0]
            signal = re.search(r"Reason:(Signal:[^\r\n]+)", fault)
            report["nativeSignal"] = signal.group(1).strip() if signal else ""
            pcs = re.findall(
                r"^#\d\d pc ([0-9a-fA-F]+) /data/storage/el1/bundle/"
                r"libs/arm64/libchrome_main_web\.so", fault_thread, re.M)
            if pcs:
                symbolizer = ROOT / "src/third_party/llvm-build/"
                symbolizer /= "Release+Asserts/bin/llvm-symbolizer"
                library = matching_symbol_library(
                    report["crashNativeBuildIds"]["libchrome_main_web.so"])
                if library is None:
                    report["symbolizationSkipped"] = (
                        "No preserved library matches the fault Build ID")
                    pcs = []
                else:
                    report["symbolLibrary"] = str(library.relative_to(ROOT))
            if pcs:
                result = subprocess.run(
                    [str(symbolizer), "--obj=" + str(library),
                     "--functions=linkage", *["0x" + pc for pc in pcs]],
                    capture_output=True, timeout=45)
                symbols = decode(result.stdout).strip().split("\n\n")
                report["nativeFaultFrames"] = [
                    {"pc": "0x" + pc, "symbol": symbols[i].splitlines()[0]}
                    for i, pc in enumerate(pcs[:len(symbols)])]
                for frame in report["nativeFaultFrames"][:8]:
                    print(f"  {frame['pc']} {frame['symbol']}", flush=True)
    destination = ROOT / "reports" / f"api26-device-startup-{args.label}.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    for fatal in report["fatalMessages"]:
        print(fatal, flush=True)
    print(f"Startup capture: {destination}", flush=True)
    if report["startupCrashObserved"]:
        raise SystemExit(1)
    if report["launchBlocked"] or report.get("runtimeInterrupted"):
        raise SystemExit(2)
    if report.get("processExitedWithoutNativeFault"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
