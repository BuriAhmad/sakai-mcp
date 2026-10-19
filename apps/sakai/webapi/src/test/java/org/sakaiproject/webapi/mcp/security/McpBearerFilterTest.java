/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.security;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;

import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.AuthenticationException;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.Authentication;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import javax.servlet.ServletException;

public class McpBearerFilterTest {

    private ServerConfigurationService configuration;
    private AuthenticationManager authenticationManager;
    private SessionManager sessionManager;
    private UsageSessionService usageSessionService;
    private Session previous;
    private Session delegated;
    private McpBearerFilter filter;
    private String token;
    private RSAKey signingKey;
    private Instant now;

    @Before
    public void setup() throws Exception {
        configuration = mock(ServerConfigurationService.class);
        authenticationManager = mock(AuthenticationManager.class);
        sessionManager = mock(SessionManager.class);
        usageSessionService = mock(UsageSessionService.class);
        previous = mock(Session.class);
        delegated = mock(Session.class);
        when(configuration.getBoolean("mcp.integration.enabled", false)).thenReturn(true);
        when(sessionManager.getCurrentSession()).thenReturn(previous, delegated);
        when(sessionManager.startSession()).thenReturn(delegated);
        when(authenticationManager.authenticate(any()))
                .thenReturn(new Authentication("sakai-user", "test-eid"));
        when(usageSessionService.login(
                        anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenReturn(true);

        signingKey = new RSAKeyGenerator(2048).keyID("test-key").generate();
        DefaultJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
        processor.setJWSKeySelector(
                new JWSVerificationKeySelector<>(
                        JWSAlgorithm.RS256,
                        new ImmutableJWKSet<>(new JWKSet(signingKey.toPublicJWK()))));
        now = Instant.now();
        McpJwtVerifier verifier =
                new McpJwtVerifier(
                        "https://issuer.example.test/",
                        "tenant",
                        "api://sakai",
                        "sakai.mcp.access",
                        Clock.fixed(now, ZoneOffset.UTC),
                        processor);
        token = tokenFor("test-eid", "external-object");
        filter =
                new McpBearerFilter(
                        configuration,
                        authenticationManager,
                        sessionManager,
                        usageSessionService,
                        verifier);
    }

    private String tokenFor(String eid, String objectId) throws Exception {
        SignedJWT jwt =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS256).keyID("test-key").build(),
                        new JWTClaimsSet.Builder()
                                .issuer("https://issuer.example.test/")
                                .audience("api://sakai")
                                .claim("tid", "tenant")
                                .claim("oid", objectId)
                                .claim("scp", "sakai.mcp.access")
                                .claim("extn.SakaiEid", List.of(eid))
                                .notBeforeTime(Date.from(now.minusSeconds(10)))
                                .expirationTime(Date.from(now.plusSeconds(300)))
                                .build());
        jwt.sign(new RSASSASigner(signingKey));
        return jwt.serialize();
    }

