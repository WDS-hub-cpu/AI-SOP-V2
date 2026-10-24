$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

Write-Step "Starting backend and frontend"

try {
    & "$PSScriptRoot\start-backend.ps1"
} catch {
    Write-Fail "Backend failed to start: $($_.Exception.Message)"
    exit 1
}

try {
    & "$PSScriptRoot\start-frontend.ps1"
} catch {
    Write-Fail "Frontend failed to start: $($_.Exception.Message)"
    Write-Host "Backend is still running. Stop it with: scripts\stop-backend.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Ok "All services are running."
Write-Host "Frontend : http://127.0.0.1:5173/"
Write-Host "API docs : http://127.0.0.1:8000/docs"
Write-Host "Health   : http://127.0.0.1:8000/api/v1/health"
Write-Host ""
Write-Host "Stop everything with: stop-all.bat" -ForegroundColor DarkGray
