/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpCourseControllerTest {

    private SiteService sites;
    private AnnouncementService announcements;
    private McpCourseController controller;

    @Before
    public void setup() {
        SessionManager sessions = mock(SessionManager.class);
        Session session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session);
        when(session.getUserId()).thenReturn("student-a");
        sites = mock(SiteService.class);
        announcements = mock(AnnouncementService.class);
        controller = new McpCourseController(sessions, sites, announcements);
    }

    @Test
    public void deniesUnrelatedCourseBeforeReadingAnnouncements() throws Exception {
        when(sites.getSiteVisit("course-b"))
                .thenThrow(new PermissionException("student-a", "site.visit", "course-b"));
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> controller.announcements("course-b"));
        assertEquals(HttpStatus.FORBIDDEN, failure.getStatus());
        verifyNoInteractions(announcements);
    }

    @Test
    public void courseListExcludesUnvisitableSite() throws Exception {
        Site own = mock(Site.class);
        Site unrelated = mock(Site.class);
        when(own.getId()).thenReturn("course-a");
        when(own.getTitle()).thenReturn("Course A");
        when(own.getType()).thenReturn("course");
        when(unrelated.getId()).thenReturn("course-b");
        when(unrelated.getType()).thenReturn("course");
        when(sites.getUserSites()).thenReturn(List.of(own, unrelated));
        when(sites.getSiteVisit("course-a")).thenReturn(own);
        when(sites.getSiteVisit("course-b"))
                .thenThrow(new PermissionException("student-a", "site.visit", "course-b"));
        assertEquals(List.of(new McpCourseController.Course("course-a", "Course A")),
                controller.courses().get("courses"));
    }
}
