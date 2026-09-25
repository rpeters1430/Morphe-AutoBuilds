import json
import logging
import re
import os
import shutil
from sys import exit
from pathlib import Path
from os import getenv
import subprocess
from src import (
    r2,
    utils,
    release,
    downloader,
    build_config,
)

def _should_retry_with_older_version(output: str | None) -> bool:
    """Detect common patterns that indicate the chosen app version is not
    actually compatible with the selected patches (fingerprint mismatch, etc.)."""
    if not output:
        return False
    t = output.lower()
    return (
        "failed to match the fingerprint" in t
        or "patch.patchexception" in t
        or ("fingerprint" in t and "failed" in t)
        or "patching aborted" in t
    )

_cli_help_cache: dict[str, str] = {}

# Manifest the planner wrote for this run; carries each entry's patch state.
PATCH_STATE_FILE = Path(getenv("PATCH_STATE_FILE") or "build-plan/new_manifest.json")

# Patch state of the last run_build() that listed its patches, for the sidecar.
last_patch_state: dict | None = None


def _app_package(app_name: str) -> str:
    for cfg in sorted(Path("apps").glob(f"*/{app_name}.json")):
        try:
            package = json.loads(cfg.read_text(encoding="utf-8")).get("package")
        except Exception:
            continue
        if package:
            return package
    return ""


def _previous_patch_state(app_name: str, source: str) -> tuple[set[str], set[str]]:
    """(known, auto-enabled) patch names recorded by earlier builds."""
    known: set[str] = set()
    auto: set[str] = set()
    try:
        entries = json.loads(PATCH_STATE_FILE.read_text(encoding="utf-8")).get("entries", {})
    except Exception:
        return known, auto
    for entry in entries.values():
        if entry.get("app_name") == app_name and entry.get("source") == source:
            known.update(entry.get("known_patches") or [])
            auto.update(entry.get("auto_patches") or [])
    return known, auto


def _new_patches_to_enable(app_name: str, source: str, settings: dict,
                           cli: Path, patches: Path) -> list[str]:
    """Patches to turn on with -e because they appeared after an earlier build.

    Patches on by default are applied anyway; this turns on the new ones
    that ship off by default, and keeps them on in later builds. Patches
    listed at the first build (the baseline) keep their default, and a "-"
    rule, exclude_patches or exclusive still wins.
    """
    global last_patch_state
    last_patch_state = None
    package = _app_package(app_name)
    listed = utils.list_app_patches(package, str(cli), str(patches)) if package else None
    if not listed:
        return []

    known, auto = _previous_patch_state(app_name, source)
    fresh = [n for n in listed if known and n not in known]
    for n in fresh:
        state = "on by default" if listed[n] else "off by default, enabling it"
        logging.info(f"🆕 New patch for {app_name}: {n} ({state})")

    _, exclude = build_config.patch_selection(settings)
    enable = set() if settings.get("exclusive") else {
        n for n in auto | {n for n in fresh if not listed[n]}
        if n in listed and n not in exclude
    }
    last_patch_state = {"known_patches": sorted(listed), "auto_patches": sorted(enable)}
    return sorted(enable)


def _cli_supports(cli: Path, flag: str) -> bool:
    """True if `<cli> patch --help` lists the flag. Older ReVanced CLIs lack
    some of the options Morphe CLI has, and fail on unknown flags."""
    key = str(cli)
    if key not in _cli_help_cache:
        try:
            proc = subprocess.run(
                ["java", "-jar", key, "patch", "--help"],
                capture_output=True, text=True, timeout=120,
            )
            _cli_help_cache[key] = (proc.stdout or "") + (proc.stderr or "")
        except Exception as e:
            logging.debug(f"Could not read CLI help for {cli}: {e}")
            _cli_help_cache[key] = ""
    return flag in _cli_help_cache[key]


def _optional_flags(cli: Path, settings: dict) -> list[str]:
    flags = []
    for key, flag in (("exclusive", "--exclusive"), ("continue_on_error", "--continue-on-error")):
        if not settings.get(key):
            continue
        if _cli_supports(cli, flag):
            flags.append(flag)
        else:
            logging.warning(f"⚠️  {cli.name} has no {flag}; ignoring '{key}'")
    return flags


