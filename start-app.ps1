param(
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$runtime = Join-Path $root ".runtime"

function Test-Endpoint {
    param([string]$Uri)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Stop-WorkspaceProcesses {
    param([string]$CommandPattern)

    $escapedRoot = [WildcardPattern]::Escape($root)
    $matches = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like "*$escapedRoot*" -and
            $_.CommandLine -like "*$CommandPattern*"
        } |
        Sort-Object ProcessId -Descending

    foreach ($process in $matches) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PortAvailable {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listeners) {
        $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        throw "$ServiceName could not start: port $Port is owned by another process ($owners)."
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment is missing. Run: cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[dev,postgres]'"
}
if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
    throw "Frontend dependencies are missing. Run: cd frontend; npm install"
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$backendHealthy = Test-Endpoint "http://127.0.0.1:8000/health"
if ($Restart -or -not $backendHealthy) {
    Stop-WorkspaceProcesses "uvicorn app.main:app"
    Start-Sleep -Milliseconds 700
    Assert-PortAvailable -Port 8000 -ServiceName "Backend"

    Push-Location $backend
    try {
        & $python -m alembic upgrade head
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed."
    }

    Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtime "backend.out.log") `
        -RedirectStandardError (Join-Path $runtime "backend.err.log") | Out-Null

    $backendHealthy = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-Endpoint "http://127.0.0.1:8000/health") {
            $backendHealthy = $true
            break
        }
    }
    if (-not $backendHealthy) {
        throw "Backend failed to start. Check .runtime\backend.err.log"
    }
}

$frontendHealthy = Test-Endpoint "http://localhost:5173"
if ($Restart -or -not $frontendHealthy) {
    Stop-WorkspaceProcesses "vite"
    Start-Sleep -Milliseconds 700
    Assert-PortAvailable -Port 5173 -ServiceName "Frontend"

    Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList "run", "dev", "--", "--host", "localhost", "--port", "5173" `
        -WorkingDirectory $frontend `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtime "frontend.out.log") `
        -RedirectStandardError (Join-Path $runtime "frontend.err.log") | Out-Null

    $frontendHealthy = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-Endpoint "http://localhost:5173") {
            $frontendHealthy = $true
            break
        }
    }
    if (-not $frontendHealthy) {
        throw "Frontend failed to start. Check .runtime\frontend.err.log"
    }
}

Write-Host ""
Write-Host "Thang Rod is ready" -ForegroundColor Green
Write-Host "Web:     http://localhost:5173"
Write-Host "API:     http://127.0.0.1:8000"
Write-Host "API docs: http://127.0.0.1:8000/docs"
