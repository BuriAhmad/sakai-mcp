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

/**
 * Authenticates bearer requests and selects their Sakai session before RequestFilter runs.
 * Ordinary browser requests continue through Sakai's normal authentication.
 */
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

    /** Only an authenticated custom MCP artifact request uses synchronous streaming. */
    public static boolean isDelegatedArtifactRequest(HttpServletRequest request) {
        return request.getAttribute(MARKER) instanceof BoundIdentity
                && DelegatedRoutes.isCustomMcpArtifactRequest(request);
    }

    @Override
    public void doFilter(
            ServletRequest servletRequest, ServletResponse servletResponse, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) servletRequest;
        HttpServletResponse response = (HttpServletResponse) servletResponse;
        // A native tool forward may revisit this filter after we have already authenticated it.
        Object sessionBinding = request.getAttribute(MARKER);
        if (sessionBinding instanceof BoundIdentity bound) {
            if (!allowsInternalDispatch(request, bound)) {
                response.sendError(403);
                return;
            }
            chain.doFilter(servletRequest, servletResponse);
            return;
        }
        if (sessionBinding != null) {
            response.sendError(403);
            return;
        }
        // Custom MCP endpoints always require bearer authentication. Ordinary browser requests
        // without a bearer header continue unchanged, unless they try to use the flow protocol.
        boolean customMcpEndpoint = DelegatedRoutes.isCustomMcpEndpoint(request);
        List<String> authorizationHeaders = Collections.list(request.getHeaders("Authorization"));
        boolean hasBearerHeader =
                authorizationHeaders.stream()
                        .anyMatch(header -> header.regionMatches(true, 0, "Bearer", 0, 6));
        if (!hasBearerHeader) {
            if (customMcpEndpoint && !configuration.getBoolean("mcp.integration.enabled", false)) {
                response.setHeader("Cache-Control", "no-store");
                response.sendError(404);
                return;
            }
            if (customMcpEndpoint
                    || request.getHeader("X-MCP-Flow") != null
                    || request.getHeader("X-MCP-Flow-End") != null) {
                DelegatedBearerAuthentication.unauthorized(request, response);
                return;
            }
            chain.doFilter(servletRequest, servletResponse);
            return;
        }
        try {
            if (customMcpEndpoint && !configuration.getBoolean("mcp.integration.enabled", false)) {
                response.setHeader("Cache-Control", "no-store");
                response.sendError(404);
                return;
            }
            request.setCharacterEncoding("UTF-8");
            response.setHeader("Cache-Control", "no-store");
            if (authorizationHeaders.size() != 1
                    || authorizationHeaders.get(0).length() > MAX_BEARER_HEADER_LENGTH) {
                DelegatedBearerAuthentication.unauthorized(request, response);
                return;
            }
            // A mapped filter can see more routes than it accepts. These checks control where
            // bearer credentials may be used; each endpoint still checks Sakai permissions.
            if (!(customMcpEndpoint ? request.isSecure() : RequestFilter.isSecure(request))
                    || !(DelegatedRoutes.allowsCustomMcpEndpoint(request)
                            || DelegatedRoutes.allowsExistingHttpEndpoint(request)
                            || DelegatedRoutes.allowsToolSessionRequest(request, configuration))) {
                response.sendError(403);
                return;
            }
            if (!customMcpEndpoint
                    && !configuration.getBoolean("mcp.integration.existingHttp.enabled", false)) {
                response.sendError(404);
                return;
            }
            if (hasMixedCredentials(request) || hasInvalidFlowHeaders(request, customMcpEndpoint)) {
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
            authenticateBearerAndContinue(request, response, chain);
        } finally {
            // Also cover policy/configuration failures before the standard Spring chain starts.
            SecurityContextHolder.clearContext();
        }
    }

    /** Spring verifies the JWT before this callback can resolve a Sakai user. */
    private void authenticateBearerAndContinue(
            HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        DelegatedBearerAuthentication springAuthentication;
        try {
            springAuthentication = bearerAuthentication();
        } catch (IllegalArgumentException e) {
            DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.CONFIGURATION);
            response.sendError(503);
            return;
        }
        springAuthentication.doFilter(
                request,
                response,
                (authenticatedRequest, authenticatedResponse) -> {
                    var authenticatedPrincipal =
                            SecurityContextHolder.getContext().getAuthentication();
                    if (!(authenticatedPrincipal instanceof JwtAuthenticationToken jwtAuthentication)
                            || !jwtAuthentication.isAuthenticated()) {
                        DelegatedBearerAuthentication.unauthorized(
                                (HttpServletRequest) authenticatedRequest,
                                (HttpServletResponse) authenticatedResponse);
                        return;
                    }
                    Object identityClaimValue =
                            jwtAuthentication.getToken().getClaims().get(springAuthentication.identityClaim);
                    if (!(identityClaimValue instanceof List<?> identityValues)
                            || identityValues.size() != 1
                            || !(identityValues.get(0) instanceof String sakaiEid)) {
                        ((HttpServletResponse) authenticatedResponse).sendError(403);
                        return;
                    }
                    ExternalIdentity identity =
                            new ExternalIdentity(
                                    sakaiEid,
                                    jwtAuthentication.getToken().getClaimAsString("tid"),
                                    jwtAuthentication.getToken().getClaimAsString("oid"));
                    executeWithDelegatedSession(
                            (HttpServletRequest) authenticatedRequest,
                            (HttpServletResponse) authenticatedResponse,
                            chain,
                            identity);
                });
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

    private static boolean hasInvalidFlowHeaders(
            HttpServletRequest request, boolean customMcpEndpoint) {
        return (customMcpEndpoint
                        && (request.getHeader("X-MCP-Flow") != null
                                || request.getHeader("X-MCP-Flow-End") != null))
                || Collections.list(request.getHeaders("X-MCP-Flow")).size() > 1
                || Collections.list(request.getHeaders("X-MCP-Flow-End")).size() > 1
                || (request.getHeader("X-MCP-Flow-End") != null
                        && (!"1".equals(request.getHeader("X-MCP-Flow-End"))
                                || request.getHeader("X-MCP-Flow") == null
                                || !"/direct/user/current.json".equals(request.getRequestURI())));
    }

    /** Runs the remaining filters and endpoint with the verified user's native Sakai session. */
    private void executeWithDelegatedSession(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain chain,
            ExternalIdentity identity)
            throws IOException, ServletException {
        // JWT verification established the external identity. Sakai now resolves its own account.
        Authentication sakaiAccount;
        try {
            sakaiAccount = authentication.authenticate(new ExternalTrustedEvidence(identity.sakaiEid()));
        } catch (AuthenticationException e) {
            response.sendError(403);
            return;
        }
        if (sakaiAccount == null
                || sakaiAccount.getUid() == null
                || sakaiAccount.getUid().isBlank()
                || !identity.sakaiEid().equals(sakaiAccount.getEid())) {
            response.sendError(403);
            return;
        }

        // Save the caller's context so nested requests can restore it, including after failures.
        Map<String, Object> previousThreadValues = new HashMap<>();
        Map<String, Object> previousRequestAttributes = new HashMap<>();
        THREAD_KEYS.forEach(k -> previousThreadValues.put(k, threads.get(k)));
        ATTRIBUTES.forEach(k -> previousRequestAttributes.put(k, request.getAttribute(k)));
        DelegatedConversations.Lease sessionLease = null;
        DelegatedResponse protectedResponse = null;
        try {
            sessions.setCurrentToolSession(null);
            try {
                // With no flow header, this creates a session owned by this request only.
                sessionLease =
                        DelegatedConversations.open(
                                configuration,
                                sessions,
                                usage,
                                sakaiAccount,
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
            Session delegatedSession = sessionLease.session;
            sessions.setCurrentSession(delegatedSession);
            request.setAttribute(
                    MARKER,
                    new BoundIdentity(
                            delegatedSession,
                            sakaiAccount.getUid(),
                            sakaiAccount.getEid(),
                            DelegatedRoutes.placement(request, configuration),
                            request.getHeader("X-MCP-Flow") != null));
            request.setAttribute("mcp.externalTenantId", identity.tenantId());
            request.setAttribute("mcp.externalObjectId", identity.objectId());
            // Keep output private until session cleanup succeeds. The wrapper also blocks cookies
            // and native session IDs from escaping to the bearer client.
            protectedResponse =
                    new DelegatedResponse(
                            response,
                            delegatedSession.getId(),
                            DelegatedRoutes.responseLimit(request));
            try {
                // RequestFilter captures this selected session; the binder checks it afterward.
                chain.doFilter(
                        new NativeSessionRequest(request, delegatedSession), protectedResponse);
            } catch (IOException | ServletException | RuntimeException e) {
                // No authenticated diagnostic or partial body reaches the container.
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.HANDLER);
                protectedResponse = null;
                badGateway(response);
            }
        } finally {
            try {
                if (sessionLease != null) {
                    // Ordinary request sessions are invalidated here, even if the endpoint failed.
                    sessionLease.close();
                }
            } catch (RuntimeException failure) {
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.SESSION_CLEANUP);
                protectedResponse = null;
                badGateway(response);
            } finally {
                try {
                    restorePreviousContext(request, previousThreadValues, previousRequestAttributes);
                } catch (RuntimeException failure) {
                    DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.CONTEXT_RESTORE);
                    protectedResponse = null;
                    badGateway(response);
                }
            }
        }
        if (protectedResponse != null) {
            try {
                // Send the buffered response after cleanup and restoration succeed.
                protectedResponse.finish();
            } catch (IOException | RuntimeException failure) {
                DelegatedDiagnostics.failure(DelegatedDiagnostics.Stage.RESPONSE_COMPLETION);
                badGateway(response);
            }
        }
    }

    private void restorePreviousContext(
            HttpServletRequest request,
            Map<String, Object> previousThreadValues,
            Map<String, Object> previousRequestAttributes) {
        List<Runnable> actions = new ArrayList<>();
        previousThreadValues.forEach((key, value) -> actions.add(() -> threads.set(key, value)));
        actions.add(
                () -> sessions.setCurrentSession((Session) previousThreadValues.get(CURRENT_SESSION)));
        actions.add(
                () ->
                        sessions.setCurrentToolSession(
                                (ToolSession) previousThreadValues.get(CURRENT_TOOL)));
        previousRequestAttributes.forEach(
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
