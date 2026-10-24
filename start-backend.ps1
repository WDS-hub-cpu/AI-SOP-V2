param(
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$port = 8000
$healthUrl = "http://127.0.0.1:$port/api/v1/health/live"
Ensure-RuntimeDirs

$existingPid = Get-PortProcessId -Port $port
if ($existingPid) {
    $status = Get-HttpStatus -Url $healthUrl
    if ($status -ge 200 -and $status -lt 500) {
        Write-Ok "Backend is already running on port $port (PID $existingPid)."
        Write-Host "API:   http://127.0.0.1:$port/api/v1"
        Write-Host "Docs:  http://127.0.0.1:$port/docs"
        exit 0
    }
    throw "Port $port is occupied by PID $existingPid but the health check failed. Run scripts\stop-backend.ps1 or inspect the process."
}

$python = Get-PythonExe
$outLog = Join-Path (Get-LogDir) "backend.out.log"
$errLog = Join-Path (Get-LogDir) "backend.err.log"

$uvicornArgs = @(
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", "$port"
)
if ($Reload) { $uvicornArgs += "--reload" }

Write-Step "Starting backend on http://127.0.0.1:$port"
$process = Start-Process -FilePath $python `
    -ArgumentList $uvicornArgs `
    -WorkingDirectory (Get-BackendDir) `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Save-Pid -Name "backend" -ProcessId $process.Id

if (Wait-HttpOrExit -Url $healthUrl -ProcessId $process.Id -TimeoutSeconds 45) {
    $listenerPid = Get-PortProcessId -Port $port
    if ($listenerPid) {
        # venv 的 python.exe 在 Windows 上可能派生子进程，记录真正监听端口的 PID
        Save-Pid -Name "backend" -ProcessId $listenerPid
    }
    $displayPid = if ($listenerPid) { $listenerPid } else { $process.Id }
    Write-Ok "Backend started (PID $displayPid)."
    Write-Host "API:   http://127.0.0.1:$port/api/v1"
    Write-Host "Docs:  http://127.0.0.1:$port/docs"
    Write-Host "Logs:  $outLog"
    Write-Host "       $errLog"
} else {
    Write-Fail "Backend did not become ready in time."
    Show-LogTail -Path $errLog -Lines 30
    Show-LogTail -Path (Join-Path (Get-LogDir) "backend.log") -Lines 30
    throw "Backend startup failed. See logs above."
}
