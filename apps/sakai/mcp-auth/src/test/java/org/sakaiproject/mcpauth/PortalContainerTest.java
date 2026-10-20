/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import org.apache.catalina.Context;
import org.apache.catalina.startup.Tomcat;
import org.apache.tomcat.util.descriptor.web.FilterDef;
import org.apache.tomcat.util.descriptor.web.FilterMap;
import org.junit.Test;
import org.sakaiproject.authz.api.*;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.portal.api.Portal;
import org.sakaiproject.portal.api.PortalService;
import org.sakaiproject.portal.charon.handlers.ToolHandler;
import org.sakaiproject.site.api.*;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.tool.impl.ActiveToolComponent;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.Authentication;
import org.sakaiproject.util.RequestFilter;

import java.io.IOException;
import java.lang.reflect.Field;
import java.net.URI;
import java.net.http.*;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;

import javax.servlet.*;
import javax.servlet.http.*;

/**
 * Actual Tomcat cross-context named forward through upstream ToolHandler/ActiveTool. A synthetic
 * state probe receives the dispatch; no academic tool operation is run.
 */
public class PortalContainerTest {
    @Test
    public void actualPortalDispatchKeepsIsolatedNativeToolSessionAcrossRequests()
            throws Exception {
        ThreadLocal<Map<String, Object>> locals = ThreadLocal.withInitial(HashMap::new);
        ThreadLocalManager threads = mock(ThreadLocalManager.class);
        when(threads.get(anyString())).thenAnswer(i -> locals.get().get(i.getArgument(0)));
        doAnswer(
                        i -> {
                            String k = i.getArgument(0);
                            Object v = i.getArgument(1);
                            if (v == null) locals.get().remove(k);
                            else locals.get().put(k, v);
                            return null;
                        })
                .when(threads)
                .set(anyString(), any());
        doAnswer(
                        i -> {
                            locals.get().clear();
                            return null;
                        })
                .when(threads)
                .clear();
        SessionManager sessions = mock(SessionManager.class);
        String key = "org.sakaiproject.api.kernel.session.current";
        when(sessions.getCurrentSession()).thenAnswer(i -> locals.get().get(key));
        when(sessions.getCurrentToolSession()).thenAnswer(i -> locals.get().get(key + ".tool"));
        doAnswer(
                        i -> {
                            threads.set(key, i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentSession(any());
        doAnswer(
                        i -> {
                            threads.set(key + ".tool", i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentToolSession(any());
        Map<String, Session> registry = new ConcurrentHashMap<>();
        when(sessions.getSession(anyString())).thenAnswer(i -> registry.get(i.getArgument(0)));
        when(sessions.getSessions()).thenAnswer(i -> new ArrayList<>(registry.values()));
        when(sessions.startSession(anyString()))
                .thenAnswer(
                        i -> {
                            String id = i.getArgument(0);
                            Session s = mock(Session.class);
                            when(s.getId()).thenReturn(id);
                            Map<String, Object> attrs = new ConcurrentHashMap<>();
                            when(s.getAttribute(anyString()))
                                    .thenAnswer(j -> attrs.get(j.getArgument(0)));
                            doAnswer(
                                            j -> {
                                                attrs.put(j.getArgument(0), j.getArgument(1));
                                                return null;
                                            })
                                    .when(s)
                                    .setAttribute(anyString(), any());
                            AtomicReference<String> uid = new AtomicReference<>(),
                                    eid = new AtomicReference<>();
                            when(s.getUserId()).thenAnswer(j -> uid.get());
                            when(s.getUserEid()).thenAnswer(j -> eid.get());
                            doAnswer(
                                            j -> {
                                                uid.set(j.getArgument(0));
                                                return null;
                                            })
                                    .when(s)
                                    .setUserId(anyString());
                            doAnswer(
                                            j -> {
                                                eid.set(j.getArgument(0));
                                                return null;
                                            })
                                    .when(s)
                                    .setUserEid(anyString());
                            ToolSession tool =
                                    mock(
                                            ToolSession.class,
                                            withSettings().extraInterfaces(HttpSession.class));
                            when(s.getToolSession("placement-a")).thenReturn(tool);
                            Map<String, Object> toolState = new ConcurrentHashMap<>();
                            when(((HttpSession) tool).getAttribute(anyString()))
                                    .thenAnswer(j -> toolState.get(j.getArgument(0)));
                            doAnswer(
                                            j -> {
                                                toolState.put(j.getArgument(0), j.getArgument(1));
                                                return null;
                                            })
                                    .when((HttpSession) tool)
                                    .setAttribute(anyString(), any());
                            doAnswer(
                                            j -> {
                                                registry.remove(id);
                                                return null;
                                            })
                                    .when(s)
                                    .invalidate();
                            registry.put(id, s);
                            return s;
                        });
        ServerConfigurationService config = mock(ServerConfigurationService.class);
        when(config.getBoolean(anyString(), anyBoolean())).thenAnswer(i -> i.getArgument(1));
        when(config.getBoolean("mcp.integration.existingHttp.enabled", false)).thenReturn(true);
        when(config.getBoolean("mcp.integration.conversations.enabled", false)).thenReturn(true);
        when(config.getString(anyString(), anyString())).thenAnswer(i -> i.getArgument(1));
        when(config.getString("mcp.integration.flowSecret", ""))
                .thenReturn(Base64.getEncoder().encodeToString(new byte[32]));
        when(config.getStrings("mcp.integration.placements"))
                .thenReturn(new String[] {"placement-a"});
        AuthenticationManager accounts = mock(AuthenticationManager.class);
        when(accounts.authenticate(any())).thenReturn(new Authentication("uid-a", "eid-a"));
        UsageSessionService usage = mock(UsageSessionService.class);
        when(usage.login(anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenAnswer(
                        i -> {
                            Session s = sessions.getCurrentSession();
                            s.setUserId(i.getArgument(0));
                            s.setUserEid(i.getArgument(1));
                            return true;
                        });
        DelegatedJwtVerifier verifier = mock(DelegatedJwtVerifier.class);
        when(verifier.verify("synthetic"))
                .thenReturn(new DelegatedJwtVerifier.Identity("eid-a", "tenant", "oid-a"));
        SiteService sites = mock(SiteService.class);
        SecurityService security = mock(SecurityService.class);
        FunctionManager functions = mock(FunctionManager.class);
        ActiveToolComponent tools =
                new ActiveToolComponent() {
                    protected SessionManager sessionManager() {
                        return sessions;
                    }

                    protected FunctionManager functionManager() {
                        return functions;
                    }

                    protected ServerConfigurationService serverConfigurationService() {
                        return config;
                    }

                    protected ThreadLocalManager threadLocalManager() {
                        return threads;
                    }

                    protected SecurityService securityService() {
                        return security;
                    }

                    protected SiteService siteService() {
                        return sites;
                    }
                };
        org.sakaiproject.component.api.ComponentManager manager =
                mock(org.sakaiproject.component.api.ComponentManager.class);
        Map<Class<?>, Object> dependencies =
                Map.of(
                        SessionManager.class,
                        sessions,
                        ThreadLocalManager.class,
                        threads,
                        ServerConfigurationService.class,
                        config,
                        ToolManager.class,
                        tools,
                        ActiveToolManager.class,
                        tools,
                        SiteService.class,
                        sites);
        when(manager.get(any(Class.class))).thenAnswer(i -> dependencies.get(i.getArgument(0)));
        Field componentField = ComponentManager.class.getDeclaredField("m_componentManager");
        componentField.setAccessible(true);
        Object previous = componentField.get(null);
        componentField.set(null, manager);
        Tomcat tomcat = new Tomcat();
        tomcat.setBaseDir(Files.createTempDirectory("sakai-auth-tomcat-").toString());
        tomcat.setPort(0);
        tomcat.getConnector().setProperty("address", "127.0.0.1");
        // Models TLS termination at the loopback-only test connector.
        tomcat.getConnector().setScheme("https");
        tomcat.getConnector().setSecure(true);
        try {
            Context portalContext =
                    tomcat.addContext(
                            "/portal", Files.createTempDirectory("sakai-portal-probe-").toString());
            portalContext.setCrossContext(true);
            Context targetContext =
                    tomcat.addContext(
                            "/announcements",
                            Files.createTempDirectory("sakai-tool-probe-").toString());
            targetContext.setCrossContext(true);
            install(
                    portalContext,
                    new DelegatedCredentialGuard(
                            config, accounts, sessions, usage, threads, verifier),
                    new RequestFilter(),
                    new DelegatedSessionFilter(sessions, threads),
                    "REQUEST");
            install(
                    targetContext,
                    new DelegatedCredentialGuard(
                            config, accounts, sessions, usage, threads, verifier),
                    new RequestFilter(),
                    new DelegatedSessionFilter(sessions, threads),
                    "FORWARD");
            AtomicReference<String> failure = new AtomicReference<>();
            Tomcat.addServlet(
                    targetContext,
                    "sakai.announcements",
                    new HttpServlet() {
                        @Override
                        protected void doGet(HttpServletRequest r, HttpServletResponse s)
                                throws IOException {
                            try {
                                assertNotNull(r.getAttribute(DelegatedCredentialGuard.MARKER));
                                // Existing ActiveTool wrappers keep REQUEST on this named dispatch.
                                assertTrue(
                                        Set.of(DispatcherType.REQUEST, DispatcherType.FORWARD)
                                                .contains(r.getDispatcherType()));
                                assertEquals("uid-a", sessions.getCurrentSession().getUserId());
                                assertEquals("eid-a", r.getRemoteUser());
                                assertEquals("placement-a", tools.getCurrentPlacement().getId());
                                assertSame(sessions.getCurrentToolSession(), r.getSession(false));
                                HttpSession tool = r.getSession(false);
                                Integer count = (Integer) tool.getAttribute("step");
                                count = count == null ? 1 : count + 1;
                                tool.setAttribute("step", count);
                                s.setContentType("text/plain");
                                s.getWriter().write(count.toString());
                            } catch (Throwable e) {
                                failure.set(e.toString());
                                s.sendError(500);
                            }
                        }
                    });
            targetContext.addServletMappingDecoded("/*", "sakai.announcements");
            ActiveToolComponent.MyActiveTool tool = tools.new MyActiveTool();
            tool.setId("sakai.announcements");
            tool.setAccessSecurity(Tool.AccessSecurity.PORTAL);
            tools.register(tool, targetContext.getServletContext());
            ToolConfiguration placement = mock(ToolConfiguration.class);
            when(placement.getId()).thenReturn("placement-a");
            when(placement.getToolId()).thenReturn("sakai.announcements");
            when(placement.getSiteId()).thenReturn("course-a");
            when(placement.getConfig()).thenReturn(new Properties());
            when(sites.findTool("placement-a")).thenReturn(placement);
            when(sites.getSiteVisit("course-a"))
                    .thenAnswer(
                            i -> {
                                assertEquals("uid-a", sessions.getCurrentSession().getUserId());
                                return mock(Site.class);
                            });
            Portal portal = mock(Portal.class);
            PortalService portalService = mock(PortalService.class);
            when(portal.getPlacement(any(), any(), any(), eq("placement-a"), eq(false)))
                    .thenReturn("placement-a");
            doAnswer(
                            i -> {
                                ((ActiveTool) i.getArgument(0))
                                        .forward(
                                                i.getArgument(1),
                                                i.getArgument(2),
                                                i.getArgument(3),
                                                i.getArgument(5),
                                                i.getArgument(6));
                                return null;
                            })
                    .when(portal)
                    .forwardTool(any(), any(), any(), any(), any(), any(), any());
            ToolHandler handler = new ToolHandler();
            handler.register(portal, portalService, portalContext.getServletContext());
            Tomcat.addServlet(
                    portalContext,
                    "portal",
                    new HttpServlet() {
                        @Override
                        protected void doGet(HttpServletRequest r, HttpServletResponse s)
                                throws IOException, ServletException {
                            try {
                                handler.doGet(
                                        new String[] {"", "tool", "placement-a"},
                                        r,
                                        s,
                                        sessions.getCurrentSession());
                            } catch (Exception e) {
                                throw new ServletException(e);
                            }
                        }
                    });
            portalContext.addServletMappingDecoded("/*", "portal");
            tomcat.start();
            int port = tomcat.getConnector().getLocalPort();
            HttpClient http = HttpClient.newHttpClient();
            for (int step = 1; step <= 2; step++) {
                HttpResponse<String> response =
                        http.send(
                                HttpRequest.newBuilder(
                                                URI.create(
                                                        "http://127.0.0.1:"
                                                                + port
                                                                + "/portal/tool/placement-a"))
                                        .header("Authorization", "Bearer synthetic")
                                        .header("X-MCP-Flow", "a".repeat(64))
                                        .GET()
                                        .build(),
                                HttpResponse.BodyHandlers.ofString());
                assertNull(failure.get());
                assertEquals(200, response.statusCode());
                assertEquals(Integer.toString(step), response.body());
                assertTrue(response.headers().allValues("set-cookie").isEmpty());
                assertTrue(response.headers().allValues("X-Sakai-Session").isEmpty());
            }
            assertEquals(1, registry.size());
            verify(sites, times(2)).getSiteVisit("course-a");
        } finally {
            try {
                tomcat.stop();
                tomcat.destroy();
            } finally {
                componentField.set(null, previous);
            }
        }
    }

    private static void install(
            Context context, Filter guard, Filter nativeFilter, Filter binder, String dispatch) {
        for (var item :
                List.of(
                        Map.entry("credentials", guard),
                        Map.entry("sakai.request", nativeFilter),
                        Map.entry("session", binder))) {
            FilterDef def = new FilterDef();
            def.setFilterName(item.getKey());
            def.setFilterClass(item.getValue().getClass().getName());
            def.setFilter(item.getValue());
            if (item.getKey().equals("sakai.request")) {
                def.addInitParameter("upload.enabled", "false");
                def.addInitParameter("tool.placement", "none");
            }
            context.addFilterDef(def);
            FilterMap map = new FilterMap();
            map.setFilterName(item.getKey());
            map.addURLPattern("/*");
            map.setDispatcher(dispatch);
            if (!dispatch.equals("REQUEST")) map.setDispatcher("REQUEST");
            context.addFilterMap(map);
        }
    }
}
