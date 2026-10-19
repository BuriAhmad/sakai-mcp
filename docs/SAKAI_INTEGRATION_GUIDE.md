# Sakai integration guide

**Current migration boundary:** follow the [canonical existing-HTTP plan](mcp/existing-api-migration/implementation-plan.md). Python must replace custom Sakai business endpoints/services with existing HTTP APIs and researched native browser forms/AJAX. Only delegated authentication/session integration may remain as a native extension. Historical endpoint recommendations and release descriptions below are evidence, not permission to add business handlers or retain the old architecture. See [current local replacement evidence and limits](mcp/existing-api-migration/five-tool-cutover-2026-10-19.md).

The [MCP-only grading migration](SAKAI_GRADING_MCP_RESOURCES.md) replaces the local importer with SDK resources and server proposal/report tools. Native resource/proposal endpoints preserve delegated permissions and existing grading gates; see its release requirements before deployment.
## Purpose

This is a durable engineering reference for **programmatically interacting with this repository's Sakai installation**. Consult it before implementing or modifying MCP tools, Sakai adapter code, custom Sakai-side endpoints, provisioning or automation scripts, and agent skills that depend on those capabilities.

It preserves source-backed and empirically discovered integration knowledge from the completed synthetic semester population work on 7 October 2026. Its purpose extends beyond that import: a future `create_assignment`, `create_grade_item`, `update_grade`, `create_announcement`, `create_calendar_event`, `create_poll`, or `manage_site_membership` operation should start from the capabilities and limitations recorded here.

The reference baseline is the tracked Sakai 25.2 tree under `apps/sakai/`, including project extensions. This is a capability reference, not a live resource inventory or a guarantee about other Sakai versions. Recheck the selected deployed release and relevant source before changing an integration.

### Related documentation

- [Assignment grading design](SAKAI_ASSIGNMENT_GRADING.md): submission/current-history research, opt-in native/MCP contracts, trusted export workspace and TA Skill. Local implementation is disabled and undeployed; see [evidence/prerequisites](evidence/mcp/assignment-grading-local.md).

- [Assignment setup design](SAKAI_ASSIGNMENT_SETUP.md): next-phase tool contracts, native Assignment/Gradebook/Calendar relationships, implementation plan, opt-in local source and repository Skill. No new runtime capabilities are enabled; see the linked local checkpoint for validation and remaining gates.

- [Repository strategy](REPOSITORY_STRATEGY.md) and [Sakai source](SAKAI_SOURCE.md): ownership and source/deployment boundaries.
- [MCP architecture](mcp/architecture.md), [Sakai WebAPI MCP adapter](mcp/sakai-adapter.md), and [MCP implementation runbook](MCP_IMPLEMENTATION_RUNBOOK.md): authoritative V1 contracts, authentication, authorization and phase gates.
- [Entra claim evidence](evidence/mcp/phase-6-entra-plan.md), [OBO provider evidence](evidence/mcp/phase-10-obo.md), and [client compatibility evidence](evidence/mcp/phase-25-client-compatibility.md): token shape, distinct resources and client integration.
- [Standard course defaults](COURSE_SITE_DEFAULTS.md): registered tools, Overview layout, authorization templates and roster privacy.
- [Infrastructure](INFRASTRUCTURE.md), [VM access](VM_ACCESS.md), [deployment runbook](Sakai_Deployment_Runbook.md), [Sakai releases](SAKAI_RELEASES.md), and [pause/resume](PAUSE_AND_RESUME.md): operating and releasing the environment.

### Evidence and confidence

Each domain distinguishes these confidence levels:

- **Confirmed:** exercised successfully in this installation and supported by source/readback evidence. This does not imply that all role combinations or failure cases were tested.
- **Partially confirmed:** interface or behavior exists in tracked source, or only part of its contract was exercised; runtime mutation/authorization remains unverified.
- **Inferred / needs verification:** a proposed integration choice or behavior that needs an implementation/probe before adoption.

The completed import read back 405 memberships, 35 grade items across 375 Student/course grade views, 1,875 exact marks, 750 blank future cells, 260 calendar events and five assignments. Content readback confirmed syllabi, announcements, Lessons sections, resource metadata, poll counts and named discussion authors. Five selected identities also passed Entra sign-in, downstream OBO mapping and MCP course-access checks. These are bounds on the evidence, not a general acceptance suite for new tools.

Private import scripts and reports remain under ignored `deployment/artifacts/synthetic-semester/`. They are optional historical evidence, may contain credentials/content, and are not available in a clean clone. This guide preserves the reusable findings independently; do not commit those artifacts to make the links work.

## Integration architecture

Sakai exposes different domain capabilities through different mechanisms. Finding an EntityProvider or a Java service does not establish that an obvious REST create/update operation exists.

```text
Agent skill: workflow and guidance
              ↓ uses
MCP tool: clean domain capability
              ↓
Python Sakai adapter / integration boundary
              ↓
Authenticated Sakai-side interface
  ├─ existing SOAP/web service, where appropriate
  ├─ EntityBroker /direct/ provider action
  ├─ tool-specific /api/ endpoint
  └─ project /api/mcp/v1/ endpoint
              ↓
Permission-aware Sakai Java services and persistence
```

The current production-shaped V1 path is the Python MCP service → delegated `/api/mcp/v1/*` endpoints → Sakai services. The seeding process separately used authenticated SOAP, EntityBroker, tool APIs and HTTP automation of native tool forms. **Wicket/UI automation is a provisioning workaround, not the preferred MCP adapter contract.**

For test-data imports, use the [test-data seeding Skill](../skills/sakai-test-data-seeding/SKILL.md) for run planning, reconciliation and user-facing acceptance, plus its assignment/submissions recipe and incident lessons. This guide remains the source for domain interface facts; extend both where a verified import teaches a reusable procedure.

Keep these responsibilities distinct:

- **Agent skill:** guidance about when and how an agent uses capabilities, their constraints and workflow.
- **MCP tool:** the capability exposed to the agent, with a bounded domain schema and appropriate read/write semantics.
- **Sakai adapter/integration:** the implementation that performs the operation, translates IDs and models, enforces the authenticated boundary and handles Sakai-specific responses.

