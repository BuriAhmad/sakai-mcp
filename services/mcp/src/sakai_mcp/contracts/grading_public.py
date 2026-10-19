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


class Attachment(native.Attachment):
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


class Submission(native.SubmissionEntry):
    attachments: Annotated[list[Attachment], Field(max_length=20)]  # type: ignore[assignment]
    inline_resource: ResourceLink | None = None


class Assignment(native.GetAssignmentGradingContextResultAssignment):
    attachments: Annotated[list[Attachment], Field(max_length=20)]  # type: ignore[assignment]


class ContextResult(native.GetAssignmentGradingContextResult):
    # Native schema remains v1; the MCP-only resource representation is v2.
    schema_version: Literal["2"]  # type: ignore[assignment]
    assignment: Assignment


class SubmissionListResult(native.ListAssignmentSubmissionsResult):
    schema_version: Literal["2"] = "2"
    items: Annotated[list[Submission], Field(max_length=100)]  # type: ignore[assignment]


class SubmissionResult(native.GradingModel):
    schema_version: Literal["2"] = "2"
    submission: Submission
    feedback_comment: Annotated[str, Field(max_length=65535)] | None
    feedback_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None
    observed_at: str
    warnings: list[str]


class Artifact(native.GradingModel):
    artifact_id: Id
    kind: Literal["archive", "attachment", "inline_text", "manifest"]
    submission_id: Id | None
    original_name: str | None
    content_type: str
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expires_at: str
    resource: ResourceLink


class ExportResult(native.GradingModel):
    schema_version: Literal["2"] = "2"
    export_id: Id
    request_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    status: Literal["pending", "ready", "partial", "failed", "expired"]
    observed_at: str
    expires_at: str
    completeness: native.Completeness
    rows: Annotated[list[native.ExportRow], Field(max_length=100)]
    artifacts: Annotated[list[Artifact], Field(max_length=100)]
    archive: Artifact | None
    next_cursor: str | None
    warnings: list[str]


class AssignmentSummary(native.GradingModel):
    assignment_id: Id
    title: Annotated[str, Field(max_length=65535)]
    configuration_revision: Id


class AssignmentListResult(native.GradingModel):
    items: Annotated[list[AssignmentSummary], Field(max_length=100)]
    next_cursor: str | None
    snapshot_revision: Id
