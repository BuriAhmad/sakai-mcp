/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.assignmentRef;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.stamp;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.count;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.decimal;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.instant;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.AssignmentServiceConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.authz.api.Member;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.user.api.User;
import org.sakaiproject.webapi.mcp.assessment.McpAssessmentService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Retained grading context and its scoped roster dependencies. */
@Service
public class McpGradingQueryService {
    private final AssignmentService assignments;
    private final McpGradingStore store;
    private final SiteService sites;
    private final ServerConfigurationService config;
    private final McpAssessmentService metadata;
    private final McpGradingAuthorization authorization;
    private final McpGradingEvidence evidence;
    private final McpGradebookProjection gradebook;

    public McpGradingQueryService(
            AssignmentService assignments,
            McpGradingStore store,
            SiteService sites,
            ServerConfigurationService config,
            McpAssessmentService metadata,
            McpGradingAuthorization authorization,
            McpGradingEvidence evidence,
            McpGradebookProjection gradebook) {
        this.assignments = assignments;
        this.store = store;
        this.sites = sites;
        this.config = config;
        this.metadata = metadata;
        this.authorization = authorization;
        this.evidence = evidence;
        this.gradebook = gradebook;
    }

    List<Map<String, Object>> roster(Assignment a) {
        authorization.identityRead(a);
        Set<String> scope = authorization.scope(a);
        Site course;
        try {
            course = sites.getSiteVisit(a.getContext());
        } catch (Exception e) {
            throw failure(HttpStatus.FORBIDDEN);
        }
        List<String> eligible =
                assignments.allowAddSubmissionUsers(assignmentRef(a)).stream()
                        .map(User::getId)
                        .filter(id -> scope == null || scope.contains(id))
                        .filter(
                                id -> {
                                    Member member = course.getMember(id);
                                    return member != null
                                            && member.isActive()
                                            && member.getRole() != null
                                            && member.getRole()
                                                    .isAllowed(
                                                            AssignmentServiceConstants
                                                                    .SECURE_ADD_ASSIGNMENT_SUBMISSION)
                                            && !member.getRole()
                                                    .isAllowed(
                                                            AssignmentServiceConstants
                                                                    .SECURE_GRADE_ASSIGNMENT_SUBMISSION);
                                })
                        .sorted()
                        .toList();
        if (eligible.size() > 5000 || assignments.getSubmissions(a).size() > 5000)
            throw failure(HttpStatus.BAD_REQUEST);
        Set<String> active = course.getUsers();
        eligible = eligible.stream().filter(active::contains).toList();
        Map<String, AssignmentSubmission> byUser = new HashMap<>();
        List<AssignmentSubmission> orphan = new ArrayList<>();
        for (AssignmentSubmission s : assignments.getSubmissions(a))
            if (authorization.allowed(a, s)) {
                if (Boolean.TRUE.equals(a.getIsGroup())) {
                    orphan.add(s);
                    continue;
                }
                for (String uid : evidence.submitters(s)) {
                    if (!eligible.contains(uid)) {
                        orphan.add(s);
                        continue;
                    }
                    if (byUser.put(uid, s) != null) throw failure(HttpStatus.CONFLICT);
                }
            }
        List<Map<String, Object>> rows = new ArrayList<>();
        for (String uid : eligible) rows.add(evidence.entry(a, uid, byUser.get(uid), false));
        for (AssignmentSubmission s :
                orphan.stream()
                        .distinct()
                        .sorted(Comparator.comparing(AssignmentSubmission::getId))
                        .toList()) rows.add(evidence.entry(a, null, s, true));
        return rows;
    }

    Map<String, Object> completeness(Assignment a) {
        return obj(
                "complete",
                true,
                "scope",
                authorization.siteGrader(a) ? "site" : "groups",
                "reasons",
                List.of());
    }