A skill cannot supply a missing backend capability. A future `create_grade_item(...)` should hide transport, Wicket, category models and Java service details from its caller. Existing permission-aware interfaces should be evaluated first; a narrow Sakai-side endpoint is a candidate when the required operation is not safely exposed remotely. This guide does not authorize expansion of the five-tool V1 catalog.

### Transport and model rules learned across domains

- `/api/`, `/direct/` and `/sakai-ws/` have separate handlers and authentication behavior. The V1 bearer filter is path-scoped; an OBO token is not a general credential for every native endpoint.
- Distinguish **Sakai internal user ID**, **EID**, **Entra object ID**, **UPN**, **site ID**, **tool registration ID**, and **tool placement ID**. They are not interchangeable. SOAP membership batches accept EIDs; membership readback returns internal IDs; portal tool URLs use placement IDs.
- Responses differ: SOAP often returns the string `success`, some methods return IDs or other success text, EntityBroker uses provider-specific collections, and Wicket returns XML fragments/redirects. HTTP 200 alone does not prove a write succeeded.
- **Initialization — Partially confirmed:** seeding visited Calendar, Resources, Syllabus and Lessons placements before their related operations. The successful sequence included those initialization visits; the precise backing-object dependencies and whether each visit is necessary remain unverified for a fully headless new site.
- Use source and live WSDL together. The historical [webservices README](../apps/sakai/webservices/README.md) is explicitly an older inventory; [CXF endpoint registration](../apps/sakai/webservices/cxf/src/resources/applicationContext.xml) describes this tree.
- Do not automatically replay ambiguous writes. Private checkpoints reduced duplicate seeding, but a checkpoint alone cannot reconcile a request that committed before its response was lost. Read back the intended object before another create.

## Authentication and session establishment

**Capability:** establish the acting Sakai identity for native services and distinguish it from delegated MCP authentication.

**Confirmed — native seeding path:** `POST /api/login` with form fields `username` and `password` established a normal Sakai session, returned a session identifier and set the browser cookie. The importer retained the cookie jar for tool/EntityBroker calls and passed the session identifier into SOAP operations. `AbstractWebService.establishSession(sessionid)` looks up that existing active session, marks it active and installs it as the current session. This worked without enabling unrestricted SOAP login.

**SOAP details:** `/sakai-ws/soap/sakai?wsdl`, `/sakai-ws/soap/contenthosting?wsdl` and `/sakai-ws/soap/messageforums?wsdl` were used. `SakaiScript` declares RPC/literal binding. The first manual encoder's document-wrapped schema assumption was insufficient: parameters came from WSDL message `part` names/types in the RPC contract. Encode booleans as XML booleans and `None` as `xsi:nil="true"`, not the text `None`. The latter mattered for calendar recurrence. Use a maintained WSDL-aware client where practical rather than promoting the task's minimal XML encoder.

**Confirmed — MCP path:** an incoming MCP access token is validated by the Python service and exchanged through certificate-backed OBO for a distinct Sakai API access token. The Sakai bearer filter validates that downstream token and creates an isolated request-local session. See the authoritative [adapter/auth document](mcp/sakai-adapter.md) for issuer, tenant, audience, scope, HTTPS and lifecycle checks.

**Failure preserved:** alphabetic EIDs were lowercased by Sakai. A downstream claim carrying the original mixed-case identifier resolved through ordinary login but failed the bearer filter's exact `identity.sakaiEid().equals(authentication.getEid())` comparison. Read back the stored EID and register that canonical value in Entra; do not infer it from display name, email or UPN. This resolved the instructor's MCP denial. Password case is a separate concern.

**Security boundary:** development seeding used the sandbox administrator's password-based session, privileged SOAP calls, VM-local execution, and real synthetic instructor/student sessions for authored objects and votes. Those credentials and Azure Run Command privileges are development/provisioning mechanisms. Normal MCP users must not inherit an admin session, password-grant login, arbitrary impersonation or caller-supplied acting-user ID. The production adapter has no admin fallback. SOAP host/login restrictions must not be broadened to make a tool work.

**Source breadcrumbs:**

- [LoginController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/controllers/LoginController.java): ordinary login/session cookie contract.
- [AbstractWebService.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/AbstractWebService.java): `establishSession` and service context.
- [HostFilter.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/rest/HostFilter.java): webservice host restrictions.
- [BaseUserDirectoryService.java](../apps/sakai/kernel/kernel-impl/src/main/java/org/sakaiproject/user/impl/BaseUserDirectoryService.java): `cleanEid` lowercases, trims and strips specified characters.
- [McpBearerFilter.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/security/McpBearerFilter.java): verified external evidence, exact EID comparison and request isolation.
- [Python Sakai client](../services/mcp/src/sakai_mcp/sakai/transport.py): fixed-origin V1 transport; [OBO provider](../services/mcp/src/sakai_mcp/security/obo.py): delegated token exchange.

**Future MCP implication:** retain the delegated boundary. Evaluate native transports behind a safely authenticated Sakai-side adapter; do not assume the V1 token will authenticate legacy SOAP or `/direct/` calls.

## Users and accounts

**Capability:** create local users with explicit internal IDs, preserve EIDs/display names and attach provisioning metadata.

**Confirmed interfaces and path:** SOAP `SakaiScript.addNewUserWithInternalId` created all 153 accounts. `checkForUser`, `checkForUserById` and `getUserId` supported collision checks; `setUserProperty` and `setUserTimeZone` applied provenance/preferences. `GET /direct/user/{internalId}.json` read back canonical instructor EIDs. These methods live in [SakaiScript.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/SakaiScript.java); the direct reader is [UserEntityProvider.java](../apps/sakai/entitybroker/core-providers/src/java/org/sakaiproject/entitybroker/providers/UserEntityProvider.java).

**Insufficient assumptions:** EID and internal ID are different. A generic account CSV was prepared but was not the executed identity-preserving path. A source account type such as `registered` or `maintain` is not its course membership role. Local Sakai creation does not create an Entra identity or licensed mailbox. Entra provisioning and its EID extension were separate Graph operations; token mapping was then verified using issued tokens.

**Suitable for one-off provisioning:** privileged SOAP creation after a complete collision preflight, followed by canonical EID readback. Do not reset an existing user's password to resolve an identifier collision.

**Recommended production MCP mechanism — Inferred / needs verification:** account provisioning needs a separate administrative authorization contract. Evaluate the existing user service/SOAP operations behind that boundary. Ordinary delegated course tools should not gain account creation merely because the seeder could do it. User mutation through EntityBroker was not exercised here.

