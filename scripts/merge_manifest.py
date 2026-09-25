#!/usr/bin/env python3
"""Merge per-build records into the final manifest.json before uploading.

Inputs:
  - new_manifest.json      (planning-time manifest, has all entries with old apk
                            filenames as fallback for carry-overs)
  - build_records/*.json   (one record per built APK, written by record_build.py)

Output:
  - manifest.json          (final manifest to attach to the release)
"""
import datetime
import json
import sys
from pathlib import Path


def main() -> int:
    new_manifest_path = Path("new_manifest.json")
    if not new_manifest_path.exists():
        print("No new_manifest.json found; nothing to merge")
        return 0

    with new_manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    entries = manifest.setdefault("entries", {})

    rec_dir = Path("build_records")
    if rec_dir.exists():
        for rec_file in sorted(rec_dir.rglob("*.json")):
            try:
                with rec_file.open("r", encoding="utf-8") as f:
                    rec = json.load(f)
            except Exception as e:
                print(f"  skip bad record {rec_file}: {e}")
                continue
            key = rec.get("key")
            apk = rec.get("apk", "")
            # resolved_version is the version actually embedded in the built APK
            # filename (extracted by record_build.py). Propagate it as
            # 'built_version' so check_app_updates.py can detect on the next run
            # when a newer app version becomes available, even for apps whose
            # config 'version' is empty (meaning "latest at build time").
            resolved_version = (rec.get("resolved_version") or "").strip()
            if not key:
                continue
            entry = entries.get(key)
            if not entry:
                # Record exists but planning didn't list this combo; create it.
                entry = {
                    "app_name": rec.get("app_name", ""),
                    "source": rec.get("source", ""),
                    "arch": rec.get("arch", "universal"),
                    "config_version": "",
                    "source_sig": "",
                    "apk": "",
                    "built_version": "",
                }
                entries[key] = entry
            if apk:
                entry["apk"] = apk
            if resolved_version:
                entry["built_version"] = resolved_version
            # The build shipped a version its patches don't list (none listed,
            # or force): the planner watches the store for this entry.
            entry["follows_store"] = bool(rec.get("follows_store"))
            # Patches this build saw and the new ones it turned on; the next
            # build enables patches missing from known_patches.
            for fkey in ("known_patches", "auto_patches"):
                if fkey in rec:
                    entry[fkey] = rec[fkey]
            pending_store = entry.pop("pending_store_version", "")
            if pending_store:
                entry["store_version_seen"] = pending_store
            # Promote pending_source_sig -> source_sig now that the build
            # succeeded.  The planner deliberately keeps the OLD source_sig
            # for rebuild entries so that a failed build doesn't "consume"
            # the signature change.  Only a successful build (= this code
            # path) finalises the new signature.
            pending_sig = entry.get("pending_source_sig", "")
            if pending_sig:
                entry["source_sig"] = pending_sig
                del entry["pending_source_sig"]
            # A scheduled build replaced any manual build's APK.
            for fkey in ("failed_sig", "failed_attempts", "last_failed_at", "manual_build"):
                entry.pop(fkey, None)
            print(f"  merged {key} -> apk={apk!r} built_version={resolved_version!r}")
    # Entries still holding pending_source_sig were planned for a rebuild but
    # got no build record, i.e. the build failed. The OLD source_sig stays in
    # place so the next planner run still sees the change, and the failure is
    # counted per input signature so check_app_updates.py can stop retrying
    # the same failing inputs every day.
    today = datetime.date.today().isoformat()
    for key, entry in entries.items():
        # A failed build must not consume the store version it was built for.
        entry.pop("pending_store_version", None)
        pending_sig = entry.pop("pending_source_sig", None)
        if not pending_sig:
            continue
        if entry.get("failed_sig") == pending_sig:
            entry["failed_attempts"] = int(entry.get("failed_attempts") or 0) + 1
        else:
            entry["failed_sig"] = pending_sig
            entry["failed_attempts"] = 1
        entry["last_failed_at"] = today
        print(f"  failed {key} (attempt {entry['failed_attempts']} with these inputs)")

    with open("manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest.json with {len(entries)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