    public Map<String, Object> context(String site, String id) {
        Assignment a = authorization.assignment(site, id);
        List<String> reasons = authorization.unsupported(a);
        boolean anonymous = assignments.assignmentUsesAnonymousGrading(a);
        List<Map<String, Object>> rows = anonymous ? List.of() : roster(a);
        var link = gradebook.link(a);
        boolean supported =
                reasons.isEmpty()
                        && authorization.siteGrader(a)
                        && store.configured()
                        && Boolean.TRUE.equals(link.get("available"))
                        && Set.of("none", "external").contains(link.get("mode"));
        if (supported) {
            try {
                gradebook.writable(a);
            } catch (RuntimeException e) {
                supported = false;
                reasons.add("unsupported_gradebook_link");
            }
        }
        if (!store.configured()) reasons.add("storage_not_configured");
        if (!authorization.siteGrader(a)) reasons.add("scoped_write_unsupported");
        return obj(
                "schema_version",
                "1",
                "observed_at",
                stamp(Instant.now()),
                "course",
                obj("id", site, "title", title(site)),
                "assignment",
                obj(
                        "id",
                        id,
                        "title",
                        a.getTitle(),
                        "instructions",
                        a.getInstructions() == null ? "" : a.getInstructions(),
                        "configuration_revision",
                        metadata.revision(a),
                        "grade_type",
                        a.getTypeOfGrade().name(),
                        "max_points",
                        a.getTypeOfGrade() == Assignment.GradeType.SCORE_GRADE_TYPE
                                ? decimal(String.valueOf(a.getMaxGradePoint()), a.getScaleFactor())
                                : null,
                        "scale_factor",
                        a.getScaleFactor(),
                        "submission_type",
                        a.getTypeOfSubmission().name(),
                        "draft",
                        false,
                        "deleted",
                        false,
                        "visible_at",
                        stamp(a.getVisibleDate()),
                        "open_at",
                        stamp(a.getOpenDate()),
                        "due_at",
                        stamp(a.getDueDate()),
                        "close_at",
                        stamp(a.getCloseDate()),
                        "group_submission",
                        Boolean.TRUE.equals(a.getIsGroup()),
                        "anonymous_grading",
                        anonymous,
                        "native_release_grades",
                        Boolean.TRUE.equals(a.getReleaseGrades()),
                        "resubmission_count",
                        count(a.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_NUMBER)),
                        "resubmission_close_at",
                        instant(
                                a.getProperties()
                                        .get(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME)),
                        "definition_reference",
                        null,
                        "definition_version",
                        null,
                        "attachments",
                        evidence.assignmentAttachments(a),
                        "integration_features",
                        reasons),
                "gradebook",
                link,
                "permissions",
                obj(
                        "read_metadata",
                        true,
                        "read_content",
                        !anonymous,
                        "save_grades",
                        supported,
                        "release_grades",
                        supported,
                        "scope",
                        authorization.siteGrader(a) ? "site" : "groups",
                        "scope_complete",
                        authorization.siteGrader(a)),
                "submission_summary",
                obj(
                        "expected_students",
                        anonymous
                                ? null
                                : rows.stream().filter(r -> r.get("student") != null).count(),
                        "submitted",
                        anonymous
                                ? null
                                : rows.stream()
                                        .filter(
                                                r ->
                                                        Set.of("submitted", "ungraded_resubmission")
                                                                .contains(r.get("status")))
                                        .count(),
                        "missing",
                        anonymous
                                ? null
                                : rows.stream()
                                        .filter(r -> "missing".equals(r.get("status")))
                                        .count(),
                        "draft",
                        anonymous
                                ? null
                                : rows.stream()
                                        .filter(r -> "draft".equals(r.get("status")))
                                        .count(),
                        "graded",
                        anonymous
                                ? null
                                : rows.stream().filter(r -> r.get("score") != null).count(),
                        "orphan_records",
                        anonymous
                                ? null
                                : rows.stream()
                                        .filter(r -> "orphan".equals(r.get("status")))
                                        .count()),
                "completeness",
                anonymous
                        ? obj(
                                "complete",
                                false,
                                "scope",
                                authorization.siteGrader(a) ? "site" : "groups",
                                "reasons",
                                List.of("anonymous_grading"))
                        : completeness(a),
                "supported",
                obj(
                        "prepare",
                        !anonymous,
                        "save",
                        supported,
                        "release",
                        supported,
                        "reasons",
                        reasons),
                "warnings",
                List.of("current_content_only"));
    }

    String title(String site) {
        try {
            return sites.getSiteVisit(site).getTitle();
        } catch (Exception e) {
            throw failure(HttpStatus.FORBIDDEN);
        }
    }

}
