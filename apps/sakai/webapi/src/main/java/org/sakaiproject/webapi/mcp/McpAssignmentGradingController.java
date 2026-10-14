/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp;

import java.util.Map;
import java.nio.file.Files;
import java.io.InputStream;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
@RequestMapping("/mcp/v1/courses/{site}/assignments/{assignment}")
public class McpAssignmentGradingController {
    private final McpAssignmentGradingService service;
    public McpAssignmentGradingController(McpAssignmentGradingService service) { this.service=service; }
    @GetMapping("/grading-context")
    public Map<String,Object> context(@PathVariable String site,@PathVariable String assignment) { return service.context(site,assignment); }
    @GetMapping("/grading-submissions")
    public Map<String,Object> list(@PathVariable String site,@PathVariable String assignment,@RequestParam(required=false) String cursor,@RequestParam(required=false) Integer limit) { return service.list(site,assignment,cursor,limit); }
    @GetMapping("/grading-submissions/{submission}")
    public Map<String,Object> detail(@PathVariable String site,@PathVariable String assignment,@PathVariable String submission) { return service.detail(site,assignment,submission); }
    @GetMapping("/grading-submissions/{submission}/files/{file}")
    public ResponseEntity<byte[]> submissionFile(@PathVariable String site,@PathVariable String assignment,@PathVariable String submission,@PathVariable String file,@RequestParam String revision) {
        return fileResponse(service.submissionFile(site,assignment,submission,file,revision));
    }
    @GetMapping("/grading-files/{file}")
    public ResponseEntity<byte[]> assignmentFile(@PathVariable String site,@PathVariable String assignment,@PathVariable String file,@RequestParam String revision) {
        return fileResponse(service.assignmentFile(site,assignment,file,revision));
    }
    private ResponseEntity<byte[]> fileResponse(McpAssignmentGradingService.FileContents file) {
        return ResponseEntity.ok().header("Cache-Control","private, no-store").header("Content-Type",file.contentType())
            .header("X-Content-SHA256",file.sha256()).contentLength(file.bytes().length).body(file.bytes());
    }
    @PostMapping("/grading-proposals")
    public Map<String,Object> createProposal(@PathVariable String site,@PathVariable String assignment,@RequestBody Map<String,Object> body) { return service.createProposal(site,assignment,body); }
    @GetMapping("/grading-proposals/{proposal}")
    public Map<String,Object> proposal(@PathVariable String site,@PathVariable String assignment,@PathVariable String proposal) { return service.proposal(site,assignment,proposal); }
    @PostMapping("/grading-exports")
    public Map<String,Object> export(@PathVariable String site,@PathVariable String assignment,@RequestBody Map<String,Object> body) { return service.export(site,assignment,body); }
    @GetMapping("/grading-exports/{export}")
    public Map<String,Object> exportStatus(@PathVariable String site,@PathVariable String assignment,@PathVariable String export,@RequestParam(required=false) String cursor,@RequestParam(required=false) Integer limit) { return service.exportStatus(site,assignment,export,cursor,limit); }
    @GetMapping("/grading-exports/{export}/artifacts/{artifact}")
    public ResponseEntity<StreamingResponseBody> artifact(@PathVariable String site,@PathVariable String assignment,@PathVariable String export,@PathVariable String artifact) {
        // Authorization completes in the delegated request thread before any asynchronous streaming.
        var file=service.download(site,assignment,export,artifact);
        return ResponseEntity.ok().header("Cache-Control","private, no-store").header("Content-Type","application/octet-stream")
            .header("ETag","\""+file.sha256()+"\"").header("X-Content-SHA256",file.sha256()).contentLength(file.size())
            .body(output -> { try(InputStream input=Files.newInputStream(file.path(),java.nio.file.LinkOption.NOFOLLOW_LINKS)) { input.transferTo(output); } });
    }
    @PostMapping("/grading-save")
    public Map<String,Object> save(@PathVariable String site,@PathVariable String assignment,@RequestBody Map<String,Object> body) { return service.write(site,assignment,"save",body); }
    @PostMapping("/grading-release")
    public Map<String,Object> release(@PathVariable String site,@PathVariable String assignment,@RequestBody Map<String,Object> body) { return service.write(site,assignment,"release",body); }
    @PostMapping("/grading-grades/query")
    public Map<String,Object> grades(@PathVariable String site,@PathVariable String assignment,@RequestBody Map<String,Object> body) { return service.grades(site,assignment,body); }
    @GetMapping("/grading-operations/{operation}")
    public Map<String,Object> operation(@PathVariable String site,@PathVariable String assignment,@PathVariable String operation) { return service.operation(site,assignment,operation); }
}
