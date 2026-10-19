/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.id;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.stamp;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.count;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.fields;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.hash;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.rows;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.string;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.content.api.ContentResource;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.grading.api.GradingService;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import java.util.UUID;

/** Immutable private export capture, inventory, expiry and artifact reads. */
@Service
public class McpGradingExportService {
    private final GradingService grading;
    private final McpGradingStore store;
    private final McpGradingAuthorization authorization;
    private final McpGradingEvidence evidence;
    static final long FILE_LIMIT = 10L * 1024 * 1024;
    static final long EXPORT_LIMIT = 100L * 1024 * 1024;

    public McpGradingExportService(
            @Qualifier("org.sakaiproject.grading.api.GradingService") GradingService grading,
            McpGradingStore store,
            McpGradingAuthorization authorization,
            McpGradingEvidence evidence) {
        this.grading = grading;
        this.store = store;
        this.authorization = authorization;
        this.evidence = evidence;
    }

    public Map<String, Object> export(String site, String id, Map<String, Object> request) {
        fields(request, "export_request_id", "expected_assignment_revision", "submissions");
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        evidence.revision(a, request);
        String eid = McpGradingStore.uuid(string(request, "export_request_id"));
        var selected = rows(request, "submissions");
        for (var row : selected) fields(row, "submission_id", "expected_content_revision");
        if (selected.stream().map(r -> string(r, "submission_id")).distinct().count()
                != selected.size()) throw failure(HttpStatus.BAD_REQUEST);
        String requestHash = hash(new TreeMap<>(request)),
                key = store.key(authorization.actor(), site, id, eid, "export");
        return store.locked(
                key,
                directory -> {
                    try {
                        var old = store.read(directory);
                        if (old != null) {
                            if (!requestHash.equals(old.get("request_sha256")))
                                throw failure(HttpStatus.CONFLICT);
                            store.requireUnexpired(directory, old);
                            // An interrupted capture remains failed/partial; never silently restart
                            // with new source bytes.
                            return obj(
                                    "export_id",
                                    eid,
                                    "request_sha256",
                                    requestHash,
                                    "status",
                                    old.get("status"),
                                    "expires_at",
                                    old.get("expires_at"),
                                    "warnings",
                                    old.get("warnings"));
                        }
                        List<Map<String, Object>> captured = new ArrayList<>(),
                                artifacts = new ArrayList<>();
                        Map<String, String> sources = new HashMap<>();
                        Instant expires = Instant.now().plusSeconds(86400);
                        var record =
                                obj(
                                        "export_id",
                                        eid,
                                        "request_sha256",
                                        requestHash,
                                        "status",
                                        "failed",
                                        "observed_at",
                                        stamp(Instant.now()),
                                        "expires_at",
                                        stamp(expires),
                                        "completeness",
                                        obj(
                                                "complete",
                                                false,
                                                "scope",
                                                authorization.siteGrader(a) ? "site" : "groups",
                                                "reasons",
                                                List.of("capture_interrupted")),
                                        "rows",
                                        captured,
                                        "artifacts",
                                        artifacts,
                                        "archive",
                                        null,
                                        "next_cursor",
                                        null,
                                        "warnings",
                                        List.of("capture_interrupted"),
                                        "_sources",
                                        sources);
                        store.write(directory, record);
                        long total = 0;
                        for (var row : selected) {
                            String sid = string(row, "submission_id"),
                                    expected = string(row, "expected_content_revision");
                            AssignmentSubmission s = authorization.submission(a, sid);
                            evidence.current(a, s, row, false);
                            List<String> ids = new ArrayList<>(), errors = new ArrayList<>();
                            List<Map<String, Object>> local = new ArrayList<>();
                            if (s.getSubmittedText() != null) {
                                byte[] bytes =
                                        s.getSubmittedText().getBytes(StandardCharsets.UTF_8);
                                if (bytes.length > 65535) errors.add("inline_over_budget");
                                else
                                    local.add(
                                            capture(
                                                    directory,
                                                    eid,
                                                    site,
                                                    id,
                                                    sid,
                                                    "inline.html",
                                                    "text/html",
                                                    new ByteArrayInputStream(bytes),
                                                    null,
                                                    expires,
                                                    EXPORT_LIMIT - total));
                            }
                            for (String reference : s.getAttachments().stream().sorted().toList()) {
                                try {
                                    ContentResource r = evidence.resource(reference);
                                    if (ResourceProperties.TYPE_URL.equals(r.getContentType())) {
                                        errors.add("url_attachment_unsupported");
                                        continue;
                                    }
                                    if ("true"
                                            .equals(
                                                    r.getProperties()
                                                            .getProperty(
                                                                    AssignmentConstants
                                                                            .PROP_INLINE_SUBMISSION)))
                                        continue;
                                    long remaining =
                                            EXPORT_LIMIT
                                                    - total
                                                    - local.stream()
                                                            .mapToLong(
                                                                    f ->
                                                                            ((Number)
                                                                                            f.get(
                                                                                                    "size_bytes"))
                                                                                    .longValue())
                                                            .sum();
                                    if (r.getContentLength() > Math.min(FILE_LIMIT, remaining)) {
                                        errors.add("file_over_budget");
                                        continue;
                                    }
                                    String before = r.getContentSha256();
                                    if (before == null || !before.matches("[a-fA-F0-9]{64}")) {
                                        errors.add("resource_hash_unavailable");
                                        continue;
                                    }
                                    try (InputStream input = r.streamContent()) {
                                        var artifact =
                                                capture(
                                                        directory,
                                                        eid,
                                                        site,
                                                        id,
                                                        sid,
                                                        Objects.toString(
                                                                r.getProperties()
                                                                        .getProperty(
                                                                                ResourceProperties
                                                                                        .PROP_DISPLAY_NAME),
                                                                "attachment"),
                                                        r.getContentType(),
                                                        input,
                                                        before,
                                                        expires,
                                                        remaining);
                                        if (!Objects.equals(
                                                before,
                                                evidence.resource(reference).getContentSha256())) {
                                            Files.deleteIfExists(
                                                    directory.resolve(
                                                            (String) artifact.get("artifact_id")));
                                            throw new IOException("source_changed");
                                        }
                                        local.add(artifact);
                                        sources.put(
                                                (String) artifact.get("artifact_id"), reference);
                                    }
                                } catch (Exception e) {
                                    errors.add("capture_failed");
                                }
                            }
                            if (!expected.equals(
                                    evidence.contentRevision(authorization.submission(a, sid))))
                                errors.add("source_changed");
                            for (var artifact : local) {
                                total += ((Number) artifact.get("size_bytes")).longValue();
                                if (total > EXPORT_LIMIT) {
                                    errors.add("export_over_budget");
                                    break;
                                }
                                artifacts.add(artifact);
                                ids.add((String) artifact.get("artifact_id"));
                            }
                            captured.add(
                                    obj(
                                            "submission_id",
                                            sid,
                                            "sakai_user_ids",
                                            evidence.submitters(s),
                                            "content_revision",
                                            expected,
                                            "captured_at",
                                            stamp(Instant.now()),
                                            "status",
                                            errors.isEmpty() ? "ready" : "incomplete",
                                            "artifact_ids",
                                            ids,
                                            "reasons",
                                            errors));
                            record.put("status", "partial");
                            store.write(directory, record);
                            if (total > EXPORT_LIMIT) break;
                        }
                        boolean complete =
                                captured.size() == selected.size()
                                        && captured.stream()
                                                .allMatch(r -> "ready".equals(r.get("status")));
                        record.put("status", complete ? "ready" : "partial");
                        record.put("warnings", List.of());
                        record.put(
                                "completeness",
                                obj(
                                        "complete",
                                        complete,
                                        "scope",
                                        authorization.siteGrader(a) ? "site" : "groups",
                                        "reasons",
                                        complete ? List.of() : List.of("incomplete_capture")));
                        store.write(directory, record);
                        return obj(
                                "export_id",
                                eid,
                                "request_sha256",
                                requestHash,
                                "status",
                                record.get("status"),
                                "expires_at",
                                stamp(expires),
                                "warnings",
                                record.get("warnings"));
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    }
                });
    }

