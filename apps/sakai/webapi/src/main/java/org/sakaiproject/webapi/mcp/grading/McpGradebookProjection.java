/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.assignmentRef;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.string;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.grading.api.GradingAuthz;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.SortType;
import org.sakaiproject.site.api.SiteService;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/** Permission-aware owned Gradebook links and target eligibility. */
@Service
public class McpGradebookProjection {
    private final AssignmentService assignments;
    private final GradingService grading;
    private final SiteService sites;
    private final GradingAuthz authz;
    private final McpGradingAuthorization authorization;
    private final McpGradingEvidence evidence;

    public McpGradebookProjection(
            AssignmentService assignments,
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            SiteService sites,
            @Qualifier("org.sakaiproject.grading.api.GradingAuthz") GradingAuthz authz,
            McpGradingAuthorization authorization,
            McpGradingEvidence evidence) {
        this.assignments = assignments;
        this.grading = grading;
        this.sites = sites;
        this.authz = authz;
        this.authorization = authorization;
        this.evidence = evidence;
    }

    org.sakaiproject.grading.api.Assignment linked(Assignment a) {
        if (!grading.isGradebookInitialized(a.getContext())) return null;
        if (grading.isGradebookGroupEnabled(a.getContext()))
            throw failure(HttpStatus.NOT_IMPLEMENTED);
        String association =
                a.getProperties()
                        .get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT);
        var items = grading.getAssignments(a.getContext(), a.getContext(), SortType.SORT_BY_NONE);
        if (items.size() > 500) throw failure(HttpStatus.BAD_REQUEST);
        List<org.sakaiproject.grading.api.Assignment> matches =
                items.stream()
                        .filter(
                                i ->
                                        assignmentRef(a).equals(i.getExternalId())
                                                || association != null
                                                        && (association.equals(
                                                                        String.valueOf(i.getId()))
                                                                || association.equals(
                                                                        i.getExternalId())))
                        .toList();
        if (matches.size() > 1) throw failure(HttpStatus.CONFLICT);
        if (!matches.isEmpty()
                && association != null
                && !association.equals(String.valueOf(matches.get(0).getId()))
                && !association.equals(matches.get(0).getExternalId()))
            throw failure(HttpStatus.CONFLICT);
        return matches.isEmpty() ? null : matches.get(0);
    }

    Map<String, Object> link(Assignment a) {
        try {
            var item = linked(a);
            boolean missing =
                    item == null
                            && a.getProperties()
                                            .get(
                                                    AssignmentConstants
                                                            .PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT)
                                    != null;
            return obj(
                    "mode",
                    item == null
                            ? (missing ? "unknown" : "none")
                            : Boolean.TRUE.equals(item.getExternallyMaintained())
                                    ? "external"
                                    : "internal",
                    "gradebook_uid",
                    item == null ? null : a.getContext(),
                    "item_id",
                    item == null ? null : String.valueOf(item.getId()),
                    "external_id",
                    item == null ? null : item.getExternalId(),
                    "released",
                    item == null ? null : item.getReleased(),
                    "counted",
                    item == null ? null : item.getCounted(),
                    "available",
                    !missing,
                    "reason",
                    missing ? "missing_link" : null);
        } catch (RuntimeException e) {
            return obj(
                    "mode",
                    "unknown",
                    "gradebook_uid",
                    null,
                    "item_id",
                    null,
                    "external_id",
                    null,
                    "released",
                    null,
                    "counted",
                    null,
                    "available",
                    false,
                    "reason",
                    "projection_unavailable");
        }
    }

    void writable(Assignment a) {
        if (!authorization.unsupported(a).isEmpty() || !authorization.siteGrader(a))
            throw failure(HttpStatus.NOT_IMPLEMENTED);
        var item = linked(a);
        if (item == null
                && a.getProperties()
                                .get(
                                        AssignmentConstants
                                                .PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT)
                        != null) throw failure(HttpStatus.CONFLICT);
        if (item != null
                && (!Boolean.TRUE.equals(item.getExternallyMaintained())
                        || !assignmentRef(a).equals(item.getExternalId())
                        || BigDecimal.valueOf(item.getPoints())
                                        .compareTo(
                                                new BigDecimal(a.getMaxGradePoint())
                                                        .divide(
                                                                BigDecimal.valueOf(
                                                                        a.getScaleFactor())))
                                != 0)) throw failure(HttpStatus.NOT_IMPLEMENTED);
    }

    void writeTarget(Assignment a, AssignmentSubmission s, Map<String, Object> row) {
        target(a, s, row);
        String uid = string(row, "sakai_user_id");
        try {
            if (!sites.getSiteVisit(a.getContext()).getUsers().contains(uid)
                    || assignments.allowAddSubmissionUsers(assignmentRef(a)).stream()
                            .noneMatch(u -> uid.equals(u.getId())))
                throw failure(HttpStatus.FORBIDDEN);
        } catch (Exception e) {
            throw failure(HttpStatus.FORBIDDEN);
        }
    }

    void target(Assignment a, AssignmentSubmission s, Map<String, Object> row) {
        if (evidence.submitters(s).size() != 1
                || !evidence.submitters(s).get(0).equals(string(row, "sakai_user_id")))
            throw failure(HttpStatus.CONFLICT);
        var item = linked(a);
        if (item != null
                && !authz.isUserAbleToGradeItemForStudent(
                        a.getContext(), a.getContext(), item.getId(), string(row, "sakai_user_id")))
            throw failure(HttpStatus.FORBIDDEN);
    }
}
