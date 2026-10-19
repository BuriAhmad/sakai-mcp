import pytest
from pydantic import ValidationError

from sakai_mcp.contracts.grading_native import (
    FeedbackPatch,
    SaveAssignmentGradesRequest,
)
from tests.fixtures.grading_requests import save_request


@pytest.mark.parametrize("score", [True, 4, 4.5, "NaN", "Infinity", "-1", "04"])
def test_scores_are_strict_exact_decimal_strings(score):
    with pytest.raises(ValidationError):
        SaveAssignmentGradesRequest.model_validate(save_request(score))


@pytest.mark.parametrize(
    "action,text",
    [("preserve", "overwrite"), ("clear", "overwrite"), ("replace", None)],
)
def test_feedback_patch_does_not_clear_omitted_fields(action, text):
    with pytest.raises(ValidationError):
        FeedbackPatch(action=action, text=text)
