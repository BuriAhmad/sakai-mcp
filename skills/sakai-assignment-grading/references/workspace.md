# Server grading, resources and reports

All Sakai-facing functionality uses the host's existing authenticated MCP connection. No separate login, importer, Python command, token cache access or physical local workspace is required.

Read list_assignments and grading context, resolve authoritative IDs, and freeze the academic plan before bulk retrieval. Listing/detail tools return metadata and ResourceLinks for attachments and native inline HTML. Read links using resources/read. A tools-only host may invoke read_assignment_grading_resource, which returns SDK EmbeddedResource through the same connection. Resources are server identities; receiving a resource does not imply it is saved to a host filesystem.

Capture explicit submission IDs/content revisions using export_assignment_submissions and inspect get_assignment_submission_export. Captured file resources preserve byte hashes, sizes, submission/user mappings and expiry. Incomplete capture is review-required. Files are individually linked; archives are not extracted and URL attachment targets are not fetched.

Call prepare_assignment_mcq_grades(course_id, assignment_id, export_id, proposal_id, config). Config must follow the published strict schema: assignment_revision; one UTF-8 TXT file; answer_count/alphabet/filename rule; expected_filenames keyed by authoritative Sakai user ID; explicit identity.filename_mismatch; normalization booleans; deterministic_mcq key/per_correct/per_incorrect/max_points/negative_marking; policies.late_penalty=null. Unsupported policies require another reviewed server implementation. Never infer institutional roll numbers from Sakai EIDs. Changing rules/evidence requires a new proposal ID. Reconcile an uncertain prepare result through get_assignment_grading_proposal before new work.

Review get_assignment_grading_proposal pages and the proposals JSON, marks CSV and review-required CSV resources. Missing, unselected, malformed, changed and unresolved rows have null scores. The fixed evaluator records per-line evidence and config/manifest/evaluator hashes. No official grades are written by preparation. No student code executes.

Call prepare_assignment_grade_payload for an exact save or release subset. It computes the canonical payload hash and performs native validation, returning commit_arguments. Present those exact rows, scores, feedback and revisions for TA approval before the separate save or release tool. Release-and-return requires its own approval. Changed payloads invalidate approval; uncertain official outcomes require get_assignment_grading_operation plus authoritative readback, never blind retries.

Resources and proposals expire with the source export (24 hours). Retain decisions/receipts in the host's authorized workflow; do not assume indefinite server evidence retention or a universal host filesystem capability. Respect institutional AI-use and privacy policy when a host puts resources into model context.
