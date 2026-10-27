"""Assignment edit observations and source-defined date-picker form fields."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sakai_mcp.contracts.assignments import observation_revision
from sakai_mcp.contracts.native_forms import NativeForm, native_form
from sakai_mcp.contracts.native_html import Element, html, one
from sakai_mcp.errors import ErrorCode, SakaiError

if TYPE_CHECKING:
    from sakai_mcp.sakai.browser_transport import NativePage
    from sakai_mcp.workflows.access import ActorIdentity

DATES = (
    "new_assignment_open_",
    "new_assignment_due_",
    "new_assignment_close_",
    "new_assignment_visible_",
    "allow_resubmit_close_",
)
PARTS = ("year", "month", "day", "hour", "min")
SUBMISSION_TYPES = {
    "text_only": "1",
    "attachments_only": "2",
    "text_and_attachments": "3",
    "non_electronic": "4",
    "single_attachment": "5",
}


def local_instant(value: str, zone: ZoneInfo) -> datetime:
    """Reject missing/ambiguous native wall times instead of guessing a DST fold."""
    try:
        naive = datetime.fromisoformat(value)
        if naive.tzinfo is not None or naive.second or naive.microsecond:
            raise ValueError
        first, second = (
            naive.replace(tzinfo=zone, fold=0),
            naive.replace(tzinfo=zone, fold=1),
        )
        if (
            first.utcoffset() != second.utcoffset()
            or first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive
        ):
            raise ValueError
        return first
    except ValueError:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY) from None


def portal_zone(page: NativePage, actor: ActorIdentity, site: str) -> ZoneInfo:
    # morpheus/tool.vm includes includeStandardHead.vm. Extract only its literal
    # user object, not the surrounding JavaScript (which is deliberately not JSON).
    matches = []
    for script in html(page.data).find(tag="script"):
        text = "".join(c for c in script.children if isinstance(c, str))
        if re.search(r"\bvar\s+portal\s*=", text):
            matches.extend(re.findall(r'"user"\s*:\s*(\{[^{}]*\})', text))
            sites = re.findall(r'"siteId"\s*:\s*"([^"\\]*)"', text)
            if sites != [site]:
                raise SakaiError(ErrorCode.CONFLICT)
    try:
        if len(matches) != 1:
            raise ValueError
        pairs = json.loads(matches[0], object_pairs_hook=lambda p: p)
        user = dict(pairs)
        if (
            len(user) != len(pairs)
            or user.get("id") != actor.uid
            or user.get("eid") != actor.eid
        ):
            raise SakaiError(ErrorCode.UNAUTHENTICATED)
        return ZoneInfo(user["timezone"])
    except (ValueError, KeyError, TypeError, ZoneInfoNotFoundError):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY) from None


def single(form: NativeForm, key: str) -> str:
    values = [v for k, v in form.controls if k == key]
    if len(values) != 1:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return values[0]


def checked(form: NativeForm, key: str) -> bool:
    values = [v for k, v in form.controls if k == key]
    if len(values) > 1:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return bool(values)


@dataclass(frozen=True, repr=False)
class SetupForm:
    form: NativeForm
    node: Element = field(repr=False)
    zone: ZoneInfo
    dates: dict[str, datetime] = field(repr=False)
    revision: str
    locale: str

    def value(self, key: str) -> str:
        return single(self.form, key)

    def option(self, key: str, value: str) -> None:
        nodes = [
            n
            for n in self.node.find(tag="select")
            if n.attrs.get("name") == key and "disabled" not in n.attrs
        ]
        options = [
            n
            for s in nodes
            for n in s.find(tag="option")
            if n.attrs.get("value") == value and "disabled" not in n.attrs
        ]
        if len(options) != 1:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)


def setup_form(
    page: NativePage, origin: str, placement: str, actor: ActorIdentity, site: str
) -> SetupForm:
    root = html(page.data)
    if root.find(css="sak-banner-error"):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    zone = portal_zone(page, actor, site)
    node = one(
        [n for n in root.find(tag="form") if n.attrs.get("name") == "newAssignmentForm"]
    )
    form = native_form(page.data, "newAssignmentForm", origin, page.url, placement)
    controls = list(form.controls)
    names = set(form.names)
    dates = {}
    for picker in node.find(tag="sakai-date-picker"):
        prefix = picker.attrs.get("hidden-prefix")
        if prefix not in DATES:
            continue  # Peer/supplement dates remain untouched; core mode rejects active features.
        if prefix in dates or "add-hidden-fields" not in picker.attrs:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        stamp = local_instant(picker.attrs.get("iso-date", ""), zone)
        dates[prefix] = stamp
        values = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute)
        for part, value in zip(PARTS, values, strict=True):
            key = prefix + part
            if key in names:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            names.add(key)
            controls.append((key, str(value)))
    if not set(DATES[:3]) <= dates.keys():
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    form = NativeForm(form.action, tuple(controls), frozenset(names), form.csrf)
    for key in (
        "assignmentId",
        "option",
        "eventSubmit_doAssignment_form",
        "new_assignment_title",
        "new_assignment_instructions",
        "assignTo",
        "new_assignment_grade_points",
        "new_assignment_grade_type",
        "new_assignment_submission_type",
    ):
        single(form, key)
    ignored = {"sakai_csrf_token", "option", "view"}
    if not checked(form, "allowVisibleDateToggle"):
        ignored.update(k for k in names if k.startswith(DATES[3]))
    if not checked(form, "allowResToggle"):
        ignored.update(k for k in names if k.startswith("allow_resubmit_"))
    locales = []
    for script in root.find(tag="script"):
        source = "".join(c for c in script.children if isinstance(c, str))
        if re.search(r"\bvar\s+portal\s*=", source):
            locales.extend(re.findall(r'"locale"\s*:\s*"([^"\\]*)"', source))
    if len(locales) != 1:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    locale = locales[0] or "en-US"  # includeStandardHead's explicit JS fallback.
    if "new_assignment_grade_assignment" not in form.names:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    revision = observation_revision(
        {
            "controls": sorted((k, v) for k, v in form.controls if k not in ignored),
            "zone": zone.key,
        }
    )
    return SetupForm(form, node, zone, dates, revision, locale)


def reference(value: str, site: str) -> str:
    prefix = f"/assignment/a/{site}/"
    if not value.startswith(prefix):
        raise SakaiError(ErrorCode.CONFLICT)
    identifier = value[len(prefix) :]
    if (
        not identifier
        or len(identifier) > 255
        or any(ord(c) <= 32 or ord(c) == 127 or c in "/\\%?#;" for c in identifier)
    ):
        raise SakaiError(ErrorCode.CONFLICT)
    return identifier


@dataclass(frozen=True, repr=False)
class ListedAssignment:
    id: str
    title: str
    draft: bool
    edit_url: str = field(repr=False)


def listed_assignments(
    page: NativePage, origin: str, placement: str, site: str
) -> dict[str, ListedAssignment]:
    from sakai_mcp.contracts.native_forms import native_url

    result = {}
    for cell in html(page.data).find(tag="td"):
        if cell.attrs.get("headers") != "title":
            continue
        title_links = [
            a
            for strong in cell.find(tag="strong")
            for a in strong.find(tag="a")
            if a.attrs.get("name") == "asnActionLink"
        ]
        if not title_links:
            continue
        title_link = one(title_links)
        query = parse_qs(
            urlsplit(title_link.attrs.get("href", "")).query, keep_blank_values=True
        )
        refs = query.get("assignmentId", [])
        if len(refs) != 1:
            raise SakaiError(ErrorCode.CONFLICT)
        identifier = reference(refs[0], site)
        draft = bool(title_link.find(css="highlight"))
        if ("eventSubmit_doEdit_assignment" in query) != draft or (
            "eventSubmit_doView_assignment" in query
        ) == draft:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        edits = []
        for link in cell.find(tag="a"):
            href = link.attrs.get("href", "")
            q = parse_qs(urlsplit(href).query, keep_blank_values=True)
            if "eventSubmit_doEdit_assignment" in q:
                if q.get("assignmentId") != refs:
                    raise SakaiError(ErrorCode.CONFLICT)
                edits.append(native_url(origin, page.url, href, placement))
        if not edits:
            continue  # Native noneditable rows are outside this setup slice.
        if len(set(edits)) != 1 or identifier in result:
            raise SakaiError(ErrorCode.CONFLICT)
        title = title_link.attrs.get("title")
        if not title or len(title) > 200:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        result[identifier] = ListedAssignment(identifier, title, draft, edits[0])
    return result


def core_supported(snapshot: SetupForm) -> None:
    # Native tag selection is JS-synchronized; posting its empty raw input can
    # clear existing associations. Preserve those drafts until tags are researched.
    if "tag_selector" in snapshot.form.names or any(
        k.startswith("rbcs") for k in snapshot.form.names
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if not checked(snapshot.form, "new_assignment_grade_assignment"):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if checked(snapshot.form, "allowResToggle"):
        if snapshot.value("new_assignment_submission_type") == "4":
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        selectors = [
            n
            for n in snapshot.node.find(tag="select")
            if n.attrs.get("name") == "allow_resubmit_number"
        ]
        selected = [
            o
            for n in selectors
            for o in n.find(tag="option")
            if "selected" in o.attrs and "disabled" not in o.attrs
        ]
        if len(selected) != 1:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if (
        snapshot.value("assignTo") != "individuals"
        or snapshot.value("new_assignment_grade_type") != "3"
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if (
        snapshot.value("new_assignment_submission_type")
        not in SUBMISSION_TYPES.values()
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    for node in snapshot.node.find(tag="input"):
        name = node.attrs.get("name", "")
        if name == "attachments" or (
            "checked" in node.attrs
            and name
            in {
                "new_assignment_use_peer_assessment",
                "new_assignment_use_review_service",
                "new_assignment_check_anonymous_grading",
                "new_assignment_check_add_due_date",
                "new_assignment_check_auto_announce",
            }
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    for rubric in snapshot.node.find(tag="sakai-rubric-association"):
        if rubric.attrs.get("association", "") not in {"", "null", "{}"}:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        points = Decimal(snapshot.value("new_assignment_grade_points"))
        if not points.is_finite() or points <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY) from None
