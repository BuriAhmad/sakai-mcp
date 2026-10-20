"""Existing Announcement DTOs: main-channel selection and exact epoch-ms dates."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import Field, StrictInt, StrictStr

from sakai_mcp.contracts.existing_api import (
    Id,
    InstantEncoding,
    WireModel,
    collection,
    instant,
    parse,
)
from sakai_mcp.errors import ErrorCode, SakaiError

OBSERVATION_CAP = 1000
LOOKBACK_DAYS = 3650


class _Announcement(WireModel):
    announcementId: Id
    siteId: Id
    channel: Id
    title: StrictStr
    body: StrictStr = Field(repr=False)
    createdOn: Annotated[StrictInt, Field(ge=0)]


def announcement_rows(
    value: Any, site: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    if (
        isinstance(value, dict)
        and value.get("entityPrefix", "announcement") != "announcement"
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    rows = collection(value, "announcement", max_rows=OBSERVATION_CAP)
    if len(rows) == OBSERVATION_CAP:
        # A globally trimmed merged response cannot establish main-channel coverage.
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    found: dict[str, dict[str, Any]] = {}
    for native in rows:
        row = parse(_Announcement, native)
        if row.siteId != site or row.channel != "main":
            continue
        if row.announcementId in found:
            raise SakaiError(ErrorCode.CONFLICT)
        posted = instant(row.createdOn, InstantEncoding.MILLISECONDS)
        # Native ViewableFilter compares the releaseDate property, not every
        # message's posting date. Enforce the intended lookback here, with long
        # datetime arithmetic, without changing either native handler.
        if posted is None or not now - timedelta(days=LOOKBACK_DAYS) <= posted <= now:
            continue
        found[row.announcementId] = {
            "id": row.announcementId,
            "title": row.title,
            "body": row.body,
            "postedAt": row.createdOn,
        }
    return sorted(found.values(), key=lambda row: (-row["postedAt"], row["id"]))[:50]
