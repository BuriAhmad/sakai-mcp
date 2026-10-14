"""Portable deterministic proposals and resource access through the MCP host connection."""

import asyncio
import base64
from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextResourceContents,
    ToolAnnotations,
)
from pydantic import Field

from sakai_mcp import grading_models as gm
from sakai_mcp import grading_resource_models as rm
from sakai_mcp.audit import audit_call
from sakai_mcp.grading_evaluator import (
    canonical,
    digest,
    evaluate_mcq,
    payload_hash,
    report_csv,
)
from sakai_mcp.grading_resources import (
    content_result,
    export_manifest,
    link,
    parse_uri,
    read_resource,
    resource_root,
)
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError

READ = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
PREPARE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)


def principal():
    token = get_access_token()
    if token is None:
        raise ToolError(ErrorCode.UNAUTHENTICATED.value)
    return token


def receipt(record: rm.ProposalRecord, course: str, assignment: str) -> CallToolResult:
    root = f"{resource_root(course, assignment)}/proposals/{record.proposal_id}/reports"
    rows = [r.model_dump() for r in record.payload.rows]
    reports = {
        "proposals": canonical(record.payload.model_dump()),
        "marks": report_csv(rows).encode(),
        "review-required": report_csv([r for r in rows if r["issues"]]).encode(),
    }
    value = rm.ProposalResult(
        proposal_id=record.proposal_id,
        export_id=record.export_id,
        expires_at=record.expires_at,
        total=len(record.payload.rows),
        proposed=sum(r.review_status == "proposed" for r in record.payload.rows),
        review_required=sum(
            r.review_status == "review_required" for r in record.payload.rows
        ),
        resources=[
            link(
                f"{root}/{name}",
                filename,
                mime,
                len(reports[name]),
                sha256=digest(reports[name]),
                expires_at=record.expires_at,
            )
            for name, filename, mime in (
                ("proposals", "proposals.json", "application/json"),
                ("marks", "marks.csv", "text/csv"),
                ("review-required", "review-required.csv", "text/csv"),
            )
        ],
    )
    return content_result(value.model_dump(mode="json", by_alias=True))


