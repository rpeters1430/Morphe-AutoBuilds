"""Per-app build settings from patch-config.json.

Every entry in ``patch_list`` names an app and the patch source (patch system)
to build it with. Optional fields customise how that build is done; anything
left out falls back to the top-level ``defaults`` block, then to the built-in
defaults below.

    {
      "defaults": { "patches_channel": "stable", "experimental": false },
      "patch_list": [
        { "app_name": "youtube", "source": "morphe" },
        { "app_name": "reddit",  "source": "morphe",
          "patches_channel": "prerelease", "experimental": true,
          "arches": ["arm64-v8a"] }
      ]
    }

Fields (per entry or in ``defaults``):
  enabled          false skips the entry without deleting it.
  patches_channel  Release channel for the patch bundle (and integrations):
                   "stable" | "prerelease" | "dev" | "source" | "<exact tag>".
  cli_channel      Same, for the patcher CLI.
  experimental     Morphe only: also consider app versions the patches mark as
                   experimental when picking which app version to patch.
  force            Patch the newest store version even if the patches don't
                   list it as compatible (passes --force to the CLI).
  version          Pin the app version (overrides apps/<platform>/<app>.json).
  arches           Architectures to build (overrides arch-config.json).
  include_patches  Patch names to force-enable (adds to patches/<app>-<source>.txt).
  exclude_patches  Patch names to disable (adds to patches/<app>-<source>.txt).

Manual runs can override a single build via env vars: PATCHES_CHANNEL,
CLI_CHANNEL, EXPERIMENTAL, FORCE_PATCH, APP_VERSION (empty or "default" = no
override).
"""
import json
import logging
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PATCH_CONFIG = REPO_ROOT / "patch-config.json"
ARCH_CONFIG = REPO_ROOT / "arch-config.json"
PATCHES_DIR = REPO_ROOT / "patches"

VALID_ARCHES = ("arm64-v8a", "armeabi-v7a", "universal")

# Channel name -> release tag understood by utils.detect_release and the
# planner's release resolver. "source" keeps whatever sources/<source>.json says.
CHANNEL_TAGS = {
    "stable": "latest",      # newest non-prerelease release
    "prerelease": "",        # newest release of any kind, prereleases included
    "dev": "dev",            # newest release whose tag contains "dev"
}
SOURCE_CHANNEL = "source"

BUILTIN_DEFAULTS = {
    "enabled": True,
    "patches_channel": SOURCE_CHANNEL,
    "cli_channel": SOURCE_CHANNEL,
    "experimental": False,
    "force": False,
    "version": "",
    "arches": None,          # None -> arch-config.json -> ["universal"]
    "include_patches": [],
    "exclude_patches": [],
}

_ENV_OVERRIDES = {
    "PATCHES_CHANNEL": "patches_channel",
    "CLI_CHANNEL": "cli_channel",
    "EXPERIMENTAL": "experimental",
    "FORCE_PATCH": "force",
    "APP_VERSION": "version",
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_raw_config(path: Path = PATCH_CONFIG) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # tolerate a bare list of entries
        data = {"patch_list": data}
    return data


def _load_arch_map(path: Path = ARCH_CONFIG) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        (e["app_name"], e["source"]): e.get("arches", ["universal"])
        for e in data
        if isinstance(e, dict) and e.get("app_name") and e.get("source")
    }


def merge_entry(entry: dict, defaults: dict, arch_map: dict | None = None) -> dict:
    """Combine an entry with defaults into a fully populated settings dict."""
    merged = dict(BUILTIN_DEFAULTS)
    merged.update({k: v for k, v in (defaults or {}).items() if v is not None})
    merged.update({k: v for k, v in entry.items() if v is not None})

    merged["enabled"] = _as_bool(merged["enabled"])
    merged["experimental"] = _as_bool(merged["experimental"])
    merged["force"] = _as_bool(merged["force"])
    merged["version"] = str(merged.get("version") or "").strip()
    merged["patches_channel"] = str(merged["patches_channel"] or SOURCE_CHANNEL).strip()
    merged["cli_channel"] = str(merged["cli_channel"] or SOURCE_CHANNEL).strip()

    if not merged.get("arches"):
        arch_map = _load_arch_map() if arch_map is None else arch_map
        merged["arches"] = arch_map.get(
            (merged.get("app_name"), merged.get("source")), ["universal"]
        )
    return merged


