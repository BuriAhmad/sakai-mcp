# Workspace and deterministic MCQ use

Use an owner-only directory outside Git, one directory per grading run. Preserve `grading-plan.md`, private `grading-config.json`, assignment/key/rubric sources, immutable raw files, manifest, normalized working copies, scripts/version hashes, results, TA decisions and write receipts. A checksum failure stops affected processing; use a new run for changed evidence/configuration.

From an installed project MCP package, the trusted importer is:

```sh
python -m sakai_mcp.grading_workspace import-export PRIVATE_RUN PRIVATE_LOGIN_CONFIG COURSE_ID ASSIGNMENT_ID EXPORT_ID
```

The login config contains nonsecret `tenant_id`, registered institutional public `client_id` and `mcp_origin=https://mcp.smartdigest.app`. The CLI opens the institution's interactive OAuth login and keeps tokens in memory. No bearer token argument, environment variable or console output is used. Register the public client's loopback callback/grants through the institution's existing authorized identity process; this Skill cannot supply a missing grant.

The importer also saves authoritative `context.json` and complete scoped `roster.json`; changed academic evidence requires a new run. The manifest preserves original name/MIME/size/hash and Sakai submitter mappings. Artifact paths are generated IDs, not original filenames; no archive extraction or untrusted code runs. The importer verifies every selected artifact, supports per-file retry and never overwrites differing raw bytes. Keep missing/unselected roster rows in the review queue.

For the strict MCQ path:

```sh
python -m sakai_mcp.grading_workspace mcq PRIVATE_RUN PRIVATE_CONFIG
```

Configuration follows the design's JSON example: course/assignment identity; `submission_contract` with one file, UTF-8, answer count/alphabet and filename rule; normalization case/whitespace rules; `grading.method=deterministic_mcq`, complete key, per-correct/per-incorrect/max, no negative marking; explicit policies. Provide authoritative `expected_filenames` keyed by Sakai user ID when a filename convention must be checked; never assume Sakai EID equals institutional roll number. `identity.filename_mismatch=recoverable` must be an explicit plan decision. No policy/key is invented by the utility.

Outputs are canonical typed `results/proposals.json`, review `marks.csv` and `review-required.csv`. No grades are written. The utility records config/manifest/script hashes and line-level comparison evidence. Wrong count/format/alphabet, BOM, unreadable text, conflicting files and incomplete capture are review-required with null score. Late penalties outside the supported explicit procedure require another reviewed deterministic implementation. Semantic criteria are handled separately with fixed rubric versions and human review.

For write payload hashing use `sakai_mcp.grading_workspace.payload_hash(kind, course, assignment, configuration_revision, grades)`. Hash covers canonical UTF-8 JSON, sorted keys and submission/user rows, exact decimal strings, revisions and feedback patches; excludes mode, operation ID and the hash itself. Use a new UUID for each newly approved payload; reuse the known ID only to reconcile its same payload. Refresh grade revisions after save before planning return.
