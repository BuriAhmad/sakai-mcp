/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.tool.api.ToolManager;
import org.sakaiproject.tool.api.ToolSession;
import org.sakaiproject.user.api.Authentication;
import org.sakaiproject.user.api.AuthenticationException;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.ExternalTrustedEvidence;
import org.sakaiproject.util.RequestFilter;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.MalformedURLException;
import java.security.Principal;
import java.time.Clock;
import java.util.*;

import javax.servlet.*;
import javax.servlet.http.*;

/** Validates credentials before native wrappers capture an isolated session. */
public final class DelegatedCredentialGuard implements Filter {
    static final String MARKER = DelegatedCredentialGuard.class.getName() + ".identity";
    private static final String CURRENT_SESSION = "org.sakaiproject.api.kernel.session.current";
    private static final String CURRENT_TOOL = CURRENT_SESSION + ".tool";
    private static final List<String> THREAD_KEYS =
            List.of(
                    CURRENT_SESSION,
                    CURRENT_TOOL,
                    "sakai:ToolComponent:current.tool",
                    "sakai:ToolComponent:current.placement",
                    RequestFilter.CURRENT_HTTP_REQUEST,
                    RequestFilter.CURRENT_HTTP_RESPONSE,
                    RequestFilter.CURRENT_SERVLET_CONTEXT,
                    "org.sakaiproject.util.RequestFilter.remote_user",
                    "org.sakaiproject.util.RequestFilter.http_session",
                    "org.sakaiproject.util.RequestFilter.context",
                    ServerConfigurationService.CURRENT_SERVER_URL,
                    ServerConfigurationService.CURRENT_PORTAL_PATH);
    private static final List<String> ATTRIBUTES =
            List.of(
                    MARKER,
                    RequestFilter.ATTR_SESSION,
                    RequestFilter.ATTR_FILTERED,
                    RequestFilter.ATTR_SET_COOKIE,
                    RequestFilter.ATTR_CHARACTER_ENCODING_DONE,
                    RequestFilter.ATTR_UPLOADS_DONE);
    private ServerConfigurationService configuration;
    private AuthenticationManager authentication;
    private SessionManager sessions;
    private UsageSessionService usage;
    private ThreadLocalManager threads;
    private volatile DelegatedJwtVerifier verifier;

    public DelegatedCredentialGuard() {}

    DelegatedCredentialGuard(
            ServerConfigurationService configuration,
            AuthenticationManager authentication,
            SessionManager sessions,
            UsageSessionService usage,
            ThreadLocalManager threads,
            DelegatedJwtVerifier verifier) {
        this.configuration = configuration;
        this.authentication = authentication;
        this.sessions = sessions;
        this.usage = usage;
        this.threads = threads;
        this.verifier = verifier;
    }

    @Override
    public void init(FilterConfig config) {
        if (configuration == null) {
            configuration = ComponentManager.get(ServerConfigurationService.class);
            authentication = ComponentManager.get(AuthenticationManager.class);
            sessions = ComponentManager.get(SessionManager.class);
            usage = ComponentManager.get(UsageSessionService.class);
            threads = ComponentManager.get(ThreadLocalManager.class);
        }
    }

    // This value is created only by the verified guard, never by an HTTP header.
    record BoundIdentity(
            Session session, String uid, String eid, String placement, boolean conversation) {}

