/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.courses;

import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.Assignment;
import org.sakaiproject.grading.api.GradeDefinition;
import org.sakaiproject.grading.api.GradingAuthz;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.SortType;
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

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/** Returns gradebook grades for exactly the delegated current user. */
@RestController
@RequestMapping("/mcp/v1/courses/{siteId}/grades")
public class McpGradesController {

    private final SessionManager sessionManager;
    private final SiteService siteService;
    private final SecurityService securityService;
    private final GradingService gradingService;

    @Autowired
    public McpGradesController(
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessionManager,
            SiteService siteService,
            SecurityService securityService,
            @Qualifier("org.sakaiproject.grading.api.GradingService")
                    GradingService gradingService) {
        this.sessionManager = sessionManager;
        this.siteService = siteService;
        this.securityService = securityService;
        this.gradingService = gradingService;
    }

    public record OwnGrade(long itemId, String title, String score, Double pointsPossible) {}

    @GetMapping("/me")
    public Map<String, List<OwnGrade>> ownGrades(@PathVariable String siteId) {
        String userId = sessionManager.getCurrentSession().getUserId();
        if (userId == null || userId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
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
        if (!securityService.unlock(GradingAuthz.PERMISSION_VIEW_OWN_GRADES, site.getReference())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        List<Assignment> visible =
                gradingService
                        .getViewableAssignmentsForCurrentUser(siteId, siteId, SortType.SORT_BY_NONE)
                        .stream()
                        .filter(a -> Boolean.TRUE.equals(a.getReleased()))
                        .limit(500)
                        .collect(Collectors.toList());
        if (visible.isEmpty()) {
            return Map.of("grades", List.of());
        }
        List<Long> itemIds = visible.stream().map(Assignment::getId).collect(Collectors.toList());
        // Passing only the current session's user ID prevents grader permissions
        // from widening the response to other students.
        Map<Long, List<GradeDefinition>> definitions =
                gradingService.getGradesWithoutCommentsForStudentsForItems(
                        siteId, siteId, itemIds, List.of(userId));
        List<OwnGrade> grades =
                visible.stream()
                        .map(
                                item -> {
                                    List<GradeDefinition> own =
                                            definitions
                                                    .getOrDefault(
                                                            item.getId(), Collections.emptyList())
                                                    .stream()
                                                    .filter(
                                                            grade ->
                                                                    Objects.equals(
                                                                            userId,
                                                                            grade.getStudentUid()))
                                                    .collect(Collectors.toList());
                                    String score = own.isEmpty() ? null : own.get(0).getGrade();
                                    return new OwnGrade(
                                            item.getId(), item.getName(), score, item.getPoints());
                                })
                        .collect(Collectors.toList());
        return Map.of("grades", grades);
    }
}
