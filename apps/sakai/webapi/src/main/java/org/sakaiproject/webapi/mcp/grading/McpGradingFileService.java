/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.digest;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.id;

import org.sakaiproject.assignment.api.AssignmentConstants;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.content.api.ContentResource;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.exception.IdUnusedException;
import org.sakaiproject.exception.PermissionException;
import org.sakaiproject.exception.ServerOverloadException;
import org.sakaiproject.exception.TypeException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Collection;
import java.util.HexFormat;
import java.util.Objects;

/** Authorized current file reads with revision and integrity checks. */
@Service
public class McpGradingFileService {
    private final SecurityService security;
    private final McpGradingAuthorization authorization;
    private final McpGradingEvidence evidence;
    static final long FILE_LIMIT = 10L * 1024 * 1024;

    public McpGradingFileService(
            SecurityService security,
            McpGradingAuthorization authorization,
            McpGradingEvidence evidence) {
        this.security = security;
        this.authorization = authorization;
        this.evidence = evidence;
    }

    public record FileContents(byte[] bytes, String contentType, String sha256) {}

    FileContents readAttachment(Collection<String> references, String key) {
        if (!key.matches("[a-f0-9]{64}")) throw failure(HttpStatus.BAD_REQUEST);
        String reference =
                references.stream()
                        .filter(r -> digest(r).equals(key))
                        .findFirst()
                        .orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
        try {
            ContentResource r = evidence.resource(reference);
            if (ResourceProperties.TYPE_URL.equals(r.getContentType())
                    || "true"
                            .equals(
                                    r.getProperties()
                                            .getProperty(
                                                    AssignmentConstants.PROP_INLINE_SUBMISSION)))
                throw failure(HttpStatus.NOT_IMPLEMENTED);
            String before = r.getContentSha256();
            if (before == null
                    || !before.matches("[a-fA-F0-9]{64}")
                    || r.getContentLength() > FILE_LIMIT) throw failure(HttpStatus.NOT_IMPLEMENTED);
            byte[] bytes;
            try (InputStream input = r.streamContent()) {
                bytes = input.readNBytes((int) FILE_LIMIT + 1);
            }
            String sha =
                    HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            if (bytes.length > FILE_LIMIT
                    || bytes.length != r.getContentLength()
                    || !sha.equalsIgnoreCase(before)
                    || !before.equalsIgnoreCase(evidence.resource(reference).getContentSha256()))
                throw failure(HttpStatus.CONFLICT);
            return new FileContents(
                    bytes,
                    r.getContentType() == null ? "application/octet-stream" : r.getContentType(),
                    sha);
        } catch (PermissionException e) {
            throw failure(HttpStatus.FORBIDDEN);
        } catch (IdUnusedException e) {
            throw failure(HttpStatus.NOT_FOUND);
        } catch (IOException
                | TypeException
                | ServerOverloadException
                | java.security.NoSuchAlgorithmException e) {
            throw failure(HttpStatus.SERVICE_UNAVAILABLE);
        }
    }

    public FileContents assignmentFile(String site, String id, String file, String revision) {
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        // Assignment attachment bytes have their own revision, independently of configuration.
        var descriptor =
                evidence.assignmentAttachments(a).stream()
                        .filter(r -> file.equals(r.get("artifact_key")))
                        .findFirst()
                        .orElseThrow(() -> failure(HttpStatus.NOT_FOUND));
        if (revision == null
                || !revision.equalsIgnoreCase(
                        Objects.toString(descriptor.get("resource_revision"), "")))
            throw failure(HttpStatus.CONFLICT);
        FileContents result = readAttachment(a.getAttachments(), file);
        if (!revision.equalsIgnoreCase(result.sha256())
                || authorization.assignment(site, id).getAttachments().stream()
                        .noneMatch(r -> digest(r).equals(file))) throw failure(HttpStatus.CONFLICT);
        return result;
    }
}
