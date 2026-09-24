#!/usr/bin/env python3
"""Morphe CLI & Interactive TUI Suite Entry Point.

Usage:
    python morphe.py              # Launch interactive TUI
    python morphe.py validate     # Run config health check directly
    python morphe.py list         # Display configured apps table
    python morphe.py build <app>  # Quick dispatch for an app
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_cli() -> None:
    from rich.console import Console
    console = Console(legacy_windows=False)

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("validate", "check"):
            from src.tui.validator import run_validation
            success = run_validation(console)
            sys.exit(0 if success else 1)
        elif cmd in ("list", "ls", "apps"):
            from src.tui.app_manager import display_apps_table
            query = sys.argv[2] if len(sys.argv) > 2 else ""
            display_apps_table(console, search_query=query)
            sys.exit(0)
        elif cmd in ("build", "dispatch"):
            if len(sys.argv) < 3:
                console.print("[red]Usage: python morphe.py build <app_name> [source][/red]")
                sys.exit(1)
            app_name = sys.argv[2]
            source = sys.argv[3] if len(sys.argv) > 3 else "morphe"
            import subprocess
            cmd_args = [
                "gh", "workflow", "run", "manual-patch.yml",
                "-f", f"app_name={app_name}",
                "-f", f"source={source}",
                "-f", "architecture=universal",
            ]
            console.print(f"[cyan]Dispatching build for {app_name} ({source})...[/cyan]")
            subprocess.run(cmd_args, check=True)
            console.print(f"[green]Dispatched successfully![/green]")
            sys.exit(0)
        elif cmd in ("help", "--help", "-h"):
            console.print("""[bold cyan]Morphe Builder CLI[/bold cyan]
Commands:
  [green]python morphe.py[/green]             Launch interactive TUI
  [green]python morphe.py validate[/green]    Run configuration health check
  [green]python morphe.py list [query][/green]  List configured applications
  [green]python morphe.py build <app>[/green] Quick trigger CI build for an app
""")
            sys.exit(0)

    # Launch full interactive TUI
    from src.tui.main_menu import main
    main()


if __name__ == "__main__":
    run_cli()
