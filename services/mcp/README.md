# Sakai MCP service

This package exposes a delegated Sakai MCP interface using the pinned MCP Python SDK. All public tool definitions live in [`src/sakai_mcp/mcp/tools.py`](src/sakai_mcp/mcp/tools.py). Tool handlers delegate to named Sakai operations or coordinated workflows; they do not implement HTTP transport or grading algorithms.

## Source map

```text
src/sakai_mcp/
  asgi.py                  Stable Uvicorn entrypoint
  bootstrap.py             Runtime construction and HTTP client lifecycle
  config.py                Validated configuration
  audit.py                 Request correlation, redaction, outcomes
  errors.py                Safe service error codes
  security/
    auth.py                Inbound delegated token validation
    obo.py                 Certificate-backed on-behalf-of token exchange
  mcp/
    tools.py               Every tool signature, description, annotation and gate
    server.py              SDK server construction
    resources.py           Resource templates and SDK resource reads
    context.py             Authenticated invocation and safe tool errors
    presenters.py          Public result, link and content formatting
    http.py                Local health and canonical OAuth discovery routes
  contracts/               Setup, native grading, public grading, proposal models
  sakai/
    client.py              Own the shared transport and operation groups
    transport.py           Fixed-origin JSON/binary HTTP, limits and retries
    paths.py               Validate and encode path identifiers
    courses.py             Course discovery and own released grades
    announcements.py       Announcement reads and single-attempt creation
    assignments.py         Setup, publication and legacy submission metadata
    grading.py             Typed grading, export, file and proposal operations
  workflows/
    grading.py             Proposal preparation, reconciliation and payloads
    resources.py           Authorized evidence resolution and manifest paging
  grading/
    evaluator.py           Pure deterministic MCQ engine
    serialization.py       Canonical JSON and payload hashes
    reports.py             Deterministic reports
```

`auth.py`, `obo.py`, configuration, audit, and setup validation retain independent boundaries. OBO means **on-behalf-of**: the transport obtains a distinct Sakai-audience token for the verified caller. No tool chooses the acting identity.

| Change | Start here |
| --- | --- |
| Inspect or change the public tool interface | `mcp/tools.py` |
| Change a native route/request/result validation | The corresponding `sakai/` operation module |
| Change timeouts, retries, HTTP bounds, stream integrity | `sakai/transport.py` |
| Change a multi-step grading procedure | `workflows/grading.py` |
| Change resource access or complete export aggregation | `workflows/resources.py` |
| Change public resource links, MIME/content results | `mcp/presenters.py` |
| Change request/response constraints | `contracts/` |
| Change grading rules or output | `grading/`; review evaluator provenance first |
| Change identity verification or token exchange | `security/auth.py` or `security/obo.py` |

A course read follows `tools.py -> client.courses -> transport -> native Sakai`. A grading proposal follows `tools.py -> GradingWorkflow -> client.grading + evaluator -> presenter`. Straight-through operations do not need an extra service layer. Skills are consumers of this interface and are not imported by the runtime.

## Local development and verification

Dependencies remain pinned in `pyproject.toml` and `uv.lock`.

```sh
cd services/mcp
uv sync --locked
../../scripts/check-mcp.sh
```

The shared check command runs lint/import ordering, formatting, typed function definitions, architecture boundaries, and tests. CI invokes this same command. No live credentials are required. Tests are organized under `unit/`, `protocol/`, `integration/`, and `security/`; reusable synthetic builders belong in `tests/fixtures/`.

`tests/contracts/` contains the public schemas, gate catalogs, and deterministic grading output captured before restructuring. Protocol tests compare actual SDK discovery against those fixtures. An intentional public change needs a reviewed contract update; do not regenerate snapshots simply to silence a failure.

The exact source of `evaluate_mcq` contributes to stored grading provenance. Its module is deliberately excluded from automatic formatting; tests verify its pre-refactor fingerprint and grading/report bytes. Any later engine change requires a separate provenance/version decision.

