/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.announcement.api.AnnouncementService;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.calendar.api.CalendarService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.ContentHostingService;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.grading.api.GradebookInformation;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.SortType;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.time.api.TimeService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpAssignmentSetupServiceTest {
    private AssignmentService assignments;
    private GradingService grading;
    private SiteService sites;
    private ServerConfigurationService config;
    private McpAssessmentService metadata;
    private McpAssignmentSetupService service;
    private Assignment saved;
    private List<org.sakaiproject.grading.api.Assignment> items;

    @Before
    public void setup() throws Exception {
        SessionManager sessions = mock(SessionManager.class);
        Session session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session); when(session.getUserId()).thenReturn("instructor-a");
        sites = mock(SiteService.class); Site site = mock(Site.class);
        when(sites.getSiteVisit("course-a")).thenReturn(site); when(site.getType()).thenReturn("course");
        when(site.getReference()).thenReturn("/site/course-a"); when(site.getTitle()).thenReturn("Synthetic Course");
        when(site.getToolForCommonId(anyString())).thenReturn(mock(org.sakaiproject.site.api.ToolConfiguration.class));
        config = mock(ServerConfigurationService.class); when(config.getBoolean("mcp.assignment.setup.enabled", false)).thenReturn(true);
        assignments = mock(AssignmentService.class); grading = mock(GradingService.class);
        when(assignments.allowAddSiteAssignment("course-a")).thenReturn(true);
        when(assignments.allowUpdateAssignmentInContext("course-a")).thenReturn(true);
        when(assignments.getScaleFactor()).thenReturn(10);
        when(grading.currentUserHasEditPerm("course-a")).thenReturn(true);
        when(grading.isGradebookInitialized("course-a")).thenReturn(true);
        GradebookInformation info = new GradebookInformation(); info.setCategoryType(1);
        when(grading.getGradebookInformation("course-a", "course-a")).thenReturn(info);
        items = new ArrayList<>(); when(grading.getAssignments("course-a", "course-a", SortType.SORT_BY_NONE)).thenAnswer(i -> items);
        when(assignments.getAssignmentsForContext("course-a")).thenReturn(List.of());
        SecurityService security = mock(SecurityService.class);
        when(security.unlock("asn.revise", org.sakaiproject.assignment.api.AssignmentReferenceReckoner.reckoner().context("course-a").reckon().getReference())).thenReturn(true);
        metadata = new McpAssessmentService(sessions, sites, assignments, grading, mock(CalendarService.class),
                mock(TimeService.class), security, config, mock(AnnouncementService.class));
        FormattedText text = mock(FormattedText.class); when(text.processFormattedText(anyString(), any(StringBuilder.class))).thenAnswer(i -> i.getArgument(0));
        service = new McpAssignmentSetupService(metadata, mock(ContentHostingService.class), text);
        saved = new Assignment(); saved.setId("assignment-a"); saved.setContext("course-a"); saved.setAuthor("instructor-a"); saved.setDraft(true);
        when(assignments.addDraftAssignment("course-a")).thenReturn(saved);
        when(assignments.getAssignment("assignment-a")).thenReturn(saved);
        when(assignments.withAssignmentLock(eq("assignment-a"), any())).thenAnswer(inv -> {
            @SuppressWarnings("unchecked") Function<Assignment, Object> callback = inv.getArgument(1);
            return callback.apply(saved);
        });
    }
    private McpAssignmentSetupService.Gradebook noGradebook() { return new McpAssignmentSetupService.Gradebook("none", null, null, null); }
    private McpAssignmentSetupService.Create request(String publication, String deadline, BigDecimal points) {
        return new McpAssignmentSetupService.Create("Assignment 3", "Submit a report.", "Asia/Karachi", null,
                "2026-10-12T09:00:00+05:00", "2026-10-26T09:00:00+05:00", "2026-10-26T09:00:00+05:00", points,
                "attachments_only", new McpAssignmentSetupService.Resubmission(0, null), publication, List.of(), noGradebook(), deadline);
    }
    @Test public void defaultDisabledEndpointDoesNotTouchDomainServices() throws Exception {
        when(config.getBoolean("mcp.assignment.setup.enabled", false)).thenReturn(false);
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class, () -> service.create("course-a", request("draft", "none", BigDecimal.TEN))).getStatus());
        verifyNoInteractions(assignments, grading);
    }
    @Test public void gradingOnlyTaCannotCreateSkeleton() throws Exception {
        when(assignments.allowAddSiteAssignment("course-a")).thenReturn(false);
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class, () -> service.create("course-a", request("draft", "none", BigDecimal.TEN))).getStatus());
        verify(assignments, never()).addDraftAssignment(anyString());
    }
    @Test public void crossSiteDenialBeforeCreation() throws Exception {
        when(sites.getSiteVisit("course-b")).thenThrow(new PermissionException("instructor-a", "site.visit", "course-b"));
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class, () -> service.create("course-b", request("draft", "none", BigDecimal.TEN))).getStatus());
        verifyNoInteractions(assignments, grading);
    }
    @Test public void unrepresentablePointsRejectedBeforePersistence() throws Exception {
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> service.create("course-a", request("draft", "none", new BigDecimal("0.01")))).getStatus());
        verify(assignments, never()).addDraftAssignment(anyString());
    }
    @Test public void draftHasNoIntegrationsAndNoReleasedGrades() throws Exception {
        Map<String,Object> result = service.create("course-a", request("draft", "none", new BigDecimal("100")));
        assertEquals("complete", result.get("outcome")); assertTrue(saved.getDraft()); assertFalse(saved.getReleaseGrades());
        assertEquals(Integer.valueOf(1000), saved.getMaxGradePoint());
        assertEquals(saved.getOpenDate(), saved.getVisibleDate());
        verify(assignments).addDraftAssignment("course-a"); verify(assignments, never()).addAssignment(anyString());
        verify(grading, never()).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    @Test public void missingRequestedCalendarCreatesNothing() throws Exception {
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class, () -> service.create("course-a", request("published", "course_calendar", BigDecimal.TEN))).getStatus());
        verify(assignments, never()).addDraftAssignment(anyString());
    }
    @Test public void configureFailureRetainsAssignmentId() throws Exception {
        doThrow(new PermissionException("instructor-a", "asn.revise", "assignment-a")).when(assignments).updateAssignment(any());
        Map<String,Object> result = service.create("course-a", request("draft", "none", BigDecimal.TEN));
        assertEquals("partial", result.get("outcome")); assertEquals("assignment-a", result.get("assignment_id")); assertTrue(saved.getDraft());
    }
    @Test public void promoteAndIdenticalPostedReplayDoNotRecreateAssignment() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN));
        var first = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "none");
        assertEquals("complete", service.publish("course-a", "assignment-a", first).get("outcome"));
        assertFalse(saved.getDraft());
        var second = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "none");
        assertEquals("unchanged", service.publish("course-a", "assignment-a", second).get("outcome"));
        verify(assignments, times(1)).addDraftAssignment("course-a");
        verify(assignments, times(2)).withAssignmentLock(eq("assignment-a"), any());
    }
    @Test public void staleRevisionProducesConflictAndNoPromotion() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN));
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class, () -> service.publish("course-a", "assignment-a",
                new McpAssignmentSetupService.Publish("stale", noGradebook(), "none"))).getStatus()); assertTrue(saved.getDraft());
    }
    @Test public void contextContainsOnlyMetadataAndDisclosesHiddenDraftScope() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN));
        when(assignments.getAssignmentsForContext("course-a")).thenReturn(List.of(saved));
        Map<String,Object> result = metadata.context("course-a", null, null);
        assertEquals(false, result.get("complete"));
        assertFalse(result.toString().contains("Submit a report.")); assertFalse(result.toString().contains("instructor-a"));
        assertFalse(result.toString().contains("submissions="));
        assertTrue(result.toString().contains("permission_scoped"));
    }
    @Test public void oversizedContextFailsWithoutClaimingCompleteness() throws Exception {
        when(assignments.getAssignmentsForContext("course-a")).thenReturn(java.util.Collections.nCopies(501, saved));
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> metadata.context("course-a", null, null)).getStatus());
    }
    @Test public void existingUnrelatedGradebookItemIsNeverAdopted() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN));
        var item = new org.sakaiproject.grading.api.Assignment(); item.setId(21L); item.setName("Assignment 3"); items.add(item);
        var gb = new McpAssignmentSetupService.Gradebook("new_external", null, false, true);
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class, () -> service.publish("course-a", "assignment-a",
                new McpAssignmentSetupService.Publish(metadata.revision(saved), gb, "none"))).getStatus());
        assertTrue(saved.getDraft());
        verify(grading, never()).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    private McpAssignmentSetupService.Gradebook externalGradebook() {
        return new McpAssignmentSetupService.Gradebook("new_external", null, true, true);
    }
    private void stageGradebook() {
        doAnswer(inv -> {
            var item = new org.sakaiproject.grading.api.Assignment();
            item.setId(21L); item.setName(saved.getTitle()); item.setPoints(saved.getMaxGradePoint().doubleValue() / saved.getScaleFactor());
            item.setExternalId(McpAssessmentService.assignmentRef(saved)); item.setReference(McpAssessmentService.assignmentRef(saved));
            item.setExternalAppName("sakai.assignment.grades"); item.setExternallyMaintained(true);
            item.setDueDate(java.util.Date.from(saved.getDueDate())); item.setReleased(false); item.setCounted(false);
            items.add(item); return null;
        }).when(grading).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    @Test public void externalItemPublishedWithExactOwnershipAndRequestedFlags() throws Exception {
        service.create("course-a", request("draft", "none", new BigDecimal("100")));
        stageGradebook();
        var publish = new McpAssignmentSetupService.Publish(metadata.revision(saved), externalGradebook(), "none");
        assertEquals("complete", service.publish("course-a", "assignment-a", publish).get("outcome"));
        assertFalse(saved.getDraft()); assertEquals(1, items.size()); assertTrue(items.get(0).getReleased()); assertTrue(items.get(0).getCounted());
        assertEquals("/assignment/a/course-a/assignment-a", saved.getProperties().get(org.sakaiproject.assignment.api.AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT));
        var replay = new McpAssignmentSetupService.Publish(metadata.revision(saved), externalGradebook(), "none");
        assertEquals("unchanged", service.publish("course-a", "assignment-a", replay).get("outcome"));
        verify(grading, times(1)).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    @Test public void postedReplayAcceptsJdbcTimestampForSameDueInstant() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); stageGradebook();
        assertEquals("complete", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        // Hibernate hydrates Date columns as Timestamp; Timestamp.equals(Date) is false for equal instants.
        items.get(0).setDueDate(java.sql.Timestamp.from(saved.getDueDate()));
        assertEquals("unchanged", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        verify(grading, times(1)).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    @Test public void postedReplayRejectsChangedJdbcDueInstant() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); stageGradebook();
        service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none"));
        items.get(0).setDueDate(java.sql.Timestamp.from(saved.getDueDate().plusSeconds(1)));
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class, () -> service.publish("course-a", "assignment-a",
                new McpAssignmentSetupService.Publish(metadata.revision(saved), externalGradebook(), "none"))).getStatus());
    }
    @Test public void gradebookFailureLeavesDraftAndKnownAssignmentForRecovery() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN));
        doThrow(new IllegalStateException("private database detail")).when(grading)
                .addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
        var publish = new McpAssignmentSetupService.Publish(metadata.revision(saved), externalGradebook(), "none");
        Map<String,Object> result = service.publish("course-a", "assignment-a", publish);
        assertEquals("partial", result.get("outcome")); assertEquals("assignment-a", result.get("assignment_id"));
        assertTrue(saved.getDraft()); assertFalse(result.toString().contains("private database"));
        stageGradebook();
        assertEquals("complete", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        assertEquals(1, items.size());
    }
    @Test public void knownPartialItemResumesWithoutSecondGradebookCreate() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); stageGradebook();
        final int[] calls = {0};
        doAnswer(inv -> {
            if (++calls[0] == 2) throw new PermissionException("instructor-a", "asn.revise", "assignment-a");
            return null;
        }).when(assignments).updateAssignment(any());
        assertEquals("partial", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        assertEquals(1, items.size()); assertTrue(saved.getDraft());
        doNothing().when(assignments).updateAssignment(any());
        assertEquals("complete", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        verify(grading, times(1)).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }
    @Test public void postedPartialResumesOnlyGradebookFlags() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); stageGradebook();
        service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(metadata.revision(saved), externalGradebook(), "none"));
        items.get(0).setReleased(false); items.get(0).setCounted(false);
        assertEquals("complete", service.publish("course-a", "assignment-a", new McpAssignmentSetupService.Publish(
                metadata.revision(saved), externalGradebook(), "none")).get("outcome"));
        assertFalse(saved.getDraft()); assertTrue(items.get(0).getReleased());
        verify(grading, times(1)).addExternalAssessmentUnreleased(any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    private void ownedCalendar(boolean loseFirstCommitResponse) throws Exception {
        var calendar = mock(org.sakaiproject.calendar.api.Calendar.class);
        when(metadata.calendars.getCalendar(any())).thenReturn(calendar);
        when(calendar.allowGetEvents()).thenReturn(true); when(calendar.allowAddCalendarEvent()).thenReturn(true);
        var edit = mock(org.sakaiproject.calendar.api.CalendarEventEdit.class);
        var range = mock(org.sakaiproject.time.api.TimeRange.class);
        var point = mock(org.sakaiproject.time.api.Time.class);
        when(point.getTime()).thenAnswer(inv -> saved.getDueDate().toEpochMilli());
        when(range.firstTime()).thenReturn(point); when(range.lastTime()).thenReturn(point);
        when(metadata.times.newTimeRange(anyLong(), eq(0L))).thenReturn(range);
        when(edit.getId()).thenReturn("deadline-1"); when(edit.getDisplayName()).thenReturn("Assignment 3");
        when(edit.getType()).thenReturn("Deadline"); when(edit.getRange()).thenReturn(range);
        when(edit.getField(org.sakaiproject.calendar.api.CalendarConstants.NEW_ASSIGNMENT_DUEDATE_CALENDAR_ASSIGNMENT_ID)).thenReturn("assignment-a");
        when(edit.getField(org.sakaiproject.calendar.api.CalendarConstants.EVENT_OWNED_BY_TOOL_ID)).thenReturn("sakai.assignment.grades");
        when(calendar.addEvent()).thenReturn(edit);
        final boolean[] committed = {false};
        when(calendar.getEvent("deadline-1")).thenAnswer(inv -> {
            if (!committed[0]) throw new org.sakaiproject.exception.IdUnusedException("deadline-1");
            return edit;
        });
        doAnswer(inv -> {
            assertEquals("deadline-1", saved.getProperties().get(org.sakaiproject.entity.api.ResourceProperties.PROP_ASSIGNMENT_DUEDATE_CALENDAR_EVENT_ID));
            committed[0] = true;
            if (loseFirstCommitResponse) throw new IllegalStateException("response lost after commit");
            return null;
        }).when(calendar).commitEvent(edit);
    }
    @Test public void oneOwnedDeadlineIsVerifiedBeforePostAndNotDuplicatedOnReplay() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); ownedCalendar(false);
        var publish = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "course_calendar");
        assertEquals("complete", service.publish("course-a", "assignment-a", publish).get("outcome"));
        assertFalse(saved.getDraft());
        var replay = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "course_calendar");
        assertEquals("unchanged", service.publish("course-a", "assignment-a", replay).get("outcome"));
        verify(metadata.calendars.getCalendar(null), times(1)).addEvent();
    }
    @Test public void lostCalendarCommitResponseResumesKnownEventWithoutDuplicate() throws Exception {
        service.create("course-a", request("draft", "none", BigDecimal.TEN)); ownedCalendar(true);
        var publish = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "course_calendar");
        Map<String,Object> first = service.publish("course-a", "assignment-a", publish);
        assertEquals("partial", first.get("outcome")); assertTrue(saved.getDraft());
        assertEquals("deadline-1", ((Map<?,?>) first.get("calendar")).get("event_id"));
        var recover = new McpAssignmentSetupService.Publish(metadata.revision(saved), noGradebook(), "course_calendar");
        assertEquals("complete", service.publish("course-a", "assignment-a", recover).get("outcome"));
        verify(metadata.calendars.getCalendar(null), times(1)).addEvent();
    }

    @Test public void groupOnlyRevisePermissionDoesNotPermitSiteWideSetup() throws Exception {
        when(metadata.security.unlock("asn.revise", org.sakaiproject.assignment.api.AssignmentReferenceReckoner.reckoner().context("course-a").reckon().getReference())).thenReturn(false);
        when(assignments.allowUpdateAssignmentInContext("course-a")).thenReturn(true);
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class, () -> service.create(
                "course-a", request("draft", "none", BigDecimal.TEN))).getStatus());
        verify(assignments, never()).addDraftAssignment(anyString());
    }

    @Test public void missingBackingGradebookIsReportedWithoutLazyInitialization() throws Exception {
        when(grading.isGradebookInitialized("course-a")).thenReturn(false);
        Map<String,Object> result = metadata.context("course-a", null, null);
        assertEquals(false, ((Map<?,?>) result.get("gradebook")).get("available"));
        verify(grading, never()).getGradebookInformation(anyString(), anyString());
        verify(grading, never()).getAssignments(anyString(), anyString(), any());
        verify(grading, never()).getGradebook(anyString(), anyString());
    }

}
