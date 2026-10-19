/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.digest;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.id;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.stamp;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.canonical;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.decimal;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.fields;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.hash;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.rows;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.string;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** Single-attempt grade save/return, durable receipts and operation reconciliation. */
@Service
public class McpGradeMutationService {
    private final AssignmentService assignments;
    private final GradingService grading;
    private final McpGradingStore store;
    private final FormattedText formatted;
    private final McpGradingAuthorization authorization;
    private final McpGradingEvidence evidence;
    private final McpGradebookProjection gradebook;
    private final ObjectMapper mapper = new ObjectMapper();

    public McpGradeMutationService(
            AssignmentService assignments,
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            McpGradingStore store,
            FormattedText formatted,
            McpGradingAuthorization authorization,
            McpGradingEvidence evidence,
            McpGradebookProjection gradebook) {
        this.assignments = assignments;
        this.grading = grading;
        this.store = store;
        this.formatted = formatted;
        this.authorization = authorization;
        this.evidence = evidence;
        this.gradebook = gradebook;
    }

    BigDecimal points(String value, Assignment a) {
        if (!value.matches("(0|[1-9][0-9]*)(\\.[0-9]+)?") || value.length() > 32)
            throw failure(HttpStatus.BAD_REQUEST);
        try {
            BigDecimal score = new BigDecimal(value),
                    scaled = score.multiply(BigDecimal.valueOf(a.getScaleFactor()));
            scaled.intValueExact();
            if (scaled.compareTo(BigDecimal.valueOf(a.getMaxGradePoint())) > 0)
                throw failure(HttpStatus.BAD_REQUEST);
            return score;
        } catch (ArithmeticException e) {
            throw failure(HttpStatus.BAD_REQUEST);
        }
    }

    @SuppressWarnings("unchecked")
    String feedback(Map<String, Object> row, AssignmentSubmission s) {
        if (!(row.get("feedback") instanceof Map<?, ?> patch))
            throw failure(HttpStatus.BAD_REQUEST);
        if (!patch.keySet().equals(Set.of("action", "text"))) throw failure(HttpStatus.BAD_REQUEST);
        String action = (String) patch.get("action");
        Object value = patch.get("text");
        if ("preserve".equals(action) && value == null) return s.getFeedbackComment();
        if ("clear".equals(action) && value == null) return null;
        if ("replace".equals(action) && value instanceof String text) {
            String safe = formatted.escapeHtmlFormattedText(text);
            if (safe.getBytes(StandardCharsets.UTF_8).length > 65535)
                throw failure(HttpStatus.BAD_REQUEST);
            return safe;
        }
        throw failure(HttpStatus.BAD_REQUEST);
    }