## Sites and course creation

**Capability:** create a published, private course site with explicit identifiers, description and metadata.

**Confirmed path:** SOAP `addNewSite` used `type=course`, `published=true`, `publicview=false`, `joinable=false`; `setSiteProperty` stored term/provenance metadata and `changeSiteDescription` populated Overview content. The importer refused collisions with unowned sites. `getSitesCurrentUserCanAccess` and page/tool readback supported inspection. [SakaiScript.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/SakaiScript.java) delegates creation to `SiteService.addSite` and saves the site.

**Failure/side effect preserved:** native creation enrolled the creating administrator as an additional Instructor. Full roster comparison caught this extra member; `removeMemberFromSite` removed that membership from each new dataset site. Creation is therefore not equivalent to an exact requested roster. This observation is confirmed for this creation path; do not generalize it to every site-creation interface without checking.

**Suitable for one-off provisioning:** SOAP creation plus explicit tool placement, membership reconciliation and object initialization. This does not prove academic-term properties create institutional registrar course sections or enterprise roster feeds; those were not exercised.

**Recommended production MCP mechanism — Inferred / needs verification:** inspect `SiteService` and creation permissions for a bounded course-provisioning operation. SOAP is a proven provisioning interface, but delegated course-creation policy and retries need verification before exposing a new MCP tool.

## Memberships, rosters and roles

**Capability:** add/remove course members, assign actual native roles and inspect the exact roster.

**Confirmed interfaces:**

- SOAP `getAvailableRoles(sessionid, "/site/" + siteId)` identified `Student`, `Teaching Assistant`, and `Instructor` in these course realms.
- SOAP `addMemberToSiteWithRoleBatch(sessionid, siteid, eids, roleid)` added comma-separated **EIDs**. It explicitly requires a superuser in this source.
- SOAP `removeMemberFromSite` removed the creator's extra membership.
- `GET /direct/membership/site/{siteId}.json` returned `membership_collection` entries with `userId` (internal ID) and `memberRole`.

[MembershipEntityProvider.java](../apps/sakai/entitybroker/core-providers/src/java/org/sakaiproject/entitybroker/providers/MembershipEntityProvider.java) also exposes a POST branch of its `site` action and `sitebyjson` batch input. **Partially confirmed:** those write branches were inspected, not exercised during this import; their user-ID resolution, policy, notifications and admin-site guards need validation.

**Insufficient assumptions:** the source label `TA` had to map to `Teaching Assistant`; discover roles rather than inventing IDs. `removeMemberFromSite` reads `site.getUserRole(userid).getId()` before removal, so an already-absent member is not a safe idempotent success assumption. Read the roster before retrying removal. A course roster need not be a registrar-managed enrollment object.

**Roster visibility:** the importer granted `roster.viewallmembers` only on each course's Student role using `allowFunctionForRole`. Roster privacy, hidden users and other permission checks remain separate. See [standard course defaults](COURSE_SITE_DEFAULTS.md); granting roster read must not confer grading/course management.

**Recommended production MCP mechanism — Inferred / needs verification:** evaluate the native membership EntityProvider/service under delegated site membership-management authorization. Do not proxy the superuser-only SOAP batch as an ordinary instructor capability. Verify group/section scope, active/provided membership semantics, notifications and cross-site denial.

## Standard course tool configuration

**Capability:** provision the navigation/pages and tool placements used by ordinary courses.

**Confirmed path:** `addNewPageToSite`, `addNewToolToPage`, `addConfigPropertyToPage` and `getPagesAndToolsForSiteForCurrentUser` built/read 16 pages and 18 placements per course. Overview is a home page with `is_home_page=true`, not a registered standalone tool. It contained `sakai.iframe.site`, `sakai.synoptic.announcement` and `sakai.summary.calendar`, with layout hints `0,0`, `0,1`, `1,1`.

**Insufficient assumptions:** tool registration IDs are not placement IDs. The registered IDs include `sakai.assignment.grades`, `sakai.site.roster2` and `sakai.mailtool`; stale labels/ordering entries can differ. The authorization template `!site.template.course` is not a navigation/template-content site. Adding a Gradebook placement alone did not configure items, categories or visibility.

**Implementation and future recommendation:** use the tracked [StandardCourseLayout.java](../apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseLayout.java) and [StandardCourseRosterPermissions.java](../apps/sakai/site-manage/site-manage-impl/impl/src/java/org/sakaiproject/sitemanage/impl/job/StandardCourseRosterPermissions.java) as source-backed layout/permission references. Reuse the existing site/page/tool services and registration checks for future provisioning. The complete mapping belongs in [COURSE_SITE_DEFAULTS.md](COURSE_SITE_DEFAULTS.md), rather than being duplicated here.

## Gradebook / GradebookNG

### Capability and terminology

The work required grade-item creation, hundreds of scores, due dates, individual weights, blank future scores, released visibility and inclusion in course calculations. A **Gradebook item** is called an `Assignment` in the grading API; it is distinct from an Assignments-tool assignment, submission or Samigo assessment. A score in Gradebook does not prove that a native quiz attempt or assignment submission exists.

### Existing remote interfaces and their limits

- **Confirmed read:** `GET /api/sites/{siteId}/grades` returned `grades` and supplied the native Student readback. Its controller has different Student/grader branches; do not use it as an own-only MCP contract. The existing V1 `GET /api/mcp/v1/courses/{siteId}/grades/me` is the delegated own-grade interface.
- **Confirmed category read:** `GET /api/sites/{siteId}/categories` was used for category readback.
- **Partially confirmed, source only:** `GET /api/sites/{siteId}/grading/item-data` returns categories/items; `POST /api/sites/{siteId}/grades/{gradingItemId}/{userId}` accepts JSON fields `grade`, `comment`, `reference`. `GradesController.submitGrade` calls `GradingService.setAssignmentScoreString` and optionally `setAssignmentScoreComment`. The POST was **not** exercised for seeding. It is a real mutation candidate for investigation, not proof of an MCP-ready write contract. The service checks item/student grading permission and externally maintained items; the controller path and delegated authentication still require review.
- **Partially confirmed, source only:** `/sakai-ws/soap/gradebook` is registered, but [SakaiGradebook.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/SakaiGradebook.java) exposes `createOrUpdateGradeScale`, not the item/category/score CRUD needed for the import. `SakaiScript` was sufficient for users/sites but did not provide the required Gradebook item/score workflow.
- **Source-confirmed limitation:** [GradebookNgEntityProvider.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/rest/GradebookNgEntityProvider.java) uses prefix `gbng` and implements front-end actions for ordering, editing notifications, comments and messaging. It does not supply the needed general item/category/score import mutation. Its class comment explicitly identifies it as front-end support rather than a third-party API. Its mention of a “standard gradebook entityprovider” is not evidence that such an integration contract is present/usable in this installation; that remains unverified.

