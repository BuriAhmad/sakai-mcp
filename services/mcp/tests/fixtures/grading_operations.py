"""Synthetic native mutation replies for transitional external receipt tests."""

from datetime import UTC, datetime

from sakai_mcp.contracts import grading_native as native


def receipt(request):
    return native.OperationReceipt(
        operation_id=request.operation_id,
        kind="save",
        mode="commit",
        payload_sha256=request.payload_sha256,
        outcome="partial",
        observed_at=datetime.now(UTC).isoformat(),
        warnings=["native_partial"],
        rows=[
            native.RowReceipt(
                submission_id="submission-a",
                sakai_user_id="student-a",
                stage="unknown",
                content_revision="content",
                grade_revision="grade",
                assignment_score="4",
                grade_released=False,
                returned=False,
                gradebook_score="4",
                reason="projection_unconfirmed",
                retry_action="human_reconciliation",
            )
        ],
    )
