param([switch]$PrepareOnly, [switch]$Test, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker command failed. Stop here and inspect the failure.' }
}

if (-not (Test-Path '.env')) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $jwt = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    $template = [IO.File]::ReadAllText((Join-Path $PWD '.env.example'))
    $template = $template.Replace('JWT_SECRET_KEY=', "JWT_SECRET_KEY=$jwt")
    [IO.File]::WriteAllText((Join-Path $PWD '.env'), $template, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Created .env with a random JWT secret. Set GOOGLE_GEMINI_API_KEY in .env locally.'
}
if ($PrepareOnly) { return }

$settings = [IO.File]::ReadAllText((Join-Path $PWD '.env'))
if ($settings -notmatch '(?m)^GOOGLE_GEMINI_API_KEY=\S+') {
    throw 'Set GOOGLE_GEMINI_API_KEY in .env, then run this script again. Never paste the key into chat.'
}
Invoke-Docker info --format '{{.OSType}}'
Invoke-Docker compose config --quiet
if (-not $SkipBuild) { Invoke-Docker compose build --no-cache }
Invoke-Docker compose up -d --wait --wait-timeout 900
foreach ($service in @('backend', 'celery-worker')) {
    $json = & docker compose exec -T $service python /opt/knowledgegpt-scripts/check_container_source.py --inside
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect $service source" }
    $hashes = $json | ConvertFrom-Json
    foreach ($entry in $hashes.PSObject.Properties) {
        $path = Join-Path $PWD ('backend/' + $entry.Name.Replace('.', '/') + '.py')
        $hostHash = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
        if ($hostHash -ne $entry.Value) { throw "$service source differs from checkout: $($entry.Name)" }
    }
    Write-Host "PASS: $service executed module hashes match checkout"
}
Invoke-Docker compose exec -T backend python /opt/knowledgegpt-scripts/local_health.py
if ($Test) {
    Invoke-Docker compose exec -T backend python /opt/knowledgegpt-scripts/smoke_test.py --base-url http://localhost:8000 --s3-transport-url http://minio:9000 --verify-database
}
Write-Host 'Open http://localhost:3000. Browser acceptance steps: docs/local-validation.md'
