/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.junit.Assert.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.sakaiproject.webapi.mcp.assessment.McpAssessmentService.*;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.*;

import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.sakaiproject.assignment.api.*;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.assignment.api.model.AssignmentSubmissionSubmitter;
import org.sakaiproject.authz.api.Member;
import org.sakaiproject.authz.api.Role;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.*;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.grading.api.*;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.*;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.user.api.*;
import org.sakaiproject.webapi.mcp.assessment.McpAssessmentService;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.io.ByteArrayInputStream;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.time.Instant;
import java.util.*;

public class McpGradingServicesTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();
    AssignmentService assignments;
    ServerConfigurationService config;
    SecurityService security;
    McpGradingAuthorization authorization;
    McpGradingEvidence evidence;
    McpGradebookProjection gradebook;
    McpGradingQueryService queries;
    McpGradingStore store;
    McpAssessmentService metadata;
    GradingService grading;
    Assignment a;
    AssignmentSubmission s;
    User student;
    User other;
    Site site;
    Session session;
    ContentHostingService content;

    @Before
    public void setup() throws Exception {
        assignments = mock(AssignmentService.class);
        config = mock(ServerConfigurationService.class);
        security = mock(SecurityService.class);
        SessionManager sessions = mock(SessionManager.class);
        session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session);
        when(session.getUserId()).thenReturn("ta");
        SiteService sites = mock(SiteService.class);
        site = mock(Site.class);
        when(site.getType()).thenReturn("course");
        when(site.getTitle()).thenReturn("Synthetic course");
        when(site.getUsers()).thenReturn(Set.of("student-a", "student-b"));
        when(sites.getSiteVisit("course-a")).thenReturn(site);
        Role studentRole = mock(Role.class);
        when(studentRole.isAllowed(AssignmentServiceConstants.SECURE_ADD_ASSIGNMENT_SUBMISSION))
                .thenReturn(true);
        Member firstMember = mock(Member.class), secondMember = mock(Member.class);
        when(firstMember.isActive()).thenReturn(true);
        when(secondMember.isActive()).thenReturn(true);
        when(firstMember.getRole()).thenReturn(studentRole);
        when(secondMember.getRole()).thenReturn(studentRole);
        when(site.getMember("student-a")).thenReturn(firstMember);
        when(site.getMember("student-b")).thenReturn(secondMember);
        when(config.getBoolean("mcp.assignment.grading.enabled", false)).thenReturn(true);
        Path root = temporary.newFolder("private").toPath();
        Files.setPosixFilePermissions(root, PosixFilePermissions.fromString("rwx------"));
        when(config.getString("mcp.assignment.grading.storage", ""))
                .thenReturn(root.toRealPath().toString());
        when(security.unlock(
                        eq(AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION),
                        anyString()))
                .thenReturn(true);
        when(assignments.allowGradeSubmission(anyString())).thenReturn(true);
        a = new Assignment();
        a.setId("assignment-a");
        a.setContext("course-a");
        a.setTitle("Quiz");
        a.setInstructions("Five MCQs");
        a.setTypeOfGrade(Assignment.GradeType.SCORE_GRADE_TYPE);
        a.setScaleFactor(10);
        a.setMaxGradePoint(50);
        a.setDueDate(Instant.parse("2026-10-08T00:00:00Z"));
        a.setTypeOfSubmission(Assignment.SubmissionType.SINGLE_ATTACHMENT_SUBMISSION);
        when(assignments.getAssignmentWithGradingEvidence("assignment-a")).thenReturn(a);
        s = new AssignmentSubmission();
        s.setId("submission-a");
        s.setAssignment(a);
        s.setSubmitted(true);
        s.setUserSubmission(true);
        s.setDateSubmitted(Instant.parse("2026-10-07T00:00:00Z"));
        s.setDateModified(s.getDateSubmitted());
        AssignmentSubmissionSubmitter submitter = new AssignmentSubmissionSubmitter();
        submitter.setSubmitter("student-a");
        submitter.setSubmission(s);
        s.setSubmitters(Set.of(submitter));
        when(assignments.getSubmissions(a)).thenReturn(Set.of(s));
        when(assignments.getSubmissionWithGradingEvidence("submission-a")).thenReturn(s);
        student = mock(User.class);
        when(student.getId()).thenReturn("student-a");
        when(student.getEid()).thenReturn("synthetic-a");
        when(student.getDisplayName()).thenReturn("Synthetic A");
        other = mock(User.class);
        when(other.getId()).thenReturn("student-b");
        when(other.getEid()).thenReturn("synthetic-b");
        when(other.getDisplayName()).thenReturn("Synthetic B");
        when(assignments.allowAddSubmissionUsers(anyString())).thenReturn(List.of(student, other));
        UserDirectoryService users = mock(UserDirectoryService.class);
        when(users.getUser("student-a")).thenReturn(student);
        when(users.getUser("student-b")).thenReturn(other);
        grading = mock(GradingService.class);
        content = mock(ContentHostingService.class);
        metadata = mock(McpAssessmentService.class);
        when(metadata.revision(any())).thenReturn("config");
        RubricsService rubrics = mock(RubricsService.class);
        store = new McpGradingStore(config);
        authorization =
                new McpGradingAuthorization(
                        assignments, grading, sessions, sites, security, config, rubrics);
        evidence = new McpGradingEvidence(assignments, content, users);
        gradebook =
                new McpGradebookProjection(
                        grading, authorization);
        queries =
                new McpGradingQueryService(
                        assignments,
                        store,
                        sites,
                        config,
                        metadata,
                        authorization,
                        evidence,
                        gradebook);
    }

    @Test
    public void gatesAndForeignSiteDenyBeforeContent() {
        when(config.getBoolean("mcp.assignment.grading.enabled", false)).thenReturn(false);
        assertEquals(
                HttpStatus.NOT_FOUND,
                assertThrows(
                                ResponseStatusException.class,
                                () -> queries.context("course-a", "assignment-a"))
                        .getStatus());
        verify(assignments, never()).getSubmissions(any());
    }

    @Test
    public void gradePermissionIsRequired() {
        when(assignments.allowGradeSubmission(anyString())).thenReturn(false);
        assertEquals(
                HttpStatus.FORBIDDEN,
                assertThrows(
                                ResponseStatusException.class,
                                () -> queries.context("course-a", "assignment-a"))
                        .getStatus());
    }

    @Test
    public void retainedContextRosterIncludesMissing() {
        var rows = queries.roster(a);
        assertEquals(2, rows.size());
        var row = rows.stream().filter(r -> "missing".equals(r.get("status"))).findFirst().orElseThrow();
        assertNull(row.get("submission_id"));
        assertNull(row.get("attempt_count"));
        verify(grading, never()).getAssignments(anyString(), anyString(), any());
    }

    @Test
    public void rosterExcludesGradeCapableCourseMembers() {
        User instructor = mock(User.class);
        when(instructor.getId()).thenReturn("instructor");
        when(assignments.allowAddSubmissionUsers(anyString()))
                .thenReturn(List.of(student, other, instructor));
        when(site.getUsers()).thenReturn(Set.of("student-a", "student-b", "instructor"));
        Role instructorRole = mock(Role.class);
        when(instructorRole.isAllowed(AssignmentServiceConstants.SECURE_ADD_ASSIGNMENT_SUBMISSION))
                .thenReturn(true);
        when(instructorRole.isAllowed(
                        AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION))
                .thenReturn(true);
        Member instructorMember = mock(Member.class);
        when(instructorMember.isActive()).thenReturn(true);
        when(instructorMember.getRole()).thenReturn(instructorRole);
        when(site.getMember("instructor")).thenReturn(instructorMember);
        var rows = queries.roster(a);
        assertEquals(2, rows.size());
        assertEquals(1, rows.stream().filter(row -> "missing".equals(row.get("status"))).count());
    }

    @Test
    public void anonymousReadDoesNotExposeRoster() {
        when(assignments.assignmentUsesAnonymousGrading(a)).thenReturn(true);
        var context = queries.context("course-a", "assignment-a");
        assertFalse((Boolean) ((Map<?, ?>) context.get("supported")).get("prepare"));
        assertThrows(
                ResponseStatusException.class,
                () -> queries.roster(a));
        verify(assignments, never()).getSubmissions(any());
    }

    @Test
    public void groupGraderCannotReadOtherStudent() {
        when(security.unlock(anyString(), anyString())).thenReturn(false);
        Group group = mock(Group.class);
        when(group.getUsers()).thenReturn(Set.of("student-b"));
        when(assignments.getGroupsAllowGradeAssignment(anyString())).thenReturn(List.of(group));
        assertEquals(
                HttpStatus.FORBIDDEN,
                assertThrows(
                                ResponseStatusException.class,
                                () -> authorization.submission(a, "submission-a"))
                        .getStatus());
    }

    @Test
    public void contextCannotClaimReadinessWithoutStore() {
        when(config.getString("mcp.assignment.grading.storage", "")).thenReturn("");
        var context = queries.context("course-a", "assignment-a");
        assertFalse((Boolean) ((Map<?, ?>) context.get("supported")).get("save"));
    }







    /** Optional synthetic outputs validate the Java/Python wire contract across implementations. */
    @Test
    public void emitSyntheticWireContractFixtures() throws Exception {
        String folder = System.getProperty("mcp.grading.contractFixtures");
        if (folder == null) return;
        Path directory = Path.of(folder);
        Files.createDirectories(directory);
        var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
        var output = new LinkedHashMap<String, Object>();
        output.put("get_assignment_grading_context", queries.context("course-a", "assignment-a"));
        // Other historical emitters retired; frozen fixtures are preserved.

        for (var entry : output.entrySet())
            mapper.writeValue(
                    directory.resolve(entry.getKey() + ".json").toFile(), entry.getValue());
    }
}
