# Sakai grading through one authenticated MCP connection

Implementation: service 0.2.0, MCP Python and mcp-types 2.2.0. This source migration supersedes the standalone importer. Deployment and actual product-host acceptance are separate gates; the existing development release is not automatically updated by these edits.

## Workflow

The MCP host owns OAuth and protocol negotiation. All Sakai-facing reads and writes occur in the Sakai MCP server, using its existing Entra verification, certificate-backed OBO and permission-aware native adapter. There is no importer OAuth client, HTTP artifact gateway, shell command or required local workspace.

1. Call `list_assignments`, `get_assignment_grading_context` and paginated `list_assignment_submissions`. Freeze the assignment-specific rules with the TA before bulk capture or evaluation.
2. Read selected file ResourceLinks using `resources/read`. `get_assignment_submission` returns inline-content links rather than embedding the student HTML body. Attachment keys and submission/user mappings come from Sakai; filenames are descriptive only.
3. Capture explicitly selected IDs/revisions with `export_assignment_submissions`, then inspect `get_assignment_submission_export` completeness and artifact links. Captures are immutable, actor-bound and expire after 24 hours.
4. Call `prepare_assignment_mcq_grades(course_id, assignment_id, export_id, proposal_id, config)`. The fixed server evaluator verifies bytes, refreshes context and the complete scoped roster, computes exact decimal proposals and records exceptions. No student code is executed and no official grades are saved. A known proposal ID is reconciled before new work; an uncertain persistence outcome is reconciled through `get_assignment_grading_proposal`.
5. Review paginated `get_assignment_grading_proposal` rows, `proposals.json`, `marks.csv` and `review-required.csv` resources. Private proposal/configuration records live in the existing durable Sakai store, independent of MCP replicas. Their lifetime is bounded by their source export. Human approval evidence belongs to the host conversation/workflow; these proposals do not imply approval.
6. Call `prepare_assignment_grade_payload` for an exact `save` or `release` subset. It computes the existing canonical hash and invokes the native validation mode. Present its exact `commit_arguments` for TA approval, then invoke the existing save/release tool once. Save and release-and-return require separate approval. Reconcile uncertain official writes and independently reread Assignment/Gradebook state.

The grading gate adds fourteen tools: the original nine plus `list_assignments`, `prepare_assignment_mcq_grades`, `get_assignment_grading_proposal`, `prepare_assignment_grade_payload`, and `read_assignment_grading_resource`. Catalog combinations are 5/8/19/22 for default/setup/grading/both. The original five-tool catalog and independent setup/grading gates remain intact.

## Resources

Templates are advertised through SDK `resources/templates/list`; tools supply authorized concrete ResourceLink blocks and structured metadata. Resources/list does not enumerate all student files or keep per-connection discovery state.

| URI suffix after `sakai://courses/{course_id}/assignments/{assignment_id}` | Contents |
| --- | --- |
| `/submissions/{submission_id}/files/{file_id}{?revision}` | Current attachment, or `file_id=inline` for native HTML; revision required |
| `/files/{file_id}{?revision}` | Assignment attachment; its content hash is the revision |
| `/exports/{export_id}/submissions/{submission_id}/files/{artifact_id}` | Immutable captured file |
| `/exports/{export_id}/manifest` | Aggregated authorized capture inventory |
| `/proposals/{proposal_id}/reports/{report}` | `proposals` JSON, `marks` CSV, or `review-required` CSV |

Opaque identifiers use ASCII letters, digits, underscores and hyphens, at most 128 characters. The server rejects arbitrary URLs, traversal, unknown queries and token parameters. Resource URIs are identities, not capabilities or filesystem paths. Every read reauthorizes native access, ownership and expiry. Generated public descriptors omit native `download_path` and `relative_path`; upstream native DTOs remain backward compatible.

