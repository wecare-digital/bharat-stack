<#
.SYNOPSIS
  Sync shared Wix Velo backend code between the stack repo and the live Wix repo.

.DESCRIPTION
  Keeps three locations in agreement for the files listed in $SyncFiles:

    1. shared/wix-velo/backend/          <- source of truth in this repo
    2. store/src/backend/                <- reference copy in this repo
    3. <WixRepo>/src/backend/            <- wecare-digital/store (branch main, private)
                                            connected to Wix Git Integration; a push
                                            AUTO-DEPLOYS to the live Wix site.

  Because location 3 auto-deploys, this script is deliberately fail-safe:

    * It never overwrites a target that has diverged from the source unless you
      pass -Force. The previous version of this script copied unconditionally,
      which would have reverted store/src/backend/events.js from 379 lines to a
      stale 156-line copy and deleted sendOrderNotifications() plus the Sinch
      SMS/RCS order-notification wiring from the live site.
    * -DryRun reports what would change and writes nothing.
    * -Pull reconciles in the opposite direction (target -> shared) so that work
      done directly in a repo can be promoted into the source of truth.

.PARAMETER DryRun
  Report differences only. No files are written.

.PARAMETER Force
  Overwrite targets even when they have diverged from the source.

.PARAMETER Pull
  Copy target -> shared instead of shared -> target. Use to promote changes that
  were made directly in store/src/backend or in the Wix repo.

.PARAMETER WixRepo
  Path to the cloned wecaredigital/store.wecare.digital repo.
  Defaults to a sibling of this repo.

.EXAMPLE
  .\shared\wix-velo\sync.ps1 -DryRun
.EXAMPLE
  .\shared\wix-velo\sync.ps1
.EXAMPLE
  .\shared\wix-velo\sync.ps1 -Pull -DryRun
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$Pull,
    [string]$WixRepo
)

$ErrorActionPreference = 'Stop'

$SharedDir = Join-Path $PSScriptRoot 'backend'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$StackTarget = Join-Path $RepoRoot 'store\src\backend'

if (-not $WixRepo -or [string]::IsNullOrWhiteSpace($WixRepo)) {
    # wecare-digital/store, cloned as a sibling of this repo.
    $WixRepo = Join-Path (Split-Path $RepoRoot -Parent) 'store'
}
$WixTarget = Join-Path $WixRepo 'src\backend'

# Files that are genuinely shared between the two repos.
#
# Deliberately NOT synced:
#   http-functions.js  - the Wix repo holds a much larger SEO/sitemap/RSS/AI-feed
#                        version. Copying the stack repo's smaller version over it
#                        would delete live functionality.
#   src/pages/*.js     - page files carry Wix-internal element IDs and can only be
#                        created/renamed from the Wix Editor.
$SyncFiles = @(
    'orderId.web.js',
    'orderId-helpers.js',
    'events.js',
    'google-services.web.js'
)

