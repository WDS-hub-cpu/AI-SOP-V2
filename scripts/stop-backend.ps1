$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$port = 8000
$stopped = $false

$savedPid = Read-Pid -Name "backend"
if ($savedPid) {
    if (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) {
        Write-Step "Stopping backend PID $savedPid"
        Stop-ProcessTree -ProcessId $savedPid
        $stopped = $true
        Wait-PortFree -Port $port -TimeoutSeconds 6 | Out-Null
    }
    Remove-PidFile -Name "backend"
}

$portPid = Get-PortProcessId -Port $port
if ($portPid) {
    $commandLine = Get-ProcessCommandLine -ProcessId $portPid
    $processName = Get-ProcessNameSafe -ProcessId $portPid
    $looksLikeBackend = ($commandLine -match "app\.main:app") -or ($commandLine -match "uvicorn")
    if ((-not $looksLikeBackend) -and $savedPid -and $processName -match "^python") {
        # 父进程已被杀掉，但子进程仍短暂占用端口
        $looksLikeBackend = $true
    }
    if ($looksLikeBackend) {
        Write-Step "Stopping backend on port $port (PID $portPid)"
        Stop-ProcessTree -ProcessId $portPid
        $stopped = $true
        Wait-PortFree -Port $port -TimeoutSeconds 6 | Out-Null
    } else {
        Write-Warn "Port $port is occupied by an unrelated process (PID $portPid, $processName)."
        Write-Host "Command line: $commandLine"
        Write-Host "Inspect with: Get-Process -Id $portPid"
    }
}

if ($stopped) {
    Write-Ok "Backend stopped."
} else {
    Write-Ok "Backend is not running."
}
