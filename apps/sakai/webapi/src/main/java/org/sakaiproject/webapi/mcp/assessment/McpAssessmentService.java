/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.assessment;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import org.sakaiproject.assignment.api.model.Assignment;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/** Transitional configuration revision required by retained grading context/mutation callers. */
@Service
public class McpAssessmentService {
  private final ObjectMapper mapper = new ObjectMapper();

  public String revision(Assignment a) {
    // Semantic configuration revision avoids cache/database precision differences in
    // modification timestamps.
    // Includes persisted content and all association properties, never submissions.
    Map<String, Object> value =
        obj(
            "id",
            a.getId(),
            "title",
            a.getTitle(),
            "instructions",
            a.getInstructions(),
            "draft",
            a.getDraft(),
            "deleted",
            a.getDeleted(),
            "visible",
            stamp(a.getVisibleDate()),
            "open",
            stamp(a.getOpenDate()),
            "due",
            stamp(a.getDueDate()),
            "close",
            stamp(a.getCloseDate()),
            "points",
            a.getMaxGradePoint(),
            "scale",
            a.getScaleFactor(),
            "grade",
            a.getTypeOfGrade(),
            "submission",
            a.getTypeOfSubmission(),
            "audience",
            a.getTypeOfAccess(),
            "group",
            a.getIsGroup(),
            "groups",
            a.getGroups().stream().sorted().toList(),
            "release",
            a.getReleaseGrades(),
            "peer_assessment",
            a.getAllowPeerAssessment(),
            "content_review",
            a.getContentReview(),
            "individual",
            a.getIndividuallyGraded(),
            "attachments",
            a.getAttachments().stream().sorted().toList(),
            "properties",
            new java.util.TreeMap<>(a.getProperties()));
    try {
      return digest(mapper.writeValueAsString(value));
    } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
      throw failure(HttpStatus.INTERNAL_SERVER_ERROR);
    }
  }
}
