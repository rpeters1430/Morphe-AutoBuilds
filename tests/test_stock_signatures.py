import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
from src import apkmirror, trawl, utils


def apk_bytes(v1=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")
        if v1:
            archive.writestr("META-INF/CERT.RSA", b"metadata fixture, not a real signature")
    return stream.getvalue()


def signing_block_apk(scheme_id):
    """Structural v2/v3 fixture: insert a block before the central directory."""
    original = apk_bytes()
    eocd = original.rfind(b"PK\x05\x06")
    directory = struct.unpack_from("<I", original, eocd + 16)[0]
    pair = struct.pack("<QI", 5, scheme_id) + b"x"
    size = len(pair) + 24
    block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + b"APK Sig Block 42"
    result = bytearray(original[:directory] + block + original[directory:])
    struct.pack_into("<I", result, eocd + len(block) + 16, directory + len(block))
    return result


class StockSignatureTests(unittest.TestCase):
    def test_unsigned_stock_is_discarded_but_unsigned_output_validation_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stock.apk")
            path.write_bytes(apk_bytes())
            self.assertTrue(utils.usable_android_archive(path))
            self.assertIsNone(utils.ensure_signed_android_archive(path))
            self.assertFalse(path.exists())

    def test_v1_signature_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stock.apk")
            original = apk_bytes(v1=True)
            path.write_bytes(original)
            self.assertEqual(utils.ensure_signed_android_archive(path), path)
            self.assertEqual(path.read_bytes(), original)

    def test_v2_v3_and_v31_blocks_are_detected(self):
        for scheme in (0x7109871A, 0xF05368A0, 0x1B93AD61):
            with self.subTest(scheme=scheme), tempfile.TemporaryDirectory() as directory:
                path = Path(directory, "stock.apk")
                path.write_bytes(signing_block_apk(scheme))
                self.assertTrue(utils.is_apk_signed(path))

    def test_malformed_or_unknown_signing_block_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "stock.apk")
            path.write_bytes(signing_block_apk(123))
            self.assertFalse(utils.is_apk_signed(path))
            data = signing_block_apk(0x7109871A)
            directory_offset = data.rfind(b"PK\x05\x06")
            directory = struct.unpack_from("<I", data, directory_offset + 16)[0]
            struct.pack_into("<Q", data, directory - 24, len(data) * 2)
            path.write_bytes(data)
            self.assertFalse(utils.is_apk_signed(path))

    def test_bundle_requires_signature_metadata_in_every_split(self):
        for signed_split in (False, True):
            with self.subTest(signed_split=signed_split), tempfile.TemporaryDirectory() as directory:
                path = Path(directory, "stock.apkm")
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("base.apk", apk_bytes(v1=True))
                    archive.writestr("split.apk", apk_bytes(v1=signed_split))
                self.assertEqual(bool(utils.ensure_signed_android_archive(path, bundle=True)), signed_split)

    def test_trawl_handles_repeated_challenged_pages_and_syncs_browser_identity(self):
        challenge = SimpleNamespace(status_code=403, text="Cloudflare", headers={})
        rendered = trawl.ScrapedResponse("url", b"app page", {"cf_clearance": "fixture"}, "Browser-UA")
        with patch.object(apkmirror, "_blocked_by_cloudflare", False), \
                patch.object(apkmirror, "session") as session, \
                patch.object(trawl, "fetch", return_value=rendered) as scrape:
            session.get.return_value = challenge
            self.assertIs(apkmirror._cf_get("https://www.apkmirror.com/first"), rendered)
            self.assertIs(apkmirror._cf_get("https://www.apkmirror.com/next"), rendered)
            self.assertEqual(scrape.call_count, 2)
            self.assertEqual(session.get.call_count, 2)
            session.headers.__setitem__.assert_called_with("User-Agent", "Browser-UA")
            self.assertFalse(apkmirror._blocked_by_cloudflare)

    def test_unresolved_challenge_stops_provider_requests(self):
        challenge = SimpleNamespace(status_code=403, text="Cloudflare", headers={})
        with patch.object(apkmirror, "_blocked_by_cloudflare", False), \
                patch.object(apkmirror, "session") as session, \
                patch.object(trawl, "fetch", return_value=None):
            session.get.return_value = challenge
            for url in ("first", "next"):
                with self.assertRaises(apkmirror.ApkMirrorBlocked):
                    apkmirror._cf_get(url)
            self.assertEqual(session.get.call_count, 1)

    def test_zero_padded_version_release_discovery(self):
        soup = BeautifulSoup('<a href="/apk/publisher/app/app-26-4-5-release/">26.4.5</a>', "html.parser")
        self.assertEqual(apkmirror._scrape_release_url_from_soup(soup, "26.04.05", {"name": "app"}, None, None),
                         "https://www.apkmirror.com/apk/publisher/app/app-26-4-5-release/")


if __name__ == "__main__":
    unittest.main()
