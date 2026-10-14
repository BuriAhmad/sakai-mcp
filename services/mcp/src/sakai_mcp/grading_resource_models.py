"""MCP-facing grading contracts, separate from the native Sakai REST DTOs."""

from typing import Annotated, Literal

from mcp.types import ResourceLink
from pydantic import Field

from sakai_mcp import grading_models as gm

Id = Annotated[str, Field(min_length=1, max_length=128)]
DecimalString = Annotated[
    str, Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=32)
]
UUIDString = Annotated[
    str,
    Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
]


class Attachment(gm.Attachment):
    resource: ResourceLink | None = None
    resource_unavailable_reason: (
        Literal[
            "unsupported_attachment_kind",
            "unreadable",
            "over_budget",
            "metadata_unavailable",
            "missing_submission_revision",
        ]
        | None
    ) = None


class Submission(gm.SubmissionEntry):
    attachments: Annotated[list[Attachment], Field(max_length=20)]  # type: ignore[assignment]
    inline_resource: ResourceLink | None = None


class Assignment(gm.GetAssignmentGradingContextResultAssignment):
    attachments: Annotated[list[Attachment], Field(max_length=20)]  # type: ignore[assignment]


class ContextResult(gm.GetAssignmentGradingContextResult):
    # Native schema remains v1; the MCP-only resource representation is v2.
    schema_version: Literal["2"]  # type: ignore[assignment]
    assignment: Assignment


class SubmissionListResult(gm.ListAssignmentSubmissionsResult):
    schema_version: Literal["2"] = "2"
    items: Annotated[list[Submission], Field(max_length=100)]  # type: ignore[assignment]


class SubmissionResult(gm.GradingModel):
    schema_version: Literal["2"] = "2"
    submission: Submission
    feedback_comment: Annotated[str, Field(max_length=65535)] | None
    feedback_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None
    observed_at: str
    warnings: list[str]


class Artifact(gm.GradingModel):
    artifact_id: Id
    kind: Literal["archive", "attachment", "inline_text", "manifest"]
    submission_id: Id | None
    original_name: str | None
    content_type: str
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expires_at: str
    resource: ResourceLink


class ExportResult(gm.GradingModel):
    schema_version: Literal["2"] = "2"
    export_id: Id
    request_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    status: Literal["pending", "ready", "partial", "failed", "expired"]
    observed_at: str
    expires_at: str
    completeness: gm.Completeness
    rows: Annotated[list[gm.ExportRow], Field(max_length=100)]
    artifacts: Annotated[list[Artifact], Field(max_length=100)]
    archive: Artifact | None
    next_cursor: str | None
    warnings: list[str]


class AssignmentSummary(gm.GradingModel):
    assignment_id: Id
    title: Annotated[str, Field(max_length=65535)]
    configuration_revision: Id


class AssignmentListResult(gm.GradingModel):
    items: Annotated[list[AssignmentSummary], Field(max_length=100)]
    next_cursor: str | None
    snapshot_revision: Id


class SubmissionContract(gm.GradingModel):
    file_count: Literal[1]
    encoding: Literal["utf-8"]
    answer_count: Annotated[int, Field(ge=1, le=100)]
    alphabet: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=8)]],
        Field(min_length=1, max_length=26),
    ]
    filename: Annotated[str, Field(max_length=256)] | None


class Normalization(gm.GradingModel):
    uppercase_answers: bool
    trim_answer_whitespace: bool
    extension_case: bool


class MCQRules(gm.GradingModel):
    method: Literal["deterministic_mcq"]
    key: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=8)]],
        Field(min_length=1, max_length=100),
    ]
    max_points: DecimalString
    per_correct: DecimalString
    per_incorrect: Literal["0"]
    negative_marking: Literal[False]


class Policies(gm.GradingModel):
    late_penalty: None


class IdentityPolicy(gm.GradingModel):
    filename_mismatch: Literal["review_required", "recoverable"]


class MCQConfig(gm.GradingModel):
    course_id: Id
    assignment_id: Id
    assignment_revision: Id
    submission_contract: SubmissionContract
    normalization: Normalization
    grading: MCQRules
    policies: Policies
    identity: IdentityPolicy
    expected_filenames: Annotated[
        dict[Id, Annotated[str, Field(max_length=256)]], Field(max_length=500)
    ]


class Criterion(gm.GradingModel):
    line: Annotated[int, Field(ge=1, le=100)]
    answer: str
    correct: bool
    points: DecimalString


class ProposalRow(gm.GradingModel):
    submission_id: Id | None
    sakai_user_id: Id | None
    score: DecimalString | None
    max_score: DecimalString
    method: Literal["deterministic_mcq"] | None
    review_status: Literal["proposed", "review_required"]
    issues: list[str]
    criteria: Annotated[list[Criterion], Field(max_length=100)]
    content_revision: Id | None
    grade_revision: Id | None
    late_status: Literal["on_time", "late", "unknown"]
    config_sha256: str
    manifest_sha256: str
    engine_version: Literal["sakai-mcq-2"]
    engine_sha256: str


class ProposalPayload(gm.GradingModel):
    schema_version: Literal["2"] = "2"
    config: MCQConfig
    rows: Annotated[list[ProposalRow], Field(max_length=500)]


class ProposalRecord(gm.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    request_sha256: str
    expires_at: str
    payload: ProposalPayload


class ProposalResult(gm.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    expires_at: str
    total: int
    proposed: int
    review_required: int
    resources: list[ResourceLink]


class ProposalPage(gm.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    expires_at: str
    config: MCQConfig
    rows: Annotated[list[ProposalRow], Field(max_length=100)]
    next_cursor: str | None
    total: int


class GradePayloadResult(gm.GradingModel):
    kind: Literal["save", "release"]
    commit_arguments: gm.SaveAssignmentGradesRequest | gm.ReleaseAssignmentGradesRequest
    validation: gm.SaveAssignmentGradesResult | gm.ReleaseAssignmentGradesResult
