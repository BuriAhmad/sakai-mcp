/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import java.io.*;
import java.nio.charset.StandardCharsets;

import javax.servlet.ServletOutputStream;
import javax.servlet.WriteListener;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpServletResponseWrapper;

/** Covers RequestFilter postprocessing as well as the handler. */
final class DelegatedResponse extends HttpServletResponseWrapper {
    private final int limit;
    private final String sessionId;
    private final ByteArrayOutputStream body = new ByteArrayOutputStream();
    private PrintWriter writer;
    private boolean streaming;
    private boolean overflow;
    private boolean applicationCommitted;
    private final ServletOutputStream buffered =
            new ServletOutputStream() {
                @Override
                public boolean isReady() {
                    return true;
                }

                @Override
                public void setWriteListener(WriteListener listener) {
                    throw new IllegalStateException("Delegated async output is unsupported");
                }

                @Override
                public void write(int value) throws IOException {
                    if (body.size() >= limit) {
                        overflow = true;
                        throw new IOException("Delegated response limit");
                    }
                    body.write(value);
                }

                @Override
                public void write(byte[] bytes, int offset, int length) throws IOException {
                    if (length > limit - body.size()) {
                        overflow = true;
                        throw new IOException("Delegated response limit");
                    }
                    body.write(bytes, offset, length);
                }

                @Override
                public void flush() {
                    applicationCommitted = true;
                }
            };

    DelegatedResponse(HttpServletResponse response, String sessionId) {
        this(response, sessionId, 1_000_000);
    }

    DelegatedResponse(HttpServletResponse response, String sessionId, int limit) {
        super(response);
        if (limit <= 0 || limit > 10 * 1024 * 1024) throw new IllegalArgumentException();
        this.limit = limit;
        if (sessionId == null || sessionId.isEmpty()) throw new IllegalArgumentException();
        this.sessionId = sessionId;
    }

    @Override
    public ServletOutputStream getOutputStream() {
        if (writer != null) throw new IllegalStateException();
        streaming = true;
        return buffered;
    }

    @Override
    public PrintWriter getWriter() throws IOException {
        if (streaming) throw new IllegalStateException();
        if (writer == null)
            writer = new PrintWriter(new OutputStreamWriter(buffered, getCharacterEncoding()));
        return writer;
    }

    // Nothing reaches the connection until the outer guard has checked the
    // complete opaque response, including native filter postprocessing. Native
    // Portal error/debug views can otherwise expose authenticated session IDs.
    @Override
    public void flushBuffer() {
        if (writer != null) writer.flush();
        applicationCommitted = true;
    }

    @Override
    public void resetBuffer() {
        if (applicationCommitted) throw new IllegalStateException();
        if (writer != null) writer.flush();
        body.reset();
        applicationCommitted = false;
    }

    @Override
    public boolean isCommitted() {
        return applicationCommitted;
    }

    @Override
    public void sendError(int status) {
        resetBuffer();
        setStatus(status);
        applicationCommitted = true;
    }

    @Override
    public void sendError(int status, String message) {
        sendError(status);
    }

    @Override
    public void sendRedirect(String url) {
        resetBuffer();
        setStatus(SC_FOUND);
        setHeader("Location", url);
        applicationCommitted = true;
    }

    void finish() throws IOException {
        flushBuffer();
        boolean unsafe =
                overflow
                        || !java.util.Set.of("UTF-8", "ISO-8859-1", "US-ASCII")
                                .contains(
                                        getCharacterEncoding().toUpperCase(java.util.Locale.ROOT));
        String encoding = getHeader("Content-Encoding");
        unsafe |= encoding != null && !"identity".equalsIgnoreCase(encoding);
        unsafe |= new String(body.toByteArray(), StandardCharsets.ISO_8859_1).contains(sessionId);
        for (String name : getHeaderNames())
            for (String value : getHeaders(name)) unsafe |= value.contains(sessionId);
        if (unsafe) {
            super.reset();
            super.setStatus(SC_BAD_GATEWAY);
            super.setHeader("Cache-Control", "no-store");
            return;
        }
        super.getOutputStream().write(body.toByteArray());
    }

    private boolean credential(String name) {
        return "Set-Cookie".equalsIgnoreCase(name)
                || "Set-Cookie2".equalsIgnoreCase(name)
                || "X-Sakai-Session".equalsIgnoreCase(name);
    }

    @Override
    public void addCookie(Cookie cookie) {}

    @Override
    public void setHeader(String name, String value) {
        if (!credential(name))
            super.setHeader(name, "Cache-Control".equalsIgnoreCase(name) ? "no-store" : value);
    }

    @Override
    public void addHeader(String name, String value) {
        if ("Cache-Control".equalsIgnoreCase(name)) super.setHeader(name, "no-store");
        else if (!credential(name)) super.addHeader(name, value);
    }

    @Override
    public void setIntHeader(String name, int value) {
        if ("Cache-Control".equalsIgnoreCase(name)) super.setHeader(name, "no-store");
        else if (!credential(name)) super.setIntHeader(name, value);
    }

    @Override
    public void addIntHeader(String name, int value) {
        if ("Cache-Control".equalsIgnoreCase(name)) super.setHeader(name, "no-store");
        else if (!credential(name)) super.addIntHeader(name, value);
    }

    @Override
    public void setDateHeader(String name, long value) {
        if ("Cache-Control".equalsIgnoreCase(name)) super.setHeader(name, "no-store");
        else if (!credential(name)) super.setDateHeader(name, value);
    }

    @Override
    public void addDateHeader(String name, long value) {
        if ("Cache-Control".equalsIgnoreCase(name)) super.setHeader(name, "no-store");
        else if (!credential(name)) super.addDateHeader(name, value);
    }

    @Override
    public void reset() {
        if (applicationCommitted) throw new IllegalStateException();
        body.reset();
        writer = null;
        streaming = false;
        super.reset();
        super.setHeader("Cache-Control", "no-store");
    }

    @Override
    public String encodeURL(String url) {
        return url;
    }

    @Override
    public String encodeRedirectURL(String url) {
        return url;
    }

    @Override
    public String encodeUrl(String url) {
        return url;
    }

    @Override
    public String encodeRedirectUrl(String url) {
        return url;
    }
}
