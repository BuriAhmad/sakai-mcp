# Standard course-site defaults

This document records the course layout verified against the Sakai 25.2 source in `apps/sakai/` and the tracked setup that makes it reproducible.

## Sakai 25.2 tool mapping

| Navigation label | Registration/mechanism | Source evidence |
| --- | --- | --- |
| Overview | Worksite Setup special `home` page, with the `SitePage.IS_HOME_PAGE` property | `SiteAction.TOOL_ID_HOME`; `SitePage.isHomePage()` |
| Syllabus | `sakai.syllabus` | `syllabus-app/.../sakai.syllabus.xml` |
| Calendar | `sakai.schedule` | `calendar-tool/.../sakai.schedule.xml` |
| Announcements | `sakai.announcements` | `announcement-tool/.../sakai.announcements.xml` |
| Resources | `sakai.resources` | `content-tool/.../sakai.resources.xml` |
| Conversations | `sakai.conversations` | `conversations/tool/.../sakai.conversations.xml` |
| Polls | `sakai.poll` | `polls/tool/.../sakai.poll.xml` |
| Discussions | `sakai.forums` | `messageforums-app/.../sakai.forums.xml` |
| Assignments | `sakai.assignment.grades` | `assignment/tool/.../sakai.assignment.grades.xml`; `sakai.assignment` is an obsolete ordering entry and has no registration in this source tree |
| Tests & Quizzes | `sakai.samigo` | `samigo-app/.../sakai.samigo.tool.xml` |
| Gradebook | `sakai.gradebookng` | `gradebookng/tool/.../sakai.gradebookng.xml` |
| Drop Box | `sakai.dropbox` | `content-tool/.../sakai.dropbox.xml` |
| Email | `sakai.mailtool` | `mailsender/tool/.../sakai.mailsender.xml`; the registered tool ID is `sakai.mailtool`. `sakai.mailbox` is the separate Email Archive tool. |
| Roster | `sakai.site.roster2` | `roster2/tool/.../sakai.site.roster.xml`; `sakai.site.roster` was a stale ID in `toolOrder.xml` |
| Site Info | `sakai.siteinfo` | `site-manage-tool/.../sakai.siteinfo.xml` |

All listed registrations are present in the tracked build and include the `course` category. The `demo.sakai.properties` stealth list hides only Profile and Search. The kernel stealth list hides Meetings, Microsoft collaboration tools, SCORM, and Tag Service; it does not hide a requested course tool. No requested tool is disabled by the tracked property defaults.

Overview is a page/container, not a registered tool page. Sakai Worksite Setup creates it using the special `home` selection. Its normal embedded components are `sakai.iframe.site` (site description), `sakai.synoptic.announcement` (Recent Announcements), and `sakai.summary.calendar` (Calendar summary). In `SiteAction`, `SYNOPTIC_TOOL_ID_MAP` maps the announcement widget to `sakai.announcements` and the calendar widget to `sakai.schedule`. The Worksite Setup save path automatically adds a configured widget only when its parent tool is selected and removes it when that parent is removed. The configured course Home components in `kernel.properties` include both requested summaries.

## Creation and migration behavior

Worksite Setup (`apps/sakai/site-manage/site-manage-tool/.../SiteAction.java`) constructs the new-site tool picker from the legacy `toolOrder.xml` ordering when `config.sitemanage.useToolGroup` is false. For a new site, it takes the selected defaults from that ordered list and writes the selected tools in the same order. The tracked course section now selects the requested registered tools, and Home is selected first. This is the Sakai-native default for sites made through Worksite Setup's normal course creation flow. User-selected reusable template sites remain an explicit copy-template workflow.

The existing fixture migration uses `SiteService` and `SitePage` from a tracked Quartz job. It accepts explicit course site IDs only, refuses a non-course, template, or special `!` site, waits for the required tool registrations because Quartz AutoRun can precede the tool WAR startup, adds missing tool placements, orders the requested pages, removes only other navigation page placements, and records an idempotency marker as an ordinary site property. Sakai tool content and data remain intact; the job does not update users, memberships, realms, assignments, submissions, grades, or announcements. The tracked `./sakai migrate-course-layout` helper reads only Course A and Course B from ignored `deployment/mcp-test-sites.env`, passes those IDs to the one-time startup job, waits for completion, then disables the runtime trigger.

The fixture generator `SeedSitesAndUsersJob` now builds new synthetic courses with the same course pages and Overview summary components. Tool-order defaults separately cover future Worksite Setup-created courses.

Tracked implementation files:

- `apps/sakai/kernel/component-manager/src/main/bundle/org/sakaiproject/config/toolOrder.xml` — default selection and order.
- `apps/sakai/kernel/component-manager/src/main/bundle/org/sakaiproject/config/kernel.properties` — Overview summary tools and disabled-by-default migration trigger.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseLayoutMigrationJob.java` — focused, idempotent SiteService migration.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/SeedSitesAndUsersJob.java` — standard layout for generated fixture courses.
- `apps/sakai/site-manage/site-manage-impl/impl/src/webapp/WEB-INF/components.xml` — migration Quartz registration.
- `scripts/migrate-course-site-layout.sh` and `deployment/run-course-site-layout-migration.sh` — explicit fixture-ID migration orchestration.

## Runtime verification record

- Exact Sakai source commit deployed: `3ab722667ff40c6da51afe0d8456e7e29396e57b`; release `20260928T112025Z-3ab722667ff4` is healthy and `/portal` returned HTTP 200.
- Existing fixture migration: Course A and Course B each logged `Standardized course navigation`; a safe repeat logged `Course navigation is already standardized` for each. The temporary migration autorun and ID list were then removed from runtime `local.properties`.
- Instructor/student UI and permission checks, and new-course Worksite Setup verification, remain outstanding. Read-only `/api/login` attempts using the ignored synthetic Student A and Instructor A credentials were rejected. Do not reset account passwords to work around this; restore or replace only through the established synthetic-account setup, then run those checks.
