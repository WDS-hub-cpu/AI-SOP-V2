param(
    [switch]$Lite,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

Write-Step "Project root: $(Get-ProjectRoot)"

# ---------- Python ----------
$python = Join-Path (Get-ProjectRoot) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Step "Creating Python virtual environment (.venv)"
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & py -3 -m venv (Join-Path (Get-ProjectRoot) ".venv")
    } else {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) { throw "Python 3 not found. Install Python 3.11+ first." }
        & $pythonCmd.Source -m venv (Join-Path (Get-ProjectRoot) ".venv")
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

$requirements = if ($Lite) { "requirements-lite.txt" } else { "requirements.txt" }
Write-Step "Installing Python dependencies ($requirements)"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path (Get-ProjectRoot) "backend\$requirements")
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }

# ---------- .env ----------
$envFile = Join-Path (Get-ProjectRoot) "backend\.env"
$envExample = Join-Path (Get-ProjectRoot) "backend\.env.example"
if ((-not (Test-Path $envFile)) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Ok "Created backend\.env from .env.example"
}

# ---------- Node / frontend ----------
$node = Get-NodeExe
$npm = Get-NpmCmd
Write-Ok "Node: $node"
Write-Ok "npm : $npm"

$viteEntry = Join-Path (Get-ProjectRoot) "frontend\node_modules\vite\bin\vite.js"
if ($Force -or -not (Test-Path $viteEntry)) {
    Write-Step "Installing frontend dependencies (npm install)"
    Push-Location (Join-Path (Get-ProjectRoot) "frontend")
    try {
        & $npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    } finally {
        Pop-Location
    }
} else {
    Write-Ok "Frontend dependencies already installed (use -Force to reinstall)"
}

Write-Host ""
Write-Ok "Installation complete."
Write-Host "Next steps:"
Write-Host "  start-all.bat                 # start backend + frontend"
Write-Host "  scripts\start-backend.ps1     # backend only"
Write-Host "  scripts\start-frontend.ps1    # frontend only"
Write-Host "  status.bat                    # show service status"
