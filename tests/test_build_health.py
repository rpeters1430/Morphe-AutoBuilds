import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import merge_manifest
import record_build
import record_manual_build
import check_app_updates as planner


class BuildHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        old = Path.cwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, old)

    def test_record_prefers_verified_version_and_carries_metadata(self):
        Path("build_meta").mkdir()
        meta = {"artifact": {"version_name": "actual", "package": "actual.package", "verified": True},
                "last_success_at": "2026-10-18T06:00:00+00:00", "last_attempt_at": "2026-10-18T06:00:00+00:00"}
        Path("build_meta/app-universal-source-v1.0.apk.json").write_text(json.dumps(meta))
        with patch.dict(os.environ, APP_NAME="app", SOURCE="source", ARCH="universal",
                        APK_PATH="app-universal-source-v1.0.apk"):
            record_build.main()
        data = json.loads(next(Path("build_records").glob("*.json")).read_text())
        self.assertEqual(data["resolved_version"], "actual")
        self.assertEqual(data["artifact"], meta["artifact"])
        self.assertEqual(data["last_success_at"], meta["last_success_at"])

    def test_failed_manual_build_keeps_previous_download(self):
        key = "app|source|universal"
        manifest = {"entries": {key: {"apk": "old.apk", "artifact": {"package": "old.package"}}}}
        record_manual_build.apply_failure_records(manifest["entries"], [
            {"key": key, "status": "failed", "error": "verification failed", "last_attempt_at": "2026-10-18"}], {key})
        self.assertEqual(manifest["entries"][key]["apk"], "old.apk")
        self.assertEqual(manifest["entries"][key]["last_error"], "verification failed")

    def test_manual_success_cannot_promote_an_unpublished_apk(self):
        with patch.dict(os.environ, APP_NAME="youtube", SOURCE="morphe", BUILD_PUBLISHED="false"), \
                patch.object(record_manual_build.planner, "build_full_matrix", return_value=[
                    {"app_name": "youtube", "source": "morphe", "arch": "universal"}]), \
                patch.object(record_manual_build.planner, "fetch_release_asset_names", return_value=["old.apk"]), \
                patch.object(record_manual_build.planner, "fetch_existing_manifest", return_value={"entries": {
                    "youtube|morphe|universal": {"apk": "old.apk", "source_sig": "old"}}}), \
                patch.object(record_manual_build, "_overrides", return_value={}), \
                patch.object(record_manual_build.planner, "get_source_signature", return_value="new"), \
                patch.object(record_manual_build.planner, "run_gh", return_value=(0, "", "")):
            Path("verified-apks").mkdir()
            Path("verified-apks/youtube-universal-morphe-v2.0.apk").write_bytes(b"apk")
            record_manual_build.main()
        data = json.loads(Path("manifest.json").read_text())["entries"]["youtube|morphe|universal"]
        self.assertEqual(data["apk"], "old.apk")
        self.assertEqual(data["source_sig"], "old")
        self.assertIn("publish", data["last_error"].lower())

    def test_manual_manifest_read_failure_never_wipes_other_apps(self):
        Path("verified-apks").mkdir()
        Path("verified-apks/youtube-universal-morphe-v2.0.apk").write_bytes(b"apk")
        with patch.dict(os.environ, APP_NAME="youtube", SOURCE="morphe", BUILD_PUBLISHED="true"), \
                patch.object(record_manual_build.planner, "build_full_matrix", return_value=[]), \
                patch.object(record_manual_build.planner, "fetch_release_asset_names", return_value=["manifest.json"]), \
                patch.object(record_manual_build.planner, "fetch_existing_manifest", return_value=None), \
                patch.object(record_manual_build.planner, "run_gh") as run:
            self.assertEqual(record_manual_build.main(), 1)
        run.assert_not_called()
        self.assertFalse(Path("manifest.json").exists())

    def test_successfully_published_manual_build_records_actual_metadata(self):
        name = "youtube-universal-morphe-v2.0.apk"
        Path("verified-apks").mkdir()
        Path("verified-apks", name).write_bytes(b"apk")
        Path("build_meta").mkdir()
        artifact = {"verified": True, "version_name": "2.0", "package": "actual.package"}
        Path("build_meta", name + ".json").write_text(json.dumps({"artifact": artifact,
            "last_success_at": "2026-10-18", "last_attempt_at": "2026-10-18"}))
        key = "youtube|morphe|universal"
        with patch.dict(os.environ, APP_NAME="youtube", SOURCE="morphe", BUILD_PUBLISHED="true"), \
                patch.object(record_manual_build.planner, "build_full_matrix", return_value=[
                    {"app_name": "youtube", "source": "morphe", "arch": "universal"}]), \
                patch.object(record_manual_build.planner, "fetch_release_asset_names", return_value=[name, "manifest.json"]), \
                patch.object(record_manual_build.planner, "fetch_existing_manifest", return_value={"entries": {
                    key: {"apk": "old.apk", "last_error": "failed"}, "other|source|universal": {"apk": "other.apk"}}}), \
                patch.object(record_manual_build, "_overrides", return_value={}), \
                patch.object(record_manual_build.planner, "get_source_signature", return_value="new"), \
                patch.object(record_manual_build.planner, "run_gh", return_value=(0, "", "")):
            self.assertEqual(record_manual_build.main(), 0)
        entries = json.loads(Path("manifest.json").read_text())["entries"]
        self.assertEqual(entries[key]["artifact"], artifact)
        self.assertNotIn("last_error", entries[key])
        self.assertEqual(entries["other|source|universal"]["apk"], "other.apk")

    def test_planner_keeps_metadata_only_for_the_same_artifact(self):
        entry = {"app_name": "youtube", "source": "morphe", "arch": "universal"}
        old = {**entry, "apk": "youtube-universal-morphe-v1.0.apk", "built_version": "1.0",
               "config_version": "", "source_sig": "sig", "artifact": {"verified": True, "sha256": "old"},
               "last_success_at": "2026-10-17", "last_attempt_at": "2026-10-18", "last_error": "failed"}
        key = "youtube|morphe|universal"
        with patch.object(planner, "get_source_signature", return_value="sig"), \
                patch.object(planner.build_config, "build_options_signature", return_value=""), \
                patch.object(planner, "load_app_config_version", return_value=""), \
                patch.object(planner, "fetch_recommended_version", return_value=""), \
                patch.object(planner, "ONLY_APPS", set()), patch.object(planner, "FORCE_FULL", False):
            _, _, preserved = planner.plan_incremental([entry], {"entries": {key: old}}, [old["apk"]])
            self.assertEqual(preserved[key]["artifact"], old["artifact"])
            replacement = "youtube-universal-morphe-v2.0.apk"
            _, _, recovered = planner.plan_incremental([entry], {"entries": {key: old}}, [replacement])
            self.assertEqual(recovered[key]["apk"], replacement)
            self.assertNotIn("artifact", recovered[key])
            self.assertNotIn("last_success_at", recovered[key])

    def test_recovery_understands_immutable_names_and_does_not_guess_shared_legacy_sources(self):
        current = "youtube-universal-adobo-r0123456789abcdef-v2.0.apk"
        other = "youtube-universal-Hoo-r0123456789abcdef-v9.0.apk"
        legacy = "youtube-universal-morphe-patches-v8.0.apk"
        self.assertEqual(planner._recover_apk_from_release("youtube", "adobo", "universal", [current, other, legacy]), current)
        self.assertEqual(planner._recover_apk_from_release("youtube", "adobo", "universal", [legacy]), "")

    def test_failure_retains_previous_metadata_and_success_clears_error(self):
        key = "app|source|arm64-v8a"
        entry = {"app_name": "app", "source": "source", "arch": "arm64-v8a", "apk": "old.apk",
                 "artifact": {"package": "old.package"}, "last_success_at": "2026-10-17",
                 "source_sig": "old", "pending_source_sig": "new"}
        Path("new_manifest.json").write_text(json.dumps({"entries": {key: entry}}))
        Path("build_records").mkdir()
        record = Path("build_records/app.json")
        record.write_text(json.dumps({"key": key, "status": "failed", "error": "No compatible source",
                                      "last_attempt_at": "2026-10-18T06:00:00+00:00", "run_url": "https://github.com/example/run"}))
        merge_manifest.main()
        data = json.loads(Path("manifest.json").read_text())["entries"][key]
        self.assertEqual(data["apk"], "old.apk")
        self.assertEqual(data["artifact"]["package"], "old.package")
        self.assertEqual(data["last_error"], "No compatible source")
        self.assertEqual(data["failed_attempts"], 1)
        self.assertEqual(data["source_sig"], "old")
        Path("new_manifest.json").write_text(json.dumps({"entries": {key: data}}))
        record.write_text(json.dumps({"key": key, "status": "success", "apk": "new.apk", "resolved_version": "2.0",
                                      "artifact": {"package": "new.package"}, "last_success_at": "2026-10-19"}))
        merge_manifest.main()
        recovered = json.loads(Path("manifest.json").read_text())["entries"][key]
        self.assertEqual(recovered["artifact"]["package"], "new.package")
        self.assertNotIn("last_error", recovered)
        self.assertNotIn("failed_attempts", recovered)


if __name__ == "__main__":
    unittest.main()
