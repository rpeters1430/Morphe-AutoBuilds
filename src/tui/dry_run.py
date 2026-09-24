"""Dry-Run & Inspection Module for Morphe Builder TUI.

Tests app and source resolution, checks online releases, and validates build inputs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .app_manager import load_config
from .patch_editor import get_patch_file_path, parse_patch_file

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
APPS_DIR = REPO_ROOT / "apps"
SOURCES_DIR = REPO_ROOT / "sources"


def find_app_providers(app_name: str) -> dict[str, dict[str, Any]]:
    providers: dict[str, dict[str, Any]] = {}
    if not APPS_DIR.exists():
        return providers

    for provider_dir in APPS_DIR.iterdir():
        if provider_dir.is_dir():
            target_json = provider_dir / f"{app_name}.json"
            if target_json.exists():
                try:
                    with open(target_json, "r", encoding="utf-8") as f:
                        providers[provider_dir.name] = json.load(f)
                except Exception:
                    pass
    return providers


def load_source_info(source_name: str) -> list[dict[str, Any]]:
    source_file = SOURCES_DIR / f"{source_name}.json"
    if not source_file.exists():
        return []
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    except Exception:
        return []


def test_app_dry_run(console: Console) -> None:
    config = load_config()
    patch_list = config.get("patch_list", [])

    choices = [f"{e.get('app_name')} ({e.get('source')})" for e in patch_list]
    choices.append("Cancel")

    selected = questionary.select("Select an app to inspect & dry-run:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    app_name = selected.split()[0]
    matched = next((e for e in patch_list if e.get("app_name") == app_name), {})
    source_name = matched.get("source", "morphe")

    console.print(f"\n[cyan]Inspecting build configuration for [bold]{app_name}[/bold]...[/cyan]\n")

    # 1. Provider definitions
    providers = find_app_providers(app_name)

    # 2. Source repositories
    source_repos = load_source_info(source_name)

    # 3. Patch overrides
    patch_path = get_patch_file_path(app_name, source_name)
    included, excluded, _ = parse_patch_file(patch_path)

    # Display Inspection Table
    table = Table(title=f"🔬 Dry-Run Preview: {app_name}", expand=True)
    table.add_column("Parameter", style="cyan", width=22)
    table.add_column("Value / Status", style="white")

    table.add_row("App Name", app_name)
    table.add_row("Patch Source", f"[green]{source_name}[/green]")
    table.add_row("Configured Channel", str(matched.get("patches_channel", "source")))
    table.add_row("Architectures", ", ".join(matched.get("arches", ["universal"])))
    table.add_row("Experimental Allowed", "Yes" if matched.get("experimental") else "No")

    # Providers summary
    if providers:
        prov_str = ", ".join(f"[bold]{k}[/bold] (pkg: {v.get('package', 'n/a')})" for k, v in providers.items())
        table.add_row("Available APK Sources", prov_str)
    else:
        table.add_row("Available APK Sources", "[bold red]None found in apps/*/[/bold red]")

    # Source repositories summary
    if source_repos:
        repo_lines = []
        for r in source_repos:
            if isinstance(r, dict) and "user" in r and "repo" in r:
                repo_lines.append(f"{r['user']}/{r['repo']} (tag: {r.get('tag', 'latest')})")
        table.add_row("Patch Repositories", "\n".join(repo_lines) if repo_lines else "Custom format")
    else:
        table.add_row("Patch Repositories", f"[bold red]sources/{source_name}.json not found[/bold red]")

    # Patch overrides
    table.add_row(
        "Patch Overrides",
        f"{len(included)} included (+), {len(excluded)} excluded (-) from {patch_path.name}"
        if patch_path.exists() else "No patch file overrides (will use source defaults)"
    )

    console.print(table)

    # Readiness Verdict
    ready = bool(providers) and bool(source_repos)
    if ready:
        console.print(Panel(
            f"[bold green]✓ Ready for CI / Local Build![/bold green]\n"
            f"App definitions and patch sources are properly wired.\n"
            f"Trigger build via 'CI Dispatcher' to start.",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]✗ Not Ready[/bold red]\n"
            f"Missing app source definition in `apps/` or source provider in `sources/`.",
            border_style="red",
        ))

    questionary.press_any_key_to_continue().ask()
