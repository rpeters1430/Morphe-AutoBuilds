import argparse
import json
import logging
import re
import subprocess
from pathlib import Path
from sys import exit

from src import (
    downloader,
    release,
    r2,
    utils,
)


APP_TITLE = "Morphe AutoBuilds"


def normalize_name(value: str) -> str:
    return value.strip().lower()


def print_banner() -> None:
    print()
    print("=" * 64)
    print(f"{APP_TITLE:^64}")
    print("Interactive APK Builder".center(64))
    print("=" * 64)


def print_section(title: str, detail: str | None = None) -> None:
    print()
    print(f"== {title} ==")
    if detail:
        print(detail)


def load_patch_config() -> list[dict]:
    config_path = Path("patch-config.json")
    if not config_path.exists():
        return []

    with config_path.open() as f:
        data = json.load(f)

    return data.get("patch_list", [])


def load_arch_config() -> list[dict]:
    config_path = Path("arch-config.json")
    if not config_path.exists():
        return []

    with config_path.open() as f:
        return json.load(f)


def get_available_apps() -> list[str]:
    app_names = set()
    apps_root = Path("apps")
    if not apps_root.exists():
        return []

    for config_path in apps_root.glob("*/*.json"):
        app_names.add(config_path.stem)

    for item in load_patch_config():
        app_name = item.get("app_name")
        if app_name:
            app_names.add(normalize_name(app_name))

    return sorted(app_names)


def get_available_sources() -> list[str]:
    sources_root = Path("sources")
    if not sources_root.exists():
        return []

    return sorted(path.stem for path in sources_root.glob("*.json"))


def get_source_display_label(source: str) -> str:
    description = downloader.describe_source(source)
    if description and description != source:
        return f"{source} ({description})"
    return source


def get_recommended_source(app_name: str) -> str | None:
    normalized_app = normalize_name(app_name)
    for item in load_patch_config():
        if normalize_name(item.get("app_name", "")) == normalized_app:
            source = item.get("source")
            if source:
                return normalize_name(source)
    return None


def get_default_arches(app_name: str, source: str) -> list[str]:
    normalized_app = normalize_name(app_name)
    normalized_source = normalize_name(source)
    for item in load_arch_config():
        if (
            normalize_name(item.get("app_name", "")) == normalized_app
            and normalize_name(item.get("source", "")) == normalized_source
        ):
            return item.get("arches", ["universal"])
    return ["universal"]


def print_choices(
    title: str,
    choices: list[str],
    default: str | None = None,
    recommended: str | None = None,
) -> None:
    print_section(title, f"{len(choices)} option(s) available")
    for index, choice in enumerate(choices, start=1):
        suffixes = []
        if recommended and choice == recommended:
            suffixes.append("recommended by daily workflow")
        if default and choice == default:
            suffixes.append("default")
        suffix = f" [{' | '.join(suffixes)}]" if suffixes else ""
        label = get_source_display_label(choice) if title == "Sources" else choice
        print(f"  {index}. {label}{suffix}")


def prompt_choice(
    title: str,
    choices: list[str],
    default: str | None = None,
    recommended: str | None = None,
) -> str:
    if not choices:
        raise ValueError(f"No choices available for {title}")

    while True:
        print_choices(title, choices, default, recommended)
        answer = input("Choose a number or name: ").strip()

        if not answer and default:
            return default

        if answer.isdigit():
            index = int(answer) - 1
            if 0 <= index < len(choices):
                return choices[index]

        for choice in choices:
            if normalize_name(choice) == normalize_name(answer):
                return choice

        print("Invalid selection. Try again.")


def prompt_arches(default_arches: list[str]) -> list[str]:
    arch_options = ["universal", "arm64-v8a", "armeabi-v7a"]
    default_text = ", ".join(default_arches)
    print_section("Architectures")
    print("  Available: universal, arm64-v8a, armeabi-v7a")
    print(f"  Default: {default_text}")
    answer = input(
        "Enter comma-separated architectures, 'all', or press Enter for default: "
    ).strip()

    if not answer:
        return default_arches

    if normalize_name(answer) == "all":
        return arch_options

    selected_arches = []
    for part in answer.split(","):
        arch = part.strip()
        if arch not in arch_options:
            raise ValueError(f"Unknown architecture: {arch}")
        if arch not in selected_arches:
            selected_arches.append(arch)

    return selected_arches


