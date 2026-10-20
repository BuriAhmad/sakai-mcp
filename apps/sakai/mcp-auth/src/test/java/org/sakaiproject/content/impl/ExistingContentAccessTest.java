/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.content.impl;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.ContentFilterService;
import org.sakaiproject.entity.api.*;
import org.sakaiproject.event.api.EventTrackingService;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.mock.web.*;
import org.springframework.test.util.ReflectionTestUtils;

/** Characterize the unchanged native handler, with explicit synthetic ACL/storage collaborators. */
public class ExistingContentAccessTest {
    private BaseContentService service;
    private BaseContentService.BaseResourceEdit resource;
    private Reference reference;
    private ResourceProperties properties;
    private ContentFilterService filters;
    private MockHttpServletRequest request;
    private MockHttpServletResponse response;
    private final String id = "/attachment/course-a/Assignments/opaque/answers.txt";
    private final byte[] bytes = "A\r\nB\n\u00e9\n".getBytes(StandardCharsets.UTF_8);

    @Before
    public void setup() throws Exception {
        service = mock(BaseContentService.class, CALLS_REAL_METHODS);
        resource = mock(BaseContentService.BaseResourceEdit.class);
        reference = mock(Reference.class);
        properties = mock(ResourceProperties.class);
        filters = mock(ContentFilterService.class);
        service.contentFilterService = filters;
        service.sessionManager = mock(SessionManager.class);
        when(service.sessionManager.getCurrentSessionUserId()).thenReturn("uid-a");
        service.serverConfigurationService = mock(ServerConfigurationService.class);
        when(service.serverConfigurationService.getBoolean(anyString(), anyBoolean()))
                .thenAnswer(i -> i.getArgument(1));
        service.m_storage = mock(BaseContentService.Storage.class);
        ReflectionTestUtils.setField(service, "eventTrackingService", mock(EventTrackingService.class));
        when(reference.getId()).thenReturn(id);
        when(reference.getReference()).thenReturn("/content" + id);
        doReturn(true).when(service).allowGetResource(id);
        doReturn(resource).when(service).getResource(id);
        when(resource.getId()).thenReturn(id);
        when(resource.getReference()).thenReturn("/content" + id);
        when(resource.getContentLength()).thenReturn((long) bytes.length);
        when(resource.getContentType()).thenReturn("text/plain");
        when(resource.getProperties()).thenReturn(properties);
        var collection = mock(org.sakaiproject.content.api.ContentCollection.class);
        when(collection.getProperties()).thenReturn(properties);
        when(resource.getContainingCollection()).thenReturn(collection);
        when(resource.streamContent()).thenAnswer(i -> new ByteArrayInputStream(bytes));
        when(filters.wrap(resource)).thenReturn(resource);
        request = new MockHttpServletRequest("GET", "/access/content" + id);
        response = new MockHttpServletResponse();
    }

    // Reuse the same synthetic native collaborators in the separately invoked audit.
    public org.sakaiproject.entity.api.HttpAccess handlerForProof() {
        return (request, response, ref, accepted) ->
                service.handleAccessResource(request, response, ref, accepted);
    }

    public Reference referenceForProof() { return reference; }

    public void useSessionsForProof(SessionManager sessions) { service.sessionManager = sessions; }

    public void denyForProof() { doReturn(false).when(service).allowGetResource(id); }

    private void read() throws Exception {
        service.handleAccessResource(request, response, reference, List.of());
    }

    @Test
    public void exactStreamBytesAndNativeMimeArePreserved() throws Exception {
        read();
        assertArrayEquals(bytes, response.getContentAsByteArray());
        assertEquals("text/plain; charset=UTF-8", response.getContentType());
        assertEquals(bytes.length, response.getContentLength());
        assertNotNull(response.getHeader("Content-Disposition"));
        verify(service).allowGetResource(id);
        verify(filters).wrap(resource);
    }

