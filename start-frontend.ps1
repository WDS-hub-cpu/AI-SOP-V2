$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$port = 5173
$url = "http://127.0.0.1:$port/"
Ensure-RuntimeDirs

$existingPid = Get-PortProcessId -Port $port
if ($existingPid) {
    $status = Get-HttpStatus -Url $url
    if ($status -ge 200 -and $status -lt 500) {
        Write-Ok "Frontend is already running on port $port (PID $existingPid)."
        Write-Host "Open: http://127.0.0.1:$port/"
        exit 0
    }
    throw "Port $port is occupied by PID $existingPid but is not serving HTTP. Run scripts\stop-frontend.ps1 or inspect the process."
}

$node = Get-NodeExe
$npm = Get-NpmCmd
$frontendDir = Get-FrontendDir
$viteEntry = Join-Path $frontendDir "node_modules\vite\bin\vite.js"

if (-not (Test-Path $viteEntry)) {
    Write-Step "Frontend dependencies missing; running npm install"
    Push-Location $frontendDir
    try {
        & $npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    } finally {
        Pop-Location
    }
}

$outLog = Join-Path (Get-LogDir) "frontend.out.log"
$errLog = Join-Path (Get-LogDir) "frontend.err.log"

Write-Step "Starting frontend on http://127.0.0.1:$port"
$process = Start-Process -FilePath $node `
    -ArgumentList @("node_modules\vite\bin\vite.js", "--host", "127.0.0.1", "--port", "$port", "--strictPort") `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Save-Pid -Name "frontend" -ProcessId $process.Id

if (Wait-HttpOrExit -Url $url -ProcessId $process.Id -TimeoutSeconds 40) {
    Write-Ok "Frontend started (PID $($process.Id))."
    Write-Host "Open: http://127.0.0.1:$port/"
    Write-Host "Logs: $outLog"
    Write-Host "      $errLog"
} else {
    Write-Fail "Frontend did not become ready in time."
    Show-LogTail -Path $errLog -Lines 30
    Show-LogTail -Path $outLog -Lines 30
    throw "Frontend startup failed. See logs above."
}
