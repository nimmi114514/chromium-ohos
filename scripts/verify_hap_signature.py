#!/usr/bin/env python3
"""Verify the release HAP with the installed API 26 signing tool."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def windows_path(path):
    return subprocess.check_output(
        ["wslpath", "-w", str(path.resolve())], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hap", type=Path, required=True)
    parser.add_argument("--deveco", type=Path, default=Path(
        "/mnt/c/Program Files/Huawei/DevEco Studio"))
    args = parser.parse_args()
    jar = args.deveco / "sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar"
    log = ROOT / "logs/hap-api26-latest-signature-verify.log"
    # Extracted certificate/profile information is private and is removed after
    # verification. Keep the temporary directory on the Windows-visible drive.
    with tempfile.TemporaryDirectory(prefix="signature-check-",
                                     dir=ROOT / "reports") as directory:
        temp = Path(directory)
        result = subprocess.run([
            str(args.deveco / "jbr/bin/java.exe"), "-jar", windows_path(jar),
            "verify-app", "-inFile", windows_path(args.hap),
            "-outCertChain", windows_path(temp / "certificate.cer"),
            "-outProfile", windows_path(temp / "profile.p7b"),
        ], capture_output=True, timeout=120)
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        log.write_text(output)
        cryptographic_verified = result.returncode == 0 and "verify-app success" in output
        verified = cryptographic_verified
        profile_bundle = None
        profile = temp / "profile.p7b"
        if verified and profile.exists():
            content = profile.read_bytes()
            if not content.lstrip().startswith(b"{"):
                cms = subprocess.run([
                    "openssl", "cms", "-verify", "-inform", "DER",
                    "-in", str(profile), "-noverify",
                ], capture_output=True, timeout=30)
                content = cms.stdout if cms.returncode == 0 else b""
            try:
                profile_bundle = json.loads(content)["bundle-info"]["bundle-name"]
            except (ValueError, KeyError):
                pass
        with zipfile.ZipFile(args.hap) as archive:
            package_bundle = json.loads(archive.read("module.json"))["app"]["bundleName"]
        bundle_matches = profile_bundle == package_bundle == "com.example.ohos.chromium"
        verified = verified and bundle_matches
    with args.hap.open("rb") as package:
        digest = hashlib.file_digest(package, "sha256").hexdigest()
    report = {
        "verifiedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "exitCode": result.returncode, "signatureVerified": verified,
        "cryptographicSignatureVerified": cryptographic_verified,
        "packageBundleName": package_bundle,
        "profileBundleName": profile_bundle,
        "bundleNameMatchesProvisioningProfile": bundle_matches,
        "tool": "Installed API26 hap-sign-tool.jar",
        "hap": str(args.hap.resolve()), "hapSha256": digest,
        "log": str(log.relative_to(ROOT)),
        "extractedSigningMetadataRetained": False,
    }
    (ROOT / "reports/api26-latest-hap-signature-verification.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print("API 26 HAP signature verification: " +
          ("passed" if verified else "failed"))
    raise SystemExit(0 if verified else 1)


if __name__ == "__main__":
    main()
