"""Patch Resolver and Cache for Morphe Builder TUI.

Fetches and caches patch lists from upstream patch repositories (Morphe, ReVanced, Extended)
so users can browse all recommended and available patches for any app.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO_ROOT / ".cache" / "patches"
APPS_DIR = REPO_ROOT / "apps"
SOURCES_DIR = REPO_ROOT / "sources"

# Known upstream endpoints for quick resolution
SOURCE_ENDPOINTS = {
    "morphe": "https://raw.githubusercontent.com/MorpheApp/morphe-patches/main/patches-list.json",
    "revanced-extended": "https://raw.githubusercontent.com/inotia00/revanced-patches/revanced-extended/patches.json",
    "revanced-extended-dev": "https://raw.githubusercontent.com/inotia00/revanced-patches/revanced-extended/patches.json",
    "revanced-anddea": "https://raw.githubusercontent.com/anddea/revanced-patches/main/patches.json",
}


def get_app_package_name(app_name: str) -> str:
    """Find Android package name from apps/*/<app_name>.json."""
    if APPS_DIR.exists():
        for p in APPS_DIR.rglob(f"{app_name}.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "package" in data and data["package"]:
                        return data["package"]
            except Exception:
                pass
    return f"com.{app_name}"


def fetch_source_patches_raw(source_name: str) -> Any:
    """Fetch patch definitions from upstream or local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{source_name}.json"

    # Check cache first
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Try fetching online
    url = SOURCE_ENDPOINTS.get(source_name)
    if not url:
        # Check sources/<source_name>.json to see if repo is known
        source_json = SOURCES_DIR / f"{source_name}.json"
        if source_json.exists():
            try:
                with open(source_json, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                items = s_data if isinstance(s_data, list) else [s_data]
                for item in items:
                    if isinstance(item, dict) and "patches" in item.get("repo", ""):
                        user = item.get("user")
                        repo = item.get("repo")
                        url = f"https://raw.githubusercontent.com/{user}/{repo}/main/patches-list.json"
                        break
            except Exception:
                pass

    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Morphe-AutoBuilds/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                return data
        except Exception as e:
            logging.debug("Could not fetch remote patches from %s: %s", url, e)

    return None


def get_available_patches_for_app(app_name: str, source_name: str) -> list[dict[str, Any]]:
    """Returns a list of dicts: {'name': str, 'description': str, 'default': bool}."""
    pkg = get_app_package_name(app_name)
    raw = fetch_source_patches_raw(source_name)

    patches: list[dict[str, Any]] = []

    if raw:
        # Case 1: Morphe format: {'NOTE': ..., 'version': ..., 'patches': [ {...} ] }
        if isinstance(raw, dict) and "patches" in raw and isinstance(raw["patches"], list):
            for p in raw["patches"]:
                p_name = p.get("name", "")
                p_desc = p.get("description") or ""
                p_default = bool(p.get("default", True))
                compat = p.get("compatiblePackages") or []

                matches = False
                if not compat:  # Universal patch
                    matches = True
                else:
                    for c in compat:
                        if isinstance(c, dict) and c.get("packageName") == pkg:
                            matches = True
                            break
                        elif isinstance(c, str) and c == pkg:
                            matches = True
                            break

                if matches and p_name:
                    patches.append({
                        "name": p_name,
                        "description": p_desc,
                        "default": p_default,
                    })

        # Case 2: inotia00 / revanced-patches format: list of patch dicts
        elif isinstance(raw, list):
            for p in raw:
                if not isinstance(p, dict):
                    continue
                p_name = p.get("name", "")
                p_desc = p.get("description") or ""
                p_default = bool(p.get("use", True))
                compat = p.get("compatiblePackages") or {}

                matches = False
                if not compat:
                    matches = True
                elif isinstance(compat, dict) and pkg in compat:
                    matches = True
                elif isinstance(compat, list):
                    for c in compat:
                        if isinstance(c, dict) and c.get("name") == pkg:
                            matches = True
                            break
                        elif isinstance(c, str) and c == pkg:
                            matches = True
                            break

                if matches and p_name:
                    patches.append({
                        "name": p_name,
                        "description": p_desc,
                        "default": p_default,
                    })

    # Sort alphabetically by name
    patches.sort(key=lambda x: x["name"].lower())
    return patches
