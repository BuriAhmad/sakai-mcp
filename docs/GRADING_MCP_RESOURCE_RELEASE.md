# Release the Sakai grading resource migration

This procedure releases the MCP-only grading migration to the development
environment. It targets the existing Sakai VM and MCP Container App in
`rg-sakai-mcp-dev`. The release is two exact-commit deployments: native Sakai
first, then the MCP service. Follow the general [Sakai release](SAKAI_RELEASES.md)
and [MCP release](MCP_RELEASES.md) runbooks for their guarded commands and
rollback details; this document supplies the migration-specific order and
acceptance checks.

The migration removes the standalone importer and exposes files and grading
proposals through the existing authenticated MCP connection. It adds native
read/proposal endpoints and does not add a database migration or change Azure
capacity. The existing `ASN_SUBMISSION.LOCK_VERSION`, owner-only grading store,
Sakai grading gate, and MCP grading gate are prerequisites. Do not rerun their
provisioning or alter academic records as part of this release.

## Release sequence

1. **Review and identify one source commit.** Keep the grading implementation,
   protocol tests, native tests, contracts and operator docs together. Preserve
   unrelated local changes. Run the repository MCP tests/types/security checks
   and the focused native MCP Maven tests; require the corresponding GitHub
   checks to pass on `main`. Record the full 40-character commit SHA.
2. **Check the live target.** Confirm the selected Azure subscription is
   `55a5701c-411e-45f1-9829-9c80f526d9eb`, resource group is
   `rg-sakai-mcp-dev`, MySQL is `Ready`, the VM is running, and the MCP app is
   running with a healthy ready revision. Do not start paused services as part
   of this procedure. Confirm that the deployed Sakai already has the
   `ASN_SUBMISSION.LOCK_VERSION` column, private grading storage, and
   `mcp.assignment.grading.enabled=true`; confirm MCP has
   `ASSIGNMENT_GRADING_ENABLED=true`.
3. **Release native Sakai first.** Run `./sakai deploy SHA --check-only`,
   replacing `SHA` with the selected full commit. Resolve any refusal before
   continuing. Then run `./sakai deploy SHA`. This stops Tomcat during the
   build, restarts it on success, and prints a Sakai release ID for rollback.
   Verify public HTTPS and the new delegated native routes. Do not perform a
   grade save or return during deployment verification.
4. **Build and scan the exact MCP commit.** In GitHub Actions, run **Build or
   deploy MCP to development Container App** from `main`, supplying that same
   full SHA with mode `check-only`. Require the source/dependency and image
   scans to pass. A check-only run does not push or deploy.
5. **Deploy the MCP revision.** Start the same workflow again for the same SHA
   with mode `deploy`. This pushes the scanned image by immutable digest and
   creates a Container App revision. Require its built-in `/live`, `/ready`,
   bearer challenge, protected-resource metadata, digest, identity and
   no-affinity checks to pass. Record the prior digest and new revision for
   rollback.
6. **Verify through a normal MCP host.** Reconnect with the host's existing
   Sakai MCP authorization. Confirm the catalog gates, five resource templates,
   `ResourceLink` results and `resources/read` for a synthetic text and binary
   fixture. Confirm the proposal/report tools work on synthetic fixture data
   and a revoked or unauthorized read is denied. Do not use real student
   submissions or call grade save/release during this acceptance pass.
7. **Record and close.** Update the dated grading release evidence with both
   source SHAs, Sakai release ID, MCP image digest/revision, test and host
   observations, rollback identifiers and any unverified checks. Keep the
   previous MCP revision and Sakai backup until the new path has been exercised.

## Rollback

If native deployment fails, `./sakai deploy` attempts code-file rollback. Record
the failed release ID and inspect its build log before retrying. After a
successful native deployment, use `./sakai rollback RELEASE_ID` to restore the
preceding application files if the new native routes fail acceptance. This
does not reverse database or content changes; this migration performs neither.

If the MCP revision fails acceptance, use the previous immutable digest and the
revision-copy procedure in [MCP releases](MCP_RELEASES.md), then verify the
health probes and authenticated catalog. Native endpoints are additive and
remain backward compatible with the previous MCP image. Do not disable gates,
change capacity, or start/stop services as an improvised rollback.

## Completion record

The release report must state the selected subscription and resource group,
source commit, prior/current Sakai release IDs, prior/current MCP digest and
revision, native endpoint checks, protocol/resource checks, remaining host
limitations and any rollback. Distinguish deployment health from acceptance by
Codex, Claude, ChatGPT, Copilot or another product host; one host's result does
not establish universal support.
