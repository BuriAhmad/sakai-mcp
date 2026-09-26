# Sakai WebAPI MCP adapter

The Sakai-side V1 adapter lives in tracked `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/`. Its servlet paths are relative to Sakai's existing `/api` WebAPI context. It is **disabled by default** and must not be enabled until the Phase 7 and 8 gates in the [runbook](../MCP_IMPLEMENTATION_RUNBOOK.md) are satisfied.

## Runtime properties

Set these as Sakai properties through the existing VM configuration procedure. They are non-secret values, but environment-specific values must be verified from the issued downstream token and Entra metadata. Do not paste tokens, private keys, or client secrets into Sakai properties.

The tracked [`configure-mcp-sakai.sh`](../../deployment/configure-mcp-sakai.sh) script writes only this marked runtime block and leaves the rest of `local.properties` intact. It records a one-time pre-MCP backup. Apply it before a guarded exact-commit deployment so that the existing release restart activates the settings; do not edit the file by hand on the VM. The script's inputs are non-secret values, but keep project-specific identifiers out of evidence.

| Property | Required meaning |
| --- | --- |
| `mcp.integration.enabled` | `true` only for a validated rollout; default `false` |
| `mcp.integration.issuer` | Exact `iss` of the Sakai API access token |
| `mcp.integration.tenant` | Exact `tid` of the accepted tenant |
| `mcp.integration.audience` | Exact Sakai API resource `aud`, distinct from the MCP resource |
| `mcp.integration.scope` | `sakai.mcp.access` delegated scope |
| `mcp.integration.jwksUri` | Trusted HTTPS JWKS URI from the tenant metadata |

The browser-facing `RequestFilter` runs first. The adapter filter runs only on `/api/mcp/v1/*`, requires Tomcat to see the request as HTTPS, rejects missing or invalid downstream bearer tokens, and resolves the verified `extn.SakaiEid` singleton array through Sakai's trusted external evidence path. It rejects disabled/unmapped accounts and any mismatch between the token identifier and resolved Sakai EID. It creates and invalidates a separate request-local Sakai session, then restores the previous context. The code never accepts an identity header or relies on a browser cookie for this path. The MCP service owns the certificate-backed OBO exchange; Sakai has no OBO credential.

## V1 routes

| Method and path after `/api` | Behavior |
| --- | --- |
| `GET /mcp/v1/courses` | Up to 500 visitable course IDs and titles for the acting user |
| `GET /mcp/v1/courses/{siteId}/grades/me` | Released gradebook items and only the acting user's grade |
| `GET /mcp/v1/courses/{siteId}/announcements` | Visit-gated, viewable main-channel announcements; bounded to 50 results |
| `GET /mcp/v1/courses/{siteId}/assignments/{assignmentId}/submissions` | Up to 100 submitted records with ID, submitter IDs, and time; requires grade permission and filters group/section visibility |
| `POST /mcp/v1/courses/{siteId}/announcements` | The only V1 write; posted plain announcement in the main channel after Sakai `annc.new` authorization |

All course paths require `SiteService.getSiteVisit` before reading or writing a course object. The generic WebAPI announcement route is not reused because its live cross-site probe exposed unrelated announcements. The grades route never accepts a target student ID. The write route does not retry an ambiguous commit; callers must not replay it automatically.

## Local verification

Use Java 17 and the Sakai reactor, because WebAPI depends on sibling Sakai modules:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

The local command and focused results are recorded in [`phase-7-sakai-adapter.md`](../evidence/mcp/phase-7-sakai-adapter.md). The exact-release-commit VM build, post-deployment negative tests, and rollback still use the repository's existing [Sakai deployment runbook](../Sakai_Deployment_Runbook.md).
