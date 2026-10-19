# T01 course-list cutover — 19 October 2026

Scope: actual default public `list_my_courses` migration and focused local
retirement, on `codex/replace-custom-sakai-api`. HEAD remains
`208d69ac624910a29a7529934ddcc18bbac853e8`; index is empty. The other 21 tools
and five resources are not declared migrated by this increment.

## Changed behavior and ownership

- `sakai/courses.py:CourseOperations.list_my_courses` always calls existing
  `/direct/user/current.json`, `/api/users/me/sites`, and selected existing Direct
  site/permission/ACCESS reads. There is no legacy fallback or selector.
- Python validates current delegated EID, binds observations to the same verified
  identity, strips rich fields, checks effective native visit eligibility and
  preserves title/ID Java UTF-16 sorting and the first 500 visitable courses.
- Actual `EntitySite` plus `JSONTranscoder` characterization proves DTO ID and
  publication share the same mask. Exact nonempty ID therefore permits false
  publication to be interpreted as unpublished for ordinary public members.
  `entityId` metadata is separate and cannot override the DTO ID. Soft-deletion
  has a different mask; fresh native ACCESS selection is still required where
  true state is unavailable. Empty DTO IDs require exact matching metadata.
- The duplicate `sakai/existing_courses.py` migration helper and temporary
  `COURSE_READ_INTERFACE` setting were removed. The existing file conventions
  now place the real implementation in `sakai/courses.py`, wire parsing in
  `contracts/existing_api.py`, and access observations in `workflows/access.py`.
- After the default facade and SDK/JWT/OBO pipeline tests passed, removed only
  the old native `McpCourseController.courses` method, `Course` record and
  `canVisit` helper. Its announcement method remains for current consumers.
  No replacement native business handler or service was introduced.

## Fresh verification

`uv --directory services/mcp sync --locked` and `./scripts/check-mcp.sh` pass:
**364 Python tests**, Ruff lint/format, mypy on **59 source files**. The default
SDK/JWT/OBO integration test invokes `list_my_courses` for two separately signed
users and rejects any request to the retired route. Focused fixtures cover native
revocation, public/unpublished/deleted state, exact/masked identity, bounded
pagination, repeated pages, native page-size clamping, 500-course selection and
failure without fallback. Frozen public catalogs, schemas and evaluator/report
fingerprints pass unchanged; no fixtures were regenerated.

Fresh Java 17 reactor tests pass **100 tests**, zero failures/errors/skips:
23 shared-auth/container, four existing Site pages/ACCESS/visibility, 73 WebAPI,
legacy and Login regression tests. The new negative Spring MVC test confirms
`GET /mcp/v1/courses` is unregistered; the retained announcement method still
rejects an unrelated site before reading announcements. Ordinary login regression
and actual existing Sites/RequestFilter chain tests pass. The embedded Portal
test uses a synthetic receiving servlet; it does not prove native rendered views.

Native command (Java 17, temporary public-dependency Maven settings):

```sh
mvn -s /tmp/sakai-auth-public-deps-settings.xml -f apps/sakai/pom.xml \
  -pl webapi,mcp-auth,entitybroker/core-providers -am \
  '-Dtest=Mcp*Test,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,LoginControllerTests,ExistingPagesActionTest,ExistingSiteVisibilityTest' \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

Only generated WebAPI build output was cleaned before this verification, so old
flat-package classes from the preexisting restructuring cannot survive into the
fresh WebAPI compilation. The full log is `/tmp/sakai-t01-native-tests.log`.
Fresh wheel/sdist build passes. Wheel inspection confirms the default existing-HTTP
course implementation is present and the retired duplicate module is absent.
Fresh Java 17 `-pl webapi -am -DskipTests package` passed. WAR inspection found
only the current `McpCourseController` and retained `Announcement` record, with
no retired `Course` record or stale flat-package MCP classes. `javap` confirms
only the announcement method remains. Artifact: `apps/sakai/webapi/target/api-25.2.war`,
SHA-256 `db28beb02dcd8dd2aa937115edbf445908651883c7d780747597d5af5d7ba70e`. This local artifact is not deployed.
Package log: `/tmp/sakai-t01-native-package.log`.


Repository guidance and `git diff --check` pass. `check_scope.py --verify-progress`
passes for **201 starting paths, 26 reviewed byte changes**, unchanged presence
and modes, empty index and immutable private start/archive hashes. The scope check
retains all **23 historical** routes and verifies **22 active** source mappings;
T01 records its former dependency as historical and rejects current callers of
retired routes.

## Preservation and compatibility

The original baseline and implementation-start manifests were not rewritten.
A further owner-only, read-back-verified checkpoint at
`/Users/burhanahmadkhan/Downloads/Sakai-T01-Local-Cutover-2026-10-19/`
preserves 13 prior files and their hashes. The removed duplicate Python helper
was migration-owned and absent from the original start; no preexisting file was
deleted or restored. Unrelated restructuring, editor/CLI/SSH/CI/seeding work stays.

This is a local N2-style retirement for T01. **Do not deploy the dirty native tip
against P0 Python**, whose course tool needs the removed route. Before release,
select reviewed exact revisions: N1 additive auth retaining P0 routes; P1 existing
HTTP Python after delegated acceptance; then N2 retirement after all route users
are drained. Older Python rollback requires compatible native route support.
There is no releasable committed revision recorded by this uncommitted increment.
Ignored historical scripts/reference examples are not proof of active consumers;
retained compatibility inventory remains part of release preparation.

## Remaining gates and next capability

No live native role/cache/SQL, configured authentication, large-course performance
or delegated deployment acceptance was run. Test service doubles characterize
control flow and DTO encoding; they do not prove production membership caches or
SQL state. Rare masked publication states without enough status permissions fail
explicitly. Observations are not an atomic snapshot or concurrency guarantee.

T03 announcement reads are next. Existing Direct provider source catches some
channel/decoration errors, merges channels and trims results; selected-role,
ordering, date and completeness parity must be verified before its actual default
cutover and shared-method retirement. Existing native browser list/detail flows
remain the researched alternative. D3/D6 apply to later grading/store boundaries
and do not block independently answerable read migration.

No deployment, feature activation, runtime start/stop, academic write, schema
change, provisioning, record deletion or stored-artifact cleanup occurred.
