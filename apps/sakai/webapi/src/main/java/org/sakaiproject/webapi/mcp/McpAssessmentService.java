/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.calendar.api.Calendar;
import org.sakaiproject.calendar.api.CalendarConstants;
import org.sakaiproject.calendar.api.CalendarEvent;
import org.sakaiproject.calendar.api.CalendarService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.CategoryDefinition;
import org.sakaiproject.grading.api.GradebookInformation;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.SortType;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.time.api.TimeService;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/** Metadata only: never traverses submission/score collections. No backing-tool initialization. */
@Service
public class McpAssessmentService {
    public static final String TIMEZONE = "mcp.assignment.timezone";
    public static final int LIMIT = 500;
    private final SessionManager sessions;
    private final SiteService sites;
    final AssignmentService assignments;
    final GradingService grading;
    final CalendarService calendars;
    final TimeService times;
    final SecurityService security;
    private final ServerConfigurationService config;
    private final AnnouncementService announcements;
    private final ObjectMapper mapper = new ObjectMapper();

    public McpAssessmentService(@Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessions,
            SiteService sites, AssignmentService assignments,
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            CalendarService calendars, TimeService times, SecurityService security,
            ServerConfigurationService config, AnnouncementService announcements) {
        this.sessions = sessions; this.sites = sites; this.assignments = assignments; this.grading = grading;
        this.calendars = calendars; this.times = times; this.security = security; this.config = config;
        this.announcements = announcements;
    }

    public String user() {
        String user = sessions.getCurrentSession().getUserId();
        if (user == null || user.isBlank()) throw failure(HttpStatus.UNAUTHORIZED);
        return user;
    }

    public Site course(String id) {
        if (!config.getBoolean("mcp.assignment.setup.enabled", false)) throw failure(HttpStatus.NOT_FOUND);
        user();
        try {
            Site site = sites.getSiteVisit(id);
            if (!"course".equals(site.getType())) throw failure(HttpStatus.NOT_FOUND);
            return site;
        } catch (IdUnusedException e) { throw failure(HttpStatus.NOT_FOUND); }
        catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
    }

    public void requireManagement(String site) {
        if (!assignments.allowAddSiteAssignment(site) || !grading.currentUserHasEditPerm(site))
            throw failure(HttpStatus.FORBIDDEN);
    }