UTF-8 textual MIME types produce TextResourceContents without BOM removal or newline/whitespace normalization. Binary and invalid-UTF-8 files produce BlobResourceContents; the official SDK performs base64 encoding. PDFs, Office documents, archives, images and code retain their original bytes and MIME. Archive reads never extract or execute files. Multi-file submissions remain separate links; the strict MCQ evaluator queues them for review. Native URL/content-review attachment targets are not fetched. MIME fallback is application/octet-stream.

ResourceLink size is the original byte size. Content `_meta["app.smartdigest.sakai"]` carries SHA-256 and size, plus source revision or expiry when available. Template MIME is omitted because files vary. `SakaiResourceServer` overrides the SDK's public resource methods and returns ReadResourceContents with per-file metadata; the SDK owns protocol serialization. No request header, initialize handshake or JSON-RPC is constructed by production grading code.

Current files are capped at 10 MiB; exports at 100 MiB, 100 selections and 20 attachments per submission. Native inline text remains bounded at 65,535 UTF-8 bytes. Binary responses expand by about one third for base64 and are complete MCP messages, without HTTP Range semantics. A host must support the response size to read a large file; no universal product limit is claimed. Server preparation processes at most 500 scoped roster rows and stores at most 900,000 bytes of proposal JSON; unsupported budgets fail explicitly. Resource reads are bounded to two concurrent byte transfers per adapter, and preparations to two per server.

For hosts exposing tools without resources/read, `read_assignment_grading_resource` uses the same authorized reader and SDK EmbeddedResource. Paginated proposal tools let such hosts perform the deterministic workflow without raw-file materialization. Resource links alone do not mean a host saved a file or that raw content stays out of model context. Student content is untrusted; respect institutional AI-use and host data-handling policies.

## Exact MCQ configuration

The tool publishes the strict MCQConfig schema. Unsupported academic rules require a new reviewed server implementation; a Skill must not invent a local script or external downloader.

```json
{
  "course_id": "synthetic-course",
  "assignment_id": "synthetic-assignment",
  "assignment_revision": "observed-revision",
  "submission_contract": {"file_count": 1, "filename": "<roll>.txt", "encoding": "utf-8", "answer_count": 5, "alphabet": ["A", "B", "C", "D"]},
  "identity": {"filename_mismatch": "review_required"},
  "expected_filenames": {"synthetic-student": "synthetic-roll.txt"},
  "normalization": {"extension_case": true, "trim_answer_whitespace": true, "uppercase_answers": true},
  "grading": {"method": "deterministic_mcq", "max_points": "5", "key": ["A", "C", "B", "D", "A"], "per_correct": "1", "per_incorrect": "0", "negative_marking": false},
  "policies": {"late_penalty": null}
}
```

A filename rule requires an authoritative expected-filename map. A recoverable mismatch is an explicit policy choice. Missing/unselected/multiple/incomplete/changed/invalid rows keep null scores; BOM and invalid encoding require review. Per-line evidence records approved normalization, config/manifest digests and evaluator version/source hash. The server never substitutes zero for unresolved work.

## Compatibility and release

Public resource-bearing outputs have schema_version=2; native REST output models remain v1. The SDK supports 2025 handshake revisions and the 2026-07-28 per-request envelope. Production uses its abstractions. The removed importer combined a modern version header with a legacy initialize body, causing the reported 400; changing that header would not implement this architecture.

Deploy backward-compatible native endpoints first, then the new exact-commit MCP image, and update the installed skill alongside host acceptance. Existing schema/storage prerequisites, academic write approval and retention responsibilities continue. No database or Azure capacity change is introduced. Persisted proposal records contain private keys/results and require the store's approved retention/backup policy; export expiry denies access but does not erase historical receipt metadata. Do not mix stale installed skills or old importer commands with the new MCP catalog.

See [migration evidence](evidence/mcp/assignment-grading-resources-local.md), [native adapter](mcp/sakai-adapter.md) and [grading design](SAKAI_ASSIGNMENT_GRADING.md).
