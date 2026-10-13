"""Opt-in grading tools, preserving strict flattened public contracts."""

from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from sakai_mcp import grading_models as gm
from sakai_mcp.audit import audit_call, record_outcome
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError


def register_grading_tools(server: MCPServer, client: SakaiClient) -> None:

    async def invoke(name: str, arguments: dict[str, Any]) -> Any:
        principal = get_access_token()
        if principal is None:
            raise ToolError(ErrorCode.UNAUTHENTICATED.value)
        kind = (
            "write"
            if name
            in {
                "save_assignment_grades",
                "release_assignment_grades",
                "export_assignment_submissions",
            }
            else "read"
        )
        async with audit_call(
            name, kind, arguments.get("course_id"), arguments.get("assignment_id")
        ):
            try:
                request_type, _ = gm.CONTRACTS[name]
                request = request_type.model_validate(arguments)
                result = await client.grading_request(name, principal, request)
                if getattr(result, "outcome", None) == "partial":
                    record_outcome("PARTIAL_SUCCESS")
                return result
            except ValidationError:
                raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    async def get_assignment_grading_context(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
    ) -> gm.GetAssignmentGradingContextResult:
        return gm.GetAssignmentGradingContextResult.model_validate(
            await invoke(
                "get_assignment_grading_context",
                {"course_id": course_id, "assignment_id": assignment_id},
            )
        )

    server.add_tool(
        get_assignment_grading_context,
        description="Read authoritative assignment configuration and scoped grading capabilities.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )

    async def list_assignment_submissions(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        cursor: Annotated[str, Field(max_length=2048)] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> gm.ListAssignmentSubmissionsResult:
        return gm.ListAssignmentSubmissionsResult.model_validate(
            await invoke(
                "list_assignment_submissions",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            )
        )

    server.add_tool(
        list_assignment_submissions,
        description="Page eligible students and current submission metadata, including missing rows.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )

    async def get_assignment_submission(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        submission_id: Annotated[str, Field(max_length=128, min_length=1)],
    ) -> gm.GetAssignmentSubmissionResult:
        return gm.GetAssignmentSubmissionResult.model_validate(
            await invoke(
                "get_assignment_submission",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "submission_id": submission_id,
                },
            )
        )

    server.add_tool(
        get_assignment_submission,
        description="Read one authorized current submission, bounded inline evidence and existing feedback.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )

    async def export_assignment_submissions(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        export_request_id: Annotated[
            str,
            Field(
                pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
            ),
        ],
        expected_assignment_revision: Annotated[
            str, Field(max_length=128, min_length=1)
        ],
        submissions: Annotated[
            list[gm.ExportSelection], Field(max_length=100, min_length=1)
        ],
    ) -> gm.ExportAssignmentSubmissionsResult:
        return gm.ExportAssignmentSubmissionsResult.model_validate(
            await invoke(
                "export_assignment_submissions",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "export_request_id": export_request_id,
                    "expected_assignment_revision": expected_assignment_revision,
                    "submissions": submissions,
                },
            )
        )

    server.add_tool(
        export_assignment_submissions,
        description="Capture selected current content into bounded temporary private artifacts; no academic mutation. Unknown outcomes require reconciliation; never replay blindly.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )

    async def get_assignment_submission_export(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        export_id: Annotated[str, Field(max_length=128, min_length=1)],
        cursor: Annotated[str, Field(max_length=2048)] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> gm.GetAssignmentSubmissionExportResult:
        return gm.GetAssignmentSubmissionExportResult.model_validate(
            await invoke(
                "get_assignment_submission_export",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "export_id": export_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            )
        )

    server.add_tool(
        get_assignment_submission_export,
        description="Read export status and paginated immutable artifact inventory.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )

    async def save_assignment_grades(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        operation_id: Annotated[
            str,
            Field(
                pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
            ),
        ],
        mode: Literal["validate", "commit"],
        expected_assignment_revision: Annotated[
            str, Field(max_length=128, min_length=1)
        ],
        payload_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")],
        grades: Annotated[list[gm.SaveRow], Field(max_length=100, min_length=1)],
    ) -> gm.SaveAssignmentGradesResult:
        return gm.SaveAssignmentGradesResult.model_validate(
            await invoke(
                "save_assignment_grades",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                    "mode": mode,
                    "expected_assignment_revision": expected_assignment_revision,
                    "payload_sha256": payload_sha256,
                    "grades": grades,
                },
            )
        )

    server.add_tool(
        save_assignment_grades,
        description="Validate or save exactly approved point grades and feedback without releasing; explicit TA approval required for commit. Unknown outcomes require reconciliation; never replay blindly.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )

    async def release_assignment_grades(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        operation_id: Annotated[
            str,
            Field(
                pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
            ),
        ],
        mode: Literal["validate", "commit"],
        expected_assignment_revision: Annotated[
            str, Field(max_length=128, min_length=1)
        ],
        payload_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")],
        grades: Annotated[list[gm.ReleaseRow], Field(max_length=100, min_length=1)],
    ) -> gm.ReleaseAssignmentGradesResult:
        return gm.ReleaseAssignmentGradesResult.model_validate(
            await invoke(
                "release_assignment_grades",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                    "mode": mode,
                    "expected_assignment_revision": expected_assignment_revision,
                    "payload_sha256": payload_sha256,
                    "grades": grades,
                },
            )
        )

    server.add_tool(
        release_assignment_grades,
        description="Validate or return selected saved grades and synchronize their verified external Gradebook projection; separate release approval required. Unknown outcomes require reconciliation; never replay blindly.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )

    async def get_assignment_grades(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        rows: Annotated[list[gm.Target], Field(max_length=100, min_length=1)],
    ) -> gm.GetAssignmentGradesResult:
        return gm.GetAssignmentGradesResult.model_validate(
            await invoke(
                "get_assignment_grades",
                {"course_id": course_id, "assignment_id": assignment_id, "rows": rows},
            )
        )

    server.add_tool(
        get_assignment_grades,
        description="Independently read exact Assignment and linked Gradebook values for selected targets.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )

    async def get_assignment_grading_operation(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
        operation_id: Annotated[
            str,
            Field(
                pattern="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
            ),
        ],
    ) -> gm.GetAssignmentGradingOperationResult:
        return gm.GetAssignmentGradingOperationResult.model_validate(
            await invoke(
                "get_assignment_grading_operation",
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                },
            )
        )

    server.add_tool(
        get_assignment_grading_operation,
        description="Read and reconcile a known principal-bound save or release receipt without committing pending work.",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
