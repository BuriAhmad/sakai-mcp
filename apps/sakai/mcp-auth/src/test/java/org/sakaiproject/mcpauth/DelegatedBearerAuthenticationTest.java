/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.*;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.*;
import com.sun.net.httpserver.HttpServer;

import org.junit.Before;
import org.junit.Test;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.springframework.http.MediaType;
import org.springframework.mock.web.*;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.net.InetSocketAddress;
import java.time.*;
import java.util.*;
import java.util.function.Consumer;

/** Real Spring decoder, provider, bearer filter and stateless context; synthetic keys only. */
public class DelegatedBearerAuthenticationTest {
    private static final Instant NOW = Instant.ofEpochSecond(1_800_000_000);
    private static final String KEYS = "https://issuer.example.test/keys";
    private RSAKey key;
    private ServerConfigurationService config;
    private NimbusJwtDecoder decoder;
    private DelegatedBearerAuthentication spring;
    private MockRestServiceServer server;

    @Before
    public void setup() throws Exception {
        SecurityContextHolder.clearContext();
        key = new RSAKeyGenerator(2048).keyID("one").generate();
        config = mock(ServerConfigurationService.class);
        when(config.getString("mcp.integration.issuer")).thenReturn("https://issuer.example.test/");
        when(config.getString("mcp.integration.tenant")).thenReturn("tenant");
        when(config.getString("mcp.integration.audience")).thenReturn("api://sakai");
        when(config.getString("mcp.integration.scope")).thenReturn("sakai.mcp.access");
        when(config.getString("mcp.integration.jwksUri")).thenReturn(KEYS);
        when(config.getString("mcp.integration.identityClaim", "extn.SakaiEid"))
                .thenReturn("extn.SakaiEid");
        RestTemplate http = DelegatedBearerAuthentication.keyHttp();
        server = MockRestServiceServer.bindTo(http).build();
        server.expect(requestTo(KEYS))
                .andRespond(
                        withSuccess(
                                new JWKSet(key.toPublicJWK()).toString(),
                                MediaType.APPLICATION_JSON));
        decoder =
                DelegatedBearerAuthentication.decoder(
                        config, Clock.fixed(NOW, ZoneOffset.UTC), http);
        spring = new DelegatedBearerAuthentication(decoder, "extn.SakaiEid");
    }

    private JWTClaimsSet.Builder claims() {
        return new JWTClaimsSet.Builder()
                .issuer("https://issuer.example.test/")
                .audience("api://sakai")
                .claim("tid", "tenant")
                .claim("oid", "object-a")
                .claim("scp", "sakai.mcp.access")
                .claim("extn.SakaiEid", List.of("eid-a"))
                .expirationTime(Date.from(NOW.plusSeconds(300)))
                .notBeforeTime(Date.from(NOW.minusSeconds(10)));
    }

