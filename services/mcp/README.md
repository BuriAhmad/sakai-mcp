# Sakai MCP service

This package exposes a delegated Sakai MCP interface using the pinned MCP Python SDK. All public tool definitions live in [`src/sakai_mcp/mcp/tools.py`](src/sakai_mcp/mcp/tools.py). Tool handlers delegate to named Sakai operations or coordinated workflows; they do not implement HTTP transport or grading algorithms.

The [existing-HTTP migration](../../docs/mcp/existing-api-migration/implementation-plan.md)
is in progress. `sakai/operations.py`, `existing_transport.py`, `webapi.py`,
`entitybroker.py`, `cxf.py` and `contracts/existing_api.py` contain
source-derived clients/contracts. Twenty defaults now use existing HTTP/external records;
[five-tool cutover evidence](../../docs/mcp/existing-api-migration/five-tool-cutover-2026-10-19.md)
records role, completeness and precision limits. Two tools still need
replacement. See `tests/fixtures/existing_http/README.md`
for unexercised fixture provenance and specific scope/serializer gaps. Auth remains
Entra/OBO; browser conversation integration is a separate local proof gate.

## Known tool limitations

See the [current limitations reference](../../docs/mcp/existing-api-migration/tool-limitations.md)
for each replaced tool's permission restrictions, completeness and precision gaps,
source/output caps, unsupported attachments, uncertain-write handling and live
acceptance gates. A local default replacement does not imply full parity or a
usable deployed workflow. Keep this reference current when tool behavior changes.

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
  contracts/               Public/wire models and bounded native HTML/XML/Gradebook parsers
  storage/                 External conditional objects/records; memory adapter is test-only
  sakai/
    client.py              Own the shared transport and operation groups
    transport.py           Fixed-origin JSON/binary HTTP, limits and retries
    paths.py               Validate and encode path identifiers
    courses.py             Course discovery and own released grades
    announcements.py       Announcement reads and single-attempt creation
    assignments.py         Setup, publication and existing submitted metadata
    grading.py             Typed grading, export, file and proposal operations
  workflows/
    grading.py             Proposal preparation, reconciliation and payloads
    resources.py           Authorized evidence resolution and manifest paging
    own_grades.py          Current-user native view and item identity correlation
    submissions.py         Scoped submitted evidence and inline text reads
    announcements.py       Existing native Add form and single-send journal
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

## Existing-HTTP migration implementation

The [canonical plan](../../docs/mcp/existing-api-migration/implementation-plan.md)
and [course cutover evidence](../../docs/mcp/existing-api-migration/t01-course-cutover-2026-10-19.md)
govern the transition. `list_my_courses` now always uses existing Sites/Direct
HTTP interfaces through `sakai/courses.py`; its legacy route and interface setting
have been removed locally. Public sites require native effective visit permissions
and fresh ACCESS selection where deleted state is masked. Exact DTO ID and
publication masking are characterized against the actual native JSON encoder.
The sorted 500-visitable-course cap is preserved; transport/item bounds still
apply. Rare masked states without sufficient status permissions fail explicitly.
This source cutover requires separately authorized additive native authentication
and live acceptance before release; the local native tip is incompatible with
older Python clients that still call the retired course endpoint.

The auth-only native source is now [mcp-auth](../../apps/sakai/mcp-auth/README.md).
Other public capabilities still use transitional native business routes; their
historical service/schema/locking descriptions above are compatibility evidence.
Browser transport/parsers are locally tested with synthetic shapes; actual form,
role, helper and Wicket callback acceptance is still required before wiring writes.

`storage/` provides conditional private objects and immutable records; its Blob
adapter uses managed identity and disabled automatic retries. It performs no
provisioning and has no delete/public URL API. The memory adapter is test-only;
no production fallback is allowed. Original export/proposal expiry is preserved,
receipts have no implicit deletion, and known IDs never substitute for fresh
native source authorization. `workflows/operation_journal.py` persists send intent
and read-only outcome observations; it never sends an academic mutation. Neither
the journal nor Blob adapter is wired into the current public grading workflow.
Official existing-HTTP commits require the plan's explicit D3 guarantee decision.

`get_course_announcements` now always reads existing Direct HTTP in the original
`sakai/announcements.py`; the duplicate helper and selector are removed. It keeps
native message IDs/body/milliseconds, a 3650-day posting window and 50-row cap.
The public result adds explicit `coverage.complete=false`: native merged selection,
role filtering and skipped DTO/channel failures cannot certify completeness.
B2 UI list/detail enumeration remains the next completeness gate. Its native read
controller is retired locally; the announcement write controller remains.

`list_assignments` now uses existing Assignment site HTTP after a fresh effective
site-wide `asn.grade` check, independently of setup. This endpoint hydrates evidence;
only site-wide grading discovery may use the bounded response. Python discards
student bodies/notes/grades before output/hashing. Group-only TAs fail explicitly
before that request; native B3/B7 metadata-only lists remain their candidate.
`http1-` cursor/configuration observations are actor/site-bound, detect exposed
metadata changes and reject old cursors; they are not full native configuration
revisions or locks. Other grading tools still obtain their own native revisions.
Its old native discovery controller/method are retired; shared grading reads stay.
See [cohort evidence](../../docs/mcp/existing-api-migration/read-cohort-cutover-2026-10-19.md)
for role/over-fetch/completeness limits and separately required live acceptance.
The local native tip is incompatible with old announcement/discovery clients too.

