<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Git maintenance -- TODO

- [ ] **Keep forks current (`-SyncForks`).** The script pulls from `origin` only, so a fork's
      default branch falls behind its original and nothing reports it (seen on 2026-10-26:
      `kotlinx.serialization` master 136 commits behind, `VeraCrypt` master 42, `llama.cpp`
      master 174). For a repository with an `upstream` remote, an opt-in switch would:
      fetch `upstream`, fast-forward the local default branch to `upstream/<default>` (the same
      `git fetch . <ref>:<branch>` refusal of non-fast-forward updates the script already uses)
      and push it to `origin` without force. A default branch with commits of its own is
      reported and left alone, and so is every other branch -- a PR branch that is behind its
      original is rebased by hand, not by this script. Without the switch, report how far each
      default branch is behind `upstream`, so the drift is at least visible.
