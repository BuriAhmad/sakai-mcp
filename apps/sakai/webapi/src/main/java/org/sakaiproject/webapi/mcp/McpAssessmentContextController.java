/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/mcp/v1/courses/{siteId}/assessment-context")
public class McpAssessmentContextController {
    private final McpAssessmentService service;
    public McpAssessmentContextController(McpAssessmentService service) { this.service = service; }
    @GetMapping
    public Map<String, Object> context(@PathVariable String siteId,
            @RequestParam(required = false) String window_start, @RequestParam(required = false) String window_end) {
        return service.context(siteId, window_start, window_end);
    }
}
