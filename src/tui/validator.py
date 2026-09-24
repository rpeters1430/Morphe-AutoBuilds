"""Configuration & Health Validator for Morphe Builder.

Runs comprehensive checks across patch-config.json, apps/, sources/, and keystores.
"""
from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PATCH_CONFIG_PATH = REPO_ROOT / "patch-config.json"
APPS_DIR = REPO_ROOT / "apps"
SOURCES_DIR = REPO_ROOT / "sources"
PATCHES_DIR = REPO_ROOT / "patches"
KEYSTORE_PATH = REPO_ROOT / "keystore" / "public.jks"

VALID_ARCHES = {"arm64-v8a", "armeabi-v7a", "universal"}
VALID_CHANNELS = {"source", "stable", "prerelease", "dev"}


def run_validation(console: Console) -> bool:
    console.print("\n[bold cyan]🔍 Running Morphe Builder Health & Configuration Check...[/bold cyan]\n")

    errors: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []

    # 1. Check patch-config.json existence & JSON validity
    if not PATCH_CONFIG_PATH.exists():
        errors.append(f"Missing configuration file: {PATCH_CONFIG_PATH}")
        raw_config = {}
    else:
        try:
            with open(PATCH_CONFIG_PATH, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
            passed.append("patch-config.json is valid JSON")
        except Exception as e:
            errors.append(f"Invalid JSON in patch-config.json: {e}")
            raw_config = {}

    patch_list = raw_config.get("patch_list", [])
    if not isinstance(patch_list, list):
        errors.append("patch_list must be a list of objects")
        patch_list = []

    # 2. Check keystore
    if KEYSTORE_PATH.exists():
        passed.append(f"Signing keystore found at keystore/public.jks ({KEYSTORE_PATH.stat().st_size} bytes)")
    else:
        warnings.append("Signing keystore keystore/public.jks not found (needed for local APK signing)")

    # 3. Check sources
    known_sources = set()
    if SOURCES_DIR.exists():
        for s_file in SOURCES_DIR.glob("*.json"):
            known_sources.add(s_file.stem)
            try:
                with open(s_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                if not isinstance(s_data, (list, dict)):
                    errors.append(f"sources/{s_file.name} is neither a list nor an object")
            except Exception as e:
                errors.append(f"sources/{s_file.name} has JSON syntax error: {e}")
        passed.append(f"Verified {len(known_sources)} patch sources in sources/")
    else:
        errors.append("sources/ directory does not exist")

    # 4. Check available apps
    available_apps = set()
    if APPS_DIR.exists():
        for app_file in APPS_DIR.rglob("*.json"):
            available_apps.add(app_file.stem)
        passed.append(f"Discovered {len(available_apps)} app definitions in apps/")
    else:
        errors.append("apps/ directory does not exist")

    # 5. Check each entry in patch_list
    enabled_count = 0
    disabled_count = 0
    seen_combos = set()

    for idx, entry in enumerate(patch_list):
        where = f"patch_list[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} is not an object")
            continue

        app = entry.get("app_name")
        src = entry.get("source")
        if not app or not src:
            errors.append(f"{where}: 'app_name' and 'source' are required")
            continue

        combo = (app, src)
        if combo in seen_combos:
            warnings.append(f"Duplicate entry for app '{app}' with source '{src}'")
        seen_combos.add(combo)

        enabled = entry.get("enabled", True)
        if enabled:
            enabled_count += 1
        else:
            disabled_count += 1

        if src not in known_sources:
            errors.append(f"{app}: source '{src}' not found in sources/*.json")

        if app not in available_apps:
            warnings.append(f"{app}: no app definition found in apps/*/{app}.json")

        arches = entry.get("arches")
        if arches:
            if not isinstance(arches, list) or not all(a in VALID_ARCHES for a in arches):
                errors.append(f"{app}: invalid arches {arches}. Must be a subset of {list(VALID_ARCHES)}")

        channel = entry.get("patches_channel")
        if channel and channel not in VALID_CHANNELS and not channel.startswith("v"):
            warnings.append(f"{app}: non-standard patches_channel '{channel}'")

    passed.append(f"Validated {len(patch_list)} entries: {enabled_count} enabled, {disabled_count} disabled")

    # Display Report
    table = Table(title="📋 System & Configuration Health Report", expand=True)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Category", style="cyan", width=15)
    table.add_column("Detail", style="white")

    for p in passed:
        table.add_row("[bold green]PASS[/bold green]", "Configuration", p)

    for w in warnings:
        table.add_row("[bold yellow]WARN[/bold yellow]", "Warning", f"[yellow]{w}[/yellow]")

    for e in errors:
        table.add_row("[bold red]FAIL[/bold red]", "Error", f"[red]{e}[/red]")

    console.print(table)

    if errors:
        console.print(f"\n[bold red]❌ Health check failed with {len(errors)} error(s) and {len(warnings)} warning(s).[/bold red]\n")
        return False
    elif warnings:
        console.print(f"\n[bold yellow]⚠️ Health check passed with {len(warnings)} warning(s).[/bold yellow]\n")
        return True
    else:
        console.print("\n[bold green]✓ All configuration and sanity checks passed perfectly![/bold green]\n")
        return True
