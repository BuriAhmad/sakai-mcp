"""Public MCP result presentation, resource links, and byte-preserving content."""

import re
from datetime import UTC, datetime
from math import isfinite
from typing import Any, cast
from urllib.parse import quote

from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ResourceLink, TextContent
from pydantic import BaseModel

from sakai_mcp.config import Settings
from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts import grading_proposals as proposals
from sakai_mcp.contracts import grading_public as public
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.reports import report_csv
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.workflows.resources import ResourceData, resource_root

FILE_LIMIT = 10 * 1024 * 1024
META = "app.smartdigest.sakai"


def paginate_rows(
    rows: list[dict[str, Any]],
    cursor: str | None,
    limit: int | None,
    settings: Settings,
    cap: int,
    *,
    scope: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    size = settings.page_size_default if limit is None else limit
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or not 1 <= size <= settings.page_size_max
    ):
        raise ToolError(ErrorCode.VALIDATION_ERROR.value)
    revision = None
    if scope is not None:
        revision = "http1-" + digest(canonical({"scope": scope, "rows": rows}))
        if cursor is not None:
            parts = cursor.split(":")
            if len(parts) != 2:
                raise ToolError(ErrorCode.VALIDATION_ERROR.value)
            if parts[0] != revision:
                raise ToolError(ErrorCode.CONFLICT.value)
            cursor = parts[1]
    if cursor is None:
        offset = 0
    elif (
        isinstance(cursor, str)
        and cursor.isascii()
        and cursor.isdecimal()
        and len(cursor) <= 6
    ):
        offset = int(cursor)
    else:
        raise ToolError(ErrorCode.VALIDATION_ERROR.value)
    end = min(offset + size, len(rows))
    return {
        "items": rows[offset:end],
        "next_cursor": (f"{revision}:{end}" if revision else str(end))
        if end < len(rows)
        else None,
        "source_limit_reached": len(rows) >= cap,
    }


def present_announcement(row: dict[str, Any]) -> dict[str, Any]:
    posted = row.get("postedAt")
    if not isinstance(posted, int) or isinstance(posted, bool):
        raise ToolError(ErrorCode.INTERNAL_ERROR.value)
    try:
        posted_at = (
            datetime.fromtimestamp(posted / 1000, UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, ValueError):
        raise ToolError(ErrorCode.INTERNAL_ERROR.value) from None
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "body": row.get("body"),
        "posted_at": posted_at,
    }


def present_submission(row: dict[str, Any]) -> dict[str, Any]:
    stamp = row.get("submittedAt")
    if stamp is not None:
        try:
            if (
                isinstance(stamp, (int, float))
                and not isinstance(stamp, bool)
                and isfinite(stamp)
                and stamp >= 0
            ):
                # Sakai 25.2 serializes AssignmentSubmission Instant as epoch seconds.
                parsed = datetime.fromtimestamp(stamp, UTC)
            elif isinstance(stamp, str):
                parsed = datetime.fromisoformat(stamp)
                if parsed.tzinfo is None:
                    raise ValueError("timestamp has no timezone")
            else:
                raise ValueError("unsupported timestamp")
            stamp = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except (OverflowError, ValueError):
            raise ToolError(ErrorCode.INTERNAL_ERROR.value) from None
    return {
        "id": row.get("id"),
        "submitter_ids": row.get("submitterIds"),
        "submitted_at": stamp,
    }


def mime_type(value: str) -> str:
    essence = value.split(";", 1)[0].strip().lower()
    return (
        essence
        if re.fullmatch(
            r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*", essence
        )
        else "application/octet-stream"
    )


def link(
    uri: str, name: str, mime: str, size: int | None, **metadata: Any
) -> ResourceLink:
    return ResourceLink(
        uri=uri, name=name, mime_type=mime_type(mime), size=size, _meta={META: metadata}
    )


def submission_links(
    row: dict[str, Any], course: str, assignment: str
) -> dict[str, Any]:
    root = resource_root(course, assignment)
    sid, revision = row["submission_id"], row["content_revision"]
    for attachment in row["attachments"]:
        attachment["resource"] = None
        attachment["resource_unavailable_reason"] = attachment_unavailable(
            attachment, bool(sid and revision)
        )
        if (
            sid
            and revision
            and attachment["readable"]
            and attachment["kind"] == "file"
            and attachment["size_bytes"] is not None
            and attachment["size_bytes"] <= FILE_LIMIT
        ):
            uri = f"{root}/submissions/{quote(sid, safe='')}/files/{quote(attachment['artifact_key'], safe='')}?revision={quote(revision, safe='')}"
            attachment["resource"] = link(
                uri,
                attachment["original_name"],
                attachment["content_type"] or "application/octet-stream",
                attachment["size_bytes"],
                sha256=attachment["resource_revision"],
                content_revision=revision,
            ).model_dump(mode="json", by_alias=True, exclude_none=True)
    row["inline_resource"] = None
    if sid and revision and row["inline_text_present"]:
        row["inline_resource"] = link(
            f"{root}/submissions/{quote(sid, safe='')}/files/inline?revision={quote(revision, safe='')}",
            "inline.html",
            "text/html",
            None,
            content_revision=revision,
        ).model_dump(mode="json", by_alias=True, exclude_none=True)
    return row


def attachment_unavailable(
    attachment: dict[str, Any], has_revision: bool = True
) -> str | None:
    if attachment["kind"] != "file":
        return "unsupported_attachment_kind"
    if not attachment["readable"]:
        return "unreadable"
    if attachment["size_bytes"] is None or not attachment["resource_revision"]:
        return "metadata_unavailable"
    if attachment["size_bytes"] > FILE_LIMIT:
        return "over_budget"
    return None if has_revision else "missing_submission_revision"