The conclusion is operation-specific: a limited score POST exists in source, but a complete remote create/configure/import interface was not established. Do not claim either that “Gradebook has no API” or that `/direct/gbng` offers complete CRUD.

### Native import and what worked

**Confirmed — suitable for one-off provisioning/test data:** the importer automated authenticated GradebookNG HTTP/Wicket forms. It discovered the Gradebook placement, opened `/portal/tool/{placementId}/settings`, configured categories and release settings, then used `/portal/tool/{placementId}/importexport` and its generated AJAX callbacks.

Native CSV headers used `Student ID`, `Student Name`, and item columns such as `Quiz 1 [100]`. The seeding CSV's Student ID was the user's EID, resolved by the native importer to internal user IDs. Blank future cells stayed blank. A prepared sidecar settings CSV was documentation/input to the automation, **not** a separately supported Gradebook settings import API.

The wizard stages were upload, item selection, per-new-item configuration and final confirmation. Upload used a multipart file with its rendered field name; new items needed categories, dates and flags before Finish. The importer checked native success feedback and then read all 375 Student/course reports; it did not treat a successful POST as sufficient.

### Why Wicket automation was difficult

These are confirmed implementation details of this seeding workaround, not stable public APIs:

1. Callback URLs and component IDs are generated from the active Wicket page/session. Extract the current `Wicket.Ajax.ajax(...)` callback, preserve its form fields and keep the cookie jar. Static guesses about a REST path or generic form action were insufficient.
2. The `Wicket-Ajax-BaseURL` header had to match the page's generated `Wicket.Ajax.baseUrl`, not a guessed full portal path. The automation also set `Wicket-Ajax: true` and handled `X-Requested-With`.
3. Wicket responses contained XML `<component>` replacements and redirects; upload responses could wrap the XML in a `<textarea>`. Later requests needed updated component markup/callbacks, not the original DOM.
4. Displaying a due-date string alone failed validation. `SakaiDateTimeField` reads a request parameter named **component markup ID + `ISO8601`**; the importer supplied that value as well. A Gradebook due date is a date field; this does not preserve an assessment's exact scheduled time, which was stored separately in Calendar.
5. Category name and weight changes needed their native AJAX events before Save: name `blur`, weight change. Posting every visible field only on Save left the model/running-total validation inconsistent. `SettingsPage` validates category state before its usual form submission behavior.
6. Choosing a category required its change callback so the item “counted” control became valid/enabled. The importer explicitly set `released` and `counted`; default assumptions produced items that did not meet the intended calculation/display configuration.

The initial incomplete item configuration was reconciled through native UI deletion of only the newly created, explicitly identified test items, followed by weighted reimport. This was a controlled seeding repair, not a production strategy of deleting/recreating items that may already have submissions, external links or grades.

### Categories, weights, release and counting

**Confirmed seeding configuration:** each of seven items had its own weighted category: four quizzes at 5% each, Assignment 20%, Midterm 25%, Final 35%. This translated **item weights** into a native category-weighting model. The UI displays percentage weights; grading definitions use fractional weights, as shown by the panel's conversion and category validation. Do not copy UI `5` into an internal fractional weight without converting it.

The category weights totaled 100%. Category selection, counted-in-course-grade status, released-item status and course-grade display settings are separate. The importer enabled released-item/course-grade display, selected percentage/letter presentation rather than course-grade points, and configured every imported item as released and counted. Future items were therefore visible but had no score; blank is not zero. The intended current-progress model excluded the future 40% and normalized completed work against 60%; exact raw scores/blank cells were fully verified. The private access guide calculated selected Student progress from the source weights and marks; the retained automated grade readbacks do not independently verify Sakai’s computed course-grade percentage. General drop rules, extra credit, unequal maxima and other calculation policies were not acceptance-tested.

Singleton categories were a dataset-specific way to express individual weights. They are not a recommendation that every real course should have one category per item.

### Source breadcrumbs for future implementation

| Source | Why it matters |
| --- | --- |
| [GradesController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/controllers/GradesController.java) | Native reports, category/item reads, single-score POST and grader/Student branches. |
| [McpGradesController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/courses/McpGradesController.java) | Existing delegated own-grade contract and release/permission handling. |
| [GradingService.java](../apps/sakai/gradebookng/api/src/main/java/org/sakaiproject/grading/api/GradingService.java) | `addAssignment`, `updateAssignment`, `saveGradesAndComments`, `setAssignmentScoreString`, category definitions and `updateGradebookSettings`; internal service, not a remote API. |
| [GradingServiceImpl.java](../apps/sakai/gradebookng/impl/src/main/java/org/sakaiproject/grading/impl/GradingServiceImpl.java) | Actual permission checks, externally maintained item behavior and grade persistence/events. |
| [GradebookNgBusinessService.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/business/GradebookNgBusinessService.java) | Tool-level item operations and `saveGradesAndCommentsForImport`. |
| [ImportExportPage.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/pages/ImportExportPage.java) and [ImportGradesHelper.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/business/util/ImportGradesHelper.java) | Wizard state and parsing/selection preparation. |
| [GradeImportUploadStep.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/importExport/GradeImportUploadStep.java) | File-change AJAX and upload/validation step. |
| [GradeItemImportSelectionStep.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/importExport/GradeItemImportSelectionStep.java) and [CreateGradeItemStep.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/importExport/CreateGradeItemStep.java) | Import selection and per-item definition configuration. |
| [GradeImportConfirmationStep.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/importExport/GradeImportConfirmationStep.java) | Finish actually creates/updates items and calls import grade saving; partial error handling matters for retries. |
| [SettingsPage.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/pages/SettingsPage.java) and [SettingsCategoryPanel.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/SettingsCategoryPanel.java) | Category/weight validation and AJAX model updates. |
| [AddOrEditGradeItemPanelContent.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/AddOrEditGradeItemPanelContent.java) and [SettingsGradeReleasePanel.java](../apps/sakai/gradebookng/tool/src/java/org/sakaiproject/gradebookng/tool/panels/SettingsGradeReleasePanel.java) | Category-dependent counted control, item release and course-grade display. |
| [SakaiDateTimeField.java](../apps/sakai/wicket/wicket9/src/java/org/sakaiproject/wicket/component/SakaiDateTimeField.java) | Component-specific `ISO8601` parameter conversion. |

