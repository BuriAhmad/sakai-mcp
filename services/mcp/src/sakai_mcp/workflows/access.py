"""Short-lived native authorization observations, never a grant of permissions."""

from dataclasses import dataclass
from datetime import UTC, datetime

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.existing_api import (
    CurrentUser,
    Id,
    SiteDetail,
    WireModel,
    collection,
    parse,
    user_permissions,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import (
    ExistingApiTransport,
    JsonObservation,
    TokenIdentity,
)
from sakai_mcp.sakai.operations import (
    ACCESS_SITES,
    CURRENT_SITE,
    CURRENT_USER,
    USER_PERMISSIONS,
)


class _AccessSite(WireModel):
    id: Id


@dataclass(frozen=True, repr=False)
class ActorIdentity:
    tenant: str
    object_id: str
    uid: str
    eid: str

    def token_identity(self) -> TokenIdentity:
        return TokenIdentity(self.tenant, self.object_id, self.eid)

    def require_same(self, observation: JsonObservation) -> None:
        native = observation.identity
        if (native.tenant_id, native.object_id, native.sakai_eid) != (
            self.tenant,
            self.object_id,
            self.eid,
        ):
            raise SakaiError(ErrorCode.UNAUTHENTICATED)


@dataclass(frozen=True, repr=False)
class CourseAccess:
    site: str
    actor: ActorIdentity
    functions: frozenset[str] | None
    native_visit_proof: str
    observed_at: datetime


class AccessObservations:
    def __init__(self, transport: ExistingApiTransport) -> None:
        self.transport = transport

    async def actor(self, principal: AccessToken) -> ActorIdentity:
        observed = await self.transport.observe_json(CURRENT_USER, principal)
        user = parse(CurrentUser, observed.value)
        if (
            user.eid != observed.identity.sakai_eid
            or not user.id.strip()
            or user.id != user.id.strip()
        ):
            raise SakaiError(ErrorCode.FORBIDDEN)
        return ActorIdentity(
            observed.identity.tenant_id, observed.identity.object_id, user.id, user.eid
        )

    async def course(
        self, principal: AccessToken, actor: ActorIdentity, site: str
    ) -> CourseAccess:
        observed = await self.transport.observe_json(
            CURRENT_SITE, principal, parameters={"site": site}
        )
        actor.require_same(observed)
        native = parse(SiteDetail, observed.value)
        if (
            native.id != site and not (native.id == "" and native.entityId == site)
        ) or (native.entityId is not None and native.entityId != site):
            raise SakaiError(ErrorCode.CONFLICT)
        if native.type != "course":
            raise SakaiError(ErrorCode.NOT_FOUND)
        if native.pubView is None:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if not native.pubView:
            # Source SiteEntityProvider.isAllowedAccessSite invokes the same
            # allowAccessSite used by getSiteVisit before fields can be masked.
            return CourseAccess(
                site, actor, None, "native-nonpublic-allowAccessSite", datetime.now(UTC)
            )
        permissions = await self.transport.observe_json(
            USER_PERMISSIONS, principal, parameters={"site": site}
        )
        actor.require_same(permissions)
        functions = user_permissions(permissions.value)
        if "site.upd" in functions:
            # EntitySite exposes true deleted/published fields to maintainers.
            if native.softlyDeleted is None:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            required = (
                "site.visit.softly.deleted"
                if native.softlyDeleted
                else ("site.visit" if native.published else "site.visit.unp")
            )
            if required not in functions:
                raise SakaiError(ErrorCode.FORBIDDEN)
            proof = "maintainer-visible-state-and-effective-function"
        elif {"site.visit", "site.visit.unp", "site.visit.softly.deleted"} <= functions:
            # All possible native status branches are authorized. No masked
            # published/deleted field is interpreted as authoritative false.
            proof = "all-native-visit-status-branches-authorized"
        else:
            # Public-view getEntity bypasses allowAccessSite and can mask state.
            # Direct ACCESS selection uses native site-user access plus a fresh
            # SQL exclusion of softly deleted sites. Effective permission is
            # still checked separately; a known ID or SQL row is not a grant.
            if native.id:
                # The native DTO masks id and published under the same noAccess
                # predicate. Exact nonempty id proves false is unmasked too.
                required = "site.visit" if native.published else "site.visit.unp"
                if required not in functions:
                    raise SakaiError(ErrorCode.FORBIDDEN)
            elif not {"site.visit", "site.visit.unp"} <= functions:
                # False can mean unpublished or role-masked. Do not silently
                # remove a visitable site by treating that ambiguity as denial.
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            await self._current_access_site(principal, actor, site)
            proof = "native-ACCESS-not-deleted-and-effective-visit-function"
        return CourseAccess(site, actor, functions, proof, datetime.now(UTC))

    async def functions(
        self, principal: AccessToken, access: CourseAccess
    ) -> frozenset[str]:
        if access.functions is not None:
            return access.functions
        observed = await self.transport.observe_json(
            USER_PERMISSIONS, principal, parameters={"site": access.site}
        )
        access.actor.require_same(observed)
        return user_permissions(observed.value)

    async def _current_access_site(
        self, principal: AccessToken, actor: ActorIdentity, site: str
    ) -> None:
        seen: set[str] = set()
        offset = 0
        for _ in range(20):
            observed = await self.transport.observe_json(
                ACCESS_SITES,
                principal,
                query={"select": "access", "_start": str(offset), "_limit": "100"},
            )
            actor.require_same(observed)
            rows = collection(observed.value, "site", max_rows=100)
            ids = [parse(_AccessSite, row).id for row in rows]
            if len(set(ids)) != len(ids) or seen.intersection(ids):
                raise SakaiError(ErrorCode.CONFLICT)
            if site in ids:
                return  # Positive current native access observation, not a snapshot lock.
            seen.update(ids)
            if not rows:
                raise SakaiError(ErrorCode.FORBIDDEN)
            # Native maxPageSize is configurable. Advance by observed rows,
            # never mistake a server-clamped short page for end of inventory.
            offset += len(rows)
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
