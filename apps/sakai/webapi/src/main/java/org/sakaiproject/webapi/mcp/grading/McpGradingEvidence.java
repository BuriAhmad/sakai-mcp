/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.digest;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.stamp;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.count;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.decimal;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.hash;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.instant;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.string;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.assignment.api.model.AssignmentSubmissionSubmitter;
import org.sakaiproject.content.api.ContentHostingService;
import org.sakaiproject.content.api.ContentResource;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.exception.TypeException;
import org.sakaiproject.user.api.User;
import org.sakaiproject.user.api.UserDirectoryService;
import org.sakaiproject.user.api.UserNotDefinedException;
import org.sakaiproject.webapi.mcp.assessment.McpAssessmentService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** Hydrated evidence mapping, content revisions and submission preconditions. */
@Service
public class McpGradingEvidence {
    private final AssignmentService assignments;
    private final ContentHostingService content;
    private final UserDirectoryService users;
    private final McpAssessmentService metadata;
    private final McpGradingAuthorization authorization;

    public McpGradingEvidence(
            AssignmentService assignments,
            ContentHostingService content,
            UserDirectoryService users,
            McpAssessmentService metadata,
            McpGradingAuthorization authorization) {
        this.assignments = assignments;
        this.content = content;
        this.users = users;
        this.metadata = metadata;
        this.authorization = authorization;
    }

    Map<String, Object> identity(String uid) {
        try {
            User u = users.getUser(uid);
            return obj("sakai_user_id", uid, "eid", u.getEid(), "display_name", u.getDisplayName());
        } catch (UserNotDefinedException e) {
            return obj("sakai_user_id", uid, "eid", null, "display_name", null);
        }
    }

    List<String> submitters(AssignmentSubmission s) {
        return s.getSubmitters().stream()
                .map(AssignmentSubmissionSubmitter::getSubmitter)
                .sorted()
                .toList();
    }

    ContentResource resource(String reference)
            throws PermissionException, IdUnusedException, TypeException {
        return content.getResource(assignments.removeReferencePrefix(reference));
    }

    List<Map<String, Object>> attachments(AssignmentSubmission s) {
        if (s.getAttachments().size() > 20) throw failure(HttpStatus.BAD_REQUEST);
        List<Map<String, Object>> result = new ArrayList<>();
        for (String reference : s.getAttachments().stream().sorted().toList()) {
            String key = digest(reference);
            try {
                ContentResource r = resource(reference);
                String kind =
                        ResourceProperties.TYPE_URL.equals(r.getContentType())
                                ? "url"
                                : "true"
                                                .equals(
                                                        r.getProperties()
                                                                .getProperty(
                                                                        AssignmentConstants
                                                                                .PROP_INLINE_SUBMISSION))
                                        ? "inline_content_review"
                                        : "file";
                String sha = r.getContentSha256();
                // Missing authoritative resource hash cannot safely support content writes/export.
                result.add(
                        obj(
                                "artifact_key",
                                key,
                                "original_name",
                                Optional.ofNullable(
                                                r.getProperties()
                                                        .getProperty(
                                                                ResourceProperties
                                                                        .PROP_DISPLAY_NAME))
                                        .orElse(key),
                                "content_type",
                                r.getContentType(),
                                "size_bytes",
                                r.getContentLength(),
                                "resource_revision",
                                sha,
                                "kind",
                                kind,
                                "readable",
                                sha != null && sha.matches("[a-fA-F0-9]{64}")));
            } catch (Exception e) {
                result.add(
                        obj(
                                "artifact_key",
                                key,
                                "original_name",
                                key,
                                "content_type",
                                null,
                                "size_bytes",
                                null,
                                "resource_revision",
                                null,
                                "kind",
                                "file",
                                "readable",
                                false));
            }
        }
        return result;
    }

    List<Map<String, Object>> assignmentAttachments(Assignment a) {
        AssignmentSubmission evidence = new AssignmentSubmission();
        evidence.setAttachments(a.getAttachments());
        return attachments(evidence);
    }

    String contentRevision(AssignmentSubmission s) {
        return hash(
                obj(
                        "id",
                        s.getId(),
                        "users",
                        submitters(s),
                        "submitted",
                        s.getSubmitted(),
                        "user",
                        s.getUserSubmission(),
                        "at",
                        stamp(s.getDateSubmitted()),
                        "text",
                        s.getSubmittedText(),
                        "attachments",
                        attachments(s)));
    }

