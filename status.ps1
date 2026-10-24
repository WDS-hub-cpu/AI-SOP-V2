$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

function Show-Service {
    param(
        [string]$Name,
        [int]$Port,
        [string]$HealthUrl,
        [string]$BaseUrl
    )
    $processId = Get-PortProcessId -Port $Port
    if (-not $processId) {
        Write-Warn "$Name : not running (port $Port is free)"
        return
    }
    $status = Get-HttpStatus -Url $HealthUrl
    if ($status -ge 200 -and $status -lt 500) {
        Write-Ok "$Name : running (PID $processId, HTTP $status)"
    } else {
        Write-Warn "$Name : port $Port is occupied by PID $processId, HTTP check failed"
    }
    Write-Host "    URL: $BaseUrl"
}

Write-Host "=========== Industrial AI SOP - service status ===========" -ForegroundColor Cyan
Show-Service -Name "Backend " -Port 8000 -HealthUrl "http://127.0.0.1:8000/api/v1/health/live" -BaseUrl "http://127.0.0.1:8000/docs"
Show-Service -Name "Frontend" -Port 5173 -HealthUrl "http://127.0.0.1:5173/" -BaseUrl "http://127.0.0.1:5173/"

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 3
    if ($health.code -eq 0) {
        $data = $health.data
        Write-Host ""
        Write-Host "Model    : $($data.model.status) (simulated=$($data.model.simulated))"
        Write-Host "Camera   : $($data.camera.status) (simulated=$($data.camera.simulated))"
        Write-Host "Runtime  : $($data.runtime.state) (simulated=$($data.runtime.simulated))"
        Write-Host "Database : $($data.database.path)"
    }
} catch {
    Write-Warn "Unable to read backend health details."
}

Write-Host ""
Write-Host "Logs: logs\backend.log, logs\backend.err.log, logs\frontend.out.log" -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
