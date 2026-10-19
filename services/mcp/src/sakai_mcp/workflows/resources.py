"""Authorized grading resource resolution, manifest consistency, and URI validation."""

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.reports import report_csv
from sakai_mcp.grading.serialization import canonical
from sakai_mcp.sakai.client import SakaiClient


@dataclass(frozen=True)
class ResourceData:
    data: bytes | native.ExportReceipt
    mime: str
    metadata: dict[str, Any] = field(default_factory=dict)
    course_id: str = ""
    assignment_id: str = ""


def resource_data(data: bytes, mime: str, **metadata: Any) -> ResourceData:
    return ResourceData(data, mime, metadata)


def resource_root(course: str, assignment: str) -> str:
    return f"sakai://courses/{quote(course, safe='')}/assignments/{quote(assignment, safe='')}"


async def export_manifest(
    client: SakaiClient,
    principal: AccessToken,
    course: str,
    assignment: str,
    export: str,
) -> native.ExportReceipt:
    cursor, seen, artifacts, snapshot = None, set(), [], None
    while True:
        page = await client.grading.get_assignment_submission_export(
            principal,
            native.GetAssignmentSubmissionExportRequest(
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
) -> ResourceData:
    course, assignment, parts, revision = parse_uri(uri)
    if len(parts) == 4 and parts[0] == "submissions" and parts[2] == "files":
        if revision is None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, mime, sha = await client.grading.read_grading_file(
            principal, course, assignment, parts[1], parts[3], revision
        )
        return resource_data(data, mime, content_revision=revision)
    if len(parts) == 2 and parts[0] == "files":
        if revision is None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, mime, sha = await client.grading.read_grading_file(
            principal, course, assignment, None, parts[1], revision
        )
        if sha.lower() != revision.lower():
            raise SakaiError(ErrorCode.CONFLICT)
        return resource_data(data, mime)
    if parts and parts[0] == "exports" and revision is None:
        page = (
            await export_manifest(client, principal, course, assignment, parts[1])
            if len(parts) in {3, 6}
            else None
        )
        if page is not None and len(parts) == 3 and parts[2] == "manifest":
            return ResourceData(
                page,
                "application/json",
                {"expires_at": page.expires_at},
                course,
                assignment,
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
            data, _, sha = await client.grading.read_grading_artifact(
                principal, course, assignment, page.export_id, artifact.artifact_id
            )
            if len(data) != artifact.size_bytes or sha != artifact.sha256:
                raise SakaiError(ErrorCode.CONFLICT)
            return resource_data(
                data, artifact.content_type, expires_at=artifact.expires_at
            )
    if (
        len(parts) == 4
        and parts[0] == "proposals"
        and parts[2] == "reports"
        and revision is None
    ):
        record = await client.grading.get_proposal(
            principal, course, assignment, parts[1]
        )
        rows = [r.model_dump() for r in record.payload.rows]
        if parts[3] == "proposals":
            return resource_data(
                canonical(record.payload.model_dump()),
                "application/json",
                expires_at=record.expires_at,
            )
        if parts[3] in {"marks", "review-required"}:
            selected = rows if parts[3] == "marks" else [r for r in rows if r["issues"]]
            return resource_data(
                report_csv(selected).encode(), "text/csv", expires_at=record.expires_at
            )
    raise SakaiError(ErrorCode.NOT_FOUND)
