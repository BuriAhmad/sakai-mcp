# Recipe: assignment with imported student submissions

Scope: individual, attachment-based synthetic Assignments-tool fixtures. The 13 October 2026 import verified a point assignment with 79 submitted files and one deliberately missing student, finally closed and entirely ungraded/unreturned. Group submissions, anonymous grading, historical attempts and exact historical timestamps need further research.

## Preflight

Read the general workflow and recorded lessons. Inspect the live Assignments placement and eligible Student roster; exclude graders/instructors using native eligibility rules. Resolve canonical EIDs to internal IDs and confirm each synthetic student's enrollment and submission permission. Reuse existing accounts unless creation is requested.

Separate student-facing brief/PDF from private answers, expected scores and ground truth. Preserve intentional wrong filenames, unsupported formats and malformed text. Expected scores are assertions, not grades to write.

Define submission type, grade model/points, instructions, publication, open/due/accept-until dates, resubmission policy, Gradebook relationship and notifications. Inspect defaults: a standalone fixture need not create Gradebook, Calendar or announcement objects.

## Create and attach student-facing materials

Use supported setup tools when available/authorized for this operation, or the verified native instructor workflow. The historical importer used an instructor session and `newAssignmentForm`, discovering actions/fields from the page. Source breadcrumbs: `apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/tool/AssignmentAction.java` and templates under `apps/sakai/assignment/tool/src/webapp/`.

Reconcile existing assignments before creating. Record the new ID/native reference immediately; verify course, author, title, instructions, scale and lifecycle. The observed form used submission-type `5` and point-grade `3`; check current form/source enums before reusing those historical values.

The historical PDF path was instructor `POST /direct/content/direct-upload.json` with multipart `upload` and `context=<site-id>`. It returned a URL; the assignment reference used `/content` plus the path after `/access/content`. Resource upload did not attach it to the assignment. The native editor persisted that reference through `attachments`. Verify current provider/form contracts, preserve the returned reference for reconciliation, and test Student downloads: instructor access to hidden upload storage is insufficient.

## Import through each student's actual workflow

Authenticate each authorized synthetic student through native `POST /api/login`, retain their cookie jar, and verify `/direct/user/current.json` resolves to the intended internal ID. Don't substitute instructor/admin authorship.

Discover the placement from live configuration. The observed navigation was:

```text
/portal/tool/<placement-id>?assignmentReference=/assignment/a/<site-id>/<assignment-id>&sakai_action=doView_submission
```

From `addSubmissionForm`, preserve hidden fields and discover the file action. The verified single-file sequence was:

1. Upload with the rendered `doAttachUploadSingle` action and multipart `upload`, original filename and detected content type.
2. Check attachment/form state. This stage can be a draft.
3. Submit with `option=confirm`; check Submission Confirmation contains the intended file.
4. Use the new confirmation form's fields and `option=post` to commit.
5. Read the submitted record/attachment, compare actual bytes/hash, and checkpoint ID plus verified lifecycle flags.

Inspect current controls instead of replaying this sequence into an already submitted or differently configured assignment. Verify/resume matching records without overwriting them. Leave the intentional missing student without a submission.

## Arrange a closed fixture

For requested already-submitted work with an ended deadline, a temporary open window may be used within that authorized fixture arrangement. Native submissions get actual import timestamps. After all files are verified, set due/accept-until after the latest submission and before the current time in the requested timezone. Check both UTC instants and displayed local times; never copy the old run's dates.

If exact historical timestamps are required or the requested deadline predates actual imports, this method does not satisfy the request. Research a supported migration mechanism; don't silently backdate records or patch database rows.

Past due/close edits returned a warning/confirmation form on the first POST. Detect that specific warning, preserve the new form state, confirm once and read back. This known second stage is not permission to replay arbitrary ambiguous writes.

## Acceptance

- Exact eligible roster and submitted/missing sets; no TA/instructor submissions or missing-student placeholders.
- Intended attachment names/types/sizes and verified bytes; submission timestamps before the final deadline when required.
- Requested publication, dates, resubmission policy, author, points and links. Committed submissions rather than drafts; graded/released/returned flags match the request.
- Instructor list/detail and complete grading roster. Use `get_assignment_grading_context` and paged `list_assignment_submissions` when enabled/authorized; don't assume legacy Direct JSON's embedded `submissions` is complete.
- Navigate as Student, request inner `/portal/tool/<placement-id>?panel=Main`, check substantive assignment/attachment content, and download the submitted file and PDF. Exercise distinct exceptional formats as needed.
- If TA usability is in scope, test that TA's delegated identity. Instructor success plus configured `asn.grade` doesn't prove another account's OAuth path.
- Report separate local-package, live-record, UI and download checks, tested actors and remaining limits.

## Reuse limits

Ignored `deployment/artifacts/cs210-mcq-import/` scripts are historical evidence, not maintained import tools. They contain fixed IDs/dates, role assumptions and outdated Direct verification. Don't run them unchanged for another package. Don't borrow a historical client's refresh-token cache as general authentication; use the intended actor's approved current connection/credentials.

For marking after import use `sakai-assignment-grading`. Seeding completed submissions does not authorize writing expected scores or returning grades.