    public boolean canReviseSiteAssignment(String site) {
        return security.unlock(org.sakaiproject.assignment.api.AssignmentServiceConstants.SECURE_UPDATE_ASSIGNMENT,
                org.sakaiproject.assignment.api.AssignmentReferenceReckoner.reckoner().context(site).reckon().getReference());
    }
    public Calendar calendar(String site) {
        try { return calendars.getCalendar(calendarRef(site)); }
        catch (IdUnusedException | PermissionException e) { return null; }
    }
    public String calendarRef(String site) { return calendars.calendarReference(site, SiteService.MAIN_CONTAINER); }
    public static String assignmentRef(Assignment a) { return org.sakaiproject.assignment.api.AssignmentReferenceReckoner.reckoner().assignment(a).reckon().getReference(); }
    public static ResponseStatusException failure(HttpStatus status) { return new ResponseStatusException(status); }
    public static String stamp(Instant t) { return t == null ? null : t.toString(); }
    public static String id(Object id) { return id == null ? null : id.toString(); }
    private static String optionalCalendarField(CalendarEvent event, String name) {
        String value = event.getField(name);
        return value == null || value.isEmpty() ? null : value;
    }
    public static Map<String, Object> obj(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }
    static <T> List<T> bounded(Collection<T> values) {
        if (values.size() > LIMIT) throw failure(HttpStatus.BAD_REQUEST);
        return new ArrayList<>(values);
    }
    public static String digest(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    public String revision(Assignment a) {
        // Semantic configuration revision avoids cache/database precision differences in modification timestamps.
        // Includes persisted content and all association properties, never submissions.
        Map<String, Object> value = obj("id", a.getId(), "title", a.getTitle(),
                "instructions", a.getInstructions(), "draft", a.getDraft(), "deleted", a.getDeleted(),
                "visible", stamp(a.getVisibleDate()), "open", stamp(a.getOpenDate()), "due", stamp(a.getDueDate()),
                "close", stamp(a.getCloseDate()), "points", a.getMaxGradePoint(), "scale", a.getScaleFactor(),
                "grade", a.getTypeOfGrade(), "submission", a.getTypeOfSubmission(), "audience", a.getTypeOfAccess(),
                "group", a.getIsGroup(), "groups", a.getGroups().stream().sorted().toList(),
                "release", a.getReleaseGrades(), "peer_assessment", a.getAllowPeerAssessment(), "content_review", a.getContentReview(),
                "individual", a.getIndividuallyGraded(), "attachments", a.getAttachments().stream().sorted().toList(),
                "properties", new java.util.TreeMap<>(a.getProperties()));
        try { return digest(mapper.writeValueAsString(value)); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw failure(HttpStatus.INTERNAL_SERVER_ERROR); }
    }
    public List<org.sakaiproject.grading.api.Assignment> items(String site) {
        return grading.isGradebookInitialized(site) ? bounded(grading.getAssignments(site, site, SortType.SORT_BY_NONE)) : List.of();
    }
    public Map<String, Object> item(org.sakaiproject.grading.api.Assignment i) {
        return obj("id", id(i.getId()), "title", i.getName(), "max_points", i.getPoints(),
                "due_on", i.getDueDate() == null ? null : i.getDueDate().toInstant().atZone(ZoneOffset.UTC).toLocalDate().toString(),
                "category_id", id(i.getCategoryId()), "released", Boolean.TRUE.equals(i.getReleased()),
                "counted", Boolean.TRUE.equals(i.getCounted()), "extra_credit", Boolean.TRUE.equals(i.getExtraCredit()),
                "externally_maintained", Boolean.TRUE.equals(i.getExternallyMaintained()), "external_id", i.getExternalId(),
                "external_app", i.getExternalAppName(), "gradable_reference", i.getReference());
    }
    private record ItemIndex(Map<String, org.sakaiproject.grading.api.Assignment> ids,
            Map<String, org.sakaiproject.grading.api.Assignment> external) {}
    private ItemIndex indexItems(List<org.sakaiproject.grading.api.Assignment> items) {
        Map<String, org.sakaiproject.grading.api.Assignment> ids = new java.util.HashMap<>(), external = new java.util.HashMap<>();
        for (var item : items) {
            ids.put(id(item.getId()), item);
            if (item.getExternalId() != null) external.put(item.getExternalId(), item);
        }
        return new ItemIndex(ids, external);
    }
    public Map<String, Object> gradeLink(Assignment a, List<org.sakaiproject.grading.api.Assignment> items) {
        return gradeLink(a, indexItems(items));
    }
    private Map<String, Object> gradeLink(Assignment a, ItemIndex items) {
        String association = a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT);
        var owned = items.external().get(assignmentRef(a));
        var linked = owned != null ? owned : association == null ? null :
                items.ids().containsKey(association) ? items.ids().get(association) : items.external().get(association);
        String mode = linked != null ? (linked == owned ? "new_external" : "existing") : association == null ? "none" : "unknown";
        boolean exact = linked != null && association != null && (association.equals(id(linked.getId())) || association.equals(linked.getExternalId()));
        return obj("gradebook_item_id", linked == null ? null : id(linked.getId()), "external_id", linked == null ? null : linked.getExternalId(),
                "category_id", linked == null ? null : id(linked.getCategoryId()), "mode", mode,
                "status", linked == null ? (association == null ? "not_requested" : "missing") : exact ? "linked" : "mismatch",
                "released", linked == null ? null : Boolean.TRUE.equals(linked.getReleased()),
                "counted", linked == null ? null : Boolean.TRUE.equals(linked.getCounted()));
    }
    public Map<String, Object> calendarLink(Assignment a) {
        String eventId = a.getProperties().get(ResourceProperties.PROP_ASSIGNMENT_DUEDATE_CALENDAR_EVENT_ID);
        String status = eventId == null ? "not_requested" : "unknown";
        if (eventId != null) {
            Calendar calendar = calendar(a.getContext());
            if (calendar != null) {
                try {
                    CalendarEvent event = calendar.getEvent(eventId);
                    status = ownsDeadline(a, event) ? "linked" : "mismatch";
                } catch (IdUnusedException e) { status = "missing"; }
                catch (PermissionException e) { status = "unknown"; }
            }
        }
        return obj("event_id", eventId, "calendar_reference", eventId == null ? null : calendarRef(a.getContext()), "status", status);
    }
    public boolean ownsDeadline(Assignment a, CalendarEvent e) {
        return Objects.equals(a.getId(), e.getField(CalendarConstants.NEW_ASSIGNMENT_DUEDATE_CALENDAR_ASSIGNMENT_ID))
                && AssignmentConstants.TOOL_ID.equals(e.getField(CalendarConstants.EVENT_OWNED_BY_TOOL_ID))
                && Objects.equals(a.getTitle(), e.getDisplayName()) && "Deadline".equals(e.getType())
                && a.getDueDate() != null && e.getRange().firstTime().getTime() == a.getDueDate().toEpochMilli()
                && e.getRange().lastTime().getTime() == a.getDueDate().toEpochMilli();
    }
    public Map<String, Object> assignment(Assignment a, List<org.sakaiproject.grading.api.Assignment> items) {
        return assignment(a, indexItems(items));
    }
    private Map<String, Object> assignment(Assignment a, ItemIndex items) {
        Instant now = Instant.now();
        String status = Boolean.TRUE.equals(a.getDraft()) ? "draft" :
                a.getOpenDate() == null || now.isBefore(a.getOpenDate()) ? "posted_future" :
                a.getCloseDate() != null && now.isAfter(a.getCloseDate()) ? "closed" : "open";
        String[] grades = {"none", "ungraded", "letter", "points", "pass_fail", "check"};
        String[] submissions = {"none", "text_only", "attachments_only", "text_and_attachments", "non_electronic", "single_attachment", "external_tool", "video"};
        Integer scale = a.getScaleFactor();
        Object points = a.getTypeOfGrade() == Assignment.GradeType.SCORE_GRADE_TYPE && a.getMaxGradePoint() != null && scale != null && scale > 0
                ? BigDecimal.valueOf(a.getMaxGradePoint()).divide(BigDecimal.valueOf(scale)) : null;
        String until = a.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME);
        int count;
        try { count = Integer.parseInt(a.getProperties().getOrDefault(AssignmentConstants.ALLOW_RESUBMIT_NUMBER, "0")); }
        catch (NumberFormatException e) { count = 0; }
        String deadline = null;
        try { if (count != 0 && until != null) deadline = stamp(Instant.ofEpochMilli(Long.parseLong(until))); }
        catch (NumberFormatException e) { /* absent metadata, no invented policy */ }
        return obj("id", a.getId(), "title", a.getTitle(), "revision", revision(a), "status", status,
                "draft", Boolean.TRUE.equals(a.getDraft()), "deleted", Boolean.TRUE.equals(a.getDeleted()),
                "visible_at", stamp(a.getVisibleDate()), "open_at", stamp(a.getOpenDate()), "due_at", stamp(a.getDueDate()),
                "close_at", stamp(a.getCloseDate()), "max_points", points,
                "grading_type", a.getTypeOfGrade() == null ? "unknown" : grades[a.getTypeOfGrade().ordinal()],
                "submission_type", a.getTypeOfSubmission() == null ? "unknown" : submissions[a.getTypeOfSubmission().ordinal()],
                "resubmission", obj("count", count, "until", deadline), "attachment_resource_refs", a.getAttachments().stream().sorted().toList(),
                "release_grades", Boolean.TRUE.equals(a.getReleaseGrades()), "audience", a.getTypeOfAccess() == Assignment.Access.SITE ? "site" : "groups",
                "group_submission", Boolean.TRUE.equals(a.getIsGroup()), "gradebook_link", gradeLink(a, items), "calendar_link", calendarLink(a),
                "native_announcement_id", a.getProperties().get(ResourceProperties.PROP_ASSIGNMENT_OPENDATE_ANNOUNCEMENT_MESSAGE_ID),
                "instructions_sha256", digest(Objects.toString(a.getInstructions(), "")), "timezone", a.getProperties().get(TIMEZONE));
    }
    public Map<String, Object> context(String siteId, String start, String end) {
        Site site = course(siteId); requireManagement(siteId);
        Instant first, last;
        try {
            if ((start == null) != (end == null)) throw new IllegalArgumentException();
            first = start == null ? Instant.now().atZone(ZoneOffset.UTC).toLocalDate().minusDays(14).atStartOfDay(ZoneOffset.UTC).toInstant() : OffsetDateTime.parse(start).toInstant();
            last = end == null ? first.plus(Duration.ofDays(56)) : OffsetDateTime.parse(end).toInstant();
            if (!first.isBefore(last) || Duration.between(first, last).compareTo(Duration.ofDays(90)) > 0) throw new IllegalArgumentException();
        } catch (RuntimeException e) { throw failure(HttpStatus.BAD_REQUEST); }
        boolean hasGradebook = site.getToolForCommonId("sakai.gradebookng") != null && grading.isGradebookInitialized(siteId);
        var items = hasGradebook ? items(siteId) : List.<org.sakaiproject.grading.api.Assignment>of();
        GradebookInformation info = hasGradebook ? grading.getGradebookInformation(siteId, siteId) : null;
        var categories = info == null ? List.<CategoryDefinition>of() : bounded(grading.getCategoryDefinitions(siteId, siteId));
        ItemIndex index = indexItems(items);
        var rows = bounded(assignments.getAssignmentsForContext(siteId)).stream().map(a -> assignment(a, index)).toList();
        Calendar calendar = calendar(siteId);
        boolean canRead = calendar != null && calendar.allowGetEvents();
        List<Map<String, Object>> events = new ArrayList<>();
        if (canRead) {
            try {
                for (CalendarEvent e : bounded(calendar.getEvents(times.newTimeRange(first, last), null, LIMIT + 1))) {
                    events.add(obj("id", e.getId(), "title", e.getDisplayName(), "start_at", stamp(Instant.ofEpochMilli(e.getRange().firstTime().getTime())),
                            "end_at", stamp(Instant.ofEpochMilli(e.getRange().lastTime().getTime())), "type", e.getType(),
                            "assignment_id", optionalCalendarField(e, CalendarConstants.NEW_ASSIGNMENT_DUEDATE_CALENDAR_ASSIGNMENT_ID),
                            "owner_tool_id", optionalCalendarField(e, CalendarConstants.EVENT_OWNED_BY_TOOL_ID)));
                }
            } catch (PermissionException e) { canRead = false; events.clear(); }
        }
        boolean sharedDrafts = security.unlock(org.sakaiproject.assignment.api.AssignmentServiceConstants.SECURE_SHARE_DRAFTS, site.getReference())
                && assignments.allowAllGroups(siteId);
        boolean groupGradebooks = site.getToolForCommonId("sakai.gradebookng") != null && grading.isGradebookGroupEnabled(siteId);
        List<String> warnings = new ArrayList<>(List.of("Cross-service observation is not a transactional snapshot.", "Course timezone policy is unknown; default calendar window uses UTC."));
        if (!sharedDrafts) warnings.add("Other authors' drafts may be hidden; absence does not prove no conflicts.");
        if (groupGradebooks) warnings.add("Group Gradebooks are unsupported for assignment setup writes.");
        Map<String, Object> result = obj("course", obj("id", siteId, "title", site.getTitle(), "timezone", null, "timezone_source", "unknown"),
                "observed_at", stamp(Instant.now()), "capabilities", obj("create_site_assignment", true,
                "revise_assignment", canReviseSiteAssignment(siteId), "edit_gradebook_items", true,
                "read_calendar", canRead, "add_calendar_event", calendar != null && calendar.allowAddCalendarEvent(),
                "create_announcement", site.getToolForCommonId("sakai.announcements") != null && security.unlock("annc.new", announcements.channelReference(siteId, SiteService.MAIN_CONTAINER))),
                "complete", sharedDrafts && hasGradebook && canRead && !groupGradebooks,
                "sections", obj("assignments", obj("status", sharedDrafts ? "complete" : "permission_scoped", "reason", sharedDrafts ? null : "Hidden drafts may exist"),
                "gradebook", obj("status", !hasGradebook ? "unavailable" : groupGradebooks ? "permission_scoped" : "complete", "reason", !hasGradebook ? "Gradebook not configured" : groupGradebooks ? "Group Gradebook metadata omitted" : null),
                "calendar", obj("status", canRead ? "complete" : calendar == null ? "unavailable" : "permission_scoped", "reason", canRead ? null : "Main Calendar unavailable or unreadable")),
                "assignments", rows, "gradebook", obj("available", info != null, "reason", info == null ? "Gradebook not configured" : null,
                "group_gradebooks_enabled", groupGradebooks, "category_mode", info == null ? null : categoryMode(info.getCategoryType()),
                "grade_entry_type", info == null ? null : gradeType(info.getGradeType()), "display_released_items", info == null ? null : info.getDisplayReleasedGradeItemsToStudents(),
                "course_grade_displayed", info == null ? null : info.getCourseGradeDisplayed(), "categories", categories.stream().map(c -> obj(
                "id", id(c.getId()), "name", c.getName(), "weight_percent", c.getWeight() == null ? null : c.getWeight() * 100,
                "equal_weight_items", Boolean.TRUE.equals(c.getEqualWeight()), "drop_lowest", integer(c.getDropLowest()), "drop_highest", integer(c.getDropHighest()),
                "keep_highest", integer(c.getKeepHighest()), "extra_credit", Boolean.TRUE.equals(c.getExtraCredit()), "drop_keep_enabled", Boolean.TRUE.equals(c.getDropKeepEnabled()))).toList(),
                "items", items.stream().map(this::item).toList()), "calendar", obj("scope", "site_main", "window_start", stamp(first), "window_end", stamp(last), "events", events), "warnings", warnings);
        try { if (mapper.writeValueAsBytes(result).length > 1_000_000) throw failure(HttpStatus.BAD_REQUEST); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw failure(HttpStatus.INTERNAL_SERVER_ERROR); }
        return result;
    }
    static int integer(Integer i) { return i == null ? 0 : i; }
    static String categoryMode(Integer i) { return i == null ? null : switch(i) { case 1 -> "none"; case 2 -> "categories"; case 3 -> "weighted_categories"; default -> null; }; }
    static String gradeType(Integer i) { return i == null ? "unknown" : switch(i) { case 1 -> "points"; case 2 -> "percentage"; case 3 -> "letter"; default -> "unknown"; }; }
}
