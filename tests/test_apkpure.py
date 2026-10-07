import unittest
from unittest.mock import patch

from src import apkpure


def entry(name, abis, url=True):
    return {
        "package_name": "example.app",
        "version_name": name,
        "native_code": abis,
        "asset": {"url": f"https://example/{name}/{'-'.join(abis)}"} if url else {},
    }


class ApkPureApiTests(unittest.TestCase):
    def test_universal_prefers_arm64_over_earlier_v7a_split(self):
        versions = [entry("480.15", ["armeabi-v7a"]), entry("480.15", ["arm64-v8a"])]
        self.assertEqual(apkpure._api_match(versions, "480.15", "universal")["native_code"], ["arm64-v8a"])
        self.assertEqual(apkpure._api_match(versions, "480.15", "armeabi-v7a")["native_code"], ["armeabi-v7a"])

    def test_exact_name_beats_beta_with_the_same_number(self):
        versions = [entry("2026.08.13-beta", []), entry("2026.08.13-release", [])]
        self.assertEqual(apkpure._api_match(versions, "2026.08.13-release", "universal")["version_name"],
                         "2026.08.13-release")

    def test_normalized_match_skips_other_channels(self):
        versions = [entry("2026.08.03-tv-release", []), entry("2026.08.05-beta", [])]
        self.assertIsNone(apkpure._api_match(versions, "2026.08.03", "universal"))
        self.assertIsNone(apkpure._api_match(versions, "2026.08.05", "universal"))

    def test_entries_without_a_download_url_are_ignored(self):
        self.assertIsNone(apkpure._api_match([entry("1.0", [], url=False)], "1.0", "universal"))

    def test_download_link_uses_api_before_the_website(self):
        with patch.object(apkpure, "_api_versions", return_value=[entry("1.0", ["arm64-v8a"])]), \
                patch.object(apkpure.session, "get") as website:
            link = apkpure.get_download_link("1.0", "example", {"name": "example", "package": "example.app"})
        self.assertEqual(link, "https://example/1.0/arm64-v8a")
        website.assert_not_called()


if __name__ == "__main__":
    unittest.main()