function Get-Sha([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    return (Get-FileHash $path -Algorithm SHA256).Hash
}

$targets = @(
    [pscustomobject]@{ Name = 'stack repo (store/src/backend)'; Path = $StackTarget; Present = (Test-Path $StackTarget) }
    [pscustomobject]@{ Name = 'wix live repo (auto-deploys!)'; Path = $WixTarget; Present = (Test-Path $WixTarget) }
)

Write-Host ''
Write-Host '=== Wix Velo Sync ===' -ForegroundColor Cyan
Write-Host ("mode      : " + $(if ($Pull) { 'PULL (target -> shared)' } else { 'PUSH (shared -> target)' })) -ForegroundColor Gray
Write-Host ("dry run   : $DryRun") -ForegroundColor Gray
Write-Host ("force     : $Force") -ForegroundColor Gray
Write-Host ("shared    : $SharedDir") -ForegroundColor Gray
foreach ($t in $targets) {
    $mark = if ($t.Present) { 'OK' } else { 'MISSING' }
    $col = if ($t.Present) { 'Gray' } else { 'Yellow' }
    Write-Host ("target    : $($t.Path)  [$mark]  $($t.Name)") -ForegroundColor $col
}
Write-Host ''

$changed = 0
$blocked = 0
$identical = 0

foreach ($file in $SyncFiles) {
    $sharedPath = Join-Path $SharedDir $file
    Write-Host ("-- $file") -ForegroundColor White

    if (-not $Pull -and -not (Test-Path $sharedPath)) {
        Write-Host '     SKIP: not present in shared/' -ForegroundColor Yellow
        continue
    }

    foreach ($t in $targets) {
        if (-not $t.Present) {
            Write-Host ("     SKIP [$($t.Name)]: path not available") -ForegroundColor DarkYellow
            continue
        }

        $targetPath = Join-Path $t.Path $file
        $src = if ($Pull) { $targetPath } else { $sharedPath }
        $dst = if ($Pull) { $sharedPath } else { $targetPath }

        $srcHash = Get-Sha $src
        $dstHash = Get-Sha $dst

        if (-not $srcHash) {
            Write-Host ("     SKIP [$($t.Name)]: source missing ($src)") -ForegroundColor DarkYellow
            continue
        }

        if ($srcHash -eq $dstHash) {
            $identical++
            Write-Host ("     SAME [$($t.Name)]") -ForegroundColor DarkGray
            continue
        }

        $srcLen = (Get-Item $src).Length
        $dstLen = if ($dstHash) { (Get-Item $dst).Length } else { 0 }

        # Divergence guard: destination exists, differs, and is larger than the
        # source. That is the exact shape of the events.js incident, so refuse.
        if ($dstHash -and -not $Force -and $dstLen -gt $srcLen) {
            $blocked++
            Write-Host ("     BLOCKED [$($t.Name)]: destination is LARGER than source " +
                        "($dstLen vs $srcLen bytes).") -ForegroundColor Red
            Write-Host '              Refusing to overwrite - this would delete code.' -ForegroundColor Red
            Write-Host '              Inspect the diff, then re-run with -Pull (to promote the' -ForegroundColor Red
            Write-Host '              destination) or -Force (to genuinely overwrite it).' -ForegroundColor Red
            continue
        }

        if ($DryRun) {
            $changed++
            Write-Host ("     WOULD COPY [$($t.Name)]: $srcLen bytes -> replaces $dstLen bytes") -ForegroundColor Yellow
            continue
        }

        Copy-Item $src $dst -Force
        $changed++
        Write-Host ("     COPIED [$($t.Name)]: $srcLen bytes -> $dst") -ForegroundColor Green
    }
}

Write-Host ''
Write-Host '=== Summary ===' -ForegroundColor Cyan
Write-Host ("  identical : $identical") -ForegroundColor Gray
Write-Host ("  changed   : $changed") -ForegroundColor $(if ($changed) { 'Green' } else { 'Gray' })
Write-Host ("  blocked   : $blocked") -ForegroundColor $(if ($blocked) { 'Red' } else { 'Gray' })

if ($blocked -gt 0) {
    Write-Host ''
    Write-Host 'Resolve blocked files before pushing. Do NOT push a partial sync to the' -ForegroundColor Red
    Write-Host 'Wix repo - it auto-deploys to the live site.' -ForegroundColor Red
    exit 1
}

if (-not $DryRun -and $changed -gt 0) {
    Write-Host ''
    Write-Host 'Next steps - commit and push BOTH repos:' -ForegroundColor Cyan
    Write-Host '  git add -A; git commit -m "sync velo code"; git push origin stack' -ForegroundColor White
    Write-Host ("  git -C `"$WixRepo`" add -A; git -C `"$WixRepo`" commit -m " +
                '"sync velo code"; git -C "' + $WixRepo + '" push origin main') -ForegroundColor White
    Write-Host ''
    Write-Host 'The second push auto-deploys to the live Wix site. Verify the site afterwards.' -ForegroundColor Yellow
}
