#!/usr/bin/env python3
"""Build the HAP with the installed Windows DevEco Studio API 26 tools."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def windows_path(path):
    return subprocess.check_output(
        ["wslpath", "-w", str(path.resolve())], text=True).strip()


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deveco", type=Path, default=Path(
        "/mnt/c/Program Files/Huawei/DevEco Studio"))
    parser.add_argument("--hap-project", type=Path,
                        default=ROOT.parent / "chromium-2in1-hap")
    parser.add_argument("--stage", choices=["install", "arkts", "hap"],
                        default="arkts")
    parser.add_argument("--module", choices=["web_engine", "chromium"],
                        default="web_engine")
    parser.add_argument("--build-mode", choices=["debug", "release"],
                        default="debug")
    args = parser.parse_args()
    module = "chromium" if args.stage == "hap" else args.module
    sdk = json.loads((args.deveco / "sdk/default/sdk-pkg.json").read_text())
    if str(sdk["data"]["apiVersion"]) != "26":
        raise SystemExit("Expected the installed API 26 SDK")
    if args.stage == "hap":
        source = (ROOT / "src").resolve()
        # This script validates every native artifact before copying anything.
        subprocess.run(["bash", str(args.hap_project /
                        "scripts/prepare_chromium_runtime.sh"),
                        str(source), str(source / "out/OHOS")], check=True)
    deveco = windows_path(args.deveco)
    code = [f"$deveco={ps_literal(deveco)}",
            "$env:DEVECO_SDK_HOME=Join-Path $deveco 'sdk'",
            "$env:HVIGOR_HOME=Join-Path $deveco 'tools\\hvigor'",
            "$env:NODE_HOME=Join-Path $deveco 'tools\\node'",
            "$env:OHPM_HOME=Join-Path $deveco 'tools\\ohpm'",
            "$env:JAVA_HOME=Join-Path $deveco 'jbr'",
            '$env:Path="$env:NODE_HOME;$env:OHPM_HOME\\bin;'
            '$env:JAVA_HOME\\bin;$env:Path"',
            f"Set-Location {ps_literal(windows_path(args.hap_project))}"]
    if args.stage == "install":
        code.append('& "$env:NODE_HOME\\node.exe" '
                    '"$env:OHPM_HOME\\bin\\pm-cli.js" install --all')
    else:
        # In module mode the task is relative to the selected module. The
        # target prefix is required for direct CompileArkTS invocation.
        task = "assembleHap" if args.stage == "hap" else "default@CompileArkTS"
        command = ["--mode", "module", "-p", f"module={module}@default",
                   "-p", "product=default", "-p",
                   f"buildMode={args.build_mode}", task,
                   "--no-daemon", "--no-parallel"]
        code.append('& "$env:NODE_HOME\\node.exe" '
                    '"$env:HVIGOR_HOME\\bin\\hvigorw.js" ' +
                    " ".join(ps_literal(arg) for arg in command))
    code.append("exit $LASTEXITCODE")
    log = ROOT / "logs" / (
        f"hap-api26-{args.stage}-{module}-{args.build_mode}.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    print(f"Using API 26 SDK {sdk['data']['version']}; log: {log}", flush=True)
    with log.open("w") as output:
        result = subprocess.run([
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile", "-NonInteractive", "-Command", ";\n".join(code)],
            stdout=output, stderr=subprocess.STDOUT)
    print(f"{args.stage} finished with exit code {result.returncode}", flush=True)
    if result.returncode == 0 and args.stage == "hap" and args.build_mode == "release":
        subprocess.run([
            sys.executable, str(ROOT / "scripts/verify_hap_contents.py"),
            "--hap", str(args.hap_project / "chromium/build/default/outputs/"
                         "default/chromium-default-signed.hap")], check=True)
        subprocess.run([
            sys.executable, str(ROOT / "scripts/verify_hap_signature.py"),
            "--deveco", str(args.deveco), "--hap", str(args.hap_project /
                "chromium/build/default/outputs/default/chromium-default-signed.hap")
        ], check=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
