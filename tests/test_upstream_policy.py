import json
from contextlib import ExitStack
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from src import __main__ as builder, build_config, downloader, utils


class UpstreamPolicyTests(unittest.TestCase):
    def test_new_and_previously_auto_enabled_patches_keep_developer_defaults(self):
        listed = {"Existing patch": True, "Add microG-RE support": False,
                  "Add original microG support": False}
        with patch.object(builder, "_app_package", return_value="example.app"), \
                patch.object(utils, "list_app_patches", return_value=listed), \
                patch.object(builder, "_previous_patch_state", return_value=(
                    {"Existing patch"}, {"Add microG-RE support"})):
            selected = builder._new_patches_to_enable(
                "example", "source", {"app_name": "example", "source": "source"},
                Path("morphe-cli.jar"), Path("patches.mpp"))
        self.assertEqual(selected, [])
        self.assertEqual(builder.last_patch_state["auto_patches"], [])

    def test_scheduled_entries_require_supported_versions(self):
        self.assertTrue(build_config.merge_entry(
            {"app_name": "example", "source": "source"}, {}, {})["supported_only"])
        self.assertTrue(all(entry["supported_only"] for entry in build_config.iter_entries()))

    def test_no_compatible_versions_is_not_treated_as_version_agnostic(self):
        output = "INFO: Morphe data root: /tmp/data\nWARN: No compatible versions found in: patches.mpp"
        with patch.object(utils, "run_process", return_value=output):
            self.assertIsNone(utils.get_supported_versions(
                "example.app", "morphe-cli.jar", "patches.mpp"))

    def test_version_agnostic_app_requires_explicit_cli_any(self):
        output = ("INFO: Morphe data root: /tmp/data\nINFO: Package name: example.app\n"
                  "Most common compatible versions:\n\tAny")
        with patch.object(utils, "run_process", return_value=output):
            self.assertEqual(utils.get_supported_versions(
                "example.app", "morphe-cli.jar", "patches.mpp"), [])

    def test_disabled_patch_listing_does_not_override_no_compatible_versions(self):
        output = "INFO: Morphe data root: /tmp/data\nWARN: No compatible versions found in: patches.mpp"
        with patch.object(utils, "run_process", return_value=output), \
                patch.object(utils, "list_app_patches", return_value={"Optional patch": False}):
            self.assertIsNone(utils.get_supported_versions(
                "example.app", "morphe-cli.jar", "patches.mpp"))

    def test_pinned_version_must_be_supported_too(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(downloader, "Path", side_effect=lambda *a: Path(directory, *a)), \
                patch.object(utils, "get_supported_versions", return_value=["1.0"]), \
                patch.object(downloader.aptoide, "get_download_link", side_effect=AssertionError("unsupported APK requested")):
            configs = Path(directory, "apps", "aptoide")
            configs.mkdir(parents=True)
            (configs / "example.json").write_text(json.dumps({"package": "example.app", "version": "2.0"}))
            with self.assertRaises(downloader.UnknownPatchCompatibilityError):
                downloader.download_platform("example", "aptoide", "cli.jar", "patches.mpp",
                                             supported_only=True)

    def test_cli_recommended_patch_coverage_order_is_preserved(self):
        output = ("INFO: Package name: example.app\nMost common compatible versions:\n"
                  "\t1.0 (5 patches)\n\t2.0 (1 patch)")
        with patch.object(utils, "run_process", return_value=output):
            self.assertEqual(utils.get_supported_versions(
                "example.app", "morphe-cli.jar", "patches.mpp"), ["1.0", "2.0"])

    def test_pinned_build_passes_its_explicit_compatibility_override(self):
        policies = []

        def unavailable(*args, **kwargs):
            policies.append(kwargs["supported_only"])
            return None, None, []

        with tempfile.TemporaryDirectory() as directory:
            cli, patches = Path(directory, "morphe-cli.jar"), Path(directory, "patches.mpp")
            cli.touch()
            patches.touch()
            settings = build_config.merge_entry({"app_name": "example", "source": "source",
                "version": "2.0", "supported_only": False}, {}, {})
            with ExitStack() as stack:
                stack.enter_context(patch.object(builder, "_cli_supports", return_value=False))
                for provider in ("apkmirror", "apkpure", "aptoide", "github", "uptodown", "apkcombo", "apkfab"):
                    stack.enter_context(patch.object(downloader, "download_" + provider, side_effect=unavailable))
                self.assertIsNone(builder.run_build("example", "source", settings=settings,
                                                   tools=([cli, patches], "source")))
            self.assertEqual(policies, [False] * 7)


class ToolDownloadRetryTests(unittest.TestCase):
    def test_retry_exhaustion_long_cooldown_and_permanent_errors(self):
        counts = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                counts[self.path] = counts.get(self.path, 0) + 1
                status, delay = {"/busy": (503, "0"), "/cooldown": (429, "120"),
                                 "/forbidden": (403, "0")}[self.path]
                self.send_response(status)
                self.send_header("Retry-After", delay)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with patch.object(utils.time, "sleep"):
                for path, status in (("/busy", 503), ("/cooldown", 429), ("/forbidden", 403)):
                    response = utils.get_with_retry(base + path)
                    self.assertEqual(response.status_code, status)
                    response.close()
            self.assertEqual(counts, {"/busy": 3, "/cooldown": 1, "/forbidden": 1})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_rate_limited_tool_and_release_metadata_are_retried(self):
        counts = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                counts[self.path] = counts.get(self.path, 0) + 1
                self.send_response(429 if counts[self.path] == 1 else 200)
                self.send_header("Retry-After", "0")
                self.end_headers()
                self.wfile.write(b'{"release": "v1"}' if self.path == "/metadata" else b"patch-tool")

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with tempfile.TemporaryDirectory() as directory:
                result = downloader.download_resource(base + "/tool", str(Path(directory, "tool.mpp")))
                self.assertEqual(result.read_bytes(), b"patch-tool")
            self.assertEqual(utils.fetch_json(base + "/metadata"), {"release": "v1"})
            self.assertEqual(counts, {"/tool": 2, "/metadata": 2})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
