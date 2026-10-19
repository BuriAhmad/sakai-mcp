/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import org.sakaiproject.component.api.ServerConfigurationService;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Set;

import javax.servlet.DispatcherType;
import javax.servlet.http.HttpServletRequest;

/** Credential reach only. Native handlers still enforce operation permissions. */
final class DelegatedRoutes {

    static boolean legacy(HttpServletRequest request) {
        return request.getRequestURI().startsWith("/api/mcp/v1/");
    }

    static boolean allows(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (!("/api".equals(request.getContextPath()) || "/direct".equals(request.getContextPath()))
                || !path.startsWith(request.getContextPath() + "/")
                || request.getDispatcherType() != DispatcherType.REQUEST
                || !"GET".equals(request.getMethod())
                || request.getContentLengthLong() > 0
                || request.getHeader("Transfer-Encoding") != null) return false;
        if ("/direct/site.json".equals(path)) {
            return "access".equals(request.getParameter("select"))
                    && request.getQueryString() != null
                    && request.getQueryString().length() <= 1024
                    && request.getParameterMap().entrySet().stream()
                            .allMatch(
                                    e ->
                                            Set.of("select", "_start", "_limit")
                                                            .contains(e.getKey())
                                                    && e.getValue().length == 1
                                                    && ("select".equals(e.getKey())
                                                            || e.getValue()[0].matches(
                                                                    "[0-9]{1,10}")));
        }
        if (path.startsWith("/direct/announcement/site/") && path.endsWith(".json")) {
            String id = path.substring("/direct/announcement/site/".length(), path.length() - 5);
            return canonicalId(id)
                    && (request.getQueryString() == null
                            || request.getQueryString().length() <= 1024)
                    && request.getParameterMap().entrySet().stream()
                            .allMatch(
                                    e ->
                                            Set.of("n", "d", "a").contains(e.getKey())
                                                    && e.getValue().length == 1
                                                    && e.getValue()[0].matches("[0-9]{1,10}"));
        }
        if (request.getQueryString() != null || !request.getParameterMap().isEmpty()) return false;
        // Canonical opaque site IDs. No encoded slash, matrix
        // parameters, alternate endpoint/action or caller-selected actor.
        return "/api/users/me/sites".equals(path)
                || "/direct/user/current.json".equals(path)
                || siteRead(path)
                || assignmentSiteRead(path)
                || assignmentItemRead(path)
                || ownGradeRead(path);
    }

    private static boolean assignmentItemRead(String path) {
        String prefix = "/direct/assignment/item/";
        return path.startsWith(prefix) && path.endsWith(".json")
                && canonicalId(path.substring(prefix.length(), path.length() - 5));
    }

    private static boolean ownGradeRead(String path) {
        String prefix = "/api/sites/";
        if (!path.startsWith(prefix)) return false;
        String suffix = path.endsWith("/grading/item-data") ? "/grading/item-data" : "/grades";
        return path.endsWith(suffix)
                && path.length() > prefix.length() + suffix.length()
                && canonicalId(path.substring(prefix.length(), path.length() - suffix.length()));
    }

    private static boolean assignmentSiteRead(String path) {
        String prefix = "/direct/assignment/site/";
        return path.startsWith(prefix) && path.endsWith(".json")
                && canonicalId(path.substring(prefix.length(), path.length() - 5));
    }

    private static boolean siteRead(String path) {
        if (!path.startsWith("/direct/site/")) return false;
        String suffix =
                path.endsWith("/userPerms.json")
                        ? "/userPerms.json"
                        : path.endsWith("/pages.json") ? "/pages.json" : ".json";
        if (!path.endsWith(suffix) || path.length() <= "/direct/site/".length() + suffix.length()) return false;
        String raw = path.substring("/direct/site/".length(), path.length() - suffix.length());
        return canonicalId(raw);
    }

    private static boolean canonicalId(String raw) {
        if (raw.length() > 2048) return false;
        try {
            String id = decode(raw);
            return !id.isEmpty()
                    && id.length() <= 255
                    && id.equals(id.strip())
                    && !Set.of(".", "..").contains(id)
                    && id.chars()
                            .noneMatch(
                                    c -> Character.isISOControl(c) || "/\\%?#;:".indexOf(c) >= 0);
        } catch (IllegalArgumentException | CharacterCodingException e) {
            return false;
        }
    }

    private static String decode(String raw) throws CharacterCodingException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        for (int i = 0; i < raw.length(); ) {
            if (raw.charAt(i) == '%') {
                if (i + 2 >= raw.length()) throw new IllegalArgumentException();
                int hi = Character.digit(raw.charAt(i + 1), 16),
                        lo = Character.digit(raw.charAt(i + 2), 16);
                if (hi < 0 || lo < 0) throw new IllegalArgumentException();
                bytes.write((hi << 4) | lo);
                i += 3;
            } else {
                int cp = raw.codePointAt(i);
                if (cp >= 0xD800 && cp <= 0xDFFF) throw new IllegalArgumentException();
                bytes.writeBytes(
                        new String(Character.toChars(cp)).getBytes(StandardCharsets.UTF_8));
                i += Character.charCount(cp);
            }
        }
        return StandardCharsets.UTF_8
                .newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes.toByteArray()))
                .toString();
    }

    static String placement(HttpServletRequest request, ServerConfigurationService configuration) {
        String path = request.getRequestURI();
        if (!"/portal".equals(request.getContextPath()) || !path.startsWith("/portal/tool/"))
            return null;
        String tail = path.substring("/portal/tool/".length());
        String id = tail.split("/", 2)[0];
        if (!id.matches("[A-Za-z0-9_-]{1,255}")
                || path.contains("..")
                || path.contains("%")
                || path.contains(";")
                || path.contains("\\")
                || path.contains("//")) return null;
        String[] configured = configuration.getStrings("mcp.integration.placements");
        return configured != null && Arrays.asList(configured).contains(id) ? id : null;
    }

    static boolean conversationAllows(
            HttpServletRequest request, ServerConfigurationService configuration) {
        if (request.getDispatcherType() != DispatcherType.REQUEST
                || request.getHeader("X-MCP-Flow") == null) return false;
        if (request.getHeader("X-MCP-Flow-End") != null)
            return "/direct/user/current.json".equals(request.getRequestURI()) && allows(request);
        if (allows(request)) return true;
        if (placement(request, configuration) == null
                || !Set.of("GET", "POST").contains(request.getMethod())) return false;
        if (request.getContentLengthLong() > 262144
                || request.getHeader("Transfer-Encoding") != null) return false;
        if ("POST".equals(request.getMethod())
                && (request.getContentType() == null
                        || !request.getContentType()
                                .toLowerCase(java.util.Locale.ROOT)
                                .startsWith("application/x-www-form-urlencoded"))) return false;
        // Only credential-shaped fields are inspected. Native forms/CSRF and
        // permission checks retain all business input interpretation.
        return request.getParameterMap().keySet().stream()
                .noneMatch(
                        k ->
                                Set.of(
                                                "sessionid",
                                                "sakai.session",
                                                "jsessionid",
                                                "oauth_token",
                                                "authorization")
                                        .contains(k.toLowerCase(java.util.Locale.ROOT)));
    }

    private DelegatedRoutes() {}
}
