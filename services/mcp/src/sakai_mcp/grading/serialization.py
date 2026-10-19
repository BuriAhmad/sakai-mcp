"""Canonical grading bytes and hashes; shared with native contracts."""

import hashlib
import json
from typing import Any


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def payload_hash(
    kind: str, course: str, assignment: str, revision: str, grades: list[dict[str, Any]]
) -> str:
    return digest(
        canonical(
            {
                "kind": kind,
                "course_id": course,
                "assignment_id": assignment,
                "expected_assignment_revision": revision,
                "grades": sorted(
                    grades, key=lambda r: (r["submission_id"], r["sakai_user_id"])
                ),
            }
        )
    )
