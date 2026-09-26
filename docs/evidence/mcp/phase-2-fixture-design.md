# Phase 2 sandbox fixture design

This is the intended **synthetic** Sakai test world, to be built and verified through ordinary Sakai UI/services before the Phase 2 gate passes. Existing seeded identities, memberships, and gradebook records should be reused where they fit; no credentials or generated user IDs belong in repository evidence.

| Context | Intended fixture |
| --- | --- |
| Course A | Existing seeded course site, used as **Introduction to Data Analytics — Autumn 2026** in synthetic content; Instructor A, Student A, Student B |
| Course B | Separate existing seeded course site, used as **Research Methods in Education — Autumn 2026** in synthetic content; Instructor B, at least one student; Instructor A has no privileged membership |
| Announcements | Three per course: welcome/syllabus, week-two activity, and assessment reminder. Mix visible and delayed/draft visibility only if Sakai's normal controls make the behavior testable. |
| Assignments | Two per course. Course A: *Dataset Profile and Quality Audit* and *Exploratory Analysis Brief*. Course B: *Literature Search Log* and *Survey Design Critique*. Use normal opening/due dates in October 2026 and normal site permissions. |
| Submissions | At least two distinct student submissions in Course A and one in Course B, with short synthetic text and no real personal data. One graded and one ungraded Course A submission would exercise both states. |
| Existing grades | Keep the existing seeded gradebooks/records; verify Student A and B each see their own records and cannot retrieve each other's by forged IDs. |

Proposed announcement text is mundane course information: where to find the syllabus, when a lab or seminar meets, and when a draft is due. Submission text will be short original fixture prose with no personal information. Use distinct titles and timestamps so pagination and duplicate-write tests can identify the intended object. Keep an internal private mapping of the selected sandbox accounts/site IDs only for test execution; commit only sanitized role labels and result categories.

The built-in job gives course sites generated identifiers and titles. Keep those source-created titles rather than changing seed data solely for display. Course labels here describe the synthetic teaching context and appear in announcements and assignments.

Verification before PASS: inspect actual site roles and Sakai permissions; prove Instructor A is denied in Course B; prove a student is denied announcement creation and privileged submission reads; prove the course/assignment relationship; confirm created fixtures in normal Sakai UI; record the number of objects and sanitized allow/deny outcomes.
