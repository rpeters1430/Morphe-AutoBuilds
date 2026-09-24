#!/usr/bin/env python3
"""Check patch-config.json for mistakes before any build runs.

Errors (exit 1): unknown fields, wrong types, unknown sources, bad arches or
channels. Warnings: duplicate entries, apps with no download config.

Run locally with:  python scripts/validate_config.py
"""
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Load the module by path so this runs without the builder's dependencies
# (importing the src package pulls in curl_cffi and PyGithub).
_spec = importlib.util.spec_from_file_location("build_config", REPO_ROOT / "src" / "build_config.py")
build_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_config)

SOURCES_DIR = REPO_ROOT / "sources"
APPS_DIR = REPO_ROOT / "apps"

FIELD_TYPES = {
    "app_name": str,
    "source": str,
    "enabled": bool,
    "patches_channel": str,
    "cli_channel": str,
    "experimental": bool,
    "force": bool,
    "version": str,
    "arches": list,
    "include_patches": list,
    "exclude_patches": list,
    "exclusive": bool,
    "continue_on_error": bool,
    "patch_options": dict,
}
DEFAULTS_FIELDS = set(FIELD_TYPES) - {"app_name", "source"}
ROOT_FIELDS = {"defaults", "patch_list"}
CHANNEL_NAMES = set(build_config.CHANNEL_TAGS) | {build_config.SOURCE_CHANNEL}


def check_fields(where: str, obj: dict, allowed: set, errors: list) -> None:
    for key, value in obj.items():
        if key.startswith("$") or key.startswith("_"):  # "$schema", "_comment"
            continue
        if key not in allowed:
            errors.append(f"{where}: unknown field '{key}'")
            continue
        expected = FIELD_TYPES[key]
        if not isinstance(value, expected):
            errors.append(f"{where}: '{key}' should be {expected.__name__}, got {type(value).__name__}")
            continue
        if key in ("patches_channel", "cli_channel") and not value.strip():
            errors.append(f"{where}: '{key}' is empty (use one of {sorted(CHANNEL_NAMES)} or a tag)")
        if key == "arches":
            bad = [a for a in value if a not in build_config.VALID_ARCHES]
            if bad or not value:
                errors.append(f"{where}: arches must be a non-empty subset of {list(build_config.VALID_ARCHES)}")
        if key in ("include_patches", "exclude_patches") and not all(isinstance(p, str) for p in value):
            errors.append(f"{where}: '{key}' must be a list of patch names")
        if key == "patch_options":
            for patch, opts in value.items():
                if not isinstance(opts, dict):
                    errors.append(f"{where}: patch_options['{patch}'] must be an object of option key -> value")


def check_selection(where: str, entry: dict, warnings: list) -> None:
    """Warn about patch selections that can't do what they look like."""
    include = set(entry.get("include_patches") or []) | set(entry.get("patch_options") or {})
    exclude = set(entry.get("exclude_patches") or [])
    for name in sorted(include & exclude):
        warnings.append(f"{where}: '{name}' is both enabled and excluded; it stays excluded")
    if entry.get("exclusive") and not include:
        rules = build_config.PATCHES_DIR / f"{entry['app_name']}-{entry['source']}.txt"
        has_plus = rules.exists() and any(
            line.strip().startswith("+") for line in rules.read_text(encoding="utf-8").splitlines()
        )
        if not has_plus:
            warnings.append(f"{where}: exclusive is on but no patches are enabled, so nothing will be patched")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    raw = build_config.load_raw_config()
    if not isinstance(raw, dict):
        errors.append("top level must be an object with a 'patch_list' array")
        raw = {}
    for key in raw:
        if key not in ROOT_FIELDS and not key.startswith(("$", "_")):
            errors.append(f"unknown top-level field '{key}' (expected one of {sorted(ROOT_FIELDS)})")
    if not isinstance(raw.get("patch_list"), list):
        errors.append("'patch_list' is missing or not an array")
        raw["patch_list"] = []
    if not isinstance(raw.get("defaults", {}), dict):
        errors.append("'defaults' must be an object")
        raw["defaults"] = {}
    check_fields("defaults", raw.get("defaults") or {}, DEFAULTS_FIELDS, errors)

    sources = {f.stem for f in SOURCES_DIR.glob("*.json")}
    seen = set()
    for i, entry in enumerate(raw.get("patch_list", [])):
        where = f"patch_list[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: must be an object")
            continue
        app, src = entry.get("app_name"), entry.get("source")
        if app and src:
            where = f"{where} ({app}/{src})"
        if not app or not src:
            errors.append(f"{where}: 'app_name' and 'source' are required")
            continue
        check_fields(where, entry, set(FIELD_TYPES), errors)

        if src not in sources:
            errors.append(f"{where}: no sources/{src}.json")
        if not any((APPS_DIR / platform / f"{app}.json").exists() for platform in (
            "apkmirror", "apkpure", "uptodown", "aptoide", "github", "apkcombo"
        )):
            warnings.append(f"{where}: no apps/<platform>/{app}.json, so the APK can't be downloaded")
        if (app, src) in seen:
            warnings.append(f"{where}: duplicate entry; only the first one is used")
        seen.add((app, src))

    # Merging needs a well-formed file; skip the summary if it isn't.
    merged = [] if errors else build_config.iter_entries(include_disabled=True)
    enabled = [e for e in merged if e["enabled"]]
    for e in enabled:
        check_selection(f"{e['app_name']}/{e['source']}", e, warnings)
    channels = {}
    for e in enabled:
        key = (e["patches_channel"], e["cli_channel"], e["experimental"])
        channels[key] = channels.get(key, 0) + 1

    for w in warnings:
        print(f"::warning::{w}" if _in_actions() else f"WARNING: {w}")
    for err in errors:
        print(f"::error::{err}" if _in_actions() else f"ERROR: {err}")

    print(f"\n{len(enabled)} enabled / {len(merged) - len(enabled)} disabled entries")
    for (pc, cc, exp), n in sorted(channels.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d} x patches={pc} cli={cc} experimental={exp}")
    if errors:
        print(f"\n{len(errors)} error(s) in patch-config.json")
        return 1
    print("patch-config.json OK")
    return 0


def _in_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS") == "true"


if __name__ == "__main__":
    sys.exit(main())
