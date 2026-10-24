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
