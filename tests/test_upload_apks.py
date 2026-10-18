import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import upload_apks


class UploadApksTests(unittest.TestCase):
    def test_existing_immutable_asset_is_skipped_and_new_assets_never_clobber(self):
        with patch.object(upload_apks.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, json.dumps({"assets": [{"name": "same.apk"}]}), ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ]) as run:
            upload_apks.upload(["folder/same.apk", "folder/new.apk", "folder/new.apk.sha256"])
        command = run.call_args_list[-1].args[0]
        self.assertEqual(command, ["gh", "release", "upload", "latest", "folder/new.apk", "folder/new.apk.sha256"])
        self.assertNotIn("--clobber", command)

    def test_failed_listing_aborts_instead_of_overwriting_assets(self):
        with patch.object(upload_apks.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "view")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                upload_apks.upload(["new.apk"])
        self.assertEqual(run.call_count, 1)
