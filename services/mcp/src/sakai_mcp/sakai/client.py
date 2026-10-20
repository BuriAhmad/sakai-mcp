"""Own one shared transport and expose typed Sakai operation groups."""

import httpx

from sakai_mcp.config import Settings
from sakai_mcp.sakai.announcements import AnnouncementOperations
from sakai_mcp.sakai.assignments import AssignmentOperations
from sakai_mcp.sakai.browser_transport import BrowserTransport
from sakai_mcp.sakai.courses import CourseOperations
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.grading import GradingOperations
from sakai_mcp.sakai.transport import SakaiTransport
from sakai_mcp.security.obo import OBOProvider
from sakai_mcp.storage.azure_blob import AzureBlobObjectStore
from sakai_mcp.storage.records import PrivateRecords
from sakai_mcp.workflows.announcements import AnnouncementCreation
from sakai_mcp.workflows.assignment_setup import AssignmentSetup
from sakai_mcp.workflows.captures import Captures
from sakai_mcp.workflows.submissions import SubmissionReads


class SakaiClient:
    def __init__(
        self,
        settings: Settings,
        obo: OBOProvider,
        http: httpx.AsyncClient | None = None,
        *,
        private_records: PrivateRecords | None = None,
    ) -> None:
        self.transport = SakaiTransport(settings, obo, http)
        self.existing_transport = ExistingApiTransport(settings, obo, http)
        self.browser_transport = BrowserTransport(settings, obo, http)
        self.courses = CourseOperations(
            self.transport, self.existing_transport, self.browser_transport
        )
        self._private_store = None
        if (
            private_records is None
            and settings.private_store_account_url
            and settings.private_store_container
        ):
            self._private_store = AzureBlobObjectStore.managed_identity(
                settings.private_store_account_url,
                settings.private_store_container,
                client_id=settings.private_store_managed_identity_client_id,
            )
            private_records = PrivateRecords(self._private_store)
        self.announcements = AnnouncementOperations(
            self.transport,
            self.existing_transport,
            AnnouncementCreation(
                self.existing_transport, self.browser_transport, private_records
            ),
        )
        self.submissions = SubmissionReads(
            self.existing_transport, self.browser_transport
        )
        self.assignments = AssignmentOperations(
            settings,
            self.submissions,
            AssignmentSetup(self.submissions, private_records),
        )
        self.grading = GradingOperations(
            self.transport,
            self.existing_transport,
            self.submissions,
            Captures(self.submissions, private_records),
        )

    async def aclose(self) -> None:
        try:
            await self.transport.aclose()
        finally:
            try:
                await self.existing_transport.aclose()
            finally:
                try:
                    await self.browser_transport.aclose()
                finally:
                    if self._private_store is not None:
                        await self._private_store.aclose()