    String gradeRevision(AssignmentSubmission s) {
        return hash(
                obj(
                        "grade",
                        s.getGrade(),
                        "feedback",
                        s.getFeedbackComment(),
                        "graded",
                        s.getGraded(),
                        "released",
                        s.getGradeReleased(),
                        "returned",
                        s.getReturned(),
                        "at",
                        stamp(s.getDateReturned()),
                        "version",
                        s.getLockVersion()));
    }

    Map<String, Object> flags(AssignmentSubmission s) {
        return obj(
                "submitted",
                Boolean.TRUE.equals(s.getSubmitted()),
                "user_submission",
                Boolean.TRUE.equals(s.getUserSubmission()),
                "graded",
                Boolean.TRUE.equals(s.getGraded()),
                "grade_released",
                Boolean.TRUE.equals(s.getGradeReleased()),
                "returned",
                Boolean.TRUE.equals(s.getReturned()));
    }

    Map<String, Object> overrides(AssignmentSubmission s) {
        return obj(
                "remaining_resubmissions",
                s == null
                        ? null
                        : count(s.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_NUMBER)),
                "resubmission_close_at",
                s == null
                        ? null
                        : instant(
                                s.getProperties()
                                        .get(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME)),
                "extension_close_at",
                s == null
                        ? null
                        : instant(
                                s.getProperties()
                                        .get(AssignmentConstants.ALLOW_EXTENSION_CLOSETIME)),
                "warnings",
                List.of());
    }

    Map<String, Object> entry(Assignment a, String uid, AssignmentSubmission s, boolean orphan) {
        String status =
                s == null
                        ? "missing"
                        : orphan
                                ? "orphan"
                                : !Boolean.TRUE.equals(s.getUserSubmission())
                                        ? "placeholder"
                                        : !Boolean.TRUE.equals(s.getSubmitted())
                                                ? "draft"
                                                : Boolean.TRUE.equals(s.getReturned())
                                                                && !Boolean.TRUE.equals(
                                                                        s.getGraded())
                                                        ? "ungraded_resubmission"
                                                        : "submitted";
        String late =
                s == null || s.getDateSubmitted() == null || a.getDueDate() == null
                        ? "unknown"
                        : s.getDateSubmitted().isAfter(a.getDueDate()) ? "late" : "on_time";
        return obj(
                "student",
                uid == null ? null : identity(uid),
                "submitters",
                s == null ? List.of() : submitters(s).stream().map(this::identity).toList(),
                "submission_id",
                s == null ? null : s.getId(),
                "group_id",
                s == null ? null : s.getGroupId(),
                "status",
                status,
                "flags",
                s == null ? null : flags(s),
                "submitted_at",
                s == null ? null : stamp(s.getDateSubmitted()),
                "returned_at",
                s == null ? null : stamp(s.getDateReturned()),
                "content_revision",
                s == null ? null : contentRevision(s),
                "grade_revision",
                s == null ? null : gradeRevision(s),
                "attempt_count",
                null,
                "history_completeness",
                "current_only",
                "inline_text_present",
                s != null && s.getSubmittedText() != null && !s.getSubmittedText().isBlank(),
                "attachments",
                s == null ? List.of() : attachments(s),
                "attachments_complete",
                true,
                "late_status",
                late,
                "overrides",
                overrides(s),
                "score",
                s == null || a.getTypeOfGrade() != Assignment.GradeType.SCORE_GRADE_TYPE
                        ? null
                        : decimal(s.getGrade(), a.getScaleFactor()),
                "warnings",
                List.of());
    }

    void revision(Assignment a, Map<String, Object> request) {
        if (!metadata.revision(a).equals(string(request, "expected_assignment_revision")))
            throw failure(HttpStatus.CONFLICT);
    }

    void current(Assignment a, AssignmentSubmission s, Map<String, Object> row, boolean grade) {
        if (!a.getId().equals(s.getAssignment().getId()) || !authorization.allowed(a, s))
            throw failure(HttpStatus.FORBIDDEN);
        if (!Boolean.TRUE.equals(s.getSubmitted())
                || !Boolean.TRUE.equals(s.getUserSubmission())
                || !contentRevision(s).equals(string(row, "expected_content_revision")))
            throw failure(HttpStatus.CONFLICT);
        if (grade && !gradeRevision(s).equals(string(row, "expected_grade_revision")))
            throw failure(HttpStatus.CONFLICT);
    }
}
