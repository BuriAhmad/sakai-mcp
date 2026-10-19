/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import org.junit.Before;
import org.junit.Test;
import org.mockito.MockedStatic;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.Authentication;
import org.sakaiproject.util.RequestFilter;
import org.springframework.mock.web.*;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

import javax.servlet.*;
import javax.servlet.http.*;

/** Actual upstream RequestFilter chain; no custom test business endpoint. */
public class DelegatedChainTest {
    private ServerConfigurationService configuration;
    private SessionManager sessions;
    private ThreadLocalManager threads;
    private AuthenticationManager authentication;
    private UsageSessionService usage;
    private DelegatedJwtVerifier verifier;
    private DelegatedCredentialGuard guard;
    private DelegatedSessionFilter binder;
    private final ThreadLocal<Map<String, Object>> state = ThreadLocal.withInitial(HashMap::new);
    private final Map<String, Session> registry = new ConcurrentHashMap<>();
    private final AtomicInteger sequence = new AtomicInteger();
    private static final String SESSION = "org.sakaiproject.api.kernel.session.current";
    private static final String TOOL = SESSION + ".tool";

    @Before
    public void setup() throws Exception {
        configuration = mock(ServerConfigurationService.class);
        when(configuration.getBoolean(anyString(), anyBoolean())).thenAnswer(i -> i.getArgument(1));
        when(configuration.getBoolean("mcp.integration.existingHttp.enabled", false))
                .thenReturn(true);
        when(configuration.getString(anyString(), anyString())).thenAnswer(i -> i.getArgument(1));
        sessions = mock(SessionManager.class);
        threads = mock(ThreadLocalManager.class);
        when(threads.get(anyString())).thenAnswer(i -> state.get().get(i.getArgument(0)));
        doAnswer(
                        i -> {
                            String k = i.getArgument(0);
                            Object v = i.getArgument(1);
                            if (v == null) state.get().remove(k);
                            else state.get().put(k, v);
                            return null;
                        })
                .when(threads)
                .set(anyString(), any());
        doAnswer(
                        i -> {
                            state.get().clear();
                            return null;
                        })
                .when(threads)
                .clear();
        when(sessions.getCurrentSession()).thenAnswer(i -> state.get().get(SESSION));
        when(sessions.getCurrentToolSession()).thenAnswer(i -> state.get().get(TOOL));
        doAnswer(
                        i -> {
                            threads.set(SESSION, i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentSession(any());
        doAnswer(
                        i -> {
                            threads.set(TOOL, i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentToolSession(any());
        when(sessions.startSession()).thenAnswer(i -> newSession());
        when(sessions.startSession(anyString())).thenAnswer(i -> newSession(i.getArgument(0)));
        when(sessions.getSessions()).thenAnswer(i -> new ArrayList<>(registry.values()));
        when(sessions.getSession(anyString())).thenAnswer(i -> registry.get(i.getArgument(0)));
        authentication = mock(AuthenticationManager.class);
        when(authentication.authenticate(any())).thenReturn(new Authentication("uid-a", "eid-a"));
        usage = mock(UsageSessionService.class);
        when(usage.login(anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenAnswer(
                        i -> {
                            Session s = sessions.getCurrentSession();
                            s.setUserId(i.getArgument(0));
                            s.setUserEid(i.getArgument(1));
                            return true;
                        });
        verifier = mock(DelegatedJwtVerifier.class);
        when(verifier.verify("token-a"))
                .thenReturn(new DelegatedJwtVerifier.Identity("eid-a", "tenant", "oid-a"));
        guard =
                new DelegatedCredentialGuard(
                        configuration, authentication, sessions, usage, threads, verifier);
        binder = new DelegatedSessionFilter(sessions, threads);
    }

    private Session newSession() {
        return newSession("synthetic-" + sequence.incrementAndGet());
    }

    private Session newSession(String id) {
        Session s = mock(Session.class);
        Map<String, Object> attrs = new HashMap<>();
        AtomicReference<String> uid = new AtomicReference<>(), eid = new AtomicReference<>();
        when(s.getId()).thenReturn(id);
        when(s.getUserId()).thenAnswer(i -> uid.get());
        when(s.getUserEid()).thenAnswer(i -> eid.get());
        doAnswer(
                        i -> {
                            uid.set(i.getArgument(0));
                            return null;
                        })
                .when(s)
                .setUserId(anyString());
        doAnswer(
                        i -> {
                            eid.set(i.getArgument(0));
                            return null;
                        })
                .when(s)
                .setUserEid(anyString());
        when(s.getAttribute(anyString())).thenAnswer(i -> attrs.get(i.getArgument(0)));
        doAnswer(
                        i -> {
                            attrs.put(i.getArgument(0), i.getArgument(1));
                            return null;
                        })
                .when(s)
                .setAttribute(anyString(), any());
        doAnswer(
                        i -> {
                            registry.remove(id);
                            return null;
                        })
                .when(s)
                .invalidate();
        ContextSession context =
                mock(ContextSession.class, withSettings().extraInterfaces(HttpSession.class));
        when(s.getContextSession(anyString())).thenReturn(context);
        registry.put(id, s);
        return s;
    }

    private RequestFilter nativeFilter(String context) throws Exception {
        try (MockedStatic<ComponentManager> components = mockStatic(ComponentManager.class)) {
            components.when(() -> ComponentManager.get(SessionManager.class)).thenReturn(sessions);
            components
                    .when(() -> ComponentManager.get(ThreadLocalManager.class))
                    .thenReturn(threads);
            components
                    .when(() -> ComponentManager.get(ServerConfigurationService.class))
                    .thenReturn(configuration);
            RequestFilter filter = new RequestFilter();
            MockServletContext servlet = new MockServletContext();
            servlet.setContextPath(context);
            MockFilterConfig config = new MockFilterConfig(servlet, "sakai.request");
            config.addInitParameter("upload.enabled", "false");
            if (context.equals("/direct")) config.addInitParameter("sakai.session.auth", "basic");
            filter.init(config);
            return filter;
        }
    }

    private MockHttpServletRequest request(String path) {
        MockHttpServletRequest r = new MockHttpServletRequest("GET", path);
        r.setSecure(true);
        r.setScheme("https");
        r.setServerPort(443);
        r.addHeader("Authorization", "Bearer token-a");
        r.setContextPath(path.startsWith("/api/") ? "/api" : "/direct");
        r.setServletPath(path.substring(r.getContextPath().length()));
        return r;
    }

    @Test
    public void actualNativeWrapperCapturesDelegatedSessionAndSuppressesCredentials()
            throws Exception {
        for (String path :
                List.of(
                        "/api/users/me/sites",
                        "/api/sites/course-a/grades",
                        "/api/sites/course-a/grading/item-data",
                        "/direct/user/current.json",
                        "/direct/site/course-a.json",
                        "/direct/assignment/item/assignment-a.json",
                        "/direct/site/course-a/userPerms.json",
                        "/direct/site/course-a/pages.json",
                        "/direct/announcement/site/course-a.json")) {
            Session outer = newSession();
            outer.setUserId("browser");
            outer.setUserEid("browser-eid");
            sessions.setCurrentSession(outer);
            ToolSession prior = mock(ToolSession.class);
            sessions.setCurrentToolSession(prior);
            RequestFilter nativeFilter =
                    nativeFilter(path.startsWith("/api/") ? "/api" : "/direct");
            MockHttpServletResponse response = new MockHttpServletResponse();
            MockHttpServletRequest request = request(path);
            AtomicBoolean reached = new AtomicBoolean();
            guard.doFilter(
                    request,
                    response,
                    (r, s) ->
                            nativeFilter.doFilter(
                                    r,
                                    s,
                                    (nr, ns) ->
                                            binder.doFilter(
                                                    nr,
                                                    ns,
                                                    (finalRequest, finalResponse) -> {
                                                        HttpServletRequest h =
                                                                (HttpServletRequest) finalRequest;
                                                        Session delegated =
                                                                sessions.getCurrentSession();
                                                        reached.set(true);
                                                        assertNotSame(outer, delegated);
                                                        assertEquals(
                                                                "uid-a", delegated.getUserId());
                                                        assertSame(
                                                                delegated,
                                                                h.getAttribute(
                                                                        RequestFilter
                                                                                .ATTR_SESSION));
                                                        assertEquals("eid-a", h.getRemoteUser());
                                                        assertEquals(
                                                                "uid-a",
                                                                h.getUserPrincipal().getName());
                                                        assertNotNull(h.getSession(false));
                                                        assertSame(
                                                                h,
                                                                threads.get(
                                                                        RequestFilter
                                                                                .CURRENT_HTTP_REQUEST));
                                                        assertNull(h.getHeader("Authorization"));
                                                        HttpServletResponse out =
                                                                (HttpServletResponse) finalResponse;
                                                        out.addCookie(
                                                                new Cookie(
                                                                        "JSESSIONID", "private"));
                                                        out.setIntHeader("Cache-Control", 100);
                                                        out.addDateHeader("Cache-Control", 100);
                                                        out.setHeader("X-Sakai-Session", "private");
                                                        out.addHeader(
                                                                "set-cookie", "private=value");
                                                        out.setHeader(
                                                                "Content-Type", "application/json");
                                                        assertThrows(
                                                                IllegalStateException.class,
                                                                h::startAsync);
                                                    })));
            assertTrue(reached.get());
            assertEquals(200, response.getStatus());
            assertEquals("no-store", response.getHeader("Cache-Control"));
            assertFalse(response.containsHeader("Set-Cookie"));
            assertFalse(response.containsHeader("X-Sakai-Session"));
            assertEquals("application/json", response.getHeader("Content-Type"));
            assertSame(outer, sessions.getCurrentSession());
            assertSame(prior, sessions.getCurrentToolSession());
            assertEquals(1, registry.size());
            assertNull(request.getAttribute(DelegatedCredentialGuard.MARKER));
            registry.clear();
            state.get().clear();
        }
    }

    @Test
    public void ownGradeReachRejectsStudentSelectionAndMutation() throws Exception {
        for (String path : List.of("/api/sites/course-a/grades/7/student-a", "/api/users/other/grades",
                "/api/sites/course-a/grading/other-data", "/api/sites/grades", "/api/sites/grading/item-data")) {
            var response = new MockHttpServletResponse();
            guard.doFilter(request(path), response, (r, s) -> fail("unselected grade route accepted"));
            assertEquals(403, response.getStatus());
        }
        var query = request("/api/sites/course-a/grades");
        query.setQueryString("userId=other");
        query.addParameter("userId", "other");
        var response = new MockHttpServletResponse();
        guard.doFilter(query, response, (r, s) -> fail("selected-other-student query accepted"));
        assertEquals(403, response.getStatus());
        var mutation = request("/api/sites/course-a/grades");
        mutation.setMethod("POST");
        response = new MockHttpServletResponse();
        guard.doFilter(mutation, response, (r, s) -> fail("grade write accepted"));
        assertEquals(403, response.getStatus());
    }

    @Test
    public void assignmentDiscoveryAcceptsOnlyTheExistingSiteRead() throws Exception {
        var allowed = request("/direct/assignment/site/course-a.json");
        AtomicBoolean reached = new AtomicBoolean();
        guard.doFilter(allowed, new MockHttpServletResponse(), (r, s) -> reached.set(true));
        assertTrue(reached.get());
        for (String path : List.of("/direct/assignment/unknown/assignment-a.json",
                "/direct/assignment/setGrade.json", "/direct/assignment/site/course-a/other.json")) {
            var response = new MockHttpServletResponse();
            guard.doFilter(request(path), response, (r, s) -> fail("unselected route accepted"));
            assertEquals(403, response.getStatus());
        }
        allowed.setQueryString("hydrate=false");
        allowed.addParameter("hydrate", "false");
        var response = new MockHttpServletResponse();
        guard.doFilter(allowed, response, (r, s) -> fail("invented parameter accepted"));
        assertEquals(403, response.getStatus());
    }

    @Test
    public void announcementReadQueryReachExcludesCredentialsAndOtherActions() throws Exception {
        MockHttpServletRequest allowed = request("/direct/announcement/site/course-a.json");
        allowed.setQueryString("n=1000&d=3650&a=0");
        allowed.addParameter("n", "1000");
        allowed.addParameter("d", "3650");
        allowed.addParameter("a", "0");
        AtomicBoolean reached = new AtomicBoolean();
        guard.doFilter(allowed, new MockHttpServletResponse(), (r, s) -> reached.set(true));
        assertTrue(reached.get());
        for (String field : List.of("sessionid", "userId", "props", "n")) {
            MockHttpServletRequest denied = request("/direct/announcement/site/course-a.json");
            denied.setQueryString(field + "=borrowed");
            denied.addParameter(field, "borrowed");
            MockHttpServletResponse out = new MockHttpServletResponse();
            guard.doFilter(denied, out, (r, s) -> fail("unsafe query accepted"));
            assertEquals(403, out.getStatus());
        }
        MockHttpServletRequest access = request("/direct/site.json");
        access.setQueryString("select=access&_start=0&_limit=100");
        access.addParameter("select", "access");
        access.addParameter("_start", "0");
        access.addParameter("_limit", "100");
        AtomicBoolean selected = new AtomicBoolean();
        guard.doFilter(access, new MockHttpServletResponse(), (r, s) -> selected.set(true));
        assertTrue(selected.get());
        access.setParameter("select", "any");
        MockHttpServletResponse invalidSelect = new MockHttpServletResponse();
        guard.doFilter(access, invalidSelect, (r, s) -> fail("non-ACCESS selection accepted"));
        assertEquals(403, invalidSelect.getStatus());
        MockHttpServletRequest props = request("/direct/site/course-a/pages.json");
        props.setQueryString("config=true");
        props.addParameter("config", "true");
        MockHttpServletResponse out = new MockHttpServletResponse();
        guard.doFilter(props, out, (r, s) -> fail("admin options accepted"));
        assertEquals(403, out.getStatus());
    }

    @Test
    public void ordinaryRequestsRemainUnchangedAndLegacyStillReachesOldChain() throws Exception {
        for (String path : List.of("/api/login", "/direct/session", "/api/mcp/v1/courses")) {
            MockHttpServletRequest r = request(path);
            r.removeHeader("Authorization");
            if (path.contains("mcp/v1")) r.addHeader("Authorization", "Bearer token-a");
            MockHttpServletResponse s = new MockHttpServletResponse();
            AtomicBoolean called = new AtomicBoolean();
            guard.doFilter(
                    r,
                    s,
                    (a, b) -> {
                        assertSame(r, a);
                        assertSame(s, b);
                        called.set(true);
                    });
            assertTrue(called.get());
        }
        verifyNoInteractions(verifier, authentication, usage);
    }

    @Test
    public void mixedCredentialsUnsafePathsMethodsAndDispatchesFailBeforeSessionCreation()
            throws Exception {
        List<MockHttpServletRequest> denied = new ArrayList<>();
        MockHttpServletRequest cookie = request("/direct/user/current.json");
        cookie.setCookies(new Cookie("JSESSIONID", "browser"));
        denied.add(cookie);
        MockHttpServletRequest duplicate = request("/direct/user/current.json");
        duplicate.addHeader("Authorization", "Basic secret");
        denied.add(duplicate);
        MockHttpServletRequest query = request("/direct/user/current.json");
        query.setQueryString("sessionid=browser");
        denied.add(query);
        MockHttpServletRequest flow = request("/direct/user/current.json");
        flow.addHeader("X-MCP-Flow", "unproven");
        denied.add(flow);
        MockHttpServletRequest post = request("/api/users/me/sites");
        post.setMethod("POST");
        denied.add(post);
        MockHttpServletRequest forward = request("/api/users/me/sites");
        forward.setDispatcherType(DispatcherType.FORWARD);
        denied.add(forward);
        denied.add(request("/api/login"));
        denied.add(request("/direct/site/a%2fb.json"));
        for (MockHttpServletRequest r : denied) {
            MockHttpServletResponse s = new MockHttpServletResponse();
            guard.doFilter(r, s, (a, b) -> fail("unsafe credential reached handler"));
            assertTrue(s.getStatus() == 401 || s.getStatus() == 403);
        }
        assertEquals(0, sequence.get());
        verifyNoInteractions(usage);
    }

    @Test
    public void cleanupRunsOnLoginFailureAndHandlerException() throws Exception {
        doReturn(false)
                .when(usage)
                .login(anyString(), anyString(), anyString(), anyString(), anyString());
        MockHttpServletResponse response = new MockHttpServletResponse();
        guard.doFilter(request("/direct/user/current.json"), response, (r, s) -> fail());
        assertEquals(503, response.getStatus());
        assertTrue(registry.isEmpty());
        assertNull(sessions.getCurrentSession());
        setup();
        MockHttpServletResponse failed = new MockHttpServletResponse();
        guard.doFilter(
                request("/direct/user/current.json"),
                failed,
                (r, s) -> {
                    ((HttpServletResponse) s).getWriter().write("private uncommitted body");
                    throw new ServletException(sessions.getCurrentSession().getId());
                });
        assertEquals(502, failed.getStatus());
        assertEquals(0, failed.getContentAsByteArray().length);
        assertTrue(registry.isEmpty());
        assertNull(sessions.getCurrentSession());
    }

    @Test
    public void mappingMismatchAndInvalidTokenNeverRunNativeHandler() throws Exception {
        when(authentication.authenticate(any()))
                .thenReturn(new Authentication("uid-a", "wrong-eid"));
        MockHttpServletResponse mismatch = new MockHttpServletResponse();
        guard.doFilter(request("/direct/user/current.json"), mismatch, (r, s) -> fail());
        assertEquals(403, mismatch.getStatus());
        assertTrue(registry.isEmpty());
        when(verifier.verify("token-a"))
                .thenThrow(new DelegatedJwtVerifier.InvalidTokenException());
        MockHttpServletResponse invalid = new MockHttpServletResponse();
        guard.doFilter(request("/direct/user/current.json"), invalid, (r, s) -> fail());
        assertEquals(401, invalid.getStatus());
        assertEquals("Bearer", invalid.getHeader("WWW-Authenticate"));
    }

    @Test
    public void twoUsersInterleaveWithoutIdentityOrSessionLeakage() throws Exception {
        when(verifier.verify("token-b"))
                .thenReturn(new DelegatedJwtVerifier.Identity("eid-b", "tenant", "oid-b"));
        when(authentication.authenticate(any()))
                .thenAnswer(
                        i -> {
                            String eid =
                                    ((org.sakaiproject.user.api.ExternalTrustedEvidence)
                                                    i.getArgument(0))
                                            .getIdentifier();
                            return new Authentication(eid.equals("eid-b") ? "uid-b" : "uid-a", eid);
                        });
        RequestFilter nativeFilter = nativeFilter("/direct");
        CountDownLatch both = new CountDownLatch(2);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            List<Future<?>> results = new ArrayList<>();
            for (String who : List.of("a", "b"))
                results.add(
                        pool.submit(
                                () -> {
                                    try {
                                        MockHttpServletRequest r =
                                                request("/direct/user/current.json");
                                        r.removeHeader("Authorization");
                                        r.addHeader("Authorization", "Bearer token-" + who);
                                        guard.doFilter(
                                                r,
                                                new MockHttpServletResponse(),
                                                (a, b) ->
                                                        nativeFilter.doFilter(
                                                                a,
                                                                b,
                                                                (n, o) ->
                                                                        binder.doFilter(
                                                                                n,
                                                                                o,
                                                                                (request,
                                                                                        response) -> {
                                                                                    Session
                                                                                            selected =
                                                                                                    sessions
                                                                                                            .getCurrentSession();
                                                                                    both
                                                                                            .countDown();
                                                                                    try {
                                                                                        assertTrue(
                                                                                                both
                                                                                                        .await(
                                                                                                                5,
                                                                                                                TimeUnit
                                                                                                                        .SECONDS));
                                                                                    } catch (
                                                                                            InterruptedException
                                                                                                    e) {
                                                                                        throw new ServletException(
                                                                                                e);
                                                                                    }
                                                                                    assertEquals(
                                                                                            "uid-"
                                                                                                    + who,
                                                                                            selected
                                                                                                    .getUserId());
                                                                                    assertEquals(
                                                                                            "eid-"
                                                                                                    + who,
                                                                                            ((HttpServletRequest)
                                                                                                            request)
                                                                                                    .getRemoteUser());
                                                                                    assertSame(
                                                                                            selected,
                                                                                            sessions
                                                                                                    .getCurrentSession());
                                                                                })));
                                        assertNull(sessions.getCurrentSession());
                                        assertNull(threads.get(RequestFilter.CURRENT_HTTP_REQUEST));
                                    } catch (Exception e) {
                                        throw new RuntimeException(e);
                                    }
                                }));
            for (Future<?> result : results) result.get(10, TimeUnit.SECONDS);
            assertTrue(registry.isEmpty());
        } finally {
            pool.shutdownNow();
        }
    }

    private void enableConversations() {
        when(configuration.getBoolean("mcp.integration.conversations.enabled", false))
                .thenReturn(true);
        when(configuration.getString("mcp.integration.flowSecret", ""))
                .thenReturn(Base64.getEncoder().encodeToString(new byte[32]));
    }

    @Test
    public void boundedFlowRetainsNativeStateAndEndsOnExistingRead() throws Exception {
        enableConversations();
        RequestFilter nativeFilter = nativeFilter("/direct");
        AtomicReference<Session> selected = new AtomicReference<>();
        for (int step = 0; step < 3; step++) {
            final int current = step;
            MockHttpServletRequest r = request("/direct/user/current.json");
            r.addHeader("X-MCP-Flow", "a".repeat(64));
            if (step == 2) r.addHeader("X-MCP-Flow-End", "1");
            MockHttpServletResponse response = new MockHttpServletResponse();
            guard.doFilter(
                    r,
                    response,
                    (a, b) ->
                            nativeFilter.doFilter(
                                    a,
                                    b,
                                    (n, o) ->
                                            binder.doFilter(
                                                    n,
                                                    o,
                                                    (request, output) -> {
                                                        Session session =
                                                                sessions.getCurrentSession();
                                                        if (current == 0) {
                                                            selected.set(session);
                                                            session.setAttribute(
                                                                    "synthetic-csrf", "preserved");
                                                        } else {
                                                            assertSame(selected.get(), session);
                                                            assertEquals(
                                                                    "preserved",
                                                                    session.getAttribute(
                                                                            "synthetic-csrf"));
                                                        }
                                                        assertNotEquals(
                                                                "a".repeat(64), session.getId());
                                                    })));
            assertEquals(200, response.getStatus());
            assertNull(sessions.getCurrentSession());
            assertEquals(step == 2 ? 0 : 1, registry.size());
        }
        verify(usage, times(1))
                .login(anyString(), anyString(), anyString(), anyString(), anyString());
        verify(authentication, times(3)).authenticate(any());
        verify(selected.get()).invalidate();
    }

    @Test
    public void copiedNonceSelectsDifferentUsersAndDisabledUserCannotReuse() throws Exception {
        enableConversations();
        MockHttpServletRequest first = request("/direct/user/current.json");
        first.addHeader("X-MCP-Flow", "a".repeat(64));
        guard.doFilter(first, new MockHttpServletResponse(), (a, b) -> {});
        Session original = registry.values().iterator().next();
        when(verifier.verify("token-b"))
                .thenReturn(new DelegatedJwtVerifier.Identity("eid-b", "tenant", "oid-b"));
        when(authentication.authenticate(any())).thenReturn(new Authentication("uid-b", "eid-b"));
        MockHttpServletRequest other = request("/direct/user/current.json");
        other.removeHeader("Authorization");
        other.addHeader("Authorization", "Bearer token-b");
        other.addHeader("X-MCP-Flow", "a".repeat(64));
        guard.doFilter(
                other,
                new MockHttpServletResponse(),
                (a, b) -> assertNotSame(original, sessions.getCurrentSession()));
        assertEquals(2, registry.size());
        when(authentication.authenticate(any()))
                .thenThrow(
                        new org.sakaiproject.user.api.AuthenticationException(
                                "synthetic-disabled"));
        MockHttpServletResponse disabled = new MockHttpServletResponse();
        guard.doFilter(other, disabled, (a, b) -> fail());
        assertEquals(403, disabled.getStatus());
        assertNull(sessions.getCurrentSession());
    }

    @Test
    public void missingSecretExpiredFlowAndAlternateSessionCredentialFailClosed() throws Exception {
        enableConversations();
        when(configuration.getString("mcp.integration.flowSecret", "")).thenReturn("");
        MockHttpServletRequest r = request("/direct/user/current.json");
        r.addHeader("X-MCP-Flow", "a".repeat(64));
        MockHttpServletResponse missing = new MockHttpServletResponse();
        guard.doFilter(r, missing, (a, b) -> fail());
        assertEquals(503, missing.getStatus());
        assertTrue(registry.isEmpty());
        enableConversations();
        guard.doFilter(r, new MockHttpServletResponse(), (a, b) -> {});
        Session s = registry.values().iterator().next();
        s.setAttribute(
                DelegatedConversations.STATE,
                new DelegatedConversations.Owner("tenant", "oid-a", "uid-a", "eid-a", 0));
        MockHttpServletResponse expired = new MockHttpServletResponse();
        guard.doFilter(r, expired, (a, b) -> fail());
        assertEquals(410, expired.getStatus());
        assertTrue(registry.isEmpty());
        MockHttpServletRequest alternate = request("/direct/user/current.json");
        alternate.addHeader("X-MCP-Flow", "a".repeat(64));
        alternate.setParameter("sakai.session", "browser");
        MockHttpServletResponse rejected = new MockHttpServletResponse();
        guard.doFilter(alternate, rejected, (a, b) -> fail());
        assertEquals(403, rejected.getStatus());
    }

    @Test
    public void opaqueSiteIdsAreCanonicalAndMalformedEncodingIsRejected() {
        for (String id : List.of("course.a", "course%20a", "course%2Ba", "%D8%A7")) {
            assertTrue(DelegatedRoutes.allows(request("/direct/site/" + id + ".json")));
        }
        for (String id : List.of("%2e%2e", "a%2fb", "a%252fb", "%FF", "%GG", "a;b")) {
            assertFalse(DelegatedRoutes.allows(request("/direct/site/" + id + ".json")));
        }
    }

    @Test
    public void sensitiveFrameworkDebugLoggingBlocksDelegatedSessionCreation() throws Exception {
        RequestFilter.isSecure(
                request("/direct/user/current.json")); // initialize existing logger before the
        // static test double
        org.slf4j.Logger logger = mock(org.slf4j.Logger.class);
        when(logger.isDebugEnabled()).thenReturn(true);
        try (MockedStatic<org.slf4j.LoggerFactory> factory =
                mockStatic(org.slf4j.LoggerFactory.class)) {
            factory.when(() -> org.slf4j.LoggerFactory.getLogger(anyString())).thenReturn(logger);
            MockHttpServletResponse response = new MockHttpServletResponse();
            guard.doFilter(request("/direct/user/current.json"), response, (r, s) -> fail());
            assertEquals(503, response.getStatus());
            assertTrue(registry.isEmpty());
        }
    }
}
