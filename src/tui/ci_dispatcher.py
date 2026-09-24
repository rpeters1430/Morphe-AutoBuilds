"""GitHub Actions CI Dispatcher & Live Log Monitor for Morphe Builder TUI.

Uses `gh` CLI to trigger workflows, monitor live build logs, and view run status.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

import questionary
from rich.console import Console
from rich.table import Table

from .app_manager import load_config


def is_gh_available() -> bool:
    return shutil.which("gh") is not None


def check_gh_auth(console: Console) -> bool:
    if not is_gh_available():
        console.print("[bold red]Error: GitHub CLI (`gh`) is not installed or not in PATH.[/bold red]")
        console.print("[dim]Install gh from https://cli.github.com/ or via `winget install GitHub.cli`[/dim]\n")
        return False

    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[bold yellow]Warning: GitHub CLI is not logged in.[/bold yellow]")
        console.print("[dim]Run `gh auth login` in your terminal to authenticate.[/dim]\n")
        return False
    return True


def list_recent_runs(console: Console, limit: int = 10) -> list[dict[str, Any]]:
    cmd = [
        "gh", "run", "list",
        f"--limit={limit}",
        "--json", "databaseId,name,status,conclusion,headBranch,createdAt,url",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        runs = json.loads(proc.stdout)
    except Exception as e:
        console.print(f"[red]Failed to fetch workflow runs: {e}[/red]")
        return []

    table = Table(title="🚀 Recent GitHub Actions Workflow Runs", expand=True)
    table.add_column("Run ID", style="cyan", width=12)
    table.add_column("Workflow", style="bold white")
    table.add_column("Branch", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Conclusion", justify="center")
    table.add_column("Created", style="dim")

    for r in runs:
        run_id = str(r.get("databaseId"))
        name = r.get("name", "")
        branch = r.get("headBranch", "")
        status = r.get("status", "")
        conclusion = r.get("conclusion") or "running"
        created = r.get("createdAt", "")[:19].replace("T", " ")

        status_style = "green" if status == "completed" else "yellow"
        if conclusion == "success":
            conc_str = "[bold green]✓ SUCCESS[/bold green]"
        elif conclusion == "failure":
            conc_str = "[bold red]✗ FAILED[/bold red]"
        elif conclusion == "cancelled":
            conc_str = "[dim red]CANCELLED[/dim red]"
        else:
            conc_str = f"[bold yellow]⟳ {conclusion.upper()}[/bold yellow]"

        table.add_row(
            run_id,
            name,
            branch,
            f"[{status_style}]{status}[/{status_style}]",
            conc_str,
            created,
        )

    console.print(table)
    return runs


def trigger_manual_patch(console: Console) -> None:
    if not check_gh_auth(console):
        return

    config = load_config()
    patch_list = config.get("patch_list", [])

    choices = [f"{e.get('app_name')} ({e.get('source')})" for e in patch_list]
    choices.append("Cancel")

    selected = questionary.select("Select an app to build:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    app_name = selected.split()[0]
    matched = next((e for e in patch_list if e.get("app_name") == app_name), {})
    default_source = matched.get("source", "morphe")

    source = questionary.text("Confirm or change source:", default=default_source).ask()
    if not source:
        return

    arch = questionary.select(
        "Select target architecture:",
        choices=["universal", "arm64-v8a", "armeabi-v7a", "configured"],
        default="universal",
    ).ask()
    if not arch:
        return

    patches_channel = questionary.select(
        "Select patches release channel:",
        choices=["default", "stable", "prerelease", "dev"],
        default="default",
    ).ask()
    if not patches_channel:
        return

    experimental = questionary.select(
        "Allow experimental versions?",
        choices=["default", "true", "false"],
        default="default",
    ).ask()
    if not experimental:
        return

    version = questionary.text("Specific version (leave empty for latest compatible):").ask()
    if version is None:
        return

    replace_release = questionary.confirm("Replace APK in existing release?", default=True).ask()

    cmd = [
        "gh", "workflow", "run", "manual-patch.yml",
        "-f", f"app_name={app_name}",
        "-f", f"source={source}",
        "-f", f"architecture={arch}",
        "-f", f"patches_channel={patches_channel}",
        "-f", f"experimental={experimental}",
        "-f", f"replace_in_release={'true' if replace_release else 'false'}",
    ]
    if version.strip():
        cmd.extend(["-f", f"version={version.strip()}"])

    console.print(f"\n[cyan]Dispatching workflow on GitHub Actions for {app_name}...[/cyan]")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        console.print(f"[bold green]✓ Successfully dispatched manual-patch.yml for {app_name}![/bold green]\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Failed to trigger workflow: {e.stderr}[/bold red]\n")
        return

    watch = questionary.confirm("Would you like to watch live logs in terminal?", default=True).ask()
    if watch:
        console.print("[dim]Waiting for GitHub to register the run...[/dim]")
        time.sleep(4)
        runs = list_recent_runs(console, limit=3)
        if runs:
            latest_id = str(runs[0].get("databaseId"))
            console.print(f"[cyan]Streaming logs for Run #{latest_id}... (Press Ctrl+C to stop watching)[/cyan]\n")
            try:
                subprocess.run(["gh", "run", "watch", latest_id])
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped watching. The build is continuing in the cloud.[/yellow]\n")


def trigger_full_rebuild(console: Console) -> None:
    if not check_gh_auth(console):
        return

    force = questionary.confirm(
        "Force rebuild EVERY app (ignore incremental check)?",
        default=False,
    ).ask()

    confirm = questionary.confirm(
        "Are you sure you want to trigger 'Auto Build and Release Morphe'?",
        default=True,
    ).ask()
    if not confirm:
        return

    cmd = [
        "gh", "workflow", "run", "patch.yml",
        "-f", f"force_full_rebuild={'true' if force else 'false'}",
    ]
    console.print("\n[cyan]Dispatching patch.yml workflow...[/cyan]")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        console.print("[bold green]✓ Successfully triggered Auto Build and Release Morphe![/bold green]\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Failed to trigger workflow: {e.stderr}[/bold red]\n")


def inspect_run_menu(console: Console) -> None:
    runs = list_recent_runs(console, limit=10)
    if not runs:
        return

    choices = [
        f"#{r['databaseId']} - {r['name']} ({r.get('conclusion') or r.get('status')})"
        for r in runs
    ]
    choices.append("Cancel")

    selected = questionary.select("Select a run to inspect:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    run_id = selected.split()[0].replace("#", "")

    action = questionary.select(
        f"Action for Run #{run_id}:",
        choices=[
            "Watch Live / View Status",
            "View Run Logs",
            "Open in Web Browser",
            "Cancel Run",
            "Back",
        ],
    ).ask()

    if action == "Watch Live / View Status":
        try:
            subprocess.run(["gh", "run", "watch", run_id])
        except KeyboardInterrupt:
            pass
    elif action == "View Run Logs":
        subprocess.run(["gh", "run", "view", run_id, "--log"])
    elif action == "Open in Web Browser":
        subprocess.run(["gh", "run", "view", run_id, "--web"])
    elif action == "Cancel Run":
        if questionary.confirm(f"Cancel Run #{run_id}?", default=False).ask():
            subprocess.run(["gh", "run", "cancel", run_id])
            console.print(f"[yellow]Sent cancellation for #{run_id}[/yellow]")


def ci_menu(console: Console) -> None:
    while True:
        action = questionary.select(
            "🚀 GitHub Actions CI Dispatcher - Choose an action:",
            choices=[
                "Trigger Single App Build (manual-patch.yml)",
                "Trigger Full Rebuild Pipeline (patch.yml)",
                "View & Inspect Recent Runs",
                "Check GitHub CLI Status",
                "Back to Main Menu",
            ],
        ).ask()

        if not action or action == "Back to Main Menu":
            break

        if action == "Trigger Single App Build (manual-patch.yml)":
            trigger_manual_patch(console)
        elif action == "Trigger Full Rebuild Pipeline (patch.yml)":
            trigger_full_rebuild(console)
        elif action == "View & Inspect Recent Runs":
            inspect_run_menu(console)
        elif action == "Check GitHub CLI Status":
            check_gh_auth(console)
            questionary.press_any_key_to_continue().ask()