    private String sign(JWTClaimsSet claims, RSAKey signing) throws Exception {
        SignedJWT jwt =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS256).keyID("one").build(), claims);
        jwt.sign(new RSASSASigner(signing));
        return jwt.serialize();
    }

    private void rejects(Consumer<JWTClaimsSet.Builder> change) throws Exception {
        var c = claims();
        change.accept(c);
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/test");
        request.addHeader("Authorization", "Bearer " + sign(c.build(), key));
        MockHttpServletResponse response = new MockHttpServletResponse();
        spring.doFilter(request, response, (r, s) -> fail("invalid token reached Sakai bridge"));
        assertEquals(401, response.getStatus());
        assertEquals("Bearer", response.getHeader("WWW-Authenticate"));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        SecurityContextHolder.clearContext();
    }

    @Test
    public void realPipelineAuthenticatesThenClearsContextAndCachesKeys() throws Exception {
        for (int i = 0; i < 2; i++) {
            var request = new MockHttpServletRequest("GET", "/test");
            request.addHeader("Authorization", "bEaReR " + sign(claims().build(), key));
            var response = new MockHttpServletResponse();
            spring.doFilter(
                    request,
                    response,
                    (r, s) -> {
                        var auth =
                                (JwtAuthenticationToken)
                                        SecurityContextHolder.getContext().getAuthentication();
                        assertTrue(auth.isAuthenticated());
                        assertEquals(
                                List.of("eid-a"), auth.getToken().getClaims().get("extn.SakaiEid"));
                        assertTrue(auth.getAuthorities().isEmpty());
                        assertNull(request.getSession(false));
                    });
            assertEquals(200, response.getStatus());
            assertNull(SecurityContextHolder.getContext().getAuthentication());
        }
        server.verify();
    }

    @Test
    public void preservesSingletonIdentityAndCanonicalBounds() throws Exception {
        rejects(c -> c.claim("extn.SakaiEid", null));
        rejects(c -> c.claim("extn.SakaiEid", "eid-a"));
        rejects(c -> c.claim("extn.SakaiEid", List.of()));
        rejects(c -> c.claim("extn.SakaiEid", List.of("a", "b")));
        rejects(c -> c.claim("extn.SakaiEid", List.of(42)));
        rejects(c -> c.claim("extn.SakaiEid", List.of(" ")));
        rejects(c -> c.claim("extn.SakaiEid", List.of(" a")));
        rejects(c -> c.claim("extn.SakaiEid", List.of("a\nb")));
        rejects(c -> c.claim("extn.SakaiEid", List.of("a".repeat(129))));
        rejects(c -> c.claim("oid", "object\n"));
        rejects(c -> c.claim("oid", null));
        rejects(c -> c.claim("oid", "x".repeat(129)));
    }

    @Test
    public void rejectsWrongResourceIssuerTenantAndApplicationOnlyTokens() throws Exception {
        rejects(c -> c.audience("api://mcp"));
        rejects(c -> c.audience(List.of("api://sakai", "api://other")));
        rejects(c -> c.issuer("https://other.example.test/"));
        rejects(c -> c.claim("tid", "other"));
        rejects(c -> c.claim("scp", "mcp.access"));
        rejects(c -> c.claim("scp", List.of("sakai.mcp.access")));
        rejects(c -> c.claim("scp", null).claim("roles", List.of("sakai.mcp.access")));
    }

    @Test
    public void preservesAsymmetricRequiredTimestampPolicy() throws Exception {
        rejects(c -> c.expirationTime(null));
        rejects(c -> c.notBeforeTime(null));
        rejects(c -> c.expirationTime(Date.from(NOW)));
        rejects(c -> c.expirationTime(Date.from(NOW.minusSeconds(1))));
        rejects(c -> c.notBeforeTime(Date.from(NOW.plusSeconds(61))));
        assertNotNull(
                decoder.decode(
                        sign(claims().notBeforeTime(Date.from(NOW.plusSeconds(60))).build(), key)));
    }

    @Test
    public void rejectsSignatureUnsignedAndWrongAlgorithm() throws Exception {
        assertThrows(
                BadJwtException.class,
                () -> decoder.decode(sign(claims().build(), new RSAKeyGenerator(2048).generate())));
        assertThrows(
                BadJwtException.class,
                () -> decoder.decode(new PlainJWT(claims().build()).serialize()));
        SignedJWT other =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS512).keyID("one").build(),
                        claims().build());
        other.sign(new RSASSASigner(key));
        assertThrows(JwtException.class, () -> decoder.decode(other.serialize()));
    }

    @Test
    public void malformedHeaderAndTokenHaveSanitizedChallenge() throws Exception {
        for (String header : List.of("Bearer", "Bearer a b", "Bearer invalid")) {
            var request = new MockHttpServletRequest();
            request.addHeader("Authorization", header);
            var response = new MockHttpServletResponse();
            spring.doFilter(request, response, (r, s) -> fail());
            assertEquals(401, response.getStatus());
            assertEquals("Bearer", response.getHeader("WWW-Authenticate"));
            assertEquals("", response.getContentAsString());
        }
    }

    @Test
    public void keyServiceFailureIsUnavailableWithoutParserDetails() throws Exception {
        server.reset();
        server.expect(requestTo(KEYS)).andRespond(withServerError());
        var request = new MockHttpServletRequest();
        request.addHeader("Authorization", "Bearer " + sign(claims().build(), key));
        var response = new MockHttpServletResponse();
        spring.doFilter(request, response, (r, s) -> fail());
        assertEquals(503, response.getStatus());
        assertEquals("", response.getContentAsString());
        assertNull(SecurityContextHolder.getContext().getAuthentication());
    }

    @Test
    public void contextIsClearedWhenDownstreamThrowsAndParametersAreNotExamined() throws Exception {
        var request =
                new MockHttpServletRequest() {
                    @Override
                    public String[] getParameterValues(String name) {
                        throw new AssertionError("resolver parsed native form");
                    }
                };
        request.addHeader("Authorization", "Bearer " + sign(claims().build(), key));
        assertThrows(
                javax.servlet.ServletException.class,
                () ->
                        spring.doFilter(
                                request,
                                new MockHttpServletResponse(),
                                (r, s) -> {
                                    throw new javax.servlet.ServletException("synthetic");
                                }));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
    }

    @Test
    public void springRefreshesKeysForNewSigningKeyWithoutCustomKeyClient() throws Exception {
        RSAKey replacement = new RSAKeyGenerator(2048).keyID("two").generate();
        server.expect(requestTo(KEYS))
                .andRespond(
                        withSuccess(
                                new JWKSet(replacement.toPublicJWK()).toString(),
                                MediaType.APPLICATION_JSON));
        assertNotNull(decoder.decode(sign(claims().build(), key)));
        SignedJWT rotated =
                new SignedJWT(
                        new JWSHeader.Builder(JWSAlgorithm.RS256).keyID("two").build(),
                        claims().build());
        rotated.sign(new RSASSASigner(replacement));
        assertNotNull(decoder.decode(rotated.serialize()));
        server.verify();
    }

    @Test
    public void configuredIdentityNamePreservesTheSameArrayContract() throws Exception {
        when(config.getString("mcp.integration.identityClaim", "extn.SakaiEid"))
                .thenReturn("institutionalIdentity");
        DelegatedBearerAuthentication.configure(decoder, config, Clock.fixed(NOW, ZoneOffset.UTC));
        assertNotNull(
                decoder.decode(
                        sign(
                                claims().claim("extn.SakaiEid", null)
                                        .claim("institutionalIdentity", List.of("eid-a"))
                                        .build(),
                                key)));
        assertThrows(BadJwtException.class, () -> decoder.decode(sign(claims().build(), key)));
    }

    @Test
    public void trustedConfigurationRequiresHttpsAndNoRequestSelectedKeys() {
        when(config.getString("mcp.integration.jwksUri"))
                .thenReturn("http://untrusted.example.test/keys");
        assertThrows(
                IllegalArgumentException.class,
                () ->
                        DelegatedBearerAuthentication.decoder(
                                config, Clock.systemUTC(), new RestTemplate()));
    }

    @Test
    public void httpResponseLimitAppliesEvenToChunkedKeyDocuments() throws Exception {
        HttpServer local = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        local.createContext(
                "/keys",
                exchange -> {
                    exchange.sendResponseHeaders(200, 0);
                    try (var output = exchange.getResponseBody()) {
                        output.write(new byte[1_000_001]);
                    }
                });
        local.start();
        try {
            var error =
                    assertThrows(
                            org.springframework.web.client.RestClientException.class,
                            () ->
                                    DelegatedBearerAuthentication.keyHttp()
                                            .getForObject(
                                                    "http://127.0.0.1:"
                                                            + local.getAddress().getPort()
                                                            + "/keys",
                                                    String.class));
            assertEquals("Key response limit", error.getMostSpecificCause().getMessage());
        } finally {
            local.stop(0);
        }
    }
}
