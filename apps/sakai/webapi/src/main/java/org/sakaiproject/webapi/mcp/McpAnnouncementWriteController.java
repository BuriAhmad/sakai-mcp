/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp;

import java.util.Map;

import org.sakaiproject.announcement.api.AnnouncementChannel;
import org.sakaiproject.announcement.api.AnnouncementMessageEdit;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.UserDirectoryService;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** The only V1 mutation: one plain, posted announcement in the site's main channel. */
@RestController
@RequestMapping("/mcp/v1/courses/{siteId}/announcements")
public class McpAnnouncementWriteController {

    private final SessionManager sessionManager;
    private final SiteService siteService;
    private final AnnouncementService announcementService;
    private final UserDirectoryService users;
    private final FormattedText formattedText;

    @Autowired
    public McpAnnouncementWriteController(
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessionManager,
            SiteService siteService, AnnouncementService announcementService, UserDirectoryService users,
            FormattedText formattedText) {
        this.sessionManager = sessionManager;
        this.siteService = siteService;
        this.announcementService = announcementService;
        this.users = users;
        this.formattedText = formattedText;
    }

    public record CreateAnnouncement(String title, String body) {}
    public record CreatedAnnouncement(String id, String courseId, String title, Long postedAt) {}

    @PostMapping
    public ResponseEntity<Map<String, CreatedAnnouncement>> create(@PathVariable String siteId,
            @RequestBody CreateAnnouncement input) {
        String userId = sessionManager.getCurrentSession().getUserId();
        if (userId == null || userId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        }
        if (input == null || input.title() == null || input.title().isBlank() || input.title().length() > 200
                || input.body() == null || input.body().isBlank() || input.body().length() > 10_000) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        }
        Site site;
        try {
            site = siteService.getSiteVisit(siteId);
        } catch (IdUnusedException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        } catch (PermissionException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        if (!"course".equals(site.getType())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        String channelReference = announcementService.channelReference(siteId, SiteService.MAIN_CONTAINER);
        AnnouncementChannel channel;
        try {
            channel = announcementService.getAnnouncementChannel(channelReference);
        } catch (IdUnusedException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        } catch (PermissionException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        AnnouncementMessageEdit edit;
        try {
            edit = channel.addAnnouncementMessage(); // service checks annc.new
        } catch (PermissionException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        boolean commitAttempted = false;
        try {
            edit.setBody(formattedText.escapeHtml(input.body(), true));
            edit.getAnnouncementHeaderEdit().setSubject(formattedText.escapeHtml(input.title(), false));
            edit.getAnnouncementHeaderEdit().setDraft(false);
            edit.getAnnouncementHeaderEdit().setFrom(users.getCurrentUser());
            commitAttempted = true;
            channel.commitMessage(edit);
            Long postedAt = edit.getAnnouncementHeader().getDate() == null ? null
                    : edit.getAnnouncementHeader().getDate().getTime();
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("announcement",
                    new CreatedAnnouncement(edit.getId(), siteId, input.title(), postedAt)));
        } finally {
            if (!commitAttempted) {
                channel.cancelMessage(edit);
            }
        }
    }
}
