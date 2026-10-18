"""Opt-in smoke test against real Android SDK tools on the Actions runner."""
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from src import apk_metadata


@unittest.skipUnless(os.environ.get("MORPHE_ANDROID_INTEGRATION") == "1", "requires Android SDK Build-Tools")
class AndroidBuildToolsTests(unittest.TestCase):
    def test_real_signing_metadata_and_tamper_rejection(self):
        sdk = Path(os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"])
        platforms = sorted((sdk / "platforms").glob("android-*/android.jar"))
        self.assertTrue(platforms, "Runner must have an Android platform installed")
        keystore = Path(__file__).resolve().parent.parent / "keystore/public.jks"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "AndroidManifest.xml"
            manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
                package="app.morphe.verification.fixture" android:versionCode="42" android:versionName="2.1">
                <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/>
                <application android:label="Verification Fixture" android:hasCode="false"/>
                </manifest>''', encoding="utf-8")
            apk = root / "fixture.apk"
            subprocess.run([apk_metadata.find_build_tool("aapt"), "package", "-f", "-M", str(manifest),
                            "-I", str(platforms[-1]), "-F", str(apk)], check=True, capture_output=True)
            subprocess.run([apk_metadata.find_build_tool("apksigner"), "sign", "--ks", str(keystore),
                            "--ks-pass", "pass:public", "--key-pass", "pass:public",
                            "--ks-key-alias", "public", str(apk)], check=True, capture_output=True)
            data = apk_metadata.verify_apk(apk, "arm64-v8a")
            self.assertEqual(data["package"], "app.morphe.verification.fixture")
            self.assertEqual(data["version_code"], "42")
            self.assertEqual(data["version_name"], "2.1")
            self.assertEqual(data["min_sdk"], 26)
            self.assertEqual(data["native_abis"], [])
            self.assertTrue(data["verified"])
            self.assertEqual(len(data["sha256"]), 64)
            self.assertTrue(data["signer_sha256"])
            with zipfile.ZipFile(apk, "a") as archive:
                archive.writestr("assets/tampered.txt", b"modified after signing")
            with self.assertRaises(subprocess.CalledProcessError):
                apk_metadata.verify_apk(apk, "universal")
