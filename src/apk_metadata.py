"""Verify finished APKs and read metadata from the artifact itself.

Uses Android SDK Build-Tools already available on GitHub's Android runners.
No input APK is modified here: call this only after stripping and signing.
"""
import hashlib
import os
import re
import shutil
import subprocess
import zipfile
import logging
from pathlib import Path


def find_build_tool(name: str) -> str:
    tool = shutil.which(name)
    if tool:
        return tool
    for root in (os.getenv("ANDROID_HOME"), os.getenv("ANDROID_SDK_ROOT"),
                 "/usr/local/lib/android/sdk"):
        if not root:
            continue
        versions = Path(root, "build-tools")
        if versions.is_dir():
            for version in sorted(versions.iterdir(), reverse=True):
                candidate = version / (name + (".bat" if os.name == "nt" and name == "apksigner"
                                              else ".exe" if os.name == "nt" else ""))
                if candidate.is_file():
                    return str(candidate)
    raise RuntimeError(f"{name} not found; install Android SDK Build-Tools and set ANDROID_HOME")


def parse_badging(output: str) -> dict:
    package_line = re.search(r"^package: (.+)$", output, re.MULTILINE)
    fields = dict(re.findall(r"(\w+)='([^']*)'", package_line[1])) if package_line else {}
    sdk = re.search(r"^sdkVersion:'(\d+)'$", output, re.MULTILINE)
    if not fields.get("name") or not fields.get("versionName") or not fields.get("versionCode", "").isdigit() or not sdk:
        raise ValueError("Finished APK has incomplete package, version or minimum Android metadata")
    target = re.search(r"^targetSdkVersion:'(\d+)'$", output, re.MULTILINE)
    return {
        "package": fields["name"], "version_name": fields["versionName"],
        "version_code": fields["versionCode"], "min_sdk": int(sdk[1]),
        "target_sdk": int(target[1]) if target else None,
    }


def inspect_abis(apk: Path, arch: str, allow_extra: bool = False, bundle: bool = False) -> list[str]:
    with zipfile.ZipFile(apk) as archive:
        abis = {name.split("/")[1] for name in archive.namelist()
                if name.startswith("lib/") and name.count("/") >= 2 and not name.endswith("/")}
        if bundle:
            for name in archive.namelist():
                if name.endswith(".apk"):
                    with archive.open(name) as stream, zipfile.ZipFile(stream) as split:
                        abis.update(n.split("/")[1] for n in split.namelist()
                                    if n.startswith("lib/") and n.count("/") >= 2 and not n.endswith("/"))
    allowed = {"arm64-v8a", "armeabi-v7a"} if arch == "universal" else {arch}
    if (arch not in {"arm64-v8a", "armeabi-v7a", "universal"}
            or abis and (not abis.intersection(allowed) or not allow_extra and abis - allowed)):
        raise ValueError(f"Finished APK architecture mismatch: requested {arch}, found {sorted(abis)}")
    # No native libraries means this APK does not restrict CPU architecture.
    return sorted(abis)


def verify_apk(apk: Path, arch: str) -> dict:
    signature = subprocess.run(
        [find_build_tool("apksigner"), "verify", "--verbose", "--print-certs", str(apk)],
        capture_output=True, text=True, check=True, timeout=120,
    )
    data = read_manifest_metadata(apk)
    data["native_abis"] = inspect_abis(apk, arch)
    data["signer_sha256"] = re.findall(
        r"certificate SHA-256 digest:\s*([0-9a-fA-F]{64})", signature.stdout,
    )
    if not data["signer_sha256"]:
        raise ValueError("Verified APK has no readable signing certificate fingerprint")
    with apk.open("rb") as stream:
        data["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    data["size_bytes"] = apk.stat().st_size
    data["verified"] = True
    return data


def read_manifest_metadata(apk: Path) -> dict:
    aapt = find_build_tool("aapt")
    badging = subprocess.run([aapt, "dump", "badging", str(apk)],
                             capture_output=True, text=True, check=False, timeout=120)
    if badging.returncode == 0:
        return parse_badging(badging.stdout)
    # Badging also resolves labels/icons and can fail on an otherwise readable
    # obfuscated resource table. Read only required binary-manifest attributes.
    logging.warning("aapt badging failed: %s; reading manifest attributes directly", badging.stderr.strip()[:800])
    tree = subprocess.run([aapt, "dump", "xmltree", str(apk), "AndroidManifest.xml"],
                          capture_output=True, text=True, check=True, timeout=120)
    return parse_manifest_tree(tree.stdout)


def parse_manifest_tree(output: str) -> dict:
    def string(name):
        match = re.search(rf'\b{re.escape(name)}(?:\(0x[0-9a-f]+\))?="([^"\n]+)"', output)
        return match[1] if match else ""

    def number(name):
        match = re.search(rf'\b{re.escape(name)}\(0x[0-9a-f]+\)=\(type 0x1[01]\)(0x[0-9a-f]+|\d+)', output)
        return int(match[1], 16 if match[1].startswith("0x") else 10) if match else None

    package, version = string("package"), string("android:versionName")
    code, minimum = number("android:versionCode"), number("android:minSdkVersion")
    if not package or not version or code is None or minimum is None:
        raise ValueError("APK binary manifest lacks required package, version or minimum Android attributes")
    return {"package": package, "version_name": version, "version_code": str(code),
            "min_sdk": minimum, "target_sdk": number("android:targetSdkVersion")}
