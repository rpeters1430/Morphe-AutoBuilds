"""Main TUI Loop and Dashboard for Morphe Builder."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .app_manager import load_config, manage_apps_menu
from .ci_dispatcher import ci_menu, is_gh_available
from .dry_run import test_app_dry_run
from .patch_editor import patch_editor_menu
from .validator import run_validation

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(legacy_windows=False)


def print_banner() -> None:
    config = load_config()
    total_apps = len(config.get("patch_list", []))
    enabled_apps = sum(1 for e in config.get("patch_list", []) if e.get("enabled", True))

    gh_status = "[bold green]Online (`gh` CLI ready)[/bold green]" if is_gh_available() else "[bold yellow]`gh` CLI not in PATH[/bold yellow]"

    banner_text = Text()
    banner_text.append("🔧 MORPHE AUTO-BUILDER INTERACTIVE SUITE\n", style="bold cyan")
    banner_text.append(f"Apps: {enabled_apps}/{total_apps} enabled  •  GitHub CI: ", style="white")
    banner_text.append_text(Text.from_markup(gh_status))

    console.print(Panel(
        banner_text,
        border_style="cyan",
        subtitle="v2.0 • Maintainer & App Studio",
        subtitle_align="right",
    ))


def run_portal_generator(console: Console) -> None:
    """Invokes portal generator or instructions."""
    console.print("\n[bold cyan]🌐 Download Portal & Obtainium Ecosystem[/bold cyan]\n")
    try:
        from scripts.generate_portal_data import generate_portal_assets
        generate_portal_assets(console)
        
        preview = questionary.confirm("Would you like to open the portal in your web browser now?", default=True).ask()
        if preview:
            index_path = Path(__file__).resolve().parent.parent.parent / "docs" / "index.html"
            console.print(f"[cyan]Opening {index_path} in browser...[/cyan]")
            if os.name == "nt":
                os.startfile(str(index_path))
            else:
                subprocess.run(["xdg-open", str(index_path)])
    except Exception as e:
        console.print(f"[red]Error generating portal: {e}[/red]")
    questionary.press_any_key_to_continue().ask()


def main() -> None:
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()

            choices = [
                "📱 App Manager (Add, edit, toggle, search apps)",
                "🧩 Patch Editor (Include / exclude patches)",
                "🚀 CI Dispatcher & Live Log Monitor (Trigger & watch GitHub Actions)",
                "🔍 Health Check & Config Validator (Validate JSON, sources, apps)",
                "🔬 Dry-Run & Inspector (Check app & source readiness)",
                "🌐 Download Portal & Obtainium Index (Build user web catalog)",
                "🚪 Exit",
            ]

            action = questionary.select(
                "Select a tool to launch:",
                choices=choices,
                style=questionary.Style([
                    ("qmark", "fg:#00ffff bold"),
                    ("question", "bold"),
                    ("selected", "fg:#00ffff bold"),
                    ("pointer", "fg:#00ffff bold"),
                ]),
            ).ask()

            if not action or action == "🚪 Exit":
                console.print("\n[dim]Goodbye![/dim]\n")
                break

            if action.startswith("📱"):
                manage_apps_menu(console)
            elif action.startswith("🧩"):
                patch_editor_menu(console)
            elif action.startswith("🚀"):
                ci_menu(console)
            elif action.startswith("🔍"):
                run_validation(console)
                questionary.press_any_key_to_continue().ask()
            elif action.startswith("🔬"):
                test_app_dry_run(console)
            elif action.startswith("🌐"):
                run_portal_generator(console)

    except KeyboardInterrupt:
        console.print("\n\n[dim]Session closed.[/dim]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