def run_build(app_name: str, source: str, arch: str = "universal") -> str | None:
    """Build APK for specific architecture."""
    download_files, name = downloader.download_required(source)

    logging.info(f"📦 Downloaded {len(download_files)} files for {source}:")
    for file in download_files:
        logging.info(f"  - {file.name} ({file.stat().st_size} bytes)")

    is_morphe = False
    is_revanced = False

    for file in download_files:
        if "morphe-cli" in file.name.lower():
            is_morphe = True
            break
        if "revanced-cli" in file.name.lower():
            is_revanced = True
            break

    if not is_morphe and not is_revanced:
        for file in download_files:
            if file.suffix == ".mpp":
                is_morphe = True
                break
            if file.suffix in [".rvp", ".jar"] and "patches" in file.name.lower():
                is_revanced = True
                break

    if not is_morphe and not is_revanced:
        is_morphe = "morphe" in source.lower() or "custom" in source.lower()
        is_revanced = not is_morphe

    logging.info(f"🔍 Detected: {'Morphe' if is_morphe else 'ReVanced'} source type")

    if is_morphe:
        cli = utils.find_file(download_files, contains="morphe-cli", suffix=".jar", exclude=["dev"])
        if not cli:
            cli = utils.find_file(download_files, contains="morphe", suffix=".jar")

        patches = utils.find_file(download_files, contains="patches", suffix=".mpp")
        if not patches:
            patches = utils.find_file(download_files, suffix=".mpp")
    else:
        cli = utils.find_file(download_files, contains="revanced-cli", suffix=".jar")
        patches = utils.find_file(download_files, contains="patches", suffix=".rvp")
        if not patches:
            patches = utils.find_file(download_files, contains="patches", suffix=".jar")

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
        downloader.download_apkpure,
        downloader.download_uptodown,
        downloader.download_aptoide,
    ]

    input_apk = None
    version = None
    for method in download_methods:
        input_apk, version = method(app_name, str(cli), str(patches))
        if input_apk:
            break

    if input_apk is None:
        logging.error(f"❌ Failed to download APK for {app_name}")
        logging.error("All download sources failed. Skipping this app.")
        return None

    if input_apk.suffix != ".apk":
        logging.warning("Input file is not .apk, using APKEditor to merge")
        apk_editor = downloader.download_apkeditor()

        merged_apk = input_apk.with_suffix(".apk")
        utils.run_process(
            ["java", "-jar", apk_editor, "m", "-i", str(input_apk), "-o", str(merged_apk)],
            silent=True,
        )

        input_apk.unlink(missing_ok=True)

        if not merged_apk.exists():
            logging.error("Merged APK file not found")
            exit(1)

        clean_name = re.sub(r"\(\d+\)", "", merged_apk.name)
        clean_name = re.sub(r"-\d+_", "_", clean_name)
        if clean_name != merged_apk.name:
            clean_apk = merged_apk.with_name(clean_name)
            merged_apk.rename(clean_apk)
            merged_apk = clean_apk

        input_apk = merged_apk
        logging.info(f"Merged APK file generated: {input_apk}")

    if arch != "universal":
        logging.info(f"Processing APK for {arch} architecture...")

        if arch == "arm64-v8a":
            utils.run_process(
                ["zip", "--delete", str(input_apk), "lib/x86/*", "lib/x86_64/*", "lib/armeabi-v7a/*"],
                silent=True,
                check=False,
            )
        elif arch == "armeabi-v7a":
            utils.run_process(
                ["zip", "--delete", str(input_apk), "lib/x86/*", "lib/x86_64/*", "lib/arm64-v8a/*"],
                silent=True,
                check=False,
            )
    else:
        utils.run_process(
            ["zip", "--delete", str(input_apk), "lib/x86/*", "lib/x86_64/*"],
            silent=True,
            check=False,
        )

    exclude_patches = []
    include_patches = []

    patches_path = Path("patches") / f"{app_name}-{source}.txt"
    if patches_path.exists():
        with patches_path.open("r") as patches_file:
            for line in patches_file:
                line = line.strip()
                if line.startswith("-"):
                    exclude_patches.extend(["-d", line[1:].strip()])
                elif line.startswith("+"):
                    include_patches.extend(["-e", line[1:].strip()])

    logging.info("Checking APK for corruption...")
    try:
        fixed_apk = Path(f"{app_name}-fixed-v{version}.apk")
        subprocess.run(
            ["zip", "-FF", str(input_apk), "--out", str(fixed_apk)],
            check=False,
            capture_output=True,
        )

        if fixed_apk.exists() and fixed_apk.stat().st_size > 0:
            input_apk.unlink(missing_ok=True)
            fixed_apk.rename(input_apk)
            logging.info("APK fixed successfully")
    except Exception as e:
        logging.warning(f"Could not fix APK: {e}")

    output_apk = Path(f"{app_name}-{arch}-patch-v{version}.apk")

    if is_morphe:
        logging.info("🔧 Using Morphe patching system...")
        try:
            utils.run_process(
                [
                    "java",
                    "-jar",
                    str(cli),
                    "patch",
                    "--patches",
                    str(patches),
                    "--out",
                    str(output_apk),
                    str(input_apk),
                    *exclude_patches,
                    *include_patches,
                ],
                stream=True,
            )
        except subprocess.CalledProcessError:
            logging.info("Trying alternative Morphe command format...")
            utils.run_process(
                [
                    "java",
                    "-jar",
                    str(cli),
                    "--patches",
                    str(patches),
                    "--input",
                    str(input_apk),
                    "--output",
                    str(output_apk),
                ],
                stream=True,
            )
    else:
        logging.info("🔧 Using ReVanced patching system...")
        cli_name = Path(cli).name.lower()
        is_revanced_v6_or_newer = any(
            f"revanced-cli-{major}" in cli_name for major in ("6", "7", "8")
        )

        if is_revanced_v6_or_newer:
            utils.run_process(
                [
                    "java",
                    "-jar",
                    str(cli),
                    "patch",
                    "-p",
                    str(patches),
                    "-b",
                    "--out",
                    str(output_apk),
                    str(input_apk),
                    *exclude_patches,
                    *include_patches,
                ],
                stream=True,
            )
        else:
            utils.run_process(
                [
                    "java",
                    "-jar",
                    str(cli),
                    "patch",
                    "--patches",
                    str(patches),
                    "--out",
                    str(output_apk),
                    str(input_apk),
                    *exclude_patches,
                    *include_patches,
                ],
                stream=True,
            )

    input_apk.unlink(missing_ok=True)

    signed_apk = Path(f"{app_name}-{arch}-{name}-v{version}.apk")
    apksigner = utils.find_apksigner()
    if not apksigner:
        exit(1)

    try:
        utils.run_process(
            [
                str(apksigner),
                "sign",
                "--verbose",
                "--ks",
                "keystore/public.jks",
                "--ks-pass",
                "pass:public",
                "--key-pass",
                "pass:public",
                "--ks-key-alias",
                "public",
                "--in",
                str(output_apk),
                "--out",
                str(signed_apk),
            ],
            stream=True,
        )
    except Exception as e:
        logging.warning(f"Standard signing failed: {e}")
        logging.info("Trying alternative signing method...")
        utils.run_process(
            [
                str(apksigner),
                "sign",
                "--verbose",
                "--min-sdk-version",
                "21",
                "--ks",
                "keystore/public.jks",
                "--ks-pass",
                "pass:public",
                "--key-pass",
                "pass:public",
                "--ks-key-alias",
                "public",
                "--in",
                str(output_apk),
                "--out",
                str(signed_apk),
            ],
            stream=True,
        )

    output_apk.unlink(missing_ok=True)
    print(f"✅ APK built: {signed_apk.name}")
    return str(signed_apk)


