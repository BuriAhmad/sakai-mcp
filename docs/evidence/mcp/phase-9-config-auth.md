# Phase 9 — MCP configuration and inbound principal (2026-09-27)

Status: **PASS; configuration and inbound principal gate satisfied**.

The project service now has a validated, environment-driven non-secret configuration model and an Entra bearer verifier implementing the pinned MCP Python SDK `TokenVerifier` interface. The verifier accepts only RS256 signatures from the configured HTTPS JWKS, exact issuer/tenant/MCP audience, valid token time claims, delegated `mcp.access` scope, and nonempty human `oid` plus client metadata. It returns a principal based on `tid + oid`; no Sakai institutional ID is inferred from UPN or email. Key retrieval is bounded by a two-second timeout and cached by the library. The MCP server and Sakai client do not yet exist, so these source checks make no Sakai calls.

Local tests use ephemeral RSA keys and synthetic tenant/resource values. Five test functions cover valid delegated identity and denial for no/malformed token, bad signature or algorithm, expired or early token, wrong issuer/tenant/audience/scope, missing human identity, app-only roles, unavailable JWKS, and insecure configuration. `pytest`, Ruff, and mypy passed. A fresh actual Entra delegated MCP token was also verified against tenant JWKS and the observed claims: PASS. No Sakai call occurred in these tests. No credential, token, test-user identity, or live Sakai data appears here.
