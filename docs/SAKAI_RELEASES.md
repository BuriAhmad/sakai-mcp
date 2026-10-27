# Releasing Sakai to the development VM

This procedure targets only `rg-sakai-mcp-dev/vm-sakai-dev`. A Git push runs checks but **does not deploy**. A release is an explicit choice of one pushed commit. The source must be `origin/main`; feature branches are merged and pushed before release. Follow [the Git workflow](GIT_WORKFLOW.md).

## First release checklist

1. Finish the Sakai change in `apps/sakai/`, commit it, and push it to the feature branch, validate it, then merge it into `main` and push `main`.
2. Wait for the repository and Sakai source GitHub checks to pass. CI validates the parent POM and compiles all Sakai modules; the release repeats the full Maven build on the VM. The package builds skip Java tests; CI subsequently runs the focused authentication/login suite. Run focused tests for other changed modules before treating their features as validated.
3. Confirm the change needs no database migration or irreversible runtime change. This release route backs up Tomcat application files, **not MySQL data**. Handle schema changes with a separate migration and database recovery plan.
4. Ensure Azure MySQL is `Ready` and the VM is running. If the environment is stopped, run `./sakai start` only when the user has explicitly requested or permitted allocation. The deploy command refuses to start the VM implicitly. Allow plenty of time before the VM's 19:00 Pakistan-time auto-shutdown.
5. Review the repository's [Dependabot alerts](https://github.com/BuriAhmad/sakai-mcp/security/dependabot) before any production use. Importing upstream Sakai brought a large existing dependency-alert backlog; this dev release workflow does not resolve it.

From the repo root on a Mac:

```bash
./sakai deploy HEAD --check-only
./sakai deploy HEAD
```

The deploy command accepts `HEAD` or a commit SHA. It refuses commits not pushed to the pushed `origin/main` history and refuses uncommitted Sakai/deployment changes. It opens SSH only to the current public IPv4 `/32`, sends an archive of the chosen commit, then builds it on the VM. The VM does not need a GitHub key or a Git clone for this path.

The VM stops Tomcat during the build because its 8 GiB RAM is insufficient to safely run Tomcat and the full Maven build together. It copies the current `webapps`, `components`, and `lib` directories into a staging Tomcat layout, deploys the new Maven output there, retains the original directories for rollback, and starts Tomcat. The command waits for the local portal and then checks public HTTPS. A failure after Tomcat is stopped triggers automatic code-file rollback and restart.

The VM build runs in a transient `sakai-release-RELEASE_ID.service` systemd unit.
The CLI polls the unit, verifies the release's `healthy` status and checks public
HTTPS. An SSH monitor disconnection does not cancel the VM job. If the CLI is
interrupted or monitoring times out, inspect the unit and release status before
starting another release; do not assume failure or start a competing build.

```bash
./sakai shell 'sudo journalctl -u sakai-release-RELEASE_ID.service --no-pager -n 50'
./sakai shell 'systemctl show sakai-release-RELEASE_ID.service --property=ActiveState --property=Result'
```

The existing VM-side lock, checksum, clean-source, staging, rollback and local
health checks remain in force. A failed unit is reported as failure; monitor
transport errors are retried rather than treated as successful deployment.

Build output and release state remain under `/opt/sakai-releases/RELEASE_ID/`; the selected commit is recorded in `/opt/sakai-releases/current`. The original `/opt/sakai-src` checkout is not overwritten; the source used for each build is in that release's `source/` directory. Runtime properties in `/opt/tomcat/sakai/local.properties`, the database, and user uploads are not copied into the Git repository or replaced by this procedure.

To inspect a build:

```bash
./sakai shell 'sudo tail -n 100 /opt/sakai-releases/RELEASE_ID/build.log'
./sakai shell 'sudo cat /opt/sakai-releases/current'
```

To restore the preceding application files after a successful release:

```bash
./sakai rollback RELEASE_ID
```

Only the current release can be rolled back by this command. It does not reverse database migrations or content changes made while the new code ran. Keep the release and its backup directories until the change has been exercised; cleanup is a separate, reviewed operation.

For the MCP development adapter, the current verified release and rollback ID are recorded in [`phase-8-release.md`](evidence/mcp/phase-8-release.md). The runtime-only MCP property block is separate from the code release; `configure-mcp-sakai.sh false ...` can disable that route when supplied the same verified non-secret metadata, followed by a guarded restart/release. A code rollback does not remove announcements already posted, Entra registrations/grants, or the property block. Repeat ordinary student/instructor login, bearer denial, own-data, cross-course, and write-permission checks after a Sakai MCP change.

Each full release can retain several gigabytes of build output and a roughly 2 GiB rollback copy on the VM's 64 GiB disk. Check free space with `./sakai shell 'df -h /opt; sudo du -sh /opt/sakai-releases/*'` before repeated releases. Do not delete the current release or its backup to make room; review and remove only older, no-longer-needed releases in a separate maintenance step.

## Manual GitHub release

The [Deploy Sakai to development VM](https://github.com/BuriAhmad/sakai-mcp/actions/workflows/deploy-sakai.yml) workflow runs only when manually started from `main`. Enter the full 40-character commit SHA and choose `check-only` first; then choose `deploy`. Its `sakai-dev` environment is limited to the `main` branch. Starting the workflow is the manual release gate; the environment has no separate required-reviewer approval rule. The workflow uses a GitHub-federated Azure identity, a dedicated VM SSH key stored as an environment secret, and temporarily changes the same SSH rule to the runner's `/32`. It restores the prior rule when the job ends. If a runner is interrupted before cleanup, `./sakai open-ssh` restores access from your Mac.

GitHub's Azure identity has Reader access to this resource group, VM Contributor access to this one VM, and Network Contributor access to this one NSG. It does not receive your Mac's personal SSH key. The VM key can be revoked by removing the `sakai-mcp-github-deploy` entry from `/home/sakaiadmin/.ssh/authorized_keys` and deleting the `SAKAI_DEPLOY_SSH_KEY` environment secret.

The workflow does not automatically start MySQL, run database migrations, or deploy on every push. This is deliberately a manual dev-VM release; do not treat a 200 response at `/portal` as proof that every Sakai feature is healthy. Exercise the affected feature, login, and uploads after each meaningful change.

## Main-only release policy

All new releases select an exact pushed commit on `origin/main`. Implement and
validate changes on a feature branch, retain it, merge with `--no-ff`, then push
main and select its merge commit. See [the Git workflow](GIT_WORKFLOW.md) and
[the Git release Skill](../skills/git-release-workflow/SKILL.md).

The former `--branch` exception was used for the dated auth development releases.
It was retired on 26 October 2026 at the user's request. Historical release
records retain their original commands; those are execution history, not current
instructions. The CLI rejects the old option. The durable VM unit, lock, checksum,
staging, backup, rollback and health checks remain unchanged.
