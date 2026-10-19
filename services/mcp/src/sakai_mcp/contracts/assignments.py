"""Bounded published Assignment discovery from the existing site-action DTO.

The native serializer hydrates evidence. The caller must establish site-wide
asn.grade before using it; this parser does not repair native authorization.
"""

import hashlib
import json
from typing import Any

from pydantic import Field, StrictBool, StrictStr

from sakai_mcp.contracts.existing_api import Id, WireModel, collection, parse
from sakai_mcp.errors import ErrorCode, SakaiError


class AssignmentMetadata(WireModel):
    id: Id
    context: Id
    title: StrictStr = Field(max_length=65535)
    draft: StrictBool
    # Required observations: never infer missing native flags/configuration.
    gradeScale: Id
    submissionType: Id
    gradeScaleMaxPoints: StrictStr | None = None
    maxGradePoint: StrictStr | None = None
    access: StrictStr | None = None
    groups: list[Id] | None = Field(default=None, max_length=5000)
    anonymousGrading: StrictBool | None = None
    allowPeerAssessment: StrictBool | None = None
    allowResubmission: StrictBool | None = None
    openTimeString: StrictStr
    dueTimeString: StrictStr
    closeTimeString: StrictStr


def observation_revision(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    try:
        return "http1-" + hashlib.sha256(encoded.encode()).hexdigest()
    except UnicodeError:
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def assignment_summaries(value: Any, site: str) -> list[dict[str, str]]:
    if (
        isinstance(value, dict)
        and value.get("entityPrefix", "assignment") != "assignment"
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    rows = collection(value, "assignment", max_rows=5000)
    found: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for raw in rows:
        row = parse(AssignmentMetadata, raw)
        if row.context != site or row.id in seen:
            raise SakaiError(ErrorCode.CONFLICT)
        seen.add(row.id)
        if row.draft:
            continue
        # Deliberately exclude instructions, notes, submission bodies/grades and
        # arbitrary property bags. No retained body becomes model or log input.
        metadata = row.model_dump()
        found[row.id] = {
            "assignment_id": row.id,
            "title": row.title,
            "configuration_revision": observation_revision(metadata),
        }
    return sorted(found.values(), key=lambda r: r["assignment_id"].encode("utf-16-be"))
