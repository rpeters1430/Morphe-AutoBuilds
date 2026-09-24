"""Patch Editor for Morphe Builder TUI.

Allows interactive viewing, adding, and toggling of patch rules in patches/<app>-<source>.txt,
preloaded with all upstream patches and defaults for the selected application.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .app_manager import load_config
from .patch_resolver import get_available_patches_for_app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PATCHES_DIR = REPO_ROOT / "patches"


def get_patch_file_path(app_name: str, source: str) -> Path:
    candidates = [
        PATCHES_DIR / f"{app_name}-{source}.txt",
        PATCHES_DIR / f"{app_name}.txt",
    ]
    for c in candidates:
        if c.exists():
            return c
    return PATCHES_DIR / f"{app_name}-{source}.txt"


def parse_patch_file(path: Path) -> tuple[list[str], list[str], list[str]]:
    """Returns (included_patches, excluded_patches, other_lines)."""
    if not path.exists():
        return [], [], []

    included = []
    excluded = []
    others = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                others.append(line)
            elif clean.startswith("+"):
                included.append(clean[1:].strip())
            elif clean.startswith("-"):
                excluded.append(clean[1:].strip())
            else:
                others.append(line)

    return included, excluded, others


def write_patch_file(path: Path, included: list[str], excluded: list[str], others: list[str] | None = None) -> None:
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    if others:
        for o in others:
            if o.strip():
                lines.append(o.strip())
        if lines:
            lines.append("")

    if included:
        lines.append("# Force Included Patches")
        for p in sorted(set(included)):
            lines.append(f"+ {p}")
        lines.append("")

    if excluded:
        lines.append("# Excluded Patches")
        for p in sorted(set(excluded)):
            lines.append(f"- {p}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


def display_patch_summary(
    console: Console,
    app_name: str,
    source: str,
    path: Path,
    included: list[str],
    excluded: list[str],
    available_patches: list[dict],
) -> None:
    table = Table(title=f"🧩 Patch Configuration for {app_name} ({source})", expand=True)
    table.add_column("Type", style="bold", width=16)
    table.add_column("Patch Name", style="white")
    table.add_column("Source Default", style="dim", width=18)

    avail_map = {p["name"].lower(): p for p in available_patches}

    if not included and not excluded:
        def_on = sum(1 for p in available_patches if p.get("default", True))
        def_off = len(available_patches) - def_on
        table.add_row(
            "[dim]Source Defaults[/dim]",
            f"[dim]No custom overrides defined in {path.name}. Using default profile ({def_on} enabled, {def_off} disabled).[/dim]",
            "[green]All Recommended ON[/green]" if def_on else "None",
        )
    else:
        for inc in included:
            info = avail_map.get(inc.lower(), {})
            d_val = "Default: ON" if info.get("default", True) else "Default: OFF"
            table.add_row("[green]+ FORCE INCLUDE[/green]", inc, f"[dim]{d_val}[/dim]")
        for exc in excluded:
            info = avail_map.get(exc.lower(), {})
            d_val = "Default: ON" if info.get("default", True) else "Default: OFF"
            table.add_row("[red]- FORCE EXCLUDE[/red]", exc, f"[dim]{d_val}[/dim]")

    console.print(table)
    console.print(f"[dim]Override file: {path} • Total available patches in {source}: {len(available_patches)}[/dim]\n")


def browse_and_toggle_patches(
    console: Console,
    available_patches: list[dict],
    included: list[str],
    excluded: list[str],
) -> tuple[list[str], list[str]]:
    """Interactive checklist with all known patches for this app."""
    if not available_patches:
        console.print("[yellow]No upstream patch list found for this app and source.[/yellow]")
        return included, excluded

    # Determine current effective state for each patch
    # A patch is enabled if:
    # (patch is in included) OR (patch default is True and patch not in excluded)
    inc_set = {p.lower() for p in included}
    exc_set = {p.lower() for p in excluded}

    choices = []
    for p in available_patches:
        name = p["name"]
        default_on = p.get("default", True)
        name_lower = name.lower()

        # Is it currently enabled?
        is_checked = False
        if name_lower in inc_set:
            is_checked = True
        elif name_lower in exc_set:
            is_checked = False
        else:
            is_checked = default_on

        tag = "(Recommended)" if default_on else "(Optional)"
        choices.append(questionary.Choice(
            title=f"{name} {tag}",
            value=name,
            checked=is_checked,
        ))

    selected = questionary.checkbox(
        "Toggle patches (Space to toggle, Enter to apply selection):",
        choices=choices,
    ).ask()

    if selected is None:
        return included, excluded

    selected_set = {s.lower() for s in selected}
    new_included = []
    new_excluded = []

    for p in available_patches:
        name = p["name"]
        name_lower = name.lower()
        default_on = p.get("default", True)

        if name_lower in selected_set:
            # User wants it ON
            if not default_on:
                # Needed an explicit include override
                new_included.append(name)
        else:
            # User wants it OFF
            if default_on:
                # Needed an explicit exclude override
                new_excluded.append(name)

    # Preserve any custom patches not in available_patches
    avail_names_lower = {p["name"].lower() for p in available_patches}
    for inc in included:
        if inc.lower() not in avail_names_lower and inc not in new_included:
            new_included.append(inc)
    for exc in excluded:
        if exc.lower() not in avail_names_lower and exc not in new_excluded:
            new_excluded.append(exc)

    console.print(f"[green]Updated overrides: {len(new_included)} force included, {len(new_excluded)} force excluded.[/green]")
    return new_included, new_excluded


def edit_app_patches(console: Console, app_name: str, source: str) -> None:
    patch_file = get_patch_file_path(app_name, source)
    included, excluded, others = parse_patch_file(patch_file)

    console.print(f"[cyan]Loading patch profile for {app_name} ({source})...[/cyan]")
    available_patches = get_available_patches_for_app(app_name, source)

    while True:
        display_patch_summary(console, app_name, source, patch_file, included, excluded, available_patches)

        choices = [
            f"📋 Browse & Toggle Patches ({len(available_patches)} available)",
            "➕ Add Custom Patch to Include (+)",
            "➖ Add Custom Patch to Exclude (-)",
            "🔄 Toggle or Remove Existing Override",
            "🧹 Reset to Source Defaults (Remove All Overrides)",
            "📝 Open File in System Editor",
            "💾 Save and Return",
            "Cancel / Discard Changes",
        ]

        action = questionary.select("Select patch action:", choices=choices).ask()
        if not action or action == "Cancel / Discard Changes":
            break

        if action == "💾 Save and Return":
            write_patch_file(patch_file, included, excluded, others)
            console.print(f"[bold green]✓ Saved patch configuration to {patch_file.name}![/bold green]\n")
            break

        if action.startswith("📋 Browse & Toggle Patches"):
            included, excluded = browse_and_toggle_patches(console, available_patches, included, excluded)

        elif action == "➕ Add Custom Patch to Include (+)":
            name = questionary.text("Enter patch name to force-include:").ask()
            if name and name.strip():
                p_name = name.strip()
                if p_name in excluded:
                    excluded.remove(p_name)
                if p_name not in included:
                    included.append(p_name)
                console.print(f"[green]Added override: + {p_name}[/green]")

        elif action == "➖ Add Custom Patch to Exclude (-)":
            name = questionary.text("Enter patch name to force-exclude:").ask()
            if name and name.strip():
                p_name = name.strip()
                if p_name in included:
                    included.remove(p_name)
                if p_name not in excluded:
                    excluded.append(p_name)
                console.print(f"[red]Added override: - {p_name}[/red]")

        elif action == "🔄 Toggle or Remove Existing Override":
            all_patches = [f"+ {p}" for p in included] + [f"- {p}" for p in excluded]
            if not all_patches:
                console.print("[yellow]No custom patch overrides defined.[/yellow]")
                continue
            all_patches.append("Cancel")

            selected = questionary.select("Select an override to modify:", choices=all_patches).ask()
            if not selected or selected == "Cancel":
                continue

            sign = selected[0]
            p_name = selected[2:]

            patch_action = questionary.select(
                f"Action for '{p_name}':",
                choices=[
                    "Remove override (Return to source default)",
                    "Switch to " + ("Exclude (-)" if sign == "+" else "Include (+)"),
                    "Cancel",
                ],
            ).ask()

            if patch_action == "Remove override (Return to source default)":
                if sign == "+" and p_name in included:
                    included.remove(p_name)
                elif sign == "-" and p_name in excluded:
                    excluded.remove(p_name)
                console.print(f"[yellow]Removed override for {p_name}[/yellow]")
            elif patch_action and patch_action.startswith("Switch to"):
                if sign == "+":
                    included.remove(p_name)
                    excluded.append(p_name)
                else:
                    excluded.remove(p_name)
                    included.append(p_name)
                console.print(f"[green]Toggled {p_name}[/green]")

        elif action == "🧹 Reset to Source Defaults (Remove All Overrides)":
            confirm = questionary.confirm("Clear all custom overrides and use source defaults?", default=False).ask()
            if confirm:
                included.clear()
                excluded.clear()
                if patch_file.exists():
                    patch_file.unlink()
                console.print(f"[green]Reset to default recommendations. Deleted {patch_file.name}.[/green]")

        elif action == "📝 Open File in System Editor":
            write_patch_file(patch_file, included, excluded, others)
            console.print(f"[cyan]Opening {patch_file} in default editor...[/cyan]")
            if os.name == "nt":
                os.startfile(str(patch_file))
            else:
                subprocess.run(["xdg-open", str(patch_file)])
            questionary.press_any_key_to_continue("Press any key after you finish editing and saving in your editor...").ask()
            included, excluded, others = parse_patch_file(patch_file)


def patch_editor_menu(console: Console) -> None:
    config = load_config()
    patch_list = config.get("patch_list", [])

    choices = [f"{e.get('app_name')} ({e.get('source')})" for e in patch_list]
    choices.append("Back to Main Menu")

    selected = questionary.select(
        "Select an application to view/edit patches:",
        choices=choices,
    ).ask()

    if not selected or selected == "Back to Main Menu":
        return

    app_name = selected.split()[0]
    source = selected.split("(")[1].rstrip(")")
    edit_app_patches(console, app_name, source)
