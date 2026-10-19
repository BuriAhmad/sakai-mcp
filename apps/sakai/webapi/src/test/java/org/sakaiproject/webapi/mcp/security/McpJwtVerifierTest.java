/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp.security;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.RemoteKeySourceException;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;

import org.junit.Before;
import org.junit.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.function.Consumer;

public class McpJwtVerifierTest {

    private static final String ISSUER = "https://login.example.test/tenant/";
    private static final String TENANT = "tenant";
    private static final String AUDIENCE = "api://sakai";
    private static final Instant NOW = Instant.now();

    private RSAKey signingKey;
    private McpJwtVerifier verifier;

    @Before
    public void setup() throws Exception {
        signingKey = new RSAKeyGenerator(2048).keyID("test-key").generate();
        DefaultJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
        processor.setJWSKeySelector(
                new JWSVerificationKeySelector<>(
                        JWSAlgorithm.RS256,
                        new ImmutableJWKSet<>(new JWKSet(signingKey.toPublicJWK()))));
        verifier =
                new McpJwtVerifier(
                        ISSUER,
                        TENANT,
                        AUDIENCE,
                        "sakai.mcp.access",
                        Clock.fixed(NOW, ZoneOffset.UTC),
                        processor);
    }

    private JWTClaimsSet.Builder validClaims() {
        return new JWTClaimsSet.Builder()
                .issuer(ISSUER)
                .audience(AUDIENCE)
                .claim("tid", TENANT)
                .claim("oid", "test-object")
                .claim("scp", "sakai.mcp.access")
                .claim("extn.SakaiEid", List.of("test-eid"))
                .notBeforeTime(Date.from(NOW.minusSeconds(10)))
                .expirationTime(Date.from(NOW.plusSeconds(300)));
    }

    private String sign(JWTClaimsSet claims) throws Exception {
        SignedJWT jwt =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS256).keyID("test-key").build(),
                        claims);
        jwt.sign(new RSASSASigner(signingKey));
        return jwt.serialize();
    }

    private void rejects(Consumer<JWTClaimsSet.Builder> change) throws Exception {
        JWTClaimsSet.Builder builder = validClaims();
        change.accept(builder);
        assertThrows(
                McpJwtVerifier.InvalidTokenException.class,
                () -> verifier.verify(sign(builder.build())));
    }

    @Test
    public void acceptsOnlyTheObservedSingletonExtensionShape() throws Exception {
        McpJwtVerifier.Identity identity = verifier.verify(sign(validClaims().build()));
        assertEquals("test-eid", identity.sakaiEid());
        assertEquals(TENANT, identity.tenantId());
        assertEquals("test-object", identity.objectId());
        rejects(b -> b.claim("extn.SakaiEid", null));
        rejects(b -> b.claim("extn.SakaiEid", "test-eid"));
        rejects(b -> b.claim("extn.SakaiEid", List.of("one", "two")));
        rejects(b -> b.claim("extn.SakaiEid", List.of(" ")));
    }

    @Test
    public void rejectsOtherResourceAndIdentityClaims() throws Exception {
        rejects(b -> b.audience("api://mcp"));
        rejects(b -> b.issuer("https://other.example.test/"));
        rejects(b -> b.claim("tid", "other-tenant"));
        rejects(b -> b.claim("scp", "mcp.access"));
        rejects(b -> b.claim("oid", null));
        rejects(b -> b.expirationTime(Date.from(NOW.minusSeconds(1))));
        rejects(b -> b.notBeforeTime(Date.from(NOW.plusSeconds(61))));
    }

    @Test
    public void rejectsInvalidSignature() throws Exception {
        RSAKey otherKey = new RSAKeyGenerator(2048).keyID("test-key").generate();
        SignedJWT jwt =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS256).keyID("test-key").build(),
                        validClaims().build());
        jwt.sign(new RSASSASigner(otherKey));
        assertThrows(
                McpJwtVerifier.InvalidTokenException.class, () -> verifier.verify(jwt.serialize()));
    }

    @Test
    @SuppressWarnings("unchecked")
    public void distinguishesKeyServiceFailureFromInvalidCredentials() throws Exception {
        ConfigurableJWTProcessor<SecurityContext> unavailable =
                mock(ConfigurableJWTProcessor.class);
        when(unavailable.process(
                        anyString(), org.mockito.ArgumentMatchers.<SecurityContext>isNull()))
                .thenThrow(new RemoteKeySourceException("test unavailable", null));
        McpJwtVerifier offline =
                new McpJwtVerifier(
                        ISSUER,
                        TENANT,
                        AUDIENCE,
                        "sakai.mcp.access",
                        Clock.fixed(NOW, ZoneOffset.UTC),
                        unavailable);
        assertThrows(
                McpJwtVerifier.VerificationUnavailableException.class,
                () -> offline.verify(sign(validClaims().build())));
    }
}
