/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.access.tool;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import java.nio.charset.StandardCharsets;
import javax.servlet.*;
import javax.servlet.http.*;
import org.junit.Test;
import org.sakaiproject.content.impl.ExistingContentAccessTest;
import org.sakaiproject.entity.api.*;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.util.ParameterParser;
import org.springframework.mock.web.*;

/** Explicit audit only: select with -Dtest=AccessServletProof. Not default regression selection. */
public class AccessServletProof {
    public static class NativeFixture extends AccessServlet {
        final ExistingContentAccessTest content = new ExistingContentAccessTest();
        public NativeFixture(SessionManager sessions) throws Exception {
            content.setup();
            content.useSessionsForProof(sessions);
            m_ready = true;
            sessionManager = sessions;
            entityManager = mock(EntityManager.class);
            var ref = content.referenceForProof();
            when(entityManager.newReference(anyString())).thenReturn(ref);
            var producer = mock(EntityProducer.class);
            when(ref.getEntityProducer()).thenReturn(producer);
            when(producer.getHttpAccess()).thenReturn(content.handlerForProof());
        }
        public void handle(ServletRequest input, ServletResponse output) throws ServletException {
            var request = (HttpServletRequest) input;
            var params = mock(ParameterParser.class);
            when(params.getPath()).thenReturn("/content/attachment/course-a/Assignments/opaque/answers.txt");
            request.setAttribute(ATTR_PARAMS, params);
            dispatch(request, (HttpServletResponse) output);
        }
    }

    private SessionManager sessions() {
        var sessions = mock(SessionManager.class);
        when(sessions.getCurrentSession()).thenReturn(mock(Session.class));
        when(sessions.getCurrentSessionUserId()).thenReturn("uid-a");
        return sessions;
    }

    @Test
    public void actualServletDispatchesToActualContentHandler() throws Exception {
        var fixture = new NativeFixture(sessions());
        var response = new MockHttpServletResponse();
        fixture.handle(new MockHttpServletRequest(), response);
        assertEquals(200, response.getStatus());
        assertArrayEquals("A\r\nB\né\n".getBytes(StandardCharsets.UTF_8), response.getContentAsByteArray());
        assertEquals("text/plain; charset=UTF-8", response.getContentType());
    }

    @Test
    public void actualServletMapsNativeContentDenialToForbidden() throws Exception {
        var fixture = new NativeFixture(sessions());
        fixture.content.denyForProof();
        var response = new MockHttpServletResponse();
        fixture.handle(new MockHttpServletRequest(), response);
        assertEquals(403, response.getStatus());
        assertEquals(0, response.getContentAsByteArray().length);
    }
}
