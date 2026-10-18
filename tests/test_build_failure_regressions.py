import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
from src import __main__ as builder, apk_metadata, apkfab, apkmirror, apkpure


class LatestRunRegressions(unittest.TestCase):
    def test_universal_strips_legacy_and_non_arm_dirs_before_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory, "proton.apk")
            with zipfile.ZipFile(apk, "w") as archive:
                for abi in ("arm64-v8a", "armeabi-v7a", "armeabi", "mips", "mips64", "x86", "x86_64"):
                    archive.writestr(f"lib/{abi}/library.so", b"native")
            builder._strip_arch_libs(apk, "universal")
            self.assertEqual(apk_metadata.inspect_abis(apk, "universal"), ["arm64-v8a", "armeabi-v7a"])

    def test_apkpure_does_not_offer_x86_when_building_for_arm(self):
        variants = [{"version_name": "5.62.11", "native_code": ["x86_64"],
                     "asset": {"url": "https://example/x86.apk"}}]
        self.assertIsNone(apkpure._api_match(variants, "5.62.11", "universal"))
        self.assertIsNone(apkpure._api_match(variants, "5.62.11", "arm64-v8a"))

    def test_latest_pinterest_skips_chromeos_stub(self):
        versions = [{"version_name": "2000000000.0.0-CrOS", "native_code": [], "asset": {"url": "https://example/stub.apk"}},
                    {"version_name": "14.41.0", "native_code": ["arm64-v8a"], "asset": {"url": "https://example/phone.apk"}}]
        with patch.object(apkpure, "_api_versions", return_value=versions):
            self.assertEqual(apkpure.get_latest_version("pinterest", {"package": "com.pinterest"}), "14.41.0")

    def test_apkmirror_never_substitutes_18_24_1_for_18_24(self):
        soup = BeautifulSoup('<a href="/apk/wps/wps/wps-18-24-1-release/">18.24.1</a>', "html.parser")
        self.assertIsNone(apkmirror._scrape_release_url_from_soup(soup, "18.24", {"name": "wps"}))
        self.assertFalse(apkmirror._exact_version_in_text("WPS Office 18.24.1 arm64-v8a APK", "18.24"))

    def test_apkfab_prefers_arm_variant_over_x86_with_same_version(self):
        versions = '<div class="version_history">' + ''.join(
            f'<div class="list"><div class="package_info"><div class="title"><span class="version">434.0</span></div></div>'
            f'<span>{abi}</span><a href="/download?sha1={sha}">Download</a></div>'
            for abi, sha in (("x86_64", "a" * 40), ("arm64-v8a", "b" * 40))) + '</div>'
        final = '<a href="https://d.apkfab.com/get-download?correct-arm">Download</a>'
        with patch.object(apkfab, "_fetch", side_effect=[
                SimpleNamespace(content=versions.encode()), SimpleNamespace(content=final.encode())]) as fetch:
            link = apkfab.get_download_link("434.0", "threads", {"name": "threads", "package": "example", "arch": "universal"})
        self.assertEqual(link, "https://d.apkfab.com/get-download?correct-arm")
        self.assertIn("b" * 40, fetch.call_args.args[0])

    def test_patch_load_error_cannot_publish_an_unpatched_gamehub(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "output.apk")
            output.write_bytes(b"unpatched")
            with self.assertRaises(subprocess.CalledProcessError):
                builder._reject_empty_patch_run("SEVERE: Failed to load patches from patches.rvp:\njava.lang.NoClassDefFoundError", [], output)
            self.assertFalse(output.exists())

    def test_manifest_dump_fallback_does_not_resolve_application_labels(self):
        xmltree = '''E: manifest (line=1)
  A: android:versionCode(0x0101021b)=(type 0x10)0x14a8dd88
  A: android:versionName(0x0101021c)="583.0.0.29.95" (Raw: "583.0.0.29.95")
  A: package="com.facebook.orca" (Raw: "com.facebook.orca")
  E: uses-sdk (line=2)
    A: android:minSdkVersion(0x0101020c)=(type 0x10)0x1c
    A: android:targetSdkVersion(0x01010270)=(type 0x10)0x23
  E: application (line=3)
    A: android:label(0x01010001)=@0x7f120000
'''
        with patch.object(apk_metadata, "find_build_tool", return_value="aapt"), \
                patch.object(apk_metadata.subprocess, "run", side_effect=[
                    subprocess.CompletedProcess([], 1, "", "ERROR getting 'android:label' attribute"),
                    subprocess.CompletedProcess([], 0, xmltree, "")]):
            data = apk_metadata.read_manifest_metadata(Path("messenger.apk"))
        self.assertEqual(data["package"], "com.facebook.orca")
        self.assertEqual(data["version_name"], "583.0.0.29.95")
        self.assertEqual(data["min_sdk"], 28)


if __name__ == "__main__":
    unittest.main()
