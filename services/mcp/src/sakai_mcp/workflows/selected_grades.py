"""Selected Assignment grades with rendered release evidence; no inferred projection."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import observation_revision
from sakai_mcp.contracts.gradebook_projection import Projection, projection
from sakai_mcp.contracts.native_forms import native_url
from sakai_mcp.contracts.native_html import Element, html, one
from sakai_mcp.contracts.submissions import REASONS, entry
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import digest
from sakai_mcp.sakai.browser_transport import NativePage
from sakai_mcp.workflows.access import ActorIdentity
from sakai_mcp.workflows.captures import assignment_revision
from sakai_mcp.workflows.submissions import SubmissionReads


def release_observations(
    page: NativePage, origin: str, site: str, assignment: str
) -> dict[tuple[str, str], bool]:
    """Source: list_submissions.vm; exact photo + grade link + released cell."""
    table = one(html(page.data).find(id="submissionList"))
    # Placement URL has already been bound by the browser conversation.
    parts = urlsplit(page.url).path.split("/")
    if len(parts) < 4 or parts[1:3] != ["portal", "tool"]:
        raise SakaiError(ErrorCode.CONFLICT)
    placement = parts[3]
    result = {}
    for row in table.find(tag="tr"):
        photos = row.find(tag="sakai-user-photo")
        if not photos:
            continue
        photo = one(photos)
        uid = photo.attrs.get("user-id")
        if uid in {None, "", "blank"}:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        links = []
        for link in row.find(tag="a"):
            href = link.attrs.get("href", "")
            query = parse_qs(urlsplit(href).query, keep_blank_values=True)
            if "eventSubmit_doGrade_submission" in query:
                native_url(origin, page.url, href, placement)
                if query.get("assignmentId") != [f"/assignment/a/{site}/{assignment}"]:
                    raise SakaiError(ErrorCode.CONFLICT)
                refs = query.get("submissionId", [])
                prefix = f"/assignment/s/{site}/{assignment}/"
                if len(refs) != 1 or not refs[0].startswith(prefix):
                    raise SakaiError(ErrorCode.CONFLICT)
                sid = refs[0][len(prefix) :]
                if not sid or "/" in sid:
                    raise SakaiError(ErrorCode.CONFLICT)
                links.append(sid)
        if not links:
            continue  # Missing-user rows cannot establish a submission's flags.
        if len(links) != 1:
            raise SakaiError(ErrorCode.CONFLICT)
        sid = links[0]
        cell = one(
            [c for c in row.find(tag="td") if c.attrs.get("headers") == "gradereleased"]
        )
        spans = cell.find(tag="span")
        if (
            cell.text().strip()
            or len(spans) > 1
            or any(isinstance(c, Element) and c.tag != "span" for c in cell.children)
            or (spans and "si-check" not in spans[0].attrs.get("class", "").split())
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        key = (sid, uid)
        if key in result:
            raise SakaiError(ErrorCode.CONFLICT)
        result[key] = bool(spans)
    return result


def paged_releases(
    pages: tuple[NativePage, ...], origin: str, site: str, assignment: str
) -> dict[tuple[str, str], bool]:
    result: dict[tuple[str, str], bool] = {}
    ids: set[str] = set()
    users: set[str] = set()
    for page in pages:
        rows = release_observations(page, origin, site, assignment)
        for (sid, uid), released in rows.items():
            if sid in ids or uid in users or len(result) >= 5000:
                raise SakaiError(ErrorCode.CONFLICT)
            ids.add(sid)
            users.add(uid)
            result[(sid, uid)] = released
    return result


async def gradebook_projection(
    submissions: SubmissionReads,
    token: AccessToken,
    expected_actor: ActorIdentity,
    site: str,
    assignment: str,
    users: set[str],
) -> Projection | None:
    # Instructor table is broader than selected Assignment rows. Establish native
    # full grading + item-edit + instructor authority before opening it.
    actor = await submissions.access.actor(token)
    if actor != expected_actor:
        raise SakaiError(ErrorCode.UNAUTHENTICATED)
    access = await submissions.access.course(token, actor, site)
    functions = await submissions.access.functions(token, access)
    if not {
        "gradebook.gradeAll",
        "gradebook.editAssignments",
        "section.role.instructor",
    } <= set(functions):
        return None
    bound = await submissions.discovery.resolve(token, site, "sakai.gradebookng")
    if bound.access.actor != actor:
        raise SakaiError(ErrorCode.UNAUTHENTICATED)
    async with submissions.browser.conversation(
        token, bound.target.placement, identity=actor.token_identity()
    ) as flow:
        page = await flow.navigate(bound.target.url + "/grades")
        result = projection(page.data, site, assignment, users)
    return result


async def selected_grades(
    submissions: SubmissionReads,
    token: AccessToken,
    request: native.GetAssignmentGradesRequest,
) -> native.GetAssignmentGradesResult:
    targets = [(r.submission_id, r.sakai_user_id) for r in request.rows]
    if len(set(targets)) != len(targets):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    actor, assignment, rows, page = await submissions.observed_source(
        token, request.course_id, request.assignment_id, all_pages=True
    )
    released = paged_releases(
        page, submissions.browser.origin, request.course_id, request.assignment_id
    )
    by_id = {r.id: r for r in rows}
    results = []
    for sid, uid in targets:
        row = by_id.get(sid)
        if row is None or len(row.submitters) != 1 or row.submitters[0].id != uid:
            raise SakaiError(ErrorCode.CONFLICT)
        if (sid, uid) not in released:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        observation = entry(row, assignment)
        if assignment.gradeScale != "SCORE_GRADE_TYPE":
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if observation.content_revision is None or observation.grade_revision is None:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        results.append(
            native.GradeRow(
                submission_id=sid,
                sakai_user_id=uid,
                content_revision=observation.content_revision,
                grade_revision=observation_revision(
                    {
                        "grade": observation.grade_revision,
                        "released": released[(sid, uid)],
                    }
                ),
                score=observation.score,
                feedback_sha256=digest(row.feedbackComment.encode())
                if row.feedbackComment is not None
                else None,
                flags=native.NativeFlags(
                    submitted=row.submitted,
                    user_submission=row.userSubmission,
                    graded=row.graded,
                    grade_released=released[(sid, uid)],
                    returned=row.returned,
                ),
                returned_at=None,
                gradebook_score=None,
                gradebook_comment_sha256=None,
                gradebook_state="unavailable",
                reason="independent_gradebook_readback_unavailable",
            )
        )
    # Reject an observable release-state race; no native snapshot or CAS is implied.
    after = await submissions._individual_pages(
        token, actor, request.course_id, request.assignment_id, all_pages=True
    )
    current = paged_releases(
        after, submissions.browser.origin, request.course_id, request.assignment_id
    )
    if any(
        current.get(key) is None or current[key] != released[key] for key in targets
    ):
        raise SakaiError(ErrorCode.CONFLICT)
    projected = await gradebook_projection(
        submissions,
        token,
        actor,
        request.course_id,
        request.assignment_id,
        {uid for _, uid in targets},
    )
    if projected is not None:
        for result in results:
            result.gradebook_score = projected.values[result.sakai_user_id]
            result.gradebook_state = "available"
            result.reason = "display_score_only_comment_unavailable"
    return native.GetAssignmentGradesResult(
        observed_at=datetime.now(UTC).isoformat(),
        assignment_revision=assignment_revision(assignment),
        gradebook=projected.link
        if projected is not None
        else native.Link(
            mode="unknown",
            gradebook_uid=None,
            item_id=None,
            external_id=None,
            released=None,
            counted=None,
            available=False,
            reason="independent_gradebook_readback_unavailable",
        ),
        rows=results,
        completeness=native.Completeness(
            complete=False,
            scope="site",
            reasons=[
                "gradebook_comment_bytes_unavailable"
                if projected is not None
                else "independent_gradebook_readback_unavailable",
                "native_reads_not_atomic",
            ],
        ),
        warnings=[
            *[r for r in REASONS if r != "raw_release_and_lock_version_unavailable"],
            "raw_lock_version_unavailable",
            "returned_at_unavailable",
            "release_observed_in_native_list",
            "observations_not_native_cas",
            *(projected.warnings if projected is not None else ()),
        ],
    )
