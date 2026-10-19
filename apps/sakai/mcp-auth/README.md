# Delegated authentication/session integration

Authentication-only shared JAR for existing HTTP handlers, governed by the
[canonical plan](../../../docs/mcp/existing-api-migration/implementation-plan.md).
No endpoint, domain operation, permission advisor or custom persistence is defined.

The credential guard precedes native RequestFilter. It verifies the distinct
Sakai-audience token, resolves the canonical enabled account using native trusted
evidence, logs in an isolated registered Session and supplies its cookie only
inside the server. RequestFilter therefore captures the selected session. The
following binder checks that identity, aligns principal/remote-user/current-request
accessors, and blocks asynchronous escape. The outer response wrapper suppresses
session headers/cookies, including native filter postprocessing.

Placement-free scope includes seven GETs: `/api/users/me/sites`,
`/direct/user/current.json`, `/direct/site/{id}.json`, and
`/direct/site/{id}/userPerms.json`, `/direct/site/{id}/pages.json`, and
`/direct/announcement/site/{id}.json`. Only the announcement read accepts the
selected single numeric `n,d,a` parameters. `/direct/site.json` permits only
`select=access` and numeric `_start,_limit`; alternative selections are rejected.
Other reads have no query/body; mixed
credentials are rejected. The
independent property `mcp.integration.existingHttp.enabled` defaults **false**.
Native handlers retain all ordinary permission behavior.

Browser conversations additionally require `mcp.integration.conversations.enabled`
(default **false**), a Base64 32–64-byte server secret `mcp.integration.flowSecret`,
and an explicit `mcp.integration.placements` allowlist of reviewed placement IDs.
Each request still needs a freshly verified Bearer/account. A private random
`X-MCP-Flow` nonce selects an HMAC-derived native session bound to tenant/object/UID/
EID. Native Session attributes hold only auth ownership/deadline. No native session
credential is issued to Python. Conversations have a five-minute maximum age,
60-second native inactivity interval and caps of four per actor/256 per node.
Striped locks serialize requests/creation; they do not lock business records.

The actor's real Portal/ActiveTool dispatch establishes placement and ToolSession.
Existing named dispatch can still report REQUEST through Sakai's wrappers; the
shared server-created marker plus exact current session/tool/placement validate
nested dispatch. External target-WAR requests cannot manufacture that marker.
The integration is registered on the existing Portal, Assignment, Announcement,
Gradebook and filepicker servlet names, excluding synoptic/admin/resources routes.
Unexpected ASYNC/ERROR, borrowed cookies/session parameters, unknown placements
and alternate actors fail closed. No ordinary tool/login behavior is changed.

Python terminates a flow using `X-MCP-Flow-End: 1` on the existing current-user GET.
Failed/expired-token cleanup falls back to native inactivity cleanup; immediate
cleanup is not claimed. Node-local sessions require backend affinity, and a native
restart loses UI state. Durable mutation receipts belong outside Sakai.

Local Java 17 tests exercise actual RequestFilter chains, two-user interleaving,
JWT/account negatives, expiry/end handling, and an embedded Tomcat named forward
through actual ToolHandler/ActiveTool classes. The receiving state-probe servlet
is synthetic: these tests do **not** certify actual Assignment/Announcement/Wicket
rendering, business operations, OAuth1 runtime behavior, or deployed availability.
A separate existing Sites controller/ordinary Login regression runs in WebAPI.

From the repository root, use Java 17 and the reactor (not an assumed installed
Sakai JAR set):

```sh
mvn -f apps/sakai/pom.xml -pl webapi,mcp-auth -am \
  '-Dtest=Delegated*Test,PortalContainerTest,ExistingSitesChainTest,LoginControllerTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

Packaging uses `deploy.target=shared` and provided WAR dependencies. The existing
`deploy/pom.xml` already supplies the reviewed Nimbus version to shared libraries;
release exactly one auth JAR. Existing WebAPI `/mcp/v1/` traffic continues to its
legacy filter during migration; there is no fallback from a failed existing API.
Deployment, flags/secrets/placement configuration, runtime starts and synthetic
academic acceptance require separate authorization and exact-revision manifests.

Delegated responses are buffered up to 1,000,000 bytes before emission. The current
native session credential is rejected in body or headers, including fragmented
writes and native diagnostic views. Opaque compressed/unsupported encodings and
unhandled downstream failures yield an empty 502; normal tested bodies remain
byte-exact. This does not parse business HTML/JSON and does not certify every
native error renderer. General content streaming beyond these selected bounded
reads requires a separate capability review. Ordinary requests bypass this wrapper.
