# Deployment paths

- `infra/` defines the Azure development resources; see `infra/README.md`.
- `configure-vm.sh`, `configure-sakai.sh`, and `deploy-sakai.sh` document the **original Sakai 25.2 bootstrap**. `deploy-sakai.sh` intentionally refuses a modified source checkout.
- `release-sakai-vm.sh` is the guarded, code-only release and rollback procedure for later commits. Do not invoke it by hand; use the root `./sakai deploy COMMIT` and `./sakai rollback RELEASE_ID` commands, or the manual GitHub Actions deployment workflow.

Read [the release runbook](../docs/SAKAI_RELEASES.md) before a first release. The release script stops Tomcat for the build, keeps a rollback copy of application directories, and does not alter the database, uploads, or `local.properties`.
