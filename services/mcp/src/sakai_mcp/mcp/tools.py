"""All public MCP tool definitions, explicit schemas, annotations, and feature gates.

Handlers delegate native operations and coordinated work. No HTTP or evaluation lives here.
"""

import base64
from typing import Annotated, Any, Literal, get_type_hints

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextResourceContents,
    ToolAnnotations,
)
from pydantic import Field, ValidationError

from sakai_mcp.audit import audit_call, record_created, record_outcome
from sakai_mcp.config import Settings
from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts import grading_proposals as proposals
from sakai_mcp.contracts import grading_public as public
from sakai_mcp.contracts.assignment_setup import (
    AssessmentContext,
    CreateAssignmentRequest,
    GradebookConfiguration,
    PublishAssignmentRequest,
    Resubmission,
    SetupResult,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.mcp.context import invoke_grading, principal
from sakai_mcp.mcp.presenters import (
    paginate_rows,
    present_announcement,
    present_resource,
    present_submission,
    receipt,
    tool_result,
)
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.workflows.grading import GradingWorkflow
from sakai_mcp.workflows.resources import parse_uri, read_resource

READ_HINTS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
WRITE_HINTS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
READ = READ_HINTS
PREPARE = WRITE_HINTS


def register_tools(server: MCPServer, settings: Settings, client: SakaiClient) -> None:
    @server.tool(
        description="List courses the signed-in Sakai user can visit.",
        annotations=READ_HINTS,
    )
    async def list_my_courses() -> dict[str, Any]:
        async with audit_call("list_my_courses", "read"):
            try:
                courses = await client.courses.list_my_courses(principal())
                return {"courses": courses}
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Read only the signed-in user's released grades in a course.",
        annotations=READ_HINTS,
    )
    async def get_my_grades(course_id: str) -> dict[str, Any]:
        async with audit_call("get_my_grades", "read", course_id):
            try:
                grades = await client.courses.get_my_grades(principal(), course_id)
                return {
                    "grades": grades,
                    "coverage": {
                        "score_representation": "native-own-view",
                        "display_precision_may_apply": True,
                    },
                }
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Read visible announcements from a course.", annotations=READ_HINTS
    )
    async def get_course_announcements(
        course_id: str, cursor: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        async with audit_call("get_course_announcements", "read", course_id):
            try:
                token = principal()
                if not token.subject:
                    raise SakaiError(ErrorCode.UNAUTHENTICATED)
                announcements = await client.announcements.get_course_announcements(
                    token, course_id
                )
                result = paginate_rows(
                    [present_announcement(row) for row in announcements],
                    cursor,
                    limit,
                    settings,
                    50,
                    scope=(token.subject, course_id),
                )
                result["coverage"] = {
                    "kind": "existing-provider-observation",
                    "complete": False,
                    "lookback_days": 3650,
                    "reason": "Native merged-channel selection and skipped rows cannot certify completeness.",
                }
                return result
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Read submission metadata the signed-in grader may see.",
        annotations=READ_HINTS,
    )
    async def get_course_submissions(
        course_id: str,
        assignment_id: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        async with audit_call(
            "get_course_submissions", "read", course_id, assignment_id
        ):
            try:
                token = principal()
                if not token.subject:
                    raise SakaiError(ErrorCode.UNAUTHENTICATED)
                submissions = await client.assignments.get_course_submissions(
                    token, course_id, assignment_id
                )
                result = paginate_rows(
                    [present_submission(row) for row in submissions],
                    cursor,
                    limit,
                    settings,
                    100,
                    scope=(token.subject, course_id, assignment_id),
                )
                result["coverage"] = {
                    "complete": False,
                    "reason": "Native serializers may omit submissions and inactive submitters; timestamps expose whole seconds.",
                }
                return result
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Create one plain course announcement when Sakai permits it.",
        annotations=WRITE_HINTS,
    )
    async def create_course_announcement(
        course_id: str, title: str, body: str
    ) -> dict[str, Any]:
        async with audit_call("create_course_announcement", "write", course_id):
            try:
                announcement = await client.announcements.create_course_announcement(
                    principal(), course_id, title, body
                )
                record_created(announcement["id"])
                return {"announcement": announcement}
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    if settings.assignment_setup_enabled:

        @server.tool(
            description="Inspect instructor assessment metadata, links and completeness before setup.",
            annotations=READ_HINTS,
        )
        async def get_course_assessment_context(
            course_id: str,
            window_start: str | None = None,
            window_end: str | None = None,
        ) -> AssessmentContext:
            async with audit_call("get_course_assessment_context", "read", course_id):
                try:
                    return await client.assignments.get_course_assessment_context(
                        principal(), course_id, window_start, window_end
                    )
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        async def create_assignment(
            course_id: str,
            title: str,
            instructions: str,
            timezone: str,
            visible_at: str | None,
            open_at: str,
            due_at: str,
            close_at: str,
            max_points: float,
            submission_type: Literal[
                "text_only",
                "attachments_only",
                "text_and_attachments",
                "non_electronic",
                "single_attachment",
            ],
            resubmission: Resubmission,
            publication: Literal["draft", "published"],
            attachment_resource_refs: list[str],
            gradebook: GradebookConfiguration,
            calendar_deadline: Literal["none", "course_calendar"],
        ) -> SetupResult:
            async with audit_call("create_assignment", "write", course_id):
                try:
                    request = CreateAssignmentRequest(
                        course_id=course_id,
                        title=title,
                        instructions=instructions,
                        timezone=timezone,
                        visible_at=visible_at,
                        open_at=open_at,
                        due_at=due_at,
                        close_at=close_at,
                        max_points=max_points,
                        submission_type=submission_type,
                        resubmission=resubmission,
                        publication=publication,
                        attachment_resource_refs=attachment_resource_refs,
                        gradebook=gradebook,
                        calendar_deadline=calendar_deadline,
                    )
                    result = await client.assignments.create_assignment(
                        principal(), request
                    )
                    record_created(result.assignment_id)
                    if result.outcome == "partial":
                        record_outcome("PARTIAL_SUCCESS")
                    return result
                except ValidationError:
                    raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        async def publish_assignment(
            course_id: str,
            assignment_id: str,
            expected_assignment_revision: str,
            gradebook: GradebookConfiguration,
            calendar_deadline: Literal["none", "course_calendar"],
        ) -> SetupResult:
            async with audit_call(
                "publish_assignment", "write", course_id, assignment_id
            ):
                try:
                    request = PublishAssignmentRequest(
                        course_id=course_id,
                        assignment_id=assignment_id,
                        expected_assignment_revision=expected_assignment_revision,
                        gradebook=gradebook,
                        calendar_deadline=calendar_deadline,
                    )
                    result = await client.assignments.publish_assignment(
                        principal(), request
                    )
                    if result.outcome == "partial":
                        record_outcome("PARTIAL_SUCCESS")
                    return result
                except ValidationError:
                    raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        # Publish the same field bounds as the validated contracts, including nested definitions.
        create_assignment.__annotations__.update(
            get_type_hints(CreateAssignmentRequest, include_extras=True)
        )
        publish_assignment.__annotations__.update(
            get_type_hints(PublishAssignmentRequest, include_extras=True)
        )
        server.add_tool(
            create_assignment,
            description="Create a points-based site assignment and coordinate approved linked objects. Never replay an ambiguous create.",
            annotations=WRITE_HINTS,
        )
        server.add_tool(
            publish_assignment,
            description="Promote or resume one known assignment using its observed revision. Creates only missing owned links.",
            annotations=WRITE_HINTS,
        )

    if settings.assignment_grading_enabled:
        register_grading_tools(server, client)


