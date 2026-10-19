/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.assignmentRef;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.id;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.AssignmentServiceConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/** Request-local actor, site, assignment and group authorization. */
@Service
public class McpGradingAuthorization {
    private final AssignmentService assignments;
    private final GradingService grading;
    private final SessionManager sessions;
    private final SiteService sites;
    private final SecurityService security;
    private final ServerConfigurationService config;
    private final RubricsService rubrics;

    public McpGradingAuthorization(
            AssignmentService assignments,
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            @Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessions,
            SiteService sites,
            SecurityService security,
            ServerConfigurationService config,
            RubricsService rubrics) {
        this.assignments = assignments;
        this.grading = grading;
        this.sessions = sessions;
        this.sites = sites;
        this.security = security;
        this.config = config;
        this.rubrics = rubrics;
    }

    String actor() {
        String actor = sessions.getCurrentSession().getUserId();
        if (actor == null || actor.isBlank()) throw failure(HttpStatus.UNAUTHORIZED);
        return actor;
    }

    Assignment assignment(String site, String id) {
        if (!config.getBoolean("mcp.assignment.grading.enabled", false))
            throw failure(HttpStatus.NOT_FOUND);
        actor();
        try {
            Site course = sites.getSiteVisit(site);
            if (!"course".equals(course.getType())) throw failure(HttpStatus.NOT_FOUND);
            Assignment a = assignments.getAssignmentWithGradingEvidence(id);
            if (!site.equals(a.getContext())
                    || Boolean.TRUE.equals(a.getDeleted())
                    || Boolean.TRUE.equals(a.getDraft())) throw failure(HttpStatus.NOT_FOUND);
            if (!assignments.allowGradeSubmission(assignmentRef(a)))
                throw failure(HttpStatus.FORBIDDEN);
            return a;
        } catch (PermissionException e) {
            throw failure(HttpStatus.FORBIDDEN);
        } catch (IdUnusedException e) {
            throw failure(HttpStatus.NOT_FOUND);
        }
    }

    boolean siteGrader(Assignment a) {
        return security.unlock(
                AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION,
                SiteService.REFERENCE_ROOT + "/" + a.getContext());
    }

    Set<String> scope(Assignment a) {
        if (siteGrader(a)) return null;
        Set<String> permitted =
                assignments.getGroupsAllowGradeAssignment(assignmentRef(a)).stream()
                        .flatMap(g -> g.getUsers().stream())
                        .collect(Collectors.toSet());
        if (permitted.isEmpty()) throw failure(HttpStatus.FORBIDDEN);
        return permitted;
    }

    boolean allowed(Assignment a, AssignmentSubmission sub) {
        Set<String> scope = scope(a);
        if (scope == null) return true;
        if (sub.getGroupId() != null
                && assignments.getGroupsAllowGradeAssignment(assignmentRef(a)).stream()
                        .noneMatch(g -> sub.getGroupId().equals(g.getId()))) return false;
        return !sub.getSubmitters().isEmpty()
                && sub.getSubmitters().stream().allMatch(s -> scope.contains(s.getSubmitter()));
    }

    AssignmentSubmission submission(Assignment a, String id) {
        try {
            AssignmentSubmission s = assignments.getSubmissionWithGradingEvidence(id);
            if (s == null) throw failure(HttpStatus.NOT_FOUND);
            if (!a.getId().equals(s.getAssignment().getId())) throw failure(HttpStatus.NOT_FOUND);
            if (!allowed(a, s)) throw failure(HttpStatus.FORBIDDEN);
            return s;
        } catch (PermissionException e) {
            throw failure(HttpStatus.FORBIDDEN);
        }
    }

    List<String> unsupported(Assignment a) {
        List<String> reasons = new ArrayList<>();
        if (Boolean.TRUE.equals(a.getIsGroup()) || a.getTypeOfAccess() != Assignment.Access.SITE)
            reasons.add("group_assignment");
        if (assignments.assignmentUsesAnonymousGrading(a)) reasons.add("anonymous_grading");
        if (a.getTypeOfGrade() != Assignment.GradeType.SCORE_GRADE_TYPE)
            reasons.add("non_point_grade");
        if (Boolean.TRUE.equals(a.getAllowPeerAssessment())) reasons.add("peer_assessment");
        if (a.getTypeOfSubmission() == null || a.getTypeOfSubmission().ordinal() > 5)
            reasons.add("external_submission");
        if (rubrics.hasAssociatedRubric(AssignmentConstants.TOOL_ID, a.getId()))
            reasons.add("rubric_integration");
        return reasons;
    }

    void identityRead(Assignment a) {
        if (assignments.assignmentUsesAnonymousGrading(a))
            throw failure(HttpStatus.NOT_IMPLEMENTED);
    }
}
