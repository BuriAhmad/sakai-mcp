/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import org.junit.Test;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.event.api.UsageSessionService;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.user.api.AuthenticationManager;
import org.sakaiproject.util.Authentication;
import org.sakaiproject.webapi.DelegatedStreamingConfiguration;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.*;

import java.util.*;

public class DelegatedStreamingMvcTest {
    private static final String ARTIFACT =
            "/api/mcp/v1/courses/site/assignments/assignment/grading-exports/export/artifacts/artifact";

    @RestController
    public static class Fixture {
        final byte[] data;
        final SessionManager sessions;

        Fixture(byte[] data, SessionManager sessions) {
            this.data = data;
            this.sessions = sessions;
        }

        @GetMapping(
                "/mcp/v1/courses/site/assignments/assignment/grading-exports/export/artifacts/artifact")
        public ResponseEntity<StreamingResponseBody> artifact() {
            return ResponseEntity.ok()
                    .header("X-Content-SHA256", "synthetic-digest")
                    .contentLength(data.length)
                    .body(
                            out -> {
                                assertEquals("uid-a", sessions.getCurrentSession().getUserId());
                                assertNotNull(
                                        SecurityContextHolder.getContext().getAuthentication());
                                out.write(data);
                            });
        }

        @GetMapping("/ordinary-stream")
        public StreamingResponseBody ordinary() {
            return out -> out.write("ordinary".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }

        @GetMapping("/mcp/v1/courses/site/assignments/assignment/grading-files/file")
        public ResponseEntity<byte[]> file() {
            return ResponseEntity.ok().body(data);
        }
    }

    @Test
    public void realMvcArtifactRunsSynchronouslyInsideSingleGuardAndPreservesLargeFiles()
            throws Exception {
        byte[] data = new byte[1_000_001];
        Arrays.fill(data, (byte) 'x');
        verifyOutput(data, ARTIFACT, 200);
        verifyOutput(
                data, "/api/mcp/v1/courses/site/assignments/assignment/grading-files/file", 200);
    }

    @Test
    public void nativeFileCapAndCredentialScanningStillFailClosed() throws Exception {
        verifyOutput(new byte[10 * 1024 * 1024 + 1], ARTIFACT, 502);
        verifyOutput(
                "content private-native-session-id content"
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8),
                ARTIFACT,
                502);
    }

    private void verifyOutput(byte[] data, String path, int status) throws Exception {
        Map<String, Object> locals = new HashMap<>();
        var config = mock(ServerConfigurationService.class);
        when(config.getBoolean("mcp.integration.enabled", false)).thenReturn(true);
        when(config.getString("mcp.integration.identityClaim", "extn.SakaiEid"))
                .thenReturn("extn.SakaiEid");
        var sessions = mock(SessionManager.class);
        var threads = mock(ThreadLocalManager.class);
        when(threads.get(anyString())).thenAnswer(i -> locals.get(i.getArgument(0)));
        doAnswer(
                        i -> {
                            if (i.getArgument(1) == null) locals.remove(i.getArgument(0));
                            else locals.put(i.getArgument(0), i.getArgument(1));
                            return null;
                        })
                .when(threads)
                .set(anyString(), any());
        String current = "org.sakaiproject.api.kernel.session.current";
        when(sessions.getCurrentSession()).thenAnswer(i -> locals.get(current));
        doAnswer(
                        i -> {
                            locals.put(current, i.getArgument(0));
                            return null;
                        })
                .when(sessions)
                .setCurrentSession(any());
        var session = mock(Session.class);
        when(session.getId()).thenReturn("private-native-session-id");
        when(session.getUserId()).thenReturn("uid-a");
        when(session.getUserEid()).thenReturn("eid-a");
        when(sessions.startSession()).thenReturn(session);
        var accounts = mock(AuthenticationManager.class);
        when(accounts.authenticate(any())).thenReturn(new Authentication("uid-a", "eid-a"));
        var usage = mock(UsageSessionService.class);
        when(usage.login(anyString(), anyString(), anyString(), anyString(), anyString()))
                .thenReturn(true);
        var decoder = mock(JwtDecoder.class);
        when(decoder.decode("synthetic"))
                .thenReturn(
                        Jwt.withTokenValue("synthetic")
                                .header("alg", "RS256")
                                .claim("extn.SakaiEid", List.of("eid-a"))
                                .claim("tid", "tenant")
                                .claim("oid", "object")
                                .build());
        var guard =
                new DelegatedCredentialGuard(config, accounts, sessions, usage, threads, decoder);
        MockMvc mvc =
                MockMvcBuilders.standaloneSetup(new Fixture(data, sessions))
                        .addFilters(guard)
                        .build();
        DelegatedStreamingConfiguration.delegatedArtifactStreaming()
                .postProcessAfterInitialization(
                        mvc.getDispatcherServlet()
                                .getWebApplicationContext()
                                .getBean(RequestMappingHandlerAdapter.class),
                        "adapter");
        var result =
                mvc.perform(
                                get(path)
                                        .contextPath("/api")
                                        .secure(true)
                                        .header("Authorization", "Bearer synthetic"))
                        .andReturn();
        assertFalse(result.getRequest().isAsyncStarted());
        assertEquals(status, result.getResponse().getStatus());
        if (status == 200) assertArrayEquals(data, result.getResponse().getContentAsByteArray());
        else assertEquals(0, result.getResponse().getContentAsByteArray().length);
        assertNull(result.getResponse().getHeader("Set-Cookie"));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        assertNull(sessions.getCurrentSession());
        if (status == 200 && ARTIFACT.equals(path)) {
            var ordinary = mvc.perform(get("/api/ordinary-stream").contextPath("/api")).andReturn();
            assertTrue(ordinary.getRequest().isAsyncStarted());
            var completed =
                    mvc.perform(
                                    org.springframework.test.web.servlet.request
                                            .MockMvcRequestBuilders.asyncDispatch(ordinary))
                            .andReturn();
            assertEquals("ordinary", completed.getResponse().getContentAsString());
            verify(decoder, times(1)).decode("synthetic");
        }
        verify(session).invalidate();
    }
}
