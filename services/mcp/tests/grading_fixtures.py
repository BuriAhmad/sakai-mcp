"""Synthetic grading data shared by resource and proposal integration tests."""

from sakai_mcp import grading_models as gm
from sakai_mcp.grading_evaluator import digest
from sakai_mcp.grading_resource_models import MCQConfig

COURSE, ASSIGNMENT, SUBMISSION = "course-a", "assignment-a", "submission-a"
EXPORT = "00000000-0000-0000-0000-000000000001"
PROPOSAL = "00000000-0000-0000-0000-000000000002"
ARTIFACT = "00000000-0000-0000-0000-000000000003"
DATA = b"A\r\nC\r\nB\r\nD\r\nA\r\n"


def submission():
    return gm.SubmissionEntry.model_validate(
        {
            "student": {
                "sakai_user_id": "student-a",
                "eid": "synthetic",
                "display_name": "Synthetic",
            },
            "submitters": [
                {
                    "sakai_user_id": "student-a",
                    "eid": "synthetic",
                    "display_name": "Synthetic",
                }
            ],
            "submission_id": SUBMISSION,
            "group_id": None,
            "status": "submitted",
            "flags": {
                "submitted": True,
                "user_submission": True,
                "graded": False,
                "grade_released": False,
                "returned": False,
            },
            "submitted_at": None,
            "returned_at": None,
            "content_revision": "content",
            "grade_revision": "grade",
            "attempt_count": None,
            "history_completeness": "current_only",
            "inline_text_present": True,
            "attachments": [
                {
                    "artifact_key": "a" * 64,
                    "original_name": "roll.txt",
                    "content_type": "text/plain",
                    "size_bytes": len(DATA),
                    "resource_revision": digest(DATA),
                    "kind": "file",
                    "readable": True,
                }
            ],
            "attachments_complete": True,
            "late_status": "on_time",
            "overrides": {
                "remaining_resubmissions": None,
                "resubmission_close_at": None,
                "extension_close_at": None,
                "warnings": [],
            },
            "score": None,
            "warnings": [],
        }
    )


def context():
    return gm.GetAssignmentGradingContextResult.model_validate(
        {
            "schema_version": "1",
            "observed_at": "2026-10-14T00:00:00Z",
            "course": {"id": COURSE, "title": "Synthetic"},
            "assignment": {
                "id": ASSIGNMENT,
                "title": "Synthetic",
                "instructions": "Five MCQs",
                "configuration_revision": "config",
                "grade_type": "points",
                "max_points": "5",
                "scale_factor": 10,
                "submission_type": "single_attachment",
                "draft": False,
                "deleted": False,
                "visible_at": None,
                "open_at": None,
                "due_at": None,
                "close_at": None,
                "group_submission": False,
                "anonymous_grading": False,
                "native_release_grades": False,
                "resubmission_count": None,
                "resubmission_close_at": None,
                "definition_reference": None,
                "definition_version": None,
                "attachments": [],
                "integration_features": [],
            },
            "gradebook": {
                "mode": "none",
                "gradebook_uid": None,
                "item_id": None,
                "external_id": None,
                "released": None,
                "counted": None,
                "available": True,
                "reason": None,
            },
            "permissions": {
                "read_metadata": True,
                "read_content": True,
                "save_grades": True,
                "release_grades": True,
                "scope": "site",
                "scope_complete": True,
            },
            "submission_summary": {
                "expected_students": 1,
                "submitted": 1,
                "missing": 0,
                "draft": 0,
                "graded": 0,
                "orphan_records": 0,
            },
            "completeness": {"complete": True, "scope": "site", "reasons": []},
            "supported": {
                "prepare": True,
                "save": True,
                "release": True,
                "reasons": [],
            },
            "warnings": [],
        }
    )


def roster():
    return gm.ListAssignmentSubmissionsResult(
        items=[submission()],
        next_cursor=None,
        snapshot_revision="roster",
        observed_at="2026-10-14T00:00:00Z",
        completeness=gm.Completeness(complete=True, scope="site", reasons=[]),
        warnings=[],
    )


def manifest(data=DATA, mime="text/plain"):
    return gm.ExportReceipt(
        export_id=EXPORT,
        request_sha256="b" * 64,
        status="ready",
        observed_at="2026-10-14T00:00:00Z",
        expires_at="2026-10-15T00:00:00Z",
        completeness=gm.Completeness(complete=True, scope="site", reasons=[]),
        rows=[
            gm.ExportRow(
                submission_id=SUBMISSION,
                sakai_user_ids=["student-a"],
                content_revision="content",
                captured_at=None,
                status="ready",
                artifact_ids=[ARTIFACT],
                reasons=[],
            )
        ],
        artifacts=[
            gm.Artifact(
                artifact_id=ARTIFACT,
                kind="attachment",
                submission_id=SUBMISSION,
                original_name="roll.txt",
                relative_path="submissions/raw/submission-a/artifact",
                content_type=mime,
                size_bytes=len(data),
                sha256=digest(data),
                download_path=f"/grading-artifacts/{COURSE}/{ASSIGNMENT}/{EXPORT}/{ARTIFACT}",
                expires_at="2026-10-15T00:00:00Z",
            )
        ],
        archive=None,
        next_cursor=None,
        warnings=[],
    )


def config():
    return MCQConfig.model_validate(
        {
            "course_id": COURSE,
            "assignment_id": ASSIGNMENT,
            "assignment_revision": "config",
            "submission_contract": {
                "file_count": 1,
                "encoding": "utf-8",
                "answer_count": 5,
                "alphabet": ["A", "B", "C", "D"],
                "filename": "<roll>.txt",
            },
            "normalization": {
                "uppercase_answers": True,
                "trim_answer_whitespace": True,
                "extension_case": True,
            },
            "grading": {
                "method": "deterministic_mcq",
                "key": ["A", "C", "B", "D", "A"],
                "max_points": "5",
                "per_correct": "1",
                "per_incorrect": "0",
                "negative_marking": False,
            },
            "policies": {"late_penalty": None},
            "identity": {"filename_mismatch": "review_required"},
            "expected_filenames": {"student-a": "roll.txt"},
        }
    )
