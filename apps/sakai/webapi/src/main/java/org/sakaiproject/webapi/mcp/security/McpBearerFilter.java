/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.security;

import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.Authentication;
import org.sakaiproject.user.api.AuthenticationException;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.ExternalTrustedEvidence;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.MalformedURLException;

import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/** Only the /mcp/v1/* servlet route accepts delegated bearer credentials. */
@Component("mcpBearerFilter")
public class McpBearerFilter implements Filter {

    private final ServerConfigurationService configuration;
    private final AuthenticationManager authenticationManager;
    private final SessionManager sessionManager;
    private final UsageSessionService usageSessionService;
    private volatile McpJwtVerifier verifier;

    @Autowired
    public McpBearerFilter(
            ServerConfigurationService configuration,
            AuthenticationManager authenticationManager,
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessionManager,
            UsageSessionService usageSessionService) {
        this.configuration = configuration;
        this.authenticationManager = authenticationManager;
        this.sessionManager = sessionManager;
        this.usageSessionService = usageSessionService;
    }

    McpBearerFilter(
            ServerConfigurationService configuration,
            AuthenticationManager authenticationManager,
            SessionManager sessionManager,
            UsageSessionService usageSessionService,
            McpJwtVerifier verifier) {
        this(configuration, authenticationManager, sessionManager, usageSessionService);
        this.verifier = verifier;
    }

    @Override
    public void doFilter(ServletRequest rawRequest, ServletResponse rawResponse, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) rawRequest;
        HttpServletResponse response = (HttpServletResponse) rawResponse;
        response.setHeader("Cache-Control", "no-store");
        if (!configuration.getBoolean("mcp.integration.enabled", false)) {
            response.sendError(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        if (!request.isSecure()) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN);
            return;
        }
        String authorization = request.getHeader("Authorization");
        if (authorization == null
                || !authorization.startsWith("Bearer ")
                || authorization.indexOf(' ', 7) >= 0) {
            unauthorized(response);
            return;
        }
        McpJwtVerifier.Identity identity;
        try {
            identity = verifier().verify(authorization.substring(7));
        } catch (McpJwtVerifier.InvalidTokenException e) {
            unauthorized(response);
            return;
        } catch (McpJwtVerifier.VerificationUnavailableException | ServletException e) {
            response.sendError(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            return;
        }
        Authentication authentication;
        try {
            // Sakai 25.2 resolves AID/EID and rejects disabled accounts here.
            authentication =
                    authenticationManager.authenticate(
                            new ExternalTrustedEvidence(identity.sakaiEid()));
        } catch (AuthenticationException e) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN);
            return;
        }
        if (authentication == null
                || authentication.getUid() == null
                || authentication.getUid().isBlank()
                || !identity.sakaiEid().equals(authentication.getEid())) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN);
            return;
        }

        Session previous = sessionManager.getCurrentSession();
        Session delegated = sessionManager.startSession();
        if (delegated == null) {
            response.sendError(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            return;
        }
        try {
            sessionManager.setCurrentSession(delegated);
            boolean loggedIn =
                    usageSessionService.login(
                            authentication.getUid(),
                            authentication.getEid(),
                            request.getRemoteAddr(),
                            "/api/mcp/v1",
                            UsageSessionService.EVENT_LOGIN_WS);
            if (!loggedIn) {
                response.sendError(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
                return;
            }
            request.setAttribute("mcp.externalTenantId", identity.tenantId());
            request.setAttribute("mcp.externalObjectId", identity.objectId());
            chain.doFilter(request, response);
        } finally {
            // Invalidate only the new session; never log out a browser session
            // that RequestFilter may have bound for this request.
            try {
                sessionManager.setCurrentSession(delegated);
                delegated.invalidate();
            } finally {
                sessionManager.setCurrentSession(previous);
            }
        }
    }

    private McpJwtVerifier verifier() throws ServletException {
        McpJwtVerifier result = verifier;
        if (result == null) {
            synchronized (this) {
                result = verifier;
                if (result == null) {
                    try {
                        result =
                                new McpJwtVerifier(
                                        configuration.getString("mcp.integration.issuer"),
                                        configuration.getString("mcp.integration.tenant"),
                                        configuration.getString("mcp.integration.audience"),
                                        configuration.getString("mcp.integration.scope"),
                                        configuration.getString("mcp.integration.jwksUri"));
                    } catch (MalformedURLException | IllegalArgumentException e) {
                        throw new ServletException("MCP token verifier is not configured", e);
                    }
                    verifier = result;
                }
            }
        }
        return result;
    }

    private static void unauthorized(HttpServletResponse response) throws IOException {
        response.setHeader("WWW-Authenticate", "Bearer");
        response.sendError(HttpServletResponse.SC_UNAUTHORIZED);
    }
}
