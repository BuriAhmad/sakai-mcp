/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/mcp/v1/courses/{site}/assignments/{assignment}")
public class McpAssignmentGradingController {
    private final McpGradingQueryService queries;

    public McpAssignmentGradingController(McpGradingQueryService queries) {
        this.queries = queries;
    }

    @GetMapping("/grading-context")
    public Map<String, Object> context(@PathVariable String site, @PathVariable String assignment) {
        return queries.context(site, assignment);
    }

}
