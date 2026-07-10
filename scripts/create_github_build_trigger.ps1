# Creates the Cloud Build deployer identity and the main-branch GitHub trigger.
# The first run creates a Cloud Build GitHub connection and prints an OAuth URL.
# Complete that one browser authorization, then re-run this script.

param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$ConnectionRegion = "us-central1",
    [string]$ConnectionName = "dnd-and-beyond-github",
    [string]$RepositoryName = "dnd-and-beyond",
    [string]$RepositoryOwner = "GlassHouse97",
    [string]$GitHubRepository = "DND-And-Beyond",
    [string]$TriggerName = "dnd-and-beyond-main",
    [string]$RuntimeServiceAccountName = "dnd-and-beyond-runtime",
    [string]$DeployerServiceAccountName = "dnd-and-beyond-deployer"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

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
Invoke-Gcloud @("services", "enable", "cloudbuild.googleapis.com", "secretmanager.googleapis.com", "run.googleapis.com", "artifactregistry.googleapis.com")

$projectNumber = (& gcloud projects describe $ProjectId --format "value(projectNumber)").Trim()
if ([string]::IsNullOrWhiteSpace($projectNumber)) { Write-Error "Could not read the project number." }
$runtimeServiceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$deployerServiceAccount = "$DeployerServiceAccountName@$ProjectId.iam.gserviceaccount.com"

$deployerCheck = Invoke-GcloudOptional @("iam", "service-accounts", "describe", $deployerServiceAccount)
if ($deployerCheck.ExitCode -ne 0) {
    Write-Host "==> Creating dedicated Cloud Build deployer identity" -ForegroundColor Cyan
    Invoke-Gcloud @("iam", "service-accounts", "create", $DeployerServiceAccountName, "--display-name", "DND and Beyond Cloud Build deployer")
}

foreach ($role in @(
    "roles/cloudbuild.builds.builder",
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/secretmanager.viewer",
    "roles/logging.logWriter"
)) {
    Invoke-Gcloud @("projects", "add-iam-policy-binding", $ProjectId, "--member", "serviceAccount:$deployerServiceAccount", "--role", $role, "--quiet")
}
Invoke-Gcloud @(
    "iam", "service-accounts", "add-iam-policy-binding", $runtimeServiceAccount,
    "--member", "serviceAccount:$deployerServiceAccount",
    "--role", "roles/iam.serviceAccountUser",
    "--quiet"
)

# Cloud Build needs this only to store and manage its own GitHub OAuth token.
$cloudBuildServiceAgent = "service-$projectNumber@gcp-sa-cloudbuild.iam.gserviceaccount.com"
Invoke-Gcloud @("projects", "add-iam-policy-binding", $ProjectId, "--member", "serviceAccount:$cloudBuildServiceAgent", "--role", "roles/secretmanager.admin", "--quiet")

$connectionCheck = Invoke-GcloudOptional @("builds", "connections", "describe", $ConnectionName, "--region", $ConnectionRegion, "--format", "value(installationState.stage)")
if ($connectionCheck.ExitCode -ne 0) {
    Write-Host "==> Creating the Cloud Build GitHub connection" -ForegroundColor Cyan
    & gcloud builds connections create github $ConnectionName --region $ConnectionRegion
    if ($LASTEXITCODE -ne 0) { Write-Error "Cloud Build GitHub connection creation failed." }
    Write-Host "Complete the GitHub authorization URL printed above, install the Cloud Build GitHub App for $RepositoryOwner/$GitHubRepository, then run this script again." -ForegroundColor Yellow
    exit 2
}
if ((($connectionCheck.Output | Select-Object -First 1).Trim()) -ne "COMPLETE") {
    Write-Host "The GitHub connection is not complete yet. Run: gcloud builds connections describe $ConnectionName --region $ConnectionRegion" -ForegroundColor Yellow
    exit 2
}

$repositoryResource = "projects/$ProjectId/locations/$ConnectionRegion/connections/$ConnectionName/repositories/$RepositoryName"
$repositoryCheck = Invoke-GcloudOptional @("builds", "repositories", "describe", $RepositoryName, "--connection", $ConnectionName, "--region", $ConnectionRegion)
if ($repositoryCheck.ExitCode -ne 0) {
    Invoke-Gcloud @("builds", "repositories", "create", $RepositoryName, "--remote-uri", "https://github.com/$RepositoryOwner/$GitHubRepository.git", "--connection", $ConnectionName, "--region", $ConnectionRegion)
}

$triggerCheck = Invoke-GcloudOptional @("builds", "triggers", "describe", $TriggerName, "--region", $ConnectionRegion)
if ($triggerCheck.ExitCode -eq 0) {
    Write-Host "Trigger $TriggerName already exists. No changes were made." -ForegroundColor Green
    exit 0
}

Invoke-Gcloud @(
    "builds", "triggers", "create", "github",
    "--name", $TriggerName,
    "--description", "Deploy DND and Beyond when main is updated",
    "--repository", $repositoryResource,
    "--branch-pattern", "^main$",
    "--build-config", "cloudbuild.github.yaml",
    "--service-account", "projects/$ProjectId/serviceAccounts/$deployerServiceAccount",
    "--region", $ConnectionRegion
)

Write-Host "DONE. Every push to main now builds and deploys DND and Beyond." -ForegroundColor Green
