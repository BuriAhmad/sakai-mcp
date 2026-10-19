# Recorded failures and lessons

Sources: synthetic semester seeding in `docs/SAKAI_INTEGRATION_GUIDE.md` and 13 October 2026 assignment work in `docs/evidence/mcp/assignment-grading-release.md`. Resolve these paths against the repository. Observations apply to those interfaces/source revisions; they aren't universal Sakai guarantees.

## Observed incidents

| Symptom or mistake | Finding and correction | Future decision |
| --- | --- | --- |
| Final import report said PASS while the student's page was blank. Records/downloads were checked; the page wasn't. | A portal shell and 200 response hid the failed inner tool. | Define acceptance first; verify the actual student assignment page, substantive inner body and links. Say what each PASS covers. |
| Attachment-bearing page raised `HibernateException: Unable to resolve owner of loading collection AssignmentSubmission.attachments`; older assignment worked. | Detached Hibernate collection failed in rendering. Evidence was hydrated inside a read-only transaction and the student page switched to that load. | Reproduce the actual fixture and inspect the exact server exception. Don't reimport missing-looking content or alter database rows as a workaround. Use normal code/release paths for application defects. |
| After restart, Direct assignment JSON embedded zero submissions, while the grading endpoints returned all 79. Verifier retries failed on the empty field. | The legacy representation wasn't reliable for complete roster readback; records remained intact. | Check dedicated roster completeness/pagination or another authoritative route before declaring loss or importing again. Keep discrepancies explicit. |
| Grading read reported 81 expected and two missing instead of 80/one. | Instructor appeared in candidate users. Fix required active `asn.submit` membership without `asn.grade`. This was a grading-read bug, not an import duplicate. | Compare exact Student eligibility, not all members or a raw candidate API. Exclude graders/instructors from missing counts. |
| Past-date edits returned a warning page before persisting. | HTTP success did not mean requested dates were saved. | Confirm the specific warning using returned form state and read back both due and accept-until; don't blindly resend original requests. |
| Release preflight rejected 11 GiB available (12 required); VM had also been auto-deallocated. | Builds depend on current disk/runtime state; pushes don't deploy. | Within authorized deployment scope inspect preflight, reclaim only generated outputs/old transfer files/cache, and preserve deployed/rollback/data files. Don't recreate a VM for stopped services or disk shortage. |
| Initial SOAP encoder assumed document-wrapped messages; live binding was RPC/literal. Text `None` was also wrong for recurrence. | WSDL parameter/types and XML nil semantics differed from guesses. | Read source/live WSDL; prefer a WSDL-aware client and encode typed values/`xsi:nil` correctly. |
| Mixed-case external EID passed login but failed delegated exact identity comparison after Sakai lowercased it. | Canonical stored EID was needed for external mapping. | Read stored identifiers; don't infer from UPN/display name or weaken bearer checks. |
| Native site creation added the administrator as an extra Instructor. | Creation changed the intended roster. | Compare complete membership after creation and reconcile only authorized fixture side effects. |
| TA listed courses but assignment setup context returned FORBIDDEN. | Course visibility, setup and grading permissions differ. | Choose grading tools for TA marking, inspect native permissions and test that TA identity. Don't grant broad setup rights just to make grading work. |

## Demonstrated distinctions and safeguards

These are operational lessons, not claims that each caused a failure:

- The first pilot uploaded a file; later `confirm` then `post` committed it. Upload isn't submission. The pilot plus 78 bulk checkpoint rows yielded 79 submitted records; checkpoint length alone wasn't the total.
- Resource upload and assignment attachment are separate. The hidden instructor resource needed the assignment reference and Student download verification.
- Wrong filenames, a PDF exception and malformed text were intentional. Repairing them changes the dataset. Answer keys and expected scores remained private and weren't written as grades.
- A temporary open window followed by closure after actual timestamps makes a closed current fixture, not historical submissions.
- Native forms included unrelated Gradebook, Calendar, announcement and notification defaults. Inspect and set these according to requested scope.
- Instructor checks passed, while the TA's OAuth path and live official save/return weren't accepted end to end. Installed tools and local tests aren't a blanket PASS.
- Raw evidence/fixtures remained ignored and had zero tracked files. Recount after work; added evidence or caches can change the old “122 files” figure.

## Add future learning

Record date/source version, requested object/lifecycle, symptom, actual cause or uncertainty, correction, evidence, reusable decision and limits. Keep identities, credentials, uploads and raw logs private. Add a new recipe once repeatable behavior is verified; label source-only research as such. Prefer a narrow supported lesson over a new universal prohibition.
