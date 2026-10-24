/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.Authentication;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Bounded authentication conversations stored only in native Session attributes. */
final class DelegatedConversations {
    static final String STATE = DelegatedConversations.class.getName() + ".state";
    private static final Object CREATION = new Object();
    private static final ReentrantLock[] LOCKS = new ReentrantLock[64];

    static {
        Arrays.setAll(LOCKS, i -> new ReentrantLock());
    }

    record Owner(String tenant, String object, String uid, String eid, long deadline) {}

    static final class Denied extends Exception {
        final int status;

        Denied(int status) {
            this.status = status;
        }
    }

    static final class Lease implements AutoCloseable {
        final Session session;
        private final SessionManager sessions;
        private final ReentrantLock lock;
        private boolean retain;

        Lease(Session session, SessionManager sessions, ReentrantLock lock, boolean retain) {
            this.session = session;
            this.sessions = sessions;
            this.lock = lock;
            this.retain = retain;
        }

        void abort() {
            retain = false;
        }

        @Override
        public void close() {
            try {
                if (!retain) {
                    sessions.setCurrentSession(session);
                    session.invalidate();
                }
            } finally {
                if (lock != null) lock.unlock();
            }
        }
    }

    static Lease open(
            ServerConfigurationService configuration,
            SessionManager sessions,
            UsageSessionService usage,
            Authentication account,
            DelegatedCredentialGuard.ExternalIdentity identity,
            String nonce,
            boolean end,
            String remote,
            Clock clock)
            throws Denied {
        if (nonce == null) return create(sessions, usage, account, null, null, false, remote);
        if (!nonce.matches("[a-f0-9]{64}")) throw new Denied(403);
        if (!configuration.getBoolean("mcp.integration.conversations.enabled", false))
            throw new Denied(404);
        String id;
        try {
            byte[] secret =
                    Base64.getDecoder()
                            .decode(configuration.getString("mcp.integration.flowSecret", ""));
            if (secret.length < 32 || secret.length > 64) throw new IllegalArgumentException();
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            id =
                    "mcp_"
                            + HexFormat.of()
                                    .formatHex(
                                            mac.doFinal(
                                                    ("sakai-mcp-flow-v1\0"
                                                                    + identity.tenantId()
                                                                    + "\0"
                                                                    + identity.objectId()
                                                                    + "\0"
                                                                    + account.getUid()
                                                                    + "\0"
                                                                    + account.getEid()
                                                                    + "\0"
                                                                    + nonce)
                                                            .getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new Denied(503);
        }
        ReentrantLock lock = LOCKS[Math.floorMod(id.hashCode(), LOCKS.length)];
        if (!lock.tryLock()) throw new Denied(409);
        try {
            synchronized (CREATION) {
                Session s = sessions.getSession(id);
                if (s == null) {
                    if (end) throw new Denied(410);
                    long total = 0, owned = 0;
                    for (Session existing : sessions.getSessions()) {
                        Object saved = existing.getAttribute(STATE);
                        if (saved instanceof Owner owner) {
                            total++;
                            if (owner.tenant().equals(identity.tenantId())
                                    && owner.object().equals(identity.objectId())) owned++;
                        }
                    }
                    if (total >= 256 || owned >= 4) throw new Denied(503);
                    Lease lease = create(sessions, usage, account, id, lock, true, remote);
                    try {
                        lease.session.setAttribute(
                                STATE,
                                new Owner(
                                        identity.tenantId(),
                                        identity.objectId(),
                                        account.getUid(),
                                        account.getEid(),
                                        clock.millis() + 300_000));
                    } catch (RuntimeException e) {
                        lease.abort();
                        lease.close();
                        throw new Denied(503);
                    }
                    return lease;
                }
                Object saved = s.getAttribute(STATE);
                if (!(saved instanceof Owner owner)
                        || !owner.tenant().equals(identity.tenantId())
                        || !owner.object().equals(identity.objectId())
                        || !owner.uid().equals(account.getUid())
                        || !owner.eid().equals(account.getEid())
                        || !account.getUid().equals(s.getUserId())
                        || !account.getEid().equals(s.getUserEid())) throw new Denied(403);
                if (clock.millis() >= owner.deadline()) {
                    sessions.setCurrentSession(s);
                    s.invalidate();
                    throw new Denied(410);
                }
                return new Lease(s, sessions, lock, !end);
            }
        } catch (Denied | RuntimeException e) {
            // create() may already have released its lease on failed login.
            if (lock.isHeldByCurrentThread()) lock.unlock();
            if (e instanceof Denied denied) throw denied;
            throw new Denied(503);
        }
    }

    private static Lease create(
            SessionManager sessions,
            UsageSessionService usage,
            Authentication account,
            String id,
            ReentrantLock lock,
            boolean retain,
            String remote)
            throws Denied {
        Session session = id == null ? sessions.startSession() : sessions.startSession(id);
        if (session == null) throw new Denied(503);
        Lease lease = new Lease(session, sessions, lock, retain);
        try {
            sessions.setCurrentSession(session);
            session.setMaxInactiveInterval(60);
            if (!usage.login(
                            account.getUid(),
                            account.getEid(),
                            remote,
                            "MCP existing HTTP delegated context",
                            UsageSessionService.EVENT_LOGIN_WS)
                    || !account.getUid().equals(session.getUserId())
                    || !account.getEid().equals(session.getUserEid())) throw new Denied(503);
            return lease;
        } catch (Denied | RuntimeException e) {
            lease.abort();
            lease.close();
            if (e instanceof Denied denied) throw denied;
            throw new Denied(503);
        }
    }

    private DelegatedConversations() {}
}
