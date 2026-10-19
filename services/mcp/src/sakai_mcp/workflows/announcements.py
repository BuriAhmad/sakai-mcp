"""Existing native Add/form POST with durable single-send intent and readback."""

from datetime import UTC, datetime
from html import escape
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.announcements import announcement_rows
from sakai_mcp.contracts.native_forms import native_form, native_url
from sakai_mcp.contracts.native_html import html, one
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.sakai.browser_transport import BrowserTransport, NativePage
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import ANNOUNCEMENTS
from sakai_mcp.storage.base import RecordOwner
from sakai_mcp.storage.records import PrivateRecords
from sakai_mcp.workflows.access import AccessObservations
from sakai_mcp.workflows.operation_journal import OperationJournal
from sakai_mcp.workflows.placements import PlacementDiscovery


def action_links(
    page: NativePage, origin: str, placement: str, action: str
) -> list[str]:
    urls: set[str] = set()
    for link in html(page.data).find(tag="a"):
        href = link.attrs.get("href", "")
        if not href or href.startswith(("javascript:", "#")):
            continue
        query = parse_qs(urlsplit(href).query, keep_blank_values=True)
        if action not in query:
            continue
        urls.add(native_url(origin, page.url, href, placement))
    return sorted(urls)


def message_ids(page: NativePage, origin: str, placement: str, site: str) -> set[str]:
    result = set()
    for url in action_links(page, origin, placement, "eventSubmit_doShowmetadata"):
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        refs = query.get("itemReference")
        prefix = f"/announcement/msg/{site}/main/"
        if refs is None or len(refs) != 1:
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        if not refs[0].startswith(prefix):
            continue  # Authorized merged channels are never write destinations.
        message = refs[0][len(prefix) :]
        if not message or "/" in message or len(message) > 255:
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        result.add(message)
    return result


class AnnouncementCreation:
    def __init__(
        self,
        existing: ExistingApiTransport,
        browser: BrowserTransport,
        records: PrivateRecords | None,
    ) -> None:
        self.existing, self.browser = existing, browser
        self.journal = OperationJournal(records) if records is not None else None
        self.discovery = PlacementDiscovery(existing)
        self.access = AccessObservations(existing)

    async def create(
        self, principal: AccessToken, site: str, title: str, body: str
    ) -> dict[str, Any]:
        if self.journal is None:
            # No ephemeral fallback, no unjournaled academic POST.
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        bound = await self.discovery.resolve(principal, site, "sakai.announcements")
        if "annc.new" not in await self.access.functions(principal, bound.access):
            raise SakaiError(ErrorCode.FORBIDDEN)
        actor = bound.access.actor
        owner = RecordOwner(
            actor.tenant, actor.object_id, actor.uid, site, "__announcements__"
        )
        operation = str(uuid4())
        placement = bound.target.placement
        async with self.browser.conversation(
            principal, placement, identity=actor.token_identity()
        ) as flow:
            baseline = await flow.navigate()
            original = message_ids(baseline, self.browser.origin, placement, site)
            add = action_links(
                baseline,
                self.browser.origin,
                placement,
                "eventSubmit_doNewannouncement",
            )
            if len(add) != 1:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            edit = await flow.navigate(add[0])
            root = html(edit.data)
            form_node = one(
                [
                    f
                    for f in root.find(tag="form")
                    if f.attrs.get("name") == "reviseForm"
                ]
            )
            # Require the actual native allowed controls, not merely their names.
            if not any(
                n.attrs.get("name") == "announceTo"
                and n.attrs.get("value") == "site"
                and "disabled" not in n.attrs
                for n in form_node.find(tag="input")
            ):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if not any(
                n.attrs.get("value") == "o" and "disabled" not in n.attrs
                for n in form_node.find(tag="option")
            ):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if root.find(css="sak-banner-error"):
                raise SakaiError(ErrorCode.FORBIDDEN)
            form = native_form(
                edit.data, "reviseForm", self.browser.origin, edit.url, placement
            )
            prepared_body = (
                escape(body, quote=False)
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .replace("\n", "<br />")
            )
            changes: dict[str, str | list[str]] = {
                "subject": escape(title, quote=False),
                "body": prepared_body,
                "option": "post",
                "eventSubmit_doAnnouncement_form": "",
                "announceTo": "site",
                "hidden": "false",
                "notify": "o",
            }
            for field in [
                "selectedRoles",
                "selectedGroups",
                "use_start_date",
                "use_end_date",
                "highlight",
            ]:
                if field in form.names:
                    changes[field] = []
            form.values(changes)
            # No stale action/credential, selected destination, attachment helper or
            # notification choice can be supplied by the public tool arguments.
            request = {
                "kind": "announcement-create",
                "site": site,
                "title": title,
                "body": body,
                "baseline_ids": sorted(original),
                "notification": "optional",
                "destination": "main",
            }
            request_hash = digest(canonical(request))
            now = datetime.now(UTC)
            await self.journal.prepare(owner, operation, request, request_hash, now=now)
            await self.journal.begin_send(
                owner, operation, request_hash, now=datetime.now(UTC)
            )
            try:
                posted = await flow.submit(form, changes, academic=True)
                if html(posted.data).find(css="sak-banner-error"):
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                candidates = (
                    message_ids(posted, self.browser.origin, placement, site) - original
                )
                if len(candidates) != 1:
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                observed = await self.existing.observe_json(
                    ANNOUNCEMENTS,
                    principal,
                    parameters={"site": site},
                    query={"n": "1000", "d": "1", "a": "0"},
                )
                actor.require_same(observed)
                matches = [
                    r
                    for r in announcement_rows(observed.value, site)
                    if r["id"] in candidates
                    and r["title"] == title
                    and r["body"].replace("<br/>", "<br />").replace("<br>", "<br />")
                    == prepared_body
                    and r["postedAt"] >= int(now.timestamp() * 1000)
                ]
                if len(matches) != 1:
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                found = matches[0]
                await self.journal.observe(
                    owner,
                    operation,
                    {
                        "message_id": found["id"],
                        "posted_at": found["postedAt"],
                        "verified_body_sha256": digest(found["body"].encode()),
                    },
                    partial=False,
                    now=datetime.now(UTC),
                )
                return {
                    "id": found["id"],
                    "courseId": site,
                    "title": title,
                    "postedAt": found["postedAt"],
                    "verification": {
                        "kind": "native-response-and-readback",
                        "causation_guaranteed": False,
                    },
                }
            except SakaiError:
                try:
                    await self.journal.unknown(owner, operation, now=datetime.now(UTC))
                except SakaiError:
                    pass  # Sending already persists; no lease expiry permits replay.
                raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