def register_proposal_tools(server: MCPServer, client: SakaiClient) -> None:
    prepare_slots = asyncio.Semaphore(2)

    @server.tool(
        description="Construct the canonical hash and validate one exact save or release-and-return payload without committing. Review commit_arguments with the TA; invoke the separate save/release tool only after explicit approval. No external hashing script is needed.",
        annotations=READ,
    )
    async def prepare_assignment_grade_payload(
        course_id: rm.Id,
        assignment_id: rm.Id,
        kind: Literal["save", "release"],
        operation_id: rm.UUIDString,
        expected_assignment_revision: rm.Id,
        grades: Annotated[
            list[gm.SaveRow | gm.ReleaseRow], Field(min_length=1, max_length=100)
        ],
    ) -> rm.GradePayloadResult:
        async with audit_call(
            "prepare_assignment_grade_payload", "read", course_id, assignment_id
        ):
            try:
                rows = [r.model_dump() for r in grades]
                value = {
                    "course_id": course_id,
                    "assignment_id": assignment_id,
                    "operation_id": operation_id,
                    "mode": "validate",
                    "expected_assignment_revision": expected_assignment_revision,
                    "payload_sha256": payload_hash(
                        kind,
                        course_id,
                        assignment_id,
                        expected_assignment_revision,
                        rows,
                    ),
                    "grades": rows,
                }
                request_type = (
                    gm.SaveAssignmentGradesRequest
                    if kind == "save"
                    else gm.ReleaseAssignmentGradesRequest
                )
                request = request_type.model_validate(value)
                name = (
                    "save_assignment_grades"
                    if kind == "save"
                    else "release_assignment_grades"
                )
                validation = await client.grading_request(name, principal(), request)
                return rm.GradePayloadResult(
                    kind=kind,
                    commit_arguments=request.model_copy(update={"mode": "commit"}),
                    validation=validation,
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
        course_id: rm.Id,
        cursor: Annotated[str, Field(max_length=2048)] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> rm.AssignmentListResult:
        async with audit_call("list_assignments", "read", course_id):
            try:
                return await client.grading_assignments(
                    principal(), course_id, cursor, limit
                )
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(
        description="Prepare deterministic MCQ proposals from an existing immutable export using an explicitly approved key/configuration. No official grades are saved or returned. Reports are MCP resources. Use get_assignment_grading_proposal to reconcile the same proposal ID after an uncertain outcome.",
        annotations=PREPARE,
    )
    async def prepare_assignment_mcq_grades(
        course_id: rm.Id,
        assignment_id: rm.Id,
        export_id: rm.UUIDString,
        proposal_id: rm.UUIDString,
        config: rm.MCQConfig,
    ) -> Annotated[CallToolResult, rm.ProposalResult]:
        async with (
            audit_call(
                "prepare_assignment_mcq_grades", "write", course_id, assignment_id
            ),
            prepare_slots,
        ):
            try:
                token = principal()
                if (
                    config.course_id != course_id
                    or config.assignment_id != assignment_id
                    or len(canonical(config.model_dump())) > 50_000
                ):
                    raise SakaiError(ErrorCode.VALIDATION_ERROR)
                # Reconcile a known receipt before doing any new work. Never replay a private write blindly.
                try:
                    existing = await client.grading_proposal(
                        token, course_id, assignment_id, proposal_id
                    )
                except SakaiError as error:
                    if error.code != ErrorCode.NOT_FOUND:
                        raise
                else:
                    if (
                        existing.export_id != export_id
                        or existing.payload.config != config
                    ):
                        raise SakaiError(ErrorCode.CONFLICT)
                    return receipt(existing, course_id, assignment_id)
                manifest = await export_manifest(
                    client, token, course_id, assignment_id, export_id
                )
                files: dict[str, bytes] = {}
                for artifact in manifest.artifacts:
                    try:
                        data, _, sha = await client.read_grading_artifact(
                            token,
                            course_id,
                            assignment_id,
                            export_id,
                            artifact.artifact_id,
                        )
                        if sha != artifact.sha256 or len(data) != artifact.size_bytes:
                            raise SakaiError(ErrorCode.CONFLICT)
                        files[artifact.artifact_id] = data
                    except SakaiError as error:
                        if error.code not in {
                            ErrorCode.DEPENDENCY_UNAVAILABLE,
                            ErrorCode.RATE_LIMITED,
                        }:
                            raise
                        continue
                context = await client.grading_request(
                    "get_assignment_grading_context",
                    token,
                    gm.GetAssignmentGradingContextRequest(
                        course_id=course_id, assignment_id=assignment_id
                    ),
                )
                roster: list[dict[str, Any]] = []
                seen: set[str] = set()
                cursor, revision = None, None
                while True:
                    page = await client.grading_request(
                        "list_assignment_submissions",
                        token,
                        gm.ListAssignmentSubmissionsRequest(
                            course_id=course_id,
                            assignment_id=assignment_id,
                            cursor=cursor,
                            limit=100,
                        ),
                    )
                    if not page.completeness.complete or revision not in {
                        None,
                        page.snapshot_revision,
                    }:
                        raise SakaiError(ErrorCode.CONFLICT)
                    revision = page.snapshot_revision
                    roster.extend(r.model_dump() for r in page.items)
                    if len(roster) > 500:
                        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                    if cursor in seen:
                        raise SakaiError(ErrorCode.CONFLICT)
                    seen.add(cursor)
                evidence = manifest.model_dump()
                evidence.update(course_id=course_id, assignment_id=assignment_id)
                # Path descriptors are legacy native DTO details, never required by this evaluator.
                for artifact in evidence["artifacts"]:
                    artifact.pop("download_path")
                    artifact.pop("relative_path")
                rows = evaluate_mcq(
                    config.model_dump(), context.model_dump(), roster, evidence, files
                )
                payload = rm.ProposalPayload(
                    config=config, rows=[rm.ProposalRow.model_validate(r) for r in rows]
                )
                record = await client.grading_proposal(
                    token,
                    course_id,
                    assignment_id,
                    proposal_id,
                    payload.model_dump(),
                    export_id,
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
        course_id: rm.Id,
        assignment_id: rm.Id,
        proposal_id: rm.UUIDString,
        cursor: Annotated[str, Field(pattern=r"^[0-9]{1,6}$")] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> rm.ProposalPage:
        async with audit_call(
            "get_assignment_grading_proposal", "read", course_id, assignment_id
        ):
            try:
                record = await client.grading_proposal(
                    principal(), course_id, assignment_id, proposal_id
                )
                offset = 0 if cursor is None else int(cursor)
                if offset > len(record.payload.rows):
                    raise SakaiError(ErrorCode.VALIDATION_ERROR)
                end = min(len(record.payload.rows), offset + limit)
                return rm.ProposalPage(
                    proposal_id=record.proposal_id,
                    export_id=record.export_id,
                    expires_at=record.expires_at,
                    config=record.payload.config,
                    rows=record.payload.rows[offset:end],
                    total=len(record.payload.rows),
                    next_cursor=str(end) if end < len(record.payload.rows) else None,
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
                item = await read_resource(client, principal(), uri)
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
