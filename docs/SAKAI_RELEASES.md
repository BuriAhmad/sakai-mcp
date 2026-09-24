# Releasing Sakai to the development VM

This procedure targets only `rg-sakai-mcp-dev/vm-sakai-dev`. A Git push runs checks but **does not deploy**. A release is an explicit choice of one commit on `origin/main`.

## First release checklist

1. Finish the Sakai change in `apps/sakai/`, commit it, and push it to `main`.
2. Wait for the repository and Sakai source GitHub checks to pass. The current Sakai check validates the parent POM; the release itself performs the full Maven build with tests skipped. Add focused tests for changed modules before treating a change as validated.
3. Confirm the change needs no database migration or irreversible runtime change. This release route backs up Tomcat application files, **not MySQL data**. Handle schema changes with a separate migration and database recovery plan.
4. Ensure Azure MySQL is `Ready`. If the environment is stopped, run `./sakai start` first. Allow plenty of time before the VM's 19:00 Pakistan-time auto-shutdown.

From the repo root on a Mac:

```bash
./sakai deploy HEAD --check-only
./sakai deploy HEAD
```

The deploy command accepts `HEAD` or a commit SHA. It refuses commits not pushed to `origin/main` and refuses uncommitted Sakai/deployment changes. It opens SSH only to the current public IPv4 `/32`, sends an archive of the chosen commit, then builds it on the VM. The VM does not need a GitHub key or a Git clone for this path.

The VM stops Tomcat during the build because its 8 GiB RAM is insufficient to safely run Tomcat and the full Maven build together. It copies the current `webapps`, `components`, and `lib` directories into a staging Tomcat layout, deploys the new Maven output there, retains the original directories for rollback, and starts Tomcat. The command waits for the local portal and then checks public HTTPS. A failure after Tomcat is stopped triggers automatic code-file rollback and restart.

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

## Manual GitHub release

The [Deploy Sakai to development VM](https://github.com/BuriAhmad/sakai-mcp/actions/workflows/deploy-sakai.yml) workflow runs only when manually started from `main`. Enter the full 40-character commit SHA and choose `check-only` first; then choose `deploy`. Its `sakai-dev` environment is limited to the `main` branch. The workflow uses a GitHub-federated Azure identity, a dedicated VM SSH key stored as an environment secret, and temporarily changes the same SSH rule to the runner's `/32`. It restores the prior rule when the job ends. If a runner is interrupted before cleanup, `./sakai open-ssh` restores access from your Mac.

GitHub's Azure identity has Reader access to this resource group, VM Contributor access to this one VM, and Network Contributor access to this one NSG. It does not receive your Mac's personal SSH key. The VM key can be revoked by removing the `sakai-mcp-github-deploy` entry from `/home/sakaiadmin/.ssh/authorized_keys` and deleting the `SAKAI_DEPLOY_SSH_KEY` environment secret.

The workflow does not automatically start MySQL, run database migrations, or deploy on every push. This is deliberately a manual dev-VM release; do not treat a 200 response at `/portal` as proof that every Sakai feature is healthy. Exercise the affected feature, login, and uploads after each meaningful change.