def build_selected(app_name: str, source: str, arches: list[str]) -> list[str]:
    built_apks = []
    for arch in arches:
        logging.info(f"🔨 Building {app_name} for {arch} architecture...")
        apk_path = run_build(app_name, source, arch)
        if apk_path:
            built_apks.append(apk_path)
            print(f"✅ Built {arch} version: {Path(apk_path).name}")
    return built_apks


def interactive_mode() -> int:
    print_banner()
    apps = get_available_apps()
    sources = get_available_sources()

    app_name = prompt_choice("Apps", apps)
    recommended_source = get_recommended_source(app_name)
    if recommended_source:
        print()
        print(
            f"Daily workflow recommendation: {app_name} -> {get_source_display_label(recommended_source)}"
        )
    source = prompt_choice("Sources", sources, recommended_source, recommended_source)
    default_arches = get_default_arches(app_name, source)

    try:
        arches = prompt_arches(default_arches)
    except ValueError as exc:
        logging.error(str(exc))
        return 1

    print_section("Build Plan")
    print(f"  App: {app_name}")
    print(f"  Source: {get_source_display_label(source)}")
    print(f"  Architectures: {', '.join(arches)}")
    confirm = input("Proceed? [Y/n]: ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("Cancelled.")
        return 0

    built_apks = build_selected(app_name, source, arches)
    print_section("Build Result")
    print(f"Built {len(built_apks)} APK(s) for {app_name}:")
    for apk in built_apks:
        print(f"  📱 {Path(apk).name}")
    return 0 if built_apks else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build patched APKs for a selected app/source.")
    parser.add_argument("app_name", nargs="?", help="App to build")
    parser.add_argument("--source", help="Patch source to use")
    parser.add_argument(
        "--arch",
        action="append",
        choices=["universal", "arm64-v8a", "armeabi-v7a"],
        help="Architecture to build. Repeat to build multiple arches.",
    )
    parser.add_argument("--list-apps", action="store_true", help="List discovered apps and exit")
    parser.add_argument("--list-sources", action="store_true", help="List discovered sources and exit")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive selection mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_apps:
        for app_name in get_available_apps():
            print(app_name)
        return

    if args.list_sources:
        for source in get_available_sources():
            print(source)
        return

    if args.interactive or not args.app_name:
        exit(interactive_mode())

    app_name = normalize_name(args.app_name)
    source = normalize_name(args.source) if args.source else get_recommended_source(app_name)
    if not source:
        logging.error(f"No source provided and no recommended source found for app: {app_name}")
        exit(1)

    arches = args.arch or get_default_arches(app_name, source)
    built_apks = build_selected(app_name, source, arches)

    print(f"\n🎯 Built {len(built_apks)} APK(s) for {app_name}:")
    for apk in built_apks:
        print(f"  📱 {Path(apk).name}")

    if not built_apks:
        exit(1)


if __name__ == "__main__":
    main()