### Recommended production MCP mechanism

**Inferred / needs verification:** for `update_grade`, investigate the existing score POST/service and determine whether its authorization, error handling and identity boundary fit the proposed contract. For `create_grade_item`, categories and weighting, no sufficient general remote mutation was established; a narrow delegated Sakai-side endpoint over `GradingService` is a plausible approach after checking existing interfaces.

Do not drive Wicket per-grade calls in the production MCP service. A domain endpoint should validate site/item/Student relationships, grader group/section scope, externally maintained ownership, null-versus-zero semantics, maxima, release policy and concurrency. Grade item creation, grade saving and category settings are distinct operations; the bulk import wizard is not their production contract.

## Assignments

**Capability:** post a native assignment with instructions, point grading and open/due/close dates, independently of imported Gradebook scores.

**Confirmed path:** `GET /direct/assignment/site/{siteId}.json` read back `assignment_collection`. Creation used the native tool form opened through `/portal/tool/{placementId}?sakai_action=doNew_assignment`. The importer preserved `newAssignmentForm` state, used `option=post`, supplied `new_assignment_*` date/grade/submission fields, and handled the explicit past-date confirmation before checking that creation completed. This is form automation, not Wicket Gradebook automation.

**Partially confirmed alternative:** [Assignments.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/Assignments.java) exposes SOAP `createAssignment` on the registered assignments service. Its implementation sets posted/released state, uses grade/submission enum indexes, integrates a Gradebook item and adds a calendar deadline when a calendar exists. It was not the executed seeding path. Those side effects could create an extra calendar deadline or conflict with the independently imported Gradebook item; evaluate them before considering it a substitute for a minimal create contract. This source review does not establish that the SOAP operation failed.

[AssignmentEntityProvider.java](../apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/entityproviders/AssignmentEntityProvider.java) exposes site/item/submission/grade actions; an EntityProvider's presence alone did not establish a general assignment-creation request. [AssignmentAction.java](../apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/tool/AssignmentAction.java) defines the native UI workflow; [AssignmentServiceImpl.java](../apps/sakai/assignment/impl/src/java/org/sakaiproject/assignment/impl/AssignmentServiceImpl.java) supplies the underlying permission-aware service.

**Suitable for one-off provisioning:** instructor-authenticated form posting with Gradebook integration, extra Calendar creation and email notifications disabled. Source data had no submissions; the importer did not fabricate them or treat the standalone Gradebook marks as graded native submissions.

**Recommended production MCP mechanism — Inferred / needs verification:** evaluate SOAP creation and `AssignmentService` against explicit draft/publish, grading, notification and calendar semantics. A narrow delegated endpoint may be appropriate where the native SOAP side effects differ from the desired tool. Preserve assignment/site equality and grading group scope already required by the [V1 submission adapter](mcp/sakai-adapter.md).

## Calendar and schedule

**Capability:** create class meetings, office hours and assessment/deadline events with correct time ranges and locations.

**Confirmed path:** SOAP `SakaiScript.addCalendarEvent` writes the site's `/calendar/calendar/{siteId}/main` calendar through `CalendarService`. Arguments include epoch-millisecond start/end, inclusion flags, text/formatted description, type, location and optional recurrence frequency/interval. `GET /direct/calendar/site/{siteId}.json?firstDate=...&lastDate=...&detailed=true` returned `calendar_collection` for count readback.

**Failed assumption:** serializing Python `None` as a string did not express “no recurrence.” Use SOAP `xsi:nil` for the nullable frequency. The source creates a recurrence rule whenever the frequency is non-null. The successful seed used explicit finite dated occurrences in Asia/Karachi, converted to epoch milliseconds; it did not validate recurring-event editing or timezone/DST rules across regions.

**Suitable for one-off provisioning:** visit the Calendar placement to initialize it, then create finite instances and verify the bounded semester range. Assignment creation was configured to avoid an additional deadline event.

**Recommended production MCP mechanism — Inferred / needs verification:** existing SOAP is a proven event-creation mechanism, but verify delegated permissions, missing-calendar initialization, recurrence/end conditions and create reconciliation before adopting it. An endpoint over `CalendarService` is an alternative if the current bearer boundary cannot safely reach the needed native operation. Relevant implementation: [SakaiScript.addCalendarEvent](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/SakaiScript.java).

## Announcements

**Capability:** read visible course announcements and create posted or scheduled content with correct author/site scope.

**Confirmed seeding path:** instructor-authenticated native form `/portal/tool/{placementId}?sakai_action=doNewannouncement`, preserving `reviseForm`, posted subject/body, site audience, explicit release-date parts and notification setting. This preserved historical dates without using the V1 plain-post write. `GET /direct/announcement/site/{siteId}.json?d=3650&n=100` read back both source announcements in each course.

**Existing production path:** V1 `GET`/`POST /api/mcp/v1/courses/{siteId}/announcements` uses the delegated user. [McpCourseController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/courses/McpCourseController.java) visit-gates reads; [McpAnnouncementWriteController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/announcements/McpAnnouncementWriteController.java) implements the existing bounded posted-announcement write. The five synthetic accounts exercised V1 reads, not a new write acceptance run.

**Failures/limitations preserved:**

- Earlier repository reconnaissance showed unrelated-site leakage through generic `/api/sites/{siteId}/announcements`. Reuse its underlying service selectively, not the generic route as an MCP proxy. See [Phase 3 evidence](evidence/mcp/phase-3-sakai-api-reconnaissance.md).
- This import found an existing V1 age-filter bug: `McpCourseController` passes `3650` to `getMaxAgeInDaysAndAmountFilter`; [BaseAnnouncementService.java](../apps/sakai/announcement/announcement-impl/impl/src/java/org/sakaiproject/announcement/impl/BaseAnnouncementService.java) calculates `maxAgeInDays * 24 * 60 * 60 * 1000` with Java integer arithmetic before converting to long. It wraps to `1,827,387,392` milliseconds, approximately **21.15 days**. Recent announcements appeared through MCP, while older posted announcements remained visible through native reads. This was diagnosed and documented, not fixed/deployed during seeding. Recheck source/release before assuming the defect still exists.
- A larger lookback parameter does not necessarily expand returned history. Distinguish filtering defects from missing writes; do not recreate announcements or alter source dates merely to make a read succeed.

