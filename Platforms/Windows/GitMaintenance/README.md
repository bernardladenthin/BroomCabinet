<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Git maintenance

Housekeeping for a folder full of git clones. For every repository directly
below the root folder, `Update-GitRepos.ps1`:

1. `git fetch --all --prune`, then `git pull --ff-only` (skipped when the
   current branch has no upstream); if a feature branch is checked out, the
   local default branch is fast-forwarded to its upstream as well
2. deletes local branches that are already merged into the remote default
   branch (`origin/HEAD`) with `git branch -d`
3. runs `git gc`

A failing repository does not stop the run; the ones with errors are listed at
the end.

| File | Purpose |
|------|---------|
| `Update-GitRepos.ps1` | The script (Windows PowerShell 5.1 or PowerShell 7). |
| `run_UpdateGitRepos.bat` | Double-click launcher; bypasses the execution policy for this one file. |

## Usage

```bat
run_UpdateGitRepos.bat                       all repos next to this BroomCabinet clone
run_UpdateGitRepos.bat -WhatIf               dry run: show what would happen
run_UpdateGitRepos.bat -Root D:\src          a different folder
```

Or directly from PowerShell, in the folder that holds the clones:

```powershell
powershell -ExecutionPolicy Bypass -File <path>\Update-GitRepos.ps1 -WhatIf
```

`-Root` defaults to the current directory when the `.ps1` is called directly.

## Details worth knowing

* **Pull is fast-forward only.** A branch that diverged from its upstream is not
  merged or rebased — the pull fails, is reported, and you sort it out by hand.
  The same applies to the default branch when it is updated in the background.
* **"Merged" means merged into `origin/HEAD`**, not into the checked-out
  branch, so the cleanup is correct even while a feature branch is checked out.
  Without `origin/HEAD` it falls back to `HEAD`; set it with
  `git remote set-head origin --auto`.
* **Never deleted:** `main`, `master`, `develop`, the default branch, the
  current branch and branches checked out in another worktree.
* **`-d`, not `-D`.** Git itself refuses to delete a branch it does not
  consider merged, so nothing unmerged is lost. Squash- or rebase-merged PR
  branches are therefore *not* removed (their commits are not in the default
  branch) — delete those manually with `git branch -D` once you are sure.
