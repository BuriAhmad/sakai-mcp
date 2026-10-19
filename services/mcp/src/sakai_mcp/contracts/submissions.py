"""Existing SimpleSubmission DTOs, distinct from the modern grader action maps."""

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, StrictBool, StrictInt, StrictStr

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import AssignmentMetadata, observation_revision
from sakai_mcp.contracts.existing_api import Id, WireModel, parse
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import digest

REASONS = [
    "native_serializer_may_omit_records",
    "expected_roster_not_verified",
    "raw_release_and_lock_version_unavailable",
    "attachment_bytes_not_captured",
]


class WireSubmitter(WireModel):
    id: Id
    displayId: StrictStr | None = None
    displayName: StrictStr | None = None


class WireAttachment(WireModel):
    ref: StrictStr
    name: StrictStr
    size: StrictInt = Field(ge=0)
    type: StrictStr | None = None


class WireSubmission(WireModel):
    id: Id
    gradableId: Id
    submitted: StrictBool
    userSubmission: StrictBool
    graded: StrictBool
    returned: StrictBool
    draft: StrictBool
    submitters: list[WireSubmitter] = Field(min_length=1, max_length=100)
    submittedText: StrictStr | None = Field(default=None, max_length=65535, repr=False)
    submittedAttachments: list[WireAttachment] | None = Field(
        default=None, max_length=20
    )
    dateSubmittedEpochSeconds: StrictInt | None = Field(default=None, ge=0)
    groupId: Id | None = None
    grade: StrictStr | None = None
    late: StrictBool | None = None
    feedbackComment: StrictStr | None = Field(
        default=None, max_length=65535, repr=False
    )


class AssignmentEvidence(AssignmentMetadata):
    anonymousGrading: StrictBool
    submissions: list[dict[str, Any]] | None = Field(
        default=None, max_length=5000, repr=False
    )


def submitted_rows(assignment: AssignmentEvidence) -> list[WireSubmission]:
    if assignment.anonymousGrading or assignment.allowPeerAssessment is not False:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if assignment.draft:
        raise SakaiError(ErrorCode.NOT_FOUND)
    result = []
    seen: set[str] = set()
    for raw in assignment.submissions or []:
        row = parse(WireSubmission, raw)
        if row.gradableId != assignment.id or row.id in seen:
            raise SakaiError(ErrorCode.CONFLICT)
        seen.add(row.id)
        # These interfaces filter inactive submitters and may drop entire rows.
        # No all-submitter/group/anonymous scope guarantee is inferred here.
        if row.groupId or len(row.submitters) != 1:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if row.submitted:
            if row.submittedAttachments is None:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            result.append(row)
    return result


def submitted_at(row: WireSubmission) -> str | None:
    if row.dateSubmittedEpochSeconds is None:
        return None
    try:
        return (
            datetime.fromtimestamp(row.dateSubmittedEpochSeconds, UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (ValueError, OverflowError, OSError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def entry(
    row: WireSubmission, assignment: AssignmentEvidence
) -> native.SubmissionEntry:
    attachments = []
    refs: set[str] = set()
    for attachment in row.submittedAttachments or []:
        if attachment.ref in refs or not attachment.ref.startswith(
            ("/content/attachment/", "/content/group/")
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        refs.add(attachment.ref)
        attachments.append(
            native.Attachment(
                artifact_key=digest(attachment.ref.encode()),
                original_name=attachment.name,
                content_type=attachment.type,
                size_bytes=attachment.size,
                resource_revision=None,
                kind="url" if attachment.type == "text/url" else "file",
                readable=False,
            )
        )
    content_revision = observation_revision(
        {
            "kind": "submission-content",
            "assignment": assignment.id,
            "id": row.id,
            "submitters": [u.id for u in row.submitters],
            "submitted": row.submitted,
            "at": row.dateSubmittedEpochSeconds,
            "text": row.submittedText,
            "attachments": [a.model_dump() for a in attachments],
        }
    )
    grade_revision = observation_revision(
        {
            "kind": "submission-grade",
            "id": row.id,
            "grade": row.grade,
            "graded": row.graded,
            "returned": row.returned,
            "comment": row.feedbackComment,
        }
    )
    score = (
        row.grade
        if assignment.gradeScale == "SCORE_GRADE_TYPE" and row.grade not in {"", None}
        else None
    )
    # Native getGradeForSubmitter returns displayed units; never scale twice.
    # Comma/localized/letter values are unknown under this strict point model.
    if score is not None:
        import re

        if not re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]+)?", score):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    identities = [
        native.Identity(sakai_user_id=u.id, eid=u.displayId, display_name=u.displayName)
        for u in row.submitters
    ]
    return native.SubmissionEntry(
        student=identities[0],
        submitters=identities,
        submission_id=row.id,
        group_id=None,
        status="placeholder"
        if not row.userSubmission
        else (
            "ungraded_resubmission" if row.returned and not row.graded else "submitted"
        ),
        flags=None,
        submitted_at=submitted_at(row),
        returned_at=None,
        content_revision=content_revision,
        grade_revision=grade_revision,
        attempt_count=None,
        history_completeness="unknown",
        inline_text_present=bool(row.submittedText and row.submittedText.strip()),
        attachments=attachments,
        attachments_complete=False,
        late_status="unknown"
        if row.late is None
        else ("late" if row.late else "on_time"),
        overrides=native.Overrides(
            remaining_resubmissions=None,
            resubmission_close_at=None,
            extension_close_at=None,
            warnings=["overrides_not_observed"],
        ),
        score=score,
        warnings=[*REASONS, "unsubmitted_and_orphan_rows_not_enumerated"],
    )
