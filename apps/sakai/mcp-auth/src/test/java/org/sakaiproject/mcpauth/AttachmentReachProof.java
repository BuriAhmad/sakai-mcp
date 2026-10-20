/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.Test;
import org.sakaiproject.access.tool.AccessServletProof.NativeFixture;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.util.RequestFilter;
import org.springframework.mock.web.*;
import org.springframework.test.util.ReflectionTestUtils;

/** Positive readiness audit; a failure must remain recorded, not repaired during this audit. */
public class AttachmentReachProof extends DelegatedChainTest {
    @Test
    public void delegatedContentMustReachNativeServletChain() throws Exception {
        var guard = (DelegatedCredentialGuard) ReflectionTestUtils.getField(this, "guard");
        var binder = (DelegatedSessionFilter) ReflectionTestUtils.getField(this, "binder");
        var sessions = (SessionManager) ReflectionTestUtils.getField(this, "sessions");
        RequestFilter nativeFilter = ReflectionTestUtils.invokeMethod(this, "nativeFilter", "/access");
        var fixture = new NativeFixture(sessions);
        var request = new MockHttpServletRequest("GET", "/access/content/attachment/course-a/Assignments/opaque/answers.txt");
        request.setContextPath("/access");
        request.setServletPath("");
        request.setPathInfo("/content/attachment/course-a/Assignments/opaque/answers.txt");
        request.setSecure(true);
        request.setScheme("https");
        request.setServerPort(443);
        request.addHeader("Authorization", "Bearer token-a");
        var response = new MockHttpServletResponse();
        var reached = new AtomicBoolean();
        guard.doFilter(request, response, (r, s) ->
            nativeFilter.doFilter(r, s, (nr, ns) -> binder.doFilter(nr, ns, (br, bs) -> {
                reached.set(true);
                fixture.handle(br, bs);
            })));
        assertEquals("Delegated AccessServlet readiness; reached=" + reached.get(), 200, response.getStatus());
        assertTrue(reached.get());
        assertNull(sessions.getCurrentSession());
    }
}
