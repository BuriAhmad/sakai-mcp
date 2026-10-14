/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import static org.sakaiproject.webapi.mcp.McpAssessmentService.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.*;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.sakaiproject.assignment.api.*;
import org.sakaiproject.assignment.api.model.*;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.authz.api.Member;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.*;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.exception.*;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.GradingAuthz;
import org.sakaiproject.grading.api.SortType;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.*;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.*;
import org.sakaiproject.util.api.FormattedText;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/** Delegated grading coordinator; no administrator identity or generic URL proxy. */
@Service
public class McpAssignmentGradingService {
    final AssignmentService assignments;
    final GradingService grading;
    final ContentHostingService content;
    final McpGradingStore store;
    private final SessionManager sessions;
    private final SiteService sites;
    private final SecurityService security;
    private final ServerConfigurationService config;
    private final UserDirectoryService users;
    private final GradingAuthz authz;
    private final RubricsService rubrics;
    private final FormattedText formatted;
    private final McpAssessmentService metadata;
    private final ObjectMapper mapper = new ObjectMapper();
    static final long FILE_LIMIT = 10L * 1024 * 1024, EXPORT_LIMIT = 100L * 1024 * 1024;

    public McpAssignmentGradingService(@Qualifier("org.sakaiproject.tool.api.SessionManager") SessionManager sessions,
            SiteService sites, AssignmentService assignments, SecurityService security, ServerConfigurationService config,
            UserDirectoryService users, ContentHostingService content,
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            @Qualifier("org.sakaiproject.grading.api.GradingAuthz") GradingAuthz authz,
            RubricsService rubrics, FormattedText formatted, McpAssessmentService metadata, McpGradingStore store) {
        this.sessions=sessions; this.sites=sites; this.assignments=assignments; this.security=security;
        this.config=config; this.users=users; this.content=content; this.grading=grading; this.authz=authz;
        this.rubrics=rubrics; this.formatted=formatted; this.metadata=metadata; this.store=store;
    }
    String actor() {
        String actor = sessions.getCurrentSession().getUserId();
        if (actor == null || actor.isBlank()) throw failure(HttpStatus.UNAUTHORIZED);
        return actor;
    }
    Assignment assignment(String site, String id) {
        if (!config.getBoolean("mcp.assignment.grading.enabled", false)) throw failure(HttpStatus.NOT_FOUND);
        actor();
        try {
            Site course = sites.getSiteVisit(site);
            if (!"course".equals(course.getType())) throw failure(HttpStatus.NOT_FOUND);
            Assignment a=assignments.getAssignmentWithGradingEvidence(id);
            if (!site.equals(a.getContext()) || Boolean.TRUE.equals(a.getDeleted()) || Boolean.TRUE.equals(a.getDraft())) throw failure(HttpStatus.NOT_FOUND);
            if (!assignments.allowGradeSubmission(assignmentRef(a))) throw failure(HttpStatus.FORBIDDEN);
            return a;
        } catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
        catch (IdUnusedException e) { throw failure(HttpStatus.NOT_FOUND); }
    }
    boolean siteGrader(Assignment a) { return security.unlock(AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION, SiteService.REFERENCE_ROOT + "/" + a.getContext()); }
    Set<String> scope(Assignment a) {
        if (siteGrader(a)) return null;
        Set<String> permitted = assignments.getGroupsAllowGradeAssignment(assignmentRef(a)).stream().flatMap(g -> g.getUsers().stream()).collect(Collectors.toSet());
        if (permitted.isEmpty()) throw failure(HttpStatus.FORBIDDEN);
        return permitted;
    }
    boolean allowed(Assignment a, AssignmentSubmission sub) {
        Set<String> scope=scope(a);
        if (scope==null) return true;
        if (sub.getGroupId()!=null && assignments.getGroupsAllowGradeAssignment(assignmentRef(a)).stream().noneMatch(g -> sub.getGroupId().equals(g.getId()))) return false;
        return !sub.getSubmitters().isEmpty() && sub.getSubmitters().stream().allMatch(s -> scope.contains(s.getSubmitter()));
    }
    AssignmentSubmission submission(Assignment a, String id) {
        try {
            AssignmentSubmission s=assignments.getSubmissionWithGradingEvidence(id);
            if (s == null) throw failure(HttpStatus.NOT_FOUND);
            if (!a.getId().equals(s.getAssignment().getId())) throw failure(HttpStatus.NOT_FOUND);
            if (!allowed(a,s)) throw failure(HttpStatus.FORBIDDEN);
            return s;
        } catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
    }
    List<String> unsupported(Assignment a) {
        List<String> reasons=new ArrayList<>();
        if (Boolean.TRUE.equals(a.getIsGroup()) || a.getTypeOfAccess()!=Assignment.Access.SITE) reasons.add("group_assignment");
        if (assignments.assignmentUsesAnonymousGrading(a)) reasons.add("anonymous_grading");
        if (a.getTypeOfGrade()!=Assignment.GradeType.SCORE_GRADE_TYPE) reasons.add("non_point_grade");
        if (Boolean.TRUE.equals(a.getAllowPeerAssessment())) reasons.add("peer_assessment");
        if (a.getTypeOfSubmission()==null || a.getTypeOfSubmission().ordinal()>5) reasons.add("external_submission");
        if (rubrics.hasAssociatedRubric(AssignmentConstants.TOOL_ID,a.getId())) reasons.add("rubric_integration");
        return reasons;
    }
    void identityRead(Assignment a) { if (assignments.assignmentUsesAnonymousGrading(a)) throw failure(HttpStatus.NOT_IMPLEMENTED); }
    static String decimal(String scaled, int factor) {
        if (scaled==null || scaled.isBlank()) return null;
        try { return new BigDecimal(scaled).divide(BigDecimal.valueOf(factor)).stripTrailingZeros().toPlainString(); }
        catch (RuntimeException e) { throw failure(HttpStatus.NOT_IMPLEMENTED); }
    }
    Map<String,Object> identity(String uid) {
        try { User u=users.getUser(uid); return obj("sakai_user_id",uid,"eid",u.getEid(),"display_name",u.getDisplayName()); }
        catch (UserNotDefinedException e) { return obj("sakai_user_id",uid,"eid",null,"display_name",null); }
    }
    List<String> submitters(AssignmentSubmission s) { return s.getSubmitters().stream().map(AssignmentSubmissionSubmitter::getSubmitter).sorted().toList(); }
    String hash(Object value) {
        try { return digest(mapper.writeValueAsString(value)); }
        catch (IOException e) { throw failure(HttpStatus.INTERNAL_SERVER_ERROR); }
    }
    ContentResource resource(String reference) throws PermissionException, IdUnusedException, TypeException {
        return content.getResource(assignments.removeReferencePrefix(reference));
    }
    List<Map<String,Object>> attachments(AssignmentSubmission s) {
        if (s.getAttachments().size()>20) throw failure(HttpStatus.BAD_REQUEST);
        List<Map<String,Object>> result=new ArrayList<>();
        for (String reference : s.getAttachments().stream().sorted().toList()) {
            String key=digest(reference);
            try {
                ContentResource r=resource(reference);
                String kind=ResourceProperties.TYPE_URL.equals(r.getContentType()) ? "url" :
                        "true".equals(r.getProperties().getProperty(AssignmentConstants.PROP_INLINE_SUBMISSION)) ? "inline_content_review" : "file";
                String sha=r.getContentSha256();
                // Missing authoritative resource hash cannot safely support content writes/export.
                result.add(obj("artifact_key",key,"original_name",Optional.ofNullable(r.getProperties().getProperty(ResourceProperties.PROP_DISPLAY_NAME)).orElse(key),
                    "content_type",r.getContentType(),"size_bytes",r.getContentLength(),"resource_revision",sha,
                    "kind",kind,"readable",sha!=null && sha.matches("[a-fA-F0-9]{64}")));
            } catch (Exception e) { result.add(obj("artifact_key",key,"original_name",key,"content_type",null,"size_bytes",null,"resource_revision",null,"kind","file","readable",false)); }
        }
        return result;
    }
    List<Map<String,Object>> assignmentAttachments(Assignment a) {
        AssignmentSubmission evidence=new AssignmentSubmission(); evidence.setAttachments(a.getAttachments()); return attachments(evidence);
    }
    String contentRevision(AssignmentSubmission s) {
        return hash(obj("id",s.getId(),"users",submitters(s),"submitted",s.getSubmitted(),"user",s.getUserSubmission(),
                "at",stamp(s.getDateSubmitted()),"text",s.getSubmittedText(),"attachments",attachments(s)));
    }
    String gradeRevision(AssignmentSubmission s) {
        return hash(obj("grade",s.getGrade(),"feedback",s.getFeedbackComment(),"graded",s.getGraded(),"released",s.getGradeReleased(),
            "returned",s.getReturned(),"at",stamp(s.getDateReturned()),"version",s.getLockVersion()));
    }
    Map<String,Object> flags(AssignmentSubmission s) { return obj("submitted",Boolean.TRUE.equals(s.getSubmitted()),"user_submission",Boolean.TRUE.equals(s.getUserSubmission()),"graded",Boolean.TRUE.equals(s.getGraded()),"grade_released",Boolean.TRUE.equals(s.getGradeReleased()),"returned",Boolean.TRUE.equals(s.getReturned())); }
    static Integer count(String value) { try { return value==null ? null : Integer.valueOf(value); } catch (RuntimeException e) { return null; } }
    static String instant(String value) { try { return value==null ? null : Instant.ofEpochMilli(Long.parseLong(value)).toString(); } catch (RuntimeException e) { return null; } }
    Map<String,Object> overrides(AssignmentSubmission s) {
        return obj("remaining_resubmissions",s==null?null:count(s.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_NUMBER)),
            "resubmission_close_at",s==null?null:instant(s.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME)),
            "extension_close_at",s==null?null:instant(s.getProperties().get(AssignmentConstants.ALLOW_EXTENSION_CLOSETIME)),"warnings",List.of());
    }
    Map<String,Object> entry(Assignment a, String uid, AssignmentSubmission s, boolean orphan) {
        String status=s==null?"missing":orphan?"orphan":!Boolean.TRUE.equals(s.getUserSubmission())?"placeholder":!Boolean.TRUE.equals(s.getSubmitted())?"draft":
            Boolean.TRUE.equals(s.getReturned())&&!Boolean.TRUE.equals(s.getGraded())?"ungraded_resubmission":"submitted";
        String late=s==null||s.getDateSubmitted()==null||a.getDueDate()==null?"unknown":s.getDateSubmitted().isAfter(a.getDueDate())?"late":"on_time";
        return obj("student",uid==null?null:identity(uid),"submitters",s==null?List.of():submitters(s).stream().map(this::identity).toList(),
            "submission_id",s==null?null:s.getId(),"group_id",s==null?null:s.getGroupId(),"status",status,"flags",s==null?null:flags(s),
            "submitted_at",s==null?null:stamp(s.getDateSubmitted()),"returned_at",s==null?null:stamp(s.getDateReturned()),
            "content_revision",s==null?null:contentRevision(s),"grade_revision",s==null?null:gradeRevision(s),"attempt_count",null,
            "history_completeness","current_only","inline_text_present",s!=null&&s.getSubmittedText()!=null&&!s.getSubmittedText().isBlank(),
            "attachments",s==null?List.of():attachments(s),"attachments_complete",true,"late_status",late,"overrides",overrides(s),
            "score",s==null||a.getTypeOfGrade()!=Assignment.GradeType.SCORE_GRADE_TYPE?null:decimal(s.getGrade(),a.getScaleFactor()),"warnings",List.of());
    }
    List<Map<String,Object>> roster(Assignment a) {
        identityRead(a);
        Set<String> scope=scope(a);
        Site course;
        try { course=sites.getSiteVisit(a.getContext()); }
        catch (Exception e) { throw failure(HttpStatus.FORBIDDEN); }
        List<String> eligible=assignments.allowAddSubmissionUsers(assignmentRef(a)).stream().map(User::getId)
            .filter(id -> scope==null||scope.contains(id))
            .filter(id -> {
                Member member=course.getMember(id);
                return member!=null && member.isActive() && member.getRole()!=null
                    && member.getRole().isAllowed(AssignmentServiceConstants.SECURE_ADD_ASSIGNMENT_SUBMISSION)
                    && !member.getRole().isAllowed(AssignmentServiceConstants.SECURE_GRADE_ASSIGNMENT_SUBMISSION);
            }).sorted().toList();
        if (eligible.size()>5000 || assignments.getSubmissions(a).size()>5000) throw failure(HttpStatus.BAD_REQUEST);
        Set<String> active=course.getUsers();
        eligible=eligible.stream().filter(active::contains).toList();
        Map<String,AssignmentSubmission> byUser=new HashMap<>();
        List<AssignmentSubmission> orphan=new ArrayList<>();
        for (AssignmentSubmission s:assignments.getSubmissions(a)) if (allowed(a,s)) {
            if (Boolean.TRUE.equals(a.getIsGroup())) { orphan.add(s); continue; }
            for (String uid:submitters(s)) {
                if (!eligible.contains(uid)) { orphan.add(s); continue; }
                if (byUser.put(uid,s)!=null) throw failure(HttpStatus.CONFLICT);
            }
        }
        List<Map<String,Object>> rows=new ArrayList<>();
        for (String uid:eligible) rows.add(entry(a,uid,byUser.get(uid),false));
        for (AssignmentSubmission s:orphan.stream().distinct().sorted(Comparator.comparing(AssignmentSubmission::getId)).toList()) rows.add(entry(a,null,s,true));
        return rows;
    }
    Map<String,Object> completeness(Assignment a) { return obj("complete",true,"scope",siteGrader(a)?"site":"groups","reasons",List.of()); }
    org.sakaiproject.grading.api.Assignment linked(Assignment a) {
        if (!grading.isGradebookInitialized(a.getContext())) return null;
        if (grading.isGradebookGroupEnabled(a.getContext())) throw failure(HttpStatus.NOT_IMPLEMENTED);
        String association=a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT);
        var items=grading.getAssignments(a.getContext(),a.getContext(),SortType.SORT_BY_NONE);
        if (items.size()>500) throw failure(HttpStatus.BAD_REQUEST);
        List<org.sakaiproject.grading.api.Assignment> matches=items.stream().filter(i -> assignmentRef(a).equals(i.getExternalId()) || association!=null&&(association.equals(String.valueOf(i.getId()))||association.equals(i.getExternalId()))).toList();
        if (matches.size()>1) throw failure(HttpStatus.CONFLICT);
        if (!matches.isEmpty() && association!=null && !association.equals(String.valueOf(matches.get(0).getId())) && !association.equals(matches.get(0).getExternalId())) throw failure(HttpStatus.CONFLICT);
        return matches.isEmpty()?null:matches.get(0);
    }
    Map<String,Object> link(Assignment a) {
        try {
            var item=linked(a);
            boolean missing=item==null&&a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT)!=null;
            return obj("mode",item==null?(missing?"unknown":"none"):Boolean.TRUE.equals(item.getExternallyMaintained())?"external":"internal",
                "gradebook_uid",item==null?null:a.getContext(),"item_id",item==null?null:String.valueOf(item.getId()),"external_id",item==null?null:item.getExternalId(),
                "released",item==null?null:item.getReleased(),"counted",item==null?null:item.getCounted(),"available",!missing,"reason",missing?"missing_link":null);
        } catch (RuntimeException e) { return obj("mode","unknown","gradebook_uid",null,"item_id",null,"external_id",null,"released",null,"counted",null,"available",false,"reason","projection_unavailable"); }
    }
    public Map<String,Object> context(String site,String id) {
        Assignment a=assignment(site,id); List<String> reasons=unsupported(a);
        boolean anonymous=assignments.assignmentUsesAnonymousGrading(a);
        List<Map<String,Object>> rows=anonymous?List.of():roster(a);
        var link=link(a);
        boolean supported=reasons.isEmpty()&&siteGrader(a)&&store.configured()&&Boolean.TRUE.equals(link.get("available"))&&Set.of("none","external").contains(link.get("mode"));
        if(supported) { try { writable(a); } catch(RuntimeException e) { supported=false; reasons.add("unsupported_gradebook_link"); } }
        if (!store.configured()) reasons.add("storage_not_configured");
        if (!siteGrader(a)) reasons.add("scoped_write_unsupported");
        return obj("schema_version","1","observed_at",stamp(Instant.now()),"course",obj("id",site,"title",title(site)),
            "assignment",obj("id",id,"title",a.getTitle(),"instructions",a.getInstructions()==null?"":a.getInstructions(),"configuration_revision",metadata.revision(a),
                "grade_type",a.getTypeOfGrade().name(),"max_points",a.getTypeOfGrade()==Assignment.GradeType.SCORE_GRADE_TYPE?decimal(String.valueOf(a.getMaxGradePoint()),a.getScaleFactor()):null,
                "scale_factor",a.getScaleFactor(),"submission_type",a.getTypeOfSubmission().name(),"draft",false,"deleted",false,
                "visible_at",stamp(a.getVisibleDate()),"open_at",stamp(a.getOpenDate()),"due_at",stamp(a.getDueDate()),"close_at",stamp(a.getCloseDate()),
                "group_submission",Boolean.TRUE.equals(a.getIsGroup()),"anonymous_grading",anonymous,"native_release_grades",Boolean.TRUE.equals(a.getReleaseGrades()),
                "resubmission_count",count(a.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_NUMBER)),"resubmission_close_at",instant(a.getProperties().get(AssignmentConstants.ALLOW_RESUBMIT_CLOSETIME)),
                "definition_reference",null,"definition_version",null,"attachments",assignmentAttachments(a),"integration_features",reasons),
            "gradebook",link,"permissions",obj("read_metadata",true,"read_content",!anonymous,"save_grades",supported,"release_grades",supported,"scope",siteGrader(a)?"site":"groups","scope_complete",siteGrader(a)),
            "submission_summary",obj("expected_students",anonymous?null:rows.stream().filter(r -> r.get("student")!=null).count(),"submitted",anonymous?null:rows.stream().filter(r -> Set.of("submitted","ungraded_resubmission").contains(r.get("status"))).count(),
                "missing",anonymous?null:rows.stream().filter(r -> "missing".equals(r.get("status"))).count(),"draft",anonymous?null:rows.stream().filter(r -> "draft".equals(r.get("status"))).count(),
                "graded",anonymous?null:rows.stream().filter(r -> r.get("score")!=null).count(),"orphan_records",anonymous?null:rows.stream().filter(r -> "orphan".equals(r.get("status"))).count()),
            "completeness",anonymous?obj("complete",false,"scope",siteGrader(a)?"site":"groups","reasons",List.of("anonymous_grading")):completeness(a),
            "supported",obj("prepare",!anonymous,"save",supported,"release",supported,"reasons",reasons),"warnings",List.of("current_content_only"));
    }
    String title(String site) { try { return sites.getSiteVisit(site).getTitle(); } catch (Exception e) { throw failure(HttpStatus.FORBIDDEN); } }
    public Map<String,Object> list(String site,String id,String cursor,Integer limit) {
        Assignment a=assignment(site,id); var rows=roster(a); String revision=hash(obj("actor",actor(),"site",site,"assignment",id,"rows",rows));
        int offset=0,size=limit==null?50:limit;
        if (size<1||size>100) throw failure(HttpStatus.BAD_REQUEST);
        if (cursor!=null) {
            String[] parts=cursor.split(":");
            if(parts.length!=2||!revision.equals(parts[0])) throw failure(HttpStatus.CONFLICT);
            try { offset=Integer.parseInt(parts[1]); } catch (RuntimeException e) { throw failure(HttpStatus.BAD_REQUEST); }
            if(offset<0||offset>rows.size()) throw failure(HttpStatus.BAD_REQUEST);
        }
        int end=Math.min(rows.size(),offset+size);
        return obj("items",rows.subList(offset,end),"next_cursor",end<rows.size()?revision+":"+end:null,"snapshot_revision",revision,"observed_at",stamp(Instant.now()),"completeness",completeness(a),"warnings",List.of());
    }
    public Map<String,Object> detail(String site,String id,String sid) {
        Assignment a=assignment(site,id); identityRead(a); AssignmentSubmission s=submission(a,sid);
        return obj("submission",entry(a,submitters(s).size()==1?submitters(s).get(0):null,s,false),"inline_text",s.getSubmittedText(),"inline_content_type",s.getSubmittedText()==null?null:"text/html",
            "feedback_comment",s.getFeedbackComment(),"feedback_sha256",s.getFeedbackComment()==null?null:digest(s.getFeedbackComment()),"observed_at",stamp(Instant.now()),"warnings",List.of());
    }
    public Map<String,Object> listAssignments(String site,String cursor,Integer limit) {
        if (!config.getBoolean("mcp.assignment.grading.enabled",false)) throw failure(HttpStatus.NOT_FOUND);
        actor();
        try { if (!"course".equals(sites.getSiteVisit(site).getType())) throw failure(HttpStatus.NOT_FOUND); }
        catch (PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
        catch (IdUnusedException e) { throw failure(HttpStatus.NOT_FOUND); }
        var available=assignments.getAssignmentsForContext(site);
        if (available.size()>5000) throw failure(HttpStatus.BAD_REQUEST);
        List<Map<String,Object>> items=available.stream()
            .filter(a -> site.equals(a.getContext()) && !Boolean.TRUE.equals(a.getDraft()) && !Boolean.TRUE.equals(a.getDeleted())
                && assignments.allowGradeSubmission(assignmentRef(a)))
            .sorted(Comparator.comparing(Assignment::getId))
            .map(a -> {
                // Hydrate grading evidence before hashing lazy groups/attachments/properties.
                Assignment hydrated=assignment(site,a.getId());
                return obj("assignment_id",hydrated.getId(),"title",hydrated.getTitle(),"configuration_revision",metadata.revision(hydrated));
            })
            .toList();
        String revision=hash(obj("actor",actor(),"site",site,"items",items));
        int size=limit==null?50:limit, offset=0;
        if(size<1||size>100) throw failure(HttpStatus.BAD_REQUEST);
        if(cursor!=null) {
            String[] parts=cursor.split(":");
            if(parts.length!=2||!revision.equals(parts[0])) throw failure(HttpStatus.CONFLICT);
            try { offset=Integer.parseInt(parts[1]); } catch(NumberFormatException e) { throw failure(HttpStatus.BAD_REQUEST); }
        }
        if(offset<0||offset>items.size()) throw failure(HttpStatus.BAD_REQUEST);
        int end=Math.min(items.size(),offset+size);
        return obj("items",items.subList(offset,end),"next_cursor",end<items.size()?revision+":"+end:null,"snapshot_revision",revision);
    }
    public record FileContents(byte[] bytes,String contentType,String sha256) {}
    FileContents readAttachment(Collection<String> references,String key) {
        if(!key.matches("[a-f0-9]{64}")) throw failure(HttpStatus.BAD_REQUEST);
        String reference=references.stream().filter(r -> digest(r).equals(key)).findFirst().orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
        try {
            ContentResource r=resource(reference);
            if(ResourceProperties.TYPE_URL.equals(r.getContentType()) || "true".equals(r.getProperties().getProperty(AssignmentConstants.PROP_INLINE_SUBMISSION)))
                throw failure(HttpStatus.NOT_IMPLEMENTED);
            String before=r.getContentSha256();
            if(before==null||!before.matches("[a-fA-F0-9]{64}")||r.getContentLength()>FILE_LIMIT) throw failure(HttpStatus.NOT_IMPLEMENTED);
            byte[] bytes;
            try(InputStream input=r.streamContent()) { bytes=input.readNBytes((int)FILE_LIMIT+1); }
            String sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            if(bytes.length>FILE_LIMIT || bytes.length!=r.getContentLength() || !sha.equalsIgnoreCase(before)
                    || !before.equalsIgnoreCase(resource(reference).getContentSha256())) throw failure(HttpStatus.CONFLICT);
            return new FileContents(bytes,r.getContentType()==null?"application/octet-stream":r.getContentType(),sha);
        } catch(PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
        catch(IdUnusedException e) { throw failure(HttpStatus.NOT_FOUND); }
        catch(IOException|TypeException|ServerOverloadException|java.security.NoSuchAlgorithmException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
    }
    public FileContents submissionFile(String site,String id,String sid,String file,String revision) {
        Assignment a=assignment(site,id); identityRead(a); AssignmentSubmission s=submission(a,sid);
        if(revision==null||!revision.equals(contentRevision(s))) throw failure(HttpStatus.CONFLICT);
        FileContents result;
        if("inline".equals(file)) {
            if(s.getSubmittedText()==null) throw failure(HttpStatus.NOT_FOUND);
            byte[] bytes=s.getSubmittedText().getBytes(StandardCharsets.UTF_8);
            if(bytes.length>65535) throw failure(HttpStatus.NOT_IMPLEMENTED);
            result=new FileContents(bytes,"text/html",digest(s.getSubmittedText()));
        } else result=readAttachment(s.getAttachments(),file);
        if(!revision.equals(contentRevision(submission(a,sid)))) throw failure(HttpStatus.CONFLICT);
        return result;
    }
    public FileContents assignmentFile(String site,String id,String file,String revision) {
        Assignment a=assignment(site,id); identityRead(a);
        // Assignment attachment bytes have their own revision, independently of configuration.
        var descriptor=assignmentAttachments(a).stream().filter(r -> file.equals(r.get("artifact_key"))).findFirst().orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
        if(revision==null||!revision.equalsIgnoreCase(Objects.toString(descriptor.get("resource_revision"),""))) throw failure(HttpStatus.CONFLICT);
        FileContents result=readAttachment(a.getAttachments(),file);
        if(!revision.equalsIgnoreCase(result.sha256()) || assignment(site,id).getAttachments().stream().noneMatch(r -> digest(r).equals(file))) throw failure(HttpStatus.CONFLICT);
        return result;
    }
    public Map<String,Object> createProposal(String site,String id,Map<String,Object> request) {
        fields(request,"proposal_id","export_id","payload");
        Assignment a=assignment(site,id); identityRead(a);
        String pid=McpGradingStore.uuid(string(request,"proposal_id")), eid=McpGradingStore.uuid(string(request,"export_id"));
        var export=exportStatus(site,id,eid,null,1);
        if(!(request.get("payload") instanceof Map<?,?> payload) || payload.isEmpty()) throw failure(HttpStatus.BAD_REQUEST);
        String requestHash=hash(request), key=store.key(actor(),site,id,pid,"proposal");
        return store.locked(key,directory -> {
            try {
                var old=store.read(directory);
                if(old!=null) {
                    store.requireUnexpired(directory,old);
                    if(!requestHash.equals(old.get("request_sha256"))) throw failure(HttpStatus.CONFLICT);
                    return old;
                }
                var record=obj("proposal_id",pid,"export_id",eid,"request_sha256",requestHash,"expires_at",export.get("expires_at"),"payload",payload);
                store.write(directory,record); return record;
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
    }
    public Map<String,Object> proposal(String site,String id,String pid) {
        Assignment a=assignment(site,id); identityRead(a);
        var record=store.locked(store.key(actor(),site,id,pid,"proposal"),directory -> {
            try {
                var found=store.read(directory); if(found==null) throw failure(HttpStatus.NOT_FOUND);
                store.requireUnexpired(directory,found); return found;
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
        exportStatus(site,id,string(record,"export_id"),null,1); // Reauthorize every source submission and export lifetime.
        return record;
    }
    static String string(Map<String,Object> value,String key) {
        Object v=value.get(key); if(!(v instanceof String s)||s.isBlank()||s.length()>2048) throw failure(HttpStatus.BAD_REQUEST); return s;
    }
    @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> value,String key) {
        if (!(value.get(key) instanceof List<?> list)||list.isEmpty()||list.size()>100||list.stream().anyMatch(v -> !(v instanceof Map))) throw failure(HttpStatus.BAD_REQUEST);
        return (List<Map<String,Object>>)list;
    }
    void revision(Assignment a,Map<String,Object> request) { if(!metadata.revision(a).equals(string(request,"expected_assignment_revision"))) throw failure(HttpStatus.CONFLICT); }
    void current(Assignment a,AssignmentSubmission s,Map<String,Object> row,boolean grade) {
        if(!a.getId().equals(s.getAssignment().getId())||!allowed(a,s)) throw failure(HttpStatus.FORBIDDEN);
        if (!Boolean.TRUE.equals(s.getSubmitted()) || !Boolean.TRUE.equals(s.getUserSubmission()) || !contentRevision(s).equals(string(row,"expected_content_revision"))) throw failure(HttpStatus.CONFLICT);
        if(grade&&!gradeRevision(s).equals(string(row,"expected_grade_revision"))) throw failure(HttpStatus.CONFLICT);
    }
    static void fields(Map<String,Object> value,String... allowed) {
        if(!value.keySet().equals(Set.of(allowed))) throw failure(HttpStatus.BAD_REQUEST);
    }
    public Map<String,Object> export(String site,String id,Map<String,Object> request) {
        fields(request,"export_request_id","expected_assignment_revision","submissions");
        Assignment a=assignment(site,id); identityRead(a); revision(a,request);
        String eid=McpGradingStore.uuid(string(request,"export_request_id")); var selected=rows(request,"submissions");
        for(var row:selected) fields(row,"submission_id","expected_content_revision");
        if(selected.stream().map(r -> string(r,"submission_id")).distinct().count()!=selected.size()) throw failure(HttpStatus.BAD_REQUEST);
        String requestHash=hash(new TreeMap<>(request)), key=store.key(actor(),site,id,eid,"export");
        return store.locked(key, directory -> {
            try {
                var old=store.read(directory);
                if(old!=null) {
                    if(!requestHash.equals(old.get("request_sha256"))) throw failure(HttpStatus.CONFLICT);
                    store.requireUnexpired(directory,old);
                    // An interrupted capture remains failed/partial; never silently restart with new source bytes.
                    return obj("export_id",eid,"request_sha256",requestHash,"status",old.get("status"),"expires_at",old.get("expires_at"),"warnings",old.get("warnings"));
                }
                List<Map<String,Object>> captured=new ArrayList<>(), artifacts=new ArrayList<>();
                Map<String,String> sources=new HashMap<>();
                Instant expires=Instant.now().plusSeconds(86400);
                var record=obj("export_id",eid,"request_sha256",requestHash,"status","failed","observed_at",stamp(Instant.now()),"expires_at",stamp(expires),
                    "completeness",obj("complete",false,"scope",siteGrader(a)?"site":"groups","reasons",List.of("capture_interrupted")),"rows",captured,"artifacts",artifacts,"archive",null,"next_cursor",null,"warnings",List.of("capture_interrupted"),"_sources",sources);
                store.write(directory,record);
                long total=0;
                for(var row:selected) {
                    String sid=string(row,"submission_id"), expected=string(row,"expected_content_revision");
                    AssignmentSubmission s=submission(a,sid); current(a,s,row,false);
                    List<String> ids=new ArrayList<>(), errors=new ArrayList<>();
                    List<Map<String,Object>> local=new ArrayList<>();
                    if(s.getSubmittedText()!=null) {
                        byte[] bytes=s.getSubmittedText().getBytes(StandardCharsets.UTF_8);
                        if(bytes.length>65535) errors.add("inline_over_budget");
                        else local.add(capture(directory,eid,site,id,sid,"inline.html","text/html",new ByteArrayInputStream(bytes),null,expires,EXPORT_LIMIT-total));
                    }
                    for(String reference:s.getAttachments().stream().sorted().toList()) {
                        try {
                            ContentResource r=resource(reference);
                            if(ResourceProperties.TYPE_URL.equals(r.getContentType())) { errors.add("url_attachment_unsupported"); continue; }
                            if("true".equals(r.getProperties().getProperty(AssignmentConstants.PROP_INLINE_SUBMISSION))) continue;
                            long remaining=EXPORT_LIMIT-total-local.stream().mapToLong(f -> ((Number)f.get("size_bytes")).longValue()).sum();
                            if(r.getContentLength()>Math.min(FILE_LIMIT,remaining)) { errors.add("file_over_budget"); continue; }
                            String before=r.getContentSha256();
                            if(before==null||!before.matches("[a-fA-F0-9]{64}")) { errors.add("resource_hash_unavailable"); continue; }
                            try(InputStream input=r.streamContent()) {
                                var artifact=capture(directory,eid,site,id,sid,Objects.toString(r.getProperties().getProperty(ResourceProperties.PROP_DISPLAY_NAME),"attachment"),r.getContentType(),input,before,expires,remaining);
                                if(!Objects.equals(before,resource(reference).getContentSha256())) { Files.deleteIfExists(directory.resolve((String)artifact.get("artifact_id"))); throw new IOException("source_changed"); }
                                local.add(artifact); sources.put((String)artifact.get("artifact_id"),reference);
                            }
                        } catch(Exception e) { errors.add("capture_failed"); }
                    }
                    if (!expected.equals(contentRevision(submission(a,sid)))) errors.add("source_changed");
                    for(var artifact:local) {
                        total+=((Number)artifact.get("size_bytes")).longValue();
                        if(total>EXPORT_LIMIT) { errors.add("export_over_budget"); break; }
                        artifacts.add(artifact); ids.add((String)artifact.get("artifact_id"));
                    }
                    captured.add(obj("submission_id",sid,"sakai_user_ids",submitters(s),"content_revision",expected,"captured_at",stamp(Instant.now()),
                        "status",errors.isEmpty()?"ready":"incomplete","artifact_ids",ids,"reasons",errors));
                    record.put("status","partial"); store.write(directory,record);
                    if(total>EXPORT_LIMIT) break;
                }
                boolean complete=captured.size()==selected.size()&&captured.stream().allMatch(r -> "ready".equals(r.get("status")));
                record.put("status",complete?"ready":"partial"); record.put("warnings",List.of()); record.put("completeness",obj("complete",complete,"scope",siteGrader(a)?"site":"groups","reasons",complete?List.of():List.of("incomplete_capture")));
                store.write(directory,record);
                return obj("export_id",eid,"request_sha256",requestHash,"status",record.get("status"),"expires_at",stamp(expires),"warnings",record.get("warnings"));
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
    }
    Map<String,Object> capture(Path directory,String eid,String site,String id,String sid,String name,String type,InputStream input,String expected,Instant expires,long remaining) throws IOException {
        String aid=UUID.randomUUID().toString(); Path file=directory.resolve(aid);
        MessageDigest sha;
        try { sha=MessageDigest.getInstance("SHA-256"); } catch(Exception e) { throw new IOException("hash_unavailable"); }
        long length=0;
        try(OutputStream output=Files.newOutputStream(file,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
            byte[] buffer=new byte[16384]; int count;
            while((count=input.read(buffer))!=-1) { length+=count; if(length>Math.min(FILE_LIMIT,remaining)) throw new IOException("file_over_budget"); output.write(buffer,0,count); sha.update(buffer,0,count); }
        } catch(Exception e) { Files.deleteIfExists(file); throw e; }
        Files.setPosixFilePermissions(file,java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
        try(var channel=java.nio.channels.FileChannel.open(file,StandardOpenOption.WRITE)) { channel.force(true); }
        String hash=HexFormat.of().formatHex(sha.digest());
        if(expected!=null&&!hash.equalsIgnoreCase(expected)) { Files.deleteIfExists(file); throw new IOException("source_changed"); }
        return obj("artifact_id",aid,"kind","inline.html".equals(name)?"inline_text":"attachment","submission_id",sid,"original_name",name,
            "relative_path","submissions/raw/"+sid+"/"+aid,"content_type",type==null?"application/octet-stream":type,"size_bytes",length,"sha256",hash,
            "download_path","/grading-artifacts/"+site+"/"+id+"/"+eid+"/"+aid,"expires_at",stamp(expires));
    }
    public Map<String,Object> exportStatus(String site,String id,String eid,String cursor,Integer limit) {
        Assignment a=assignment(site,id); identityRead(a);
        return store.locked(store.key(actor(),site,id,eid,"export"),directory -> {
            try {
                var record=store.read(directory); if(record==null) throw failure(HttpStatus.NOT_FOUND);
                store.requireUnexpired(directory,record);
                @SuppressWarnings("unchecked") var captured=(List<Map<String,Object>>)record.get("rows");
                for(var row:captured) submission(a,string(row,"submission_id"));
                int offset=cursor==null?0:Integer.parseInt(cursor), size=limit==null?50:limit;
                if(offset<0||size<1||size>100) throw failure(HttpStatus.BAD_REQUEST);
                @SuppressWarnings("unchecked") var artifacts=(List<Map<String,Object>>)record.get("artifacts");
                if(offset>artifacts.size()) throw failure(HttpStatus.BAD_REQUEST);
                var page=new LinkedHashMap<>(record); page.remove("_sources"); int end=Math.min(artifacts.size(),offset+size);
                page.put("artifacts",artifacts.subList(offset,end)); page.put("next_cursor",end<artifacts.size()?String.valueOf(end):null);
                return page;
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
            catch(NumberFormatException e) { throw failure(HttpStatus.BAD_REQUEST); }
        });
    }
    public record Download(Path path,long size,String sha256) {}
    public Download download(String site,String id,String eid,String aid) {
        Assignment a=assignment(site,id); identityRead(a); McpGradingStore.uuid(aid);
        return store.locked(store.key(actor(),site,id,eid,"export"),directory -> {
            try {
                var record=store.read(directory); if(record==null) throw failure(HttpStatus.NOT_FOUND);
                store.requireUnexpired(directory,record);
                @SuppressWarnings("unchecked") var artifacts=(List<Map<String,Object>>)record.get("artifacts");
                var descriptor=artifacts.stream().filter(r -> aid.equals(r.get("artifact_id"))).findFirst().orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
                var current=submission(a,(String)descriptor.get("submission_id"));
                @SuppressWarnings("unchecked") var sources=(Map<String,String>)record.get("_sources");
                if(sources!=null && sources.containsKey(aid)) {
                    String source=sources.get(aid);
                    if(!current.getAttachments().contains(source)) throw failure(HttpStatus.FORBIDDEN);
                    try { resource(source); } catch(Exception e) { throw failure(HttpStatus.FORBIDDEN); }
                }
                Path path=directory.resolve(aid); if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)) throw failure(HttpStatus.NOT_FOUND);
                return new Download(path,((Number)descriptor.get("size_bytes")).longValue(),(String)descriptor.get("sha256"));
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
    }
    void writable(Assignment a) {
        if(!unsupported(a).isEmpty()||!siteGrader(a)) throw failure(HttpStatus.NOT_IMPLEMENTED);
        var item=linked(a);
        if(item==null && a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT)!=null) throw failure(HttpStatus.CONFLICT);
        if(item!=null && (!Boolean.TRUE.equals(item.getExternallyMaintained())||!assignmentRef(a).equals(item.getExternalId())||
                BigDecimal.valueOf(item.getPoints()).compareTo(new BigDecimal(a.getMaxGradePoint()).divide(BigDecimal.valueOf(a.getScaleFactor())))!=0)) throw failure(HttpStatus.NOT_IMPLEMENTED);
    }
    void writeTarget(Assignment a,AssignmentSubmission s,Map<String,Object> row) {
        target(a,s,row);
        String uid=string(row,"sakai_user_id");
        try { if(!sites.getSiteVisit(a.getContext()).getUsers().contains(uid)||assignments.allowAddSubmissionUsers(assignmentRef(a)).stream().noneMatch(u -> uid.equals(u.getId()))) throw failure(HttpStatus.FORBIDDEN); }
        catch(Exception e) { throw failure(HttpStatus.FORBIDDEN); }
    }
    BigDecimal points(String value,Assignment a) {
        if(!value.matches("(0|[1-9][0-9]*)(\\.[0-9]+)?")||value.length()>32) throw failure(HttpStatus.BAD_REQUEST);
        try {
            BigDecimal score=new BigDecimal(value),scaled=score.multiply(BigDecimal.valueOf(a.getScaleFactor()));
            scaled.intValueExact(); if(scaled.compareTo(BigDecimal.valueOf(a.getMaxGradePoint()))>0) throw failure(HttpStatus.BAD_REQUEST);
            return score;
        } catch(ArithmeticException e) { throw failure(HttpStatus.BAD_REQUEST); }
    }
    void target(Assignment a,AssignmentSubmission s,Map<String,Object> row) {
        if(submitters(s).size()!=1||!submitters(s).get(0).equals(string(row,"sakai_user_id"))) throw failure(HttpStatus.CONFLICT);
        var item=linked(a);
        if(item!=null&&!authz.isUserAbleToGradeItemForStudent(a.getContext(),a.getContext(),item.getId(),string(row,"sakai_user_id"))) throw failure(HttpStatus.FORBIDDEN);
    }
    @SuppressWarnings("unchecked") String feedback(Map<String,Object> row,AssignmentSubmission s) {
        if(!(row.get("feedback") instanceof Map<?,?> patch)) throw failure(HttpStatus.BAD_REQUEST);
        if(!patch.keySet().equals(Set.of("action","text"))) throw failure(HttpStatus.BAD_REQUEST);
        String action=(String)patch.get("action"); Object value=patch.get("text");
        if("preserve".equals(action)&&value==null) return s.getFeedbackComment();
        if("clear".equals(action)&&value==null) return null;
        if("replace".equals(action)&&value instanceof String text) {
            String safe=formatted.escapeHtmlFormattedText(text);
            if(safe.getBytes(StandardCharsets.UTF_8).length>65535) throw failure(HttpStatus.BAD_REQUEST);
            return safe;
        }
        throw failure(HttpStatus.BAD_REQUEST);
    }
    Object canonical(Object value) {
        if(value instanceof Map<?,?> map) {
            Map<String,Object> sorted=new TreeMap<>(); map.forEach((k,v) -> sorted.put((String)k,canonical(v))); return sorted;
        }
        if(value instanceof List<?> list) return list.stream().map(this::canonical).toList();
        return value;
    }
    public Map<String,Object> write(String site,String id,String kind,Map<String,Object> request) {
        fields(request,"operation_id","mode","expected_assignment_revision","payload_sha256","grades");
        try { if(mapper.writeValueAsBytes(request).length>60_000) throw failure(HttpStatus.BAD_REQUEST); } catch(IOException e) { throw failure(HttpStatus.BAD_REQUEST); }
        Assignment a=assignment(site,id); writable(a);
        String oid=McpGradingStore.uuid(string(request,"operation_id")),mode=string(request,"mode");
        if(!Set.of("validate","commit").contains(mode)) throw failure(HttpStatus.BAD_REQUEST);
        var selected=new ArrayList<>(rows(request,"grades"));
        for(var row:selected) {
            if(kind.equals("save")) fields(row,"submission_id","sakai_user_id","expected_content_revision","expected_grade_revision","score","feedback");
            else fields(row,"submission_id","sakai_user_id","expected_content_revision","expected_grade_revision","expected_score","expected_feedback_sha256");
        }
        selected.sort(Comparator.comparing(r -> string(r,"submission_id")+"\n"+string(r,"sakai_user_id")));
        if(selected.stream().map(r -> string(r,"submission_id")).distinct().count()!=selected.size()) throw failure(HttpStatus.BAD_REQUEST);
        var payload=obj("kind",kind,"course_id",site,"assignment_id",id,"expected_assignment_revision",string(request,"expected_assignment_revision"),"grades",selected);
        String sha=hash(canonical(payload)); if(!sha.equals(string(request,"payload_sha256"))) throw failure(HttpStatus.BAD_REQUEST);
        if(mode.equals("commit")) {
            var old=store.locked(store.key(actor(),site,id,oid,"operation"),directory -> {
                try { return store.read(directory); } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
            });
            if(old!=null) {
                if(!sha.equals(old.get("payload_sha256"))) throw failure(HttpStatus.CONFLICT);
                for(var row:rows(old,"rows")) target(a,submission(a,string(row,"submission_id")),row);
                return old;
            }
        }
        revision(a,request);
        // Whole batch preflight before the first official change.
        for(var row:selected) {
            AssignmentSubmission s=submission(a,string(row,"submission_id")); current(a,s,row,true); writeTarget(a,s,row);
            if(kind.equals("save")) {
                points(string(row,"score"),a); feedback(row,s);
                if(Boolean.TRUE.equals(s.getGradeReleased())||Boolean.TRUE.equals(s.getReturned())) throw failure(HttpStatus.CONFLICT);
            } else {
                if(!Boolean.TRUE.equals(s.getGraded())||Boolean.TRUE.equals(s.getGradeReleased())||Boolean.TRUE.equals(s.getReturned())||
                    points(string(row,"expected_score"),a).compareTo(new BigDecimal(decimal(s.getGrade(),a.getScaleFactor())))!=0||
                    !Objects.equals(row.get("expected_feedback_sha256"),s.getFeedbackComment()==null?null:digest(s.getFeedbackComment()))) throw failure(HttpStatus.CONFLICT);
            }
        }
        var receipt=obj("operation_id",oid,"kind",kind,"mode",mode,"payload_sha256",sha,"outcome","validated","observed_at",stamp(Instant.now()),"rows",new ArrayList<Map<String,Object>>(),"warnings",List.of());
        @SuppressWarnings("unchecked") var results=(List<Map<String,Object>>)receipt.get("rows");
        for(var row:selected) results.add(rowReceipt(a,submission(a,string(row,"submission_id")),string(row,"sakai_user_id"),"validated",null));
        if(mode.equals("validate")) return receipt;
        return store.locked(store.key(actor(),site,id,oid,"operation"),directory -> {
            try {
                var old=store.read(directory);
                if(old!=null) { if(!sha.equals(old.get("payload_sha256"))) throw failure(HttpStatus.CONFLICT); return old; }
                receipt.put("outcome","unknown"); store.write(directory,receipt);
                for(int index=0;index<selected.size();index++) {
                    var row=selected.get(index); String sid=string(row,"submission_id"),uid=string(row,"sakai_user_id");
                    results.set(index,rowReceipt(a,submission(a,sid),uid,"unknown","commit_in_progress")); store.write(directory,receipt);
                    try {
                        var saved=assignments.withGradingSubmissionLock(sid,s -> {
                            Assignment fresh=assignment(site,id); revision(fresh,request); writable(fresh); current(fresh,s,row,true); writeTarget(fresh,s,row);
                            if(kind.equals("save")) { s.setGrade(points(string(row,"score"),fresh).multiply(BigDecimal.valueOf(fresh.getScaleFactor())).toBigIntegerExact().toString()); s.setFeedbackComment(feedback(row,s)); s.setGraded(true); s.setGradedBy(actor()); }
                            else { s.setGradeReleased(true); s.setReturned(true); s.setDateReturned(Instant.now()); }
                            try { assignments.updateSubmission(s); } catch(PermissionException e) { throw failure(HttpStatus.FORBIDDEN); }
                            return s;
                        });
                        results.set(index,rowReceipt(a,saved,uid,kind.equals("save")?"saved":"assignment_released",null)); store.write(directory,receipt);
                        if(kind.equals("release")) {
                            String releasedContent=contentRevision(saved),releasedGrade=gradeRevision(saved);
                            assignments.withGradingSubmissionLock(sid,locked -> {
                                Assignment fresh=assignment(site,id); revision(fresh,request); writable(fresh); writeTarget(fresh,locked,row);
                                if(!releasedContent.equals(contentRevision(locked))||!releasedGrade.equals(gradeRevision(locked))) throw failure(HttpStatus.CONFLICT);
                                var item=linked(fresh);
                                if(item!=null) {
                                    grading.updateExternalAssessmentScore(site,site,item.getExternalId(),uid,decimal(locked.getGrade(),fresh.getScaleFactor()));
                                    grading.updateExternalAssessmentComment(site,site,item.getExternalId(),uid,formatted.convertFormattedTextToPlaintext(locked.getFeedbackComment()));
                                }
                                return null;
                            });
                            results.set(index,rowReceipt(a,saved,uid,"gradebook_synced",null)); store.write(directory,receipt);
                        }
                    } catch(Exception e) {
                        // No blind retry after native events or database errors. Prior stage remains visible.
                        var previous=results.get(index); previous.put("reason","requires_reconciliation"); previous.put("retry_action","human_reconciliation");
                        receipt.put("warnings",List.of("manual_reconciliation_required")); store.write(directory,receipt);
                    }
                }
                receipt.put("outcome",results.stream().allMatch(r -> (kind.equals("save")?"saved":"gradebook_synced").equals(r.get("stage")))?"completed":"partial");
                store.write(directory,receipt); return receipt;
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
    }
    Map<String,Object> rowReceipt(Assignment a,AssignmentSubmission s,String uid,String stage,String reason) {
        return obj("submission_id",s.getId(),"sakai_user_id",uid,"stage",stage,"content_revision",contentRevision(s),"grade_revision",gradeRevision(s),
            "assignment_score",decimal(s.getGrade(),a.getScaleFactor()),"grade_released",s.getGradeReleased(),"returned",s.getReturned(),"gradebook_score",null,
            "reason",reason,"retry_action",stage.equals("unknown")?"human_reconciliation":"none");
    }
    public Map<String,Object> operation(String site,String id,String oid) {
        Assignment a=assignment(site,id); identityRead(a);
        return store.locked(store.key(actor(),site,id,oid,"operation"),directory -> {
            try { var record=store.read(directory); if(record==null) throw failure(HttpStatus.NOT_FOUND);
                for(var row:rows(record,"rows")) { var s=submission(a,string(row,"submission_id")); target(a,s,row); }
                return record;
            } catch(IOException e) { throw failure(HttpStatus.SERVICE_UNAVAILABLE); }
        });
    }
    public Map<String,Object> grades(String site,String id,Map<String,Object> request) {
        fields(request,"rows");
        Assignment a=assignment(site,id); identityRead(a); List<Map<String,Object>> result=new ArrayList<>();
        for(var row:rows(request,"rows")) {
            fields(row,"submission_id","sakai_user_id");
            AssignmentSubmission s=submission(a,string(row,"submission_id")); target(a,s,row); String uid=string(row,"sakai_user_id");
            String gbScore=null,comment=null,state="not_linked",reason=null;
            try { var item=linked(a); if(item!=null) {
                gbScore=grading.getAssignmentScoreString(site,site,item.getId(),uid);
                var definition=grading.getAssignmentScoreComment(site,item.getId(),uid); comment=definition==null?null:definition.getCommentText(); state="available";
            } else if(a.getProperties().get(AssignmentConstants.PROP_ASSIGNMENT_ASSOCIATE_GRADEBOOK_ASSIGNMENT)!=null) { state="unavailable";reason="missing_link"; }
            } catch(Exception e) { state="unavailable"; reason="projection_unavailable"; }
            result.add(obj("submission_id",s.getId(),"sakai_user_id",uid,"content_revision",contentRevision(s),"grade_revision",gradeRevision(s),"score",decimal(s.getGrade(),a.getScaleFactor()),
                "feedback_sha256",s.getFeedbackComment()==null?null:digest(s.getFeedbackComment()),"flags",flags(s),"returned_at",stamp(s.getDateReturned()),
                "gradebook_score",gbScore==null||gbScore.isBlank()?null:new BigDecimal(gbScore).stripTrailingZeros().toPlainString(),"gradebook_comment_sha256",comment==null?null:digest(comment),"gradebook_state",state,"reason",reason));
        }
        return obj("observed_at",stamp(Instant.now()),"assignment_revision",metadata.revision(a),"gradebook",link(a),"rows",result,"completeness",completeness(a),"warnings",List.of());
    }
}
