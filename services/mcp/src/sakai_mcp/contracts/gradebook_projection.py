"""Selected native table scores, correlated by external reference and stable UID."""

import re
from dataclasses import dataclass, field

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.gradebook_ui import scores, table_data
from sakai_mcp.contracts.native_html import html, one
from sakai_mcp.errors import ErrorCode, SakaiError


@dataclass(frozen=True, repr=False)
class Projection:
    link: native.Link
    values: dict[str, str | None] = field(repr=False)
    warnings: tuple[str, ...]


def projection(data: bytes, site: str, assignment: str, users: set[str]) -> Projection:
    """GbGradebookData/GradebookPage: points-only site Gradebook display evidence."""
    form = one([f for f in html(data).find(tag="form") if "data-site-id" in f.attrs])
    table = table_data(data)
    settings = table.get("settings")
    if (
        form.attrs.get("data-site-id") != site
        or form.attrs.get("data-guid") != site
        or not isinstance(settings, dict)
        or settings.get("gUid") != site
    ):
        raise SakaiError(ErrorCode.CONFLICT)
    if (
        settings.get("isPointsGradeEntry") is not True
        or settings.get("isPercentageGradeEntry") is not False
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    ref = f"/assignment/a/{site}/{assignment}"
    if len(ref) > 128:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    candidates = [
        (i, col)
        for i, col in enumerate(table["columns"])
        if col.get("externalId") == ref
    ]
    # Absence in a filtered native table does not prove 'not linked'.
    if len(candidates) != 1:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    index, column = candidates[0]
    if (
        column.get("type") != "assignment"
        or column.get("externalAppName") != "sakai.assignment.grades"
        or column.get("externallyMaintained") is not True
        or type(column.get("released")) is not bool
        or type(column.get("includedInCourseGrade")) is not bool
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if len(str(column["assignmentId"])) > 128:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    decoded = scores(table["serializedGrades"], table["rowCount"], table["columnCount"])
    values: dict[str, str | None] = {}
    warnings = {"gradebook_display_score_only", "gradebook_comment_bytes_unavailable"}
    for row, student in enumerate(table["students"]):
        uid = student["userId"]
        if uid not in users:
            continue
        value = decoded[row * table["columnCount"] + index]
        warnings.update(value.warnings)
        if "native-fraction-carry-unverified" in value.warnings:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if value.value is not None and (
            value.value.adjusted() > 31 or value.value.as_tuple().exponent < -31
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        text = format(value.value, "f") if value.value is not None else None
        if text is not None and (
            len(text) > 32 or re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]+)?", text) is None
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        values[uid] = text
        warnings.add("gradebook_representation_" + value.representation)
    if set(values) != users:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return Projection(
        native.Link(
            mode="external",
            gradebook_uid=site,
            item_id=str(column["assignmentId"]),
            external_id=ref,
            released=column["released"],
            counted=column["includedInCourseGrade"],
            available=True,
            reason="display_score_only_comment_unavailable",
        ),
        values,
        tuple(sorted(warnings)),
    )
