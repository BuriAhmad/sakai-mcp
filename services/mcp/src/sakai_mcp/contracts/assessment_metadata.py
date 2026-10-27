"""Existing grading/item-data DTOs: metadata only, no student score reads."""

import math
import sys
from typing import Any

from sakai_mcp.contracts import assignment_setup as public
from sakai_mcp.errors import ErrorCode, SakaiError


def native_id(value: Any) -> str:
    if type(value) is not int or not 0 < value < 2**63:
        raise SakaiError(ErrorCode.CONFLICT)
    return str(value)


def assessment_metadata(
    value: Any, site: str
) -> tuple[list[public.GradebookItem], list[public.Category], list[str]]:
    if not isinstance(value, dict) or any(
        not isinstance(value.get(k), list) for k in ("items", "categories")
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    if any(len(value[k]) > 500 for k in ("items", "categories")):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    items, categories, warnings = (
        [],
        [],
        [
            "gradebook_settings_and_item_due_dates_not_observed",
            "gradebook_metadata_uses_native_double_precision",
        ],
    )
    seen_items, seen_categories = set(), set()
    for row in value["items"]:
        if not isinstance(row, dict) or row.get("context") != site:
            raise SakaiError(ErrorCode.CONFLICT)
        identifier = native_id(row.get("id"))
        if identifier in seen_items:
            raise SakaiError(ErrorCode.CONFLICT)
        seen_items.add(identifier)
        if not isinstance(row.get("name"), str) or not 0 < len(row["name"]) <= 255:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if any(
            type(row.get(k)) is not bool
            for k in ("released", "counted", "extraCredit", "externallyMaintained")
        ):
            warnings.append("gradebook_item_full_flags_unavailable: " + identifier)
            continue
        points = row.get("points")
        if points is not None and (
            type(points) not in {int, float}
            or not 0 <= points <= sys.float_info.max
            or not math.isfinite(points)
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        category = row.get("categoryId")
        items.append(
            public.GradebookItem(
                id=identifier,
                title=row["name"],
                max_points=float(points) if points is not None and points > 0 else None,
                due_on=None,
                category_id=native_id(category) if category is not None else None,
                released=row["released"],
                counted=row["counted"],
                extra_credit=row["extraCredit"],
                externally_maintained=row["externallyMaintained"],
                external_id=row.get("externalId"),
                external_app=row.get("externalAppName"),
                gradable_reference=row.get("reference"),
            )
        )
    for row in value["categories"]:
        if not isinstance(row, dict):
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        identifier = native_id(row.get("id"))
        if identifier in seen_categories:
            raise SakaiError(ErrorCode.CONFLICT)
        seen_categories.add(identifier)
        if not isinstance(row.get("name"), str) or not 0 < len(row["name"]) <= 255:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if any(
            type(row.get(k)) is not bool
            for k in ("equalWeight", "extraCredit", "dropKeepEnabled")
        ) or any(
            type(row.get(k)) is not int or row[k] < 0
            for k in ("dropLowest", "dropHighest", "keepHighest")
        ):
            warnings.append("gradebook_category_full_rules_unavailable: " + identifier)
            continue
        weight = row.get("weight")
        if weight is not None and (
            type(weight) not in {int, float}
            or not 0 <= weight <= 1
            or not math.isfinite(weight)
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        categories.append(
            public.Category(
                id=identifier,
                name=row["name"],
                weight_percent=float(weight * 100) if weight is not None else None,
                equal_weight_items=row["equalWeight"],
                drop_lowest=row["dropLowest"],
                drop_highest=row["dropHighest"],
                keep_highest=row["keepHighest"],
                extra_credit=row["extraCredit"],
                drop_keep_enabled=row["dropKeepEnabled"],
            )
        )
    return items, categories, warnings
