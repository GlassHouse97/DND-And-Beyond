# Deploy DND and Beyond to Cloud Run using Secret Manager-backed configuration.
#
# One-time setup:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_cloud_secrets.ps1 -ProjectId your-project-id
#
# After setup, this script never reads or uploads local production credentials.

param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "us-east1",
    [string]$ServiceName = "dnd-and-beyond",
    [string]$RuntimeServiceAccountName = "dnd-and-beyond-runtime"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$runtimeServiceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$image = "$Region-docker.pkg.dev/$ProjectId/dnd-and-beyond/app"
$secretBindings = @(
    "DATABASE_URL=dnd-and-beyond-database-url:latest",
    "SMTP_HOST=dnd-and-beyond-smtp-host:latest",
    "SMTP_PORT=dnd-and-beyond-smtp-port:latest",
    "SMTP_USERNAME=dnd-and-beyond-smtp-username:latest",
    "SMTP_PASSWORD=dnd-and-beyond-smtp-password:latest",
    "SMTP_FROM=dnd-and-beyond-smtp-from:latest"
) -join ","

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

Write-Host "==> Configuring project $ProjectId" -ForegroundColor Cyan
Invoke-Gcloud @("config", "set", "project", $ProjectId)
Invoke-Gcloud @("services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com")

foreach ($secretName in @(
    "dnd-and-beyond-database-url",
    "dnd-and-beyond-smtp-host",
    "dnd-and-beyond-smtp-port",
    "dnd-and-beyond-smtp-username",
    "dnd-and-beyond-smtp-password",
    "dnd-and-beyond-smtp-from"
)) {
    $secretCheck = Invoke-GcloudOptional @("secrets", "describe", $secretName)
    if ($secretCheck.ExitCode -ne 0) {
        Write-Error "Missing Secret Manager secret '$secretName'. Run scripts\setup_cloud_secrets.ps1 first."
    }
}

$runtimeCheck = Invoke-GcloudOptional @("iam", "service-accounts", "describe", $runtimeServiceAccount)
if ($runtimeCheck.ExitCode -ne 0) {
    Write-Error "Missing runtime service account '$runtimeServiceAccount'. Run scripts\setup_cloud_secrets.ps1 first."
}

$repositoryCheck = Invoke-GcloudOptional @("artifacts", "repositories", "describe", "dnd-and-beyond", "--location", $Region)
if ($repositoryCheck.ExitCode -ne 0) {
    Write-Host "==> Creating Artifact Registry repository" -ForegroundColor Cyan
    Invoke-Gcloud @("artifacts", "repositories", "create", "dnd-and-beyond", "--repository-format", "docker", "--location", $Region)
}

$serviceCheck = Invoke-GcloudOptional @("run", "services", "describe", $ServiceName, "--region", $Region, "--format", "value(status.url)")
$serviceUrl = $serviceCheck.Output | Select-Object -First 1
$firstDeploy = $serviceCheck.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($serviceUrl)
if ($firstDeploy) {
    $serviceUrl = "http://localhost:8080"
    Write-Host "==> First deploy: bootstrap build (public URL not known yet)" -ForegroundColor Yellow
}

function Build-And-Deploy {
    param([string]$ApiUrl)
    Write-Host "==> Building image (API_URL=$ApiUrl)" -ForegroundColor Cyan
    Invoke-Gcloud @("builds", "submit", "--config", "cloudbuild.yaml", "--substitutions", "_API_URL=$ApiUrl,_IMAGE=$image")

    Write-Host "==> Deploying to Cloud Run with Secret Manager references" -ForegroundColor Cyan
    Invoke-Gcloud @(
        "run", "deploy", $ServiceName,
        "--image", $image,
        "--region", $Region,
        "--allow-unauthenticated",
        "--session-affinity",
        "--timeout", "3600",
        "--min-instances", "0",
        "--max-instances", "2",
        "--memory", "1Gi",
        "--service-account", $runtimeServiceAccount,
        "--update-env-vars", "APP_BASE_URL=$ApiUrl",
        "--update-secrets", $secretBindings
    )
}

Build-And-Deploy -ApiUrl $serviceUrl

if ($firstDeploy) {
    $serviceUrl = (& gcloud run services describe $ServiceName --region $Region --format "value(status.url)")
    if ([string]::IsNullOrWhiteSpace($serviceUrl)) { Write-Error "Could not read the deployed service URL" }
    Write-Host "==> Service created at $serviceUrl - rebuilding with the real URL baked in" -ForegroundColor Yellow
    Build-And-Deploy -ApiUrl $serviceUrl
}

Write-Host ""
Write-Host "DONE. Your app is live at: $serviceUrl" -ForegroundColor Green
