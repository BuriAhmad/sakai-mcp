"""Fixed existing HTTP interfaces with source provenance and semantic retry policy.

This is not a public operation dispatcher. No legacy MCP route belongs here.
Candidates with unresolved security/product/authentication requirements cannot execute.
"""

from dataclasses import dataclass
from enum import StrEnum
from string import Formatter
from types import MappingProxyType
from urllib.parse import quote, urlencode

from sakai_mcp.errors import ErrorCode, SakaiError

BASELINE = "b5b7800f0fcddf9d0db47276a66065189365d905"
WEB = "apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/controllers/"
PROVIDERS = "apps/sakai/entitybroker/core-providers/src/java/org/sakaiproject/entitybroker/providers/"
ASSIGNMENT = "apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/entityproviders/AssignmentEntityProvider.java"
SOAP = (
    "apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/Assignments.java"
)


class Effect(StrEnum):
    READ = "read"
    MAY_INITIALIZE = "may-initialize-native-state"
    WRITE = "write"


class Encoding(StrEnum):
    JSON = "json"
    CONTENT = "content"
    SOAP = "soap"


@dataclass(frozen=True)
class Operation:
    name: str
    method: str
    template: str
    source: str
    function: str
    card: str
    effect: Effect = Effect.READ
    encoding: Encoding = Encoding.JSON
    query_keys: frozenset[str] = frozenset()
    max_bytes: int = 1_000_000
    blocked_reason: str | None = None
    soap_operation: str | None = None

    @property
    def attempts(self) -> int:
        # Existing webservices include mutating GETs and read-only POSTs.
        return 3 if self.effect == Effect.READ else 1

    def path(
        self,
        parameters: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> str:
        parameters, query = parameters or {}, query or {}
        expected = {
            field for _, field, _, _ in Formatter().parse(self.template) if field
        }
        if set(parameters) != expected or not set(query) <= self.query_keys:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        encoded = {}
        for name, value in parameters.items():
            if name == "resource":
                if not isinstance(value, str) or not value.startswith(
                    ("/content/attachment/", "/content/group/")
                ):
                    raise SakaiError(ErrorCode.VALIDATION_ERROR)
                components = value.removeprefix("/content/").split("/")
                encoded[name] = "/".join(_segment(part) for part in components)
            else:
                encoded[name] = _segment(value)
        if any(
            not isinstance(v, str)
            or len(v) > 4096
            or any(ord(c) < 32 or ord(c) == 127 for c in v)
            for v in query.values()
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        path = self.template.format(**encoded)
        return path + ("?" + urlencode(query) if query else "")


def _segment(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 255
        or value != value.strip()
        or value in {".", ".."}
        or any(c in value for c in "/\\%?#;:")
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    return quote(value, safe="")


CURRENT_USER = Operation(
    "current-user",
    "GET",
    "/direct/user/current.json",
    PROVIDERS + "UserEntityProvider.java",
    "getCurrentUser",
    "A0",
)
CURRENT_SITE = Operation(
    "site",
    "GET",
    "/direct/site/{site}.json",
    PROVIDERS + "SiteEntityProvider.java",
    "getEntity",
    "A0",
)
USER_PERMISSIONS = Operation(
    "user-permissions",
    "GET",
    "/direct/site/{site}/userPerms.json",
    PROVIDERS + "SiteEntityProvider.java",
    "handleUserPerms",
    "A0",
)
SITES = Operation(
    "sites",
    "GET",
    "/api/users/me/sites",
    WEB + "SitesController.java",
    "getSites",
    "A1",
)
SITE_PAGES = Operation(
    "site-pages",
    "GET",
    "/direct/site/{site}/pages.json",
    PROVIDERS + "SiteEntityProvider.java",
    "getPagesAndTools",
    "B0",
)
ACCESS_SITES = Operation(
    "access-sites",
    "GET",
    "/direct/site.json",
    PROVIDERS + "SiteEntityProvider.java",
    "getEntities",
    "A0",
    query_keys=frozenset({"select", "_start", "_limit"}),
)
GRADES = Operation(
    "grade-summaries",
    "GET",
    "/api/sites/{site}/grades",
    WEB + "GradesController.java",
    "getSiteGrades",
    "A2",
    # Only OwnGradeReads may select this after excluding the native aggregate branch.
)
ITEM_DATA = Operation(
    "grading-item-data",
    "GET",
    "/api/sites/{site}/grading/item-data",
    WEB + "GradesController.java",
    "getSiteCategories",
    "A2",
    effect=Effect.MAY_INITIALIZE,
    # Authorized grader/editor metadata reads; may initialize native backing state.
)
ANNOUNCEMENTS = Operation(
    "announcements",
    "GET",
    "/direct/announcement/site/{site}.json",
    "apps/sakai/announcement/announcement-tool/tool/src/java/org/sakaiproject/announcement/entityprovider/AnnouncementEntityProviderImpl.java",
    "getAnnouncementsForSite",
    "A3",
    query_keys=frozenset({"n", "d", "a"}),
)
ASSIGNMENTS = Operation(
    "assignments",
    "GET",
    "/direct/assignment/site/{site}.json",
    ASSIGNMENT,
    "getAssignmentsForSite",
    "A4",
    # Adopted only by the site-wide-grader discovery workflow. Hydrates evidence;
    # never use for setup or group-restricted graders.
)
ASSIGNMENT_ITEM = Operation(
    "assignment-item",
    "GET",
    "/direct/assignment/item/{assignment}.json",
    ASSIGNMENT,
    "getAssignment",
    "A4",
    # Adopted only after site-wide authority and B7 individual/non-anonymous UI proof.
)
GRADABLE = Operation(
    "gradable",
    "GET",
    "/direct/assignment/gradable.json",
    ASSIGNMENT,
    "getGradableForSite",
    "A5",
    query_keys=frozenset({"gradableId", "submissionId"}),
    blocked_reason="D4: any-submitter scope and neighbor hydration require explicit coverage",
)
FULL_SUBMISSIONS = Operation(
    "full-submissions",
    "GET",
    "/direct/assignment/fullSubmissions.json",
    ASSIGNMENT,
    "getFullSubmissions",
    "A5",
    query_keys=frozenset({"gradableId", "submissionIds"}),
    blocked_reason="D4: selected IDs are not explicitly checked against assignment in provider",
)
SET_GRADE = Operation(
    "set-grade",
    "POST",
    "/direct/assignment/setGrade.json",
    ASSIGNMENT,
    "setGrade",
    "A7",
    effect=Effect.WRITE,
    # Adopted only by the supported single-row grading workflow after preflight.
)
CONTENT = Operation(
    "content",
    "GET",
    "/access/content/{resource}",
    "apps/sakai/kernel/kernel-impl/src/main/java/org/sakaiproject/content/impl/BaseContentService.java",
    "handleAccessResource",
    "A9",
    encoding=Encoding.CONTENT,
    max_bytes=10 * 1024 * 1024,
    blocked_reason="D4: selected-source scope, MIME and byte-fidelity acceptance required",
)
CALENDAR = Operation(
    "calendar",
    "GET",
    "/api/sites/{site}/calendar",
    WEB + "CalendarController.java",
    "getSiteCalendar",
    "A10",
    blocked_reason="D4: visit checks, backing-state effects and swallowed errors unverified",
)
SOAP_ASSIGNMENTS = Operation(
    "soap-assignments",
    "POST",
    "/sakai-ws/soap/assignments",
    SOAP,
    "getAssignmentsForContext",
    "A8",
    encoding=Encoding.SOAP,
    soap_operation="getAssignmentsForContext",
    blocked_reason="D5: CXF credential-argument integration and host policy unverified",
)
SOAP_CREATE_GET = Operation(
    "rest-create-assignment",
    "GET",
    "/sakai-ws/rest/assignments/createAssignment",
    SOAP,
    "createAssignment",
    "A8",
    effect=Effect.WRITE,
    blocked_reason="D2: immediately publishes with incompatible setup semantics; never invoke",
)
RAW_ASSIGNMENT = Operation(
    "raw-assignment-annc",
    "GET",
    "/direct/assignment/annc/{site}/{assignment}.json",
    ASSIGNMENT,
    "getAssignDataForAnnouncement",
    "A14",
    blocked_reason="D4: advisor, raw relationship serialization and authorization require investigation",
)

OPERATIONS = MappingProxyType(
    {
        op.name: op
        for op in (
            CURRENT_USER,
            CURRENT_SITE,
            USER_PERMISSIONS,
            SITES,
            SITE_PAGES,
            ACCESS_SITES,
            GRADES,
            ITEM_DATA,
            ANNOUNCEMENTS,
            ASSIGNMENTS,
            ASSIGNMENT_ITEM,
            GRADABLE,
            FULL_SUBMISSIONS,
            SET_GRADE,
            CONTENT,
            CALENDAR,
            SOAP_ASSIGNMENTS,
            SOAP_CREATE_GET,
            RAW_ASSIGNMENT,
        )
    }
)
