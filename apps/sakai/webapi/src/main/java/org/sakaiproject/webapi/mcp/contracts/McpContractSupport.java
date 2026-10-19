/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.contracts;

import org.sakaiproject.assignment.api.model.Assignment;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

/** Stable native MCP contract primitives shared by assessment and grading. */
public final class McpContractSupport {
    private McpContractSupport() {}

    public static String assignmentRef(Assignment a) {
        return org.sakaiproject.assignment.api.AssignmentReferenceReckoner.reckoner()
                .assignment(a)
                .reckon()
                .getReference();
    }

    public static ResponseStatusException failure(HttpStatus status) {
        return new ResponseStatusException(status);
    }

    public static String stamp(Instant t) {
        return t == null ? null : t.toString();
    }

    public static String id(Object id) {
        return id == null ? null : id.toString();
    }

    public static Map<String, Object> obj(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }

    public static String digest(String value) {
        try {
            return HexFormat.of()
                    .formatHex(
                            MessageDigest.getInstance("SHA-256")
                                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
