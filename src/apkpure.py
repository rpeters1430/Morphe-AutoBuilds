"""APKPure (https://apkpure.net).

Primary path: APKPure's own app API (tapi.pureapk.com), which sits outside
the website's Cloudflare wall and returns direct download URLs for the ~20
newest builds. The website scrape stays as the fallback for older versions.
"""

import logging
import re

from bs4 import BeautifulSoup

from src import session, utils

# Define a standard browser User-Agent to avoid 403 Forbidden errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://apkpure.net/'
}

# The API serves requests that look like they come from the APKPure app.
API_URL = "https://tapi.pureapk.com/v3/get_app_his_version"
API_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 5 Build/TQ3A.230901.001); APKPure/3.20.34 (Aegon)",
    "Ual-Access-Businessid": "projecta",
    "Ual-Access-ProjectA": '{"device_info":{"abis":["x86_64","arm64-v8a","x86","armeabi-v7a","armeabi"],"android_id":"50f838123d9a9c94","brand":"google","country":"United States","country_code":"US","imei":"","language":"en-US","manufacturer":"Google","mode":"Pixel 5","os_ver":"33","os_ver_name":"13","platform":1,"product":"redfin","screen_height":1080,"screen_width":1920},"host_app_info":{"build_no":"468","channel":"","md5":"6756e53158d6f6c013650a40d8f1147b","pkg_name":"com.apkpure.aegon","sdk_ver":"3.20.34","version_code":3203427,"version_name":"3.20.34"}}',
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


# Pre-release or form-factor builds that share a version number with the
# phone release (e.g. "2026.08.13-beta", "2026.08.03-tv-release").
_OTHER_CHANNEL = re.compile(r"\b(alpha|beta|tv|wear|auto)\b", re.IGNORECASE)


def _api_versions(package: str) -> list[dict]:
    """The API's version list for a package (newest first), or [] on failure."""
    if not package:
        return []
    try:
        res = session.get(
            API_URL, headers=API_HEADERS,
            params={"package_name": package, "hl": "en"}, timeout=20,
        )
        if res.status_code != 200:
            logging.debug(f"APKPure API returned {res.status_code} for {package}")
            return []
        versions = res.json().get("version_list") or []
    except Exception as e:
        logging.debug(f"APKPure API failed for {package}: {e}")
        return []
    # Guard against the API answering for a different (similarly named) app.
    return [v for v in versions if v.get("package_name") in (None, package)]


def _api_download_url(entry: dict) -> str | None:
    asset = entry.get("asset") or {}
    return asset.get("url") or next(iter(asset.get("urls") or []), None)


def _abi_rank(entry: dict, arch: str) -> int:
    """Lower is better. The API lists one entry per ABI build of a version.

    Same policy as APKCombo: a "universal" build must install on 64-bit-only
    phones, so an armeabi-v7a-only file is the last resort.
    """
    abis = {str(a).lower() for a in entry.get("native_code") or []}
    has64, has32 = "arm64-v8a" in abis, "armeabi-v7a" in abis
    if arch == "arm64-v8a":
        order = (has64, not abis)
    elif arch == "armeabi-v7a":
        order = (has32, not abis)
    else:
        order = (has64 and has32, not abis, has64, has32)
    for rank, matched in enumerate(order):
        if matched:
            return rank
    return len(order)


def _api_match(versions: list[dict], version: str, arch: str) -> dict | None:
    """Best downloadable entry for `version` and `arch` (ties keep API order)."""
    wanted = (version or "").strip()
    wanted_norm = utils.normalize_version(wanted)
    downloadable = [v for v in versions if _api_download_url(v)]

    def name(entry: dict) -> str:
        return (entry.get("version_name") or "").strip()

    # Exact names first: normalize_version() equates "2026.08.13-beta",
    # "-release" and "-tv-release", which are different builds.
    entries = [v for v in downloadable if name(v) == wanted]
    if not entries and wanted_norm:
        entries = [
            v for v in downloadable
            if utils.normalize_version(name(v)) == wanted_norm
            and not _OTHER_CHANNEL.search(name(v))
        ]
    if not entries:
        return None
    return min(entries, key=lambda v: _abi_rank(v, arch))


def get_latest_version(app_name: str, config: str) -> str:
    versions = _api_versions(config.get("package", ""))
    if versions:
        latest = (versions[0].get("version_name") or "").strip()
        if latest:
            return latest

    url = f"https://apkpure.net/{config['name']}/{config['package']}/versions"

    try:
        # Added headers to the request
        response = session.get(url, headers=HEADERS)
        response.raise_for_status()

        content_size = len(response.content)
        logging.info(f"URL:{response.url} [{content_size}/{content_size}] -> \"-\" [1]")

        soup = BeautifulSoup(response.content, "html.parser")
        version_info = soup.find('div', class_='ver-top-down')

        if version_info and 'data-dt-version' in version_info.attrs:
            return version_info['data-dt-version']

    except Exception as e:
        logging.error(f"Failed to fetch latest version for {app_name}: {e}")

    return None

def get_download_link(version: str, app_name: str, config: str) -> str:
    versions = _api_versions(config.get("package", ""))
    if versions:
        entry = _api_match(versions, version, config.get("arch") or "universal")
        if entry:
            abis = ", ".join(entry.get("native_code") or []) or "no native code"
            logging.info(f"APKPure API download link for {app_name} v{version} ({abis})")
            return _api_download_url(entry)
        logging.info(f"APKPure API has no downloadable {version} for {app_name}; trying the website")

    # APKPure often uses a specific structure for download pages
    url = f"https://apkpure.net/{config['name']}/{config['package']}/download/{version}"

    try:
        response = session.get(url, headers=HEADERS)
        response.raise_for_status()

        content_size = len(response.content)
        logging.info(f"URL:{response.url} [{content_size}/{content_size}] -> \"-\" [1]")

        soup = BeautifulSoup(response.content, "html.parser")

        # Look for the download link; APKPure sometimes uses 'download_link' or 'fast-download'
        download_link = soup.find('a', id='download_link')
        if download_link:
            return download_link['href']

    except Exception as e:
        logging.error(f"Failed to fetch download link for {app_name} v{version}: {e}")

    return None