def iter_entries(include_disabled: bool = False, path: Path = PATCH_CONFIG) -> list[dict]:
    """All patch_list entries with defaults applied, in config order."""
    raw = load_raw_config(path)
    defaults = raw.get("defaults") or {}
    arch_map = _load_arch_map()
    entries = []
    for entry in raw.get("patch_list", []):
        if not isinstance(entry, dict) or not entry.get("app_name") or not entry.get("source"):
            continue
        merged = merge_entry(entry, defaults, arch_map)
        if merged["enabled"] or include_disabled:
            entries.append(merged)
    return entries


def get_entry(app_name: str, source: str, apply_env: bool = True) -> dict:
    """Settings for one (app, source) build. Falls back to defaults if the pair
    isn't listed (e.g. a manual run of an unlisted combination)."""
    raw = load_raw_config() if PATCH_CONFIG.exists() else {}
    defaults = raw.get("defaults") or {}
    found = next(
        (
            e for e in raw.get("patch_list", [])
            if isinstance(e, dict) and e.get("app_name") == app_name and e.get("source") == source
        ),
        {"app_name": app_name, "source": source},
    )
    merged = merge_entry(found, defaults)

    if apply_env:
        for env_name, key in _ENV_OVERRIDES.items():
            value = (os.getenv(env_name) or "").strip()
            if not value or value.lower() == "default":
                continue
            merged[key] = _as_bool(value) if key in ("experimental", "force") else value
            logging.info(f"⚙️  {env_name}={value} overrides '{key}' for {app_name}/{source}")
    return merged


def channel_to_tag(channel: str) -> str | None:
    """Release tag for a channel, or None to keep the source file's own tag."""
    channel = (channel or SOURCE_CHANNEL).strip()
    if channel.lower() == SOURCE_CHANNEL:
        return None
    return CHANNEL_TAGS.get(channel.lower(), channel)


def is_cli_entry(repo_entry: dict) -> bool:
    name = (repo_entry.get("repo") or repo_entry.get("project") or "").lower()
    return name == "cli" or name.endswith("-cli") or name.endswith("/cli")


def apply_channels(repo_entries: list, patches_channel: str, cli_channel: str) -> list:
    """Return a copy of a sources/<source>.json list with the channels applied.

    The first element (the {"name": ...} metadata slot) and any entry without a
    repo are passed through untouched.
    """
    patches_tag = channel_to_tag(patches_channel)
    cli_tag = channel_to_tag(cli_channel)
    out = []
    for item in repo_entries:
        if not isinstance(item, dict) or not (item.get("repo") or item.get("project")):
            out.append(item)
            continue
        tag = cli_tag if is_cli_entry(item) else patches_tag
        out.append({**item, "tag": tag} if tag is not None else dict(item))
    return out


def build_options_signature(entry: dict) -> str:
    """Short string of the settings that change the build output without
    changing the patch source release. Empty for default settings so existing
    manifests stay valid."""
    parts = []
    if entry.get("experimental"):
        parts.append("exp")
    if entry.get("force"):
        parts.append("force")
    if entry.get("include_patches"):
        parts.append("inc=" + ",".join(sorted(entry["include_patches"])))
    if entry.get("exclude_patches"):
        parts.append("exc=" + ",".join(sorted(entry["exclude_patches"])))
    return "|opts:" + ";".join(parts) if parts else ""


def patch_selection(entry: dict) -> tuple[list[str], list[str]]:
    """(include, exclude) patch names from patches/<app>-<source>.txt plus the
    entry's include_patches/exclude_patches."""
    include = list(entry.get("include_patches") or [])
    exclude = list(entry.get("exclude_patches") or [])
    patches_path = PATCHES_DIR / f"{entry['app_name']}-{entry['source']}.txt"
    if patches_path.exists():
        for line in patches_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("-"):
                exclude.append(line[1:].strip())
            elif line.startswith("+"):
                include.append(line[1:].strip())
    return include, exclude
