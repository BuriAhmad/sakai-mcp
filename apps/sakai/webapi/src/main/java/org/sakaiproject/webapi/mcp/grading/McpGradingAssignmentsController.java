/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/mcp/v1/courses/{site}/grading-assignments")
public class McpGradingAssignmentsController {
    private final McpGradingQueryService service;

    public McpGradingAssignmentsController(McpGradingQueryService service) {
        this.service = service;
    }

    @GetMapping
    public Map<String, Object> list(
            @PathVariable String site,
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return service.listAssignments(site, cursor, limit);
    }
}
