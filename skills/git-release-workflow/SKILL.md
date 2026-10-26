---
name: git-release-workflow
description: Follow this repository's feature-branch development, main integration, exact-commit release and revert workflow when changing code, integrating work or preparing a deployment.
---

# Git release workflow

Use [the repository Git workflow](../../docs/GIT_WORKFLOW.md) as the procedure.

- Develop and validate all changes, including release documentation and fixes,
  on a feature branch. Main receives reviewed merges; never edit source on main.
- Inspect worktrees and their ownership before choosing a checkout. Preserve
  uncommitted and ignored private files. A worktree is a directory, not a branch.
- Integrate the reviewed branch into current main with `--no-ff`, retain the
  feature branch and baseline references, and push without rewriting history.
  Resolve integration conflicts on the feature/integration branch and rerun
  affected checks before merging. Preserve already integrated features.
- Release only an exact pushed commit on `origin/main`, after required checks.
  A push alone does not authorize deployment, starts, configuration activation,
  data/schema changes or cleanup. Check existing user authorization and the
  relevant service release runbook before changing runtime state.
- Record the selected Git commit and actual runtime release separately; main can
  contain newer documentation or unreleased changes. Verify the deployed revision.
- Revert on a new branch, then validate, merge and release through main. Use the
  merge's main parent deliberately. Review dependent features and data/configuration
  effects; Git rollback alone cannot undo runtime data or configuration changes.

Do not substitute a tool-only or other partial development tree for the assembled
main application. Do not force-push main, delete feature/baseline branches or remove
worktrees as an incidental release step.
