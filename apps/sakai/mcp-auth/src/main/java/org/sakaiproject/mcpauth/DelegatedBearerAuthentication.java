/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import org.sakaiproject.component.api.ServerConfigurationService;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.security.authentication.AuthenticationServiceException;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtIssuerValidator;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationProvider;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationEntryPoint;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationFilter;
import org.springframework.security.oauth2.server.resource.web.DefaultBearerTokenResolver;
import org.springframework.security.web.context.NullSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextHolderFilter;
import org.springframework.web.client.RestOperations;
import org.springframework.web.client.RestTemplate;

import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.List;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletRequestWrapper;
import javax.servlet.http.HttpServletResponse;

/** Configures the standard Spring Resource Server pipeline; owns no JWT processor or key client. */
final class DelegatedBearerAuthentication {
    private final SecurityContextHolderFilter context;
    private final BearerTokenAuthenticationFilter bearer;
    final String identityClaim;

    DelegatedBearerAuthentication(ServerConfigurationService configuration) {
        this(decoder(configuration, Clock.systemUTC(), keyHttp()), identityClaim(configuration));
    }

    DelegatedBearerAuthentication(JwtDecoder decoder, String identityClaim) {
        this.identityClaim = identityClaim;
        JwtAuthenticationProvider provider = new JwtAuthenticationProvider(decoder);
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        // OAuth scopes admit a credential; only native Sakai services grant permissions.
        converter.setJwtGrantedAuthoritiesConverter(jwt -> Collections.emptyList());
        provider.setJwtAuthenticationConverter(converter);
        bearer = new BearerTokenAuthenticationFilter(new ProviderManager(List.of(provider)));
        var repository = new NullSecurityContextRepository();
        context = new SecurityContextHolderFilter(repository);
        bearer.setSecurityContextRepository(repository);
        DefaultBearerTokenResolver resolver = new DefaultBearerTokenResolver();
        bearer.setBearerTokenResolver(
                request ->
                        resolver.resolve(
                                new HttpServletRequestWrapper(request) {
                                    @Override
                                    public String[] getParameterValues(String name) {
                                        // 5.7 examines access_token even with parameter transport
                                        // disabled.
                                        // Do not parse native forms here or admit a second
                                        // credential transport.
                                        return "access_token".equals(name)
                                                ? null
                                                : super.getParameterValues(name);
                                    }
                                }));
        bearer.setAuthenticationEntryPoint(
                (request, response, failure) -> unauthorized(request, response));
        bearer.setAuthenticationFailureHandler(
                (request, response, failure) -> {
                    if (failure instanceof AuthenticationServiceException) {
                        response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
                    } else {
                        unauthorized(request, response);
                    }
                });
    }

    void doFilter(HttpServletRequest request, HttpServletResponse response, FilterChain downstream)
            throws IOException, ServletException {
        context.doFilter(request, response, (r, s) -> bearer.doFilter(r, s, downstream));
    }

    static void unauthorized(HttpServletRequest request, HttpServletResponse response)
            throws IOException, ServletException {
        // Standard challenge, without exposing parser, claim or upstream error details.
        new BearerTokenAuthenticationEntryPoint()
                .commence(
                        request,
                        response,
                        new org.springframework.security.authentication.BadCredentialsException(
                                "Invalid bearer credential"));
    }

    static String identityClaim(ServerConfigurationService configuration) {
        String claim = configuration.getString("mcp.integration.identityClaim", "extn.SakaiEid");
        if (claim == null || claim.isBlank() || !claim.equals(claim.trim())) {
            throw new IllegalArgumentException("Invalid delegated identity claim configuration");
        }
        return claim;
    }

    static NimbusJwtDecoder decoder(
            ServerConfigurationService configuration, Clock clock, RestOperations http) {
        NimbusJwtDecoder decoder =
                NimbusJwtDecoder.withJwkSetUri(https(setting(configuration, "jwksUri")))
                        .jwsAlgorithm(SignatureAlgorithm.RS256)
                        .restOperations(http)
                        .build();
        configure(decoder, configuration, clock);
        return decoder;
    }

