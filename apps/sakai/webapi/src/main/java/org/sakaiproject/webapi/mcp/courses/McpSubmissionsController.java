/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.courses;

import org.sakaiproject.assignment.api.AssignmentReferenceReckoner;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.AssignmentServiceConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.assignment.api.model.AssignmentSubmissionSubmitter;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.site.api.Group;
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

import java.time.Instant;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/** Minimal submission metadata for authorized site or group graders. */
@RestController
@RequestMapping("/mcp/v1/courses/{siteId}/assignments")
public class McpSubmissionsController {

    private final SessionManager sessionManager;
    private final SiteService siteService;
    private final AssignmentService assignmentService;
    private final SecurityService securityService;

    @Autowired
    public McpSubmissionsController(
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessionManager,
            SiteService siteService,
            AssignmentService assignmentService,
            SecurityService securityService) {
        this.sessionManager = sessionManager;
        this.siteService = siteService;
        this.assignmentService = assignmentService;
        this.securityService = securityService;
    }

    public record Submission(String id, List<String> submitterIds, Instant submittedAt) {}

    @GetMapping("/{assignmentId}/submissions")
    public Map<String, List<Submission>> submissions(
            @PathVariable String siteId, @PathVariable String assignmentId) {
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
        Assignment assignment;
        try {
            assignment = assignmentService.getAssignment(assignmentId);
        } catch (IdUnusedException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        } catch (PermissionException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        if (!siteId.equals(assignment.getContext())
                || Boolean.TRUE.equals(assignment.getDeleted())
                || Boolean.TRUE.equals(assignment.getDraft())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        String reference =
                AssignmentReferenceReckoner.reckoner()
                        .assignment(assignment)
                        .reckon()
                        .getReference();
        if (!assignmentService.allowGradeSubmission(reference)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        boolean siteGrader =
                securityService.unlock(
                        AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION,
                        site.getReference());
        Collection<Group> allowedGroups =
                siteGrader ? List.of() : assignmentService.getGroupsAllowGradeAssignment(reference);
        if (!siteGrader && allowedGroups.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        Set<String> allowedGroupIds =
                allowedGroups.stream().map(Group::getId).collect(Collectors.toSet());
        Set<String> allowedUserIds =
                allowedGroups.stream()
                        .flatMap(g -> g.getUsers().stream())
                        .collect(Collectors.toSet());
        List<Submission> result =
                assignmentService.getSubmissions(assignment).stream()
                        .filter(submission -> Boolean.TRUE.equals(submission.getSubmitted()))
                        .filter(
                                submission ->
                                        siteGrader
                                                || allowedSubmission(
                                                        submission,
                                                        allowedGroupIds,
                                                        allowedUserIds))
                        .sorted(
                                Comparator.comparing(
                                                AssignmentSubmission::getDateSubmitted,
                                                Comparator.nullsLast(Comparator.naturalOrder()))
                                        .thenComparing(AssignmentSubmission::getId))
                        .limit(100)
                        .map(
                                submission ->
                                        new Submission(
                                                submission.getId(),
                                                submission.getSubmitters().stream()
                                                        .map(
                                                                AssignmentSubmissionSubmitter
                                                                        ::getSubmitter)
                                                        .sorted()
                                                        .collect(Collectors.toList()),
                                                submission.getDateSubmitted()))
                        .collect(Collectors.toList());
        return Map.of("submissions", result);
    }

    private static boolean allowedSubmission(
            AssignmentSubmission submission, Set<String> groupIds, Set<String> userIds) {
        if (submission.getGroupId() != null && !groupIds.contains(submission.getGroupId())) {
            return false;
        }
        return !submission.getSubmitters().isEmpty()
                && submission.getSubmitters().stream()
                        .allMatch(s -> userIds.contains(s.getSubmitter()));
    }
}
