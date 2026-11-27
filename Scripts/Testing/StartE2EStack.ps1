# Starts an isolated NEXTRON stack for the browser tests, so they never write into the operator's data.
#
#   database  nextron_e2e (created and migrated here)      storage  tmp/e2e-storage
#   API       http://127.0.0.1:8002                        worker   same database and storage
#   web       http://localhost:8090 (Next dev, its own build folder .next-e2e)
#   Qdrant    collection nextron_e2e_images                Neo4j and web visual search: off
#
# Usage (repository root):  powershell -File Scripts\Testing\StartE2EStack.ps1
# Then:                     cd Tests\End-To-End; npx playwright test        (its defaults point at this stack)
# Stop:                     powershell -File Scripts\Testing\StartE2EStack.ps1 -Stop
# Start it from a PowerShell window (or a detached process): servers started inside a short-lived shell job end with it.
# Reset its data:           powershell -File Scripts\Testing\StartE2EStack.ps1 -Reset   (drops nextron_e2e only)
param([switch]$Stop, [switch]$Reset)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path "$PSScriptRoot\..\.."
$py = "$root\.venv\Scripts\python.exe"
$logs = "$root\tmp"; New-Item -ItemType Directory -Force $logs | Out-Null

# The processes this script started are recorded in tmp/e2e-pids.txt, so stopping touches nothing else
# (the operator's own API and worker run the same code with the same command line).
$pidFile = "$logs\e2e-pids.txt"
function Stop-E2E {
  if (Test-Path $pidFile) {
    foreach ($p in Get-Content $pidFile) { if ($p) { & taskkill /PID $p /T /F 2>&1 | Out-Null } }
    Remove-Item $pidFile -Force
  }
  Get-NetTCPConnection -LocalPort 8002, 8090 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { & taskkill /PID $_.OwningProcess /T /F 2>&1 | Out-Null }
}
if ($Stop) { Stop-E2E; "E2E stack stopped"; return }

# the test database lives on the same PostgreSQL server as DATABASE_URL in Backend/.env
$url = & $py -m Scripts.Testing.E2EDatabase $(if ($Reset) { '--reset' })
if ($LASTEXITCODE -ne 0 -or -not $url) { throw "Could not create the nextron_e2e database" }
if ($Reset -and (Test-Path "$root\tmp\e2e-storage")) { Get-ChildItem "$root\tmp\e2e-storage" -Recurse -File | ForEach-Object { $_.IsReadOnly = $false }; Remove-Item "$root\tmp\e2e-storage" -Recurse -Force }

$env:DATABASE_URL = $url
# alembic logs to stderr, which Windows PowerShell 5 turns into a terminating error under ErrorActionPreference=Stop
$ErrorActionPreference = 'Continue'
& $py -m alembic -c "$root\Database\PostgreSQL\alembic.ini" upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Migrating nextron_e2e failed" }
$ErrorActionPreference = 'Stop'

Stop-E2E
$env:NEXTRON_E2E = '1'
$env:STORAGE_ROOT = "$root\tmp\e2e-storage"
$env:CORS_ORIGINS = 'http://localhost:8090,http://127.0.0.1:8090'
$env:NEO4J_URI = ''
$env:QDRANT_COLLECTION = 'nextron_e2e_images'
$env:WEB_VISUAL_SEARCH_ENABLED = 'false'
$api = Start-Process -PassThru -FilePath $py -ArgumentList '-m', 'uvicorn', 'Backend.App.Main:app', '--host', '127.0.0.1', '--port', '8002' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$logs\e2e-api.log" -RedirectStandardError "$logs\e2e-api.err.log"
$worker = Start-Process -PassThru -FilePath $py -ArgumentList '-m', 'Backend.App.Workers.Worker' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$logs\e2e-worker.log" -RedirectStandardError "$logs\e2e-worker.err.log"

$env:NEXT_PUBLIC_NEXTRON_API = 'http://localhost:8002/api/v1'
$env:NEXT_DIST_DIR = '.next-e2e'
$web = Start-Process -PassThru -FilePath 'npm.cmd' -ArgumentList 'exec', 'next', '--', 'dev', '-p', '8090' -WorkingDirectory "$root\Frontend\Web" -WindowStyle Hidden -RedirectStandardOutput "$logs\e2e-web.log" -RedirectStandardError "$logs\e2e-web.err.log"

Set-Content -Path $pidFile -Value @($api.Id, $worker.Id, $web.Id)

foreach ($u in 'http://127.0.0.1:8002/api/v1/health/ready', 'http://localhost:8090/') {
  for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 5 | Out-Null; break } catch { Start-Sleep 1 } }
}
"E2E stack ready: API http://127.0.0.1:8002, web http://localhost:8090 (database nextron_e2e)"