    public Map<String, Object> write(
            String site, String id, String kind, Map<String, Object> request) {
        fields(
                request,
                "operation_id",
                "mode",
                "expected_assignment_revision",
                "payload_sha256",
                "grades");
        try {
            if (mapper.writeValueAsBytes(request).length > 60_000)
                throw failure(HttpStatus.BAD_REQUEST);
        } catch (IOException e) {
            throw failure(HttpStatus.BAD_REQUEST);
        }
        Assignment a = authorization.assignment(site, id);
        gradebook.writable(a);
        String oid = McpGradingStore.uuid(string(request, "operation_id")),
                mode = string(request, "mode");
        if (!Set.of("validate", "commit").contains(mode)) throw failure(HttpStatus.BAD_REQUEST);
        var selected = new ArrayList<>(rows(request, "grades"));
        for (var row : selected) {
            if (kind.equals("save"))
                fields(
                        row,
                        "submission_id",
                        "sakai_user_id",
                        "expected_content_revision",
                        "expected_grade_revision",
                        "score",
                        "feedback");
            else
                fields(
                        row,
                        "submission_id",
                        "sakai_user_id",
                        "expected_content_revision",
                        "expected_grade_revision",
                        "expected_score",
                        "expected_feedback_sha256");
        }
        selected.sort(
                Comparator.comparing(
                        r -> string(r, "submission_id") + "\n" + string(r, "sakai_user_id")));
        if (selected.stream().map(r -> string(r, "submission_id")).distinct().count()
                != selected.size()) throw failure(HttpStatus.BAD_REQUEST);
        var payload =
                obj(
                        "kind",
                        kind,
                        "course_id",
                        site,
                        "assignment_id",
                        id,
                        "expected_assignment_revision",
                        string(request, "expected_assignment_revision"),
                        "grades",
                        selected);
        String sha = hash(canonical(payload));
        if (!sha.equals(string(request, "payload_sha256"))) throw failure(HttpStatus.BAD_REQUEST);
        if (mode.equals("commit")) {
            var old =
                    store.locked(
                            store.key(authorization.actor(), site, id, oid, "operation"),
                            directory -> {
                                try {
                                    return store.read(directory);
                                } catch (IOException e) {
                                    throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                                }
                            });
            if (old != null) {
                if (!sha.equals(old.get("payload_sha256"))) throw failure(HttpStatus.CONFLICT);
                for (var row : rows(old, "rows"))
                    gradebook.target(
                            a, authorization.submission(a, string(row, "submission_id")), row);
                return old;
            }
        }
        evidence.revision(a, request);
        // Whole batch preflight before the first official change.
        for (var row : selected) {
            AssignmentSubmission s = authorization.submission(a, string(row, "submission_id"));
            evidence.current(a, s, row, true);
            gradebook.writeTarget(a, s, row);
            if (kind.equals("save")) {
                points(string(row, "score"), a);
                feedback(row, s);
                if (Boolean.TRUE.equals(s.getGradeReleased())
                        || Boolean.TRUE.equals(s.getReturned())) throw failure(HttpStatus.CONFLICT);
            } else {
                if (!Boolean.TRUE.equals(s.getGraded())
                        || Boolean.TRUE.equals(s.getGradeReleased())
                        || Boolean.TRUE.equals(s.getReturned())
                        || points(string(row, "expected_score"), a)
                                        .compareTo(
                                                new BigDecimal(
                                                        decimal(s.getGrade(), a.getScaleFactor())))
                                != 0
                        || !Objects.equals(
                                row.get("expected_feedback_sha256"),
                                s.getFeedbackComment() == null
                                        ? null
                                        : digest(s.getFeedbackComment())))
                    throw failure(HttpStatus.CONFLICT);
            }
        }
        var receipt =
                obj(
                        "operation_id",
                        oid,
                        "kind",
                        kind,
                        "mode",
                        mode,
                        "payload_sha256",
                        sha,
                        "outcome",
                        "validated",
                        "observed_at",
                        stamp(Instant.now()),
                        "rows",
                        new ArrayList<Map<String, Object>>(),
                        "warnings",
                        List.of());
        @SuppressWarnings("unchecked")
        var results = (List<Map<String, Object>>) receipt.get("rows");
        for (var row : selected)
            results.add(
                    rowReceipt(
                            a,
                            authorization.submission(a, string(row, "submission_id")),
                            string(row, "sakai_user_id"),
                            "validated",
                            null));
        if (mode.equals("validate")) return receipt;
        return store.locked(
                store.key(authorization.actor(), site, id, oid, "operation"),
                directory -> {
                    try {
                        var old = store.read(directory);
                        if (old != null) {
                            if (!sha.equals(old.get("payload_sha256")))
                                throw failure(HttpStatus.CONFLICT);
                            return old;
                        }
                        receipt.put("outcome", "unknown");
                        store.write(directory, receipt);
                        for (int index = 0; index < selected.size(); index++) {
                            var row = selected.get(index);
                            String sid = string(row, "submission_id"),
                                    uid = string(row, "sakai_user_id");
                            results.set(
                                    index,
                                    rowReceipt(
                                            a,
                                            authorization.submission(a, sid),
                                            uid,
                                            "unknown",
                                            "commit_in_progress"));
                            store.write(directory, receipt);
                            try {
                                var saved =
                                        assignments.withGradingSubmissionLock(
                                                sid,
                                                s -> {
                                                    Assignment fresh =
                                                            authorization.assignment(site, id);
                                                    evidence.revision(fresh, request);
                                                    gradebook.writable(fresh);
                                                    evidence.current(fresh, s, row, true);
                                                    gradebook.writeTarget(fresh, s, row);
                                                    if (kind.equals("save")) {
                                                        s.setGrade(
                                                                points(string(row, "score"), fresh)
                                                                        .multiply(
                                                                                BigDecimal.valueOf(
                                                                                        fresh
                                                                                                .getScaleFactor()))
                                                                        .toBigIntegerExact()
                                                                        .toString());
                                                        s.setFeedbackComment(feedback(row, s));
                                                        s.setGraded(true);
                                                        s.setGradedBy(authorization.actor());
                                                    } else {
                                                        s.setGradeReleased(true);
                                                        s.setReturned(true);
                                                        s.setDateReturned(Instant.now());
                                                    }
                                                    try {
                                                        assignments.updateSubmission(s);
                                                    } catch (PermissionException e) {
                                                        throw failure(HttpStatus.FORBIDDEN);
                                                    }
                                                    return s;
                                                });
                                results.set(
                                        index,
                                        rowReceipt(
                                                a,
                                                saved,
                                                uid,
                                                kind.equals("save")
                                                        ? "saved"
                                                        : "assignment_released",
                                                null));
                                store.write(directory, receipt);
                                if (kind.equals("release")) {
                                    String releasedContent = evidence.contentRevision(saved),
                                            releasedGrade = evidence.gradeRevision(saved);
                                    assignments.withGradingSubmissionLock(
                                            sid,
                                            locked -> {
                                                Assignment fresh =
                                                        authorization.assignment(site, id);
                                                evidence.revision(fresh, request);
                                                gradebook.writable(fresh);
                                                gradebook.writeTarget(fresh, locked, row);
                                                if (!releasedContent.equals(
                                                                evidence.contentRevision(locked))
                                                        || !releasedGrade.equals(
                                                                evidence.gradeRevision(locked)))
                                                    throw failure(HttpStatus.CONFLICT);
                                                var item = gradebook.linked(fresh);
                                                if (item != null) {
                                                    grading.updateExternalAssessmentScore(
                                                            site,
                                                            site,
                                                            item.getExternalId(),
                                                            uid,
                                                            decimal(
                                                                    locked.getGrade(),
                                                                    fresh.getScaleFactor()));
                                                    grading.updateExternalAssessmentComment(
                                                            site,
                                                            site,
                                                            item.getExternalId(),
                                                            uid,
                                                            formatted
                                                                    .convertFormattedTextToPlaintext(
                                                                            locked
                                                                                    .getFeedbackComment()));
                                                }
                                                return null;
                                            });
                                    results.set(
                                            index,
                                            rowReceipt(a, saved, uid, "gradebook_synced", null));
                                    store.write(directory, receipt);
                                }
                            } catch (Exception e) {
                                // No blind retry after native events or database errors. Prior
                                // stage remains visible.
                                var previous = results.get(index);
                                previous.put("reason", "requires_reconciliation");
                                previous.put("retry_action", "human_reconciliation");
                                receipt.put("warnings", List.of("manual_reconciliation_required"));
                                store.write(directory, receipt);
                            }
                        }
                        receipt.put(
                                "outcome",
                                results.stream()
                                                .allMatch(
                                                        r ->
                                                                (kind.equals("save")
                                                                                ? "saved"
                                                                                : "gradebook_synced")
                                                                        .equals(r.get("stage")))
                                        ? "completed"
                                        : "partial");
                        store.write(directory, receipt);
                        return receipt;
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    }
                });
    }

    Map<String, Object> rowReceipt(
            Assignment a, AssignmentSubmission s, String uid, String stage, String reason) {
        return obj(
                "submission_id",
                s.getId(),
                "sakai_user_id",
                uid,
                "stage",
                stage,
                "content_revision",
                evidence.contentRevision(s),
                "grade_revision",
                evidence.gradeRevision(s),
                "assignment_score",
                decimal(s.getGrade(), a.getScaleFactor()),
                "grade_released",
                s.getGradeReleased(),
                "returned",
                s.getReturned(),
                "gradebook_score",
                null,
                "reason",
                reason,
                "retry_action",
                stage.equals("unknown") ? "human_reconciliation" : "none");
    }

    public Map<String, Object> operation(String site, String id, String oid) {
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        return store.locked(
                store.key(authorization.actor(), site, id, oid, "operation"),
                directory -> {
                    try {
                        var record = store.read(directory);
                        if (record == null) throw failure(HttpStatus.NOT_FOUND);
                        for (var row : rows(record, "rows")) {
                            var s = authorization.submission(a, string(row, "submission_id"));
                            gradebook.target(a, s, row);
                        }
                        return record;
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    }
                });
    }
}
