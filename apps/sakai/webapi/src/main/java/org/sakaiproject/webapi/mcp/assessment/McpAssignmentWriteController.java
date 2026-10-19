/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.assessment;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/mcp/v1/courses/{siteId}/assignments")
public class McpAssignmentWriteController {
    private final McpAssignmentSetupService service;
    private final JsonMapper mapper =
            JsonMapper.builder()
                    .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                    .disable(DeserializationFeature.ACCEPT_FLOAT_AS_INT)
                    .disable(MapperFeature.ALLOW_COERCION_OF_SCALARS)
                    .build();

    public McpAssignmentWriteController(McpAssignmentSetupService service) {
        this.service = service;
    }

    private <T> T request(JsonNode body, Class<T> type) {
        try {
            return mapper.treeToValue(body, type);
        } catch (Exception e) {
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.BAD_REQUEST);
        }
    }

    private void fields(JsonNode body, String... names) {
        if (body == null || !body.isObject())
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.BAD_REQUEST);
        for (String name : names)
            if (!body.has(name))
                throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                        HttpStatus.BAD_REQUEST);
    }

    private void gradebook(JsonNode body) {
        fields(body, "mode");
        if ("none".equals(body.path("mode").asText())) {
            if (body.size() != 1)
                throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                        HttpStatus.BAD_REQUEST);
        } else if ("new_external".equals(body.path("mode").asText())) {
            fields(body, "category_id", "release_to_students", "count_toward_course_grade");
            if (body.size() != 4)
                throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                        HttpStatus.BAD_REQUEST);
        } else
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.BAD_REQUEST);
    }

    @PostMapping
    public Map<String, Object> create(@PathVariable String siteId, @RequestBody JsonNode body) {
        fields(
                body,
                "title",
                "instructions",
                "timezone",
                "visible_at",
                "open_at",
                "due_at",
                "close_at",
                "max_points",
                "submission_type",
                "resubmission",
                "publication",
                "attachment_resource_refs",
                "gradebook",
                "calendar_deadline");
        fields(body.get("resubmission"), "count", "until");
        gradebook(body.get("gradebook"));
        return service.create(siteId, request(body, McpAssignmentSetupService.Create.class));
    }

    @PostMapping("/{assignmentId}/publish")
    public Map<String, Object> publish(
            @PathVariable String siteId,
            @PathVariable String assignmentId,
            @RequestBody JsonNode body) {
        fields(body, "expected_assignment_revision", "gradebook", "calendar_deadline");
        gradebook(body.get("gradebook"));
        return service.publish(
                siteId, assignmentId, request(body, McpAssignmentSetupService.Publish.class));
    }
}
