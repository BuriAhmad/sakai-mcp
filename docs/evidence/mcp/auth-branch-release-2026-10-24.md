# Auth branch release — 24 October 2026

**Final status: deployed and healthy.** Native source commit
`2844430a44cf5cf0896ca05c522f7fe4f04c16bd`; release
`20261024T163517Z-2844430a44cf`. Main remains `208d69ac`.
Preparation history follows; the final results below supersede interim blockers.

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

## Preparation blocker (resolved)

Azure rejected the narrow current-IP SSH rule update with
`RequestDisallowedByAzure`: the CLI identity requires MFA authentication.
The user was asked to refresh `az login`. No VM artifact was installed and no
authentication flag, Entra registration or database change was made.

This record will be updated with the actual release revision, rollback ID,
runtime dependency inventory and acceptance results after access is restored.

## Intermediate observed state (superseded below)

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

## Final release result

- Approved cleanup completed: ten older release directories removed under the
  release lock; current and immediately preceding releases retained. Free space
  increased from 4.7 GiB to 38 GiB, and was 32 GiB after the new release.
- [GitHub run 40110954188](https://github.com/BuriAhmad/sakai-mcp/actions/runs/40110954188)
  passed parent validation, full application build, 203 browser tests in 66 files,
  and the consolidated focused Java suite (42 shared auth + 65 WebAPI tests).
  This run is at `d325e548`; the deployed revision adds only reviewed staging
  validation and documentation, with identical Sakai application source.
- Local focused Java tests: 107 passed; Python tests: 145 passed. Release-script
  Bash syntax and ShellCheck error checks passed; staging checks accepted a valid
  tree and rejected missing dependencies and duplicate versions.
- VM rebuilt all 455 modules from the exact archived revision using the normal
  parent build and `clean install sakai:deploy` route; build succeeded.
- Installed shared auth libraries: `sakai-mcp-auth-25.2`, Nimbus 9.37.4 only,
  Spring Security core/web/oauth2-core/oauth2-resource-server/oauth2-jose 5.7.14.
  API WAR carries none of those shared security JARs. Login WAR retains Security
  config 5.7.14 and SAML extension 1.0.10.RELEASE.
- Installed shared auth JAR has the consolidated factory and no old verifier/filter
  classes. API WAR has no McpBearerFilter, McpJwtVerifier or DelegatedJwtVerifier.
- `/opt/sakai-releases/current` records the new release and exact commit; status
  is `healthy`. VM-local and public HTTPS portal checks passed.
- Final Azure state: VM running, MySQL Ready, MCP Container App Running. The
  existing MCP image was resumed; no Python runtime source change required an
  image release. Existing authentication flags/metadata were preserved.

### Connection interruption and guarded completion

The local SSH connection broke after the remote Maven build started. The remote
build continued and completed staging, but the release process terminated before
switching directories. Readback confirmed status `built`, no process holding the
release lock, an unchanged prior installation/current record, and intact staging.

A one-time completion script in `/var/tmp/sakai-auth-complete-staged.sh` reused
reviewed release functions, dependency validation, directory switching, rollback
trap and health loop from the tracked release script. It additionally required
this exact staged commit, status `built`, unchanged previous-current and empty
backup destinations. It ran with nohup and redirected output to the release's
`completion.log`, allowing completion despite client disconnection. It did not
rebuild, alter application code or reduce any health/rollback check. This was an
explicit operational recovery from the documented CLI path, not a new normal
release command. Future long SSH releases can have the same connection-lifetime
limitation; use a durable logged runner before the next unattended release.

### Live request checks

| Check | Result |
| --- | --- |
| Public HTTPS `/portal` | 200 |
| Browser `/portal/login` and `/sakai-login-tool/container` | 200 |
| POST `/api/login` without credentials | 400, as specified |
| GET `/api/login` | 500 from unchanged handler for unsupported GET; controller is POST-only |
| Legacy course route without bearer | 401 |
| Legacy course route with invalid or malformed combined bearer | 401 |
| Connected real MCP `list_my_courses` | Success, two accessible courses |
| Connected real MCP `get_course_announcements` | Success for one accessible course |

The two read-only connected MCP requests exercised real inbound authentication,
OBO and the deployed Sakai delegated route. No bearer was fabricated or logged;
no academic write was performed. Course identifiers/content are omitted here.
This is positive live acceptance for the connected principal and those routes,
not certification of every tool, role or permission boundary.

### Retained rollback and artifact manifest

`./sakai rollback 20261024T163517Z-2844430a44cf` restores the previous
application directories. All three backups (`webapps`, `components`, `lib`) exist.
The previous current record is `20261013T172837Z-d54bcc13fcc8`. Code rollback
does not roll back data. No database/schema, uploads, Entra registration or
runtime property changes were made by this release.

| Installed artifact | SHA-256 |
| --- | --- |
| Shared sakai-mcp-auth-25.2.jar | `0bf58e92b933610f7ebd6a5656d6d5c81d23c85d6efa6452239879ecdea00838` |
| api.war | `858a0e505856da336021212bd56597604ca6fb690c903a9099add72ad8ea9c4c` |
| sakai-login-tool.war | `d2d93917e678b902b050001b7ed2a380aebf71c41ae1af13c574448994deca46` |

### Remaining final-testing gates

A complete regular username/password browser sign-in/logout check, the
student/instructor cross-course permission matrix, and tool-specific session/flow
acceptance remain. Existing-HTTP
reach was not enabled during deployment. Historical failed attachment proofs are
still unaccepted. The unsupported-GET 500 above is an existing API error-mapping
limitation; its source was not changed in this authentication release. The
repository's pre-existing dependency vulnerability backlog remains outside this
refactor and must be reviewed before production use.

### Login configuration clarification

Read-only deployed checks after the user's question confirmed no active imports
in the login WAR's applicationContext.xml, no SAML login/authentication runtime
property keys or SAML XML overrides under Sakai home, and no SAML profile mention
in setenv.sh. This environment uses ordinary username/password login; bundled
SAML classes/libraries are unused capability, not evidence of enabled SAML login.
The earlier unconditional SAML acceptance wording was overly broad. A SAML IdP
round trip is required only if SAML is configured in a future environment. MCP's
Entra delegated OAuth bearer flow is separate from ordinary browser login.