**Source breadcrumbs:** [AnnouncementEntityProviderImpl.java](../apps/sakai/announcement/announcement-tool/tool/src/java/org/sakaiproject/announcement/entityprovider/AnnouncementEntityProviderImpl.java) implements direct site reads; [AnnouncementAction.java](../apps/sakai/announcement/announcement-tool/tool/src/java/org/sakaiproject/announcement/tool/AnnouncementAction.java) handles native publication and release/retract dates.

**Recommended production MCP mechanism:** keep the existing delegated V1 announcement contract and write-reconciliation policy. **Inferred / needs verification:** extending it to schedules/drafts/attachments needs explicit service-level semantics and permission checks, not native-form replay. Fix/test the age calculation as a separate application change.

## Polls, options and votes

**Capability:** create a poll with ordered choices, record votes and read its results.

**Confirmed interfaces and payload shape:**

- `POST /direct/poll.json`: JSON including `siteId`, `text`, `description`, `voteOpenStr`, `voteCloseStr`, `minOptions`, `maxOptions`, `limitVoting`, `displayResult`.
- `POST /direct/poll-option.json`: JSON including `pollId`, `text`, `optionOrder`.
- `POST /direct/poll-vote.json`: form fields `pollId`, `pollOption`, authenticated as the actual voter.
- `GET /direct/poll/{pollId}.json?includeVotes=true&includeOptions=true`: native readback of options/votes; vote counts matched all source aggregates.

**Implementation:** [PollEntityProvider.java](../apps/sakai/polls/tool/src/java/org/sakaiproject/poll/tool/entityproviders/PollEntityProvider.java), [PollOptionEntityProvider.java](../apps/sakai/polls/tool/src/java/org/sakaiproject/poll/tool/entityproviders/PollOptionEntityProvider.java), and [PollVoteEntityProvider.java](../apps/sakai/polls/tool/src/java/org/sakaiproject/poll/tool/entityproviders/PollVoteEntityProvider.java). Creation responses were not assumed to be a common JSON object: the importer reconciled the Location/returned identifier before creating dependent options/votes.

**Suitable for one-off provisioning:** source polls specified only aggregate counts. The seed generated individual votes deterministically in roster order and recorded a private ledger; these assignments were newly generated data, not historical source facts. Each vote used that synthetic Student's session, rather than an administrator supplying an arbitrary voter ID.

**Recommended production MCP mechanism — Inferred / needs verification:** the existing EntityBroker operations are good candidates behind a delegated adapter. Confirm poll ownership/site scope, allowed vote window, multiple-choice limits, result visibility and vote-data privacy. Admin readback with `includeVotes` does not establish a Student's permission to inspect individual voters. Update/delete behavior and negative authorization cases were not exercised.

## Resources and content

**Capability:** create resource metadata/content under a course collection and read the resulting objects.

**Confirmed path:** SOAP `ContentHosting.createContentItem` on `/sakai-ws/soap/contenthosting` used the instructor session, resource title, `/group/{siteId}/` collection, content string, description, MIME type and binary flag. `getResources` returned XML resource records used to verify names. [ContentHosting.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/ContentHosting.java) delegates to `ContentHostingService.addResource`; its binary branch base64-decodes the content argument.

**Seeding limitation:** source data provided title/description/attachment state, not file bodies. The importer created zero-byte `text/html` resource placeholders carrying that metadata. This confirmed resource creation/listing, **not** binary upload, downloadable real file contents, attachment linking or overwrite semantics in this task. Collection paths and resource IDs must be distinguished; human titles are not a reliable identity/reconciliation key.

**Recommended production MCP mechanism — Inferred / needs verification:** evaluate the existing ContentHosting interfaces/service against the specific operation. For uploads, verify content type/size, returned resource ID, collection authorization, duplicate-name behavior, visibility and attachment linkage. The seeding placeholder path is not an upload implementation. Separate existing upload evidence is in [infrastructure documentation](INFRASTRUCTURE.md); do not treat it as this task's test coverage.

## Syllabus

**Capability:** create a published syllabus text item and read its content.

**Confirmed path:** initialize the native Syllabus placement, then `POST /direct/syllabus/0.json` with form fields `add=true`, `title`, `siteId`, `published=true`, `content`. `GET /direct/syllabus/site/{siteId}.json` returned an object with `items`, each including `title` and HTML `data`. Native readback verified the source text after HTML/whitespace normalization.

**Important non-CRUD behavior:** [SyllabusEntityProvider.java](../apps/sakai/syllabus/syllabus-app/src/java/org/sakaiproject/tool/syllabus/entityproviders/SyllabusEntityProvider.java) implements the add operation inside `updateEntity` using the `add` parameter. Its `createEntity` is not the useful create workflow. Guessing `POST /direct/syllabus.json` from REST conventions would miss the actual front-end contract.

**Suitable for one-off provisioning:** reuse the provider's existing front-end action. **Recommended production MCP mechanism — Inferred / needs verification:** evaluate this action or the underlying syllabus services behind delegated site authorization. Attachments, date scheduling, multi-item ordering, updates and negative permission cases remain unverified.

## Lessons

**Capability:** populate a new Lessons page with two text summaries.

**Confirmed interfaces:** `GET /direct/lessons/site/{siteId}.json` identified the root lesson item; the native tool's Add Text link exposed the backing page ID (`sendingPage`). `POST /api/sites/{siteId}/lessons/{lessonId}/items/bulk` created two text items with `pageId`, `type=5`, `title`, `html`. These became two sections of one native Lessons page, not two new navigation pages. The importer verified the rendered titles and summaries.

**Limitation:** [LessonsController.java](../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/controllers/LessonsController.java) rejects the bulk create if the target page already contains items and validates permitted item types. This is an empty-page population endpoint, not a general append/update API. Root lesson item ID and backing page ID are distinct. [LessonsEntityProvider.java](../apps/sakai/lessonbuilder/tool/src/java/org/sakaiproject/lessonbuildertool/tool/entityproviders/LessonsEntityProvider.java) handles direct lesson/site reads.

