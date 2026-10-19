/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.InputStream;
import java.nio.file.Files;
import java.util.Map;

@RestController
@RequestMapping("/mcp/v1/courses/{site}/assignments/{assignment}")
public class McpAssignmentGradingController {
    private final McpGradingQueryService queries;
    private final McpGradingFileService files;
    private final McpGradingExportService exports;
    private final McpGradingProposalService proposals;
    private final McpGradeMutationService mutations;

    public McpAssignmentGradingController(
            McpGradingQueryService queries,
            McpGradingFileService files,
            McpGradingExportService exports,
            McpGradingProposalService proposals,
            McpGradeMutationService mutations) {
        this.queries = queries;
        this.files = files;
        this.exports = exports;
        this.proposals = proposals;
        this.mutations = mutations;
    }

    @GetMapping("/grading-context")
    public Map<String, Object> context(@PathVariable String site, @PathVariable String assignment) {
        return queries.context(site, assignment);
    }

    @GetMapping("/grading-submissions")
    public Map<String, Object> list(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return queries.list(site, assignment, cursor, limit);
    }

    @GetMapping("/grading-submissions/{submission}")
    public Map<String, Object> detail(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String submission) {
        return queries.detail(site, assignment, submission);
    }

    @GetMapping("/grading-submissions/{submission}/files/{file}")
    public ResponseEntity<byte[]> submissionFile(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String submission,
            @PathVariable String file,
            @RequestParam String revision) {
        return fileResponse(files.submissionFile(site, assignment, submission, file, revision));
    }

    @GetMapping("/grading-files/{file}")
    public ResponseEntity<byte[]> assignmentFile(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String file,
            @RequestParam String revision) {
        return fileResponse(files.assignmentFile(site, assignment, file, revision));
    }

    private ResponseEntity<byte[]> fileResponse(McpGradingFileService.FileContents file) {
        return ResponseEntity.ok()
                .header("Cache-Control", "private, no-store")
                .header("Content-Type", file.contentType())
                .header("X-Content-SHA256", file.sha256())
                .contentLength(file.bytes().length)
                .body(file.bytes());
    }

    @PostMapping("/grading-proposals")
    public Map<String, Object> createProposal(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestBody Map<String, Object> body) {
        return proposals.createProposal(site, assignment, body);
    }

    @GetMapping("/grading-proposals/{proposal}")
    public Map<String, Object> proposal(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String proposal) {
        return proposals.proposal(site, assignment, proposal);
    }

    @PostMapping("/grading-exports")
    public Map<String, Object> export(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestBody Map<String, Object> body) {
        return exports.export(site, assignment, body);
    }

    @GetMapping("/grading-exports/{export}")
    public Map<String, Object> exportStatus(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String export,
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return exports.exportStatus(site, assignment, export, cursor, limit);
    }

    @GetMapping("/grading-exports/{export}/artifacts/{artifact}")
    public ResponseEntity<StreamingResponseBody> artifact(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String export,
            @PathVariable String artifact) {
        // Authorization completes in the delegated request thread before any asynchronous
        // streaming.
        var file = exports.download(site, assignment, export, artifact);
        return ResponseEntity.ok()
                .header("Cache-Control", "private, no-store")
                .header("Content-Type", "application/octet-stream")
                .header("ETag", "\"" + file.sha256() + "\"")
                .header("X-Content-SHA256", file.sha256())
                .contentLength(file.size())
                .body(
                        output -> {
                            try (InputStream input =
                                    Files.newInputStream(
                                            file.path(), java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
                                input.transferTo(output);
                            }
                        });
    }

    @PostMapping("/grading-save")
    public Map<String, Object> save(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestBody Map<String, Object> body) {
        return mutations.write(site, assignment, "save", body);
    }

    @PostMapping("/grading-release")
    public Map<String, Object> release(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestBody Map<String, Object> body) {
        return mutations.write(site, assignment, "release", body);
    }

    @PostMapping("/grading-grades/query")
    public Map<String, Object> grades(
            @PathVariable String site,
            @PathVariable String assignment,
            @RequestBody Map<String, Object> body) {
        return queries.grades(site, assignment, body);
    }

    @GetMapping("/grading-operations/{operation}")
    public Map<String, Object> operation(
            @PathVariable String site,
            @PathVariable String assignment,
            @PathVariable String operation) {
        return mutations.operation(site, assignment, operation);
    }
}
