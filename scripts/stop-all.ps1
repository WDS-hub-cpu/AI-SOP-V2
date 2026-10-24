$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

Write-Step "Stopping frontend"
& "$PSScriptRoot\stop-frontend.ps1"

Write-Step "Stopping backend"
& "$PSScriptRoot\stop-backend.ps1"

Write-Ok "All services stopped."