**Recommended production MCP mechanism — Inferred / needs verification:** use the confirmed bulk interface only for an explicitly empty page after authorization review. Investigate other services/endpoints for incremental edits, subpages, ordering and conditions. Do not remove existing page items to satisfy the empty-page precondition.

## Discussions / message forums

**Capability:** create a forum/topic prompt and replies authored by named enrolled Students, then inspect the thread.

**Confirmed path:** SOAP `MessageForums.addMessage` on `/sakai-ws/soap/messageforums`, using the instructor session for the prompt and each Student's own session for their reply. [MessageForums.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/MessageForums.java) finds/creates forum/topic objects and sets each subsequent message as a reply to the last message in the topic. It is not an arbitrary parent-message API.

**Confirmed readback:** `/direct/forums/site/{siteId}.json` lists sparse forums; `/direct/forums/site/{siteId}/forum/{forumId}.json` includes topics; `/direct/forums/site/{siteId}/forum/{forumId}/topic/{topicId}.json` returns thread summaries. To verify all reply bodies/authors, use `/direct/forums/site/{siteId}/forum/{forumId}/topic/{topicId}/message/{messageId}.json` and traverse its replies. Initially treating the topic's single root-thread summary as all messages incorrectly suggested replies were absent.

**Implementation:** [ForumsEntityProviderImpl.java](../apps/sakai/msgcntr/messageforums-app/src/java/org/sakaiproject/tool/messageforums/entityproviders/ForumsEntityProviderImpl.java) separates forum/topic/message representations. Full readback confirmed all fifteen reply bodies and internal author IDs; display names alone were not used as identity proof.

**Recommended production MCP mechanism — Inferred / needs verification:** inspect the forum services for explicit topic/message parent semantics and delegated author permissions. SOAP's last-message reply behavior may not fit a future `reply_to_message` contract. Drafts, moderation, post-before-view rules, availability, notifications and negative role checks were not fully investigated.

## Assessments / Tests & Quizzes (Samigo)

**Capability touched:** install the tool and represent supplied quiz/exam metadata and scores. The dataset contained no questions or attempts; no native Samigo assessments, attempts or submission-grade synchronization were created.

**Partially confirmed, source only:** CXF registers `/sakai-ws/soap/testsandquizzes`; [TestsAndQuizzes.java](../apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/TestsAndQuizzes.java) includes `createAssessmentFromText` and `createAssessmentFromExport` using SamLite/QTI services. These were not exercised, and their presence does not establish publishing, attempt creation or grade synchronization support.

**Insufficient assumption:** creating a Gradebook “Quiz” column or scheduling an exam is not creating a Samigo assessment. **Recommended production MCP mechanism:** investigation still required; evaluate native assessment authoring/import/publish services and security separately. Do not infer a quiz API contract from the successful Gradebook import.

## Capability matrix

“Write” describes what was established for this task or in source, not permission for every MCP user. Production choices below are recommendations to evaluate; only the existing five V1 routes are implemented in the MCP service.

| Domain | Existing interface | Read | Write | Used during seeding | Likely MCP approach | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| Identity/session | `/api/login`; delegated V1 bearer/OBO | Session/token validated | Native session established | Admin plus named user sessions; five OBO identities | Existing delegated bearer boundary | Confirmed |
| Users | `SakaiScript`; direct user reader | Yes | Explicit internal-ID creation, properties, timezone | Privileged SOAP | Separately authorized provisioning adapter | Confirmed seeding; delegated writes need verification |
| Sites | `SakaiScript` / `SiteService` | Yes | Creation/properties/description | SOAP plus creator-member reconciliation | Evaluate native services and creation policy | Confirmed seeding |
| Memberships | SOAP batches; `/direct/membership/site/...` | Yes | SOAP batch/removal; direct POST exists in source | Privileged SOAP, direct readback | Evaluate direct/service writes with site management scope | Confirmed SOAP/read; direct write partial |
| Tool layout | SOAP page/tool operations; layout Java helpers | Yes | Yes | Explicit pages/placements and Student roster grant | Site/page/tool services | Confirmed seeding |
| Grade items | GradebookNG wizard; grading service | Yes | Wizard/internal service; general remote create unestablished | Wicket CSV wizard | Investigate remote interface; narrow service endpoint candidate | Confirmed UI; remote mutation partial |
| Scores | Native/MCP grades reads; native single-score POST in source | Yes | CSV import confirmed; POST unexercised | Wicket import, Student/MCP readback | Evaluate score POST / `GradingService` | Confirmed bulk; POST partial |
| Categories/weights/release | Native category read; Settings UI; grading service | Categories yes | UI/internal service confirmed; remote settings mutation unestablished | Wicket settings and per-item flags | Evaluate service-backed endpoint | Confirmed UI; remote mutation needs verification |
| Assignments | Direct reader; native form; SOAP `createAssignment` | Yes | Native form confirmed; SOAP source only | Instructor form, no submission fabrication | Evaluate SOAP/service side effects | Confirmed form/read; SOAP partial |
| Calendar | SOAP `addCalendarEvent`; direct site reader | Yes | Finite events yes | SOAP epoch ranges, no recurrence | Evaluate SOAP/service under delegated scope | Confirmed finite-event seed; recurrence unverified |
| Announcements | Direct reader; native form; V1 GET/POST | Yes, with existing MCP lookback defect | Native dated form; V1 plain write already implemented | Instructor form, direct/MCP reads | Existing V1 service adapter; separate lookback fix | Confirmed reads/form; expanded writes unverified |
| Polls/options/votes | Direct providers | Yes, privileged result readback | Create poll/options; own vote | Instructor JSON, Student vote forms | Evaluate existing providers behind delegated boundary | Confirmed positive paths; negative/privacy cases partial |
| Resources | ContentHosting SOAP/service | XML listing yes | Metadata/empty content yes | Zero-byte resource placeholders | Evaluate content service/upload contract | Confirmed placeholders; binary/attachment work unverified here |
| Syllabus | Direct provider add/update action | Yes | Published text item yes | `/direct/syllabus/0.json` add action | Evaluate provider/services | Confirmed positive text path |
| Lessons | Direct root reader; WebAPI bulk create | Root/render yes | Empty-page text bulk yes | Two text sections on new page | Bulk for empty pages; investigate incremental service API | Confirmed empty-page path |
| Discussions | MessageForums SOAP; direct forum provider | Full threads yes | Prompt/reply chain yes | Named authenticated authors | Evaluate explicit parent/author service contract | Confirmed positive paths; moderation/permissions partial |
| Samigo | Registered SOAP text/QTI import in source | Unknown / not yet investigated | Source import methods only; unexercised | Tool placement; metadata/marks elsewhere | Investigation required | Partially confirmed interface; lifecycle unknown |
| Conversations, Email, Drop Box, Site Info | Tool registrations configured | Domain API not investigated | Domain API not investigated | Navigation placements only | Investigation required for domain operations | Confirmed placement only |

