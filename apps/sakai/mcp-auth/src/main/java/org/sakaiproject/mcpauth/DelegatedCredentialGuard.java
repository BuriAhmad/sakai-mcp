/*
 * Copyright (c) 2026 The Apereo Foundation
 *
 * Licensed under the Educational Community License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *             http://opensource.org/licenses/ecl2
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
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
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.io.IOException;
import java.security.Principal;
import java.time.Clock;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

import javax.servlet.AsyncContext;
import javax.servlet.DispatcherType;
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletRequestWrapper;
import javax.servlet.http.HttpServletResponse;

/** Validates credentials before native wrappers capture an isolated session. */
public final class DelegatedCredentialGuard implements Filter {
    static final String MARKER = DelegatedCredentialGuard.class.getName() + ".identity";
    private static final int MAX_BEARER_HEADER_LENGTH = 16_391;
    private static final Set<String> INTERNAL_TOOLS =
            Set.of(
                    "sakai.assignment.grades",
                    "sakai.assignment",
                    "sakai.announcements",
                    "sakai.gradebookng",
                    "sakai.filepicker");
    private static final Set<String> CREDENTIAL_PARAMETERS =
            Set.of(
                    "sessionid",
                    "sakai.session",
                    "jsessionid",
                    "oauth_token",
                    "oauth_signature",
                    "oauth_consumer_key",
                    "authorization",
                    "access_token");
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
                    RequestFilter.ATTR_UPLOADS_DONE,
                    "mcp.externalTenantId",
                    "mcp.externalObjectId");
    private ServerConfigurationService configuration;
    private AuthenticationManager authentication;
    private SessionManager sessions;
    private UsageSessionService usage;
    private ThreadLocalManager threads;
    private volatile DelegatedBearerAuthentication bearerAuthentication;

    public DelegatedCredentialGuard() {}

    DelegatedCredentialGuard(
            ServerConfigurationService configuration,
            AuthenticationManager authentication,
            SessionManager sessions,
            UsageSessionService usage,
            ThreadLocalManager threads,
            JwtDecoder decoder) {
        this.configuration = configuration;
        this.authentication = authentication;
        this.sessions = sessions;
        this.usage = usage;
        this.threads = threads;
        this.bearerAuthentication =
                new DelegatedBearerAuthentication(
                        decoder, DelegatedBearerAuthentication.identityClaim(configuration));
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

    record ExternalIdentity(String sakaiEid, String tenantId, String objectId) {}

    /** Only a server-created binding can request synchronous legacy artifact output. */
    public static boolean isDelegatedArtifactRequest(HttpServletRequest request) {
        return request.getAttribute(MARKER) instanceof BoundIdentity
                && DelegatedRoutes.legacyArtifact(request);
    }

    @Override
    public void doFilter(ServletRequest raw, ServletResponse output, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) raw;
        HttpServletResponse response = (HttpServletResponse) output;
        Object internal = request.getAttribute(MARKER);
        if (internal instanceof BoundIdentity bound) {
            if (!allowsInternalDispatch(request, bound)) {
                response.sendError(403);
                return;
            }
            chain.doFilter(raw, output);
            return;
        }
        if (internal != null) {
            response.sendError(403);
            return;
        }
        boolean legacy = DelegatedRoutes.legacy(request);
        List<String> headers = Collections.list(request.getHeaders("Authorization"));
        boolean bearer = headers.stream().anyMatch(h -> h.regionMatches(true, 0, "Bearer", 0, 6));
        if (!bearer) {
            if (legacy && !configuration.getBoolean("mcp.integration.enabled", false)) {
                response.setHeader("Cache-Control", "no-store");
                response.sendError(404);
                return;
            }
            if (legacy
                    || request.getHeader("X-MCP-Flow") != null
                    || request.getHeader("X-MCP-Flow-End") != null) {
                DelegatedBearerAuthentication.unauthorized(request, response);
                return;
            }
            chain.doFilter(raw, output);
            return;
        }
        try {
            if (legacy && !configuration.getBoolean("mcp.integration.enabled", false)) {
                response.setHeader("Cache-Control", "no-store");
                response.sendError(404);
                return;
            }
            request.setCharacterEncoding("UTF-8");
            response.setHeader("Cache-Control", "no-store");
            if (headers.size() != 1 || headers.get(0).length() > MAX_BEARER_HEADER_LENGTH) {
                DelegatedBearerAuthentication.unauthorized(request, response);
                return;
            }
            if (!(legacy ? request.isSecure() : RequestFilter.isSecure(request))
                    || !(DelegatedRoutes.legacyAllows(request)
                            || DelegatedRoutes.allows(request)
                            || DelegatedRoutes.conversationAllows(request, configuration))) {
                response.sendError(403);
                return;
            }
            if (!legacy
                    && !configuration.getBoolean("mcp.integration.existingHttp.enabled", false)) {
                response.sendError(404);
                return;
            }
            if (hasMixedCredentials(request) || hasInvalidFlowHeaders(request, legacy)) {
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
                    DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.LOGGING_POLICY);
                    response.sendError(503);
                    return;
                }
            }
            DelegatedBearerAuthentication spring;
            try {
                spring = bearerAuthentication();
            } catch (IllegalArgumentException e) {
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.CONFIGURATION);
                response.sendError(503);
                return;
            }
            spring.doFilter(
                    request,
                    response,
                    (r, out) -> {
                        var principal = SecurityContextHolder.getContext().getAuthentication();
                        if (!(principal instanceof JwtAuthenticationToken jwt)
                                || !jwt.isAuthenticated()) {
                            DelegatedBearerAuthentication.unauthorized(
                                    (HttpServletRequest) r, (HttpServletResponse) out);
                            return;
                        }
                        Object claim = jwt.getToken().getClaims().get(spring.identityClaim);
                        if (!(claim instanceof List<?> values)
                                || values.size() != 1
                                || !(values.get(0) instanceof String eid)) {
                            ((HttpServletResponse) out).sendError(403);
                            return;
                        }
                        ExternalIdentity identity =
                                new ExternalIdentity(
                                        eid,
                                        jwt.getToken().getClaimAsString("tid"),
                                        jwt.getToken().getClaimAsString("oid"));
                        bind((HttpServletRequest) r, (HttpServletResponse) out, chain, identity);
                    });
        } finally {
            // Also cover policy/configuration failures before the standard Spring chain starts.
            SecurityContextHolder.clearContext();
        }
    }

    private boolean allowsInternalDispatch(HttpServletRequest request, BoundIdentity bound) {
        ToolManager tools = ComponentManager.get(ToolManager.class);
        return bound.conversation()
                && (request.getDispatcherType() == DispatcherType.REQUEST
                        || request.getDispatcherType() == DispatcherType.FORWARD
                        || request.getDispatcherType() == DispatcherType.INCLUDE)
                && sessions.getCurrentSession() == bound.session()
                && tools != null
                && tools.getCurrentPlacement() != null
                && Objects.equals(bound.placement(), tools.getCurrentPlacement().getId())
                && tools.getCurrentTool() != null
                && INTERNAL_TOOLS.contains(tools.getCurrentTool().getId());
    }

    private static boolean hasMixedCredentials(HttpServletRequest request) {
        return request.getHeader("Cookie") != null
                || (request.getCookies() != null && request.getCookies().length > 0)
                || request.getUserPrincipal() != null
                || request.getRemoteUser() != null
                || request.getHeader("X-Sakai-Session") != null
                || request.getParameterMap().keySet().stream()
                        .anyMatch(k -> CREDENTIAL_PARAMETERS.contains(k.toLowerCase(Locale.ROOT)));
    }

    private static boolean hasInvalidFlowHeaders(HttpServletRequest request, boolean legacy) {
        return (legacy
                        && (request.getHeader("X-MCP-Flow") != null
                                || request.getHeader("X-MCP-Flow-End") != null))
                || Collections.list(request.getHeaders("X-MCP-Flow")).size() > 1
                || Collections.list(request.getHeaders("X-MCP-Flow-End")).size() > 1
                || (request.getHeader("X-MCP-Flow-End") != null
                        && (!"1".equals(request.getHeader("X-MCP-Flow-End"))
                                || request.getHeader("X-MCP-Flow") == null
                                || !"/direct/user/current.json".equals(request.getRequestURI())));
    }

    private void bind(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain chain,
            ExternalIdentity identity)
            throws IOException, ServletException {
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
        DelegatedResponse guardedResponse = null;
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
                if (denied.status == 503) {
                    DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.NATIVE_SESSION);
                }
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
            request.setAttribute("mcp.externalTenantId", identity.tenantId());
            request.setAttribute("mcp.externalObjectId", identity.objectId());
            guardedResponse =
                    new DelegatedResponse(
                            response, delegated.getId(), DelegatedRoutes.responseLimit(request));
            try {
                chain.doFilter(new NativeSessionRequest(request, delegated), guardedResponse);
            } catch (IOException | ServletException | RuntimeException e) {
                // No authenticated diagnostic or partial body reaches the container.
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.HANDLER);
                guardedResponse = null;
                badGateway(response);
            }
        } finally {
            try {
                if (lease != null) {
                    lease.close();
                }
            } catch (RuntimeException failure) {
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.SESSION_CLEANUP);
                guardedResponse = null;
                badGateway(response);
            } finally {
                try {
                    restore(request, beforeThreads, beforeAttributes);
                } catch (RuntimeException failure) {
                    DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.CONTEXT_RESTORE);
                    guardedResponse = null;
                    badGateway(response);
                }
            }
        }
        if (guardedResponse != null) {
            try {
                // Emit only once owned session cleanup and native restoration have completed.
                guardedResponse.finish();
            } catch (IOException | RuntimeException failure) {
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.RESPONSE_COMPLETION);
                badGateway(response);
            }
        }
    }

    private void restore(
            HttpServletRequest request,
            Map<String, Object> beforeThreads,
            Map<String, Object> beforeAttributes) {
        List<Runnable> actions = new ArrayList<>();
        beforeThreads.forEach((key, value) -> actions.add(() -> threads.set(key, value)));
        actions.add(() -> sessions.setCurrentSession((Session) beforeThreads.get(CURRENT_SESSION)));
        actions.add(
                () ->
                        sessions.setCurrentToolSession(
                                (ToolSession) beforeThreads.get(CURRENT_TOOL)));
        beforeAttributes.forEach(
                (key, value) ->
                        actions.add(
                                () -> {
                                    if (value == null) {
                                        request.removeAttribute(key);
                                    } else {
                                        request.setAttribute(key, value);
                                    }
                                }));
        RuntimeException failed = null;
        for (Runnable action : actions) {
            try {
                action.run();
            } catch (RuntimeException failure) {
                failed = failure;
            }
        }
        if (failed != null) {
            throw failed;
        }
    }

    private static void badGateway(HttpServletResponse response) {
        if (!response.isCommitted()) {
            response.reset();
            response.setStatus(HttpServletResponse.SC_BAD_GATEWAY);
            response.setHeader("Cache-Control", "no-store");
        }
    }

    private DelegatedBearerAuthentication bearerAuthentication() {
        DelegatedBearerAuthentication result = bearerAuthentication;
        if (result == null) {
            synchronized (this) {
                result = bearerAuthentication;
                if (result == null) {
                    result = new DelegatedBearerAuthentication(configuration);
                    bearerAuthentication = result;
                }
            }
        }
        return result;
    }

    private static final class NativeSessionRequest extends HttpServletRequestWrapper {
        private final Cookie cookie;

        NativeSessionRequest(HttpServletRequest request, Session session) {
            super(request);
            String name = System.getProperty(RequestFilter.SAKAI_COOKIE_PROP, "JSESSIONID");
            String suffix = System.getProperty(RequestFilter.SAKAI_SERVERID, "sakai");
            if (suffix.isEmpty()) {
                suffix = "sakai";
            }
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
            if ("Authorization".equalsIgnoreCase(name)) {
                return null;
            }
            if ("Cookie".equalsIgnoreCase(name)) {
                return cookie.getName() + "=" + cookie.getValue();
            }
            return super.getHeader(name);
        }

        @Override
        public Enumeration<String> getHeaders(String name) {
            if ("Authorization".equalsIgnoreCase(name)) {
                return Collections.emptyEnumeration();
            }
            if ("Cookie".equalsIgnoreCase(name)) {
                return Collections.enumeration(List.of(getHeader(name)));
            }
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
