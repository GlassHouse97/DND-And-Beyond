# Deploys DND and Beyond to Google Cloud Run.
#
# Prerequisites (one-time):
#   1. Install the gcloud CLI and run: gcloud auth login
#   2. Create a Google Cloud project (console.cloud.google.com) with billing enabled
#      (usage at friends-group scale stays inside the free tier).
#   3. Copy .env.production.example to .env.production and fill it in.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\deploy_cloudrun.ps1 -ProjectId your-project-id
#
# The frontend needs the app's public URL baked in at build time, so the first
# ever deploy builds twice: once to create the service and learn its URL, then
# again with that URL compiled in. Later deploys build once.

param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "us-east1",
    [string]$ServiceName = "dnd-and-beyond"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# --- read .env.production ---------------------------------------------------
$envFile = Join-Path $repoRoot ".env.production"
if (-not (Test-Path $envFile)) {
    Write-Error "Missing .env.production - copy .env.production.example and fill it in."
}
$prodVars = @{}
foreach ($line in Get-Content $envFile) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $name, $value = $trimmed -split "=", 2
    $prodVars[$name.Trim()] = $value.Trim()
}
foreach ($required in @("DATABASE_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")) {
    if (-not $prodVars.ContainsKey($required) -or $prodVars[$required] -eq "") {
        Write-Error "Missing $required in .env.production"
    }
}

$image = "$Region-docker.pkg.dev/$ProjectId/dnd-and-beyond/app"

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
    [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

Write-Host "==> Configuring project $ProjectId" -ForegroundColor Cyan
Invoke-Gcloud @("config", "set", "project", $ProjectId)
Invoke-Gcloud @("services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com")

# Create the image repository if it does not exist yet.
$repositoryCheck = Invoke-GcloudOptional @("artifacts", "repositories", "describe", "dnd-and-beyond", "--location", $Region)
if ($repositoryCheck.ExitCode -ne 0) {
    Write-Host "==> Creating Artifact Registry repository" -ForegroundColor Cyan
    Invoke-Gcloud @("artifacts", "repositories", "create", "dnd-and-beyond", "--repository-format", "docker", "--location", $Region)
}

# If the service already exists we know its URL and can build correctly once.
$serviceCheck = Invoke-GcloudOptional @("run", "services", "describe", $ServiceName, "--region", $Region, "--format", "value(status.url)")
$serviceUrl = $serviceCheck.Output | Select-Object -First 1
if ($serviceCheck.ExitCode -ne 0) { $serviceUrl = "" }
$firstDeploy = [string]::IsNullOrWhiteSpace($serviceUrl)
if ($firstDeploy) {
    $serviceUrl = "http://localhost:8080"  # placeholder for the bootstrap build
    Write-Host "==> First deploy: bootstrap build (public URL not known yet)" -ForegroundColor Yellow
}

function Build-And-Deploy {
    param([string]$ApiUrl)
    Write-Host "==> Building image (API_URL=$ApiUrl)" -ForegroundColor Cyan
    Invoke-Gcloud @("builds", "submit", "--config", "cloudbuild.yaml", "--substitutions", "_API_URL=$ApiUrl,_IMAGE=$image")

    Write-Host "==> Deploying to Cloud Run" -ForegroundColor Cyan
    $envPairs = @(
        "DATABASE_URL=$($prodVars['DATABASE_URL'])",
        "APP_BASE_URL=$ApiUrl",
        "SMTP_HOST=$($prodVars['SMTP_HOST'])",
        "SMTP_PORT=$($prodVars['SMTP_PORT'])",
        "SMTP_USERNAME=$($prodVars['SMTP_USERNAME'])",
        "SMTP_PASSWORD=$($prodVars['SMTP_PASSWORD'])",
        "SMTP_FROM=$($prodVars['SMTP_FROM'])"
    )
    # ^ delimiter because DATABASE_URL contains commas-safe characters like '=' and '&'
    $joined = $envPairs -join "^"
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
        "--set-env-vars", "^^^$joined"
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
Write-Host "Share that link with your players."
