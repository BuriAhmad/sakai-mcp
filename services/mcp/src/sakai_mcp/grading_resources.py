"""Authorized Sakai resource resolution and SDK resource links; no MCP client."""

import re
from typing import Any, cast
from urllib.parse import parse_qs, quote, unquote, urlsplit

from mcp.server.auth.provider import AccessToken
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ResourceLink, ResourceTemplate, TextContent
from pydantic import BaseModel

from sakai_mcp import grading_models as gm
from sakai_mcp import grading_resource_models as rm
from sakai_mcp.grading_evaluator import canonical, digest, report_csv
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError

FILE_LIMIT = 10 * 1024 * 1024
META = "app.smartdigest.sakai"
ROOT = "sakai://courses/{course_id}/assignments/{assignment_id}"
TEMPLATES = [
    (
        ROOT + "/submissions/{submission_id}/files/{file_id}{?revision}",
        "Submission files",
    ),
    (ROOT + "/files/{file_id}{?revision}", "Assignment files"),
    (
        ROOT + "/exports/{export_id}/submissions/{submission_id}/files/{artifact_id}",
        "Captured submission files",
    ),
    (ROOT + "/exports/{export_id}/manifest", "Captured submission manifest"),
    (
        ROOT + "/proposals/{proposal_id}/reports/{report}",
        "Grading proposals and reports",
    ),
]


def resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uri_template=uri,
            name=name,
            description="Delegated grading evidence. Current files require the supplied revision; captures expire.",
        )
        for uri, name in TEMPLATES
    ]


def resource_root(course: str, assignment: str) -> str:
    return f"sakai://courses/{quote(course, safe='')}/assignments/{quote(assignment, safe='')}"


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
    page: gm.ExportReceipt, course: str, assignment: str
) -> rm.ExportResult:
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
    return rm.ExportResult.model_validate(value)


def tool_result(name: str, result: Any, course: str, assignment: str) -> CallToolResult:
    native_type = gm.CONTRACTS[name][1]
    native = native_type.model_validate(result)
    value = native.model_dump()
    public: BaseModel
    if name == "get_assignment_submission_export":
        public = export_result(cast(gm.ExportReceipt, native), course, assignment)
    elif name == "list_assignment_submissions":
        value["items"] = [
            submission_links(row, course, assignment) for row in value["items"]
        ]
        public = rm.SubmissionListResult.model_validate(value)
    elif name == "get_assignment_submission":
        value["submission"] = submission_links(value["submission"], course, assignment)
        value.pop("inline_text")
        value.pop("inline_content_type")
        public = rm.SubmissionResult.model_validate(value)
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
        public = rm.ContextResult.model_validate(value)
    return content_result(public.model_dump(mode="json", by_alias=True))


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