## Before implementing a new MCP Sakai tool

1. Read this guide's domain section and the [V1 runbook](MCP_IMPLEMENTATION_RUNBOOK.md). A proposed tool still needs an explicit catalog/phase decision.
2. Check the exact tracked and deployed version. Search CXF endpoint registrations/WSDL, relevant EntityProviders and WebAPI controllers for an existing remote operation.
3. Follow the operation into its Java service/tool implementation. Distinguish source-exposed, live-tested and inferred behavior; inspect side effects and object initialization.
4. Define acting identity, site/object relationships and actual permissions. Test ordinary user, permitted grader/instructor, unrelated site, and relevant group/section/privacy cases before production adoption.
5. Prefer a stable programmatic contract to native UI automation. A working UI importer is evidence that the domain operation exists, not a ready MCP transport.
6. If required functionality exists internally but lacks a safe remote contract, consider a narrow delegated Sakai-side endpoint over the existing services. Do not bypass services with database writes or broaden webservice access.
7. Keep transport, identity mapping, error translation and Sakai model quirks behind the adapter. Return clean domain results; never accept caller-selected actor identity or arbitrary destination URLs.
8. Plan bounded reads, write side effects, concurrency and ambiguous-result reconciliation. Use object IDs and authenticated readback, not success-looking HTTP status or guessed title matches.
9. Record the new confirmed findings, limitations and source references here. Put credentials, token samples and content-bearing probe output in private ignored artifacts, not documentation/Git.

## Temporary scripts and operational context

The following are **one-off seeding automation**, under ignored `deployment/artifacts/synthetic-semester/`: `seed_structure.py`, `content_core.py`, `content_pages.py`, `import_grades.py`, `settings_grades.py`, and `all_gradebooks.py`. They demonstrate the executed SOAP/provider/form paths but contain hard-coded dataset behavior, privileged session assumptions and private inputs. The UI helpers are not a reusable production adapter.

`inspect_content.py`, `inspect_edit_forms.py`, `ui_import_inspect.py`, `ui_remote_probe.py` and `probe_remote.py` are **diagnostic probes**. `verify_dataset.py`, `verify_content.py`, `finalize_readback.py`, `verify_identity.py` and `verify_mcp_remote.py` are **task-specific readback checks**. Their count/shape assertions and later fixes explain the evidence, but are not a general authorization test suite. Some local scripts were earlier variants; VM-executed patches corrected RPC WSDL parsing and nullable SOAP encoding, so an old local helper must not be treated as the final protocol authority.

The **reusable integration implementation** is the tracked Python service under `services/mcp/src/sakai_mcp/` and Sakai Java adapter under `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/`. See [the service README](../services/mcp/README.md) and [adapter document](mcp/sakai-adapter.md).

During seeding the Mac's connectivity to Azure/Sakai/SSH was intermittent. Azure CLI Run Command executed the importer on the VM using loopback HTTP; no broad SSH rule or public Tomcat exposure was required. This was an operational workaround, not an application API. VM-local form redirects could point to the public HTTPS origin; the local HTTP helper translated those known Sakai redirects back to loopback. Do not turn that helper's URL rewriting into an arbitrary-URL proxy in MCP.

Preserve the [release](SAKAI_RELEASES.md), [VM access](VM_ACCESS.md) and [pause/resume](PAUSE_AND_RESUME.md) boundaries. Documentation or source changes do not authorize a compute start, restart or deployment. This guide requires no live mutation to consult.

## Known gaps / future integration investigation

- **Gradebook remote mutations:** exercise the existing single-score POST under a verified acting identity; check authorization, clearing grades, comment behavior, external item ownership and errors. Establish whether item/category/settings remote mutations exist before deciding on extensions. Define concurrency and partial bulk-write reconciliation.
- **Grade calculations:** extend verification beyond the seeded singleton categories/equal maxima to empty categories, drop/keep rules, extra credit, external items and course-grade display policies.
- **Announcements:** fix and verify the integer-overflow lookback in a separate source/release task; preserve cross-site denial. Scheduled/draft/attachment operations and notification policy need a wider contract than V1 plain creation.
- **Memberships and course provisioning:** direct membership write authorization, protected/provided enrollment, group/section boundaries, creator enrollment, institutional course sections and notifications need testing. Superuser batch success is not delegated-instructor acceptance.
- **Assignments:** test SOAP `createAssignment` and its Gradebook/Calendar/release side effects against the desired domain contract. Native submission creation, returned grades and synchronization were not covered by this dataset.
- **Calendar:** confirm backing-calendar initialization, recurrence lifecycle, update/delete, cross-timezone behavior, permissions and retry reconciliation.
- **Polls and resources:** test negative permission/privacy cases, update/delete, real binary content and attachment/linking behavior. Synthetic aggregate-vote realization is not a production voting policy.
- **Syllabus, Lessons and forums:** verify delegated mutations and incremental editing; investigate attachments, availability, ordering, conditions, explicit reply parents, moderation and notifications.
- **Samigo:** question/QTI import, draft/publish, delivery, attempts, permissions and Gradebook synchronization remain unexercised. Tool presence and Gradebook scores cannot establish these capabilities.
- **Conversations, Email, Drop Box and Site Info domain APIs:** not investigated beyond course tool placement.
- **Transport adoption:** native SOAP/EntityBroker endpoints were exercised with development sessions, not downstream V1 bearer tokens. Any new adapter must establish a safe delegated path and preserve request/session isolation. Do not promote an admin or Wicket workaround into MCP by default.
