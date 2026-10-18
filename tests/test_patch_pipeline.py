import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import __main__ as builder, build_config, downloader, utils


class PatchPipelineTests(unittest.TestCase):
    def test_stripping_rejects_wrong_arch_before_removing_its_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory, "wrong.apk")
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("lib/armeabi-v7a/lib.so", b"32-bit code")
            original = apk.read_bytes()
            with self.assertRaisesRegex(ValueError, "architecture"):
                builder._strip_arch_libs(apk, "arm64-v8a")
            self.assertEqual(apk.read_bytes(), original)

    def test_zero_patch_success_is_rejected_and_output_deleted(self):
        for cli, morphe in (("morphe-cli.jar", True), ("revanced-cli-6.jar", False)):
            with self.subTest(cli=cli), tempfile.TemporaryDirectory() as directory:
                output = Path(directory, "output.apk")
                output.write_bytes(b"unpatched")
                with patch.object(utils, "run_process", return_value="INFO: Applying 0 patches..."):
                    with self.assertRaises(subprocess.CalledProcessError) as error:
                        builder._run_patch(Path(cli), Path("patches.mpp"), Path("input.apk"), output, morphe, [])
                self.assertFalse(output.exists())
                self.assertTrue(builder._should_retry_with_older_version(error.exception.output))

    def test_nonempty_patch_run_is_accepted(self):
        with patch.object(utils, "run_process", return_value="INFO: Applying 4 patches..."):
            builder._run_patch(Path("morphe-cli.jar"), Path("patches.mpp"), Path("input.apk"), Path("output.apk"), True, [])

    def test_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "output.apk")
            output.write_bytes(b"unpatched")
            cli_output = "INFO: Filtering patches for com.example.app v2.0.0...\nINFO: Applying 3 patches..."
            with patch.object(utils, "run_process", return_value=cli_output):
                with self.assertRaises(subprocess.CalledProcessError):
                    builder._run_patch(Path("morphe-cli.jar"), Path("patches.mpp"), Path("input.apk"), output, True, [], downloaded_version="1.0.0")
            self.assertFalse(output.exists())

    def test_stock_input_is_unchanged_until_patching_and_output_is_stripped_before_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_cwd = Path.cwd()
            os.chdir(root)
            self.addCleanup(os.chdir, original_cwd)
            stock = root / "stock.apk"
            with zipfile.ZipFile(stock, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
                archive.writestr("META-INF/CERT.RSA", b"signature metadata fixture")
                archive.writestr("lib/x86/libexample.so", b"x86")
                archive.writestr("lib/arm64-v8a/libexample.so", b"arm64")
            original_bytes = stock.read_bytes()
            wrong_arch = root / "x86.apk"
            with zipfile.ZipFile(wrong_arch, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
                archive.writestr("META-INF/CERT.RSA", b"signature metadata fixture")
                archive.writestr("lib/x86_64/libexample.so", b"x86")
            unsigned = root / "unsigned.apk"
            with zipfile.ZipFile(unsigned, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
            cli, patches = root / "morphe-cli.jar", root / "patches.mpp"
            cli.touch()
            patches.touch()
            events = []

            def patch_apk(cli, patches, input_apk, output_apk, is_morphe, args, *extra, **kwargs):
                self.assertEqual(input_apk.read_bytes(), original_bytes)
                events.append("patch")
                output_apk.write_bytes(input_apk.read_bytes())

            def sign(command, **kwargs):
                self.assertEqual(events, ["patch"])
                events.append("sign")
                apk = Path(command[command.index("--in") + 1])
                with zipfile.ZipFile(apk) as archive:
                    self.assertNotIn("lib/x86/libexample.so", archive.namelist())
                    self.assertIn("lib/arm64-v8a/libexample.so", archive.namelist())
                Path(command[command.index("--out") + 1]).write_bytes(apk.read_bytes())

            try:
                settings = build_config.get_entry("niagara", "Hoo")
                with patch.object(downloader, "download_apkmirror", __name__="download_apkmirror", return_value=(unsigned, "1.16.31", ["1.16.31"])), \
                        patch.object(downloader, "download_apkpure", __name__="download_apkpure", return_value=(wrong_arch, "1.16.31", ["1.16.31"])), \
                        patch.object(downloader, "download_aptoide", return_value=(stock, "1.16.31", ["1.16.31"])), \
                        patch.object(builder, "_cli_supports", return_value=True), \
                        patch.object(builder, "_new_patches_to_enable", return_value=[]), \
                        patch.object(builder, "_run_patch", side_effect=patch_apk), \
                        patch.object(builder.apk_metadata, "verify_apk", return_value={"verified": True, "version_name": "1.16.31", "sha256": "a" * 64}), \
                        patch.object(utils, "find_apksigner", return_value="apksigner"), \
                        patch.object(utils, "run_process", side_effect=sign), \
                        patch.object(utils.shutil, "which", return_value=None):
                    result = builder.run_build("niagara", "Hoo", settings=settings, tools=([cli, patches], "Hoo"))
                self.assertEqual(events, ["patch", "sign"])
                self.assertFalse(unsigned.exists())
                self.assertFalse(wrong_arch.exists())
                self.assertTrue(Path(result).exists())
                self.assertIn("-Hoo-r" + "a" * 16 + "-v", result)
                self.assertTrue(Path("build_meta", f"{Path(result).name}.json").exists())
            finally:
                os.chdir(original_cwd)

    def test_rejected_signed_apk_is_deleted_and_never_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory, "rejected.apk")
            apk.write_bytes(b"invalid signed artifact")
            with patch.object(builder.apk_metadata, "verify_apk", side_effect=ValueError("architecture mismatch")):
                with self.assertRaisesRegex(ValueError, "architecture mismatch"):
                    builder._verify_output(apk, "arm64-v8a")
            self.assertFalse(apk.exists())

    def test_build_meta_keeps_verified_metadata_when_patch_state_is_added(self):
        with tempfile.TemporaryDirectory() as directory:
            old = Path.cwd()
            os.chdir(directory)
            self.addCleanup(os.chdir, old)
            with patch.object(builder.apk_metadata, "verify_apk", return_value={"package": "actual.package", "verified": True}):
                builder._verify_output(Path("app.apk"), "universal")
            builder._write_build_meta("app.apk", follows_store=True)
            import json
            data = json.loads(Path("build_meta/app.apk.json").read_text())
            self.assertEqual(data["artifact"]["package"], "actual.package")
            self.assertTrue(data["follows_store"])
            self.assertIn("last_success_at", data)


if __name__ == "__main__":
    unittest.main()
