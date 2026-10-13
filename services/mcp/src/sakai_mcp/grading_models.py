"""Strict contracts for opt-in grading; generated from the reviewed design schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GradingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class GetAssignmentGradingContextRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]


class GetAssignmentGradingContextResultCourse(GradingModel):
    id: Annotated[str, Field(max_length=128, min_length=1)]
    title: Annotated[str, Field(max_length=65535)]


class Attachment(GradingModel):
    artifact_key: Annotated[str, Field(max_length=128, min_length=1)]
    original_name: Annotated[str, Field(max_length=65535)]
    content_type: Annotated[str, Field(max_length=65535)] | None
    size_bytes: Annotated[int, Field(ge=0)] | None
    resource_revision: Annotated[str, Field(max_length=128, min_length=1)] | None
    kind: Literal["file", "url", "inline_content_review"]
    readable: bool


class GetAssignmentGradingContextResultAssignment(GradingModel):
    id: Annotated[str, Field(max_length=128, min_length=1)]
    title: Annotated[str, Field(max_length=65535)]
    instructions: Annotated[str, Field(max_length=65535)]
    configuration_revision: Annotated[str, Field(max_length=128, min_length=1)]
    grade_type: Annotated[str, Field(max_length=128, min_length=1)]
    max_points: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    scale_factor: Annotated[int, Field(ge=1)]
    submission_type: Annotated[str, Field(max_length=128, min_length=1)]
    draft: bool
    deleted: bool
    visible_at: str | None
    open_at: str | None
    due_at: str | None
    close_at: str | None
    group_submission: bool
    anonymous_grading: bool
    native_release_grades: bool
    resubmission_count: Annotated[int, Field(ge=-1)] | None
    resubmission_close_at: str | None
    definition_reference: Annotated[str, Field(max_length=128, min_length=1)] | None
    definition_version: Annotated[str, Field(max_length=128, min_length=1)] | None
    attachments: Annotated[list[Attachment], Field(max_length=20)]
    integration_features: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class Link(GradingModel):
    mode: Literal["none", "external", "internal", "group", "unknown"]
    gradebook_uid: Annotated[str, Field(max_length=128, min_length=1)] | None
    item_id: Annotated[str, Field(max_length=128, min_length=1)] | None
    external_id: Annotated[str, Field(max_length=128, min_length=1)] | None
    released: bool | None
    counted: bool | None
    available: bool
    reason: Annotated[str, Field(max_length=128, min_length=1)] | None


class Permissions(GradingModel):
    read_metadata: bool
    read_content: bool
    save_grades: bool
    release_grades: bool
    scope: Literal["site", "groups", "none"]
    scope_complete: bool


class GetAssignmentGradingContextResultSubmissionSummary(GradingModel):
    expected_students: Annotated[int, Field(ge=0)] | None
    submitted: Annotated[int, Field(ge=0)] | None
    missing: Annotated[int, Field(ge=0)] | None
    draft: Annotated[int, Field(ge=0)] | None
    graded: Annotated[int, Field(ge=0)] | None
    orphan_records: Annotated[int, Field(ge=0)] | None


class Completeness(GradingModel):
    complete: bool
    scope: Literal["site", "groups"]
    reasons: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class GetAssignmentGradingContextResultSupported(GradingModel):
    prepare: bool
    save: bool
    release: bool
    reasons: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class GetAssignmentGradingContextResult(GradingModel):
    schema_version: Literal["1"]
    observed_at: str
    course: GetAssignmentGradingContextResultCourse
    assignment: GetAssignmentGradingContextResultAssignment
    gradebook: Link
    permissions: Permissions
    submission_summary: GetAssignmentGradingContextResultSubmissionSummary
    completeness: Completeness
    supported: GetAssignmentGradingContextResultSupported
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class ListAssignmentSubmissionsRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    cursor: Annotated[str, Field(max_length=2048)] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50


class Identity(GradingModel):
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]
    eid: Annotated[str, Field(max_length=128, min_length=1)] | None
    display_name: Annotated[str, Field(max_length=65535)] | None


class NativeFlags(GradingModel):
    submitted: bool
    user_submission: bool
    graded: bool
    grade_released: bool
    returned: bool


class Overrides(GradingModel):
    remaining_resubmissions: Annotated[int, Field(ge=-1)] | None
    resubmission_close_at: str | None
    extension_close_at: str | None
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class SubmissionEntry(GradingModel):
    student: Identity | None
    submitters: Annotated[list[Identity], Field(max_length=100)]
    submission_id: Annotated[str, Field(max_length=128, min_length=1)] | None
    group_id: Annotated[str, Field(max_length=128, min_length=1)] | None
    status: Literal[
        "missing",
        "draft",
        "placeholder",
        "submitted",
        "ungraded_resubmission",
        "orphan",
        "unknown",
    ]
    flags: NativeFlags | None
    submitted_at: str | None
    returned_at: str | None
    content_revision: Annotated[str, Field(max_length=128, min_length=1)] | None
    grade_revision: Annotated[str, Field(max_length=128, min_length=1)] | None
    attempt_count: Annotated[int, Field(ge=0)] | None
    history_completeness: Literal["unknown", "current_only"]
    inline_text_present: bool
    attachments: Annotated[list[Attachment], Field(max_length=20)]
    attachments_complete: bool
    late_status: Literal["on_time", "late", "unknown"]
    overrides: Overrides
    score: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class ListAssignmentSubmissionsResult(GradingModel):
    items: Annotated[list[SubmissionEntry], Field(max_length=100)]
    next_cursor: Annotated[str, Field(max_length=2048)] | None
    snapshot_revision: Annotated[str, Field(max_length=128, min_length=1)]
    observed_at: str
    completeness: Completeness
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class GetAssignmentSubmissionRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]


class GetAssignmentSubmissionResult(GradingModel):
    submission: SubmissionEntry
    inline_text: Annotated[str, Field(max_length=65535)] | None
    inline_content_type: Literal["text/html"] | None
    feedback_comment: Annotated[str, Field(max_length=65535)] | None
    feedback_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None
    observed_at: str
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class ExportSelection(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    expected_content_revision: Annotated[str, Field(max_length=128, min_length=1)]


class ExportAssignmentSubmissionsRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    export_request_id: Annotated[
        str,
        Field(pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
    ]
    expected_assignment_revision: Annotated[str, Field(max_length=128, min_length=1)]
    submissions: Annotated[list[ExportSelection], Field(max_length=100, min_length=1)]


class ExportAssignmentSubmissionsResult(GradingModel):
    export_id: Annotated[str, Field(max_length=128, min_length=1)]
    request_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    status: Literal["pending", "ready", "partial", "failed"]
    expires_at: str
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class GetAssignmentSubmissionExportRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    export_id: Annotated[str, Field(max_length=128, min_length=1)]
    cursor: Annotated[str, Field(max_length=2048)] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50


class ExportRow(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_ids: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=100)
    ]
    content_revision: Annotated[str, Field(max_length=128, min_length=1)]
    captured_at: str | None
    status: Literal["ready", "incomplete", "source_changed", "failed"]
    artifact_ids: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=21)
    ]
    reasons: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class Artifact(GradingModel):
    artifact_id: Annotated[str, Field(max_length=128, min_length=1)]
    kind: Literal["archive", "attachment", "inline_text", "manifest"]
    submission_id: Annotated[str, Field(max_length=128, min_length=1)] | None
    original_name: Annotated[str, Field(max_length=65535)] | None
    relative_path: Annotated[str, Field(max_length=65535)]
    content_type: Annotated[str, Field(max_length=65535)]
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    download_path: Annotated[
        str, Field(pattern="^/grading-artifacts/", max_length=2048)
    ]
    expires_at: str


class ExportReceipt(GradingModel):
    export_id: Annotated[str, Field(max_length=128, min_length=1)]
    request_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    status: Literal["pending", "ready", "partial", "failed", "expired"]
    observed_at: str
    expires_at: str
    completeness: Completeness
    rows: Annotated[list[ExportRow], Field(max_length=100)]
    artifacts: Annotated[list[Artifact], Field(max_length=100)]
    archive: Artifact | None
    next_cursor: Annotated[str, Field(max_length=2048)] | None
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


GetAssignmentSubmissionExportResult = ExportReceipt


class FeedbackPatch(GradingModel):
    action: Literal["preserve", "replace", "clear"]
    text: Annotated[str, Field(max_length=65535)] | None

    @model_validator(mode="after")
    def validate_patch(self):
        if (self.action == "replace") != (self.text is not None):
            raise ValueError("replace requires text; preserve/clear require null")
        return self


class SaveRow(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]
    expected_content_revision: Annotated[str, Field(max_length=128, min_length=1)]
    expected_grade_revision: Annotated[str, Field(max_length=128, min_length=1)]
    score: Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
    feedback: FeedbackPatch


class SaveAssignmentGradesRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    operation_id: Annotated[
        str,
        Field(pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
    ]
    mode: Literal["validate", "commit"]
    expected_assignment_revision: Annotated[str, Field(max_length=128, min_length=1)]
    payload_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    grades: Annotated[list[SaveRow], Field(max_length=100, min_length=1)]


class RowReceipt(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]
    stage: Literal[
        "pending",
        "validated",
        "saved",
        "assignment_released",
        "gradebook_synced",
        "verified",
        "conflict",
        "failed",
        "unknown",
    ]
    content_revision: Annotated[str, Field(max_length=128, min_length=1)] | None
    grade_revision: Annotated[str, Field(max_length=128, min_length=1)] | None
    assignment_score: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    grade_released: bool | None
    returned: bool | None
    gradebook_score: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    reason: Annotated[str, Field(max_length=128, min_length=1)] | None
    retry_action: Literal[
        "none",
        "read_operation",
        "refresh_and_review",
        "resume_pending_after_reconciliation",
        "human_reconciliation",
    ]


class OperationReceipt(GradingModel):
    operation_id: Annotated[str, Field(max_length=128, min_length=1)]
    kind: Literal["save", "release"]
    mode: Literal["validate", "commit"]
    payload_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    outcome: Literal["validated", "completed", "partial", "rejected", "unknown"]
    observed_at: str
    rows: Annotated[list[RowReceipt], Field(max_length=100)]
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


SaveAssignmentGradesResult = OperationReceipt


class ReleaseRow(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]
    expected_content_revision: Annotated[str, Field(max_length=128, min_length=1)]
    expected_grade_revision: Annotated[str, Field(max_length=128, min_length=1)]
    expected_score: Annotated[
        str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)
    ]
    expected_feedback_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None


class ReleaseAssignmentGradesRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    operation_id: Annotated[
        str,
        Field(pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
    ]
    mode: Literal["validate", "commit"]
    expected_assignment_revision: Annotated[str, Field(max_length=128, min_length=1)]
    payload_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    grades: Annotated[list[ReleaseRow], Field(max_length=100, min_length=1)]


ReleaseAssignmentGradesResult = OperationReceipt


class Target(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]


class GetAssignmentGradesRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    rows: Annotated[list[Target], Field(max_length=100, min_length=1)]


class GradeRow(GradingModel):
    submission_id: Annotated[str, Field(max_length=128, min_length=1)]
    sakai_user_id: Annotated[str, Field(max_length=128, min_length=1)]
    content_revision: Annotated[str, Field(max_length=128, min_length=1)]
    grade_revision: Annotated[str, Field(max_length=128, min_length=1)]
    score: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    feedback_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None
    flags: NativeFlags
    returned_at: str | None
    gradebook_score: (
        Annotated[str, Field(pattern="^(0|[1-9][0-9]*)(\\.[0-9]+)?$", max_length=32)]
        | None
    )
    gradebook_comment_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None
    gradebook_state: Literal["not_linked", "available", "unavailable"]
    reason: Annotated[str, Field(max_length=128, min_length=1)] | None


class GetAssignmentGradesResult(GradingModel):
    observed_at: str
    assignment_revision: Annotated[str, Field(max_length=128, min_length=1)]
    gradebook: Link
    rows: Annotated[list[GradeRow], Field(max_length=100)]
    completeness: Completeness
    warnings: Annotated[
        list[Annotated[str, Field(max_length=128, min_length=1)]], Field(max_length=30)
    ]


class GetAssignmentGradingOperationRequest(GradingModel):
    course_id: Annotated[str, Field(max_length=128, min_length=1)]
    assignment_id: Annotated[str, Field(max_length=128, min_length=1)]
    operation_id: Annotated[
        str,
        Field(pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
    ]


GetAssignmentGradingOperationResult = OperationReceipt

CONTRACTS: dict[str, tuple[type[GradingModel], type[GradingModel]]] = {
    "get_assignment_grading_context": (
        GetAssignmentGradingContextRequest,
        GetAssignmentGradingContextResult,
    ),
    "list_assignment_submissions": (
        ListAssignmentSubmissionsRequest,
        ListAssignmentSubmissionsResult,
    ),
    "get_assignment_submission": (
        GetAssignmentSubmissionRequest,
        GetAssignmentSubmissionResult,
    ),
    "export_assignment_submissions": (
        ExportAssignmentSubmissionsRequest,
        ExportAssignmentSubmissionsResult,
    ),
    "get_assignment_submission_export": (
        GetAssignmentSubmissionExportRequest,
        GetAssignmentSubmissionExportResult,
    ),
    "save_assignment_grades": (SaveAssignmentGradesRequest, SaveAssignmentGradesResult),
    "release_assignment_grades": (
        ReleaseAssignmentGradesRequest,
        ReleaseAssignmentGradesResult,
    ),
    "get_assignment_grades": (GetAssignmentGradesRequest, GetAssignmentGradesResult),
    "get_assignment_grading_operation": (
        GetAssignmentGradingOperationRequest,
        GetAssignmentGradingOperationResult,
    ),
}
