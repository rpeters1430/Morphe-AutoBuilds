import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import aptoide, utils


class DownloadSafetyTests(unittest.TestCase):
    def test_repository_providers_are_not_synthesized_from_package_ids(self):
        from src import downloader
        for provider in ("github", "apkmirror"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as directory, \
                    patch.object(downloader, "Path", side_effect=lambda *a: Path(directory, *a)), \
                    patch.object(utils, "get_supported_versions") as compatible:
                configs = Path(directory, "apps", "apkpure")
                configs.mkdir(parents=True)
                (configs / "example.json").write_text('{"package": "example.app"}')
                self.assertEqual(downloader.download_platform("example", provider, "cli.jar", "p.mpp"), (None, None, []))
                compatible.assert_not_called()

    def test_apk_and_bundle_require_android_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "app.apk"
            bundle = root / "app.apkm"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("base.apk", apk.read_bytes())
            self.assertTrue(utils.usable_android_archive(apk))
            self.assertTrue(utils.usable_android_archive(bundle, bundle=True))
            self.assertFalse(utils.usable_android_archive(bundle))

    def test_bundle_rejects_corrupt_embedded_apk(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "broken.apkm"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("base.apk", b"not a zip")
            self.assertFalse(utils.usable_android_archive(bundle, bundle=True))

    def test_bundle_rejects_invalid_split(self):
        with tempfile.TemporaryDirectory() as directory:
            base = io.BytesIO()
            with zipfile.ZipFile(base, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"manifest")
            bundle = Path(directory) / "broken.apkm"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("base.apk", base.getvalue())
                archive.writestr("split.apk", b"not a zip")
            self.assertFalse(utils.usable_android_archive(bundle, bundle=True))

    def test_unusable_download_is_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.apk"
            archive.write_bytes(b"not an apk")
            with patch.object(utils.shutil, "which", return_value=None):
                self.assertIsNone(utils.ensure_usable_android_archive(archive))
            self.assertFalse(archive.exists())

    def test_aptoide_does_not_substitute_a_version(self):
        listing = {"list": [{"package": "example.app", "file": {
            "vername": "2.0", "vercode": 20,
        }}]}
        with patch.object(aptoide, "_safe_get_json", return_value=listing) as request:
            self.assertIsNone(aptoide.get_download_link("1.0", "example", {"package": "example.app"}))
            request.assert_called_once()

    def test_force_skips_stale_store_latest(self):
        from src import downloader
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(downloader, "Path", side_effect=lambda *a: Path(directory, *a)), \
                patch.object(utils, "get_supported_versions", return_value=["7.92.0", "7.80.0"]), \
                patch.object(aptoide, "get_latest_version", return_value="4.13.0"), \
                patch.object(aptoide, "get_download_link", return_value=None) as link:
            config = Path(directory, "apps", "aptoide")
            config.mkdir(parents=True)
            (config / "example.json").write_text('{"package": "example.app"}')
            downloader.download_platform("example", "aptoide", "cli.jar", "p.mpp", force=True)
        self.assertEqual([c.args[0] for c in link.call_args_list], ["7.92.0", "7.80.0"])

    def _candidates_tried(self, supported, latest="9.0.0", force=False, supported_only=False):
        """Run aptoide's download_platform and return the versions it tried."""
        from src import downloader
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(downloader, "Path", side_effect=lambda *a: Path(directory, *a)), \
                patch.object(utils, "get_supported_versions", return_value=supported), \
                patch.object(aptoide, "get_latest_version", return_value=latest), \
                patch.object(aptoide, "get_download_link", return_value=None) as link:
            config = Path(directory, "apps", "aptoide")
            config.mkdir(parents=True)
            (config / "example.json").write_text('{"package": "example.app"}')
            downloader.download_platform("example", "aptoide", "cli.jar", "p.mpp", force=force,
                                         supported_only=supported_only)
        return [c.args[0] for c in link.call_args_list]

    def test_store_latest_is_tried_after_supported_versions(self):
        self.assertEqual(self._candidates_tried(["7.92.0", "7.80.0"]), ["7.92.0", "7.80.0", "9.0.0"])

    def test_supported_only_skips_store_latest(self):
        self.assertEqual(self._candidates_tried(["7.92.0"], supported_only=True), ["7.92.0"])

    def test_store_latest_used_when_patches_name_no_versions(self):
        self.assertEqual(self._candidates_tried([]), ["9.0.0"])

    def test_force_tries_store_latest_first(self):
        self.assertEqual(self._candidates_tried(["7.92.0"], force=True), ["9.0.0", "7.92.0"])

    def test_unknown_compatibility_fails_the_build(self):
        from src import downloader
        with self.assertRaises(downloader.UnknownPatchCompatibilityError):
            self._candidates_tried(None)

    def test_force_builds_latest_when_compatibility_unknown(self):
        self.assertEqual(self._candidates_tried(None, force=True), ["9.0.0"])


if __name__ == "__main__":
    unittest.main()
