/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class McpAssignmentWriteControllerTest {
    private final McpAssignmentSetupService service = mock(McpAssignmentSetupService.class);
    private final McpAssignmentWriteController controller = new McpAssignmentWriteController(service);
    private final ObjectMapper mapper = new ObjectMapper();
    private String publish(String gb) { return "{\"expected_assignment_revision\":\"revision-a\",\"gradebook\":" + gb + ",\"calendar_deadline\":\"none\"}"; }
    @Test public void missingExplicitPolicyAndUnknownAuthorityAreRejected() throws Exception {
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> controller.create("course-a", mapper.readTree("{\"title\":\"Assignment 3\"}"))).getStatus());
        String extra = publish("{\"mode\":\"none\"}");
        extra = extra.substring(0, extra.length() - 1) + ",\"user_id\":\"other-person\"}";
        final String forged = extra;
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class, () -> controller.publish("course-a", "assignment-a", mapper.readTree(forged))).getStatus());
        verifyNoInteractions(service);
    }
    @Test public void gradebookPolicyIsExplicitAndBooleansAreNotCoerced() throws Exception {
        assertThrows(ResponseStatusException.class, () -> controller.publish("course-a", "assignment-a", mapper.readTree(publish("{\"mode\":\"new_external\"}"))));
        assertThrows(ResponseStatusException.class, () -> controller.publish("course-a", "assignment-a", mapper.readTree(publish("{\"mode\":\"none\",\"category_id\":null}"))));
        assertThrows(ResponseStatusException.class, () -> controller.publish("course-a", "assignment-a", mapper.readTree(publish("{\"mode\":\"new_external\",\"category_id\":null,\"release_to_students\":\"true\",\"count_toward_course_grade\":true}"))));
        verifyNoInteractions(service);
    }
}
