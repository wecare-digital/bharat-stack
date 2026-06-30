<#
  upgrade-latest.ps1  —  Move ALL frontend/backend npm deps to their latest versions.
  Run on a machine WITH npm network access (local dev or CI). Idempotent.

  Usage:
    pwsh ./upgrade-latest.ps1            # bump everything to @latest, audit fix, build, test
    pwsh ./upgrade-latest.ps1 -Force     # also run `npm audit fix --force` (may pull new majors)
    pwsh ./upgrade-latest.ps1 -NoTest    # skip vitest

  What it does NOT do: commit, push, or deploy. Those are explicit manual steps (see docs/UPGRADE_TO_LATEST.md).
#>
param(
    [switch]$Force,
    [switch]$NoTest
)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$PROD = @(
    '@aws-amplify/backend','@aws-amplify/ui-react',
    '@aws-sdk/client-bedrock','@aws-sdk/client-bedrock-runtime',
    '@capacitor/android','@capacitor/app','@capacitor/browser','@capacitor/cli','@capacitor/core',
    '@capacitor/haptics','@capacitor/ios','@capacitor/keyboard','@capacitor/push-notifications',
    '@capacitor/splash-screen','@capacitor/status-bar',
    'aws-amplify','flag-icons','next','react','react-dom','react-router-dom'
)
$DEV = @(
    '@aws-amplify/backend-cli','@aws-amplify/backend-data','@aws-amplify/data-construct',
    '@aws-amplify/graphql-schema-generator','@testing-library/jest-dom','@testing-library/react',
    '@types/node','@types/react','@types/react-dom','@vitejs/plugin-react','jsdom','typescript','vitest'
)

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Step '0. Safety: backup manifests + create upgrade branch'
Copy-Item package.json "package.json.bak" -Force
Copy-Item package-lock.json "package-lock.json.bak" -Force
$branch = 'chore/deps-latest'
git rev-parse --verify $branch *> $null
if ($LASTEXITCODE -eq 0) { git checkout $branch } else { git checkout -b $branch }

Step '1. Bump production dependencies to @latest'
npm install --save ($PROD | ForEach-Object { "$_@latest" })

Step '2. Bump dev dependencies to @latest'
npm install --save-dev ($DEV | ForEach-Object { "$_@latest" })

Step '3. Audit fix (transitive vulns)'
npm audit fix
if ($Force) { Step '3b. Audit fix --force (may pull new majors)'; npm audit fix --force }

Step '4. Dedupe + clean install from refreshed lockfile'
npm dedupe
npm install

Step '5. Build (verifies nothing broke)'
npm run build

if (-not $NoTest) { Step '6. Tests'; npm test }

Step 'DONE'
Write-Host 'Review changes:  git diff package.json' -ForegroundColor Green
Write-Host 'Residual vulns:  npm audit' -ForegroundColor Green
Write-Host 'Backups left at package.json.bak / package-lock.json.bak (delete once happy).' -ForegroundColor Green
Write-Host 'Next: commit, push, then deploy (see docs/UPGRADE_TO_LATEST.md).' -ForegroundColor Green
