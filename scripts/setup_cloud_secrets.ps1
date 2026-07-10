# One-time migration of production credentials into Google Secret Manager.
# Reads the gitignored .env.production file, never prints secret values, and
# switches Cloud Run to a dedicated runtime identity with secret references.

param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "us-east1",
    [string]$ServiceName = "dnd-and-beyond",
    [string]$EnvFile = ".env.production",
    [string]$RuntimeServiceAccountName = "dnd-and-beyond-runtime"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile = Join-Path $repoRoot $EnvFile
}
if (-not (Test-Path $EnvFile)) {
    Write-Error "Missing $EnvFile. Copy .env.production.example and fill it in first."
}

$productionValues = @{}
foreach ($line in Get-Content $EnvFile) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $name, $value = $trimmed -split "=", 2
    $productionValues[$name.Trim()] = $value.Trim()
}

$secretMap = [ordered]@{
    DATABASE_URL = "dnd-and-beyond-database-url"
    SMTP_HOST = "dnd-and-beyond-smtp-host"
    SMTP_PORT = "dnd-and-beyond-smtp-port"
    SMTP_USERNAME = "dnd-and-beyond-smtp-username"
    SMTP_PASSWORD = "dnd-and-beyond-smtp-password"
    SMTP_FROM = "dnd-and-beyond-smtp-from"
}
foreach ($variable in $secretMap.Keys) {
    if (-not $productionValues.ContainsKey($variable) -or [string]::IsNullOrWhiteSpace($productionValues[$variable])) {
        Write-Error "Missing $variable in $EnvFile"
    }
}

function Invoke-Gcloud {
    param([string[]]$GcloudArgs)
    & gcloud @GcloudArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "gcloud $($GcloudArgs[0]) failed" }
}

function Invoke-GcloudOptional {
    param([string[]]$GcloudArgs)
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & gcloud @GcloudArgs 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    [PSCustomObject]@{ ExitCode = $exitCode; Output = $output }
}

Invoke-Gcloud @("config", "set", "project", $ProjectId)
Invoke-Gcloud @("services", "enable", "secretmanager.googleapis.com", "run.googleapis.com")

$runtimeServiceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$runtimeCheck = Invoke-GcloudOptional @("iam", "service-accounts", "describe", $runtimeServiceAccount)
if ($runtimeCheck.ExitCode -ne 0) {
    Write-Host "==> Creating dedicated Cloud Run runtime identity" -ForegroundColor Cyan
    Invoke-Gcloud @("iam", "service-accounts", "create", $RuntimeServiceAccountName, "--display-name", "DND and Beyond Cloud Run runtime")
}

foreach ($variable in $secretMap.Keys) {
    $secretName = $secretMap[$variable]
    $secretCheck = Invoke-GcloudOptional @("secrets", "describe", $secretName)
    if ($secretCheck.ExitCode -ne 0) {
        Write-Host "==> Creating secret $secretName" -ForegroundColor Cyan
        Invoke-Gcloud @("secrets", "create", $secretName, "--replication-policy", "automatic")
    }

    $temporaryFile = New-TemporaryFile
    try {
        [System.IO.File]::WriteAllText(
            $temporaryFile.FullName,
            [string]$productionValues[$variable],
            [System.Text.UTF8Encoding]::new($false)
        )
        Invoke-Gcloud @("secrets", "versions", "add", $secretName, "--data-file", $temporaryFile.FullName)
    }
    finally {
        Remove-Item -LiteralPath $temporaryFile.FullName -Force -ErrorAction SilentlyContinue
    }

    Invoke-Gcloud @(
        "secrets", "add-iam-policy-binding", $secretName,
        "--member", "serviceAccount:$runtimeServiceAccount",
        "--role", "roles/secretmanager.secretAccessor"
    )
}

$secretBindings = ($secretMap.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value):latest" }) -join ","
$legacyEnvironmentNames = ($secretMap.Keys | ForEach-Object { [string]$_ }) -join ","
Write-Host "==> Switching Cloud Run to Secret Manager references" -ForegroundColor Cyan
Invoke-Gcloud @(
    "run", "services", "update", $ServiceName,
    "--region", $Region,
    "--service-account", $runtimeServiceAccount,
    "--remove-env-vars", $legacyEnvironmentNames,
    "--update-secrets", $secretBindings
)

Write-Host "DONE. Cloud Run now uses Secret Manager through $runtimeServiceAccount." -ForegroundColor Green
