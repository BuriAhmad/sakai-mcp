"""Current-user Gradebook UI plus collision-safe existing native item identity."""

from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.existing_api import Grades, parse
from sakai_mcp.contracts.gradebook_ui import own_grade_rows
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.browser_transport import BrowserTransport
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import GRADES, ITEM_DATA
from sakai_mcp.workflows.access import AccessObservations
from sakai_mcp.workflows.placements import PlacementDiscovery

AGGREGATE_FUNCTIONS = frozenset(
    {"gradebook.gradeAll", "asn.grade", "assessment.gradeAssessment.any"}
)


class OwnGradeReads:
    def __init__(
        self, existing: ExistingApiTransport, browser: BrowserTransport
    ) -> None:
        self.existing, self.browser = existing, browser
        self.discovery = PlacementDiscovery(existing)
        self.access = AccessObservations(existing)

    async def read(self, principal: AccessToken, site: str) -> list[dict[str, Any]]:
        bound = await self.discovery.resolve(principal, site, "sakai.gradebookng")
        actor = bound.access.actor
        functions = await self.access.functions(principal, bound.access)
        if "gradebook.viewOwnGrades" not in functions:
            raise SakaiError(ErrorCode.FORBIDDEN)
        is_grader = bool(functions & AGGREGATE_FUNCTIONS)
        operation = ITEM_DATA if is_grader else GRADES
        observed = await self.existing.observe_json(
            operation, principal, parameters={"site": site}
        )
        actor.require_same(observed)
        identities: dict[str, tuple[int, str | None, Decimal | None]] = {}
        if is_grader:
            value = observed.value
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("items"), list)
                or len(value["items"]) > 5000
            ):
                raise SakaiError(ErrorCode.INTERNAL_ERROR)
            for row in value["items"]:
                if not isinstance(row, dict) or row.get("released") is not True:
                    continue
                name, item = row.get("name"), row.get("id")
                if (
                    not isinstance(name, str)
                    or type(item) is not int
                    or item <= 0
                    or name in identities
                ):
                    raise SakaiError(ErrorCode.CONFLICT)
                maximum = row.get("points")
                try:
                    points = Decimal(str(maximum)) if maximum is not None else None
                    if points is not None and (not points.is_finite() or points < 0):
                        raise ValueError
                except (InvalidOperation, ValueError):
                    raise SakaiError(ErrorCode.INTERNAL_ERROR) from None
                identities[name] = (item, None, points)
        else:
            for row in parse(Grades, observed.value).grades:
                if row.canGrade or row.siteId != site or row.name in identities:
                    raise SakaiError(ErrorCode.CONFLICT)
                identities[row.name] = (
                    row.id,
                    None if row.notGradedYet or row.score in {None, ""} else row.score,
                    None,
                )
        if len({v[0] for v in identities.values()}) != len(identities):
            raise SakaiError(ErrorCode.CONFLICT)
        placement = bound.target.placement
        async with self.browser.conversation(
            principal, placement, identity=actor.token_identity()
        ) as flow:
            # Existing GradebookNgApplication.mountPage('/gradebook', StudentPage).
            # No selected student argument; StudentPage uses getCurrentUser().
            page = await flow.navigate(bound.target.url.rstrip("/") + "/gradebook")
            rows = own_grade_rows(page.data)
        result = []
        for row in rows:
            if row.title not in identities:
                raise SakaiError(ErrorCode.CONFLICT)
            item, native_score, native_points = identities[row.title]
            if not is_grader and native_score is not None and row.score is not None:
                try:
                    equal = Decimal(native_score) == Decimal(row.score)
                except InvalidOperation:
                    equal = native_score == row.score
                if not equal:
                    raise SakaiError(ErrorCode.CONFLICT)
            if not is_grader and (native_score is None) != (row.score is None):
                raise SakaiError(ErrorCode.CONFLICT)
            if (
                native_points is not None
                and row.points is not None
                and native_points != row.points
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            points = native_points if native_points is not None else row.points
            maximum = float(points) if points is not None else None
            if maximum is not None and not isfinite(maximum):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            result.append(
                {
                    "itemId": item,
                    "title": row.title,
                    "score": row.score if is_grader else native_score,
                    "pointsPossible": maximum,
                }
            )
        return sorted(result, key=lambda r: r["itemId"])
