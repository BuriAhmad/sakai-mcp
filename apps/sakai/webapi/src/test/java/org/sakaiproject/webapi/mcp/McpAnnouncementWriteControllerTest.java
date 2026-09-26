/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.announcement.api.AnnouncementChannel;
import org.sakaiproject.announcement.api.AnnouncementMessageEdit;
import org.sakaiproject.announcement.api.AnnouncementMessageHeader;
import org.sakaiproject.announcement.api.AnnouncementMessageHeaderEdit;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.UserDirectoryService;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpAnnouncementWriteControllerTest {

    private SiteService sites;
    private AnnouncementService announcements;
    private AnnouncementChannel channel;
    private McpAnnouncementWriteController controller;

    @Before
    public void setup() throws Exception {
        SessionManager sessions = mock(SessionManager.class);
        Session session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session);
        when(session.getUserId()).thenReturn("instructor-a");
        sites = mock(SiteService.class);
        Site site = mock(Site.class);
        when(sites.getSiteVisit("course-a")).thenReturn(site);
        when(site.getType()).thenReturn("course");
        announcements = mock(AnnouncementService.class);
        when(announcements.channelReference("course-a", SiteService.MAIN_CONTAINER)).thenReturn("main-channel");
        channel = mock(AnnouncementChannel.class);
        when(announcements.getAnnouncementChannel("main-channel")).thenReturn(channel);
        FormattedText text = mock(FormattedText.class);
        when(text.escapeHtml(any(String.class), anyBoolean())).thenAnswer(inv -> inv.getArgument(0));
        controller = new McpAnnouncementWriteController(sessions, sites, announcements,
                mock(UserDirectoryService.class), text);
    }

    @Test
    public void unrelatedCourseCannotBeTargeted() throws Exception {
        when(sites.getSiteVisit("course-b"))
                .thenThrow(new PermissionException("instructor-a", "site.visit", "course-b"));
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> controller.create("course-b", new McpAnnouncementWriteController.CreateAnnouncement(
                        "Week 4 update", "The lab is open.")));
        assertEquals(HttpStatus.FORBIDDEN, failure.getStatus());
        verifyNoInteractions(announcements);
    }

    @Test
    public void studentWithoutAnnouncementCreatePermissionIsDenied() throws Exception {
        when(channel.addAnnouncementMessage())
                .thenThrow(new PermissionException("student-a", "annc.new", "main-channel"));
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> controller.create("course-a", new McpAnnouncementWriteController.CreateAnnouncement(
                        "Week 4 update", "The lab is open.")));
        assertEquals(HttpStatus.FORBIDDEN, failure.getStatus());
    }

    @Test
    public void permittedInstructorCreatesExactlyOnePostedAnnouncement() throws Exception {
        AnnouncementMessageEdit edit = mock(AnnouncementMessageEdit.class);
        AnnouncementMessageHeaderEdit header = mock(AnnouncementMessageHeaderEdit.class);
        when(channel.addAnnouncementMessage()).thenReturn(edit);
        when(edit.getAnnouncementHeaderEdit()).thenReturn(header);
        when(edit.getAnnouncementHeader()).thenReturn(mock(AnnouncementMessageHeader.class));
        when(edit.getId()).thenReturn("new-announcement");
        assertEquals(HttpStatus.CREATED, controller.create("course-a",
                new McpAnnouncementWriteController.CreateAnnouncement("Week 4 update", "The lab is open."))
                        .getStatusCode());
        verify(header).setDraft(false);
        verify(channel).commitMessage(edit);
    }
}
