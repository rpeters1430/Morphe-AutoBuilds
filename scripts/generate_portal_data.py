#!/usr/bin/env python3
"""Generate data.json and apps.json for the GitHub Pages download portal and Obtainium."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import datetime
import html
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Load by path so this runs without the builder's dependencies.
_spec = importlib.util.spec_from_file_location("build_config", REPO_ROOT / "src" / "build_config.py")
build_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_config)

DEFAULT_REPO = "rpeters1430/Morphe-AutoBuilds"
DOCS_DIR = REPO_ROOT / "docs"
PATCH_CONFIG_PATH = REPO_ROOT / "patch-config.json"
APPS_DIR = REPO_ROOT / "apps"
DATA_JSON_PATH = DOCS_DIR / "data.json"
DATA_JS_PATH = DOCS_DIR / "data.js"
OBTAINIUM_JSON_PATH = DOCS_DIR / "apps.json"
# Static per-app pages Obtainium's HTML source reads instead of the GitHub API.
OBTAINIUM_PAGES_DIR = DOCS_DIR / "obtainium"
# ISO-8601 upload time written next to each APK link on the per-arch pages.
OBTAINIUM_DATE_REGEX = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"

# Package IDs of the patched APKs where the patches rename the app (GmsCore
# support, Piko's X build), keyed by (app_name, source). Obtainium refuses to install an APK
# whose package ID differs from the entry's ID, so the feed must use these.
PATCHED_PACKAGES = {
    ("youtube", "morphe"): "app.morphe.android.youtube",
    ("youtube-music", "morphe"): "app.morphe.android.apps.youtube.music",
    ("x-new", "piko-newx"): "com.twitter.android.piko",
    ("google-photos", "akash-photos"): "app.morphe.android.apps.photos",
}

CATEGORIES = {
    "youtube": "Video & Streaming",
    "youtube-music": "Music & Audio",
    "spotify": "Music & Audio",
    "soundcloud": "Music & Audio",
    "pandora": "Music & Audio",
    "reddit": "Social & Community",
    "instagram": "Social & Community",
    "tiktok": "Social & Community",
    "threads": "Social & Community",
    "tumblr": "Social & Community",
    "twitter": "Social & Community",
    "x": "Social & Community",
    "pinterest": "Social & Community",
    "messenger": "Communication",
    "discord": "Communication",
    "telegram": "Communication",
    "viber": "Communication",
    "proton-mail": "Communication",
    "lightroom": "Photography",
    "google-photos": "Photography",
    "pixiv": "Art & Design",
    "duolingo": "Education",
    "hellochinese": "Education",
    "mimo": "Education",
    "photomath": "Education",
    "snorelab": "Health & Fitness",
    "strava": "Health & Fitness",
    "macrofactor": "Health & Fitness",
    "lyfta": "Health & Fitness",
    "ventusky": "Weather",
    "windy": "Weather",
    "camscanner": "Productivity",
    "xodo": "Productivity",
    "rar": "Productivity",
    "solid": "Productivity",
    "tasker": "Productivity",
    "adobe-acrobat": "Productivity",
    "adobe-scan": "Productivity",
    "aftership": "Productivity",
    "brave-beta": "Browsers",
    "anime-depth-wallpapers": "Personalization",
}

APP_ICONS = {
    "youtube": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/youtube.svg",
    "youtube-music": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/youtube-music.svg",
    "spotify": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/spotify.svg",
    "soundcloud": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/soundcloud.svg",
    "reddit": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/reddit.svg",
    "instagram": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/instagram.svg",
    "tiktok": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/tiktok.svg",
    "twitter": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/twitter.svg",
    "x": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/twitter.svg",
    "pinterest": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/pinterest.svg",
    "discord": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/discord.svg",
    "telegram": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/telegram.svg",
    "duolingo": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/duolingo.svg",
    "strava": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/strava.svg",
    "google-photos": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/google-photos.svg",
}


def get_repo_slug() -> str:
    """Detect GitHub repo slug (e.g. rpeters1430/Morphe-AutoBuilds)."""
    if os.getenv("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        proc = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner"], capture_output=True, text=True)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data.get("nameWithOwner", DEFAULT_REPO)
    except Exception:
        pass
    return DEFAULT_REPO


def get_pages_base_url(repo_slug: str) -> str:
    """GitHub Pages URL of the catalog, e.g. https://owner.github.io/repo/."""
    if os.getenv("PORTAL_BASE_URL"):
        return os.environ["PORTAL_BASE_URL"].rstrip("/") + "/"
    owner, _, repo = repo_slug.partition("/")
    return f"https://{owner.lower()}.github.io/{repo}/"


