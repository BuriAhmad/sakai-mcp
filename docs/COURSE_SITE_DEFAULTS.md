# Standard course-site defaults

This document records the course layout verified against the Sakai 25.2 source in `apps/sakai/` and the tracked setup that makes it reproducible.

## Sakai 25.2 tool mapping

| Navigation label | Registration/mechanism | Source evidence |
| --- | --- | --- |
| Overview | Worksite Setup special `home` page, with the `SitePage.IS_HOME_PAGE` property | `SiteAction.TOOL_ID_HOME`; `SitePage.isHomePage()` |
| Syllabus | `sakai.syllabus` | `syllabus-app/.../sakai.syllabus.xml` |
| Lessons | `sakai.lessonbuildertool` | `lessonbuilder/tool/src/webapp/WEB-INF/tools/sakai.lessonbuildertool.xml` |
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

The explicit fixture setup uses `SiteService` and `SitePage` for layout and `AuthzGroupService` for permissions. It reads only Course A/B IDs from ignored `deployment/mcp-test-sites.env`, refuses non-course, special, and template sites, and waits for required tool registrations. It upgrades the previous Boolean migration marker to `sakai.course.layout.standard.version=2`, adds Lessons, and configures the native two-column Overview: description `0,0`, Recent Announcements `0,1`, Calendar `1,1`. Repeating v2 does not reorder already-upgraded courses. The fixture seeder uses the same layout implementation. Additional/custom pages and existing tool placements are preserved; the setup does not delete course content, accounts, memberships, submissions, grades, or announcements.

The only new role grant is `roster.viewallmembers` on the **Student** role, in the normal-course authorization template `!site.template.course` and the explicitly selected course realms. These grants are checked independently of the layout marker and saved only if absent. `BaseSite.getAzg()` copies the course authorization template into new course realms; existing courses require the explicit setup. The template is an authorization default, not a navigation site. Gateway, admin, workspace, project, and generic site-template realms are not modified. A missing Student role fails rather than guessing a role or creating one.

This grant allows students to see active, visible course members. Sakai Roster still applies hidden-member privacy and `roster2.visibleroles` filtering, and checks email/profile/other capabilities separately. No hidden-member, email, export, grading, or course-management grant is added. Roster's internal `isInstructor` field is derived from this permission and used by its fallback membership filter; it does not change a user's actual role. No Roster or MCP role logic is overridden.

`./sakai migrate-course-layout` runs this explicit setup, including the course authorization template. It must follow the code deployment for the future Student roster default to take effect on the existing installation. It uses the release lock and removes temporary autorun properties on success or failure, so a failed attempt cannot silently retry on a later restart. A permission save and layout save are independent Sakai operations; a partial failure is recoverable by rerunning the setup. Code rollback alone does not undo saved realm permissions or page metadata.

Tracked implementation files:

- `apps/sakai/kernel/component-manager/src/main/bundle/org/sakaiproject/config/toolOrder.xml` — default selection and order.
- `apps/sakai/kernel/component-manager/src/main/bundle/org/sakaiproject/config/kernel.properties` — Overview summary tools and disabled-by-default migration trigger.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseLayout.java` — shared tool order, Overview titles and layout.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseRosterPermissions.java` — Student-only roster grant through AuthzGroupService.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseLayoutMigrationJob.java` — explicit v2 layout upgrade and course-template/fixture permission setup.
- `apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/SeedSitesAndUsersJob.java` — standard layout for generated fixture courses.
- `apps/sakai/site-manage/site-manage-impl/impl/src/webapp/WEB-INF/components.xml` — migration Quartz registration.
- `scripts/migrate-course-site-layout.sh` and `deployment/run-course-site-layout-migration.sh` — explicit fixture-ID migration orchestration.

## Applying v2 after an explicitly requested resume

Azure remains paused during local development. When the owner explicitly requests resume and deployment, follow `PAUSE_AND_RESUME.md` and `SAKAI_RELEASES.md`, then:

1. Deploy the pushed full commit with `./sakai deploy COMMIT` after CI passes.
2. Run `./sakai migrate-course-layout`; require a successful v2 completion record for each configured fixture.
3. Verify instructor/student navigation order and Overview's two columns. Confirm Student A sees active, non-hidden Student B in Course A, remains denied instructor functions, and cannot view another course's roster without membership. Check existing privacy filters and fixtures.
4. Create a clearly synthetic temporary course through Worksite Setup, verify all 16 default pages and Student roster visibility, then remove it through Sakai's supported site removal path.

Local regression coverage includes the legacy-marker upgrade, existing placement preservation, missing-tool prevalidation, exact Overview hints/title, repeated setup, Student-only permission change, refusal of special sites, and failure on a missing Student role. Live rendering and authorization remain pending while Azure is paused.

## Historical v1 runtime verification record

- Exact Sakai source commit deployed: `3ab722667ff40c6da51afe0d8456e7e29396e57b`; release `20260928T112025Z-3ab722667ff4` was healthy and `/portal` returned HTTP 200 at the 2026-09-28 check.
- Existing fixture migration: Course A and Course B each logged `Standardized course navigation`; a safe repeat logged `Course navigation is already standardized` for each. The temporary migration autorun and ID list were then removed from runtime `local.properties`.
- Instructor/student UI and permission checks, and new-course Worksite Setup verification, remain outstanding. Read-only `/api/login` attempts using the ignored synthetic Student A and Instructor A credentials were rejected. Do not reset account passwords to work around this; restore or replace only through the established synthetic-account setup, then run those checks.

## V2 status — 2026-10-03

Implemented and checked locally: 14 focused tests passed, along with Bash syntax, ShellCheck, XML/default-order validation, repository guidance, and whitespace checks. Not deployed or applied to Azure. The earlier v1 record above does not verify the Lessons, Overview layout correction, or Student roster grant added in v2.
