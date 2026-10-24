$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$port = 5173
$stopped = $false

$savedPid = Read-Pid -Name "frontend"
if ($savedPid) {
    if (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) {
        Write-Step "Stopping frontend PID $savedPid"
        Stop-ProcessTree -ProcessId $savedPid
        $stopped = $true
        Wait-PortFree -Port $port -TimeoutSeconds 6 | Out-Null
    }
    Remove-PidFile -Name "frontend"
}

$portPid = Get-PortProcessId -Port $port
if ($portPid) {
    $commandLine = Get-ProcessCommandLine -ProcessId $portPid
    $processName = Get-ProcessNameSafe -ProcessId $portPid
    $looksLikeFrontend = ($commandLine -match "vite") -or ($commandLine -match "node_modules")
    if ((-not $looksLikeFrontend) -and $savedPid -and $processName -eq "node") {
        $looksLikeFrontend = $true
    }
    if ($looksLikeFrontend) {
        Write-Step "Stopping frontend on port $port (PID $portPid)"
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
    Write-Ok "Frontend stopped."
} else {
    Write-Ok "Frontend is not running."
}
