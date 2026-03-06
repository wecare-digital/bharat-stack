# Sync shared Wix Velo backend code to both repos
# Run from the stack.wecare.digital repo root
#
# Usage: .\shared\wix-velo\sync.ps1
#
# This copies shared backend files to:
#   1. store/src/backend/ (base repo reference copy)
#   2. ../store.wecare.digital/src/backend/ (Wix live repo)

$ErrorActionPreference = "Stop"

$SharedDir = "$PSScriptRoot\backend"
$BaseTarget = "store\src\backend"
$WixTarget = "..\store.wecare.digital\src\backend"

# Files to sync (only backend files that are shared)
$SyncFiles = @(
    "orderId.web.js",
    "events.js"
)

Write-Host "=== Wix Velo Sync ===" -ForegroundColor Cyan
Write-Host ""

foreach ($file in $SyncFiles) {
    $src = Join-Path $SharedDir $file
    if (-not (Test-Path $src)) {
        Write-Host "  SKIP: $file (not found in shared/)" -ForegroundColor Yellow
        continue
    }

    # Copy to base repo reference
    $dst1 = Join-Path $BaseTarget $file
    Copy-Item $src $dst1 -Force
    Write-Host "  OK: $file -> $BaseTarget" -ForegroundColor Green

    # Copy to Wix live repo
    if (Test-Path (Split-Path $WixTarget)) {
        $dst2 = Join-Path $WixTarget $file
        Copy-Item $src $dst2 -Force
        Write-Host "  OK: $file -> $WixTarget" -ForegroundColor Green
    } else {
        Write-Host "  SKIP: $file -> $WixTarget (repo not cloned)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Done. Remember to commit + push BOTH repos:" -ForegroundColor Cyan
Write-Host "  1. git add -A && git commit -m 'sync velo code' && git push origin base" -ForegroundColor White
Write-Host "  2. git -C ../store.wecare.digital add -A && git -C ../store.wecare.digital commit -m 'sync velo code' && git -C ../store.wecare.digital push origin main" -ForegroundColor White
