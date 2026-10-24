/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.Test;
import org.mockito.MockedStatic;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.coursemanagement.api.CourseManagementService;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.messaging.api.UserMessagingService;
import org.sakaiproject.portal.api.PortalService;
import org.sakaiproject.site.api.*;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.Authentication;
import org.sakaiproject.util.RequestFilter;
import org.sakaiproject.webapi.controllers.SitesController;
import org.springframework.mock.web.*;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

import javax.servlet.http.HttpSession;

/** Real WebAPI controller and native filter; domain services are synthetic doubles. */
public class ExistingSitesChainTest {
    private static Jwt jwt(String eid, String tenant, String oid) {
        return Jwt.withTokenValue("fixture")
                .header("alg", "RS256")
                .claim("extn.SakaiEid", List.of(eid))
                .claim("tid", tenant)
                .claim("oid", oid)
                .build();
    }

    @Test
    public void delegatedRequestRunsExistingSitesControllerAndOrdinaryAnonymousStillDenied()
            throws Exception {
        Map<String, Object> state = new HashMap<>();
        ThreadLocalManager threads = mock(ThreadLocalManager.class);
        when(threads.get(anyString())).thenAnswer(i -> state.get(i.getArgument(0)));
        doAnswer(
                        i -> {
                            if (i.getArgument(1) == null) state.remove(i.getArgument(0));
                            else state.put(i.getArgument(0), i.getArgument(1));
                            return null;
                        })
                .when(threads)
                .set(anyString(), any());
        doAnswer(
                        i -> {
                            state.clear();
                            return null;
                        })
                .when(threads)
                .clear();
        SessionManager sessions = mock(SessionManager.class);
        String key = "org.sakaiproject.api.kernel.session.current";
        when(sessions.getCurrentSession()).thenAnswer(i -> state.get(key));
        doAnswer(
                        i -> {
                            threads.set(key, i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentSession(any());
        Session session = mock(Session.class);
        when(session.getId()).thenReturn("isolated");
        AtomicReference<String> uid = new AtomicReference<>(), eid = new AtomicReference<>();
        when(session.getUserId()).thenAnswer(i -> uid.get());
        when(session.getUserEid()).thenAnswer(i -> eid.get());
        doAnswer(
                        i -> {
                            uid.set(i.getArgument(0));
                            return null;
                        })
                .when(session)
                .setUserId(anyString());
        doAnswer(
                        i -> {
                            eid.set(i.getArgument(0));
                            return null;
                        })
                .when(session)
                .setUserEid(anyString());
        ContextSession context =
                mock(ContextSession.class, withSettings().extraInterfaces(HttpSession.class));
        when(session.getContextSession(anyString())).thenReturn(context);
        when(sessions.startSession()).thenReturn(session);
        when(sessions.getSession("isolated")).thenReturn(session);
        ServerConfigurationService config = mock(ServerConfigurationService.class);
        when(config.getString("mcp.integration.identityClaim", "extn.SakaiEid"))
                .thenReturn("extn.SakaiEid");
        when(config.getBoolean(anyString(), anyBoolean())).thenAnswer(i -> i.getArgument(1));
        when(config.getBoolean("mcp.integration.existingHttp.enabled", false)).thenReturn(true);
        when(config.getString(anyString(), anyString())).thenAnswer(i -> i.getArgument(1));
        AuthenticationManager accounts = mock(AuthenticationManager.class);
        when(accounts.authenticate(any())).thenReturn(new Authentication("uid-a", "eid-a"));
        UsageSessionService usage = mock(UsageSessionService.class);
        when(usage.login(anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenAnswer(
                        i -> {
                            session.setUserId(i.getArgument(0));
                            session.setUserEid(i.getArgument(1));
                            return true;
                        });
        JwtDecoder decoder = mock(JwtDecoder.class);
        when(decoder.decode("synthetic")).thenReturn(jwt("eid-a", "tenant", "oid-a"));
        DelegatedCredentialGuard guard =
                new DelegatedCredentialGuard(config, accounts, sessions, usage, threads, decoder);
        DelegatedSessionFilter binder = new DelegatedSessionFilter(sessions, threads);
        RequestFilter nativeFilter;
        try (MockedStatic<ComponentManager> cm = mockStatic(ComponentManager.class)) {
            cm.when(() -> ComponentManager.get(SessionManager.class)).thenReturn(sessions);
            cm.when(() -> ComponentManager.get(ThreadLocalManager.class)).thenReturn(threads);
            cm.when(() -> ComponentManager.get(ServerConfigurationService.class))
                    .thenReturn(config);
            nativeFilter = new RequestFilter();
            MockServletContext servlet = new MockServletContext();
            servlet.setContextPath("/api");
            MockFilterConfig filterConfig = new MockFilterConfig(servlet, "sakai.request");
            filterConfig.addInitParameter("upload.enabled", "false");
            nativeFilter.init(filterConfig);
        }
        SitesController controller = new SitesController();
        ReflectionTestUtils.setField(controller, "sessionManager", sessions);
        SiteService sites = mock(SiteService.class);
        when(sites.getUserSites())
                .thenAnswer(
                        i -> {
                            assertEquals("uid-a", sessions.getCurrentSession().getUserId());
                            return List.of();
                        });
        ReflectionTestUtils.setField(controller, "siteService", sites);
        PortalService portal = mock(PortalService.class);
        when(portal.getPinnedSites()).thenReturn(List.of());
        ReflectionTestUtils.setField(controller, "portalService", portal);
        CourseManagementService courses = mock(CourseManagementService.class);
        when(courses.getAcademicSessions()).thenReturn(List.of());
        ReflectionTestUtils.setField(controller, "cmService", courses);
        UserMessagingService messages = mock(UserMessagingService.class);
        when(messages.getNotifications()).thenReturn(List.of());
        ReflectionTestUtils.setField(controller, "userMessagingService", messages);
        ReflectionTestUtils.setField(controller, "serverConfigurationService", config);
        MockMvc mvc =
                MockMvcBuilders.standaloneSetup(controller)
                        .setControllerAdvice(
                                new org.sakaiproject.webapi.exception.GlobalExceptionHandler())
                        .addFilters(guard, nativeFilter, binder)
                        .build();
        mvc.perform(
                        get("/api/users/me/sites")
                                .contextPath("/api")
                                .secure(true)
                                .header("Authorization", "Bearer synthetic"))
                .andExpect(status().isOk())
                .andExpect(
                        result ->
                                assertEquals(
                                        new com.fasterxml.jackson.databind.ObjectMapper()
                                                .readTree("{\"terms\":[],\"sites\":[]}"),
                                        new com.fasterxml.jackson.databind.ObjectMapper()
                                                .readTree(
                                                        result.getResponse().getContentAsString())))
                .andExpect(header().doesNotExist("Set-Cookie"))
                .andExpect(header().doesNotExist("X-Sakai-Session"));
        verify(session).invalidate();
        verify(sites).getUserSites();
        assertNull(sessions.getCurrentSession());
        uid.set(null);
        eid.set(null);
        mvc.perform(get("/api/users/me/sites").contextPath("/api").secure(true))
                .andExpect(status().isForbidden());
    }
}