def run_build(app_name: str, source: str, arch: str = "universal", settings: dict | None = None,
              tools: tuple[list[Path], str] | None = None) -> str:
    """Build APK for specific architecture. `tools` is download_required()'s
    result; pass it to reuse one CLI/patches download across arches."""
    settings = settings or build_config.get_entry(app_name, source)
    experimental = settings["experimental"]
    force = settings["force"]
    pinned_version = settings["version"] or None

    download_files, name = tools or downloader.download_required(
        source, settings["patches_channel"], settings["cli_channel"]
    )

    # Log downloaded files for debugging
    logging.info(f"📦 Downloaded {len(download_files)} files for {source}:")
    for file in download_files:
        logging.info(f"  - {file.name} ({file.stat().st_size} bytes)")

    # DETECT SOURCE TYPE BASED ON DOWNLOADED FILES
    is_morphe = False
    is_revanced = False

    # Check file contents to determine source type
    for file in download_files:
        if "morphe-cli" in file.name.lower():
            is_morphe = True
            break
        elif "revanced-cli" in file.name.lower():
            is_revanced = True
            break

    # If not detected by CLI name, check patch file extension
    if not is_morphe and not is_revanced:
        for file in download_files:
            if file.suffix == ".mpp":
                is_morphe = True
                break
            elif file.suffix in [".rvp", ".jar"] and "patches" in file.name.lower():
                is_revanced = True
                break

    # If still not detected, fallback to source name
    if not is_morphe and not is_revanced:
        is_morphe = "morphe" in source.lower() or "custom" in source.lower()
        is_revanced = not is_morphe  # Default to ReVanced if not Morphe

    logging.info(f"🔍 Detected: {'Morphe' if is_morphe else 'ReVanced'} source type")

    # FIND FILES BASED ON DETECTED TYPE
    if is_morphe:
        # Find Morphe files - prefer non-dev version
        cli = utils.find_file(download_files, contains="morphe-cli", suffix=".jar", exclude=["dev"])
        if not cli:
            # Fallback to any Morphe CLI
            cli = utils.find_file(download_files, contains="morphe", suffix=".jar")
        
        if not cli:
            cli = utils.find_file(download_files, suffix=".jar")
        patches = utils.find_file(download_files, contains="patches", suffix=".mpp")
        if not patches:
            # Fallback to any .mpp file
            patches = utils.find_file(download_files, suffix=".mpp")
    else:
        # Find ReVanced files
        cli = utils.find_file(download_files, contains="revanced-cli", suffix=".jar")
        patches = utils.find_file(download_files, contains="patches", suffix=".rvp")
        
        if not patches:
            # Try .jar extension for patches
            patches = utils.find_file(download_files, contains="patches", suffix=".jar")

    # Validate tools
    if not cli:
        logging.error(f"❌ CLI not found for source: {source}")
        logging.error(f"Available files: {[f.name for f in download_files]}")
        return None
    if not patches:
        logging.error(f"❌ Patches not found for source: {source}")
        logging.error(f"Available files: {[f.name for f in download_files]}")
        return None

    logging.info(f"✅ Using CLI: {cli.name}")
    logging.info(f"✅ Using patches: {patches.name}")

    download_methods = [
        downloader.download_apkmirror,
        downloader.download_aptoide,
        downloader.download_github,
        downloader.download_uptodown,
        downloader.download_apkpure,
        downloader.download_apkcombo,
    ]

    input_apk = None
    version = None
    candidates: list[str] = []
    used_method = None
    for method in download_methods:
        input_apk, version, candidates = method(
            app_name, str(cli), str(patches), arch,
            override_version=pinned_version, experimental=experimental, force=force,
        )
        if input_apk:
            used_method = method
            break

    if input_apk is None or not used_method or not version:
        logging.error(f"❌ Failed to download APK for {app_name}")
        logging.error("All download sources failed. Skipping this app.")
        return None

    # Try the downloaded version first, then (if available) older compatible
    # versions from the patch set. This prevents a single bad/overstated
    # compatibility entry from breaking the whole build.
    versions_to_try: list[str] = [version]
    if candidates and version in candidates:
        versions_to_try += [v for v in candidates if v != version]

    new_patches = _new_patches_to_enable(app_name, source, settings, cli, patches)
    if new_patches:
        settings = {**settings, "include_patches": [*settings["include_patches"], *new_patches]}
    patch_args = build_config.patch_cli_args(settings)
    force_args = ["--force"] if force else []
    extra_flags = _optional_flags(cli, settings)
    if patch_args or extra_flags:
        logging.info(f"🧩 Patch selection: {' '.join([*extra_flags, *patch_args])}")

    for attempt_idx, ver in enumerate(versions_to_try):
        if attempt_idx > 0:
            logging.warning(
                f"Retrying {app_name}/{source}/{arch} with older version {ver} due to patch failure..."
            )
            # Cleanup any previous attempt artifacts.
            try:
                input_apk.unlink(missing_ok=True)
            except Exception:
                pass

            input_apk, version, _ = used_method(
                app_name, str(cli), str(patches), arch,
                override_version=ver, experimental=experimental, force=force,
            )
            if input_apk is None:
                continue
            version = ver

        # --- Normalize/merge input into .apk when needed ---
        if input_apk.suffix != ".apk":
            # Check if it is a split bundle (contains multiple .apk files or is .apkm/.xapk/.apks)
            is_bundle = False
            try:
                import zipfile
                if zipfile.is_zipfile(input_apk):
                    with zipfile.ZipFile(input_apk, "r") as z:
                        namelist = z.namelist()
                        has_split_apks = any(n.endswith(".apk") for n in namelist)
                        is_bundle = has_split_apks or input_apk.suffix.lower() in [".apkm", ".xapk", ".apks", ".zip"]
            except Exception as e:
                logging.debug(f"Zip inspection failed for {input_apk}: {e}")

            target_apk = input_apk.with_name(f"{input_apk.stem}.apk" if not input_apk.name.endswith(".apk") else input_apk.name)

            if is_bundle:
                logging.info(f"Input file is a bundle ({input_apk.name}), using APKEditor to merge")
                apk_editor = downloader.download_apkeditor()
                merged_apk = input_apk.with_suffix(".apk")
                merged_apk.unlink(missing_ok=True)

                try:
                    utils.run_process([
                        "java", "-jar", str(apk_editor), "m",
                        "-f",
                        "-i", str(input_apk),
                        "-o", str(merged_apk)
                    ], silent=True, check=True)
                    input_apk.unlink(missing_ok=True)
                    input_apk = merged_apk
                except Exception as e:
                    logging.warning(f"APKEditor merge failed ({e}); checking if file can be used as standalone APK")
                    if input_apk.exists():
                        target_apk.unlink(missing_ok=True)
                        os.replace(input_apk, target_apk)
                        input_apk = target_apk
            else:
                logging.info(f"Normalizing standalone APK filename to {target_apk.name}")
                if input_apk != target_apk:
                    target_apk.unlink(missing_ok=True)
                    os.replace(input_apk, target_apk)
                    input_apk = target_apk

            if not input_apk.exists():
                logging.error("Processed APK file not found")
                raise RuntimeError("Processed APK file not found")

            # Clean up filename: remove build number like (1575420) and -1575420.
            # Only strip 6+ digit build-number tokens so legitimate short version
            # segments (e.g. "app-2_0") are not mangled.
            clean_name = re.sub(r'\(\d+\)', '', input_apk.name)  # Remove (1575420)
            clean_name = re.sub(r'-\d{6,}_', '_', clean_name)  # Remove -1575420_ -> _
            if clean_name != input_apk.name:
                clean_apk = input_apk.with_name(clean_name)
                clean_apk.unlink(missing_ok=True)
                os.replace(input_apk, clean_apk)
                input_apk = clean_apk

            logging.info(f"Normalized APK file: {input_apk}")

        # --- ARCHITECTURE-SPECIFIC PROCESSING ---
        if arch != "universal":
            logging.info(f"Processing APK for {arch} architecture...")
            if arch == "arm64-v8a":
                utils.strip_zip_entries(input_apk, ["lib/x86/*", "lib/x86_64/*", "lib/armeabi-v7a/*"])
            elif arch == "armeabi-v7a":
                utils.strip_zip_entries(input_apk, ["lib/x86/*", "lib/x86_64/*", "lib/arm64-v8a/*"])
        else:
            utils.strip_zip_entries(input_apk, ["lib/x86/*", "lib/x86_64/*"])

        # Validate APK integrity
        logging.info("Checking APK integrity...")
        if not utils.check_apk_integrity(input_apk):
            logging.warning("APK integrity check failed; attempting repair with zip -FF if available")
            if shutil.which("zip"):
                fixed_apk = Path(f"{app_name}-fixed-v{version}.apk")
                subprocess.run([
                    "zip", "-FF", str(input_apk), "--out", str(fixed_apk)
                ], check=False, capture_output=True)

                # zip -FF can "succeed" while dropping almost every entry
                # (seen: 3229 entries -> 3, no AndroidManifest.xml), so only
                # swap in the repaired file when it is really an APK.
                if utils.check_apk_integrity(fixed_apk) and utils.has_manifest(fixed_apk):
                    input_apk.unlink(missing_ok=True)
                    fixed_apk.rename(input_apk)
                    logging.info("APK fixed successfully")
                else:
                    fixed_apk.unlink(missing_ok=True)
                    logging.warning("Repair produced no usable APK; keeping original APK")
            else:
                logging.warning("zip command not available for repair; proceeding with current APK")
        else:
            logging.info("APK integrity OK; no repair needed")

        # Include architecture in output filename
        output_apk = Path(f"{app_name}-{arch}-patch-v{version}.apk")

        try:
            # USE DIFFERENT COMMANDS BASED ON SOURCE TYPE
            if is_morphe:
                logging.info("🔧 Using Morphe patching system...")
                morphe_cmd = [
                    "java", "-jar", str(cli),
                    "patch", "--patches", str(patches),
                    "--out", str(output_apk), str(input_apk),
                    *patch_args, *force_args, *extra_flags
                ]
                utils.run_process(morphe_cmd, capture=True, stream=True)
            else:
                logging.info("🔧 Using ReVanced patching system...")
                cli_name = Path(cli).name.lower()
                is_revanced_v6_or_newer = (
                    'revanced-cli-6' in cli_name or 'revanced-cli-7' in cli_name or 'revanced-cli-8' in cli_name
                )

                if is_revanced_v6_or_newer:
                    utils.run_process([
                        "java", "-jar", str(cli),
                        "patch", "-p", str(patches), "-b",
                        "--out", str(output_apk), str(input_apk),
                        *patch_args, *force_args, *extra_flags
                    ], capture=True, stream=True)
                else:
                    utils.run_process([
                        "java", "-jar", str(cli),
                        "patch", "--patches", str(patches),
                        "--out", str(output_apk), str(input_apk),
                        *patch_args, *force_args, *extra_flags
                    ], capture=True, stream=True)

        except subprocess.CalledProcessError as e:
            # Remove temp input apk; we'll re-download if retrying.
            input_apk.unlink(missing_ok=True)
            output_apk.unlink(missing_ok=True)

            if attempt_idx < len(versions_to_try) - 1 and _should_retry_with_older_version(getattr(e, "output", None)):
                continue
            raise

        # Patch succeeded -> cleanup input and sign.
        input_apk.unlink(missing_ok=True)

        signed_apk = Path(f"{app_name}-{arch}-{name}-v{version}.apk")

        apksigner = utils.find_apksigner()
        if not apksigner:
            raise RuntimeError("apksigner not found")

        try:
            utils.run_process([
                str(apksigner), "sign", "--verbose",
                "--ks", "keystore/public.jks",
                "--ks-pass", "pass:public",
                "--key-pass", "pass:public",
                "--ks-key-alias", "public",
                "--in", str(output_apk), "--out", str(signed_apk)
            ], capture=True, stream=True)
        except Exception as e:
            logging.warning(f"Standard signing failed: {e}")
            logging.info("Trying alternative signing method...")

            utils.run_process([
                str(apksigner), "sign", "--verbose",
                "--min-sdk-version", "21",
                "--ks", "keystore/public.jks",
                "--ks-pass", "pass:public",
                "--key-pass", "pass:public",
                "--ks-key-alias", "public",
                "--in", str(output_apk), "--out", str(signed_apk)
            ], capture=True, stream=True)

        output_apk.unlink(missing_ok=True)
        print(f"✅ APK built: {signed_apk.name}")
        return str(signed_apk)

    # If we got here, every candidate version failed.
    return None