    @Override
    public void doFilter(ServletRequest raw, ServletResponse output, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) raw;
        HttpServletResponse response = (HttpServletResponse) output;
        Object internal = request.getAttribute(MARKER);
        if (internal instanceof BoundIdentity bound) {
            ToolManager tools = ComponentManager.get(ToolManager.class);
            if (!bound.conversation()
                    || (request.getDispatcherType() != DispatcherType.REQUEST
                            && request.getDispatcherType() != DispatcherType.FORWARD
                            && request.getDispatcherType() != DispatcherType.INCLUDE)
                    || sessions.getCurrentSession() != bound.session()
                    || tools == null
                    || tools.getCurrentPlacement() == null
                    || !Objects.equals(bound.placement(), tools.getCurrentPlacement().getId())
                    || tools.getCurrentTool() == null
                    || !Set.of(
                                    "sakai.assignment.grades",
                                    "sakai.assignment",
                                    "sakai.announcements",
                                    "sakai.gradebookng",
                                    "sakai.filepicker")
                            .contains(tools.getCurrentTool().getId())) {
                response.sendError(403);
                return;
            }
            chain.doFilter(raw, output);
            return;
        }
        List<String> headers = Collections.list(request.getHeaders("Authorization"));
        boolean bearer = headers.stream().anyMatch(h -> h.regionMatches(true, 0, "Bearer", 0, 6));
        // Existing legacy filter retains sole responsibility for its namespace.
        if (DelegatedRoutes.legacy(request)) {
            chain.doFilter(raw, output);
            return;
        }
        if (!bearer) {
            if (request.getHeader("X-MCP-Flow") != null
                    || request.getHeader("X-MCP-Flow-End") != null) {
                unauthorized(response);
                return;
            }
            chain.doFilter(raw, output);
            return;
        }
        request.setCharacterEncoding("UTF-8");
        response.setHeader("Cache-Control", "no-store");
        if (headers.size() != 1 || !headers.get(0).matches("(?i)Bearer [A-Za-z0-9_.-]{1,16384}")) {
            unauthorized(response);
            return;
        }
        if (!RequestFilter.isSecure(request)
                || !(DelegatedRoutes.allows(request)
                        || DelegatedRoutes.conversationAllows(request, configuration))) {
            response.sendError(403);
            return;
        }
        if (!configuration.getBoolean("mcp.integration.existingHttp.enabled", false)) {
            response.sendError(404);
            return;
        }
        if (request.getHeader("Cookie") != null
                || (request.getCookies() != null && request.getCookies().length > 0)
                || request.getUserPrincipal() != null
                || request.getRemoteUser() != null
                || request.getHeader("X-Sakai-Session") != null
                || Collections.list(request.getHeaders("X-MCP-Flow")).size() > 1
                || Collections.list(request.getHeaders("X-MCP-Flow-End")).size() > 1
                || (request.getHeader("X-MCP-Flow-End") != null
                        && (!"1".equals(request.getHeader("X-MCP-Flow-End"))
                                || request.getHeader("X-MCP-Flow") == null
                                || !"/direct/user/current.json".equals(request.getRequestURI())))) {
            response.sendError(403);
            return;
        }
        // These existing framework DEBUG paths log native session IDs (and
        // MySession TRACE can dump attributes). Never create delegated state
        // under that logging configuration; ordinary requests are untouched.
        for (String category :
                List.of(
                        "org.sakaiproject.util.RequestFilter",
                        "org.sakaiproject.tool.impl.SessionComponent",
                        "org.sakaiproject.tool.impl.MySession")) {
            if (LoggerFactory.getLogger(category).isDebugEnabled()) {
                response.sendError(503);
                return;
            }
        }
        DelegatedJwtVerifier.Identity identity;
        try {
            identity = verifier().verify(headers.get(0).substring(7));
        } catch (DelegatedJwtVerifier.InvalidTokenException e) {
            unauthorized(response);
            return;
        } catch (DelegatedJwtVerifier.VerificationUnavailableException | ServletException e) {
            response.sendError(503);
            return;
        }
        Authentication account;
        try {
            account = authentication.authenticate(new ExternalTrustedEvidence(identity.sakaiEid()));
        } catch (AuthenticationException e) {
            response.sendError(403);
            return;
        }
        if (account == null
                || account.getUid() == null
                || account.getUid().isBlank()
                || !identity.sakaiEid().equals(account.getEid())) {
            response.sendError(403);
            return;
        }

