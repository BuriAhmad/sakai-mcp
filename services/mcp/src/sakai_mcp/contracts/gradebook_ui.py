"""Read native Gradebook data without evaluating script or inventing raw precision."""

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from sakai_mcp.contracts.native_forms import native_url
from sakai_mcp.contracts.native_xml import xml
from sakai_mcp.errors import ErrorCode, SakaiError


@dataclass(frozen=True)
class DisplayedScore:
    value: Decimal | None = field(repr=False)
    text: str | None = field(repr=False)
    representation: str
    warnings: tuple[str, ...] = ()


def scores(serialized: str, rows: int, columns: int) -> tuple[DisplayedScore, ...]:
    if (
        type(rows) is not int
        or type(columns) is not int
        or rows < 0
        or columns < 0
        or rows * columns > 100000
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    count = rows * columns
    if len(serialized) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        if serialized.startswith("json:"):
            values = json.loads(serialized[5:], parse_float=Decimal, parse_int=Decimal)
            if not isinstance(values, list) or len(values) != count:
                raise ValueError
            result = []
            for value in values:
                if value is not None and (
                    not isinstance(value, Decimal) or not value.is_finite()
                ):
                    raise ValueError
                result.append(
                    DisplayedScore(
                        value, str(value) if value is not None else None, "json-double"
                    )
                )
            return tuple(result)
        if not serialized.startswith("packed:"):
            raise ValueError
        data = base64.b64decode(serialized[7:], validate=True)
        result = []
        index = 0
        for _ in range(count):
            first = data[index]
            index += 1
            if first == 127:
                result.append(DisplayedScore(None, None, "packed-null"))
            elif first & 128:
                integer = ((first & 63) << 8) | data[index]
                index += 1
                text = str(integer)
                warnings: tuple[str, ...] = ()
                if first & 64:
                    fraction = data[index]
                    index += 1
                    if fraction > 100:
                        raise ValueError
                    text += f".{fraction:02d}"
                    warnings = ("display-rounded-to-hundredths",)
                    if fraction == 100:
                        # Preserve what the baseline JS displays, including its
                        # suspect missing carry. Never guess the original grade.
                        warnings += ("native-fraction-carry-unverified",)
                result.append(
                    DisplayedScore(Decimal(text), text, "packed-display", warnings)
                )
            else:
                result.append(
                    DisplayedScore(Decimal(first), str(first), "packed-integer")
                )
        if index != len(data):
            raise ValueError
        return tuple(result)
    except (ValueError, TypeError, IndexError, binascii.Error):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


class _Scripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.scripts: list[str] = []
        self.current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.inside = True
            self.current = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.inside:
            self.scripts.append("".join(self.current))
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.current.append(data)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def table_data(data: bytes) -> dict[str, Any]:
    """Extract only the source-defined tableData JSON literal; never run JS."""
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        parser = _Scripts()
        parser.feed(data.decode("utf-8-sig"))
        parser.close()
        found = []
        decoder = json.JSONDecoder(object_pairs_hook=_unique)
        for script in parser.scripts:
            for match in re.finditer(
                r"(?:^|[;\n])\s*(?:var|let|const)\s+tableData\s*=\s*", script
            ):
                value, _ = decoder.raw_decode(script[match.end() :])
                found.append(value)
        if len(found) != 1 or not isinstance(found[0], dict):
            raise ValueError
        result = found[0]
        students, columns = result.get("students"), result.get("columns")
        rows, cols = result.get("rowCount"), result.get("columnCount")
        if (
            not isinstance(students, list)
            or not isinstance(columns, list)
            or type(rows) is not int
            or type(cols) is not int
        ):
            raise ValueError
        if rows != len(students) or cols != len(columns):
            raise ValueError
        user_ids = [s.get("userId") if isinstance(s, dict) else None for s in students]
        if (
            any(
                not isinstance(uid, str) or not uid or len(uid) > 255
                for uid in user_ids
            )
            or len(set(user_ids)) != rows
        ):
            raise ValueError
        item_ids = []
        for column in columns:
            if not isinstance(column, dict) or column.get("type") not in {
                "assignment",
                "category",
            }:
                raise ValueError
            if column["type"] == "assignment":
                item = column.get("assignmentId")
                if type(item) is not int or item <= 0:
                    raise ValueError
                item_ids.append(item)
        if len(set(item_ids)) != len(item_ids) or not isinstance(
            result.get("serializedGrades"), str
        ):
            raise ValueError
        scores(result["serializedGrades"], rows, cols)
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


@dataclass(frozen=True)
class WicketUpdate:
    components: tuple[tuple[str, str], ...] = field(repr=False)
    redirect: str | None = field(repr=False)
    scripts_present: bool
    unknown_nodes: tuple[str, ...]


def wicket_update(data: bytes, origin: str, base: str, placement: str) -> WicketUpdate:
    root = xml(data)
    if root.tag != "ajax-response":
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    components: list[tuple[str, str]] = []
    redirect = None
    scripts = False
    unknown = []
    for child in root:
        if child.tag == "component":
            identifier = child.get("id")
            if not identifier or len(identifier) > 255 or len(child):
                raise SakaiError(ErrorCode.INTERNAL_ERROR)
            components.append((identifier, child.text or ""))
        elif child.tag == "redirect":
            if redirect is not None or not child.text:
                raise SakaiError(ErrorCode.INTERNAL_ERROR)
            redirect = native_url(origin, base, child.text, placement)
        elif child.tag in {"evaluate", "priority-evaluate"}:
            scripts = True
        else:
            unknown.append(child.tag)
    if len({key for key, _ in components}) != len(components):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return WicketUpdate(tuple(components), redirect, scripts, tuple(unknown))


@dataclass(frozen=True, repr=False)
class OwnGradeRow:
    title: str
    score: str | None
    points: Decimal | None


def own_grade_rows(data: bytes) -> list[OwnGradeRow]:
    """StudentPage's released current-user table, never instructor tableData."""
    from sakai_mcp.contracts.native_html import html, one

    root = html(data)
    summary = one(root.find(id="studentGradeSummary"))
    tables = summary.find(id="gradeSummaryTable")
    if not tables:
        # Hidden/no released items are not a fabricated table with zero scores.
        return []
    table = one(tables)
    rows = []
    for row in table.find(tag="tr", css="gb-summary-grade-row"):
        if row.find(css="gb-flag-not-released"):
            raise SakaiError(ErrorCode.CONFLICT)
        title = one(row.find(css="gb-summary-grade-title")).text()
        grades = row.find(css="gb-summary-grade-score-raw")
        score = one(grades).text().strip() if grades else None
        if score in {"", "-", "—"}:
            score = None
        maximum = row.find(css="gb-summary-grade-score-outof")
        points = None
        if maximum:
            text = one(maximum).text().strip()
            # Native resource label.studentsummary.outof is '/ {0}'. Do not
            # guess localized grouping/decimal separators or scale percentages.
            match = re.fullmatch(r"/\s*([0-9]+(?:\.[0-9]+)?)", text)
            if not match:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            points = Decimal(match[1])
        rows.append(OwnGradeRow(title, score, points))
        if len(rows) > 500:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if len({r.title for r in rows}) != len(rows):
        raise SakaiError(ErrorCode.CONFLICT)
    return rows
