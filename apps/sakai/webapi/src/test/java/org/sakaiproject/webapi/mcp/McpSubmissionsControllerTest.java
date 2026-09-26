/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.assignment.api.model.AssignmentSubmissionSubmitter;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.site.api.Group;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpSubmissionsControllerTest {

    private AssignmentService assignments;
    private SecurityService security;
    private McpSubmissionsController controller;

    @Before
    public void setup() throws Exception {
        SessionManager sessions = mock(SessionManager.class);
        Session session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session);
        when(session.getUserId()).thenReturn("instructor-a");
        SiteService sites = mock(SiteService.class);
        Site site = mock(Site.class);
        when(sites.getSiteVisit("course-a")).thenReturn(site);
        when(site.getType()).thenReturn("course");
        assignments = mock(AssignmentService.class);
        security = mock(SecurityService.class);
        controller = new McpSubmissionsController(sessions, sites, assignments, security);
    }

    @Test
    public void deniesAssignmentFromAnotherCourseBeforeReadingSubmissions() throws Exception {
        Assignment other = new Assignment();
        other.setId("assignment-b");
        other.setContext("course-b");
        when(assignments.getAssignment("assignment-b")).thenReturn(other);
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> controller.submissions("course-a", "assignment-b"));
        assertEquals(HttpStatus.NOT_FOUND, failure.getStatus());
    }

    @Test
    public void deniesCallerWithoutGradePermission() throws Exception {
        Assignment own = new Assignment();
        own.setId("assignment-a");
        own.setContext("course-a");
        when(assignments.getAssignment("assignment-a")).thenReturn(own);
        when(assignments.allowGradeSubmission(anyString())).thenReturn(false);
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
                () -> controller.submissions("course-a", "assignment-a"));
        assertEquals(HttpStatus.FORBIDDEN, failure.getStatus());
    }

    @Test
    public void sectionGraderSeesOnlyAuthorizedSubmitters() throws Exception {
        Assignment own = new Assignment();
        own.setId("assignment-a");
        own.setContext("course-a");
        when(assignments.getAssignment("assignment-a")).thenReturn(own);
        when(assignments.allowGradeSubmission(anyString())).thenReturn(true);
        Group permitted = mock(Group.class);
        when(permitted.getId()).thenReturn("section-a");
        when(permitted.getUsers()).thenReturn(Set.of("student-a"));
        when(assignments.getGroupsAllowGradeAssignment(anyString())).thenReturn(List.of(permitted));
        AssignmentSubmission allowed = submitted("submission-a", "student-a");
        AssignmentSubmission denied = submitted("submission-b", "student-b");
        when(assignments.getSubmissions(own)).thenReturn(Set.of(allowed, denied));

        List<McpSubmissionsController.Submission> result = controller.submissions("course-a", "assignment-a")
                .get("submissions");
        assertEquals(1, result.size());
        assertEquals("submission-a", result.get(0).id());
    }

    private AssignmentSubmission submitted(String id, String userId) {
        AssignmentSubmission submission = new AssignmentSubmission();
        submission.setId(id);
        submission.setSubmitted(true);
        submission.setDateSubmitted(Instant.now());
        AssignmentSubmissionSubmitter submitter = new AssignmentSubmissionSubmitter();
        submitter.setSubmitter(userId);
        submitter.setSubmission(submission);
        submission.setSubmitters(Set.of(submitter));
        return submission;
    }
}