def export_result(
    page: native.ExportReceipt, course: str, assignment: str
) -> public.ExportResult:
    value = page.model_dump()
    for artifact in value["artifacts"] + (
        [value["archive"]] if value["archive"] else []
    ):
        artifact.pop("download_path")
        artifact.pop("relative_path")
        if not artifact["submission_id"]:
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        uri = (
            f"{resource_root(course, assignment)}/exports/{quote(page.export_id, safe='')}/submissions/"
            f"{quote(artifact['submission_id'], safe='')}/files/{quote(artifact['artifact_id'], safe='')}"
        )
        artifact["resource"] = link(
            uri,
            artifact["original_name"] or artifact["artifact_id"],
            artifact["content_type"],
            artifact["size_bytes"],
            sha256=artifact["sha256"],
            expires_at=artifact["expires_at"],
        ).model_dump(mode="json", by_alias=True, exclude_none=True)
    return public.ExportResult.model_validate(value)


def tool_result(name: str, result: Any, course: str, assignment: str) -> CallToolResult:
    native_types: dict[str, type[native.GradingModel]] = {
        "get_assignment_grading_context": native.GetAssignmentGradingContextResult,
        "list_assignment_submissions": native.ListAssignmentSubmissionsResult,
        "get_assignment_submission": native.GetAssignmentSubmissionResult,
        "get_assignment_submission_export": native.ExportReceipt,
    }
    native_result = native_types[name].model_validate(result)
    value = native_result.model_dump()
    public_result: BaseModel
    if name == "get_assignment_submission_export":
        public_result = export_result(
            cast(native.ExportReceipt, native_result), course, assignment
        )
    elif name == "list_assignment_submissions":
        value["items"] = [
            submission_links(row, course, assignment) for row in value["items"]
        ]
        public_result = public.SubmissionListResult.model_validate(value)
    elif name == "get_assignment_submission":
        value["submission"] = submission_links(value["submission"], course, assignment)
        value.pop("inline_text")
        value.pop("inline_content_type")
        public_result = public.SubmissionResult.model_validate(value)
    else:
        value["schema_version"] = "2"
        for attachment in value["assignment"]["attachments"]:
            attachment["resource"] = None
            attachment["resource_unavailable_reason"] = attachment_unavailable(
                attachment
            )
            if (
                attachment["readable"]
                and attachment["kind"] == "file"
                and attachment["resource_revision"]
                and attachment["size_bytes"] is not None
                and attachment["size_bytes"] <= FILE_LIMIT
            ):
                uri = f"{resource_root(course, assignment)}/files/{quote(attachment['artifact_key'], safe='')}?revision={quote(attachment['resource_revision'], safe='')}"
                attachment["resource"] = link(
                    uri,
                    attachment["original_name"],
                    attachment["content_type"] or "application/octet-stream",
                    attachment["size_bytes"],
                    sha256=attachment["resource_revision"],
                ).model_dump(mode="json", by_alias=True, exclude_none=True)
        public_result = public.ContextResult.model_validate(value)
    return content_result(public_result.model_dump(mode="json", by_alias=True))


def content_result(value: dict[str, Any]) -> CallToolResult:
    links: list[ResourceLink] = []

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            if item.get("type") == "resource_link":
                links.append(ResourceLink.model_validate(item))
            else:
                for child in item.values():
                    collect(child)
        elif isinstance(item, list):
            for child in item:
                collect(child)

    collect(value)
    serialized = canonical(value)
    if len(serialized) > 1_000_000:
        raise ToolError(ErrorCode.UNSUPPORTED_CAPABILITY.value)
    return CallToolResult(
        content=[TextContent(text=serialized.decode()), *links],
        structured_content=value,
    )


def contents(data: bytes, mime: str, **metadata: Any) -> ReadResourceContents:
    if len(data) > FILE_LIMIT:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    mime = mime_type(mime)
    textual = (
        mime.startswith("text/")
        or mime.endswith(("+json", "+xml"))
        or mime
        in {
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-python",
        }
    )
    content: str | bytes = data
    if textual:
        try:
            content = data.decode(
                "utf-8"
            )  # Preserve CRLF and BOM; never normalize original evidence.
        except UnicodeDecodeError:
            pass
    return ReadResourceContents(
        content=content,
        mime_type=mime,
        meta={META: {"sha256": digest(data), "size_bytes": len(data), **metadata}},
    )


def receipt(
    record: proposals.ProposalRecord, course: str, assignment: str
) -> CallToolResult:
    root = f"{resource_root(course, assignment)}/proposals/{record.proposal_id}/reports"
    rows = [r.model_dump() for r in record.payload.rows]
    reports = {
        "proposals": canonical(record.payload.model_dump()),
        "marks": report_csv(rows).encode(),
        "review-required": report_csv([r for r in rows if r["issues"]]).encode(),
    }
    value = proposals.ProposalResult(
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


def present_resource(resource: ResourceData) -> ReadResourceContents:
    data = resource.data
    if isinstance(data, native.ExportReceipt):
        value = data.model_dump(exclude={"artifacts", "archive"})
        value.update(
            schema_version="2",
            course_id=resource.course_id,
            assignment_id=resource.assignment_id,
            archive=None,
        )
        value["artifacts"] = [
            export_result(
                data.model_copy(update={"artifacts": [a]}),
                resource.course_id,
                resource.assignment_id,
            )
            .artifacts[0]
            .model_dump(mode="json", by_alias=True)
            for a in data.artifacts
        ]
        data = canonical(value)
    return contents(data, resource.mime, **resource.metadata)
