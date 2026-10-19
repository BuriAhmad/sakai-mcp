# General workflow and recipe extension

## Establish the target and intended result

Record the target Sakai origin and site IDs, requested objects, actor roles, source package, final state and expected counts. A public MCP endpoint can be backed by the development VM; the word “prod” alone does not identify a different target. Use live inventory rather than deployment-history documents for current state.

Read the root/scoped guides, `docs/REPOSITORY_STRATEGY.md` and relevant sections of `docs/SAKAI_INTEGRATION_GUIDE.md`. `./sakai status` is read only. An import does not by itself request a VM start, database migration, feature enablement or code deployment. If one becomes necessary, inspect existing authorization and prepare the concrete change under the repository's runtime/release rules.

Define the final state before writing: published/draft, open/closed, submitted/draft, graded/ungraded, returned/unreturned, visible/private and linked/unlinked. Preserve unrelated existing state. Do not create members, Gradebook items, announcements or notifications just because an interface defaults to doing so.

## Preserve and validate the package

- Copy the source into `deployment/artifacts/<run-name>/` or another explicitly ignored location. Confirm both `git check-ignore -v <path>` and `git ls-files <path>`; ignoring does not untrack existing files. Use restrictive permissions for private evidence.
- Inspect archive entries before extraction: reject traversal, absolute destinations and unsafe links. Preserve original bytes and filenames. Do not silently repair deliberately malformed fixtures.
- Validate unique identities/object keys, file mapping, counts, intentional omissions, encodings/types, sizes and hashes. Keep expectations and answer keys private. Label local validation as not yet verifying the live roster or permissions.
- Compare the source roster with the live roster. Distinguish internal Sakai ID, canonical EID, Entra identity, site ID, tool registration ID and placement ID. Discover native roles instead of assuming `TA` is a valid role ID.
- Reconcile collisions and provenance. A matching title is a candidate to inspect, not permission to overwrite. Do not reset passwords or remove unrelated members to make a fixture match.

Keep a private plan/checkpoint with operation, actor, site/object IDs, expected state, source hashes, observed result and verification status. Never print credentials, cookies or tokens, or commit them to evidence.

## Choose and prove an interface

Prefer a supported import or existing permission-aware endpoint that represents the requested state. The integration guide records successful SOAP, EntityBroker, tool API and native form paths. A source handler alone does not establish a working remote contract.

Native seeding may use authorized sandbox credentials and real synthetic actor sessions. Normal MCP calls use delegated identity; an MCP bearer token is not a universal credential for legacy endpoints. Do not add admin fallback, arbitrary impersonation or broader SOAP host/login access to make an import work.

For native form automation, discover the current placement, action, file field, hidden values and confirmation stages from the rendered page. Preserve session/CSRF state, resolve relative URLs against the verified origin and reject foreign destinations. HTTP 200 can be a validation form, login page, draft, warning or blank tool body.

Prove one representative object through final commit and readback before bulk work. Exercise intentional exceptional cases when their behavior differs. Include a pilot in final totals even if it has a separate checkpoint.

## Import with reconciliation

Persist known IDs immediately. Verify writes before dependent operations. Parallelize only independent actors/objects with separate sessions, bounded load and a single safe checkpoint writer; don't share mutable forms/cookies across students.

Do not blindly retry a timeout, lost response or ambiguous create. Read back by known ID and natural/provenance keys, inspect duplicates and distinguish confirmed success, confirmed failure and unknown outcome. Resume verified objects without replacing them. Missing submissions remain absence, not empty placeholder uploads.

For denial, verify the actor and native permission for that operation. Course visibility does not imply setup, grading or submission authority. Don't change role permissions merely to suppress `FORBIDDEN` unless that change is authorized and appropriate.

## Verify and report

Compare membership, counts, lifecycle flags, timestamps, links and file names/bytes. Also verify the actor-facing workflow: instructor view, relevant TA view, student list/detail, download and expected denial. Choose representative users and distinct fixture formats; expand checks when a failure or known risk warrants it.

Check portal navigation and the inner tool body. A 200 response missing substantive assignment content fails the page check. Cross-check an empty/partial API collection with its completeness contract and an independent authoritative route before declaring data lost or importing again.

Produce private detailed evidence and a scrubbed summary. State checks, tested identities and remaining limits. Recount ignored files at reporting time. Successful provisioning does not prove MCP client authentication, grading/release or host approval behavior.

## Research and extend when no recipe matches

1. Define the exact object/lifecycle using a native UI example. Identify Java services/models and current authenticated handlers under `apps/sakai/` with `rg`.
2. Read source contracts for permissions, identifiers, side effects, transactions and readback. Consult live WSDL for SOAP. Use authoritative external docs for facts not established locally; record version/source revision.
3. Label findings **live verified**, **source confirmed**, **inferred** or **unverified**. One guessed route failing doesn't prove there is no API; finding a handler doesn't prove it is usable.
4. Run bounded read-only probes, then one authorized synthetic pilot. Reconcile and check actual user behavior before scaling. Prepare necessary code changes through the existing release path with its authorization boundaries.
5. Add `references/<specific-data-kind>.md` covering prerequisites, interface/source locations, actors/IDs, write stages, side effects, recovery and acceptance. Route to it from `SKILL.md`; add new interface facts to the integration guide.
6. Add scrubbed lessons for material failures: symptom, actual cause or uncertainty, correction, evidence, reusable decision and scope. Separate incidents from preventive advice. Keep datasets/logs/credentials and one-off scripts private unless generalized and reviewed.
7. Validate frontmatter/links, update the installed copy from the canonical repository skill, and report what was learned. Don't accumulate untested recipes or promote research candidates to proven procedures.