async def export_manifest(
    client: SakaiClient,
    principal: AccessToken,
    course: str,
    assignment: str,
    export: str,
) -> gm.ExportReceipt:
    cursor, seen, artifacts, snapshot = None, set(), [], None
    while True:
        page = await client.grading_request(
            "get_assignment_submission_export",
            principal,
            gm.GetAssignmentSubmissionExportRequest(
                course_id=course,
                assignment_id=assignment,
                export_id=export,
                cursor=cursor,
                limit=100,
            ),
        )
        if page.export_id != export or page.status not in {"ready", "partial"}:
            raise SakaiError(ErrorCode.CONFLICT)
        if snapshot is not None and (
            page.request_sha256 != snapshot.request_sha256 or page.rows != snapshot.rows
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        snapshot = page if snapshot is None else snapshot
        artifacts.extend(page.artifacts)
        if (
            len(artifacts) > 2100
            or sum(a.size_bytes for a in artifacts) > 100 * 1024 * 1024
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        cursor = page.next_cursor
        if cursor is None:
            break
        if cursor in seen:
            raise SakaiError(ErrorCode.CONFLICT)
        seen.add(cursor)
    if len({a.artifact_id for a in artifacts}) != len(artifacts):
        raise SakaiError(ErrorCode.CONFLICT)
    # Aggregate manifests may exceed a public page's 100-artifact model bound.
    return snapshot.model_copy(update={"artifacts": artifacts, "next_cursor": None})


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


def parse_uri(uri: str) -> tuple[str, str, list[str], str | None]:
    parsed = urlsplit(uri)
    if parsed.scheme != "sakai" or parsed.netloc != "courses" or parsed.fragment:
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    parts = [unquote(p) for p in parsed.path.split("/")[1:]]
    if (
        len(parts) < 3
        or parts[1] != "assignments"
        or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", p) for p in parts)
    ):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) - {"revision"} or (
        "revision" in query
        and (
            len(query["revision"]) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", query["revision"][0])
        )
    ):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    return parts[0], parts[2], parts[3:], query.get("revision", [None])[0]


async def read_resource(
    client: SakaiClient, principal: AccessToken, uri: str
) -> ReadResourceContents:
    course, assignment, parts, revision = parse_uri(uri)
    if len(parts) == 4 and parts[0] == "submissions" and parts[2] == "files":
        if revision is None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, mime, sha = await client.read_grading_file(
            principal, course, assignment, parts[1], parts[3], revision
        )
        return contents(data, mime, content_revision=revision)
    if len(parts) == 2 and parts[0] == "files":
        if revision is None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, mime, sha = await client.read_grading_file(
            principal, course, assignment, None, parts[1], revision
        )
        if sha.lower() != revision.lower():
            raise SakaiError(ErrorCode.CONFLICT)
        return contents(data, mime)
    if parts and parts[0] == "exports" and revision is None:
        page = (
            await export_manifest(client, principal, course, assignment, parts[1])
            if len(parts) in {3, 6}
            else None
        )
        if page is not None and len(parts) == 3 and parts[2] == "manifest":
            # Validate/serialize each artifact independently; the aggregate may span pages.
            value = page.model_dump(exclude={"artifacts", "archive"})
            value.update(
                schema_version="2",
                course_id=course,
                assignment_id=assignment,
                archive=None,
            )
            value["artifacts"] = [
                export_result(
                    page.model_copy(update={"artifacts": [a]}), course, assignment
                )
                .artifacts[0]
                .model_dump(mode="json", by_alias=True)
                for a in page.artifacts
            ]
            return contents(
                canonical(value), "application/json", expires_at=page.expires_at
            )
        if (
            page is not None
            and len(parts) == 6
            and parts[2] == "submissions"
            and parts[4] == "files"
        ):
            artifact = next(
                (
                    a
                    for a in page.artifacts
                    if a.artifact_id == parts[5] and a.submission_id == parts[3]
                ),
                None,
            )
            if artifact is None:
                raise SakaiError(ErrorCode.NOT_FOUND)
            data, _, sha = await client.read_grading_artifact(
                principal, course, assignment, page.export_id, artifact.artifact_id
            )
            if len(data) != artifact.size_bytes or sha != artifact.sha256:
                raise SakaiError(ErrorCode.CONFLICT)
            return contents(data, artifact.content_type, expires_at=artifact.expires_at)
    if (
        len(parts) == 4
        and parts[0] == "proposals"
        and parts[2] == "reports"
        and revision is None
    ):
        record = await client.grading_proposal(principal, course, assignment, parts[1])
        rows = [r.model_dump() for r in record.payload.rows]
        if parts[3] == "proposals":
            return contents(
                canonical(record.payload.model_dump()),
                "application/json",
                expires_at=record.expires_at,
            )
        if parts[3] in {"marks", "review-required"}:
            selected = rows if parts[3] == "marks" else [r for r in rows if r["issues"]]
            return contents(
                report_csv(selected).encode(), "text/csv", expires_at=record.expires_at
            )
    raise SakaiError(ErrorCode.NOT_FOUND)
