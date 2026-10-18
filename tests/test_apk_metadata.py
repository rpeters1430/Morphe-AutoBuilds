import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import apk_metadata


BADGING = """package: name='app.example.patched' versionCode='42' versionName='2.1'
sdkVersion:'26'
targetSdkVersion:'35'
"""


class ApkMetadataTests(unittest.TestCase):
    def apk(self, directory, abis=()):
        path = Path(directory, "output.apk")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"binary manifest fixture")
            for abi in abis:
                archive.writestr(f"lib/{abi}/example.so", b"native code")
        return path

    def test_reads_actual_manifest_abis_and_checksum_after_signature_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = self.apk(directory, ["arm64-v8a"])
            cert = "a" * 64
            with patch.object(apk_metadata, "find_build_tool", side_effect=lambda name: name), \
                    patch.object(apk_metadata.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, f"Signer #1 certificate SHA-256 digest: {cert}\n", ""),
                        subprocess.CompletedProcess([], 0, BADGING, ""),
                    ]) as run:
                data = apk_metadata.verify_apk(apk, "arm64-v8a")
            self.assertEqual(run.call_args_list[0].args[0][:3], ["apksigner", "verify", "--verbose"])
            self.assertEqual(data["package"], "app.example.patched")
            self.assertEqual(data["version_name"], "2.1")
            self.assertEqual(data["version_code"], "42")
            self.assertEqual(data["min_sdk"], 26)
            self.assertEqual(data["native_abis"], ["arm64-v8a"])
            self.assertEqual(data["sha256"], hashlib.sha256(apk.read_bytes()).hexdigest())
            self.assertEqual(data["signer_sha256"], [cert])

    def test_native_free_apk_is_compatible_with_either_arm_arch(self):
        for arch in ("arm64-v8a", "armeabi-v7a", "universal"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                self.assertEqual(apk_metadata.inspect_abis(self.apk(directory), arch), [])

    def test_wrong_or_extra_native_abi_is_rejected(self):
        for target, abis in (("arm64-v8a", ["armeabi-v7a"]),
                             ("armeabi-v7a", ["arm64-v8a"]),
                             ("arm64-v8a", ["arm64-v8a", "armeabi-v7a"]),
                             ("universal", ["x86"])):
            with self.subTest(target=target, abis=abis), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, "architecture"):
                    apk_metadata.inspect_abis(self.apk(directory, abis), target)

    def test_universal_reports_actual_arm_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(apk_metadata.inspect_abis(self.apk(directory, ["armeabi-v7a"]), "universal"),
                             ["armeabi-v7a"])

    def test_native_bundle_is_checked_before_cli_strips_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            split = self.apk(directory, ["armeabi-v7a"])
            bundle = Path(directory, "stock.apkm")
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.write(split, "split_config.armeabi.apk")
            with self.assertRaisesRegex(ValueError, "architecture"):
                apk_metadata.inspect_abis(bundle, "arm64-v8a", allow_extra=True, bundle=True)

    def test_failed_signature_verification_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = self.apk(directory)
            with patch.object(apk_metadata, "find_build_tool", return_value="apksigner"), \
                    patch.object(apk_metadata.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "verify")):
                with self.assertRaises(subprocess.CalledProcessError):
                    apk_metadata.verify_apk(apk, "universal")

    def test_manifest_without_required_metadata_is_rejected(self):
        for badging in ("", "package: name='app.example' versionCode='1' versionName='1.0'",
                        BADGING.replace("sdkVersion:'26'", "sdkVersion:'VanillaIceCream'")):
            with self.subTest(badging=badging), self.assertRaises(ValueError):
                apk_metadata.parse_badging(badging)


if __name__ == "__main__":
    unittest.main()
