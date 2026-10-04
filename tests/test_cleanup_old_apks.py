import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cleanup_old_apks as cleanup  # noqa: E402


class SupersededTests(unittest.TestCase):
    def _superseded(self, name, keep):
        prefixes = {cleanup.identity_prefix(n) for n in keep}
        app_arches = {p for p in (cleanup.app_arch_prefix(n) for n in keep) if p}
        return cleanup.is_superseded(name, prefixes, app_arches)

    def test_older_version_is_superseded(self):
        keep = ["youtube-arm64-v8a-morphe-v2.5.0.apk"]
        self.assertTrue(self._superseded("youtube-arm64-v8a-morphe-v2.4.0.apk", keep))

    def test_previous_source_is_superseded(self):
        keep = ["google-photos-arm64-v8a-akash-photos-v7.95.0.989626323.apk"]
        self.assertTrue(self._superseded(
            "google-photos-arm64-v8a-morphe-patches-v7.92.0.977185651.apk", keep))

    def test_other_arch_and_similar_app_names_are_kept(self):
        keep = ["youtube-arm64-v8a-morphe-v2.5.0.apk"]
        self.assertFalse(self._superseded("youtube-armeabi-v7a-morphe-v2.4.0.apk", keep))
        self.assertFalse(self._superseded("youtube-music-arm64-v8a-morphe-v8.1.apk", keep))


if __name__ == "__main__":
    unittest.main()
