import pytest

from sakai_mcp.grading.evaluator import evaluate_mcq
from sakai_mcp.grading.reports import report_csv
from tests.fixtures.grading_requests import make_evidence


@pytest.mark.parametrize(
    "data,score",
    [
        (b"A\nC\nB\nD\nA\n", "5"),
        (b"A\nC\nA\nD\nA\n", "4"),
        (b"a\nc\nb\nd\na\n", "5"),
        (b" A \n C\nB \nD\nA\n", "5"),
        (b"A\nC\nB\nD\n", None),
        (b"A\nC\nX\nD\nA\n", None),
        (b"", None),
        (b"%PDF-1.7 fake", None),
        (b"\n" * 500_000, None),
    ],
)
def test_deterministic_known_cases_preserve_raw(data, score):
    config, context, roster, manifest, files = make_evidence(data)
    result = evaluate_mcq(config, context, roster, manifest, files)
    assert result[0]["score"] == score
    assert result[0]["review_status"] == (
        "proposed" if score is not None else "review_required"
    )
    assert files["artifact"] == data
    assert "submission_id" in report_csv(result)


def test_integrity_failure_and_changed_identity_are_rejected():
    config, context, roster, manifest, files = make_evidence(b"A\nC\nB\nD\nA\n")
    files["artifact"] = b"changed"
    with pytest.raises(ValueError, match="integrity"):
        evaluate_mcq(config, context, roster, manifest, files)
    roster[0]["submitters"] = [{"sakai_user_id": "wrong"}]
    result = evaluate_mcq(config, context, roster, manifest, files)
    assert (
        result[0]["score"] is None and "source_identity_changed" in result[0]["issues"]
    )
