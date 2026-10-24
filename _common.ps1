# Shared helpers for local start/stop scripts (Windows PowerShell 5.1 compatible).

$ErrorActionPreference = "Stop"

$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:BackendDir = Join-Path $script:ProjectRoot "backend"
$script:FrontendDir = Join-Path $script:ProjectRoot "frontend"
$script:RunDir = Join-Path $script:ProjectRoot ".run"
$script:LogDir = Join-Path $script:ProjectRoot "logs"

function Get-ProjectRoot { return $script:ProjectRoot }
function Get-BackendDir { return $script:BackendDir }
function Get-FrontendDir { return $script:FrontendDir }
function Get-LogDir { return $script:LogDir }
function Get-RunDir { return $script:RunDir }

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Ensure-RuntimeDirs {
    foreach ($dir in @($script:RunDir, $script:LogDir, (Join-Path $script:ProjectRoot "data"))) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
}

function Get-PythonExe {
    $venvPython = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) { return $venvPython }
    throw "Python virtual environment not found. Run install.bat first."
}

function Get-NodeExe {
    $command = Get-Command node -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $localNode = Join-Path $script:ProjectRoot ".tools\node\node.exe"
    if (Test-Path $localNode) { return $localNode }
    throw "Node.js not found. Install Node.js LTS, or place a portable Node in .tools\node, then re-run install.bat."
}

function Get-NpmCmd {
    $command = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $localNpm = Join-Path $script:ProjectRoot ".tools\node\npm.cmd"
    if (Test-Path $localNpm) { return $localNpm }
    throw "npm.cmd not found. Install Node.js LTS first."
}

function Get-PortProcessId {
    param([int]$Port)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($connection) { return [int]$connection.OwningProcess }
    } catch {
        $line = netstat -ano | Select-String ":$Port\s" | Select-String "LISTENING" | Select-Object -First 1
        if ($line) {
            $parts = ($line.ToString().Trim() -split "\s+")
            return [int]$parts[-1]
        }
    }
    return $null
}

function Get-HttpStatus {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return [int]$response.StatusCode
    } catch {
        return 0
    }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = Get-HttpStatus -Url $Url
        if ($status -ge 200 -and $status -lt 500) { return $true }
        Start-Sleep -Milliseconds 600
    }
    return $false
}

function Wait-HttpOrExit {
    param(
        [string]$Url,
        [int]$ProcessId,
        [int]$TimeoutSeconds = 45
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { return $false }
        $status = Get-HttpStatus -Url $Url
        if ($status -ge 200 -and $status -lt 500) { return $true }
        Start-Sleep -Milliseconds 600
    }
    return $false
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    try {
        $info = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        if ($info) { return [string]$info.CommandLine }
    } catch {
        return ""
    }
    return ""
}

function Get-ProcessNameSafe {
    param([int]$ProcessId)
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) { return [string]$process.ProcessName }
    return ""
}

function Wait-PortFree {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 8
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-PortProcessId -Port $Port)) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return (-not (Get-PortProcessId -Port $Port))
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    taskkill /PID $ProcessId /T /F *> $null
}

function Save-Pid {
    param(
        [string]$Name,
        [int]$ProcessId
    )
    Ensure-RuntimeDirs
    Set-Content -Path (Join-Path $script:RunDir "$Name.pid") -Value $ProcessId -Encoding ASCII
}

function Read-Pid {
    param([string]$Name)
    $file = Join-Path $script:RunDir "$Name.pid"
    if (-not (Test-Path $file)) { return $null }
    $raw = (Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $raw) { return $null }
    try { return [int]$raw.Trim() } catch { return $null }
}

function Remove-PidFile {
    param([string]$Name)
    $file = Join-Path $script:RunDir "$Name.pid"
    if (Test-Path $file) { Remove-Item $file -Force -ErrorAction SilentlyContinue }
}

function Show-LogTail {
    param(
        [string]$Path,
        [int]$Lines = 20
    )
    if (Test-Path $Path) {
        Write-Host "----- $Path (last $Lines lines) -----" -ForegroundColor DarkGray
        Get-Content -Path $Path -Tail $Lines -ErrorAction SilentlyContinue
        Write-Host "----------------------------------------" -ForegroundColor DarkGray
    }
}