    private MockHttpServletRequest request() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/mcp/v1/courses");
        request.setSecure(true);
        request.addHeader("Authorization", "Bearer " + token);
        return request;
    }

    @Test
    public void bindsAndDisposesOnlyDelegatedSession() throws Exception {
        MockHttpServletRequest request = request();
        request.addHeader("X-User", "forged-user");
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean called = new AtomicBoolean();
        filter.doFilter(
                request,
                response,
                (req, res) -> {
                    called.set(true);
                    assertEquals("external-object", req.getAttribute("mcp.externalObjectId"));
                });
        assertTrue(called.get());
        verify(sessionManager, times(2)).setCurrentSession(delegated);
        verify(delegated).invalidate();
        verify(sessionManager).setCurrentSession(previous);
        verify(authenticationManager)
                .authenticate(any(org.sakaiproject.user.api.ExternalTrustedEvidence.class));
    }

    @Test
    public void restoresPreviousContextAfterControllerFailure() throws Exception {
        assertThrows(
                ServletException.class,
                () ->
                        filter.doFilter(
                                request(),
                                new MockHttpServletResponse(),
                                (req, res) -> {
                                    throw new ServletException("test failure");
                                }));
        verify(delegated).invalidate();
        verify(sessionManager).setCurrentSession(previous);
    }

    @Test
    public void rejectsCookieOnlyAndMismatchedIdentity() throws Exception {
        MockHttpServletRequest cookieOnly = new MockHttpServletRequest("GET", "/mcp/v1/courses");
        cookieOnly.setSecure(true);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(
                cookieOnly,
                response,
                (req, res) -> {
                    throw new AssertionError();
                });
        assertEquals(401, response.getStatus());

        when(authenticationManager.authenticate(any()))
                .thenReturn(new Authentication("other", "other-eid"));
        response = new MockHttpServletResponse();
        filter.doFilter(
                request(),
                response,
                (req, res) -> {
                    throw new AssertionError();
                });
        assertEquals(403, response.getStatus());
    }

    @Test
    public void disabledRouteIsUnavailable() throws Exception {
        when(configuration.getBoolean("mcp.integration.enabled", false)).thenReturn(false);
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(
                request(),
                response,
                (req, res) -> {
                    throw new AssertionError();
                });
        assertEquals(404, response.getStatus());
    }

    @Test
    public void disabledOrUnknownSakaiAccountIsRejected() throws Exception {
        when(authenticationManager.authenticate(any()))
                .thenThrow(new AuthenticationException("account disabled"));
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(
                request(),
                response,
                (req, res) -> {
                    throw new AssertionError();
                });
        assertEquals(403, response.getStatus());
    }

    @Test
    public void concurrentDelegatedUsersDoNotShareCurrentSession() throws Exception {
        ThreadLocal<Session> current = ThreadLocal.withInitial(() -> previous);
        when(sessionManager.getCurrentSession()).thenAnswer(inv -> current.get());
        org.mockito.Mockito.doAnswer(
                        inv -> {
                            current.set(inv.getArgument(0));
                            return null;
                        })
                .when(sessionManager)
                .setCurrentSession(any(Session.class));
        when(sessionManager.startSession()).thenAnswer(inv -> mock(Session.class));
        when(authenticationManager.authenticate(any()))
                .thenAnswer(
                        inv -> {
                            String eid =
                                    ((org.sakaiproject.user.api.ExternalTrustedEvidence)
                                                    inv.getArgument(0))
                                            .getIdentifier();
                            return new Authentication("sakai-" + eid, eid);
                        });
        when(usageSessionService.login(
                        anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenAnswer(
                        inv -> {
                            Session own = current.get();
                            when(own.getUserId()).thenReturn(inv.getArgument(0));
                            return true;
                        });
        CountDownLatch bothInController = new CountDownLatch(2);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<String> first =
                    pool.submit(
                            () ->
                                    concurrentRequest(
                                            "first-eid",
                                            "first-object",
                                            current,
                                            bothInController));
            Future<String> second =
                    pool.submit(
                            () ->
                                    concurrentRequest(
                                            "second-eid",
                                            "second-object",
                                            current,
                                            bothInController));
            assertEquals("sakai-first-eid", first.get(10, TimeUnit.SECONDS));
            assertEquals("sakai-second-eid", second.get(10, TimeUnit.SECONDS));
        } finally {
            pool.shutdownNow();
        }
    }

    private String concurrentRequest(
            String eid,
            String objectId,
            ThreadLocal<Session> current,
            CountDownLatch bothInController)
            throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/mcp/v1/courses");
        request.setSecure(true);
        request.addHeader("Authorization", "Bearer " + tokenFor(eid, objectId));
        AtomicReference<String> observed = new AtomicReference<>();
        filter.doFilter(
                request,
                new MockHttpServletResponse(),
                (req, res) -> {
                    bothInController.countDown();
                    try {
                        assertTrue(bothInController.await(5, TimeUnit.SECONDS));
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new ServletException(e);
                    }
                    assertEquals(objectId, req.getAttribute("mcp.externalObjectId"));
                    observed.set(current.get().getUserId());
                });
        assertEquals(previous, current.get());
        return observed.get();
    }
}
