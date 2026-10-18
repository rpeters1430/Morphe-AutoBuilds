import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import collect_verified_apks as collector


class CollectVerifiedTests(unittest.TestCase):
    def test_only_matching_verified_artifacts_are_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            old = Path.cwd()
            os.chdir(directory)
            self.addCleanup(os.chdir, old)
            Path("build_meta").mkdir()
            for name in ("good.apk", "modified.apk", "unsigned.apk", "unverified.apk"):
                Path(name).write_bytes(b"apk")
            sha = hashlib.sha256(b"apk").hexdigest()
            for name, expected, verified in (("good.apk", sha, True), ("modified.apk", "wrong", True),
                                              ("unverified.apk", sha, False)):
                Path("build_meta", f"{name}.json").write_text(json.dumps({"artifact": {"verified": verified, "sha256": expected}}))
            collector.main()
            self.assertEqual([p.name for p in Path("verified-apks").glob("*.apk")], ["good.apk"])
            self.assertIn(f"{sha}  good.apk", Path("verified-apks/good.apk.sha256").read_text())
            # A rerun must not publish a stale file left in the staging folder.
            Path("good.apk").write_bytes(b"changed")
            collector.main()
            self.assertEqual(list(Path("verified-apks").iterdir()), [])
