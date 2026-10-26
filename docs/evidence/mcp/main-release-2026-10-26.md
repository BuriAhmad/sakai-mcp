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

Guarded exact-main Sakai deployment `40292366783` succeeded. Release
`20261026T082756Z-1eb316f23371` passed the full VM build, local startup health and
public HTTPS check. Direct installed-artifact verification confirms the exact
main commit and healthy state, new readability helpers in bytecode, retired
verifier/filter classes absent, and preserved webapps/components/lib rollback
copies. The checked shared Framework/Security/Nimbus versions remain
5.3.39/5.7.14/9.37.4 respectively, one each; API WAR has no duplicate security/Nimbus
copy. Login WAR hash is unchanged from the prior release.

| Installed artifact | SHA-256 |
| --- | --- |
| sakai-mcp-auth-25.2.jar | `c4128c9a9eef3c94aad0a82dab3c99ac39e63e88db449f19b631aad26682605d` |
| api.war | `21f9d6ae348cff2b7a31e49884054c87b840e2c1c8c6c783f9f90d0870c97577` |
| sakai-login-tool.war | `d2d93917e678b902b050001b7ed2a380aebf71c41ae1af13c574448994deca46` |

Post-native-deployment live checks completed:

- **Sakai: 89/93 passed**, four genuine token/OBO principals. All four failures
  are the unchanged upstream wrong-password `/api/login` HTTP 500 mapping;
  each rejection leaves the caller anonymous. Native HTML login/logout, canonical
  EID, own/foreign course and role boundaries, mixed credentials, wrong-audience
  and tampered-token rejection, identity-header spoofing, no bearer cookies and
  tokenless follow-ups passed. All 16 interleaved student grade exercises passed.
- **MCP: 15/15 passed** after native deployment: health, unauthenticated denial,
  four-principal initialize/tools-list and MCP → OBO → Sakai course isolation.
- The first attempts were interrupted by connection refusals/timeouts and are
  not counted as completed acceptance. The successful rerun allowed at most
  three transport attempts per request, never retried an HTTP status or failed
  assertion. Sakai needed 10 transport retries; MCP needed zero. This preserves
  the observed network limitation rather than claiming a clean network run.
- Private fixtures, credentials, tokens, course IDs/content and raw logs remain
  outside Git; this record contains sanitized outcomes only. Existing-HTTP and
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


## Release interpretation and remaining issues

Both native Sakai and MCP now run source commit `1eb316f2` from main. The later
release-evidence merge changes guidance/metadata only; main's tip may therefore
be newer than the installed application without changing its source provenance.
Baseline/auth/tool references retain their recorded commits; all feature branches
remain available and no worktree was removed.
The running VM, MySQL and MCP are the existing resources; scaling, schema, Entra,
course content and academic records were not changed by the release.

The baseline wrong-password API error status remains open, SAML is not configured,
existing-HTTP/flow positive acceptance is outside this release, and delegated
attachment support remains unaccepted. No grading/announcement writes, export or
full tool-migration workflow acceptance is claimed. The certifi critical finding
is fixed in the released image; the recorded 44 unfixable-high image findings and
other upstream dependency alerts are not claimed resolved. Network instability
required bounded retries. This is a development release, not production acceptance.