def register_grading_tools(server: MCPServer, client: SakaiClient) -> None:

    async def get_assignment_grading_context(
        course_id: Annotated[str, Field(max_length=128, min_length=1)],
        assignment_id: Annotated[str, Field(max_length=128, min_length=1)],
    ) -> Annotated[CallToolResult, public.ContextResult]:
        return tool_result(
            "get_assignment_grading_context",
            await invoke_grading(
                client.grading.get_assignment_grading_context,
                native.GetAssignmentGradingContextRequest,
                {"course_id": course_id, "assignment_id": assignment_id},
            ),
            course_id,
            assignment_id,
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
    ) -> Annotated[CallToolResult, public.SubmissionListResult]:
        return tool_result(
            "list_assignment_submissions",
            await invoke_grading(
                client.grading.list_assignment_submissions,
                native.ListAssignmentSubmissionsRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            ),
            course_id,
            assignment_id,
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
    ) -> Annotated[CallToolResult, public.SubmissionResult]:
        return tool_result(
            "get_assignment_submission",
            await invoke_grading(
                client.grading.get_assignment_submission,
                native.GetAssignmentSubmissionRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "submission_id": submission_id,
                },
            ),
            course_id,
            assignment_id,
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
            list[native.ExportSelection], Field(max_length=100, min_length=1)
        ],
    ) -> native.ExportAssignmentSubmissionsResult:
        return native.ExportAssignmentSubmissionsResult.model_validate(
            await invoke_grading(
                client.grading.export_assignment_submissions,
                native.ExportAssignmentSubmissionsRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "export_request_id": export_request_id,
                    "expected_assignment_revision": expected_assignment_revision,
                    "submissions": submissions,
                },
                write=True,
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
    ) -> Annotated[CallToolResult, public.ExportResult]:
        return tool_result(
            "get_assignment_submission_export",
            await invoke_grading(
                client.grading.get_assignment_submission_export,
                native.GetAssignmentSubmissionExportRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "export_id": export_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            ),
            course_id,
            assignment_id,
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
        grades: Annotated[list[native.SaveRow], Field(max_length=100, min_length=1)],
    ) -> native.SaveAssignmentGradesResult:
        return native.SaveAssignmentGradesResult.model_validate(
            await invoke_grading(
                client.grading.save_assignment_grades,
                native.SaveAssignmentGradesRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                    "mode": mode,
                    "expected_assignment_revision": expected_assignment_revision,
                    "payload_sha256": payload_sha256,
                    "grades": grades,
                },
                write=True,
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
        grades: Annotated[list[native.ReleaseRow], Field(max_length=100, min_length=1)],
    ) -> native.ReleaseAssignmentGradesResult:
        return native.ReleaseAssignmentGradesResult.model_validate(
            await invoke_grading(
                client.grading.release_assignment_grades,
                native.ReleaseAssignmentGradesRequest,
                {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                    "mode": mode,
                    "expected_assignment_revision": expected_assignment_revision,
                    "payload_sha256": payload_sha256,
                    "grades": grades,
                },
                write=True,
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
        rows: Annotated[list[native.Target], Field(max_length=100, min_length=1)],
    ) -> native.GetAssignmentGradesResult:
        return native.GetAssignmentGradesResult.model_validate(
            await invoke_grading(
                client.grading.get_assignment_grades,
                native.GetAssignmentGradesRequest,
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
    ) -> native.GetAssignmentGradingOperationResult:
        return native.GetAssignmentGradingOperationResult.model_validate(
            await invoke_grading(
                client.grading.get_assignment_grading_operation,
                native.GetAssignmentGradingOperationRequest,
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

    register_proposal_tools(server, client)


def register_proposal_tools(server: MCPServer, client: SakaiClient) -> None:
    workflow = GradingWorkflow(client)

    @server.tool(
        description="Construct the canonical hash and validate one exact save or release-and-return payload without committing. Review commit_arguments with the TA; invoke the separate save/release tool only after explicit approval. No external hashing script is needed.",
        annotations=READ,
    )
    async def prepare_assignment_grade_payload(
        course_id: public.Id,
        assignment_id: public.Id,
        kind: Literal["save", "release"],
        operation_id: public.UUIDString,
        expected_assignment_revision: public.Id,
        grades: Annotated[
            list[native.SaveRow | native.ReleaseRow],
            Field(min_length=1, max_length=100),
        ],
    ) -> proposals.GradePayloadResult:
        async with audit_call(
            "prepare_assignment_grade_payload", "read", course_id, assignment_id
        ):
            try:
                return await workflow.prepare_grade_payload(
                    principal(),
                    course_id,
                    assignment_id,
                    kind,
                    operation_id,
                    expected_assignment_revision,
                    grades,
                )
            except ValueError:
                raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="List published assignments the delegated grader can grade, without requiring assignment-setup permissions.",
        annotations=READ,
    )
    async def list_assignments(
        course_id: public.Id,
        cursor: Annotated[str, Field(max_length=2048)] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> public.AssignmentListResult:
        async with audit_call("list_assignments", "read", course_id):
            try:
                return await client.grading.list_assignments(
                    principal(), course_id, cursor, limit
                )
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Prepare deterministic MCQ proposals from an existing immutable export using an explicitly approved key/configuration. No official grades are saved or returned. Reports are MCP resources. Use get_assignment_grading_proposal to reconcile the same proposal ID after an uncertain outcome.",
        annotations=PREPARE,
    )
    async def prepare_assignment_mcq_grades(
        course_id: public.Id,
        assignment_id: public.Id,
        export_id: public.UUIDString,
        proposal_id: public.UUIDString,
        config: proposals.MCQConfig,
    ) -> Annotated[CallToolResult, proposals.ProposalResult]:
        async with audit_call(
            "prepare_assignment_mcq_grades", "write", course_id, assignment_id
        ):
            try:
                record = await workflow.prepare_mcq(
                    principal(),
                    course_id,
                    assignment_id,
                    export_id,
                    proposal_id,
                    config,
                )
                return receipt(record, course_id, assignment_id)
            except ValueError:
                raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Read a durable grading proposal and its frozen configuration, including reconciliation after an uncertain prepare result. No academic writes.",
        annotations=READ,
    )
    async def get_assignment_grading_proposal(
        course_id: public.Id,
        assignment_id: public.Id,
        proposal_id: public.UUIDString,
        cursor: Annotated[str, Field(pattern=r"^[0-9]{1,6}$")] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> proposals.ProposalPage:
        async with audit_call(
            "get_assignment_grading_proposal", "read", course_id, assignment_id
        ):
            try:
                return await workflow.get_proposal(
                    principal(), course_id, assignment_id, proposal_id, cursor, limit
                )
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Read one Sakai grading resource through the existing authenticated MCP connection, for hosts that expose tools but not resources/read. Returns SDK EmbeddedResource content. No external download or login.",
        annotations=READ,
    )
    async def read_assignment_grading_resource(
        uri: Annotated[str, Field(max_length=2048)],
    ) -> CallToolResult:
        try:
            course, assignment, _, _ = parse_uri(uri)
            async with audit_call(
                "read_assignment_grading_resource", "read", course, assignment
            ):
                item = present_resource(await read_resource(client, principal(), uri))
                resource: TextResourceContents | BlobResourceContents
                if isinstance(item.content, bytes):
                    resource = BlobResourceContents(
                        uri=uri,
                        mime_type=item.mime_type,
                        blob=base64.b64encode(item.content).decode(),
                        _meta=item.meta,
                    )
                else:
                    resource = TextResourceContents(
                        uri=uri,
                        mime_type=item.mime_type,
                        text=item.content,
                        _meta=item.meta,
                    )
                return CallToolResult(content=[EmbeddedResource(resource=resource)])
        except SakaiError as error:
            raise ToolError(error.code.value) from None
