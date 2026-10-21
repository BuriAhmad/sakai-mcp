# Sakai evidence access and client assessment

**Current tool-development direction, 21 October 2026:** MCP retrieves authorized Sakai evidence and saves/returns explicitly approved grades through existing HTTP interfaces. The client Skill chooses the assessment method. `prepare_assignment_mcq_grades` and its server evaluation/proposal-creation path are removed locally at the user's request. This supersedes the earlier server-MCQ workflow; dated release evidence and frozen baselines remain historical and unchanged. Nothing was deployed or activated.

## Workflow

Resolve authoritative IDs using assignment/context/submission reads. Agree the rubric/key, policies and assessment approach before bulk retrieval. Methods can include direct key checks, supplied tests, optional assignment-specific scripts in the user's chosen workspace, permitted rubric-based AI assessment or human review. Student code execution needs a separately approved isolated runner.

Use the existing authenticated MCP connection for Sakai. Read ResourceLinks using resources/read, or read_assignment_grading_resource for a tools-only host. Export explicit submission IDs/content revisions and check capture status and hashes. Incomplete listings do not prove missing students; incomplete content cannot be scored as zero. Current migrated attachments remain unsupported. Captures can preserve selected inline HTML while reporting partial coverage.

Resources carry identities, MIME, sizes and SHA-256 metadata; SDK text uses UTF-8 without BOM/newline normalization and blobs use base64. This protocol does not itself save files to the client workspace. If local processing is chosen, use a verified byte-preserving host file path and compare resulting hashes/sizes; otherwise report the delivery gap. No secondary OAuth client, token extraction, browser-cookie download or server write to a client path is introduced. Actual intended-CLI file delivery remains unproven; an SDK resource roundtrip alone cannot establish it.

Produce local/host proposals and an exception queue with evidence and unresolved scores left null. `prepare_assignment_grade_payload` computes the canonical hash and performs advisory validation on explicit rows; it does not evaluate work. Present its exact commit_arguments for approval, then call save_assignment_grades once. Prepare and approve release_assignment_grades separately after verified saves. Reconcile unknown outcomes using get_assignment_grading_operation and independent get_assignment_grades readback; do not replay uncertain writes.

Current writes support one current submitted individual, integral displayed points, English native forms and no Gradebook link. There is no native CAS, cross-request transaction or general bulk-write guarantee. Side-field preservation and observation guards can reject otherwise valid assignments. Full capability/role acceptance remains open.

## Catalog, compatibility and retention

The local gate combinations are **5/8/18/21** tools (default/setup/grading/both), with five resource templates when grading is enabled. The default five and independent disabled-by-default gates remain unchanged. Thirteen optional grading tools remain. `get_assignment_grading_proposal` and `/proposals/{proposal_id}/reports/{report}` remain compatibility readers for existing records; new server proposals cannot be created. Existing actor/source authorization, expiry and frozen report bytes remain. No stored proposals, captures, receipts or schema were deleted, relocated or converted; native-format historical records are not automatically imported into the external store.

Other resource families cover current submission files, assignment files, captured files and export manifests; advertisement does not establish attachment availability. Traversal, arbitrary URLs and token parameters remain rejected. External records require configured private conditional storage. Historical native storage/lock claims do not describe the migrated writer.

The historical catalog/evaluator/report fixtures remain byte-identical. The small `local-assessment-catalog-v2.json` amendment documents the one intentional removal and preserves every remaining tool description/schema. Two old gate-count assertions failed in the fresh suite and are recorded without repair. See [research, checks and remaining gates](mcp/existing-api-migration/local-assessment-correction-2026-10-21.md).

This native tool tree excludes the separate authentication/session integration required by the Python flow protocol. Exact route/filter reach, real-role authorization, concurrent-user isolation, attachment binding/integrity and intended-host file delivery need separately assembled acceptance. No auth changes or runtime actions are included here.
