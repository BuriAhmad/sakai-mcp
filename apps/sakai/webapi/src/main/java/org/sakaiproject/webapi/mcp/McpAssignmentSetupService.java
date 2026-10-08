/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import static org.sakaiproject.webapi.mcp.McpAssessmentService.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.calendar.api.Calendar;
import org.sakaiproject.calendar.api.CalendarConstants;
import org.sakaiproject.calendar.api.CalendarEvent;
import org.sakaiproject.calendar.api.CalendarEventEdit;
import org.sakaiproject.content.api.ContentHostingService;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.CategoryDefinition;
import org.sakaiproject.grading.api.GradebookInformation;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/** Placement-free coordinator. No automatic announcement, retries, deletion, or unrelated-item adoption. */
@Service
public class McpAssignmentSetupService {
    private static final String PLAN = "mcp.assignment.setup.plan";
    private final McpAssessmentService metadata;
    private final ContentHostingService content;
    private final FormattedText text;

    public record Resubmission(Integer count, String until) {}
    public record Gradebook(String mode, String category_id, Boolean release_to_students, Boolean count_toward_course_grade) {}
    public record Create(String title, String instructions, String timezone, String visible_at, String open_at,
            String due_at, String close_at, BigDecimal max_points, String submission_type, Resubmission resubmission,
            String publication, List<String> attachment_resource_refs, Gradebook gradebook, String calendar_deadline) {}
    public record Publish(String expected_assignment_revision, Gradebook gradebook, String calendar_deadline) {}
    private record Validated(Instant visible, Instant open, Instant due, Instant close, int scaled,
            Assignment.SubmissionType submission, String instructions) {}

