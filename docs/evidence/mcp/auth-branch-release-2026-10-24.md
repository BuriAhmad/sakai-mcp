# Auth branch release — 24 October 2026

## Authorization and source

The user authorized starting the preserved development resources and deploying
`codex/auth-development`, then explicitly chose an optional branch-release route
that leaves main at baseline. No tool migration is included.

`./sakai deploy COMMIT --branch codex/auth-development` now verifies the exact
fetched remote branch instead of requiring main. The default remains main.
All existing clean-source, archive checksum, VM/database prerequisites, staged
build, health checks and automatic rollback remain in force. The GitHub manual
release environment is still main-only.

## Local preparation

- Branch pushed; main unchanged.
- Focused Maven authentication/login suite passed again (24 October, 20:53 PKT).
- Bash syntax, ShellCheck error checks, and whitespace checks passed.
- Existing source-boundary verifier passed before release-script changes.
- Environment resume started with verified subscription
  `55a5701c-411e-45f1-9829-9c80f526d9eb`, group `rg-sakai-mcp-dev`.

## Current blocker

Azure rejected the narrow current-IP SSH rule update with
`RequestDisallowedByAzure`: the CLI identity requires MFA authentication.
The user was asked to refresh `az login`. No VM artifact was installed and no
authentication flag, Entra registration or database change was made.

This record will be updated with the actual release revision, rollback ID,
runtime dependency inventory and acceptance results after access is restored.

## Latest observed state

- Azure reports MySQL Ready and VM running.
- Portal HTTPS requests are timing out; startup has not been certified healthy.
- Branch-release check-only passed for pushed commit `c5f59984`.
- Main remains `208d69ac`; no release has been installed.
- The branch-release change is reviewed separately from auth code; the source
  anchor advances to that reviewed commit without allowing scripts as metadata.

## Access restored; release preflight

The exact narrow-IP SSH rule update succeeded using a token explicitly requested
for the Azure management resource. SSH is working. The previous release is
`20261013T172837Z-d54bcc13fcc8`, commit
`d54bcc13fcc85a5ef8510ac1e2c8514fad5c356b`. The VM reports only 4.7 GiB
free, below the release script's 12 GiB requirement. No safeguard was reduced.

GitHub run `40108875653` failed at frontend execution with
`Playwright does not support chromium on ubuntu26.04-x64`. CI is pinned to
Ubuntu 22.04 for the bundled browser tooling, and the focused Java step now
explicitly includes the shared module and consolidated auth tests.

## Approved cleanup and dependency preflight

The user approved removal of the ten old release directories through
`20261013T122832Z-10b1561ed92f`, preserving the current and immediately previous
release and backups. Cleanup was started under the release lock.

Runtime inventory found the legacy bearer gate already enabled, with tenant
6831cfbb-6904-4f1a-8dba-0ab09b803a9c, v1 sts issuer and the existing
Sakai audience/scope/JWKS. No flags or metadata are changed by this release.
The existing shared directory contains Nimbus 9.37.2 and 9.37.4. The release
script now removes the known obsolete 9.37.2 JAR from staging only, requires
managed 9.37.4 and the five shared Spring Security 5.7.14 modules, and rejects
duplicate versions before switching directories. Original libraries remain in
the rollback backup.
