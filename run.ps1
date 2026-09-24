# Morphe Builder Interactive Launcher for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "`n🚀 Launching Morphe Builder Interactive Suite..." -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "❌ Error: Python 3 is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://www.python.org/ or Microsoft Store."
    Pause
    Exit 1
}

# 2. Check and install dependencies if missing
$checkModules = python -c "import rich, questionary; print('OK')" 2>$null
if ($checkModules -ne "OK") {
    Write-Host "📦 Installing required dependencies (rich, questionary)..." -ForegroundColor Yellow
    python -m pip install --quiet rich questionary
}

# 3. Launch TUI
python morphe.py $args
