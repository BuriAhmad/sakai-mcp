# Phase 10 — OBO provider (2026-09-27)

Status: **PASS for provider behavior; runtime secret distribution remains a later infrastructure gate**.

`services/mcp/src/sakai_mcp/obo.py` uses pinned MSAL Python's certificate-backed confidential-client OBO method. The certificate and private key are read only from explicitly supplied runtime file paths. Requests to Entra have configured connect/read timeouts. There is no distributed cache or administrative credential fallback. The provider re-verifies the inbound MCP token before exchange and independently validates the distinct Sakai API token's RS256 signature, exact issuer/tenant/audience/scope, same human object ID, token times, and one-element institutional ID array. All errors exposed by this provider are sanitized; token endpoint details and tokens are not logged.

Local synthetic tests cover two different users and no cross-identity reuse, wrong upstream audience, absent downstream consent, wrong downstream audience/scope/tenant/user, and missing/malformed institutional ID. The service's 17 local auth/OBO tests, Ruff, and mypy passed. A certificate-backed exchange against the development tenant was run for two different synthetic users: each downstream token retained the matching external object ID and expected synthetic Sakai EID, and the two identities remained distinct (**PASS**). No token, key, credential, user identifier, Sakai content, or grade is retained here.

The private key remains in an ignored mode-0600 local test location. Its eventual runtime location and least-privilege delivery through Azure Key Vault are implementation work for the infrastructure phase, not claimed by this provider result.