def _write_build_meta(apk_path: str, follows_store: bool) -> None:
    """Sidecar for scripts/record_build.py: facts about the build that the APK
    filename doesn't carry."""
    meta_dir = Path("build_meta")
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / f"{Path(apk_path).name}.json").write_text(
        json.dumps({"follows_store": follows_store, **(last_patch_state or {})}),
        encoding="utf-8")


def main():
    app_name = getenv("APP_NAME")
    source = getenv("SOURCE")

    if not app_name or not source:
        logging.error("APP_NAME and SOURCE environment variables must be set")
        exit(1)

    settings = build_config.get_entry(app_name, source)
    logging.info(
        f"⚙️  {app_name}/{source}: patches={settings['patches_channel']} "
        f"cli={settings['cli_channel']} experimental={settings['experimental']} "
        f"force={settings['force']} version={settings['version'] or 'auto'} "
        f"exclusive={settings['exclusive']} continue_on_error={settings['continue_on_error']}"
    )

    # An explicit ARCH (manual runs) wins over the configured arches.
    env_arch = (getenv("ARCH") or "").strip()
    arches = [env_arch] if env_arch else settings["arches"]

    # force patches the store's newest version whatever the patches list.
    force_follows = bool(settings["force"]) and not settings["version"]
    # Download the CLI and patches once for every arch: saves the repeat
    # downloads, and all arches are patched with the same release even if a
    # new one is published mid-build. (The app APK is still fetched per arch:
    # stores can serve arch-specific variants.)
    try:
        tools = downloader.download_required(
            source, settings["patches_channel"], settings["cli_channel"]
        )
    except Exception as e:
        logging.error(f"❌ Could not download the patch tools for {source}: {e}")
        exit(1)

    built_apks = []
    failed_arches = []
    for arch in arches:
        logging.info(f"🔨 Building {app_name} for {arch} architecture...")
        # One arch failing (e.g. a patch error) must not throw away the arches
        # that already built.
        try:
            apk_path = run_build(app_name, source, arch, settings, tools)
        except Exception as e:
            logging.error(f"❌ {app_name}/{source}/{arch} failed: {e}")
            apk_path = None
        if apk_path:
            built_apks.append(apk_path)
            _write_build_meta(apk_path, follows_store=force_follows or downloader.last_download_from_store)
            print(f"✅ Built {arch} version: {Path(apk_path).name}")
        else:
            failed_arches.append(arch)

    print(f"\n🎯 Built {len(built_apks)} APK(s) for {app_name}:")
    for apk in built_apks:
        print(f"  📱 {Path(apk).name}")

    if not built_apks:
        logging.error(f"❌ No APKs were built for {app_name}/{source}")
        exit(1)

    if failed_arches:
        # Partial success keeps the job green so the built APKs still ship;
        # flag the missing arches where they'll be seen. They are retried on
        # the next run because they get no build record.
        failed = ", ".join(failed_arches)
        print(f"::warning title={app_name} partially built::"
              f"{app_name}/{source} failed for {failed}; the previous APK is kept for those")
        summary = getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"### ⚠️ {app_name} ({source}) partially built\n\n"
                        f"Failed architectures: {failed}. The previous APK is kept "
                        f"for those and they are retried on the next run.\n")

if __name__ == "__main__":
    main()
