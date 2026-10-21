"""Narrow instructor context over existing HTTP; full roster remains unavailable."""

from datetime import UTC, datetime
from decimal import Decimal

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import observation_revision
from sakai_mcp.contracts.grading_context_candidate import raw_assignment_state
from sakai_mcp.contracts.setup_forms import core_supported
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.operations import CURRENT_SITE, RAW_ASSIGNMENT
from sakai_mcp.workflows.assignment_setup import AssignmentSetup
from sakai_mcp.workflows.submissions import SubmissionReads


class GradingContextReads:
    def __init__(self, source: SubmissionReads) -> None:
        self.source = source
        self.setup = AssignmentSetup(source, None)

    async def read(
        self, token: AccessToken, request: native.GetAssignmentGradingContextRequest
    ) -> native.GetAssignmentGradingContextResult:
        site, aid = request.course_id, request.assignment_id
        actor = await self.source.access.actor(token)
        access = await self.source.access.course(token, actor, site)
        functions = await self.source.access.functions(token, access)
        if (
            not {"asn.grade", "asn.new", "asn.revise", "gradebook.editAssignments"}
            <= functions
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        # Native list/detail and edit checks precede the advisor-bearing helper.
        # Never use raw A14 to bootstrap hidden/draft/group/anonymous access.
        current_actor, metadata, _ = await self.source.source(token, site, aid)
        if actor != current_actor:
            raise SakaiError(ErrorCode.UNAUTHENTICATED)
        form = await self.setup.edit_observation(token, site, aid, expected_actor=actor)
        core_supported(form)
        observed = await self.source.existing.observe_json(
            RAW_ASSIGNMENT, token, parameters={"site": site, "assignment": aid}
        )
        actor.require_same(observed)
        raw = raw_assignment_state(observed.value, site, aid)
        if (
            raw.draft
            or raw.deleted
            or raw.isGroup
            or raw.allowPeerAssessment
            or raw.contentReview
            or raw.groups
            or raw.attachments
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if raw.title != metadata.title:
            raise SakaiError(ErrorCode.CONFLICT)
        # Finite exact decimal display subset, without rounding a repeating ratio.
        if raw.scaleFactor > 1_000_000_000 or str(raw.scaleFactor).strip("0") != "1":
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        maximum = format(Decimal(raw.maxGradePoint) / Decimal(raw.scaleFactor), "f")
        if (
            metadata.gradeScale != "SCORE_GRADE_TYPE"
            or metadata.gradeScaleMaxPoints is None
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if Decimal(maximum) != Decimal(metadata.gradeScaleMaxPoints):
            raise SakaiError(ErrorCode.CONFLICT)
        course = await self.source.existing.observe_json(
            CURRENT_SITE, token, parameters={"site": site}
        )
        actor.require_same(course)
        if not isinstance(course.value, dict) or not isinstance(
            course.value.get("title"), str
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        count = raw.properties.get("allow_resubmit_number")
        close = raw.properties.get("allow_resubmit_closeTime")
        if count is not None and count not in {"-1", *map(str, range(11))}:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        resubmit = None
        if close is not None:
            if not close.isascii() or not close.isdecimal() or len(close) > 15:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            try:
                resubmit = datetime.fromtimestamp(int(close) / 1000, UTC).isoformat()
            except (ValueError, OverflowError, OSError):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY) from None
        values = raw.model_dump()
        # Exclude student relationships; the parser never retains them.
        revision = "httpctx1-" + observation_revision(values).removeprefix("http1-")
        return native.GetAssignmentGradingContextResult(
            schema_version="1",
            observed_at=datetime.now(UTC).isoformat(),
            course=native.GetAssignmentGradingContextResultCourse(
                id=site, title=course.value["title"]
            ),
            assignment=native.GetAssignmentGradingContextResultAssignment(
                id=aid,
                title=raw.title,
                instructions=raw.instructions or "",
                configuration_revision=revision,
                grade_type=metadata.gradeScale,
                max_points=maximum,
                scale_factor=raw.scaleFactor,
                submission_type=metadata.submissionType,
                draft=raw.draft,
                deleted=raw.deleted,
                visible_at=raw.visibleDate.stamp() if raw.visibleDate else None,
                open_at=raw.openDate.stamp() if raw.openDate else None,
                due_at=raw.dueDate.stamp() if raw.dueDate else None,
                close_at=raw.closeDate.stamp() if raw.closeDate else None,
                group_submission=raw.isGroup,
                anonymous_grading=metadata.anonymousGrading,
                native_release_grades=raw.releaseGrades,
                resubmission_count=int(count) if count is not None else None,
                resubmission_close_at=resubmit,
                definition_reference=None,
                definition_version=None,
                attachments=[],
                integration_features=[],
            ),
            gradebook=native.Link(
                mode="unknown",
                gradebook_uid=None,
                item_id=None,
                external_id=None,
                released=None,
                counted=None,
                available=False,
                reason="independent_gradebook_link_not_observed",
            ),
            permissions=native.Permissions(
                read_metadata=True,
                read_content=True,
                save_grades=False,
                release_grades=False,
                scope="site",
                scope_complete=False,
            ),
            submission_summary=native.GetAssignmentGradingContextResultSubmissionSummary(
                expected_students=None,
                submitted=None,
                missing=None,
                draft=None,
                graded=None,
                orphan_records=None,
            ),
            completeness=native.Completeness(
                complete=False,
                scope="site",
                reasons=[
                    "expected_roster_not_verified",
                    "independent_gradebook_link_not_observed",
                ],
            ),
            supported=native.GetAssignmentGradingContextResultSupported(
                prepare=False,
                save=False,
                release=False,
                reasons=[
                    "expected_roster_not_verified",
                    "context_revision_not_http_write_projection",
                ],
            ),
            warnings=[
                "bounded_authorized_raw_relationship_overfetch",
                "observations_not_native_cas",
                "instructor_edit_subset_only",
            ],
        )
