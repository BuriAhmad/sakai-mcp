/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.id;
import static org.sakaiproject.webapi.mcp.contracts.McpContractSupport.obj;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.fields;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.hash;
import static org.sakaiproject.webapi.mcp.grading.McpGradingJson.string;

import org.sakaiproject.assignment.api.model.Assignment;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.Map;

/** Owner-bound immutable proposals reauthorized against their source exports. */
@Service
public class McpGradingProposalService {
    private final McpGradingStore store;
    private final McpGradingAuthorization authorization;
    private final McpGradingExportService exports;

    public McpGradingProposalService(
            McpGradingStore store,
            McpGradingAuthorization authorization,
            McpGradingExportService exports) {
        this.store = store;
        this.authorization = authorization;
        this.exports = exports;
    }

    public Map<String, Object> createProposal(String site, String id, Map<String, Object> request) {
        fields(request, "proposal_id", "export_id", "payload");
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        String pid = McpGradingStore.uuid(string(request, "proposal_id")),
                eid = McpGradingStore.uuid(string(request, "export_id"));
        var export = exports.exportStatus(site, id, eid, null, 1);
        if (!(request.get("payload") instanceof Map<?, ?> payload) || payload.isEmpty())
            throw failure(HttpStatus.BAD_REQUEST);
        String requestHash = hash(request),
                key = store.key(authorization.actor(), site, id, pid, "proposal");
        return store.locked(
                key,
                directory -> {
                    try {
                        var old = store.read(directory);
                        if (old != null) {
                            store.requireUnexpired(directory, old);
                            if (!requestHash.equals(old.get("request_sha256")))
                                throw failure(HttpStatus.CONFLICT);
                            return old;
                        }
                        var record =
                                obj(
                                        "proposal_id",
                                        pid,
                                        "export_id",
                                        eid,
                                        "request_sha256",
                                        requestHash,
                                        "expires_at",
                                        export.get("expires_at"),
                                        "payload",
                                        payload);
                        store.write(directory, record);
                        return record;
                    } catch (IOException e) {
                        throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                    }
                });
    }

    public Map<String, Object> proposal(String site, String id, String pid) {
        Assignment a = authorization.assignment(site, id);
        authorization.identityRead(a);
        var record =
                store.locked(
                        store.key(authorization.actor(), site, id, pid, "proposal"),
                        directory -> {
                            try {
                                var found = store.read(directory);
                                if (found == null) throw failure(HttpStatus.NOT_FOUND);
                                store.requireUnexpired(directory, found);
                                return found;
                            } catch (IOException e) {
                                throw failure(HttpStatus.SERVICE_UNAVAILABLE);
                            }
                        });
        exports.exportStatus(
                site,
                id,
                string(record, "export_id"),
                null,
                1); // Reauthorize every source submission and export lifetime.
        return record;
    }
}
