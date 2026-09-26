# Phase 0 repository and environment inventory — 2026-09-26

Status: **PASS**. The source, release path, deployed commit, and current public HTTPS checks were verified.

## Repository

- Root: `/Users/burhanahmadkhan/Desktop/sakai-mcp`; branch `main`; starting HEAD `13e0ab661ef580b3e05eebbde9ddeaf7a531956f`.
- Existing worktree changes before this milestone: modified `.github/workflows/ci.yml` and `services/mcp/README.md`; untracked `docs/MCP_IMPLEMENTATION_RUNBOOK.md` and `scripts/check-repo-context.sh`. These are preserved as user changes.
- `apps/sakai/` is tracked by the top-level Git repository, has no nested `.git`, and was imported by `e092fa04` from Sakai 25.2 upstream commit `b5b7800f0fcddf9d0db47276a66065189365d905`. Source boundary: `docs/REPOSITORY_STRATEGY.md`.
- `services/mcp/` currently contains only its README. No MCP implementation, ACR, Container App, Key Vault, or Log Analytics definition was found in `deployment/infra/main.bicep`.

## Existing workflow to reuse

| Purpose | Source |
| --- | --- |
| Manual Sakai GitHub release | `.github/workflows/deploy-sakai.yml` (`workflow_dispatch`, `check-only` or `deploy`, selected full SHA) |
| Local exact-commit release | `./sakai deploy COMMIT`, `scripts/deploy-sakai-release.sh` |
| VM build, application swap, local health, automatic code rollback | `deployment/release-sakai-vm.sh` |
| Manual code rollback | `./sakai rollback RELEASE_ID`, `scripts/rollback-sakai-release.sh` |
| Public HTTPS health | `scripts/status-env.sh` and the `/portal` probe in `scripts/deploy-sakai-release.sh` |
| Azure source of truth | `deployment/infra/main.bicep`, `deployment/infra/parameters/dev.bicepparam`; deployment wrapper `scripts/deploy-infra.sh` |
| Runtime configuration convention | Ignored `deployment/.env` for bootstrap inputs; untracked VM `/opt/tomcat/sakai/local.properties` for Sakai runtime settings |
| Push checks | `.github/workflows/ci.yml` and `.github/workflows/sakai-source.yml`; ordinary push does not deploy Sakai |

The VM release builds the selected archive under `/opt/sakai-releases/<release-id>/source` with Java 17 and Maven, stages Tomcat `webapps`, `components`, and `lib`, then checks local and public `/portal`. Only the current release can be rolled back. Code rollback does not reverse data or configuration changes. See `docs/SAKAI_RELEASES.md`.

## Azure read-only status

`./sakai status` on 2026-09-26 confirmed selected subscription **Azure for Students** (`55a5701c-411e-45f1-9829-9c80f526d9eb`), resource group `rg-sakai-mcp-dev`, `vm-sakai-dev` initially **VM deallocated**, `mysql-sakai-dev-55a5701c-uae` **Ready** with public access disabled, and public URL `https://sakai-mcp-dev-55a5701c.koreacentral.cloudapp.azure.com/portal`. The initial HTTPS probe timed out because the VM was deallocated. After `./sakai start` finished, its public HTTPS `/portal` probe returned **HTTP 200**; an independent public curl also returned 200. Read-only VM inspection of `/opt/sakai-releases/current` returned release `20260924T181142Z-e0553fef88a0`, exact commit `e0553fef88a0ca149be3a33f0cd026aec88e9f16`. Nginx and Tomcat services were active. The startup wait took several minutes; a running Tomcat unit alone was not treated as application health.

No credentials, tokens, LMS data, or private keys are included here.
