/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.digest;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.http.HttpStatus;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/** Canonical JSON, decimal and bounded request helpers for native grading contracts. */
public class McpGradingJson {
    private static final ObjectMapper mapper = new ObjectMapper();

    private McpGradingJson() {}

    static String decimal(String scaled, int factor) {
        if (scaled == null || scaled.isBlank()) return null;
        try {
            return new BigDecimal(scaled)
                    .divide(BigDecimal.valueOf(factor))
                    .stripTrailingZeros()
                    .toPlainString();
        } catch (RuntimeException e) {
            throw failure(HttpStatus.NOT_IMPLEMENTED);
        }
    }

    static String hash(Object value) {
        try {
            return digest(mapper.writeValueAsString(value));
        } catch (IOException e) {
            throw failure(HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    static Integer count(String value) {
        try {
            return value == null ? null : Integer.valueOf(value);
        } catch (RuntimeException e) {
            return null;
        }
    }

    static String instant(String value) {
        try {
            return value == null ? null : Instant.ofEpochMilli(Long.parseLong(value)).toString();
        } catch (RuntimeException e) {
            return null;
        }
    }

    static String string(Map<String, Object> value, String key) {
        Object v = value.get(key);
        if (!(v instanceof String s) || s.isBlank() || s.length() > 2048)
            throw failure(HttpStatus.BAD_REQUEST);
        return s;
    }

    @SuppressWarnings("unchecked")
    static List<Map<String, Object>> rows(Map<String, Object> value, String key) {
        if (!(value.get(key) instanceof List<?> list)
                || list.isEmpty()
                || list.size() > 100
                || list.stream().anyMatch(v -> !(v instanceof Map)))
            throw failure(HttpStatus.BAD_REQUEST);
        return (List<Map<String, Object>>) list;
    }

    static void fields(Map<String, Object> value, String... allowed) {
        if (!value.keySet().equals(Set.of(allowed))) throw failure(HttpStatus.BAD_REQUEST);
    }

    static Object canonical(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> sorted = new TreeMap<>();
            map.forEach((k, v) -> sorted.put((String) k, canonical(v)));
            return sorted;
        }
        if (value instanceof List<?> list)
            return list.stream().map(McpGradingJson::canonical).toList();
        return value;
    }
}
