/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;

import org.junit.Test;
import org.springframework.mock.web.MockHttpServletResponse;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class DelegatedResponseTest {
    private static final String SECRET = "mcp_private_authenticated_session";

    @Test
    public void normalBodyIsByteExactAndFlushDoesNotExposePartialBody() throws Exception {
        MockHttpServletResponse original = new MockHttpServletResponse();
        DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
        byte[] expected = "literal <p>&\r\n\u00a3".getBytes(StandardCharsets.UTF_8);
        guarded.setCharacterEncoding("UTF-8");
        guarded.getOutputStream().write(expected);
        guarded.flushBuffer();
        assertTrue(guarded.isCommitted());
        assertEquals(0, original.getContentAsByteArray().length);
        guarded.finish();
        assertArrayEquals(expected, original.getContentAsByteArray());
    }

    @Test
    public void fragmentedCredentialInNativeErrorBodyNeverReachesConnection() throws Exception {
        MockHttpServletResponse original = new MockHttpServletResponse();
        DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
        guarded.getWriter().write("<p>session: mcp_private_");
        guarded.getWriter().flush();
        guarded.getWriter().write("authenticated_session</p>");
        guarded.finish();
        assertEquals(502, original.getStatus());
        assertEquals(0, original.getContentAsByteArray().length);
        assertEquals("no-store", original.getHeader("Cache-Control"));
    }

    @Test
    public void CredentialInRedirectOrOtherHeaderIsWithheld() throws Exception {
        for (String header : new String[] {"Location", "X-Debug"}) {
            MockHttpServletResponse original = new MockHttpServletResponse();
            DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
            guarded.setHeader(header, "https://example.test/?session=" + SECRET);
            guarded.finish();
            assertEquals(502, original.getStatus());
            assertNull(original.getHeader(header));
        }
    }

    @Test
    public void opaqueCompressedOrUnsupportedEncodingIsNotPassedUnchecked() throws Exception {
        for (String mode : new String[] {"gzip", "UTF-16"}) {
            MockHttpServletResponse original = new MockHttpServletResponse();
            DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
            if (mode.equals("gzip")) guarded.setHeader("Content-Encoding", mode);
            else guarded.setCharacterEncoding(mode);
            guarded.getOutputStream().write(new byte[] {1, 2, 3});
            guarded.finish();
            assertEquals(502, original.getStatus());
            assertEquals(0, original.getContentAsByteArray().length);
        }
    }

    @Test
    public void oversizeOutputFailsBeforeEmissionEvenIfWriterSwallowsIOException()
            throws Exception {
        MockHttpServletResponse original = new MockHttpServletResponse();
        DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
        assertThrows(IOException.class, () -> guarded.getOutputStream().write(new byte[1_000_001]));
        guarded.finish();
        assertEquals(502, original.getStatus());
        assertEquals(0, original.getContentAsByteArray().length);
    }

    @Test
    public void nativeErrorsDropPrivateMessageAndResetDropsBufferedText() throws Exception {
        MockHttpServletResponse original = new MockHttpServletResponse();
        DelegatedResponse guarded = new DelegatedResponse(original, SECRET);
        guarded.getWriter().write("uncommitted body");
        guarded.sendError(403, SECRET);
        guarded.finish();
        assertEquals(403, original.getStatus());
        assertEquals(0, original.getContentAsByteArray().length);
    }
}