`workflows/placements.py` resolves B0 from existing Site pages, checking actual
site/page/tool/placement relationships and rejecting ambiguous placements.
See the [new evidence](../../docs/mcp/existing-api-migration/read-discovery-2026-10-18.md).

## Existing announcement creation journal

The default announcement creation workflow requires a durable private store before
any HTTP request. Configure `PRIVATE_STORE_ACCOUNT_URL` and
`PRIVATE_STORE_CONTAINER` together, with optional
`PRIVATE_STORE_MANAGED_IDENTITY_CLIENT_ID` (see `config.py`; no environment-name
prefix). The configured, preexisting Azure container
must already meet D6 ownership, access, retention and backup requirements. Local
implementation does not provision a container, activate configuration or accept D6.
Without this configuration creation returns `DEPENDENCY_UNAVAILABLE`; there is no
in-memory production fallback. The memory adapter is explicitly injected in tests.

Each invocation persists intent and Sending before one native form POST. An
uncertain result remains journaled and returns `AMBIGUOUS_WRITE_OUTCOME`, with no
automatic resend. The public tool has no idempotency key: a new invocation is a new
intent and must not be used to retry uncertainty. Readback establishes an observed
matching message, not a native causal receipt. Existing optional notification
priority is preserved (`notify=o`); delivery is not verified locally.

## External captures and selected grades

The [current capture/grade evidence](../../docs/mcp/existing-api-migration/external-capture-cutover-2026-10-19.md)
records five further default replacements. `workflows/captures.py` owns conditional
external capture/manifest/proposal reads; `workflows/selected_grades.py` joins exact
native release indicators with selected Assignment observations. Captures require
the durable store configuration described above and currently contain inline bytes
only, always partial/incomplete. Pending captures never resume on reads/repeated
requests. Current attachment resources are explicitly unsupported. Proposal reads
require frozen external records; no live legacy owner import exists. MCQ evaluation
still refuses incomplete evidence. Selected grades now follow rendered native
pagination and independently read Gradebook point display scores for instructors
with full grading/item-edit authority, using exact external reference/app and UID
correlation. Comment bytes, raw precision and atomicity remain unavailable; other
Assignment graders retain explicit unavailable projection. See
[20 October readback evidence](../../docs/mcp/existing-api-migration/readback-2026-10-20.md)
and current limitations. No schema, storage provisioning, feature
activation or live acceptance follows from local implementation.

## Existing-HTTP assignment setup

The three setup tool defaults now use `workflows/assignment_setup.py` and the pure
`contracts/setup_forms.py` parser through the original Assignment facade. The setup
gate stays disabled by default. The useful subset supports individual points
assignments, draft/posted create and observed-revision draft publication, with a
configured durable journal and one native form POST. Current attachments/calendar
coordination and nondefault Gradebook release/count policies remain unsupported.
Context and link checks use the existing metadata-only item-data endpoint, with no
student grade/submission reads. Context returns labelled partial metadata; successful saves preserve the ID and
observation revision with explicit partial verification under the frozen full
Assignment contract. Do not retry create/publish because a result is partial.
See [20 October setup evidence](../../docs/mcp/existing-api-migration/setup-cutover-2026-10-20.md)
and the limitations reference for exact scope, locale/time precision, revision,
normalization, category, concurrency and acceptance restrictions. No native business
endpoint fallback, runtime activation or live acceptance follows from these tests.

### External grading operation receipts

`workflows/grading_operations.py` owns the T17 default and durable commit
journaling around the existing HTTP T14/T15 defaults. Durable Prepared/Sending precedes one
native commit; repeated IDs only read the stored outcome. Receipt reads reauthorize
current Assignment targets through existing HTTP, preserve historical/unknown
state and withhold historical Gradebook scores. They do not replay or reconcile
unknown authorship. Native legacy records are preserved but need a reviewed import.
See [operation evidence](../../docs/mcp/existing-api-migration/operation-read-2026-10-20.md).

### Existing HTTP grading writes and preparation

`workflows/grading_writes.py` coordinates native form/row observations, advisory
validation, one Direct grading POST and partial readback;
`contracts/grading_preservation.py` checks exactly preservable side fields.
T14/T15/T18 now use this actual default with no native business fallback. The
subset is one submitted individual integer-score row, English locale, editable
instructor scope, no Gradebook integration and plain ASCII side fields.
Use T19/T16 metadata and T11/T16 row observations; the retained T09 native context
revision is incompatible and its write capability hints are false. Validation
makes no academic POST. Commit requires durable external records; success remains
partial, unknown never replays, and no native CAS/atomicity/causation is claimed.
See [current evidence](../../docs/mcp/existing-api-migration/grading-write-2026-10-20.md)
and the limitations reference before adopting this subset. T09 and T20 remain.