    public McpAssignmentSetupService(McpAssessmentService metadata, ContentHostingService content, FormattedText text) {
        this.metadata = metadata; this.content = content; this.text = text;
    }
    private void writePermissions(String site, Site course) {
        metadata.requireManagement(site);
        if (!metadata.canReviseSiteAssignment(site)
                || course.getToolForCommonId(AssignmentConstants.TOOL_ID) == null) throw failure(HttpStatus.FORBIDDEN);
    }
    private Instant instant(String value, ZoneId zone) {
        if (value == null || value.endsWith("-00:00")
                || !value.matches("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,3})?(?:Z|[+-]\\d{2}:\\d{2})")) throw failure(HttpStatus.BAD_REQUEST);
        try {
            OffsetDateTime parsed = OffsetDateTime.parse(value);
            if (!parsed.getOffset().equals(zone.getRules().getOffset(parsed.toInstant()))) throw new IllegalArgumentException();
            // Explicit offsets resolve repeated local times; reject gaps and any offset mismatch.
            if (!zone.getRules().getValidOffsets(parsed.toLocalDateTime()).contains(parsed.getOffset())) throw new IllegalArgumentException();
            if (parsed.getNano() % 1_000_000 != 0) throw new IllegalArgumentException();
            return parsed.toInstant();
        } catch (RuntimeException e) { throw failure(HttpStatus.BAD_REQUEST); }
    }
    private Validated validate(String site, Create r) {
        if (r == null || r.title() == null || r.title().isBlank() || r.title().length() > 200
                || r.instructions() == null || r.instructions().isBlank() || r.instructions().length() > 100000
                || r.resubmission() == null || r.resubmission().count() == null || r.resubmission().count() < -1
                || r.attachment_resource_refs() == null || r.attachment_resource_refs().size() > 20
                || !List.of("draft", "published").contains(Objects.toString(r.publication(), ""))) throw failure(HttpStatus.BAD_REQUEST);
        ZoneId zone;
        try {
            if (!ZoneId.getAvailableZoneIds().contains(r.timezone())) throw new IllegalArgumentException();
            zone = ZoneId.of(r.timezone());
        } catch (Exception e) { throw failure(HttpStatus.BAD_REQUEST); }
        Instant open = instant(r.open_at(), zone), due = instant(r.due_at(), zone), close = instant(r.close_at(), zone);
        Instant visible = r.visible_at() == null ? open : instant(r.visible_at(), zone);
        if (!open.isBefore(due) || due.isAfter(close) || visible.isAfter(open)) throw failure(HttpStatus.BAD_REQUEST);
        if (r.resubmission().count() == 0) {
            if (r.resubmission().until() != null) throw failure(HttpStatus.BAD_REQUEST);
        } else if (instant(r.resubmission().until(), zone).isBefore(close)) throw failure(HttpStatus.BAD_REQUEST);
        int scaled;
        try {
            if (r.max_points() == null || r.max_points().signum() <= 0) throw new IllegalArgumentException();
            scaled = r.max_points().multiply(BigDecimal.valueOf(metadata.assignments.getScaleFactor())).intValueExact();
            if (scaled <= 0) throw new IllegalArgumentException();
        } catch (IllegalArgumentException | ArithmeticException e) { throw failure(HttpStatus.BAD_REQUEST); }
        Assignment.SubmissionType submission = switch(Objects.toString(r.submission_type(), "")) {
            case "text_only" -> Assignment.SubmissionType.TEXT_ONLY_ASSIGNMENT_SUBMISSION;
            case "attachments_only" -> Assignment.SubmissionType.ATTACHMENT_ONLY_ASSIGNMENT_SUBMISSION;
            case "text_and_attachments" -> Assignment.SubmissionType.TEXT_AND_ATTACHMENT_ASSIGNMENT_SUBMISSION;
            case "non_electronic" -> Assignment.SubmissionType.NON_ELECTRONIC_ASSIGNMENT_SUBMISSION;
            case "single_attachment" -> Assignment.SubmissionType.SINGLE_ATTACHMENT_SUBMISSION;
            default -> throw failure(HttpStatus.BAD_REQUEST);
        };
        if (r.attachment_resource_refs().stream().distinct().count() != r.attachment_resource_refs().size()) throw failure(HttpStatus.BAD_REQUEST);
        for (String ref : r.attachment_resource_refs()) {
            if (ref == null || !ref.startsWith("/content/group/" + site + "/") || ref.length() > 255
                    || List.of(ref.split("/")).contains("..")) throw failure(HttpStatus.BAD_REQUEST);
            try {
                org.sakaiproject.content.api.ContentEntity resource = content.getResource(ref.substring("/content".length()));
                Instant neededUntil = r.resubmission().until() == null ? close : instant(r.resubmission().until(), zone);
                int depth = 0;
                for (var node = resource; node != null; node = node.getContainingCollection()) {
                    if (++depth > 64 || node.isHidden()
                            || org.sakaiproject.content.api.GroupAwareEntity.AccessMode.GROUPED.equals(node.getAccess())
                            || org.sakaiproject.content.api.GroupAwareEntity.AccessMode.GROUPED.equals(node.getInheritedAccess())
                            || (node.getReleaseInstant() != null && node.getReleaseInstant().isAfter(visible))
                            || (node.getRetractInstant() != null && !node.getRetractInstant().isAfter(neededUntil)))
                        throw failure(HttpStatus.BAD_REQUEST);
                }
            }
            catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
            catch (Exception e) { throw failure(HttpStatus.BAD_REQUEST); }
        }
        String clean = text.processFormattedText(r.instructions(), new StringBuilder());
        // Native storage is a 65535-byte text field; enforce the real limit, including Unicode.
        if (clean == null || clean.isBlank() || clean.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 65535) throw failure(HttpStatus.BAD_REQUEST);
        validateIntegration(site, r.title(), r.max_points(), r.gradebook(), r.calendar_deadline(), null);
        if (r.publication().equals("draft") && (!r.gradebook().mode().equals("none") || !r.calendar_deadline().equals("none"))) throw failure(HttpStatus.BAD_REQUEST);
        boolean duplicate = metadata.assignments.getAssignmentsForContext(site).stream()
                .anyMatch(a -> !Boolean.TRUE.equals(a.getDeleted()) && r.title().equals(a.getTitle()));
        if (duplicate) throw failure(HttpStatus.CONFLICT);
        return new Validated(visible, open, due, close, scaled, submission, clean);
    }
    private void validateIntegration(String site, String title, BigDecimal points, Gradebook gb, String deadline, Assignment known) {
        if (gb == null || !List.of("none", "new_external").contains(Objects.toString(gb.mode(), ""))
                || !List.of("none", "course_calendar").contains(Objects.toString(deadline, ""))) throw failure(HttpStatus.BAD_REQUEST);
        if (metadata.grading.isGradebookGroupEnabled(site)) throw failure(HttpStatus.NOT_IMPLEMENTED);
        if (gb.mode().equals("none")) {
            if (gb.category_id() != null || gb.release_to_students() != null || gb.count_toward_course_grade() != null) throw failure(HttpStatus.BAD_REQUEST);
        } else {
            if (gb.release_to_students() == null || gb.count_toward_course_grade() == null) throw failure(HttpStatus.BAD_REQUEST);
            if (!metadata.grading.isGradebookInitialized(site)) throw failure(HttpStatus.NOT_FOUND);
            GradebookInformation info = metadata.grading.getGradebookInformation(site, site);
            if (info == null) throw failure(HttpStatus.NOT_FOUND);
            if (info.getCategoryType() == null) throw failure(HttpStatus.CONFLICT);
            if (info.getCategoryType() == 1 && gb.category_id() != null) throw failure(HttpStatus.BAD_REQUEST);
            if (info.getCategoryType() != 1 && gb.category_id() == null) throw failure(HttpStatus.BAD_REQUEST);
            CategoryDefinition category = null;
            if (gb.category_id() != null) {
                if (!gb.category_id().matches("[0-9]{1,19}")) throw failure(HttpStatus.BAD_REQUEST);
                category = metadata.grading.getCategoryDefinitions(site, site).stream()
                        .filter(c -> gb.category_id().equals(id(c.getId()))).findFirst().orElseThrow(() -> failure(HttpStatus.CONFLICT));
            }
            for (var item : metadata.items(site)) {
                boolean owned = known != null && assignmentRef(known).equals(item.getExternalId());
                if (title.equals(item.getName()) && !owned) throw failure(HttpStatus.CONFLICT);
                if (category != null && Boolean.TRUE.equals(category.getDropKeepEnabled()) && !Boolean.TRUE.equals(category.getEqualWeight())
                        && Objects.equals(category.getId(), item.getCategoryId()) && item.getPoints() != null
                        && BigDecimal.valueOf(item.getPoints()).compareTo(points) != 0) throw failure(HttpStatus.CONFLICT);
            }
        }
        if (deadline.equals("course_calendar")) {
            Calendar calendar = metadata.calendar(site);
            if (calendar == null) throw failure(HttpStatus.NOT_FOUND);
            if (!calendar.allowGetEvents() || !calendar.allowAddCalendarEvent()) throw failure(HttpStatus.FORBIDDEN);
        }
        if (known != null) {
            String association = known.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT);
            if (gb.mode().equals("none") && (association != null || metadata.items(site).stream().anyMatch(i -> assignmentRef(known).equals(i.getExternalId())))) throw failure(HttpStatus.CONFLICT);
            if (deadline.equals("none") && known.getProperties().get(ResourceProperties.PROP_ASSIGNMENT_DUEDATE_CALENDAR_EVENT_ID) != null) throw failure(HttpStatus.CONFLICT);
            if (association != null && !association.equals(assignmentRef(known))) throw failure(HttpStatus.CONFLICT);
        }
    }
    public Map<String, Object> create(String site, Create request) {
        Site course = metadata.course(site); writePermissions(site, course);
        Validated v = validate(site, request);
        Assignment a;
        try { a = metadata.assignments.addDraftAssignment(site); }
        catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
        try {
            a.setTitle(request.title()); a.setInstructions(v.instructions()); a.setVisibleDate(v.visible());
            a.setOpenDate(v.open()); a.setDueDate(v.due()); a.setCloseDate(v.close()); a.setDropDeadDate(v.due());
            a.setScaleFactor(metadata.assignments.getScaleFactor()); a.setMaxGradePoint(v.scaled());
            a.setTypeOfGrade(Assignment.GradeType.SCORE_GRADE_TYPE); a.setTypeOfSubmission(v.submission());
            a.setTypeOfAccess(Assignment.Access.SITE); a.setIsGroup(false); a.setIndividuallyGraded(true);
            a.setReleaseGrades(false); a.setAllowAttachments(true);
            a.getAttachments().addAll(request.attachment_resource_refs());
            a.getProperties().put(TIMEZONE, request.timezone());
            a.getProperties().put(AssignmentConstants.ALLOW_RESUBMIT_NUMBER, request.resubmission().count().toString());
            if (request.resubmission().until() != null) a.getProperties().put(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME,
                    Long.toString(OffsetDateTime.parse(request.resubmission().until()).toInstant().toEpochMilli()));
            a.getProperties().put(AssignmentConstants.NEW_ASSIGNMENT_ADD_TO_GRADEBOOK, AssignmentConstants.GRADEBOOK_INTEGRATION_NO);
            metadata.assignments.updateAssignment(a);
            if (request.publication().equals("draft")) return result(site, a.getId(), "complete", null);
        } catch (Exception e) { return result(site, a.getId(), "partial", "configure_assignment"); }
        try { return publish(site, a.getId(), new Publish(metadata.revision(a), request.gradebook(), request.calendar_deadline())); }
        catch (Exception e) { return result(site, a.getId(), "partial", "publish_assignment"); }
    }
    public Map<String, Object> publish(String site, String assignmentId, Publish request) {
        Site course = metadata.course(site); writePermissions(site, course);
        if (request == null || request.expected_assignment_revision() == null || request.expected_assignment_revision().isBlank()
                || request.expected_assignment_revision().length() > 256) throw failure(HttpStatus.BAD_REQUEST);
        try {
            Assignment a = metadata.assignments.getAssignment(assignmentId);
            if (!site.equals(a.getContext())) throw failure(HttpStatus.NOT_FOUND);
            return metadata.assignments.withAssignmentLock(assignmentId, locked -> coordinate(site, locked, request));
        } catch (IdUnusedException e) { throw failure(HttpStatus.NOT_FOUND); }
        catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
    }
    private Map<String, Object> coordinate(String site, Assignment a, Publish r) {
        if (!site.equals(a.getContext()) || !metadata.user().equals(a.getAuthor())) throw failure(HttpStatus.FORBIDDEN);
        if (!metadata.revision(a).equals(r.expected_assignment_revision())) throw failure(HttpStatus.CONFLICT);
        if (Boolean.TRUE.equals(a.getDeleted()) || a.getTypeOfAccess() != Assignment.Access.SITE || Boolean.TRUE.equals(a.getIsGroup())
                || a.getTypeOfGrade() != Assignment.GradeType.SCORE_GRADE_TYPE || a.getCloseDate() == null
                || a.getProperties().get(TIMEZONE) == null || Boolean.TRUE.equals(a.getReleaseGrades())
                || !a.getGroups().isEmpty() || Boolean.TRUE.equals(a.getAllowPeerAssessment()) || Boolean.TRUE.equals(a.getContentReview())
                || a.getTypeOfSubmission() == null || a.getTypeOfSubmission().ordinal() < 1 || a.getTypeOfSubmission().ordinal() > 5
                || a.getOpenDate() == null || a.getDueDate() == null || !a.getOpenDate().isBefore(a.getDueDate()) || a.getDueDate().isAfter(a.getCloseDate())
                || a.getScaleFactor() == null || a.getScaleFactor() <= 0 || a.getMaxGradePoint() == null || a.getMaxGradePoint() <= 0)
            throw failure(HttpStatus.NOT_IMPLEMENTED);
        BigDecimal points = BigDecimal.valueOf(a.getMaxGradePoint()).divide(BigDecimal.valueOf(a.getScaleFactor()));
        validateIntegration(site, a.getTitle(), points, r.gradebook(), r.calendar_deadline(), a);
        String plan = r.gradebook().mode() + ":" + r.gradebook().category_id() + ":" + r.gradebook().release_to_students()
                + ":" + r.gradebook().count_toward_course_grade() + ":" + r.calendar_deadline();
        String previous = a.getProperties().get(PLAN);
        if (previous != null && !previous.equals(plan)) throw failure(HttpStatus.CONFLICT);
        if (!Boolean.TRUE.equals(a.getDraft())) {
            if (previous == null) throw failure(HttpStatus.CONFLICT);
            if (verified(a, r)) return result(site, a.getId(), "unchanged", null);
            // A posted partial setup can resume only the approved final flags, never recreate links.
            if (r.calendar_deadline().equals("course_calendar") && !"linked".equals(metadata.calendarLink(a).get("status")))
                throw failure(HttpStatus.CONFLICT);
            if (!r.gradebook().mode().equals("new_external")) throw failure(HttpStatus.CONFLICT);
            var item = ownedItem(site, a); requireItem(a, item, r.gradebook());
            try {
                item.setReleased(r.gradebook().release_to_students()); item.setCounted(r.gradebook().count_toward_course_grade());
                metadata.grading.updateAssignment(site, site, item.getId(), item);
                if (!verified(a, r)) return result(site, a.getId(), "partial", "verify_setup");
                return result(site, a.getId(), "complete", null);
            } catch (Exception e) { return result(site, a.getId(), "partial", "apply_gradebook_flags"); }
        }
        String stage = "record_plan";
        try {
            a.getProperties().put(PLAN, plan); metadata.assignments.updateAssignment(a);
            stage = "link_gradebook";
            if (r.gradebook().mode().equals("new_external")) {
                var item = ownedItem(site, a);
                if (item == null) {
                    metadata.grading.addExternalAssessmentUnreleased(site, site, assignmentRef(a), a.getTitle(), points.doubleValue(),
                            Date.from(a.getDueDate()), AssignmentConstants.TOOL_ID,
                            r.gradebook().category_id() == null ? null : Long.valueOf(r.gradebook().category_id()), assignmentRef(a));
                    item = ownedItem(site, a);
                }
                requireItem(a, item, r.gradebook());
                if (Boolean.TRUE.equals(item.getReleased()) || Boolean.TRUE.equals(item.getCounted())) throw failure(HttpStatus.CONFLICT);
                a.getProperties().put(AssignmentConstants.NEW_ASSIGNMENT_ADD_TO_GRADEBOOK, AssignmentConstants.GRADEBOOK_INTEGRATION_ASSOCIATE);
                a.getProperties().put(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT, assignmentRef(a));
                metadata.assignments.updateAssignment(a);
            }
            stage = "link_calendar";
            if (r.calendar_deadline().equals("course_calendar")) linkCalendar(a);
            stage = "publish_assignment";
            a.setDraft(false); metadata.assignments.updateAssignment(a);
            stage = "apply_gradebook_flags";
            if (r.gradebook().mode().equals("new_external")) {
                var item = ownedItem(site, a); requireItem(a, item, r.gradebook());
                item.setReleased(r.gradebook().release_to_students()); item.setCounted(r.gradebook().count_toward_course_grade());
                metadata.grading.updateAssignment(site, site, item.getId(), item);
            }
            stage = "verify_setup";
            Assignment observed = metadata.assignments.getAssignment(a.getId());
            if (!verified(observed, r)) throw new IllegalStateException();
            return result(site, a.getId(), "complete", null);
        } catch (Exception e) { return result(site, a.getId(), "partial", stage); }
    }
    private org.sakaiproject.grading.api.Assignment ownedItem(String site, Assignment a) {
        return metadata.items(site).stream().filter(i -> assignmentRef(a).equals(i.getExternalId())).findFirst().orElse(null);
    }
    private void requireItem(Assignment a, org.sakaiproject.grading.api.Assignment i, Gradebook gb) {
        if (i == null || !Boolean.TRUE.equals(i.getExternallyMaintained()) || !AssignmentConstants.TOOL_ID.equals(i.getExternalAppName())
                || !assignmentRef(a).equals(i.getReference()) || !a.getTitle().equals(i.getName())
                || !Objects.equals(id(i.getCategoryId()), gb.category_id()) || i.getPoints() == null
                || BigDecimal.valueOf(i.getPoints()).compareTo(BigDecimal.valueOf(a.getMaxGradePoint()).divide(BigDecimal.valueOf(a.getScaleFactor()))) != 0
                || i.getDueDate() == null || i.getDueDate().getTime() != a.getDueDate().toEpochMilli()) throw failure(HttpStatus.CONFLICT);
    }
    private void linkCalendar(Assignment a) throws Exception {
        Calendar calendar = metadata.calendar(a.getContext());
        if (calendar == null) throw failure(HttpStatus.NOT_FOUND);
        String eventId = a.getProperties().get(ResourceProperties.PROP_ASSIGNMENT_DUEDATE_CALENDAR_EVENT_ID);
        if (eventId != null) {
            try {
                CalendarEvent event = calendar.getEvent(eventId);
                if (!metadata.ownsDeadline(a, event)) throw failure(HttpStatus.CONFLICT);
                return;
            } catch (IdUnusedException e) { /* Known absent event can be replaced on explicit recovery. */ }
        }
        CalendarEventEdit edit = calendar.addEvent();
        edit.setRange(metadata.times.newTimeRange(a.getDueDate().toEpochMilli(), 0));
        edit.setDisplayName(a.getTitle()); edit.setDescriptionFormatted(""); edit.setType("Deadline");
        edit.setField(CalendarConstants.NEW_ASSIGNMENT_DUEDATE_CALENDAR_ASSIGNMENT_ID, a.getId());
        edit.setField(CalendarConstants.EVENT_OWNED_BY_TOOL_ID, AssignmentConstants.TOOL_ID);
        // Persist the allocated ID before event commit so an ambiguous commit remains reconcilable.
        a.getProperties().put(ResourceProperties.PROP_ASSIGNMENT_DUEDATE_CALENDAR_EVENT_ID, edit.getId());
        a.getProperties().put(AssignmentConstants.NEW_ASSIGNMENT_DUE_DATE_SCHEDULED, "true");
        try { metadata.assignments.updateAssignment(a); }
        catch (Exception e) { calendar.cancelEvent(edit); throw e; }
        calendar.commitEvent(edit);
        if (!metadata.ownsDeadline(a, calendar.getEvent(edit.getId()))) throw failure(HttpStatus.CONFLICT);
    }
    private boolean verified(Assignment a, Publish r) {
        if (Boolean.TRUE.equals(a.getDraft()) || Boolean.TRUE.equals(a.getReleaseGrades())) return false;
        if (r.gradebook().mode().equals("new_external")) {
            var item = ownedItem(a.getContext(), a); requireItem(a, item, r.gradebook());
            if (!assignmentRef(a).equals(a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT))
                    || !Objects.equals(item.getReleased(), r.gradebook().release_to_students())
                    || !Objects.equals(item.getCounted(), r.gradebook().count_toward_course_grade())) return false;
        }
        return !r.calendar_deadline().equals("course_calendar") || "linked".equals(metadata.calendarLink(a).get("status"));
    }
    private List<String> remaining(String stage) {
        if (stage == null) return List.of();
        return switch(stage) {
            case "configure_assignment", "verify_assignment" -> List.of("verify_assignment", "verify_setup");
            case "record_plan", "link_gradebook" -> List.of("link_gradebook", "link_calendar", "publish_assignment", "apply_gradebook_flags", "verify_setup");
            case "link_calendar" -> List.of("link_calendar", "publish_assignment", "apply_gradebook_flags", "verify_setup");
            case "publish_assignment" -> List.of("publish_assignment", "apply_gradebook_flags", "verify_setup");
            case "apply_gradebook_flags" -> List.of("apply_gradebook_flags", "verify_setup");
            default -> List.of("verify_setup");
        };
    }
    private Map<String, Object> result(String site, String assignmentId, String outcome, String stage) {
        Map<String, Object> row = null;
        Map<String, Object> grade = obj("gradebook_item_id", null, "external_id", null, "category_id", null, "mode", "unknown", "status", "unknown", "released", null, "counted", null);
        Map<String, Object> calendar = obj("event_id", null, "calendar_reference", null, "status", "unknown");
        try {
            Assignment observed = metadata.assignments.getAssignment(assignmentId);
            grade = metadata.gradeLink(observed, metadata.items(site)); calendar = metadata.calendarLink(observed);
            if (observed.getTitle() != null && !observed.getTitle().isBlank()) row = metadata.assignment(observed, metadata.items(site));
        } catch (Exception e) { stage = stage == null ? "verify_assignment" : stage; outcome = "partial"; }
        if (row == null && stage == null) { stage = "verify_assignment"; outcome = "partial"; }
        return obj("outcome", outcome, "course_id", site, "assignment_id", assignmentId, "assignment", row,
                "gradebook", grade, "calendar", calendar, "verified_at", stage == null ? stamp(Instant.now()) : null,
                "remaining_steps", remaining(stage), "warnings", List.of("Calendar may be visible before final assignment publication; no cross-service atomicity is promised."),
                "failure", stage == null ? null : obj("code", "PARTIAL_SUCCESS", "stage", stage, "reason", "Setup stage failed; reread known IDs and revision before deliberate recovery.", "retry_safe", false));
    }
}
