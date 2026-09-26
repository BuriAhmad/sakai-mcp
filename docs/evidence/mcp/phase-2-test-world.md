# Phase 2 authorization test world — 2026-09-26

Status: **PASS — baseline fixture and authorization matrix verified**. No user IDs, credentials, site IDs, grades, or submission content are included.

The existing `SeedSitesAndUsersJob` source at `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/SeedSitesAndUsersJob.java` creates randomized student/instructor accounts, course sites, memberships, gradebook items/records, conversations, and resources. It does not create announcements, assignments, or assignment submissions. The job was previously run twice according to `docs/DEPLOYMENT_STATUS.md`.

Read-only queries against the live Sakai schema during this inventory found:

| Fixture inventory | Count |
| --- | ---: |
| Sites | 577 |
| Users | 205 |
| Registered student accounts | 200 |
| Instructor/maintain accounts | 2 |
| Instructor site memberships | 5 per instructor |
| Sites shared by both instructors | 0 |
| Seeded sites with at least two registered students | 10 |
| Gradebooks / grade items / grade records | 10 / 110 / 5,200 |
| Announcements | 0 |
| Assignments / submissions | 0 / 0 |

This supports selection of two separate instructor/course contexts and two students in one course, but it does **not** establish an authorization matrix yet. The missing announcement, assignment, and submission fixtures must be added using normal Sakai mechanisms, and actual permissions and visibility must be tested under the chosen users. The generated account identifiers and any login material are intentionally absent from repository evidence.

## Fixture construction update

The third normal `SeedSitesAndUsersJob` run completed on 2026-09-26. Its temporary autorun and deterministic sandbox-password properties were removed from `local.properties`. Read-only schema counts afterward showed **586 sites, 306 users, 300 registered students, and 3 maintain/instructor accounts**. The new instructor owns five additional, separate seeded course sites. This supplies a second accessible instructor context without changing any existing user's credential or membership.

Both selected course sites now have Announcements and Assignments enabled through Site Info → Manage Tools. Normal UI workflows produced **three visible synthetic announcements and two posted assignments in each course**, and **three distinct student submissions**: two in Course A and one in Course B. The Assignments tool works after the tracked Java module correction. The failed first post's incomplete untitled row was moved to Trash through the normal UI and is not counted. See [`phase-2-java-runtime-prerequisite.md`](phase-2-java-runtime-prerequisite.md).

The chosen Course A and Course B have separate instructors and cohorts. Read-only realm checks showed instructor permission for `annc.new` and `asn.grade`; students had `annc.read`, `asn.submit`, and `gradebook.viewOwnGrades`, without `annc.new` or `asn.grade`. Instructor A has no membership in Course B. A seeded Gradebook item was initially hidden from students; its standard “Release item to students” setting was enabled for one item to exercise student grade visibility.

| Baseline action | Result | Evidence observed in Sakai 25.2 UI or realm |
| --- | --- | --- |
| Student A and Student B list their own sites | ALLOW | Each signed in and saw Course A in the site list. |
| Student A and Student B view own Course A grades | ALLOW | Each Gradebook report named only that student and showed a distinct released score. |
| Student A views Student B grades | NOT EXPOSED | Student Gradebook has no student selector or target-user control; the report is bound to the logged-in student. The MCP contract must also enforce this server-side. |
| Student reads privileged Course A submissions | DENY | Student assignment UI has no Grade/submission-list action; realm lacks `asn.grade`. |
| Student creates a Course A announcement | DENY | Student announcement UI has no Add action; realm lacks `annc.new`. |
| Instructor A reads Course A submissions | ALLOW | Instructor UI listed both distinct submissions and opened one submission. |
| Instructor A reads Course B submissions | DENY | Direct Course B portal navigation returned “Site Unavailable”; instructor is not a member. |
| Instructor A creates Course A announcement | ALLOW | Three visible announcements created in Course A through the ordinary UI. |
| Instructor A creates Course B announcement | DENY | Direct Course B portal navigation returned “Site Unavailable”; instructor is not a member. |
| Instructor B creates Course B announcement | ALLOW | Three visible announcements created in Course B through the ordinary UI. |

This is a baseline UI and realm matrix; endpoint-level negative tests remain required in later phases. Assignment A has one returned submission and one ungraded submission. An attempted numeric grade release did not appear in the student Gradebook report, so that attempt is not counted as a numeric grade fixture. The released seeded Gradebook item supplies verified distinct own-grade results.

One generated sandbox instructor authenticated successfully through the existing Sakai `/api/login` endpoint (HTTP 200). With that session, `/api/users/me/sites` returned five course sites. This confirms the selected account can exercise the ordinary password-login/current-user WebAPI path; it does not prove announcement or assignment permissions. No session cookie or credential is recorded here.

Next verification: in Phase 3, trace the internal permission and release checks that enforce this UI matrix. Later endpoint tests must include explicit other-student and cross-site denial probes. Do not infer permission from a role label or table membership alone.

The earlier browser-credential approval blocker was resolved by the user's subsequent explicit authorization to create test data and use generated sandbox accounts. The first inventory session created no fixtures; its temporary authenticated CLI cookie was deleted and the VM was returned to deallocated afterward. Fixture construction now follows [`phase-2-fixture-design.md`](phase-2-fixture-design.md), with the permission matrix still required before Phase 3.
