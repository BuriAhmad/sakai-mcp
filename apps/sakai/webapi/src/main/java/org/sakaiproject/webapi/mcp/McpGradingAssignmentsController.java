/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/mcp/v1/courses/{site}/grading-assignments")
public class McpGradingAssignmentsController {
    private final McpAssignmentGradingService service;
    public McpGradingAssignmentsController(McpAssignmentGradingService service) { this.service=service; }
    @GetMapping
    public Map<String,Object> list(@PathVariable String site,@RequestParam(required=false) String cursor,@RequestParam(required=false) Integer limit) {
        return service.listAssignments(site,cursor,limit);
    }
}
