# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

# Housekeeping for every git repository directly below a folder:
#   1. git fetch --all --prune, then git pull --ff-only (if the branch has an upstream)
#   2. delete local branches already merged into the default branch (git branch -d)
#   3. git gc
# Usage: Update-GitRepos.ps1 [-Root <folder>] [-WhatIf]

[CmdletBinding(SupportsShouldProcess)]
param(
    # Folder whose immediate subdirectories are scanned for repositories.
    [string]$Root = (Get-Location).Path
)

# Never delete these, even when merged.
$protected = @('main', 'master', 'develop')

$failed = @()
$repos  = Get-ChildItem -LiteralPath $Root -Directory | Where-Object { Test-Path (Join-Path $_.FullName '.git') }
if (-not $repos) { Write-Host "No git repositories found below $Root"; return }

foreach ($repo in $repos) {
    $dir = $repo.FullName
    Write-Host ''
    Write-Host "=== $($repo.Name) ===" -ForegroundColor Cyan
    $ok = $true

    # Remote default branch, e.g. origin/main; 'HEAD' if origin/HEAD is not set.
    $base = git -C $dir symbolic-ref --short refs/remotes/origin/HEAD 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $base) { $base = 'HEAD' }
    $default = $base -replace '^origin/', ''
    $keep = $protected + $default

    # --- 1. fetch + pull ---------------------------------------------------
    if ($PSCmdlet.ShouldProcess($repo.Name, 'git fetch + pull')) {
        git -C $dir fetch --all --prune
        if ($LASTEXITCODE -ne 0) { $ok = $false }

        git -C $dir rev-parse --abbrev-ref '@{u}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            git -C $dir pull --ff-only
            if ($LASTEXITCODE -ne 0) { $ok = $false; Write-Warning 'pull failed (diverged or conflicting local changes?)' }
        } else {
            Write-Host 'current branch has no upstream - pull skipped' -ForegroundColor DarkGray
        }

        # The pull only moves the checked-out branch. If a feature branch is checked
        # out, fast-forward the local default branch to its upstream as well.
        $worktree = git -C $dir for-each-ref --format='%(worktreepath)' "refs/heads/$default"
        $upstream = git -C $dir rev-parse --abbrev-ref "$default@{u}" 2>$null
        if ($default -ne 'HEAD' -and -not $worktree -and $upstream -and $LASTEXITCODE -eq 0) {
            # Fetching from the local repository into a branch refuses non-fast-forward updates.
            git -C $dir fetch --quiet . "refs/remotes/${upstream}:refs/heads/$default"
            if ($LASTEXITCODE -ne 0) { $ok = $false; Write-Warning "$default could not be fast-forwarded to $upstream (diverged?)" }
        }
    }

    # --- 2. delete merged local branches -----------------------------------
    # "Merged" means merged into the remote default branch (origin/HEAD), so this
    # also works while a feature branch is checked out.

    # worktreepath is non-empty for the current branch and any other checked-out worktree.
    $merged = git -C $dir for-each-ref --merged $base --format='%(refname:short)|%(worktreepath)' refs/heads/
    foreach ($line in $merged) {
        $name, $worktree = $line -split '\|', 2
        if ($worktree -or $keep -contains $name) { continue }
        if ($PSCmdlet.ShouldProcess("$($repo.Name): $name", 'git branch -d')) {
            git -C $dir branch -d $name
            if ($LASTEXITCODE -ne 0) { $ok = $false }
        }
    }

    # --- 3. gc -------------------------------------------------------------
    if ($PSCmdlet.ShouldProcess($repo.Name, 'git gc')) {
        git -C $dir gc --quiet
        if ($LASTEXITCODE -ne 0) { $ok = $false }
    }

    if (-not $ok) { $failed += $repo.Name }
}

Write-Host ''
Write-Host "Done: $($repos.Count) repositories." -ForegroundColor Green
if ($failed) { Write-Host "With errors: $($failed -join ', ')" -ForegroundColor Yellow }
