import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import __main__ as builder, build_config, downloader, utils


class PatchPipelineTests(unittest.TestCase):
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

    def test_stock_input_is_unchanged_until_patching_and_output_is_stripped_before_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_cwd = Path.cwd()
            os.chdir(root)
            self.addCleanup(os.chdir, original_cwd)
            stock = root / "stock.apk"
            with zipfile.ZipFile(stock, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
                archive.writestr("lib/x86/libexample.so", b"x86")
                archive.writestr("lib/arm64-v8a/libexample.so", b"arm64")
            original_bytes = stock.read_bytes()
            cli, patches = root / "morphe-cli.jar", root / "patches.mpp"
            cli.touch()
            patches.touch()
            events = []

            def patch_apk(cli, patches, input_apk, output_apk, is_morphe, args):
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

            settings = build_config.get_entry("niagara", "Hoo")
            with patch.object(downloader, "download_apkmirror", return_value=(stock, "1.16.31", ["1.16.31"])), \
                    patch.object(builder, "_cli_supports", return_value=True), \
                    patch.object(builder, "_new_patches_to_enable", return_value=[]), \
                    patch.object(builder, "_run_patch", side_effect=patch_apk), \
                    patch.object(utils, "find_apksigner", return_value="apksigner"), \
                    patch.object(utils, "run_process", side_effect=sign), \
                    patch.object(utils.shutil, "which", return_value=None):
                result = builder.run_build("niagara", "Hoo", settings=settings, tools=([cli, patches], "Hoo"))
            self.assertEqual(events, ["patch", "sign"])
            self.assertTrue(Path(result).exists())


if __name__ == "__main__":
    unittest.main()
