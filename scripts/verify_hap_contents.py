#!/usr/bin/env python3
"""Verify that a release HAP contains this build's native code and resources."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_webui_resources(native):
    """Check page resources reached the final pack, beyond matching file hashes."""
    sys.path.insert(0, str((ROOT / "src/tools/grit").resolve()))
    from grit.format.data_pack import ReadDataPack

    packed = ReadDataPack(str(native / "resources.pak")).resources
    checked = []
    for page in ("management", "discards", "settings", "downloads", "history",
                 "bookmarks", "extensions", "new_tab_page",
                 "new_tab_page_third_party"):
        page_pack = native / "gen/chrome" / (page + "_resources.pak")
        if not page_pack.is_file():
            raise SystemExit("Missing required desktop WebUI page pack: " + page)
        resources = ReadDataPack(str(page_pack)).resources
        missing = [key for key, value in resources.items()
                   if packed.get(key) != value]
        if missing:
            raise SystemExit(f"Incomplete {page} resources in resources.pak: "
                             f"{len(missing)} missing or different IDs")
        checked.append({"page": page, "resourceCount": len(resources)})
    return checked


def allocated_sections(path):
    """Fingerprint loaded ELF sections while allowing DevEco symbol stripping."""
    result = {}
    with path.open("rb") as stream:
        header = struct.unpack("<16sHHIQQQIHHHHHH", stream.read(64))
        if header[0][:6] != b"\x7fELF\x02\x01" or header[1:3] != (3, 183):
            raise SystemExit("Expected an ELF64 AArch64 shared library")
        stream.seek(header[6])
        rows = [struct.unpack("<IIQQQQIIQQ", stream.read(header[11])[:64])
                for _ in range(header[12])]
        names = rows[header[13]]
        stream.seek(names[4])
        strings = stream.read(names[5])
        for row in rows:
            if not row[2] & 2:  # SHF_ALLOC
                continue
            name = strings[row[0]:].split(b"\0", 1)[0].decode()
            entry = {"type": row[1], "flags": row[2], "address": row[3],
                     "size": row[5], "alignment": row[8]}
            if row[1] != 8:  # SHT_NOBITS has no file bytes.
                stream.seek(row[4])
                remaining = row[5]
                sha = hashlib.sha256()
                while remaining:
                    chunk = stream.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise SystemExit("Truncated ELF section: " + name)
                    sha.update(chunk)
                    remaining -= len(chunk)
                entry["sha256"] = sha.hexdigest()
            result[name] = entry
    if not result:
        raise SystemExit("No allocated sections in native library")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hap", type=Path, required=True)
    parser.add_argument("--native-out", type=Path,
                        default=ROOT / "src/out/OHOS")
    parser.add_argument("--unsigned-only", action="store_true",
                        help="Verify an unsigned candidate without labeling it signed")
    parser.add_argument("--label", default="candidate")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("Use a simple candidate label")
    native = args.native_out.resolve()
    webui_resources = verify_webui_resources(native)
    files = {}
    for name in ("libadapter.so", "libchrome_main_web.so"):
        files["libs/arm64-v8a/" + name] = native / name
    for name in ("icudtl.dat", "resources.pak", "chrome_100_percent.pak",
                 "chrome_200_percent.pak"):
        files["resources/resfile/" + name] = native / name
    flags = (native / "gen/tools/v8_context_snapshot/buildflags.h").read_text()
    snapshots = []
    if "BUILDFLAG_INTERNAL_USE_V8_CONTEXT_SNAPSHOT() (1)" in flags:
        snapshots.append("v8_context_snapshot.bin")
    if not snapshots or "BUILDFLAG_INTERNAL_INCLUDE_BOTH_V8_SNAPSHOTS() (1)" in flags:
        snapshots.append("snapshot_blob.bin")
    for name in snapshots:
        files["resources/resfile/" + name] = native / name
    for path in sorted((native / "locales").glob("*.pak")):
        files["resources/resfile/locales/" + path.name] = path

    checked = []
    build_ids = {}
    readelf = ROOT / "src/third_party/llvm-build/Release+Asserts/bin/llvm-readelf"
    with zipfile.ZipFile(args.hap) as archive, tempfile.TemporaryDirectory(
            prefix="chromium-hap-identity-") as directory:
        names = set(archive.namelist())
        module = json.loads(archive.read("module.json"))
        app = module["app"]
        if app["bundleName"] != "com.example.chromium":
            raise SystemExit("Expected the isolated Chromium 158 bundle name")
        metadata = {key: app[key] for key in (
            "bundleName", "compileSdkVersion", "minAPIVersion",
            "targetAPIVersion", "versionName", "debug")}
        metadata["deviceTypes"] = module["module"]["deviceTypes"]
        if (not app["compileSdkVersion"].startswith("26.") or app["debug"] or
                any(app[key] % 1000000 != 26 for key in
                    ("minAPIVersion", "targetAPIVersion"))):
            raise SystemExit("Expected an API 26 release HAP")
        expected_locales = {name for name in files if "/locales/" in name}
        actual_locales = {name for name in names if "/locales/" in name}
        if not expected_locales or expected_locales != actual_locales:
            raise SystemExit("Packaged locale files differ from the native build")
        actual_snapshots = {name for name in names if name.endswith(
            ("/snapshot_blob.bin", "/v8_context_snapshot.bin"))}
        if actual_snapshots != {"resources/resfile/" + name for name in snapshots}:
            raise SystemExit("Packaged V8 snapshots differ from the build flags")
        for name, path in files.items():
            if name.endswith(".so"):
                packed_path = Path(directory) / path.name
                with archive.open(name) as packed, packed_path.open("wb") as out:
                    shutil.copyfileobj(packed, out)
                expected_sections = allocated_sections(path)
                if expected_sections != allocated_sections(packed_path):
                    raise SystemExit("HAP native code differs from build: " + name)
                ids = []
                for library in (path, packed_path):
                    notes = subprocess.check_output(
                        [str(readelf), "-n", str(library)], text=True)
                    match = re.search(r"Build ID:\s*(\w+)", notes)
                    if not match:
                        raise SystemExit("Missing native Build ID: " + name)
                    ids.append(match.group(1))
                if ids[0] != ids[1]:
                    raise SystemExit("HAP native Build ID differs: " + name)
                build_ids[path.name] = ids[0]
                with path.open("rb") as source, packed_path.open("rb") as packed:
                    expected, actual = digest(source), digest(packed)
                checked.append({"path": name, "sha256": actual,
                                "sizeBytes": archive.getinfo(name).file_size,
                                "zipCompressionMethod": archive.getinfo(name).compress_type,
                                "buildSourceSha256": expected,
                                "allocatedSectionsMatchBuild": True,
                                "allocatedSectionsChecked": len(expected_sections),
                                "symbolsStripped": actual != expected})
                continue
            with path.open("rb") as source, archive.open(name) as packed:
                expected, actual = digest(source), digest(packed)
            if expected != actual:
                raise SystemExit("HAP contains a stale or corrupt file: " + name)
            checked.append({"path": name, "sha256": actual,
                            "sizeBytes": archive.getinfo(name).file_size})

        if args.unsigned_only:
            candidate = ROOT / "artifacts/candidates" / args.label
            candidate.mkdir(parents=True, exist_ok=True)
            destination = candidate / "chromium-158-ohos-api26-arm64-unsigned.hap"
            shutil.copy2(args.hap, destination)
            library_archive = candidate / "native"
            library_archive.mkdir(exist_ok=True)
            for name in build_ids:
                shutil.copy2(native / name, library_archive / name)
            with destination.open("rb") as package:
                package_hash = digest(package)
            report = {
                "verifiedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "label": args.label, "hap": str(destination),
                "sizeBytes": destination.stat().st_size, "sha256": package_hash,
                "nativeBuildIds": build_ids, "moduleMetadata": metadata,
                "files": checked, "webuiResources": webui_resources,
                "matchesNativeBuild": True,
                "signed": False, "installableOnTargetVerified": False,
                "renderingVerified": False, "functionalRegressionPassed": False,
                "runtimeValidation": "pending",
                "diagnosticCandidate": True,
            }
            report_path = ROOT / "reports" / (
                "api26-" + args.label + "-unsigned-hap-identity.json")
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            print(f"Unsigned candidate content verified: {len(checked)} native/resource files")
            print("Bundle: " + metadata["bundleName"])
            print("SHA256: " + package_hash)
            return

        unsigned = args.hap.with_name("chromium-default-unsigned.hap")
        with zipfile.ZipFile(unsigned) as unsigned_archive:
            signed_payload = {item.filename: (item.CRC, item.file_size)
                              for item in archive.infolist()}
            unsigned_payload = {item.filename: (item.CRC, item.file_size)
                                for item in unsigned_archive.infolist()}
        # The HAP signer adds page verification metadata to the signed ZIP.
        # All original application entries must retain their bytes and sizes.
        signed_payload.pop(".pages.info", None)
        if signed_payload != unsigned_payload:
            raise SystemExit("Signed and unsigned HAP payloads differ")

    destination = ROOT / "artifacts/chromium-158.0.8116.0-ohos-api26-arm64-release-signed.hap"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.hap, destination)
    unsigned_destination = destination.with_name(destination.name.replace(
        "-signed.hap", "-unsigned.hap"))
    shutil.copy2(unsigned, unsigned_destination)
    native_archive = ROOT / "artifacts/native"
    native_archive.mkdir(parents=True, exist_ok=True)
    for name in build_ids:
        shutil.copy2(native / name, native_archive / name)
    with destination.open("rb") as package:
        package_hash = digest(package)
    report = {"verifiedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "hap": str(destination), "sizeBytes": destination.stat().st_size,
              "sha256": package_hash, "nativeBuildIds": build_ids,
              "moduleMetadata": metadata,
              "files": checked, "webuiResources": webui_resources,
              "matchesNativeBuild": True,
              "renderingVerified": False, "runtimeValidation": "pending"}
    report_path = ROOT / "reports/api26-latest-signed-hap-identity.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    manifest_path = ROOT / "artifacts/manifest.json"
    previous = ROOT / "artifacts/manifest-before-original132.json"
    if manifest_path.exists() and not previous.exists():
        shutil.copy2(manifest_path, previous)
    lock = json.loads((ROOT / "versions.json").read_text())["chromium"]
    with unsigned_destination.open("rb") as package:
        unsigned_hash = digest(package)
    manifest = {
        "created": report["verifiedAt"], "chromiumVersion": "158.0.8116.0",
        "chromiumRevision": lock["revision"], "api": 26,
        "architecture": "arm64-v8a", "buildMode": "release", "signed": True,
        "runtimeTested": False, "runtimeValidation": "pending",
        "hap": {"path": destination.name, "size": report["sizeBytes"],
                "sha256": package_hash},
        "unsignedHap": {"path": unsigned_destination.name,
                        "size": unsigned_destination.stat().st_size,
                        "sha256": unsigned_hash},
        "nativeLibraries": [item for item in checked if item["path"].endswith(".so")],
        "nativeBuildIds": build_ids,
        "resources": [item for item in checked if not item["path"].endswith(".so")],
        "moduleMetadata": metadata,
        "runtimeResourceFilesVerified": True, "allLocalePaksPreserved": True,
        "localePakCount": len(expected_locales),
        "compressNativeLibs": all(item["zipCompressionMethod"] == zipfile.ZIP_DEFLATED
                                  for item in checked if item["path"].endswith(".so")),
        "identityReport": str(report_path.relative_to(ROOT)),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "artifacts/manifest-release.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(f"HAP content verified: {len(checked)} native/resource files", flush=True)
    print(f"Signed release HAP: {destination}", flush=True)
    print(f"SHA256: {package_hash}", flush=True)


if __name__ == "__main__":
    main()
