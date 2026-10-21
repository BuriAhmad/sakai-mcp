"""Evaluator-only observed metadata, independent of the strict public T09 model."""

import re
from decimal import Decimal
from typing import Any

from sakai_mcp.contracts.grading_proposals import MCQConfig
from sakai_mcp.contracts.submissions import AssignmentEvidence
from sakai_mcp.errors import ErrorCode, SakaiError


def mcq_observation(
    assignment: AssignmentEvidence, revision: str, config: MCQConfig
) -> dict[str, Any]:
    # No raw scale/release/configuration flags are invented. These are the exact
    # metadata fields consumed by the unchanged evaluator, not a public context.
    maximum = assignment.gradeScaleMaxPoints
    if (
        assignment.id != config.assignment_id
        or assignment.context != config.course_id
        or revision != config.assignment_revision
    ):
        raise SakaiError(ErrorCode.CONFLICT)
    if (
        assignment.draft
        or assignment.anonymousGrading
        or assignment.allowPeerAssessment is not False
        or assignment.access != "SITE"
        or assignment.groups != []
        or assignment.gradeScale != "SCORE_GRADE_TYPE"
        or maximum is None
        or not re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]+)?", maximum)
        or len(maximum) > 32
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if Decimal(maximum) != Decimal(config.grading.max_points):
        raise SakaiError(ErrorCode.CONFLICT)
    # The workflow must separately prove complete manifest and stable complete
    # roster before constructing this metadata projection. This bool describes
    # evaluator metadata coverage, never native roster or full T09 completeness.
    return {
        "assignment": {"configuration_revision": revision, "max_points": maximum},
        "completeness": {"complete": True},
        "supported": {"prepare": True},
    }
