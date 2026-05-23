# Savant Installer for Windows (PowerShell)
# Usage:
#   iwr https://raw.githubusercontent.com/PabloTheThinker/savant/main/scripts/install.ps1 -UseBasicParsing | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Savant Installer (Windows)" -ForegroundColor Magenta
Write-Host "The Living, Learning Ecosystem for AI Agent Swarms" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $python = (Get-Command python -ErrorAction Stop).Source
    $version = & python --version 2>&1
    Write-Host "✓ Found $version" -ForegroundColor Green
} catch {
    Write-Host "✗ Python 3.11+ is required." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check pip
try {
    python -m pip --version | Out-Null
} catch {
    Write-Host "✗ pip is not available." -ForegroundColor Red
    exit 1
}

Write-Host "→ Installing Savant..." -ForegroundColor Cyan

$repo = "https://github.com/PabloTheThinker/savant.git"

try {
    python -m pip install --user --upgrade "git+$repo" --quiet
    Write-Host "✓ Savant installed successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Installation failed." -ForegroundColor Red
    Write-Host "Try manually: python -m pip install --user git+$repo" -ForegroundColor Yellow
    exit 1
}

# Add to user PATH if needed
$userBin = "$env:USERPROFILE\AppData\Local\Programs\Python\Python*\Scripts"
$path = [Environment]::GetEnvironmentVariable("Path", "User")
if ($path -notlike "*$userBin*") {
    Write-Host "→ Adding Savant to your user PATH..." -ForegroundColor Cyan
    [Environment]::SetEnvironmentVariable("Path", "$path;$userBin", "User")
    Write-Host "  Please restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Run the professional TUI:" -ForegroundColor White
Write-Host "  savant" -ForegroundColor Cyan
Write-Host ""
Write-Host "Documentation: https://github.com/PabloTheThinker/savant" -ForegroundColor DarkGray

# Offer to launch
$launch = Read-Host "Launch Savant now? [Y/n]"
if ($launch -eq "" -or $launch -match "^[Yy]") {
    & savant
}