# Main integration and development release — 26 October 2026

## Authorization and workflow

The user requested main as the release integration branch, all changes developed
and tested on feature branches, retained feature/baseline references, and generic
repository instructions. This supersedes the previous auth branch-release
exception. [Git workflow](../../GIT_WORKFLOW.md),
[Git release Skill](../../../skills/git-release-workflow/SKILL.md), root/deployment
AGENTS and release runbook now describe the standing practice. Main was updated
only through `--no-ff` merges; no source or evidence was edited directly on main.

## Integrated history

| Boundary | Commit | Result |
| --- | --- | --- |
| Preserved baseline | `208d69ac624910a29a7529934ddcc18bbac853e8` | Baseline checkout/branch retained; branch backed up on origin |
| Auth merge | `4eeea933` | Integrates auth including readability refactor; source branch retained |
| Workflow merge | `b9711c70bf8e47d3dbe245ba63abf3ad81f96ab9` | Main-only CLI and generic instructions; policy branch retained |
| Security dependency merge | `1eb316f23371ea4e56bf8f268f1ee91bf77eb20a` | Patched certifi bundle; maintenance branch retained |

Selected release source: **`1eb316f23371ea4e56bf8f268f1ee91bf77eb20a` on origin/main**.
Its entire `apps/sakai/` tree equals reviewed auth `c1c5c27e`; workflow and dependency
maintenance do not change the native application. The original recovery and tool
migration checkouts are untouched. Tool migration is not integrated in this release.

## Preparation and checks

- Bash syntax, ShellCheck error checks, whitespace, skill validation and repository
  context checks passed. The skill validator used an isolated PyYAML environment;
  project dependencies were unchanged by validation.
- Six local temporary-Git release checks passed: pushed main allowed, pushed
  unmerged feature denied, retired `--branch` denied, unpushed main denied,
  pushed merge allowed, dirty application denied.
- Latest auth CI `40198904498` passed before integration. Local auth readability
  verification passed 107 focused Java and eight source-boundary tests.
- Repository CI `40290145173` found critical certifi advisory
  [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2).
  Maintenance code `67527042` updates only the certifi lock entry from `2026.7.22`
  to patched `2026.10.19`. All 145 MCP tests, Ruff and mypy (17 files) passed.
  Feature CI `40290781177` passed source/image scans and all repository jobs.
  Scan policies and runtime feature gates were not weakened.
- Main release check-only accepted the selected pushed SHA. GitHub Sakai preflight
  `40290834512` passed on attempt 2; attempt 1 hit an Azure CLI Python import
  deadlock before successful preflight. Its existing SSH/sudo/disk prerequisites
  remain in force.
- Initial Azure/GitHub connections were intermittent. The VM was deallocated,
  MySQL Ready; the preserved VM was resumed under the requested release/start
  authorization. VM agent inventory reported 26 GiB free. This network's observed
  public IPv4 varied, so the existing GitHub release runner is used for stable
  SSH source admission. SSH is never broadened beyond one `/32`.

## Main CI and MCP release

Repository CI on selected main `40291069968` passed all jobs. Sakai source CI
`40290306502` passed the full 455-module build, 203 Chromium tests across 66 files,
and 107 focused Java tests (42 shared auth + 65 WebAPI, no failures/errors/skips).
The same focused Java suite was rerun locally from the assembled source checkout:
107 passed, zero failures/errors/skips, BUILD SUCCESS. That CI run is on main merge
`b9711c70`; the final selected main commit has exactly
the same complete `apps/sakai/` tree.

Exact-main MCP check-only `40291126666` passed. MCP deployment `40291461655`
succeeded from selected main `1eb316f2`:

- Revision: `ca-mcp-sakai-dev--0000019`.
- Direct Azure metadata check confirmed Running, latest equals latest-ready revision,
  source commit `1eb316f2`, and lock SHA
  `6bdf99255ce86dd68a05dfb11e365adeadeea5fe76461607daa12073246fcdc9`.
  Replica limits remain 0–2.
- Digest: `sha256:a4bb8ff32178b2852de70c676d036c8983d58ecb337b8a497c5d2d5bac419e47`.
- Previous image: `sha256:5c1079b759f0c1af56dcefbbacee2152296285ca2e8247bec01982ec69a6db4b`.
- Release passed HTTP probes, OAuth challenge, resource metadata, image identity
  and affinity checks. Source scan: 0 critical/high/secrets. Image scan: 0 critical,
  0 fixable high, 44 high without a published fix, 0 secrets; existing scan policy
  permits and records those remaining base-image findings.
- First read-only live MCP pass after the image update: **15/15 passed**, including
  initialize, tools listing and real four-principal MCP/OBO/Sakai course isolation.
  These calls preceded the pending native redeployment; repeat after it completes.

## Sakai execution and final acceptance

Guarded exact-main Sakai deployment `40292366783` staged release
`20261026T082756Z-1eb316f23371`. The full VM build passed all 455 modules; installation
and startup health checks are in progress. Final runtime
artifact verification and live checks remain pending. Existing-HTTP and
multi-request-flow gates remain disabled; attachment reach is unchanged. No
academic writes, Entra or schema changes are part of this release.


## Guidance integration follow-up

Release evidence is maintained on `codex/main-release-evidence-2026-10-26`, not
edited directly on main. The same documentation follow-up removes the inherited
whole-checkout auth-only wording from the Sakai guide and preserves the user's
existing-API/native-authentication-only boundary in the root guide. The auth
module stays authentication-only; business retirement still needs its own
approved plan and feature branch. Historical development-line ownership records
are retained as provenance. No application source changes accompany this follow-up.