    static void configure(
            NimbusJwtDecoder decoder, ServerConfigurationService configuration, Clock clock) {
        String issuer = https(setting(configuration, "issuer"));
        String tenant = setting(configuration, "tenant");
        String audience = setting(configuration, "audience");
        String scope = setting(configuration, "scope");
        String claim = identityClaim(configuration);
        JwtTimestampValidator time = new JwtTimestampValidator(Duration.ofSeconds(60));
        time.setClock(clock);
        decoder.setJwtValidator(
                new DelegatingOAuth2TokenValidator<Jwt>(
                        time,
                        new JwtIssuerValidator(issuer),
                        new JwtClaimValidator<Object>("tid", tenant::equals),
                        new JwtClaimValidator<Object>(
                                "aud",
                                value ->
                                        value instanceof List<?> values
                                                && values.size() == 1
                                                && audience.equals(values.get(0))),
                        new JwtClaimValidator<Object>(
                                "scp",
                                value ->
                                        value instanceof String scopes
                                                && List.of(scopes.split(" ")).contains(scope)),
                        new JwtClaimValidator<Object>(
                                "oid", DelegatedBearerAuthentication::identifier),
                        new JwtClaimValidator<Object>(
                                claim,
                                value ->
                                        value instanceof List<?> values
                                                && values.size() == 1
                                                && identifier(values.get(0))),
                        new JwtClaimValidator<Instant>(
                                "exp", value -> value != null && value.isAfter(clock.instant())),
                        new JwtClaimValidator<Instant>("nbf", value -> value != null)));
    }

    private static boolean identifier(Object value) {
        return value instanceof String text
                && !text.isBlank()
                && text.length() <= 128
                && text.equals(text.trim())
                && text.chars().noneMatch(Character::isISOControl);
    }

    private static String setting(ServerConfigurationService configuration, String name) {
        String value = configuration.getString("mcp.integration." + name);
        if (value == null || value.isBlank() || !value.equals(value.trim())) {
            throw new IllegalArgumentException("Missing delegated authentication configuration");
        }
        return value;
    }

    private static String https(String value) {
        URI uri = URI.create(value);
        if (!"https".equals(uri.getScheme())
                || uri.getHost() == null
                || uri.getUserInfo() != null
                || uri.getFragment() != null) {
            throw new IllegalArgumentException(
                    "Delegated authentication requires a trusted HTTPS URI");
        }
        return value;
    }

    static RestTemplate keyHttp() {
        SimpleClientHttpRequestFactory requests = new SimpleClientHttpRequestFactory();
        requests.setConnectTimeout(2_000);
        requests.setReadTimeout(2_000);
        RestTemplate http = new RestTemplate(requests);
        http.setInterceptors(
                List.of(
                        (request, body, execution) -> {
                            ClientHttpResponse response = execution.execute(request, body);
                            return new ClientHttpResponse() {
                                private InputStream stream;

                                public HttpStatus getStatusCode() throws IOException {
                                    return response.getStatusCode();
                                }

                                public int getRawStatusCode() throws IOException {
                                    return response.getRawStatusCode();
                                }

                                public String getStatusText() throws IOException {
                                    return response.getStatusText();
                                }

                                public HttpHeaders getHeaders() {
                                    return response.getHeaders();
                                }

                                public void close() {
                                    response.close();
                                }

                                public InputStream getBody() throws IOException {
                                    if (stream == null)
                                        stream =
                                                new FilterInputStream(response.getBody()) {
                                                    private int remaining = 1_000_000;

                                                    public int read() throws IOException {
                                                        int value = in.read();
                                                        if (value != -1 && --remaining < 0)
                                                            throw new IOException(
                                                                    "Key response limit");
                                                        return value;
                                                    }

                                                    public int read(
                                                            byte[] bytes, int offset, int length)
                                                            throws IOException {
                                                        int count =
                                                                in.read(
                                                                        bytes,
                                                                        offset,
                                                                        Math.min(
                                                                                length,
                                                                                Math.max(
                                                                                        1,
                                                                                        remaining
                                                                                                + 1)));
                                                        if (count > 0 && (remaining -= count) < 0)
                                                            throw new IOException(
                                                                    "Key response limit");
                                                        return count;
                                                    }
                                                };
                                    return stream;
                                }
                            };
                        }));
        return http;
    }
}
