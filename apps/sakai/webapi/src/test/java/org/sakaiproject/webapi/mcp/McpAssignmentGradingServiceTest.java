/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.sakaiproject.webapi.mcp.McpAssessmentService.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.io.ByteArrayInputStream;
import java.time.Instant;
import java.util.*;
import java.util.function.Function;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.sakaiproject.assignment.api.*;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.assignment.api.model.AssignmentSubmissionSubmitter;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.*;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.grading.api.*;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.*;
import org.sakaiproject.tool.api.*;
import org.sakaiproject.user.api.*;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpAssignmentGradingServiceTest {
    @Rule public TemporaryFolder temporary=new TemporaryFolder();
    AssignmentService assignments; ServerConfigurationService config; SecurityService security;
    McpAssignmentGradingService service; McpAssessmentService metadata; GradingService grading; GradingAuthz authz;
    Assignment a; AssignmentSubmission s; User student; Site site; Session session; ContentHostingService content;
    @Before public void setup() throws Exception {
        assignments=mock(AssignmentService.class); config=mock(ServerConfigurationService.class); security=mock(SecurityService.class);
        SessionManager sessions=mock(SessionManager.class);session=mock(Session.class);when(sessions.getCurrentSession()).thenReturn(session);when(session.getUserId()).thenReturn("ta");
        SiteService sites=mock(SiteService.class);site=mock(Site.class);when(site.getType()).thenReturn("course");when(site.getTitle()).thenReturn("Synthetic course");when(site.getUsers()).thenReturn(Set.of("student-a","student-b"));when(sites.getSiteVisit("course-a")).thenReturn(site);
        when(config.getBoolean("mcp.assignment.grading.enabled",false)).thenReturn(true);
        Path root=temporary.newFolder("private").toPath();Files.setPosixFilePermissions(root,PosixFilePermissions.fromString("rwx------"));when(config.getString("mcp.assignment.grading.storage","")).thenReturn(root.toRealPath().toString());
        when(security.unlock(eq(AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION),anyString())).thenReturn(true);
        when(assignments.allowGradeSubmission(anyString())).thenReturn(true);
        a=new Assignment();a.setId("assignment-a");a.setContext("course-a");a.setTitle("Quiz");a.setInstructions("Five MCQs");a.setTypeOfGrade(Assignment.GradeType.SCORE_GRADE_TYPE);a.setScaleFactor(10);a.setMaxGradePoint(50);a.setDueDate(Instant.parse("2026-10-08T00:00:00Z"));a.setTypeOfSubmission(Assignment.SubmissionType.SINGLE_ATTACHMENT_SUBMISSION);
        when(assignments.getAssignmentWithGradingEvidence("assignment-a")).thenReturn(a);
        s=new AssignmentSubmission();s.setId("submission-a");s.setAssignment(a);s.setSubmitted(true);s.setUserSubmission(true);s.setDateSubmitted(Instant.parse("2026-10-07T00:00:00Z"));s.setDateModified(s.getDateSubmitted());
        AssignmentSubmissionSubmitter submitter=new AssignmentSubmissionSubmitter();submitter.setSubmitter("student-a");submitter.setSubmission(s);s.setSubmitters(Set.of(submitter));
        when(assignments.getSubmissions(a)).thenReturn(Set.of(s));when(assignments.getSubmissionWithGradingEvidence("submission-a")).thenReturn(s);
        student=mock(User.class);when(student.getId()).thenReturn("student-a");when(student.getEid()).thenReturn("synthetic-a");when(student.getDisplayName()).thenReturn("Synthetic A");
        User other=mock(User.class);when(other.getId()).thenReturn("student-b");when(other.getEid()).thenReturn("synthetic-b");when(other.getDisplayName()).thenReturn("Synthetic B");
        when(assignments.allowAddSubmissionUsers(anyString())).thenReturn(List.of(student,other));UserDirectoryService users=mock(UserDirectoryService.class);when(users.getUser("student-a")).thenReturn(student);when(users.getUser("student-b")).thenReturn(other);
        grading=mock(GradingService.class);authz=mock(GradingAuthz.class);content=mock(ContentHostingService.class);
        metadata=mock(McpAssessmentService.class);when(metadata.revision(any())).thenReturn("config");
        FormattedText formatted=mock(FormattedText.class);when(formatted.escapeHtmlFormattedText(anyString())).thenAnswer(i -> i.getArgument(0));when(formatted.convertFormattedTextToPlaintext(any())).thenAnswer(i -> i.getArgument(0));
        service=new McpAssignmentGradingService(sessions,sites,assignments,security,config,users,content,grading,authz,mock(RubricsService.class),formatted,metadata,new McpGradingStore(config));
        when(assignments.withGradingSubmissionLock(anyString(),any())).thenAnswer(i -> ((Function<AssignmentSubmission,Object>)i.getArgument(1)).apply(s));
        doAnswer(i -> { s.setLockVersion(s.getLockVersion()+1); return null; }).when(assignments).updateSubmission(any());
    }
    @Test public void gatesAndForeignSiteDenyBeforeContent() {
        when(config.getBoolean("mcp.assignment.grading.enabled",false)).thenReturn(false);
        assertEquals(HttpStatus.NOT_FOUND,assertThrows(ResponseStatusException.class,() -> service.context("course-a","assignment-a")).getStatus());
        verify(assignments,never()).getSubmissions(any());
    }
    @Test public void gradePermissionIsRequired() {
        when(assignments.allowGradeSubmission(anyString())).thenReturn(false);
        assertEquals(HttpStatus.FORBIDDEN,assertThrows(ResponseStatusException.class,() -> service.context("course-a","assignment-a")).getStatus());
    }
    @Test public void rosterIncludesMissingAndPaginatedSourceIsComplete() {
        var first=service.list("course-a","assignment-a",null,1);assertNotNull(first.get("next_cursor"));
        var second=service.list("course-a","assignment-a",(String)first.get("next_cursor"),1);
        var row=((List<Map<String,Object>>)second.get("items")).get(0);assertEquals("missing",row.get("status"));assertNull(row.get("submission_id"));assertNull(row.get("attempt_count"));
        verify(grading,never()).getAssignments(anyString(),anyString(),any());
    }
    @Test public void cursorIsBoundToActorAndCurrentMetadata() {
        String cursor=(String)service.list("course-a","assignment-a",null,1).get("next_cursor");session.setUserId("other");when(session.getUserId()).thenReturn("other");
        assertEquals(HttpStatus.CONFLICT,assertThrows(ResponseStatusException.class,() -> service.list("course-a","assignment-a",cursor,1)).getStatus());
    }
    @Test public void anonymousReadDoesNotExposeRoster() {
        when(assignments.assignmentUsesAnonymousGrading(a)).thenReturn(true);
        var context=service.context("course-a","assignment-a");assertFalse((Boolean)((Map<?,?>)context.get("supported")).get("prepare"));
        assertThrows(ResponseStatusException.class,() -> service.list("course-a","assignment-a",null,50));
        verify(assignments,never()).getSubmissions(any());
    }
    @Test public void groupGraderCannotReadOtherStudent() {
        when(security.unlock(anyString(),anyString())).thenReturn(false);Group group=mock(Group.class);when(group.getUsers()).thenReturn(Set.of("student-b"));when(assignments.getGroupsAllowGradeAssignment(anyString())).thenReturn(List.of(group));
        assertEquals(HttpStatus.FORBIDDEN,assertThrows(ResponseStatusException.class,() -> service.detail("course-a","assignment-a","submission-a")).getStatus());
    }
    Map<String,Object> row(String score) { return obj("submission_id",s.getId(),"sakai_user_id","student-a","expected_content_revision",service.contentRevision(s),"expected_grade_revision",service.gradeRevision(s),"score",score,"feedback",obj("action","preserve","text",null)); }
    Map<String,Object> request(String kind,List<Map<String,Object>> rows) { var request=obj("operation_id",UUID.randomUUID().toString(),"mode","commit","expected_assignment_revision","config","grades",rows);
        request.put("payload_sha256",service.hash(service.canonical(obj("kind",kind,"course_id","course-a","assignment_id","assignment-a","expected_assignment_revision","config","grades",rows))));return request; }
    @Test public void savePreservesStudentEvidenceAndUnreleasedFlagsAndReplayDoesNotWrite() throws Exception {
        s.setSubmittedText("A C B D A");s.setPrivateNotes("preserve");s.getProperties().put(AssignmentConstants.ALLOW_EXTENSION_CLOSETIME,"123");
        var request=request("save",List.of(row("4")));var result=service.write("course-a","assignment-a","save",request);
        assertEquals("completed",result.get("outcome"));assertEquals("40",s.getGrade());assertFalse(s.getGradeReleased());assertFalse(s.getReturned());assertEquals("preserve",s.getPrivateNotes());assertEquals("123",s.getProperties().get(AssignmentConstants.ALLOW_EXTENSION_CLOSETIME));assertEquals("A C B D A",s.getSubmittedText());
        assertEquals(result,service.write("course-a","assignment-a","save",request));verify(assignments,times(1)).updateSubmission(s);verify(grading,never()).updateExternalAssessmentScore(anyString(),anyString(),anyString(),anyString(),anyString());
    }
    @Test public void validateAndAboveMaximumNeverWrite() throws Exception {
        var request=request("save",List.of(row("4")));request.put("mode","validate");assertEquals("validated",service.write("course-a","assignment-a","save",request).get("outcome"));
        assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request("save",List.of(row("6")))));verify(assignments,never()).updateSubmission(any());
    }
    @Test public void resubmissionAndReleasedRowsConflict() throws Exception {
        var request=request("save",List.of(row("4")));s.setSubmittedText("changed");assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request));
        s.setGradeReleased(true);assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request("save",List.of(row("4")))));verify(assignments,never()).updateSubmission(any());
    }
    @Test public void uncertainNativeOutcomeIsJournaledAndNeverReplayed() throws Exception {
        doThrow(new RuntimeException("private-data-must-not-leak")).when(assignments).updateSubmission(any());
        var request=request("save",List.of(row("4")));var result=service.write("course-a","assignment-a","save",request);
        assertEquals("partial",result.get("outcome"));assertFalse(result.toString().contains("private-data"));
        assertEquals(result,service.write("course-a","assignment-a","save",request));verify(assignments,times(1)).updateSubmission(any());
    }
    @Test public void releaseAndReturnAreSeparateFromSave() {
        service.write("course-a","assignment-a","save",request("save",List.of(row("4"))));
        var row=obj("submission_id",s.getId(),"sakai_user_id","student-a","expected_content_revision",service.contentRevision(s),"expected_grade_revision",service.gradeRevision(s),"expected_score","4","expected_feedback_sha256",null);
        var result=service.write("course-a","assignment-a","release",request("release",List.of(row)));
        assertEquals("completed",result.get("outcome"));assertTrue(s.getReturned());assertTrue(s.getGradeReleased());assertNotNull(s.getDateReturned());
    }
    @Test public void exportedBytesAreChecksummedAndExpiryAndOwnershipAreEnforced() throws Exception {
        s.setSubmittedText("A\nC\nB\nD\nA\n");
        var request=obj("export_request_id",UUID.randomUUID().toString(),"expected_assignment_revision","config","submissions",List.of(obj("submission_id",s.getId(),"expected_content_revision",service.contentRevision(s))));
        var receipt=service.export("course-a","assignment-a",request);String eid=(String)receipt.get("export_id");
        var status=service.exportStatus("course-a","assignment-a",eid,null,50);var artifact=((List<Map<String,Object>>)status.get("artifacts")).get(0);
        var file=service.download("course-a","assignment-a",eid,(String)artifact.get("artifact_id"));assertEquals(digest(s.getSubmittedText()),file.sha256());assertEquals(s.getSubmittedText(),Files.readString(file.path()));
        when(session.getUserId()).thenReturn("other");assertThrows(ResponseStatusException.class,() -> service.download("course-a","assignment-a",eid,(String)artifact.get("artifact_id")));
    }
    @Test public void contextCannotClaimReadinessWithoutStore() {
        when(config.getString("mcp.assignment.grading.storage","")).thenReturn("");var context=service.context("course-a","assignment-a");
        assertFalse((Boolean)((Map<?,?>)context.get("supported")).get("save"));
    }

    org.sakaiproject.grading.api.Assignment external() {
        var item=new org.sakaiproject.grading.api.Assignment();item.setId(7L);item.setPoints(5.0);item.setExternallyMaintained(true);item.setExternalId(assignmentRef(a));item.setReleased(false);item.setCounted(true);
        when(grading.isGradebookInitialized("course-a")).thenReturn(true);when(grading.getAssignments(anyString(),anyString(),any())).thenReturn(List.of(item));
        when(authz.isUserAbleToGradeItemForStudent(anyString(),anyString(),eq(7L),eq("student-a"))).thenReturn(true);return item;
    }
    Map<String,Object> returnRequest() {
        s.setGrade("40");s.setGraded(true);
        return request("release",List.of(obj("submission_id",s.getId(),"sakai_user_id","student-a","expected_content_revision",service.contentRevision(s),"expected_grade_revision",service.gradeRevision(s),"expected_score","4","expected_feedback_sha256",null)));
    }
    @Test public void externalProjectionPreservesItemVisibility() {
        var item=external();service.write("course-a","assignment-a","release",returnRequest());
        verify(grading).updateExternalAssessmentScore("course-a","course-a",assignmentRef(a),"student-a","4");verify(grading).updateExternalAssessmentComment("course-a","course-a",assignmentRef(a),"student-a",null);
        assertFalse(item.getReleased());assertTrue(item.getCounted());
    }
    @Test public void projectionFailureRetainsAssignmentStageAndReplayDoesNotNotify() throws Exception {
        external();doThrow(new RuntimeException("projection failure")).when(grading).updateExternalAssessmentComment(anyString(),anyString(),anyString(),anyString(),any());
        var request=returnRequest();var result=service.write("course-a","assignment-a","release",request);assertEquals("partial",result.get("outcome"));
        assertEquals("assignment_released",((List<Map<String,Object>>)result.get("rows")).get(0).get("stage"));assertEquals(result,service.write("course-a","assignment-a","release",request));verify(assignments,times(1)).updateSubmission(any());
    }
    @Test public void resubmissionBeforeProjectionDeniesProjection() throws Exception {
        external();doAnswer(new org.mockito.stubbing.Answer<Object>() {
            int calls; public Object answer(org.mockito.invocation.InvocationOnMock i) { if(++calls==2) s.setSubmittedText("new attempt");return ((Function<AssignmentSubmission,Object>)i.getArgument(1)).apply(s); }
        }).when(assignments).withGradingSubmissionLock(anyString(),any());
        assertEquals("partial",service.write("course-a","assignment-a","release",returnRequest()).get("outcome"));verify(grading,never()).updateExternalAssessmentScore(anyString(),anyString(),anyString(),anyString(),anyString());
    }
    @Test public void gradebookPermissionAndMismatchedAssociationDenyBeforeWriting() throws Exception {
        external();when(authz.isUserAbleToGradeItemForStudent(anyString(),anyString(),anyLong(),anyString())).thenReturn(false);
        assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request("save",List.of(row("4")))));
        a.getProperties().put(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT,"unrelated-item");assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request("save",List.of(row("4")))));verify(assignments,never()).updateSubmission(any());
    }
    @Test public void withdrawnStudentCannotReceiveNewOfficialGrade() throws Exception {
        when(site.getUsers()).thenReturn(Set.of("student-b"));assertThrows(ResponseStatusException.class,() -> service.write("course-a","assignment-a","save",request("save",List.of(row("4")))));verify(assignments,never()).updateSubmission(any());
    }
    @Test public void expiredArtifactIsDeniedAndRemoved() throws Exception {
        s.setSubmittedText("A");var request=obj("export_request_id",UUID.randomUUID().toString(),"expected_assignment_revision","config","submissions",List.of(obj("submission_id",s.getId(),"expected_content_revision",service.contentRevision(s))));
        String eid=(String)service.export("course-a","assignment-a",request).get("export_id");var status=service.exportStatus("course-a","assignment-a",eid,null,50);String aid=(String)((List<Map<String,Object>>)status.get("artifacts")).get(0).get("artifact_id");var file=service.download("course-a","assignment-a",eid,aid);
        service.store.locked(service.store.key("ta","course-a","assignment-a",eid,"export"),directory -> { try { var record=service.store.read(directory);record.put("expires_at","2020-01-01T00:00:00Z");service.store.write(directory,record);return null; } catch(Exception e) { throw new RuntimeException(e); } });
        assertEquals(HttpStatus.GONE,assertThrows(ResponseStatusException.class,() -> service.download("course-a","assignment-a",eid,aid)).getStatus());assertFalse(Files.exists(file.path()));
    }
    /** Optional synthetic outputs validate the Java/Python wire contract across implementations. */
    @Test public void emitSyntheticWireContractFixtures() throws Exception {
        String folder=System.getProperty("mcp.grading.contractFixtures");if(folder==null) return;
        Path directory=Path.of(folder);Files.createDirectories(directory);var mapper=new com.fasterxml.jackson.databind.ObjectMapper();
        var output=new LinkedHashMap<String,Object>();output.put("get_assignment_grading_context",service.context("course-a","assignment-a"));output.put("list_assignment_submissions",service.list("course-a","assignment-a",null,100));output.put("get_assignment_submission",service.detail("course-a","assignment-a",s.getId()));
        s.setSubmittedText("A");var exp=service.export("course-a","assignment-a",obj("export_request_id",UUID.randomUUID().toString(),"expected_assignment_revision","config","submissions",List.of(obj("submission_id",s.getId(),"expected_content_revision",service.contentRevision(s)))));output.put("export_assignment_submissions",exp);output.put("get_assignment_submission_export",service.exportStatus("course-a","assignment-a",(String)exp.get("export_id"),null,100));
        var save=request("save",List.of(row("4")));output.put("save_assignment_grades",service.write("course-a","assignment-a","save",save));output.put("get_assignment_grading_operation",service.operation("course-a","assignment-a",(String)save.get("operation_id")));output.put("release_assignment_grades",service.write("course-a","assignment-a","release",returnRequest()));output.put("get_assignment_grades",service.grades("course-a","assignment-a",obj("rows",List.of(obj("submission_id",s.getId(),"sakai_user_id","student-a")))));
        for(var entry:output.entrySet()) mapper.writeValue(directory.resolve(entry.getKey()+".json").toFile(),entry.getValue());
    }
}