def _page(title: str, body: str) -> str:
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"robots\" content=\"noindex\"><title>{html.escape(title)}</title></head>\n"
            f"<body>\n<h1>{html.escape(title)}</h1>\n<ul>\n{body}</ul>\n</body></html>\n")


def write_obtainium_pages(key: str, display_name: str, app_assets: list[dict], base_url: str) -> str | None:
    """Write the static pages one Obtainium entry polls; return the entry URL.

    Obtainium's GitHub source calls api.github.com on every check, which is
    limited to 60 requests an hour without a token, so a feed of ~100 apps
    exhausts it in one refresh. GitHub Pages files have no such limit and
    the APK links (github.com/.../releases/download/...) are not API calls.

    Layout: obtainium/<key>.html links to one page per architecture; Obtainium
    picks the device's architecture from those links, then reads the single
    APK link and its upload time from obtainium/<key>/<arch>.html.
    """
    newest: dict[str, dict] = {}
    for asset in app_assets:
        current = newest.get(asset["arch"])
        if current is None or (asset.get("uploaded_at") or "") > (current.get("uploaded_at") or ""):
            newest[asset["arch"]] = asset
    if not newest:
        return None
    arch_dir = OBTAINIUM_PAGES_DIR / key
    arch_dir.mkdir(parents=True, exist_ok=True)
    index_items = ""
    for arch, asset in sorted(newest.items()):
        uploaded = asset.get("uploaded_at") or ""
        url = html.escape(asset["download_url"], quote=True)
        name = html.escape(asset["filename"])
        (arch_dir / f"{arch}.html").write_text(_page(
            f"{display_name} ({arch})",
            f'<li><a href="{url}">{name}</a> <time>{html.escape(uploaded)}</time></li>\n'), encoding="utf-8")
        arch_url = html.escape(f"{base_url}obtainium/{key}/{arch}.html", quote=True)
        index_items += f'<li><a href="{arch_url}">{html.escape(arch)}</a></li>\n'
    (OBTAINIUM_PAGES_DIR / f"{key}.html").write_text(_page(display_name, index_items), encoding="utf-8")
    return f"{base_url}obtainium/{key}.html"


