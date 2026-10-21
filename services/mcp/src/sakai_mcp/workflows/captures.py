"""Owner-bound immutable HTTP observations; never a native snapshot or grade writer."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import AssignmentMetadata, observation_revision
from sakai_mcp.contracts.grading_proposals import ProposalRecord
from sakai_mcp.contracts.submissions import (
    REASONS,
    AssignmentEvidence,
    WireSubmission,
    entry,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.storage.base import RecordKind, RecordOwner, identifier
from sakai_mcp.storage.records import PrivateRecord, PrivateRecords
from sakai_mcp.workflows.submissions import SubmissionReads


def assignment_revision(assignment: AssignmentEvidence) -> str:
    # Exactly T19's metadata algorithm. Student evidence is excluded.
    return observation_revision(
        AssignmentMetadata.model_validate(assignment.model_dump()).model_dump()
    )


def offset(cursor: str | None, revision: str, count: int) -> int:
    if cursor is None:
        return 0
    parts = cursor.split(":")
    if len(parts) != 2 or parts[0] != revision:
        raise SakaiError(ErrorCode.CONFLICT)
    if not parts[1].isascii() or not parts[1].isdecimal() or len(parts[1]) > 6:
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    value = int(parts[1])
    if value > count:
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    return value


class Captures:
    def __init__(
        self, submissions: SubmissionReads, records: PrivateRecords | None
    ) -> None:
        self.submissions = submissions
        self.records = records
        self.slots = asyncio.Semaphore(2)

    def store(self) -> PrivateRecords:
        if self.records is None:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        return self.records

    async def source(
        self, token: AccessToken, course: str, assignment: str
    ) -> tuple[RecordOwner, AssignmentEvidence, dict[str, WireSubmission]]:
        self.store()  # No HTTP when durable storage is not configured.
        actor, wire, rows = await self.submissions.source(token, course, assignment)
        return (
            RecordOwner(actor.tenant, actor.object_id, actor.uid, course, assignment),
            wire,
            {r.id: r for r in rows},
        )

    @staticmethod
    def require_sources(
        receipt: native.ExportReceipt, rows: dict[str, WireSubmission]
    ) -> None:
        for row in receipt.rows:
            current = rows.get(row.submission_id)
            if current is None or sorted(row.sakai_user_ids) != sorted(
                u.id for u in current.submitters
            ):
                raise SakaiError(ErrorCode.FORBIDDEN)

    @staticmethod
    def receipt(record: PrivateRecord, export: str) -> native.ExportReceipt:
        value = record.value["value"]
        try:
            receipt = native.ExportReceipt.model_validate(value["receipt"])
            if (
                receipt.export_id != export
                or receipt.expires_at != record.value["expires_at"]
                or receipt.request_sha256 != record.value["payload_hash"]
                or digest(canonical(receipt.model_dump())) != value["receipt_sha256"]
                or receipt.next_cursor is not None
            ):
                raise ValueError
            artifacts = {a.artifact_id: a for a in receipt.artifacts}
            if len(artifacts) != len(receipt.artifacts) or len(
                {r.submission_id for r in receipt.rows}
            ) != len(receipt.rows):
                raise ValueError
            referenced = []
            for row in receipt.rows:
                for aid in row.artifact_ids:
                    if (
                        aid not in artifacts
                        or artifacts[aid].submission_id != row.submission_id
                    ):
                        raise ValueError
                    referenced.append(aid)
            if len(set(referenced)) != len(referenced) or set(referenced) != set(
                artifacts
            ):
                raise ValueError
            if any(a.expires_at != receipt.expires_at for a in receipt.artifacts):
                raise ValueError
            return receipt
        except (KeyError, ValueError, TypeError, ValidationError):
            raise SakaiError(ErrorCode.CONFLICT) from None

    @staticmethod
    def wrapped(receipt: native.ExportReceipt, capture: str) -> dict[str, Any]:
        value = receipt.model_dump()
        return {
            "provenance": "existing-http-inline-capture-v1",
            "capture": capture,
            "receipt": value,
            "receipt_sha256": digest(canonical(value)),
        }

    async def export(
        self, token: AccessToken, request: native.ExportAssignmentSubmissionsRequest
    ) -> native.ExportAssignmentSubmissionsResult:
        async with self.slots:
            return await self._export(token, request)

    async def _export(
        self, token: AccessToken, request: native.ExportAssignmentSubmissionsRequest
    ) -> native.ExportAssignmentSubmissionsResult:
        store = self.store()
        export = identifier(request.export_request_id)
        if len({s.submission_id for s in request.submissions}) != len(
            request.submissions
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        owner, assignment, rows = await self.source(
            token, request.course_id, request.assignment_id
        )
        request_hash = digest(canonical(request.model_dump()))
        try:
            previous = await store.read(
                owner, RecordKind.EXPORT, export, now=datetime.now(UTC)
            )
        except SakaiError as error:
            if error.code != ErrorCode.NOT_FOUND:
                raise
        else:
            if previous.value["payload_hash"] != request_hash:
                raise SakaiError(ErrorCode.CONFLICT)
            receipt = self.receipt(previous, export)
            self.require_sources(receipt, rows)
            return self.result(receipt)
        if request.expected_assignment_revision != assignment_revision(assignment):
            raise SakaiError(ErrorCode.CONFLICT)
        selected = []
        for choice in request.submissions:
            row = rows.get(choice.submission_id)
            if row is None:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if (
                entry(row, assignment).content_revision
                != choice.expected_content_revision
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            selected.append(row)
        now = datetime.now(UTC)
        expires = (now + timedelta(hours=24)).isoformat()
        capture = str(uuid4())
        receipt = native.ExportReceipt(
            export_id=export,
            request_sha256=request_hash,
            status="pending",
            observed_at=now.isoformat(),
            expires_at=expires,
            completeness=native.Completeness(
                complete=False, scope="site", reasons=["capture_interrupted", *REASONS]
            ),
            rows=[
                native.ExportRow(
                    submission_id=r.id,
                    sakai_user_ids=[u.id for u in r.submitters],
                    content_revision=choice.expected_content_revision,
                    captured_at=None,
                    status="incomplete",
                    artifact_ids=[],
                    reasons=["capture_interrupted"],
                )
                for r, choice in zip(selected, request.submissions, strict=True)
            ],
            artifacts=[],
            archive=None,
            next_cursor=None,
            warnings=["capture_interrupted"],
        )
        record = await store.create(
            owner,
            RecordKind.EXPORT,
            export,
            request_hash,
            self.wrapped(receipt, capture),
            expires_at=datetime.fromisoformat(expires),
            now=now,
        )
        # Only the conditional creator captures. A duplicate never resumes a pending capture.
        if record.value["value"].get("capture") != capture:
            old = self.receipt(record, export)
            self.require_sources(old, rows)
            return self.result(old)
        artifacts = []
        captured_rows = []
        for row, selected_row in zip(selected, receipt.rows, strict=True):
            reasons = ["source_inventory_incomplete"]
            ids = []
            if row.submittedAttachments:
                reasons.append("attachment_capture_unsupported")
            if row.submittedText is not None:
                data = row.submittedText.encode("utf-8")
                if len(data) > 65535:
                    reasons.append("inline_over_budget")
                else:
                    aid = str(uuid4())
                    await store.store.create(
                        store.key(owner, RecordKind.EXPORT, export, aid), data
                    )
                    artifacts.append(
                        native.Artifact(
                            artifact_id=aid,
                            kind="inline_text",
                            submission_id=row.id,
                            original_name="inline.html",
                            relative_path=f"submissions/raw/{row.id}/{aid}",
                            content_type="text/html",
                            size_bytes=len(data),
                            sha256=digest(data),
                            # Historical typed descriptor, never used as an HTTP destination.
                            download_path=f"/grading-artifacts/{export}/{aid}",
                            expires_at=expires,
                        )
                    )
                    ids.append(aid)
            captured_rows.append(
                selected_row.model_copy(
                    update={
                        "captured_at": datetime.now(UTC).isoformat(),
                        "artifact_ids": ids,
                        "reasons": reasons,
                    }
                )
            )
        after_owner, after_assignment, after = await self.source(
            token, request.course_id, request.assignment_id
        )
        if after_owner != owner:
            raise SakaiError(ErrorCode.UNAUTHENTICATED)
        for captured in captured_rows:
            current = after.get(captured.submission_id)
            if (
                assignment_revision(after_assignment)
                != request.expected_assignment_revision
                or current is None
                or entry(current, after_assignment).content_revision
                != captured.content_revision
            ):
                captured.status = "source_changed"
                captured.reasons.append("source_changed")
        receipt = receipt.model_copy(
            update={
                "status": "partial",
                "rows": captured_rows,
                "artifacts": artifacts,
                "completeness": native.Completeness(
                    complete=False, scope="site", reasons=REASONS
                ),
                "warnings": [
                    "observed_capture_not_native_snapshot",
                    "inline_only_incomplete_evidence",
                ],
            }
        )
        # Validate the final bounded manifest before persisting it. A failure leaves pending.
        receipt = native.ExportReceipt.model_validate(receipt.model_dump())
        envelope = {**record.value, "value": self.wrapped(receipt, capture)}
        await store.store.replace(
            store.key(owner, RecordKind.EXPORT, export),
            record.etag,
            canonical(envelope),
        )
        return self.result(receipt)

    @staticmethod
    def result(
        receipt: native.ExportReceipt,
    ) -> native.ExportAssignmentSubmissionsResult:
        return native.ExportAssignmentSubmissionsResult.model_validate(
            {
                k: getattr(receipt, k)
                for k in (
                    "export_id",
                    "request_sha256",
                    "status",
                    "expires_at",
                    "warnings",
                )
            }
        )

    async def manifest(
        self, token: AccessToken, course: str, assignment: str, export: str
    ) -> tuple[RecordOwner, native.ExportReceipt]:
        identifier(export)
        owner, _, rows = await self.source(token, course, assignment)
        record = await self.store().read(
            owner, RecordKind.EXPORT, export, now=datetime.now(UTC)
        )
        receipt = self.receipt(record, export)
        self.require_sources(receipt, rows)
        return owner, receipt

    async def page(
        self, token: AccessToken, request: native.GetAssignmentSubmissionExportRequest
    ) -> native.ExportReceipt:
        _, receipt = await self.manifest(
            token, request.course_id, request.assignment_id, request.export_id
        )
        revision = observation_revision(receipt.model_dump())
        start = offset(request.cursor, revision, len(receipt.artifacts))
        end = min(start + request.limit, len(receipt.artifacts))
        return receipt.model_copy(
            update={
                "artifacts": receipt.artifacts[start:end],
                "next_cursor": f"{revision}:{end}"
                if end < len(receipt.artifacts)
                else None,
            }
        )

    async def artifact(
        self,
        token: AccessToken,
        course: str,
        assignment: str,
        export: str,
        artifact: str,
    ) -> tuple[bytes, str, str]:
        identifier(artifact)
        owner, receipt = await self.manifest(token, course, assignment, export)
        descriptor = next(
            (a for a in receipt.artifacts if a.artifact_id == artifact), None
        )
        if descriptor is None:
            raise SakaiError(ErrorCode.NOT_FOUND)
        data = await self.store().artifact(
            owner,
            export,
            artifact,
            expected_size=descriptor.size_bytes,
            expected_sha256=descriptor.sha256,
            now=datetime.now(UTC),
        )
        return data, descriptor.content_type, descriptor.sha256

    async def proposal(
        self, token: AccessToken, course: str, assignment: str, proposal: str
    ) -> ProposalRecord:
        identifier(proposal)
        owner, _, _ = await self.source(token, course, assignment)
        record = await self.store().read(
            owner, RecordKind.PROPOSAL, proposal, now=datetime.now(UTC)
        )
        try:
            result = ProposalRecord.model_validate(record.value["value"]["proposal"])
            expected_hash = digest(
                canonical(
                    {
                        "proposal_id": proposal,
                        "export_id": result.export_id,
                        "payload": result.payload.model_dump(),
                    }
                )
            )
            if (
                result.proposal_id != proposal
                or result.expires_at != record.value["expires_at"]
                or result.request_sha256 != expected_hash
                or record.value["payload_hash"] != expected_hash
                or result.payload.config.course_id != course
                or result.payload.config.assignment_id != assignment
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError, ValidationError):
            raise SakaiError(ErrorCode.CONFLICT) from None
        _, manifest = await self.manifest(token, course, assignment, result.export_id)
        if datetime.fromisoformat(result.expires_at) > datetime.fromisoformat(
            manifest.expires_at
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        return result
