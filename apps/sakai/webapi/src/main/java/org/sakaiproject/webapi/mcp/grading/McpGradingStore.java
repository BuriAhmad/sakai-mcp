/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.sakaiproject.component.api.ServerConfigurationService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;

/** Private persistent Sakai storage. No paths or credentials come from callers. */
@Service
public class McpGradingStore {
    private final ServerConfigurationService config;
    private final ObjectMapper mapper = new ObjectMapper();

    public McpGradingStore(ServerConfigurationService config) {
        this.config = config;
    }

    public boolean configured() {
        try {
            root();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    Path root() throws IOException {
        String configured = config.getString("mcp.assignment.grading.storage", "");
        if (configured.isBlank())
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.NOT_IMPLEMENTED);
        Path root = Path.of(configured);
        if (!root.isAbsolute()
                || !Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS)
                || !root.equals(root.toRealPath())
                || Files.isSymbolicLink(root)) throw new IOException("storage_unavailable");
        // Provision owner-only storage explicitly. Never chmod an arbitrary existing tree.
        var permissions = Files.getPosixFilePermissions(root);
        if (permissions.stream()
                .anyMatch(p -> p.name().startsWith("GROUP") || p.name().startsWith("OTHERS")))
            throw new IOException("storage_permissions");
        return root;
    }

    static String uuid(String id) {
        try {
            if (!UUID.fromString(id).toString().equals(id)) throw new IllegalArgumentException();
            return id;
        } catch (RuntimeException e) {
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.BAD_REQUEST);
        }
    }

    String key(String actor, String site, String assignment, String id, String kind) {
        return org.sakaiproject.webapi.mcp.contracts.McpContractSupport.digest(
                actor + "\n" + site + "\n" + assignment + "\n" + uuid(id) + "\n" + kind);
    }

    Path directory(String key) throws IOException {
        if (!key.matches("[a-f0-9]{64}")) throw new IOException("invalid_key");
        Path path = root().resolve(key);
        if (!Files.exists(path, LinkOption.NOFOLLOW_LINKS))
            try {
                Files.createDirectory(
                        path,
                        PosixFilePermissions.asFileAttribute(
                                PosixFilePermissions.fromString("rwx------")));
            } catch (FileAlreadyExistsException race) {
                /* other request provisioned it */
            }
        if (!Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(path))
            throw new IOException("invalid_store");
        return path;
    }

    public <T> T locked(String key, Function<Path, T> action) {
        try {
            Path directory = directory(key), lock = directory.resolve("lock");
            try (FileChannel channel =
                    FileChannel.open(
                            lock,
                            StandardOpenOption.CREATE,
                            StandardOpenOption.WRITE,
                            LinkOption.NOFOLLOW_LINKS)) {
                // tryLock fails closed for concurrent processes/threads; never block request
                // indefinitely.
                try (var held = channel.tryLock()) {
                    if (held == null)
                        throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                                HttpStatus.CONFLICT);
                    return action.apply(directory);
                } catch (java.nio.channels.OverlappingFileLockException e) {
                    throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                            HttpStatus.CONFLICT);
                }
            }
        } catch (IOException e) {
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(
                    HttpStatus.SERVICE_UNAVAILABLE);
        }
    }

    Map<String, Object> read(Path directory) throws IOException {
        Path file = directory.resolve("record.json");
        if (!Files.exists(file, LinkOption.NOFOLLOW_LINKS)) return null;
        if (Files.isSymbolicLink(file) || Files.size(file) > 1_000_000)
            throw new IOException("invalid_record");
        return mapper.readValue(
                Files.readAllBytes(file), new TypeReference<Map<String, Object>>() {});
    }

    /**
     * Remove expired content under the existing export lock; retain receipt metadata for diagnosis.
     */
    void requireUnexpired(Path directory, Map<String, Object> record) throws IOException {
        if (!java.time.Instant.parse((String) record.get("expires_at"))
                .isAfter(java.time.Instant.now())) {
            try (var files = Files.list(directory)) {
                for (Path file : files.toList()) {
                    if (file.getFileName()
                                    .toString()
                                    .matches(
                                            "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
                            && Files.isRegularFile(file, LinkOption.NOFOLLOW_LINKS))
                        Files.delete(file);
                }
            }
            throw org.sakaiproject.webapi.mcp.contracts.McpContractSupport.failure(HttpStatus.GONE);
        }
    }

    void write(Path directory, Map<String, Object> value) throws IOException {
        byte[] bytes = mapper.writeValueAsBytes(value);
        if (bytes.length > 1_000_000) throw new IOException("record_over_budget");
        Path temporary =
                Files.createTempFile(
                        directory,
                        ".record-",
                        ".tmp",
                        PosixFilePermissions.asFileAttribute(
                                PosixFilePermissions.fromString("rw-------")));
        try {
            try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.WRITE)) {
                var buffer = java.nio.ByteBuffer.wrap(bytes);
                while (buffer.hasRemaining()) channel.write(buffer);
                channel.force(true);
            }
            Files.move(
                    temporary,
                    directory.resolve("record.json"),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) {
                channel.force(true);
            }
        } finally {
            Files.deleteIfExists(temporary);
        }
    }
}