The native integration remains in `apps/sakai/webapi/` with packages for security, courses, announcements, assessment, shared contracts, and grading. See [the native source map](../../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md). Its permission/session/lock rules remain authoritative.

## Catalog and feature gates

| Setup flag | Grading flag | Tool count | Resource templates |
| --- | --- | --- | --- |
| false | false | 5 | 0 |
| true | false | 8 | 0 |
| false | true | 19 | 5 |
| true | true | 22 | 5 |

The default tools are `list_my_courses`, `get_my_grades`, `get_course_announcements`, `get_course_submissions`, and `create_course_announcement`. Announcement creation is the only default write.

`ASSIGNMENT_SETUP_ENABLED=false` independently gates `get_course_assessment_context`, `create_assignment`, and `publish_assignment`. The matching native property is `mcp.assignment.setup.enabled`.

`ASSIGNMENT_GRADING_ENABLED=false` independently gates the fourteen grading tools and five resource templates. The matching native property is `mcp.assignment.grading.enabled`. Proposal/export preparation can write private durable records; official grade save and return remain separate approved operations. Ambiguous and partial mutations are reconciled rather than automatically replayed.

Native grading also requires `ASN_SUBMISSION.LOCK_VERSION` and canonical owner-only storage configured through `mcp.assignment.grading.storage`. The refactor preserves existing records, paths, expiry, locking and wire formats; it introduces no schema migration or feature activation.

These counts describe local source. Dated release evidence and fresh discovery determine what a deployed endpoint actually exposes.

## Runtime and configuration

Keep `MCP_PUBLIC_URL` at the verified HTTPS origin; clients connect to `/mcp`, whose canonical OAuth resource URI is the origin plus `/mcp`. MCP tokens use the separate v2 application-client-ID audience. Sakai tokens use their distinct issuer, audience, and delegated scope. See [configuration](src/sakai_mcp/config.py) and the [native adapter/authentication reference](../../docs/mcp/sakai-adapter.md).

Provide `OBO_PRIVATE_KEY_FILE` and `OBO_CERTIFICATE_FILE` as mounted runtime files outside Git, alongside the verified Entra/Sakai metadata required by `Settings`. Starting the server reads those files during app construction, never during module import.

```sh
uv run --no-sync uvicorn sakai_mcp.asgi:create_app --factory --host 127.0.0.1 --port 8000
```

`GET /live` and `GET /ready` are unauthenticated local checks and never call Entra or Sakai. `/mcp` is authenticated stateless Streamable HTTP. The app preserves the SDK lifespan and closes service-owned HTTP clients at shutdown; injected clients remain their caller's responsibility. Audit logs contain safe outcomes, generated correlation IDs and hashed references, not tokens, student content or raw LMS identifiers.

## Build, release, and evidence

The Dockerfile uses the locked non-editable installation, pinned Python base, and non-root UID/GID 10001. `scripts/build-mcp-image.sh` builds an exact-commit image and performs the existing source/dependency, secret, and image scans. Dependency versions were not changed by the restructuring.

Deployment, feature activation and runtime starts require separate authorization under [the scoped guide](AGENTS.md). Local edits and CI do not deploy or start paused resources. Follow [MCP releases](../../docs/MCP_RELEASES.md), [Sakai releases](../../docs/SAKAI_RELEASES.md), and the [native-first grading release procedure](../../docs/GRADING_MCP_RESOURCE_RELEASE.md). Existing release and rollback command paths are preserved.

See [architecture](../../docs/mcp/architecture.md), [the implementation runbook](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md), [the restructuring plan](../../docs/mcp/restructuring-plan.md), and [local restructuring evidence](../../docs/evidence/mcp/restructuring-local.md). Workflow constraints remain in [assignment setup](../../docs/SAKAI_ASSIGNMENT_SETUP.md), [assignment grading](../../docs/SAKAI_ASSIGNMENT_GRADING.md), and [grading resources](../../docs/SAKAI_GRADING_MCP_RESOURCES.md). Client acceptance and historical release evidence retain their own dates and limitations.
