import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_portal_data as portal


class PortalHealthTests(unittest.TestCase):
    def generate(self, entries, assets, manifest=None, release=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(portal, "DOCS_DIR", root), \
                    patch.object(portal, "DATA_JSON_PATH", root / "data.json"), \
                    patch.object(portal, "DATA_JS_PATH", root / "data.js"), \
                    patch.object(portal, "OBTAINIUM_JSON_PATH", root / "apps.json"), \
                    patch.object(portal, "get_repo_slug", return_value="owner/repo"), \
                    patch.object(portal.build_config, "iter_entries", return_value=[
                        {"enabled": True, "patches_channel": "stable", "patch_options": {}, "arches": ["universal"], **e}
                        for e in entries]), \
                    patch.object(portal, "fetch_release_assets", return_value=(
                        {"assets": assets} if release is None else release, "2026-10-18")), \
                    patch.object(portal, "fetch_release_manifest", return_value=manifest or {}):
                portal.generate_portal_assets()
            return json.loads((root / "data.json").read_text()), json.loads((root / "apps.json").read_text())

    def test_missing_assets_never_get_fabricated_downloads_or_feed_entries(self):
        data, feed = self.generate([{"app_name": "youtube", "source": "morphe"}], [])
        self.assertEqual(data["apps"][0]["downloads"], [])
        self.assertEqual(data["apps"][0]["status"], "not_built")
        self.assertEqual(feed["apps"], [])

    def test_retained_artifact_has_failure_health_and_actual_compatibility(self):
        name = "youtube-arm64-v8a-morphe-v2.0.apk"
        artifact = {"package": "actual.patched.package", "version_name": "2.0", "version_code": "20",
                    "native_abis": ["arm64-v8a"], "min_sdk": 26, "sha256": "abc", "verified": True}
        manifest = {"entries": {"youtube|morphe|arm64-v8a": {
            "apk": name, "artifact": artifact, "last_success_at": "2026-10-17", "last_failed_at": "2026-10-18",
            "last_attempt_at": "2026-10-18", "last_error": "Fingerprint mismatch", "failed_attempts": 2}}}
        data, feed = self.generate([{"app_name": "youtube", "source": "morphe", "arches": ["arm64-v8a"]}],
                                   [{"name": name, "url": "https://github.com/download", "size": 123}], manifest)
        app = data["apps"][0]
        self.assertEqual(app["status"], "retained")
        self.assertEqual(app["package"], "actual.patched.package")
        self.assertEqual(app["downloads"][0]["metadata"], artifact)
        self.assertEqual(app["health"][0]["last_error"], "Fingerprint mismatch")
        self.assertEqual(app["health"][0]["retry_after"], "2026-10-25")
        self.assertEqual(feed["apps"][0]["id"], "actual.patched.package")

    def test_missing_manifest_asset_is_unavailable_not_not_built(self):
        manifest = {"entries": {"youtube|morphe|universal": {"apk": "deleted.apk"}}}
        data, _ = self.generate([{"app_name": "youtube", "source": "morphe"}], [], manifest)
        self.assertEqual(data["apps"][0]["status"], "unavailable")

    def test_release_lookup_failure_is_unknown(self):
        data, feed = self.generate([{"app_name": "youtube", "source": "morphe"}], [], release={})
        self.assertEqual(data["apps"][0]["status"], "unknown")
        self.assertEqual(feed["apps"], [])

    def test_disabled_apps_are_excluded_from_bulk_feed(self):
        name = "youtube-universal-morphe-v1.0.apk"
        _, feed = self.generate([{"app_name": "youtube", "source": "morphe", "enabled": False}],
                                [{"name": name, "url": "https://github.com/download"}])
        self.assertEqual(feed["apps"], [])

    def test_different_patch_sources_never_share_downloads(self):
        entries = [{"app_name": "youtube", "source": "morphe"}, {"app_name": "youtube", "source": "revanced"}]
        name = "youtube-universal-morphe-v1.0.apk"
        data, _ = self.generate(entries, [{"name": name, "url": "https://github.com/download"}])
        apps = {a["source"]: a for a in data["apps"]}
        self.assertEqual(len(apps["morphe"]["downloads"]), 1)
        self.assertEqual(apps["revanced"]["downloads"], [])

    def test_ambiguous_legacy_source_name_is_never_assigned_to_a_new_source(self):
        # Hoo and adobo both produce morphe-patches filenames. Even if only
        # adobo is configured now, this old Hoo file cannot be attributed.
        data, feed = self.generate([{"app_name": "youtube", "source": "adobo"}],
            [{"name": "youtube-universal-morphe-patches-v1.0.apk", "url": "https://github.com/download"}])
        self.assertEqual(data["apps"][0]["downloads"], [])
        self.assertEqual(feed["apps"], [])

    def test_legacy_asset_is_available_with_unknown_verification(self):
        data, _ = self.generate([{"app_name": "youtube", "source": "morphe"}],
                                [{"name": "youtube-universal-morphe-v1.0.apk", "url": "https://github.com/download"}])
        app = data["apps"][0]
        self.assertEqual(app["status"], "available")
        self.assertEqual(app["downloads"][0]["metadata"], {})

    def test_mixed_package_arches_disable_all_obtainium_entry_points(self):
        entries = [{"app_name": "youtube", "source": "morphe", "arches": ["arm64-v8a", "armeabi-v7a"]}]
        assets, records = [], {}
        for arch, pkg in (("arm64-v8a", "new.package"), ("armeabi-v7a", "old.package")):
            name = f"youtube-{arch}-morphe-v1.0.apk"
            assets.append({"name": name, "url": "https://github.com/download"})
            records[f"youtube|morphe|{arch}"] = {"apk": name, "artifact": {"package": pkg, "verified": True}}
        data, feed = self.generate(entries, assets, {"entries": records})
        self.assertIsNone(data["apps"][0]["obtainium_config"])
        self.assertEqual(feed["apps"], [])

    def test_obtainium_matches_only_attributed_legacy_assets_and_new_source_arches(self):
        name = "youtube-universal-morphe-patches-v1.0.apk"
        manifest = {"entries": {"youtube|adobo|universal": {"apk": name}}}
        data, _ = self.generate([{"app_name": "youtube", "source": "adobo"}],
            [{"name": name, "url": "https://github.com/download"}], manifest)
        pattern = json.loads(data["apps"][0]["obtainium_config"]["additionalSettings"])["apkFilterRegEx"]
        self.assertIsNotNone(re.fullmatch(pattern, name))
        self.assertIsNotNone(re.fullmatch(pattern, "youtube-universal-adobo-r0123456789abcdef-v2.0.apk"))
        self.assertIsNone(re.fullmatch(pattern, "youtube-arm64-v8a-adobo-r0123456789abcdef-v2.0.apk"))
        self.assertIsNone(re.fullmatch(pattern, "youtube-universal-Hoo-r0123456789abcdef-v2.0.apk"))
        self.assertIsNone(re.fullmatch(pattern, "youtube-universal-morphe-patches-v0.9.apk"))


if __name__ == "__main__":
    unittest.main()