    @Test
    public void nativeAclDenialPrecedesResourceAndFilterRead() throws Exception {
        doReturn(false).when(service).allowGetResource(id);
        assertThrows(EntityPermissionException.class, this::read);
        verify(service, never()).getResource(id);
        verifyNoInteractions(filters);
        assertEquals(0, response.getContentAsByteArray().length);
    }

    @Test
    public void copyrightIsNotAutomaticallyAccepted() throws Exception {
        when(resource.requiresCopyrightAgreement()).thenReturn(true);
        assertThrows(EntityCopyrightException.class, this::read);
        verifyNoInteractions(filters);
        assertEquals(0, response.getContentAsByteArray().length);
    }

    @Test
    public void nativeOutputFilterCanChangeDeliveredBytes() throws Exception {
        var wrapped = mock(org.sakaiproject.content.api.ContentResource.class);
        byte[] changed = "filtered".getBytes(StandardCharsets.UTF_8);
        when(filters.wrap(resource)).thenReturn(wrapped);
        when(wrapped.getId()).thenReturn(id);
        when(wrapped.getProperties()).thenReturn(properties);
        var collection = resource.getContainingCollection();
        when(wrapped.getContainingCollection()).thenReturn(collection);
        when(wrapped.getContentLength()).thenReturn((long) changed.length);
        when(wrapped.getContentType()).thenReturn("text/plain");
        when(wrapped.streamContent()).thenReturn(new ByteArrayInputStream(changed));
        read();
        assertArrayEquals(changed, response.getContentAsByteArray());
        assertFalse(java.util.Arrays.equals(bytes, response.getContentAsByteArray()));
    }

    @Test
    public void truncatedNativeStreamMayStillReturnSuccess() throws Exception {
        when(resource.streamContent()).thenReturn(new ByteArrayInputStream(new byte[] {65}));
        read();
        assertEquals(200, response.getStatus());
        assertEquals(bytes.length, response.getContentLength());
        assertEquals(1, response.getContentAsByteArray().length);
    }

    @Test
    public void directStorageCanRedirectAwayFromSakai() throws Exception {
        when(service.m_storage.getDirectLink(resource)).thenReturn(URI.create("https://storage.invalid/file"));
        read();
        assertEquals(302, response.getStatus());
        assertEquals("https://storage.invalid/file", response.getRedirectedUrl());
        assertEquals(0, response.getContentAsByteArray().length);
        verify(resource, never()).streamContent();
    }
    @Test
    public void configuredDefaultHtmlFilterLeavesPlainTextAndPdfUntouched() {
        var actual = new ContentFilterServiceImpl();
        actual.setOutputFilters(List.of(new HtmlPageFilter()));
        for (String mime : List.of("text/plain", "application/pdf")) {
            when(resource.getContentType()).thenReturn(mime);
            assertSame(resource, actual.wrap(resource));
        }
    }

    @Test
    public void urlResourcesRedirectWithoutStreamingFileBytes() throws Exception {
        byte[] url = "https://outside.invalid/answer".getBytes(StandardCharsets.UTF_8);
        when(resource.getContentLength()).thenReturn((long) url.length);
        when(resource.getContentType()).thenReturn(ResourceProperties.TYPE_URL);
        when(resource.getContent()).thenReturn(url);
        read();
        assertEquals(302, response.getStatus());
        assertEquals("https://outside.invalid/answer", response.getRedirectedUrl());
        verify(resource, never()).streamContent();
    }

    @Test
    public void storageSendfileCanReturnSuccessWithoutInProcessBytes() throws Exception {
        when(service.m_storage.getDirectLink(resource)).thenReturn(URI.create("https://storage.invalid/file"));
        when(service.serverConfigurationService.getBoolean("cloud.content.sendfile", false)).thenReturn(true);
        read();
        assertEquals(200, response.getStatus());
        assertNotNull(response.getHeader("X-Sendfile"));
        assertEquals(bytes.length, response.getContentLength());
        assertEquals(0, response.getContentAsByteArray().length);
        verify(resource, never()).streamContent();
    }

}
