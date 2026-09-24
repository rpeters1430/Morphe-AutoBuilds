"""App Manager for Morphe Builder TUI.

Allows viewing, searching, adding, editing, and deleting apps in patch-config.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import questionary
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PATCH_CONFIG_PATH = REPO_ROOT / "patch-config.json"
APPS_DIR = REPO_ROOT / "apps"
SOURCES_DIR = REPO_ROOT / "sources"
VALID_ARCHES = ["arm64-v8a", "armeabi-v7a", "universal"]
CHANNELS = ["source", "stable", "prerelease", "dev"]


def load_config() -> dict[str, Any]:
    with open(PATCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    with open(PATCH_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_available_apps() -> list[str]:
    """Collect unique app names from all apps/ subdirectories."""
    apps = set()
    if APPS_DIR.exists():
        for path in APPS_DIR.rglob("*.json"):
            apps.add(path.stem)
    return sorted(apps)


def get_available_sources() -> list[str]:
    """Collect source names from sources/ directory."""
    sources = set()
    if SOURCES_DIR.exists():
        for path in SOURCES_DIR.glob("*.json"):
            sources.add(path.stem)
    return sorted(sources)


def display_apps_table(console: Console, search_query: str = "") -> None:
    config = load_config()
    patch_list = config.get("patch_list", [])

    table = Table(title="📱 Configured Applications in patch-config.json", expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("App Name", style="cyan", no_wrap=True)
    table.add_column("Source", style="green")
    table.add_column("Architectures", style="yellow")
    table.add_column("Channel", style="magenta")
    table.add_column("Experimental", style="blue")
    table.add_column("Status", justify="center")

    count = 0
    query = search_query.strip().lower()

    for idx, entry in enumerate(patch_list, start=1):
        app = entry.get("app_name", "")
        src = entry.get("source", "")
        if query and query not in app.lower() and query not in src.lower():
            continue

        count += 1
        arches = ", ".join(entry.get("arches", [])) or "default"
        channel = entry.get("patches_channel", "default")
        exp = "Yes" if entry.get("experimental") else "No"
        enabled = entry.get("enabled", True)
        status = "[bold green]ENABLED[/bold green]" if enabled else "[bold red]DISABLED[/bold red]"

        table.add_row(str(idx), app, src, arches, channel, exp, status)

    console.print(table)
    console.print(f"[dim]Showing {count} of {len(patch_list)} configured apps.[/dim]\n")


def add_app_wizard(console: Console) -> None:
    console.print("\n[bold cyan]➕ Add New Application[/bold cyan]\n")
    available_apps = get_available_apps()
    available_sources = get_available_sources()

    # Step 1: Select or enter app name
    app_choice = questionary.autocomplete(
        "Select or type the app name:",
        choices=available_apps,
        validate=lambda text: True if text.strip() else "App name cannot be empty.",
    ).ask()
    if not app_choice:
        return

    # Step 2: Select source
    source_choice = questionary.select(
        f"Select patch source for '{app_choice}':",
        choices=available_sources + ["[Custom Source Name]"],
        default="morphe" if "morphe" in available_sources else available_sources[0],
    ).ask()
    if not source_choice:
        return

    if source_choice == "[Custom Source Name]":
        source_choice = questionary.text("Enter custom source name:").ask()
        if not source_choice:
            return

    # Step 3: Architectures
    arches_choice = questionary.checkbox(
        "Select target architectures (spacebar to select, enter to confirm):",
        choices=[
            questionary.Choice("universal", checked=True),
            questionary.Choice("arm64-v8a", checked=False),
            questionary.Choice("armeabi-v7a", checked=False),
        ],
    ).ask()

    # Step 4: Channel
    channel_choice = questionary.select(
        "Select patches release channel:",
        choices=["source (default)", "stable", "prerelease", "dev"],
        default="source (default)",
    ).ask()
    channel = channel_choice.split()[0]

    # Step 5: Experimental
    exp_choice = questionary.confirm("Allow experimental app versions?", default=False).ask()

    new_entry: dict[str, Any] = {
        "app_name": app_choice.strip(),
        "source": source_choice.strip(),
    }
    if arches_choice:
        new_entry["arches"] = arches_choice
    if channel != "source":
        new_entry["patches_channel"] = channel
    if exp_choice:
        new_entry["experimental"] = True

    config = load_config()
    config.setdefault("patch_list", []).append(new_entry)
    save_config(config)

    console.print(f"\n[bold green]✓ Successfully added {app_choice} ({source_choice}) to patch-config.json![/bold green]\n")


def edit_app_wizard(console: Console) -> None:
    config = load_config()
    patch_list = config.get("patch_list", [])
    if not patch_list:
        console.print("[yellow]No apps configured to edit.[/yellow]")
        return

    choices = [
        f"{i+1}. {e.get('app_name')} ({e.get('source')}) {'[DISABLED]' if not e.get('enabled', True) else ''}"
        for i, e in enumerate(patch_list)
    ]
    choices.append("Cancel")

    selected = questionary.select("Select an app to edit:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    idx = int(selected.split(".")[0]) - 1
    entry = patch_list[idx]

    # Persistent loop for this app so user can edit multiple settings in sequence
    while True:
        app_name = entry.get("app_name", "")
        source = entry.get("source", "")
        enabled = entry.get("enabled", True)
        arches = ", ".join(entry.get("arches", [])) or "default (universal)"
        channel = entry.get("patches_channel", "source")
        experimental = entry.get("experimental", False)
        version = entry.get("version") or "latest (unpinned)"

        card_table = Table(title=f"⚙️ Editing Application: {app_name}", show_header=False, expand=True)
        card_table.add_column("Setting", style="cyan", width=22)
        card_table.add_column("Current Value", style="white")

        card_table.add_row("Status", "[bold green]ENABLED[/bold green]" if enabled else "[bold red]DISABLED[/bold red]")
        card_table.add_row("Patch Source", f"[yellow]{source}[/yellow]")
        card_table.add_row("Architectures", arches)
        card_table.add_row("Patches Channel", channel)
        card_table.add_row("Experimental", "Yes" if experimental else "No")
        card_table.add_row("Version Pin", version)

        console.print()
        console.print(card_table)
        console.print()

        action = questionary.select(
            f"Select a setting to modify for {app_name}:",
            choices=[
                f"Toggle Status (Currently: {'ENABLED' if enabled else 'DISABLED'})",
                f"Change Patch Source (Current: {source})",
                f"Change Architectures (Current: {arches})",
                f"Change Patches Channel (Current: {channel})",
                f"Toggle Experimental (Current: {'Yes' if experimental else 'No'})",
                f"Pin/Unpin Version (Current: {version})",
                "🧩 Manage Patches for this App",
                "💾 Save & Done Editing",
                "🗑️ Remove App from Config",
            ],
        ).ask()

        if not action or action == "💾 Save & Done Editing":
            save_config(config)
            console.print(f"\n[bold green]✓ Saved all changes for {app_name}![/bold green]\n")
            break

        if action.startswith("Toggle Status"):
            entry["enabled"] = not enabled
            save_config(config)
            console.print(f"[green]Set status to {'ENABLED' if entry['enabled'] else 'DISABLED'}[/green]")

        elif action.startswith("Change Patch Source"):
            sources = get_available_sources()
            new_source = questionary.select("Select new source:", choices=sources, default=source).ask()
            if new_source:
                entry["source"] = new_source
                save_config(config)
                console.print(f"[green]Changed source to {new_source}[/green]")

        elif action.startswith("Change Architectures"):
            current_arches = entry.get("arches", ["universal"])
            new_arches = questionary.checkbox(
                "Select target architectures:",
                choices=[
                    questionary.Choice("universal", checked="universal" in current_arches),
                    questionary.Choice("arm64-v8a", checked="arm64-v8a" in current_arches),
                    questionary.Choice("armeabi-v7a", checked="armeabi-v7a" in current_arches),
                ],
            ).ask()
            if new_arches is not None:
                entry["arches"] = new_arches
                save_config(config)
                console.print(f"[green]Updated architectures to {new_arches}[/green]")

        elif action.startswith("Change Patches Channel"):
            channel_choice = questionary.select(
                "Select patches channel:",
                choices=["source", "stable", "prerelease", "dev"],
                default=entry.get("patches_channel", "source"),
            ).ask()
            if channel_choice:
                entry["patches_channel"] = channel_choice
                save_config(config)
                console.print(f"[green]Updated patches_channel to {channel_choice}[/green]")

        elif action.startswith("Toggle Experimental"):
            entry["experimental"] = not experimental
            save_config(config)
            console.print(f"[green]Set experimental={entry['experimental']}[/green]")

        elif action.startswith("Pin/Unpin Version"):
            curr_ver = entry.get("version", "")
            new_ver = questionary.text(
                "Enter version string to pin (leave empty to unpin):",
                default=curr_ver,
            ).ask()
            if new_ver is not None:
                if new_ver.strip():
                    entry["version"] = new_ver.strip()
                    console.print(f"[green]Pinned version to {new_ver}[/green]")
                else:
                    entry.pop("version", None)
                    console.print("[green]Unpinned version (will use latest)[/green]")
                save_config(config)

        elif action.startswith("🧩 Manage Patches"):
            from .patch_editor import edit_app_patches
            edit_app_patches(console, app_name, source)

        elif action.startswith("🗑️ Remove App"):
            confirm = questionary.confirm(f"Are you sure you want to remove '{app_name}'?", default=False).ask()
            if confirm:
                patch_list.pop(idx)
                save_config(config)
                console.print(f"[red]Removed {app_name} from patch-config.json[/red]\n")
                break


def manage_apps_menu(console: Console) -> None:
    while True:
        action = questionary.select(
            "📱 App Manager - Choose an action:",
            choices=[
                "View All Configured Apps",
                "Search Apps",
                "Add New App",
                "Edit Configured App",
                "Back to Main Menu",
            ],
        ).ask()

        if not action or action == "Back to Main Menu":
            break

        if action == "View All Configured Apps":
            display_apps_table(console)
        elif action == "Search Apps":
            query = questionary.text("Enter search query (app or source):").ask()
            if query is not None:
                display_apps_table(console, search_query=query)
        elif action == "Add New App":
            add_app_wizard(console)
        elif action == "Edit Configured App":
            edit_app_wizard(console)
