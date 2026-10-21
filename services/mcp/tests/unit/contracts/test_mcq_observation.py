"""Internal evaluator metadata does not synthesize the strict public T09 state."""

import pytest

from sakai_mcp.contracts.mcq_observation import mcq_observation
from sakai_mcp.contracts.submissions import AssignmentEvidence
from sakai_mcp.errors import SakaiError
from sakai_mcp.workflows.captures import assignment_revision
from tests.fixtures import grading_data as f
from tests.fixtures.context_http import ContextHTTP


def observed():
    assignment = AssignmentEvidence.model_validate(ContextHTTP().assignment)
    value = f.config().model_dump()
    value["assignment_revision"] = assignment_revision(assignment)
    value["grading"].update(max_points="10", per_correct="2")
    return assignment, f.MCQConfig.model_validate(value)


def test_exact_metadata_projection_has_no_raw_release_scale_or_native_revision():
    assignment, config = observed()
    result = mcq_observation(assignment, assignment_revision(assignment), config)
    assert result["assignment"] == {
        "configuration_revision": config.assignment_revision,
        "max_points": "10.0",
    }
    assert "scale_factor" not in result["assignment"]
    assert "native_release_grades" not in result["assignment"]


@pytest.mark.parametrize(
    "change",
    [
        {"access": None},
        {"groups": None},
        {"groups": ["group-a"]},
        {"allowPeerAssessment": None},
        {"gradeScaleMaxPoints": None},
        {"gradeScaleMaxPoints": "9"},
        {"gradeScaleMaxPoints": "1,000"},
    ],
)
def test_unknown_or_incompatible_metadata_cannot_enable_scoring(change):
    assignment, config = observed()
    assignment = assignment.model_copy(update=change)
    with pytest.raises(SakaiError):
        mcq_observation(assignment, assignment_revision(assignment), config)
