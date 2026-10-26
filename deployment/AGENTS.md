# Deployment guide

This directory controls Azure resources and the Sakai VM/application setup. Read the relevant section of `docs/Sakai_Deployment_Runbook.md` before changing a deployment path; use `docs/INFRASTRUCTURE.md` for the current intended architecture.

- `deployment/infra/` contains the Sakai template and separate staged MCP foundation/app Bicep templates. Its README explains deployment inputs; do not rerun the Sakai VM/MySQL deployment to release the MCP app.
- `deployment/README.md` distinguishes the Sakai VM release from the MCP Container App revision path; follow `docs/SAKAI_RELEASES.md` and `docs/MCP_RELEASES.md` respectively.
- Keep the database private, keep SSH limited to the administrator's current `/32` address, and do not expose Tomcat directly. Preserve the resource-group boundary and cost controls unless a task explicitly changes them.
- Keep Tomcat's HTTP connector bound to loopback and its forwarded-scheme trust limited to local Nginx. `configure-tomcat-proxy.sh` owns this repeatable setting; verify an HTTPS Sakai form action after proxy changes.
- Keep Sakai's Java module options aligned with its tracked 25.2 Docker runtime. `ensure-sakai-java-opens.sh` amends the VM's `setenv.sh`; verify the affected tool after restart.
- `configure-mcp-sakai.sh` owns the optional, default-disabled MCP properties in Sakai `local.properties`. Feed it only verified non-secret Entra metadata; use the guarded exact-commit release for the Tomcat restart and preserve its configuration backup. Its optional seventh true/false argument controls `mcp.assignment.setup.enabled`; omission preserves an existing setting and defaults new installations to false. Do not enable it without a separately authorized next-phase release.
- `configure-assignment-grading-sakai.sh` owns the separate grading property block. Provision its canonical private storage and migrate `ASN_SUBMISSION.LOCK_VERSION` before enabling it; use the guarded exact-commit release to restart Tomcat.
- For the MCP-only grading resource migration, use [`docs/GRADING_MCP_RESOURCE_RELEASE.md`](../docs/GRADING_MCP_RESOURCE_RELEASE.md): verify existing schema/storage/gates, release backward-compatible native Sakai endpoints first, then deploy the same commit to the MCP Container App and record both rollback points. Do not rerun provisioning or change capacity as part of that release.
- Check the Azure subscription and affected resource scope before running a deployment or changing live resources. `./sakai status` is a read-only starting point.
- Follow the root guide's [approval initiative](../AGENTS.md#take-initiative-at-approval-boundaries): when a release or runtime action is appropriate for the user's intended outcome, prepare the concrete action and proactively request any missing authorization. Explain prerequisites, affected resources and material effects; existing authorization remains valid, and paused resources still require explicit permission to start.
- Follow `docs/PAUSE_AND_RESUME.md` for preserved stop/start of VM, MySQL, and MCP app. Never treat a forecast budget alert as authorization to change runtime state. `./sakai start` and `./sakai stop` require the user's explicit request or permission; a push or code release must not start paused resources implicitly.
- Never commit `deployment/.env`, credentials, keys, or database content. Deployment scripts should remain repeatable and should fail clearly when required inputs are missing.
- When adding a new deployment directory or pathway, document its purpose and command in that directory's README, then add a pointer here. When changing Azure resources, update the architecture documentation and any affected runbook steps.

## Release source

Follow [the Git workflow](../docs/GIT_WORKFLOW.md) and
[Git release Skill](../skills/git-release-workflow/SKILL.md). Release only exact
pushed commits on `origin/main`. Develop and validate changes on a feature branch;
merge into main before deployment. Old feature-branch release evidence is historical.