def fetch_release_assets(repo_slug: str) -> tuple[dict[str, Any], str]:
    """Fetch assets from the 'latest' release using gh CLI or fallback."""
    try:
        proc = subprocess.run(
            ["gh", "release", "view", "latest", "--repo", repo_slug, "--json", "assets,publishedAt,tagName,url"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data, data.get("publishedAt", "")
    except Exception:
        pass
    return {}, ""


def _regex_literal(text: str) -> str:
    """re.escape without escaping '-', which is literal outside [] anyway."""
    return re.escape(text).replace("\\-", "-")


def fetch_release_manifest(repo_slug: str) -> dict:
    """Download only release metadata; never download the APK collection."""
    try:
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                ["gh", "release", "download", "latest", "--repo", repo_slug,
                 "--pattern", "manifest.json", "--dir", directory],
                capture_output=True, text=True, check=True, timeout=120,
            )
            data = json.loads(Path(directory, "manifest.json").read_text(encoding="utf-8"))
            return data if isinstance(data.get("entries"), dict) else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def source_output_name(source: str) -> str:
    try:
        data = json.loads((REPO_ROOT / "sources" / f"{source}.json").read_text(encoding="utf-8"))
        return (data[0] if isinstance(data, list) else data).get("name") or source
    except (OSError, ValueError, IndexError, AttributeError):
        return source


def build_health(arch: str, record: dict, available: bool, lookup_ok: bool) -> dict:
    failed = bool(record.get("last_error") or record.get("failed_attempts"))
    status = ("retained" if failed else "available") if available else (
        "unknown" if not lookup_ok else "unavailable" if record.get("apk") or failed else "not_built")
    retry_after = ""
    if available and int(record.get("failed_attempts") or 0) >= 2:
        try:
            retry_after = (datetime.date.fromisoformat(record["last_failed_at"]) + datetime.timedelta(days=7)).isoformat()
        except (KeyError, ValueError):
            pass
    return {"arch": arch, "status": status, "last_success_at": record.get("last_success_at", ""),
            "last_attempt_at": record.get("last_attempt_at", ""), "last_error": record.get("last_error", ""),
            "run_url": record.get("run_url", ""), "retry_after": retry_after}


def parse_app_packages() -> dict[str, str]:
    """Find package name for each app."""
    packages = {}
    if APPS_DIR.exists():
        for p in APPS_DIR.rglob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if "package" in d:
                        packages[p.stem] = d["package"]
            except Exception:
                pass
    return packages


def generate_portal_assets(console=None) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    repo_slug = get_repo_slug()
    base_url = get_pages_base_url(repo_slug)
    # Rebuilt from scratch so removed apps and arches don't leave stale pages.
    shutil.rmtree(OBTAINIUM_PAGES_DIR, ignore_errors=True)
    OBTAINIUM_PAGES_DIR.mkdir(parents=True, exist_ok=True)

    if console:
        console.print(f"[cyan]Generating portal metadata for repo: [bold]{repo_slug}[/bold]...[/cyan]")

    # patch-config.json entries with defaults and arch-config.json applied
    patch_list = build_config.iter_entries(include_disabled=True, path=PATCH_CONFIG_PATH)
    # Longest name first so "youtube-music-..." isn't claimed by "youtube".
    app_names = sorted({e["app_name"] for e in patch_list}, key=len, reverse=True)
    packages = parse_app_packages()
    release_data, published_at = fetch_release_assets(repo_slug)
    assets = release_data.get("assets", [])
    manifest = fetch_release_manifest(repo_slug).get("entries", {})
    lookup_ok = "assets" in release_data
    output_sources: dict[str, set[str]] = {}
    for path in (REPO_ROOT / "sources").glob("*.json"):
        output_sources.setdefault(source_output_name(path.stem), set()).add(path.stem)
    asset_owners = {record.get("apk"): key for key, record in manifest.items() if record.get("apk")}

    # Asset map: app_name -> list of assets
    # Format of asset name typically: {app_name}-{arch}-patch-v{version}.apk or {app_name}-{arch}.apk
    assets_by_app: dict[str, list[dict[str, Any]]] = {}
    for a in assets:
        name = a.get("name", "")
        if not name.endswith(".apk"):
            continue
        download_url = a.get("url") or f"https://github.com/{repo_slug}/releases/download/latest/{name}"
        size_bytes = a.get("size", 0)
        size_mb = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes else ""

        # Detect arch
        arch = "universal"
        if "arm64-v8a" in name:
            arch = "arm64-v8a"
        elif "armeabi-v7a" in name:
            arch = "armeabi-v7a"

        # Built APKs are named {app_name}-{arch}-{source name}-v{version}.apk
        matched_app = next(
            (a for a in app_names if name.startswith(f"{a}-{arch}-")),
            next((a for a in app_names if name.startswith(f"{a}-")), None),
        )

        if matched_app:
            assets_by_app.setdefault(matched_app, []).append({
                "filename": name,
                "arch": arch,
                "download_url": download_url,
                "size": size_mb,
                "uploaded_at": a.get("updatedAt") or a.get("createdAt") or "",
            })

    apps_portal_data = []
    obtainium_apps = []

    for entry in patch_list:
        app_name = entry.get("app_name", "")
        if not app_name:
            continue

        enabled = entry.get("enabled", True)
        source = entry.get("source", "morphe")
        category = CATEGORIES.get(app_name, "Utilities & Tools")
        display_name = app_name.replace("-", " ").title()
        # Output package: a configured "Change package name" option, a known
        # rename by the patches, or the stock app's package.
        pkg = (
            (entry["patch_options"].get("Change package name") or {}).get("packageName")
            or PATCHED_PACKAGES.get((app_name, source))
            or packages.get(app_name, f"com.{app_name}")
        )
        icon = APP_ICONS.get(app_name, "")

        # Match by manifest identity, with exact legacy filename fallback.
        # Grouping by app alone mixes APKs from different patch sources.
        output_name = source_output_name(source)
        app_assets = []
        health = []
        for arch in entry["arches"]:
            record = manifest.get(f"{app_name}|{source}|{arch}", {})
            candidates = [a for a in assets_by_app.get(app_name, []) if a["arch"] == arch]
            recorded = next((a for a in candidates if a["filename"] == record.get("apk")), None)
            selected = [recorded] if recorded else [a for a in candidates
                if a["filename"] not in asset_owners and (
                    re.fullmatch(f"{re.escape(app_name)}-{re.escape(arch)}-{re.escape(source)}-r[0-9a-f]{{16}}-v.+\\.apk", a["filename"])
                    or len(output_sources.get(output_name, {source})) == 1
                    and a["filename"].startswith(f"{app_name}-{arch}-{output_name}-v"))]
            health.append(build_health(arch, record, bool(selected), lookup_ok))
            for asset in selected:
                metadata = record.get("artifact", {}) if record.get("apk") == asset["filename"] else {}
                app_assets.append({**asset, "metadata": metadata})

        actual_packages = {a["metadata"]["package"] for a in app_assets if a["metadata"].get("package")}
        if len(actual_packages) == 1:
            pkg = next(iter(actual_packages))

        # Obtainium app JSON, used for both the deep link
        # (obtainium://app/{...}) and the bulk import feed. Obtainium only reads
        # settings from additionalSettings, which must be a JSON-encoded string.
        # The HTML source polls static GitHub Pages files (no API rate limit).
        # Only this entry's attributed APKs are listed there, so no APK filter
        # is needed. Every app shares the one 'latest' release, so the upload
        # time printed next to the APK link is what marks a new build.
        key = re.sub(r"[^A-Za-z0-9._-]", "_", f"{app_name}-{source}")
        page_url = None if len(actual_packages) > 1 else write_obtainium_pages(key, display_name, app_assets, base_url)
        obtainium_config = None
        if page_url:
            obtainium_config = {
                "id": pkg,
                "url": page_url,
                "author": repo_slug.split("/")[0],
                "name": display_name,
                "overrideSource": "HTML",
                "additionalSettings": json.dumps({
                    "intermediateLink": [{
                        "customLinkFilterRegex": f"/obtainium/{_regex_literal(key)}/[^/]+\\.html$",
                        "autoLinkFilterByArch": True,
                    }],
                    "customLinkFilterRegex": "\\.apk$",
                    "releaseDateRegEx": OBTAINIUM_DATE_REGEX,
                    "versionDetection": False,
                    "releaseDateAsVersion": True,
                }),
            }

        app_entry = {
            "name": display_name,
            "slug": app_name,
            "source": source,
            "package": pkg,
            "category": category,
            "icon": icon,
            "enabled": enabled,
            "channel": entry["patches_channel"],
            "downloads": app_assets,
            "obtainium_config": obtainium_config,
            "health": health,
            "status": ("retained" if any(h["status"] == "retained" for h in health)
                       else "partial" if app_assets and any(h["status"] != "available" for h in health)
                       else "available" if app_assets
                       else "unknown" if not lookup_ok
                       else "unavailable" if any(h["status"] == "unavailable" for h in health)
                       else "not_built"),
        }
        apps_portal_data.append(app_entry)

        # Feed item for Obtainium bulk import
        if enabled and obtainium_config:
            obtainium_apps.append(obtainium_config)

    apps_portal_data.sort(key=lambda a: (a["name"].casefold(), a["source"].casefold()))
    obtainium_apps.sort(key=lambda a: str(a.get("name", "")).casefold())

    payload = {
        "repository": repo_slug,
        "release_tag": "latest",
        "last_updated": published_at or "Recent",
        "total_apps": len(apps_portal_data),
        "apps": apps_portal_data,
    }

    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write("window.PORTAL_DATA = " + json.dumps(payload, indent=2) + ";\n")

    with open(OBTAINIUM_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"apps": obtainium_apps}, f, indent=2)

    if console:
        console.print(f"[bold green]✓ Successfully generated {DATA_JSON_PATH.name}, {DATA_JS_PATH.name}, and {OBTAINIUM_JSON_PATH.name}![/bold green]\n")


if __name__ == "__main__":
    generate_portal_assets()
    print("Portal data generated in docs/")