        Map<String, Object> beforeThreads = new HashMap<>();
        Map<String, Object> beforeAttributes = new HashMap<>();
        THREAD_KEYS.forEach(k -> beforeThreads.put(k, threads.get(k)));
        ATTRIBUTES.forEach(k -> beforeAttributes.put(k, request.getAttribute(k)));
        DelegatedConversations.Lease lease = null;
        try {
            sessions.setCurrentToolSession(null);
            try {
                lease =
                        DelegatedConversations.open(
                                configuration,
                                sessions,
                                usage,
                                account,
                                identity,
                                request.getHeader("X-MCP-Flow"),
                                request.getHeader("X-MCP-Flow-End") != null,
                                request.getRemoteAddr(),
                                Clock.systemUTC());
            } catch (DelegatedConversations.Denied denied) {
                response.sendError(denied.status);
                return;
            }
            Session delegated = lease.session;
            sessions.setCurrentSession(delegated);
            request.setAttribute(
                    MARKER,
                    new BoundIdentity(
                            delegated,
                            account.getUid(),
                            account.getEid(),
                            DelegatedRoutes.placement(request, configuration),
                            request.getHeader("X-MCP-Flow") != null));
            DelegatedResponse guardedResponse = new DelegatedResponse(response, delegated.getId());
            try {
                chain.doFilter(new NativeSessionRequest(request, delegated), guardedResponse);
                guardedResponse.finish();
            } catch (IOException | ServletException | RuntimeException e) {
                // Never hand an authenticated context/exception to a container
                // diagnostic page. No handler body was emitted by the buffer.
                if (!response.isCommitted()) {
                    response.reset();
                    response.setStatus(HttpServletResponse.SC_BAD_GATEWAY);
                    response.setHeader("Cache-Control", "no-store");
                }
            }
        } finally {
            try {
                if (lease != null) lease.close();
            } finally {
                beforeThreads.forEach(threads::set);
                sessions.setCurrentSession((Session) beforeThreads.get(CURRENT_SESSION));
                sessions.setCurrentToolSession((ToolSession) beforeThreads.get(CURRENT_TOOL));
                beforeAttributes.forEach(
                        (k, v) -> {
                            if (v == null) request.removeAttribute(k);
                            else request.setAttribute(k, v);
                        });
            }
        }
    }

    private DelegatedJwtVerifier verifier() throws ServletException {
        DelegatedJwtVerifier result = verifier;
        if (result == null)
            synchronized (this) {
                result = verifier;
                if (result == null)
                    try {
                        result =
                                new DelegatedJwtVerifier(
                                        configuration.getString("mcp.integration.issuer"),
                                        configuration.getString("mcp.integration.tenant"),
                                        configuration.getString("mcp.integration.audience"),
                                        configuration.getString("mcp.integration.scope"),
                                        configuration.getString("mcp.integration.jwksUri"));
                        verifier = result;
                    } catch (MalformedURLException | IllegalArgumentException e) {
                        throw new ServletException("Delegated verifier configuration unavailable");
                    }
            }
        return result;
    }

    private static void unauthorized(HttpServletResponse response) throws IOException {
        response.setHeader("WWW-Authenticate", "Bearer");
        response.sendError(401);
    }

    private static final class NativeSessionRequest extends HttpServletRequestWrapper {
        private final Cookie cookie;

        NativeSessionRequest(HttpServletRequest request, Session session) {
            super(request);
            String name = System.getProperty(RequestFilter.SAKAI_COOKIE_PROP, "JSESSIONID");
            String suffix = System.getProperty(RequestFilter.SAKAI_SERVERID, "sakai");
            if (suffix.isEmpty()) suffix = "sakai";
            cookie = new Cookie(name, session.getId() + "." + suffix);
        }

        @Override
        public Cookie[] getCookies() {
            return new Cookie[] {cookie};
        }

        @Override
        public Principal getUserPrincipal() {
            return null;
        } // Don't trigger Direct basic-principal session selection.

        @Override
        public String getRemoteUser() {
            return null;
        }

        @Override
        public String getHeader(String name) {
            if ("Authorization".equalsIgnoreCase(name)) return null;
            if ("Cookie".equalsIgnoreCase(name)) return cookie.getName() + "=" + cookie.getValue();
            return super.getHeader(name);
        }

        @Override
        public Enumeration<String> getHeaders(String name) {
            if ("Authorization".equalsIgnoreCase(name)) return Collections.emptyEnumeration();
            if ("Cookie".equalsIgnoreCase(name))
                return Collections.enumeration(List.of(getHeader(name)));
            return super.getHeaders(name);
        }

        @Override
        public Enumeration<String> getHeaderNames() {
            List<String> names = new ArrayList<>(Collections.list(super.getHeaderNames()));
            names.removeIf(
                    n -> "Authorization".equalsIgnoreCase(n) || "Cookie".equalsIgnoreCase(n));
            names.add("Cookie");
            return Collections.enumeration(names);
        }

        @Override
        public boolean isAsyncSupported() {
            return false;
        }

        @Override
        public AsyncContext startAsync() {
            throw new IllegalStateException("Delegated async dispatch is unsupported");
        }

        @Override
        public AsyncContext startAsync(ServletRequest r, ServletResponse s) {
            return startAsync();
        }
    }
}
