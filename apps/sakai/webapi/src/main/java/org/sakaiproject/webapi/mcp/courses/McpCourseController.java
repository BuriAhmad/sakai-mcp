/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.courses;

import org.sakaiproject.announcement.api.AnnouncementMessage;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/** Narrow, current-user course reads. The filter has already bound the delegated user. */
@RestController
@RequestMapping("/mcp/v1/courses")
public class McpCourseController {

    private final SessionManager sessionManager;
    private final SiteService siteService;
    private final AnnouncementService announcementService;

    @Autowired
    public McpCourseController(
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessionManager,
            SiteService siteService,
            AnnouncementService announcementService) {
        this.sessionManager = sessionManager;
        this.siteService = siteService;
        this.announcementService = announcementService;
    }

    public record Course(String id, String title) {}

    public record Announcement(String id, String title, String body, long postedAt) {}

    @GetMapping
    public Map<String, List<Course>> courses() {
        requireUser();
        List<Course> courses =
                siteService.getUserSites().stream()
                        .filter(site -> "course".equals(site.getType()))
                        .filter(site -> canVisit(site.getId()))
                        .sorted(Comparator.comparing(Site::getTitle).thenComparing(Site::getId))
                        .limit(500)
                        .map(site -> new Course(site.getId(), site.getTitle()))
                        .collect(Collectors.toList());
        return Map.of("courses", courses);
    }

    @GetMapping("/{siteId}/announcements")
    public Map<String, List<Announcement>> announcements(@PathVariable String siteId) {
        requireUser();
        visitCourse(siteId);
        String channel = announcementService.channelReference(siteId, SiteService.MAIN_CONTAINER);
        try {
            List<Announcement> announcements =
                    announcementService
                            .getMessages(
                                    channel,
                                    announcementService.getMaxAgeInDaysAndAmountFilter(3650, 100),
                                    false,
                                    false)
                            .stream()
                            .filter(announcementService::isMessageViewable)
                            .limit(50)
                            .map(this::announcement)
                            .collect(Collectors.toList());
            return Map.of("announcements", announcements);
        } catch (IdUnusedException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        } catch (PermissionException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
    }

    private Announcement announcement(AnnouncementMessage message) {
        return new Announcement(
                message.getId(),
                message.getAnnouncementHeader().getSubject(),
                message.getBody(),
                message.getAnnouncementHeader().getDate().getTime());
    }

    private String requireUser() {
        String userId = sessionManager.getCurrentSession().getUserId();
        if (userId == null || userId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        }
        return userId;
    }

    private boolean canVisit(String siteId) {
        try {
            siteService.getSiteVisit(siteId);
            return true;
        } catch (IdUnusedException | PermissionException e) {
            return false;
        }
    }

    private Site visitCourse(String siteId) {
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
        return site;
    }
}
