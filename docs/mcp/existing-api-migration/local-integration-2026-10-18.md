# Local authentication and HTTP migration evidence — 18 October 2026

Branch: `codex/sakai-python-http-native-auth-only`. HEAD remains
`208d69ac624910a29a7529934ddcc18bbac853e8`; the index is empty. This is an
uncommitted implementation checkpoint, not a releasable revision. The immutable
starting manifest/private archives are identified by `implementation-start.json`.

## Implemented locally

- `apps/sakai/mcp-auth` contains only delegated JWT/account/session integration.
  The guard runs before native RequestFilter and the binder runs after it.
  Existing WebAPI/Direct handlers and narrowly named Portal/tool servlets have
  additive registration. Existing legacy authentication/routes remain intact.
- Four placement-free GETs are accepted: current user, rich own sites, site detail
  and site effective permissions. Browser requests require a configured placement,
  verified Bearer on every step, private flow nonce, short-lived native session,
  strict dispatch binding and cleanup. The defaults disable both modes. Source
  review found native DEBUG/TRACE session logging; delegated requests fail before
  creating state under those logging levels. Native cookies never reach Python.
- Python owns bounded native form/XML/Wicket/Gradebook parsing and single-send
  browser transport. Synthetic fixtures establish parser behavior, not real form
  acceptance. Multipart/helper transitions and rendered dynamic callbacks remain
  unaccepted; no guessed write sequence is enabled.
- `COURSE_READ_INTERFACE=existing` selects existing clients through the public
  course facade without changing tool arguments or falling back to a custom route.
  Native site visit authorization and OBO-to-native EID binding are checked.
  The default remains `legacy`. Public nonmaintainer site fields can be masked:
  insufficient visit proof fails explicitly pending a safer Portal proof. More
  than 500 rich sites is explicitly unsupported rather than silently truncated.
- External private record ownership, original expiry, immutable artifacts and
  conditional operation intent/observations are in Python. The Azure Blob adapter
  uses managed identity, conditional creation, ETag/finite-lease fencing and bounded
  downloads pinned to one ETag. SDK automatic storage retries are disabled. It has
  no delete, provisioning, SAS or public-download API. The memory implementation is
  test-only. Neither backend is wired into the deployed grading workflow.
- New journal provenance records absent native CAS/atomic-batch guarantees.
  A durable Sending/Unknown record cannot authorize a resend. Readback cannot
  establish causation. No existing-HTTP academic commit is enabled.

## Fresh verification

- `uv sync --locked` and `./scripts/check-mcp.sh`: **330 passed**; Ruff lint and
  formatting pass; mypy passes for 56 source files. Frozen public schemas, all
  four catalogs (5/8/19/22 tools), five resource templates and evaluator provenance
  pass their existing compatibility checks.
- Java 17 reactor `-pl webapi,mcp-auth -am` with
  `-Dtest=Mcp*Test,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,LoginControllerTests`
  and `-Dsurefire.failIfNoSpecifiedTests=false`: **89 passed**, zero skipped.
  Sixteen exercise the new auth module; 73 cover the existing Sites chain,
  ordinary Login controller and retained legacy MCP regressions.
- The embedded Tomcat test runs actual RequestFilter, Portal ToolHandler and
  ActiveTool dispatch across two contexts for successive requests. Its receiving
  servlet and services are synthetic. In actual Sakai named dispatch the exposed
  dispatcher type can remain REQUEST: trusted internal identity/session/placement
  binding is required, rather than relying on dispatcher type alone.
- Source tests check auth dependency boundaries and exact servlet registration
  order, including retained Direct OAuth filters. These do not certify deployed
  OAuth/Basic/login behavior, actual business views, node affinity or framework
  logging configuration.
- Fresh `uv build` produced wheel/sdist; the new browser/form/Blob modules are
  present in the wheel. Java 17 `-pl mcp-auth -am -DskipTests package` passed.
  The auth JAR has 15 classes, all under `org/sakaiproject/mcpauth`, no tests;
  SHA-256 `5f22894daa5f64cb7889cd018631581761e0dd3968c958bac68e5ca90fc4aaee`.
  This local binary is not an exact committed/deployed release.
- Private Blob tests use injected SDK doubles: no Azure connection, durability,
  backup restoration or multi-replica acceptance is claimed.

## Next gates and release ordering

1. Review the additive auth artifact/source set and create exact native/Python
   revisions from the preserved checkout. Package/dependency review must ensure
   exactly one shared auth JAR with matching Sakai/Nimbus dependencies. No broad
   staging of the unrelated restructuring is appropriate.
2. With separate runtime/release authorization, inventory the installed revision,
   configuration, schema and private records read-only. Deploy additive auth
   retaining all legacy business routes before switching any consumer. Confirm
   ordinary login/cookie/OAuth/Basic consumers, proxy TLS, debug logging, node
   affinity, role-specific identity/site visits and two-user session isolation.
3. Capture sanitized existing Sites/Direct and real Announcement/Assignment/
   Gradebook/filepicker HTTP contracts for approved synthetic roles. A browser
   GET can update native session state; academic POSTs need separate authorization.
   Keep credentials and raw user/content data outside Git. Record exact method,
   handler, role, placement class, result category/count/hash and source revision.
4. Resolve public nonmaintainer visit proof and large-site parity before making
   T01 the default. Finish each subsequent capability and its focused retirement
   only after caller, shared-consumer, public-contract and authorization checks.
   No custom route has been retired at this checkpoint; all 23 remain required by
   legacy/default clients.
5. **D3 remains a user decision:** accept tested best-effort official grading with
   strict preflight/journal/readback/partial and unknown reporting, or require
   stronger guarantees and keep existing-HTTP commits unavailable. Local
   implementation authorization alone does not settle that guarantee change.
6. **D6 before provisioning/import/cutover:** approve backend/receipt and backup
   retention, legacy owner mapping, preserved receipts, unchanged original expiry
   and an import/drain manifest. The adapter is local preparation only. Verify
   restart, conditional races and actual backup restoration before relying on it.

No deployment, feature activation, Azure start/stop/capacity change, academic write,
schema change, stored record deletion or legacy data cleanup occurred. The next
release boundary follows root `AGENTS.md` and plan §0.4; the user's explicit runtime
restrictions remain in effect.

SDK implementation references: [BlobClient](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.aio.blobclient?view=azure-python),
[finite leases](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.aio.blobleaseclient?view=azure-python),
[managed identity](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.aio.managedidentitycredential?view=azure-python),
[transport configuration](https://learn.microsoft.com/en-us/python/api/azure-core/azure.core.pipeline.transport.aiohttptransport?view=azure-python).
