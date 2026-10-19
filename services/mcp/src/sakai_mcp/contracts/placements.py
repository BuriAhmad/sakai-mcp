"""Existing Site pages action: explicit native relationships, no title matching."""

import re
from dataclasses import dataclass, field
from typing import Annotated, Any
from urllib.parse import unquote, urlsplit

from pydantic import Field, StrictStr

from sakai_mcp.contracts.existing_api import Id, WireModel, parse
from sakai_mcp.contracts.native_forms import native_url
from sakai_mcp.errors import ErrorCode, SakaiError

SUPPORTED_TOOLS = frozenset(
    {
        "sakai.announcements",
        "sakai.assignment.grades",
        "sakai.gradebookng",
        "sakai.filepicker",
    }
)


class _Tool(WireModel):
    id: Id
    toolId: Id
    placementId: Id
    context: Id
    pageId: Id
    siteId: Id
    url: StrictStr = Field(repr=False)


class _Page(WireModel):
    id: Id
    siteId: Id
    url: StrictStr = Field(repr=False)
    tools: Annotated[list[_Tool], Field(max_length=100)]


@dataclass(frozen=True, repr=False)
class Placement:
    site: str
    tool: str
    placement: str
    url: str = field(repr=False)


def _page_url(origin: str, value: str, site: str, page: str) -> None:
    try:
        expected, parsed = urlsplit(origin), urlsplit(value)
        if (
            len(value) > 8192
            or any(ord(c) <= 32 or ord(c) == 127 for c in value)
            or parsed.scheme != "https"
            or parsed.hostname != expected.hostname
            or (parsed.port or 443) != (expected.port or 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "\\" in value
            or ";" in parsed.path
            or re.search(r"%(?:2f|5c|25)", parsed.path, re.IGNORECASE)
            or unquote(parsed.path) != f"/portal/site/{site}/page/{page}"
        ):
            raise ValueError
    except ValueError:
        raise SakaiError(ErrorCode.CONFLICT) from None


def placement(value: Any, site: str, tool: str, origin: str) -> Placement:
    if tool not in SUPPORTED_TOOLS:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    # getPagesAndTools returns ActionReturn(Object), whose contract disables
    # entity metadata wrapping. Do not guess a collection envelope.
    if not isinstance(value, list) or len(value) > 1000:
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    pages = [parse(_Page, row) for row in value]
    page_ids: set[str] = set()
    placement_ids: set[str] = set()
    candidates = []
    for page in pages:
        if page.siteId != site or page.id in page_ids:
            raise SakaiError(ErrorCode.CONFLICT)
        page_ids.add(page.id)
        _page_url(origin, page.url, site, page.id)
        for native in page.tools:
            if (
                native.id != native.placementId
                or native.siteId != site
                or native.context != site
                or native.pageId != page.id
                or native.placementId in placement_ids
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            placement_ids.add(native.placementId)
            # Native toolData.url is a page URL, not a unique placement URL.
            _page_url(origin, native.url, site, page.id)
            if native.toolId == tool:
                target = native_url(
                    origin,
                    origin,
                    f"/portal/tool/{native.placementId}",
                    native.placementId,
                )
                candidates.append(Placement(site, tool, native.placementId, target))
    if not candidates:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if len(candidates) != 1:
        raise SakaiError(ErrorCode.CONFLICT)
    return candidates[0]
