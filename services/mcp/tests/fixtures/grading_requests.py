import hashlib

from sakai_mcp.grading.serialization import payload_hash


def save_request(score="4"):
    grades = [
        {
            "submission_id": "submission-a",
            "sakai_user_id": "student-a",
            "expected_content_revision": "content",
            "expected_grade_revision": "grade",
            "score": score,
            "feedback": {"action": "preserve", "text": None},
        }
    ]
    return {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "operation_id": "00000000-0000-0000-0000-000000000001",
        "mode": "commit",
        "expected_assignment_revision": "config",
        "payload_sha256": payload_hash(
            "save", "course-a", "assignment-a", "config", grades
        ),
        "grades": grades,
    }


def make_evidence(data: bytes, name="roll.txt"):
    manifest = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "rows": [
            {
                "submission_id": "submission-a",
                "sakai_user_ids": ["student-a"],
                "status": "ready",
                "content_revision": "content",
                "artifact_ids": ["artifact"],
            }
        ],
        "artifacts": [
            {
                "artifact_id": "artifact",
                "original_name": name,
                "submission_id": "submission-a",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
    }
    config = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "assignment_revision": "config",
        "submission_contract": {
            "file_count": 1,
            "encoding": "utf-8",
            "alphabet": ["A", "B", "C", "D"],
            "answer_count": 5,
            "filename": "<roll-number>.txt",
        },
        "expected_filenames": {"student-a": "roll.txt"},
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
    }
    context = {
        "assignment": {"configuration_revision": "config", "max_points": "5"},
        "completeness": {"complete": True},
        "supported": {"prepare": True},
    }
    roster = [
        {
            "submission_id": "submission-a",
            "content_revision": "content",
            "grade_revision": "grade",
            "late_status": "on_time",
            "submitters": [{"sakai_user_id": "student-a"}],
            "status": "submitted",
        }
    ]
    return config, context, roster, manifest, {"artifact": data}
