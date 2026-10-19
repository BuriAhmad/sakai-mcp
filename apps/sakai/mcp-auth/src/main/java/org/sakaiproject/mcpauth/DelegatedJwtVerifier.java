/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.mcpauth;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.RemoteKeySourceException;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jose.util.DefaultResourceRetriever;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;

import java.net.MalformedURLException;
import java.net.URL;
import java.time.Clock;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Objects;

/** Validates only delegated tokens issued for the Sakai integration API. */
public final class DelegatedJwtVerifier {

    private static final long CLOCK_SKEW_SECONDS = 60;
    private final ConfigurableJWTProcessor<SecurityContext> processor;
    private final String issuer;
    private final String tenant;
    private final String audience;
    private final String scope;
    private final Clock clock;

    public DelegatedJwtVerifier(
            String issuer, String tenant, String audience, String scope, String jwksUri)
            throws MalformedURLException {
        this(issuer, tenant, audience, scope, Clock.systemUTC(), processor(jwksUri));
    }

    DelegatedJwtVerifier(
            String issuer,
            String tenant,
            String audience,
            String scope,
            Clock clock,
            ConfigurableJWTProcessor<SecurityContext> processor) {
        this.issuer = requireSetting(issuer);
        this.tenant = requireSetting(tenant);
        this.audience = requireSetting(audience);
        this.scope = requireSetting(scope);
        this.clock = Objects.requireNonNull(clock);
        this.processor = Objects.requireNonNull(processor);
    }

    private static ConfigurableJWTProcessor<SecurityContext> processor(String jwksUri)
            throws MalformedURLException {
        // The URL comes only from trusted server configuration, never a request or token claim.
        URL url = new URL(requireSetting(jwksUri));
        if (!"https".equals(url.getProtocol())) {
            throw new IllegalArgumentException("JWKS URI must use HTTPS");
        }
        DefaultJWTProcessor<SecurityContext> result = new DefaultJWTProcessor<>();
        result.setJWSKeySelector(
                new JWSVerificationKeySelector<>(
                        JWSAlgorithm.RS256,
                        new RemoteJWKSet<>(
                                url, new DefaultResourceRetriever(2_000, 2_000, 1_000_000))));
        return result;
    }

    private static String requireSetting(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing MCP token verifier setting");
        }
        return value;
    }

    /** No value from this record is derived from request headers or a caller-selected user. */
    public record Identity(String sakaiEid, String tenantId, String objectId) {}

    public Identity verify(String compactJwt)
            throws InvalidTokenException, VerificationUnavailableException {
        if (compactJwt == null || compactJwt.isBlank() || compactJwt.length() > 16_384) {
            throw new InvalidTokenException();
        }
        try {
            JWTClaimsSet claims = processor.process(compactJwt, null);
            Instant now = clock.instant();
            Date expiry = claims.getExpirationTime();
            Date notBefore = claims.getNotBeforeTime();
            if (!issuer.equals(claims.getIssuer())
                    || !tenant.equals(claims.getStringClaim("tid"))
                    || claims.getAudience().size() != 1
                    || !audience.equals(claims.getAudience().get(0))
                    || expiry == null
                    || !expiry.toInstant().isAfter(now)
                    || notBefore == null
                    || notBefore.toInstant().isAfter(now.plusSeconds(CLOCK_SKEW_SECONDS))) {
                throw new InvalidTokenException();
            }
            String delegatedScopes = claims.getStringClaim("scp");
            if (delegatedScopes == null || !List.of(delegatedScopes.split(" ")).contains(scope)) {
                throw new InvalidTokenException();
            }
            String objectId = claims.getStringClaim("oid");
            if (objectId == null
                    || objectId.isBlank()
                    || objectId.length() > 128
                    || !objectId.equals(objectId.trim())
                    || objectId.chars().anyMatch(Character::isISOControl)) {
                throw new InvalidTokenException();
            }
            // The issued token in this tenant emits a Graph String extension as an array.
            Object extension = claims.getClaim("extn.SakaiEid");
            if (!(extension instanceof List<?> values)
                    || values.size() != 1
                    || !(values.get(0) instanceof String eid)
                    || eid.isBlank()
                    || !eid.equals(eid.trim())
                    || eid.length() > 128
                    || eid.chars().anyMatch(Character::isISOControl)) {
                throw new InvalidTokenException();
            }
            return new Identity(eid, tenant, objectId);
        } catch (InvalidTokenException e) {
            throw e;
        } catch (RemoteKeySourceException e) {
            throw new VerificationUnavailableException();
        } catch (Exception e) {
            // Never expose token content, parsing details, or upstream key service errors.
            throw new InvalidTokenException();
        }
    }

    public static final class InvalidTokenException extends Exception {
        private static final long serialVersionUID = 1L;
    }

    public static final class VerificationUnavailableException extends Exception {
        private static final long serialVersionUID = 1L;
    }
}
