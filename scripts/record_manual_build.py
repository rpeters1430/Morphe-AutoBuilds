#!/usr/bin/env python3
"""Record a manual build's APKs in the release's manifest.json.

Run by manual-patch.yml after it uploads the APKs, with the same env vars the
build used (APP_NAME, SOURCE, and any PATCHES_CHANNEL / APP_VERSION / ...
overrides). Without this, the daily planner only found the manual APK
indirectly (its manifest filename had been deleted) and kept a stale
built_version and source signature for it.

For every built APK of a configured (app, source, arch):
  - apk / built_version / follows_store are updated, and any failure backoff
    is cleared (a build just succeeded).
  - Built with the configured settings: the current source signature is
    stored too, so the daily run treats it exactly like one of its own builds
    and does not rebuild it until something changes.
  - Built with overrides (a pinned version, another patches channel or tag,
    extra patches, ...): the overrides are stored under "manual_build" and the
    signature is left alone, so the daily run keeps this APK until the
    patches or settings change and then replaces it with a normal build.

Best-effort: any problem is logged and the script exits 0; the daily planner
still recovers the APK from the release on its own.
"""
import datetime
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_app_updates as planner  # noqa: E402
from record_build import detect_arch_from_filename, extract_version_from_filename  # noqa: E402
from src import build_config  # noqa: E402

# Settings a manual run can override; "arches" is left out because building a
# single arch with the configured settings is still a normal build.
_OVERRIDABLE = ("patches_channel", "cli_channel", "experimental", "force", "version",
                "exclusive", "continue_on_error", "include_patches", "exclude_patches")


def _overrides(app: str, source: str) -> dict:
    configured = build_config.get_entry(app, source, apply_env=False)
    effective = build_config.get_entry(app, source, apply_env=True)
    return {k: effective[k] for k in _OVERRIDABLE if effective[k] != configured[k]}


def _follows_store(apk_name: str) -> bool:
    meta = Path("build_meta") / f"{apk_name}.json"
    try:
        return bool(json.loads(meta.read_text(encoding="utf-8")).get("follows_store"))
    except Exception:
        return False


def main() -> int:
    app = (os.environ.get("APP_NAME") or "").strip()
    source = (os.environ.get("SOURCE") or "").strip()
    apks = sorted(Path(".").glob("*.apk"))
    if not app or not source or not apks:
        print("Nothing to record.")
        return 0

    configured_keys = {
        planner.make_manifest_key(e["app_name"], e["source"], e["arch"])
        for e in planner.build_full_matrix()
    }

    asset_names = planner.fetch_release_asset_names() or []
    manifest = planner.fetch_existing_manifest(asset_names)
    if manifest is None:
        print("The release has no manifest.json; the next daily run creates it.")
        return 0
    entries = manifest.setdefault("entries", {})

    overrides = _overrides(app, source)
    settings = build_config.get_entry(app, source, apply_env=False)
    source_sig = ""
    if not overrides:
        source_sig = planner.get_source_signature(
            source, settings["patches_channel"], settings["cli_channel"]
        ) + build_config.build_options_signature(settings)
        if planner._is_unreliable_source_sig(source_sig):
            source_sig = ""  # couldn't read the patch releases; leave it as it was

    changed = False
    for apk in apks:
        arch = detect_arch_from_filename(apk.name)
        key = planner.make_manifest_key(app, source, arch)
        if key not in configured_keys:
            print(f"  skip {apk.name}: {key} is not a configured build")
            continue
        entry = entries.setdefault(key, {
            "app_name": app, "source": source, "arch": arch,
            "config_version": "", "source_sig": "", "apk": "", "built_version": "",
        })
        entry["apk"] = apk.name
        entry["built_version"] = extract_version_from_filename(apk.name)
        entry["follows_store"] = _follows_store(apk.name)
        for k in ("failed_sig", "failed_attempts", "last_failed_at",
                  "pending_source_sig", "pending_store_version"):
            entry.pop(k, None)
        if overrides:
            entry["manual_build"] = {
                "date": datetime.date.today().isoformat(),
                "overrides": overrides,
            }
        else:
            entry.pop("manual_build", None)
            entry["config_version"] = settings["version"] or planner.load_app_config_version(app)
            if source_sig:
                entry["source_sig"] = source_sig
        print(f"  recorded {key} -> {apk.name}"
              + (f" (overrides: {overrides})" if overrides else ""))
        changed = True

    if not changed:
        return 0
    Path(planner.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rc, _, err = planner.run_gh(["release", "upload", planner.RELEASE_TAG,
                                 planner.MANIFEST_NAME, "--clobber"])
    if rc != 0:
        print(f"⚠️  could not upload {planner.MANIFEST_NAME}: {err.strip()[:200]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logging.warning(f"record_manual_build failed: {e}")
        sys.exit(0)
