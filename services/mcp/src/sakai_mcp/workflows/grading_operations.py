"""External grading receipts; transitional sends stay single attempt and explicit."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest, payload_hash
from sakai_mcp.storage.base import RecordKind, RecordOwner, identifier
from sakai_mcp.storage.records import PrivateRecord, PrivateRecords
from sakai_mcp.workflows.submissions import SubmissionReads

Request = native.SaveAssignmentGradesRequest | native.ReleaseAssignmentGradesRequest
PROVENANCE = "grading-receipt-transition-v1"


class GradingOperationsJournal:
    def __init__(self, submissions: SubmissionReads, records: PrivateRecords | None):
        self.submissions = submissions
        self.records = records

    def store(self) -> PrivateRecords:
        if self.records is None:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        return self.records

    async def owner(
        self, token: AccessToken, course: str, assignment: str
    ) -> tuple[RecordOwner, dict[str, str]]:
        self.store()  # No HTTP without durable operation storage.
        actor, _, rows = await self.submissions.source(token, course, assignment)
        return (
            RecordOwner(actor.tenant, actor.object_id, actor.uid, course, assignment),
            {r.id: r.submitters[0].id for r in rows},
        )

    @staticmethod
    def checked(
        record: PrivateRecord, owner: RecordOwner, operation: str
    ) -> tuple[Request, native.OperationReceipt]:
        try:
            value = record.value["value"]
            if value["provenance"] != PROVENANCE or value["phase"] not in {
                "prepared",
                "sending",
                "returned",
            }:
                raise ValueError
            identifier(value["intent"])
            kind = value["kind"]
            model = (
                native.SaveAssignmentGradesRequest
                if kind == "save"
                else native.ReleaseAssignmentGradesRequest
                if kind == "release"
                else None
            )
            if model is None:
                raise ValueError
            request = model.model_validate(value["request"])
            receipt = native.OperationReceipt.model_validate(value["receipt"])
            pairs = [(r.submission_id, r.sakai_user_id) for r in request.grades]
            sha = payload_hash(
                kind,
                owner.course,
                owner.assignment,
                request.expected_assignment_revision,
                [r.model_dump() for r in request.grades],
            )
            if (
                request.course_id != owner.course
                or request.assignment_id != owner.assignment
                or request.operation_id != operation
                or request.mode != "commit"
                or len({sid for sid, _ in pairs}) != len(pairs)
                or sha != request.payload_sha256
                or sha != record.value["payload_hash"]
                or receipt.operation_id != operation
                or receipt.kind != kind
                or receipt.mode != "commit"
                or receipt.payload_sha256 != sha
                or sorted(pairs)
                != sorted((r.submission_id, r.sakai_user_id) for r in receipt.rows)
                or digest(canonical(receipt.model_dump())) != value["receipt_sha256"]
            ):
                raise ValueError
            if value["phase"] != "returned" and (
                receipt.outcome != "unknown"
                or any(r.stage not in {"pending", "unknown"} for r in receipt.rows)
            ):
                raise ValueError
            return request, receipt
        except (KeyError, TypeError, ValueError, ValidationError):
            raise SakaiError(ErrorCode.CONFLICT) from None

    @staticmethod
    def targets(request: Request, current: dict[str, str]) -> None:
        if any(current.get(r.submission_id) != r.sakai_user_id for r in request.grades):
            raise SakaiError(ErrorCode.FORBIDDEN)

    @staticmethod
    def public(receipt: native.OperationReceipt) -> native.OperationReceipt:
        # Authorization here covers Assignment targets. Historical Gradebook
        # values need separate current item/student authority; withhold them.
        warnings = list(
            dict.fromkeys(
                [
                    *receipt.warnings,
                    "historical_receipt_not_current_state",
                    "historical_gradebook_values_withheld",
                    "pending_work_not_executed_by_read",
                    "legacy_native_receipts_not_imported",
                ]
            )
        )
        if len(warnings) > 30:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return receipt.model_copy(
            update={
                "rows": [
                    r.model_copy(
                        update={
                            "gradebook_score": None,
                            "retry_action": "human_reconciliation"
                            if r.stage in {"pending", "unknown", "validated"}
                            else r.retry_action,
                        }
                    )
                    for r in receipt.rows
                ],
                "warnings": warnings,
            }
        )

    async def read(
        self, token: AccessToken, request: native.GetAssignmentGradingOperationRequest
    ) -> native.OperationReceipt:
        owner, current = await self.owner(
            token, request.course_id, request.assignment_id
        )
        record = await self.store().read(
            owner, RecordKind.OPERATION, request.operation_id, now=datetime.now(UTC)
        )
        approved, receipt = self.checked(record, owner, request.operation_id)
        self.targets(approved, current)
        return self.public(receipt)

    async def existing(
        self, token: AccessToken, request: Request
    ) -> native.OperationReceipt | None:
        owner, current = await self.owner(
            token, request.course_id, request.assignment_id
        )
        try:
            record = await self.store().read(
                owner, RecordKind.OPERATION, request.operation_id, now=datetime.now(UTC)
            )
        except SakaiError as error:
            if error.code != ErrorCode.NOT_FOUND:
                raise
            return None
        approved, receipt = self.checked(record, owner, request.operation_id)
        if approved.payload_sha256 != request.payload_sha256:
            raise SakaiError(ErrorCode.CONFLICT)
        self.targets(approved, current)
        return self.public(receipt)

    async def commit(
        self,
        token: AccessToken,
        request: Request,
        kind: Literal["save", "release"],
        send: Callable[[], Awaitable[native.OperationReceipt]],
    ) -> native.OperationReceipt:
        grades = [r.model_dump() for r in request.grades]
        if (
            len(canonical(request.model_dump())) > 60_000
            or len({r.submission_id for r in request.grades}) != len(request.grades)
            or payload_hash(
                kind,
                request.course_id,
                request.assignment_id,
                request.expected_assignment_revision,
                grades,
            )
            != request.payload_sha256
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        store = self.store()
        owner, current = await self.owner(
            token, request.course_id, request.assignment_id
        )
        self.targets(request, current)
        receipt = native.OperationReceipt(
            operation_id=request.operation_id,
            kind=kind,
            mode="commit",
            payload_sha256=request.payload_sha256,
            outcome="unknown",
            observed_at=datetime.now(UTC).isoformat(),
            warnings=["external_send_outcome_unconfirmed"],
            rows=[
                native.RowReceipt(
                    submission_id=r.submission_id,
                    sakai_user_id=r.sakai_user_id,
                    stage="unknown",
                    content_revision=None,
                    grade_revision=None,
                    assignment_score=None,
                    grade_released=None,
                    returned=None,
                    gradebook_score=None,
                    reason="external_send_outcome_unconfirmed",
                    retry_action="human_reconciliation",
                )
                for r in request.grades
            ],
        )
        intent = str(uuid4())
        record = await store.create(
            owner,
            RecordKind.OPERATION,
            request.operation_id,
            request.payload_sha256,
            {
                "provenance": PROVENANCE,
                "phase": "prepared",
                "intent": intent,
                "kind": kind,
                "request": request.model_dump(),
                "receipt": receipt.model_dump(),
                "receipt_sha256": digest(canonical(receipt.model_dump())),
            },
            expires_at=None,
            now=datetime.now(UTC),
        )
        approved, previous = self.checked(record, owner, request.operation_id)
        self.targets(approved, current)
        if record.value["value"]["intent"] != intent:
            # Existing prepared/sending/returned intent never resumes or resends.
            return self.public(previous)
        key = store.key(owner, RecordKind.OPERATION, request.operation_id)
        sending = {
            **record.value,
            "value": {**record.value["value"], "phase": "sending"},
        }
        saved = await store.store.replace(key, record.etag, canonical(sending))
        # The durable Sending state must exist before the sole native call.
        result = await send()
        completed = {
            **sending,
            "value": {
                **sending["value"],
                "phase": "returned",
                "receipt": result.model_dump(),
                "receipt_sha256": digest(canonical(result.model_dump())),
            },
        }
        checked = PrivateRecord(completed, saved.etag)
        try:
            self.checked(checked, owner, request.operation_id)
            await store.store.replace(key, saved.etag, canonical(completed))
        except SakaiError:
            # A committed native request cannot be replayed after receipt failure.
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
        return result
