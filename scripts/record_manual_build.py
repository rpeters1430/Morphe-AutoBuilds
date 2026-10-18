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

Failures preserve existing records and return nonzero so cleanup cannot
remove an APK before the manifest advances. The daily planner can recover
published immutable APKs if the manifest upload failed.
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


def apply_failure_records(entries: dict, records: list[dict], configured_keys: set[str]) -> bool:
    changed = False
    for record in records:
        key = record.get("key")
        if key not in configured_keys or record.get("status") != "failed":
            continue
        entry = entries.setdefault(key, {"app_name": record.get("app_name"),
            "source": record.get("source"), "arch": record.get("arch")})
        entry["last_error"] = record.get("error") or "Manual build failed; see workflow logs."
        for field in ("last_attempt_at", "run_url"):
            if field in record:
                entry[field] = record[field]
        changed = True
    return changed


def main() -> int:
    app = (os.environ.get("APP_NAME") or "").strip()
    source = (os.environ.get("SOURCE") or "").strip()
    apks = sorted(Path("verified-apks").glob("*.apk"))
    failure_records = [json.loads(p.read_text(encoding="utf-8")) for p in Path("build_records").glob("*.json")]
    if not app or not source or not (apks or failure_records):
        print("Nothing to record.")
        return 0

    configured_keys = {
        planner.make_manifest_key(e["app_name"], e["source"], e["arch"])
        for e in planner.build_full_matrix()
    }

    asset_names = planner.fetch_release_asset_names()
    if asset_names is None:
        print("Could not confirm release assets; preserving the existing manifest.")
        return 1
    manifest = planner.fetch_existing_manifest(asset_names)
    if manifest is None and planner.MANIFEST_NAME in asset_names:
        print("Existing manifest could not be read; refusing to replace its other app records.")
        return 1
    if manifest is None and not apks:
        print("No release manifest to update after failed manual build.")
        return 0
    manifest = manifest or {"entries": {}}
    entries = manifest.setdefault("entries", {})
    # This step also runs after a failed upload so it can record failures.
    # Locally verified bytes alone do not prove the APK was published.
    published = os.environ.get("BUILD_PUBLISHED", "false").lower() == "true"
    rejected = [apk for apk in apks if not published or apk.name not in asset_names]
    for apk in rejected:
        arch = detect_arch_from_filename(apk.name)
        failure_records.append({"key": planner.make_manifest_key(app, source, arch),
            "app_name": app, "source": source, "arch": arch, "status": "failed",
            "error": "Verified APK was not confirmed published; previous download retained.",
            "last_attempt_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    apks = [apk for apk in apks if apk not in rejected]

    overrides = _overrides(app, source)
    settings = build_config.get_entry(app, source, apply_env=False)
    source_sig = ""
    if apks and not overrides:
        source_sig = planner.get_source_signature(
            source, settings["patches_channel"], settings["cli_channel"]
        ) + build_config.build_options_signature(settings)
        if planner._is_unreliable_source_sig(source_sig):
            source_sig = ""  # couldn't read the patch releases; leave it as it was

    changed = apply_failure_records(entries, failure_records, configured_keys)
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
        meta_path = Path("build_meta") / f"{apk.name}.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for field in ("artifact", "last_success_at", "last_attempt_at", "run_url",
                          "known_patches", "auto_patches"):
                if field in meta:
                    entry[field] = meta[field]
            entry["built_version"] = meta.get("artifact", {}).get("version_name") or entry["built_version"]
        entry["follows_store"] = _follows_store(apk.name)
        for k in ("failed_sig", "failed_attempts", "last_failed_at",
                  "pending_source_sig", "pending_store_version", "last_error"):
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
        return 1
    if published and apks and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("manifest_updated=true\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logging.warning(f"record_manual_build failed: {e}")
        sys.exit(1)
