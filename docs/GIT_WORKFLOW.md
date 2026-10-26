# Git development and release workflow

This is the user's standing repository workflow, established 26 October 2026.
It applies to application code, MCP, infrastructure, configuration, documentation
and future features. The [Git release Skill](../skills/git-release-workflow/SKILL.md)
provides the agent entry point; the root guide links both.

## Branches and worktrees

- **Main:** the assembled integration and release history. Make changes through
  feature branches and merge them; never edit source or commit fixes directly here.
- **Feature branches:** develop and validate one coherent change. Start new work
  from current main, unless deliberately continuing a documented development line.
  Retain the branches after merging so their history remains easy to inspect.
- **Baseline references:** preserve the selected original state independently of
  main. Main advances; a baseline branch or tag stays at its recorded commit.
- **Worktrees:** real directories holding checkouts. Removing an unused worktree
  does not delete its branch or committed history. Review uncommitted, untracked
  and ignored files before removal. Do not remove the primary/recovery checkout
  or private inputs merely to tidy the sidebar.

## Develop, validate and integrate

1. Inspect `git worktree list`, current status, remotes and scoped guidance. Use
   an isolated feature checkout when another directory holds unrelated changes.
2. Fetch current main and create a `codex/` feature branch. Commit changes there;
   keep credentials/runtime data out of Git. Record refactors in `REFACTOR_LOG.md`.
3. Run relevant local checks and review the complete diff against main. Push the
   feature branch and inspect its CI results. If existing work diverged, integrate
   current main into the feature/integration branch, resolve conflicts there and
   rerun affected checks. A clean merge alone does not prove compatibility.
4. In a clean main checkout, update main with `--ff-only`, then merge the validated
   feature using `--no-ff`. This preserves an explicit feature boundary even if a
   fast-forward would be possible. Do not delete the feature branch.
5. Push main normally and wait for required checks on the assembled revision.
   If checks fail, fix the cause on a branch and merge it; do not edit main or
   weaken checks merely to release.

Example commands; substitute the actual reviewed feature and checkout paths:

```bash
git fetch origin
git switch -c codex/feature-name origin/main
# Edit, validate, review, commit and push the feature branch.
git push -u origin codex/feature-name
# In a clean checkout reserved for main integration:
git switch main
git pull --ff-only origin main
git merge --no-ff codex/feature-name
git push origin main
```

PR merges may implement the same workflow when used; preserve the merge boundary
and retain the source branch. Do not squash away a deliberately recorded feature
boundary or rebase shared history during release preparation.

## Release from main

Deployments select an exact commit already pushed to `origin/main`. Usually select
the newly validated merge commit, record its full SHA, and use the service's release
runbook. Sakai: [release procedure](SAKAI_RELEASES.md). MCP:
[release procedure](MCP_RELEASES.md). Runtime start/stop, feature activation,
schema/data changes and old-release cleanup retain their separate authorization
requirements. A merge or push does not trigger an automatic deployment.

For Sakai:

```bash
./sakai deploy MAIN_COMMIT --check-only
./sakai deploy MAIN_COMMIT
```

Verify the installed commit, health and affected behavior. Record the source commit,
service/release ID, checks and rollback point. Different services may be on different
main commits when their code has not changed. Main's tip may later advance with
release evidence or unreleased work; do not infer the live revision from the tip.
Release evidence is also edited on a branch and merged into main.

## Reverting a feature

Revert through a new branch and a new release, preserving history. For a deliberate
`--no-ff` merge whose first parent is main:

```bash
git switch -c codex/revert-feature origin/main
git revert -m 1 FEATURE_MERGE_COMMIT
# Review dependencies, validate, push, merge this branch into main and release.
```

`-m 1` means retain the merge's first parent as the mainline. Inspect the parents
before choosing it. A revert is a new commit, not deletion of the original branch.
Later features may depend on the reverted feature; assess compatibility and make
coordinated changes where necessary. Git does not revert database records, schema,
uploads, secrets or live configuration. A VM artifact rollback is a separate
runtime recovery action and must be recorded against the source history.

## Existing development lines

The preserved baseline, completed auth branch and ongoing tool migration illustrate
this workflow. Main can include baseline plus auth, then later integrate tool work
while retaining auth. The tool branch predates that integration and is deliberately
a partial tree: merging it requires conflict/dependency review, not replacement of
main's files. See [worktree ownership and history](DEVELOPMENT_WORKTREES.md).
