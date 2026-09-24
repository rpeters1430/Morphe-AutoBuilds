#!/usr/bin/env python3
"""Generate data.json and apps.json for the GitHub Pages download portal and Obtainium."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
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

    if console:
        console.print(f"[cyan]Generating portal metadata for repo: [bold]{repo_slug}[/bold]...[/cyan]")

    # patch-config.json entries with defaults and arch-config.json applied
    patch_list = build_config.iter_entries(include_disabled=True, path=PATCH_CONFIG_PATH)
    # Longest name first so "youtube-music-..." isn't claimed by "youtube".
    app_names = sorted({e["app_name"] for e in patch_list}, key=len, reverse=True)
    packages = parse_app_packages()
    release_data, published_at = fetch_release_assets(repo_slug)
    assets = release_data.get("assets", [])

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
        pkg = packages.get(app_name, f"com.{app_name}")
        icon = APP_ICONS.get(app_name, "")

        app_assets = assets_by_app.get(app_name, [])

        # Default fallbacks if no release assets exist yet
        if not app_assets:
            for t_arch in entry["arches"]:
                app_assets.append({
                    "filename": f"{app_name}-{t_arch}.apk",
                    "arch": t_arch,
                    "download_url": f"https://github.com/{repo_slug}/releases/download/latest/{app_name}-{t_arch}.apk",
                    "size": "Auto",
                })

        # Only this app's APKs, not e.g. youtube-music's when app_name is youtube
        arch_alt = "|".join(build_config.VALID_ARCHES)
        apk_filter = f"^{_regex_literal(app_name)}-({arch_alt})-.*\\.apk$"

        # Obtainium app JSON, used for both the deep link
        # (obtainium://app/{...}) and the bulk import feed. Obtainium only reads
        # filters from additionalSettings, which must be a JSON-encoded string.
        # Every app shares the one 'latest' release, so its tag can't tell
        # versions apart; the newest matching asset's upload date does.
        obtainium_config = {
            "id": pkg,
            "url": f"https://github.com/{repo_slug}",
            "author": repo_slug.split("/")[0],
            "name": display_name,
            "additionalSettings": json.dumps({
                "apkFilterRegEx": apk_filter,
                "invertAPKFilter": False,
                "useLatestAssetDateAsReleaseDate": True,
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
        }
        apps_portal_data.append(app_entry)

        # Feed item for Obtainium bulk import
        obtainium_apps.append(obtainium_config)

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