    Map<String, Object> capture(
            Path directory,
            String eid,
            String site,
            String id,
            String sid,
            String name,
            String type,
            InputStream input,
            String expected,
            Instant expires,
            long remaining)
            throws IOException {
        String aid = UUID.randomUUID().toString();
        Path file = directory.resolve(aid);
        MessageDigest sha;
        try {
            sha = MessageDigest.getInstance("SHA-256");
        } catch (Exception e) {
            throw new IOException("hash_unavailable");
        }
        long length = 0;
        try (OutputStream output =
                Files.newOutputStream(
                        file, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            byte[] buffer = new byte[16384];
            int count;
            while ((count = input.read(buffer)) != -1) {
                length += count;
                if (length > Math.min(FILE_LIMIT, remaining))
                    throw new IOException("file_over_budget");
                output.write(buffer, 0, count);
                sha.update(buffer, 0, count);
            }
        } catch (Exception e) {
            Files.deleteIfExists(file);
            throw e;
        }
        Files.setPosixFilePermissions(
                file, java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
        try (var channel = java.nio.channels.FileChannel.open(file, StandardOpenOption.WRITE)) {
            channel.force(true);
        }
        String hash = HexFormat.of().formatHex(sha.digest());
        if (expected != null && !hash.equalsIgnoreCase(expected)) {
            Files.deleteIfExists(file);
            throw new IOException("source_changed");
        }
        return obj(
                "artifact_id",
                aid,
                "kind",
                "inline.html".equals(name) ? "inline_text" : "attachment",
                "submission_id",
                sid,
                "original_name",
                name,
                "relative_path",
                "submissions/raw/" + sid + "/" + aid,
                "content_type",
                type == null ? "application/octet-stream" : type,
                "size_bytes",
                length,
                "sha256",
                hash,
                "download_path",
                "/grading-artifacts/" + site + "/" + id + "/" + eid + "/" + aid,
                "expires_at",
                stamp(expires));
    }

    public Map<String, Object> exportStatus(
            String site, String id, String eid, String cursor, Integer limit) {
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        return store.locked(
                store.key(authorization.actor(), site, id, eid, "export"),
                directory -> {
                    try {
                        var record = store.read(directory);
                        if (record == null) throw failure(HttpStatus.NOT_FOUND);
                        store.requireUnexpired(directory, record);
                        @SuppressWarnings("unchecked")
                        var captured = (List<Map<String, Object>>) record.get("rows");
                        for (var row : captured)
                            authorization.submission(a, string(row, "submission_id"));
                        int offset = cursor == null ? 0 : Integer.parseInt(cursor),
                                size = limit == null ? 50 : limit;
                        if (offset < 0 || size < 1 || size > 100)
                            throw failure(HttpStatus.BAD_REQUEST);
                        @SuppressWarnings("unchecked")
                        var artifacts = (List<Map<String, Object>>) record.get("artifacts");
                        if (offset > artifacts.size()) throw failure(HttpStatus.BAD_REQUEST);
                        var page = new LinkedHashMap<>(record);
                        page.remove("_sources");
                        int end = Math.min(artifacts.size(), offset + size);
                        page.put("artifacts", artifacts.subList(offset, end));
                        page.put(
                                "next_cursor", end < artifacts.size() ? String.valueOf(end) : null);
                        return page;
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    } catch (NumberFormatException e) {
                        throw failure(HttpStatus.BAD_REQUEST);
                    }
                });
    }

    public record Download(Path path, long size, String sha256) {}

    public Download download(String site, String id, String eid, String aid) {
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        McpGradingStore.uuid(aid);
        return store.locked(
                store.key(authorization.actor(), site, id, eid, "export"),
                directory -> {
                    try {
                        var record = store.read(directory);
                        if (record == null) throw failure(HttpStatus.NOT_FOUND);
                        store.requireUnexpired(directory, record);
                        @SuppressWarnings("unchecked")
                        var artifacts = (List<Map<String, Object>>) record.get("artifacts");
                        var descriptor =
                                artifacts.stream()
                                        .filter(r -> aid.equals(r.get("artifact_id")))
                                        .findFirst()
                                        .orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
                        var current =
                                authorization.submission(
                                        a, (String) descriptor.get("submission_id"));
                        @SuppressWarnings("unchecked")
                        var sources = (Map<String, String>) record.get("_sources");
                        if (sources != null && sources.containsKey(aid)) {
                            String source = sources.get(aid);
                            if (!current.getAttachments().contains(source))
                                throw failure(HttpStatus.FORBIDDEN);
                            try {
                                evidence.resource(source);
                            } catch (Exception e) {
                                throw failure(HttpStatus.FORBIDDEN);
                            }
                        }
                        Path path = directory.resolve(aid);
                        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS))
                            throw failure(HttpStatus.NOT_FOUND);
                        return new Download(
                                path,
                                ((Number) descriptor.get("size_bytes")).longValue(),
                                (String) descriptor.get("sha256"));
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    }
                });
    }
}
