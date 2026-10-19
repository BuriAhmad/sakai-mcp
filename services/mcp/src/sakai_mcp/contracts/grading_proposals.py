"""MCP-facing grading contracts, separate from the native Sakai REST DTOs."""

from typing import Annotated, Literal

from mcp.types import ResourceLink
from pydantic import Field

from sakai_mcp.contracts import grading_native as native

Id = Annotated[str, Field(min_length=1, max_length=128)]
DecimalString = Annotated[
    str, Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", max_length=32)
]
UUIDString = Annotated[
    str,
    Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"),
]


class SubmissionContract(native.GradingModel):
    file_count: Literal[1]
    encoding: Literal["utf-8"]
    answer_count: Annotated[int, Field(ge=1, le=100)]
    alphabet: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=8)]],
        Field(min_length=1, max_length=26),
    ]
    filename: Annotated[str, Field(max_length=256)] | None


class Normalization(native.GradingModel):
    uppercase_answers: bool
    trim_answer_whitespace: bool
    extension_case: bool


class MCQRules(native.GradingModel):
    method: Literal["deterministic_mcq"]
    key: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=8)]],
        Field(min_length=1, max_length=100),
    ]
    max_points: DecimalString
    per_correct: DecimalString
    per_incorrect: Literal["0"]
    negative_marking: Literal[False]


class Policies(native.GradingModel):
    late_penalty: None


class IdentityPolicy(native.GradingModel):
    filename_mismatch: Literal["review_required", "recoverable"]


class MCQConfig(native.GradingModel):
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


class Criterion(native.GradingModel):
    line: Annotated[int, Field(ge=1, le=100)]
    answer: str
    correct: bool
    points: DecimalString


class ProposalRow(native.GradingModel):
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


class ProposalPayload(native.GradingModel):
    schema_version: Literal["2"] = "2"
    config: MCQConfig
    rows: Annotated[list[ProposalRow], Field(max_length=500)]


class ProposalRecord(native.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    request_sha256: str
    expires_at: str
    payload: ProposalPayload


class ProposalResult(native.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    expires_at: str
    total: int
    proposed: int
    review_required: int
    resources: list[ResourceLink]


class ProposalPage(native.GradingModel):
    proposal_id: UUIDString
    export_id: UUIDString
    expires_at: str
    config: MCQConfig
    rows: Annotated[list[ProposalRow], Field(max_length=100)]
    next_cursor: str | None
    total: int


class GradePayloadResult(native.GradingModel):
    kind: Literal["save", "release"]
    commit_arguments: (
        native.SaveAssignmentGradesRequest | native.ReleaseAssignmentGradesRequest
    )
    validation: native.SaveAssignmentGradesResult | native.ReleaseAssignmentGradesResult
