/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.announcement.entityprovider;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import org.azeckoski.reflectutils.transcoders.JSONTranscoder;
import org.junit.Test;
import org.sakaiproject.announcement.api.*;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.authz.api.Member;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.entity.api.*;
import org.sakaiproject.entitybroker.EntityView;
import org.sakaiproject.site.api.*;
import org.sakaiproject.time.api.TimeService;
import org.sakaiproject.tool.api.SessionManager;

import java.util.*;

/** Existing provider/codec characterization, without academic mutations. */
public class ExistingAnnouncementActionTest {
    @Test
    public void nativeReadRequiresPermissionAndMapsMainChannelMessageAndDate() throws Exception {
        AnnouncementEntityProviderImpl provider = new AnnouncementEntityProviderImpl();
        SessionManager sessions = mock(SessionManager.class);
        SecurityService security = mock(SecurityService.class);
        SiteService sites = mock(SiteService.class);
        AnnouncementService announcements = mock(AnnouncementService.class);
        TimeService times = mock(TimeService.class);
        EntityManager entities = mock(EntityManager.class);
        ServerConfigurationService configuration = mock(ServerConfigurationService.class);
        provider.setSessionManager(sessions);
        provider.setSecurityService(security);
        provider.setSiteService(sites);
        provider.setAnnouncementService(announcements);
        provider.setTimeService(times);
        provider.setEntityManager(entities);
        provider.setServerConfigurationService(configuration);
        when(sessions.getCurrentSessionUserId()).thenReturn("uid-a");
        when(sites.siteExists("course-a")).thenReturn(true);
        when(sites.siteReference("course-a")).thenReturn("/site/course-a");
        Map<String, Object> query = Map.of("n", "1000", "d", "3650", "a", "0");
        EntityView view = new EntityView("/announcement/site/course-a.json");
        assertThrows(SecurityException.class, () -> provider.getAnnouncementsForSite(view, query));
        verifyNoInteractions(announcements);
        when(security.unlock(AnnouncementService.SECURE_ANNC_READ, "/site/course-a"))
                .thenReturn(true);
        Site site = mock(Site.class);
        when(sites.getSite("course-a")).thenReturn(site);
        when(site.getTitle()).thenReturn("Synthetic course");
        ToolConfiguration placement = mock(ToolConfiguration.class);
        when(site.getToolForCommonId("sakai.announcements")).thenReturn(placement);
        when(placement.getPlacementConfig()).thenReturn(new Properties());
        when(placement.getConfig()).thenReturn(new Properties());
        when(announcements.channelReference("course-a", "main"))
                .thenReturn("/announcement/channel/course-a/main");
        AnnouncementMessage message = mock(AnnouncementMessage.class, RETURNS_DEEP_STUBS);
        when(message.getId()).thenReturn("message-a");
        when(message.getReference()).thenReturn("/announcement/msg/course-a/main/message-a");
        when(message.getAnnouncementHeader().getSubject()).thenReturn("Literal & <title>");
        when(message.getBody()).thenReturn("<p>untrusted</p>\r\n");
        when(message.getAnnouncementHeader().getFrom().getId()).thenReturn("uid-a");
        when(message.getHeader().getDate().getTime()).thenReturn(1790000000123L);
        when(message.getProperties().getPropertyList("selectedRoles")).thenReturn(null);
        when(message.getHeader().getAttachments()).thenReturn(Collections.emptyList());
        Reference ref = mock(Reference.class);
        when(entities.newReference(message.getReference())).thenReturn(ref);
        when(ref.getContext()).thenReturn("course-a");
        when(ref.getContainer()).thenReturn("main");
        when(announcements.getMessages(anyString(), any(), eq(false), eq(false)))
                .thenReturn(List.of(message));
        List<?> result = provider.getAnnouncementsForSite(view, query);
        assertEquals(1, result.size());
        AnnouncementEntityProviderImpl.DecoratedAnnouncement row =
                (AnnouncementEntityProviderImpl.DecoratedAnnouncement) result.get(0);
        assertEquals("message-a", row.getAnnouncementId());
        assertEquals("course-a:main:message-a", row.getId());
        assertEquals("main", row.getChannel());
        assertEquals(1790000000123L, row.getCreatedOn().getTime());
        // The default EntityBroker JSON codec emits java.util.Date as an exact
        // epoch-millisecond number, not a guessed localized or ISO string.
        String json = new JSONTranscoder(true, true, false).encode(row, null, null);
        assertTrue(
                java.util.regex.Pattern.compile("\"createdOn\"\\s*:\\s*1790000000123\\b")
                        .matcher(json)
                        .find());
        when(message.getHeader().getDraft()).thenReturn(true);
        assertTrue(provider.getAnnouncementsForSite(view, query).isEmpty());
        // Selection happens in the existing provider, not Python. A non-owner's
        // role-targeted row can disappear after the native count was applied.
        when(message.getHeader().getDraft()).thenReturn(false);
        when(message.getAnnouncementHeader().getFrom().getId()).thenReturn("other");
        Member member = mock(Member.class);
        org.sakaiproject.authz.api.Role role = mock(org.sakaiproject.authz.api.Role.class);
        when(site.getMember("uid-a")).thenReturn(member);
        when(member.getRole()).thenReturn(role);
        when(role.getId()).thenReturn("Student");
        when(message.getProperties().getPropertyList("selectedRoles")).thenReturn(List.of("Instructor"));
        assertTrue(provider.getAnnouncementsForSite(view, query).isEmpty());
        when(message.getProperties().getPropertyList("selectedRoles")).thenReturn(List.of("Student"));
        assertEquals(1, provider.getAnnouncementsForSite(view, query).size());
        // A failed DTO decoration is swallowed by the unmodified provider.
        when(entities.newReference(message.getReference())).thenThrow(new IllegalStateException("synthetic"));
        assertTrue(provider.getAnnouncementsForSite(view, query).isEmpty());
        // Missing/denied main channel with no public fallback is also an empty
        // observation. Short results cannot prove a complete or empty channel.
        when(announcements.getMessages(anyString(), any(), eq(false), eq(false)))
                .thenThrow(new org.sakaiproject.exception.IdUnusedException("synthetic"));
        assertTrue(provider.getAnnouncementsForSite(view, query).isEmpty());
    }
}
