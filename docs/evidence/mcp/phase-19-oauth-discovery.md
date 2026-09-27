# Phase 19 — OAuth discovery and protected resource (2026-09-28)

Status: **BLOCKED; the resource identity gate fails in the deployed configuration**.

## State and sources

- Started from clean `main`/`origin/main` at `685a7b67adc5444d16cb636f0d83313599819385`; selected Azure for Students subscription `55a5701c-411e-45f1-9829-9c80f526d9eb` and tenant `6831cfbb-6904-4f1a-8dba-0ab09b803a9c`.
- The live app remained revision `ca-mcp-sakai-dev--cyayjql`, image `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:3847c28104cb1890fd59426bd288e91bb0c9b6032202f2b641ead018e4baa5c3`, source commit `46cd695bc6536930b4e550b7c8b28e6be9383e48`. No deployment or Entra mutation occurred in this phase.
- Rechecked the [current versioned MCP authorization specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), especially Protected Resource Metadata, canonical server URI, resource indicator, audience validation, and 401/403 handling. This is newer than the pinned Python MCP SDK 2.2.0's tested handshake-era protocol. The [Microsoft Entra identifier URI rules](https://learn.microsoft.com/en-us/entra/identity-platform/identifier-uri-restrictions) restrict HTTPS application ID URIs to an initial or verified tenant domain in the secure patterns. The tenant currently has only its initial `onmicrosoft.com` verified domain; the Container Apps host is not a verified tenant domain.

## Live observations

The test used fresh access tokens for one synthetic student, issued through the previously configured public test client, and a fresh certificate-backed OBO token. Tokens and credentials remained only in process memory or the pre-existing ignored local credential files. The one-off harness is ignored under `deployment/artifacts/mcp-obo/`. No bearer value or sensitive LMS response body was printed or copied here.

| Probe | Observed | Gate |
| --- | --- | --- |
| Unauthenticated `/mcp` initialization | HTTP 401, Bearer `invalid_token`, `resource_metadata` points to public HTTPS `/.well-known/oauth-protected-resource` | Pass |
| Malformed bearer at `/mcp` | HTTP 401 with the same discovery challenge | Pass |
| Protected-resource metadata | HTTP 200; `authorization_servers` lists the tenant `https://sts.windows.net/<tenant>/` issuer; `scopes_supported` is `mcp.access`; bearer method is header | Pass for reachability and scope |
| Advertised `resource` | `https://ca-mcp-sakai-dev.redsand-d8b00261.koreacentral.azurecontainerapps.io/` | **Mismatch**: trailing slash and different from Entra MCP application URI `api://2f4af41f-622b-4de8-9ec2-5efb28601b57` |
| Advertised issuer's OpenID configuration | HTTP 200 at issuer-relative `.well-known/openid-configuration`; `issuer` matches advertised issuer; authorization/token endpoints present | Pass |
| Fresh delegated MCP token | Issued `aud` equals registered `api://` MCP URI and `scp=mcp.access`; HTTP 200 MCP `initialize` result | Pass for this issued token |
| Fresh OBO Sakai token at MCP | Issued `aud` equals distinct Sakai `api://` URI and `scp=sakai.mcp.access`; HTTP 401 MCP challenge | Pass |
| MCP token at Sakai narrow API | HTTP 401 | Pass |
| OBO Sakai token at Sakai narrow API | HTTP 200; the human `tid`/`oid` pair matched the inbound token | Pass for token separation; response body omitted |

The live MCP accepts tokens intended for the registered `api://` resource, but its discovery document tells generic clients to use the HTTPS resource URI. The [current specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) requires the client `resource` parameter to identify the canonical MCP server URI and the server to accept tokens issued for that intended resource. A successful direct test-client token request by `api://…/mcp.access` does not prove a discovering client can request the advertised HTTPS resource or obtain an acceptable audience. Changing only the metadata string or the verifier's expected audience would leave Entra issuance and/or canonical URI semantics inconsistent. The existing default Container Apps hostname is outside the tenant's verified domains; a compliant identity/hostname design requires a deliberate Entra and public endpoint decision before mutation.

## Claim-negative coverage and limits

The focused local tests passed **23/23** across inbound auth, OBO, and protocol modules. They use independently signed synthetic tokens to isolate bad signature/algorithm, expiry and not-before, wrong issuer, wrong tenant, wrong audience, missing delegated scope, missing human identity, and app-only role rejection. These are source-level checks of the deployed commit's tracked verifier logic, not live Entra-issued negative tokens. Live rejection was directly observed for no token, malformed token, and a valid Entra Sakai-audience token. Wrong issuer, wrong tenant, missing `mcp.access`, and expired *validly signed* token were not independently produced by the development issuer and are **not claimed as deployed negative proof**. A modified JWT would fail signature verification first and would not isolate its changed claim.

## Resolution gate

Choose and document a public MCP canonical hostname/resource identity that Entra can register and issue as an access-token audience, preserving the distinct Sakai audience and current OBO chain. Then update tracked configuration and Entra registration/grants through the established release path, verify a discovering OAuth client actually requests the advertised resource, and repeat all Phase 19 positive/negative checks with sanitized output. The lack of a verified domain for the present Container Apps hostname is a material architecture/configuration decision; this report does not silently change audience validation or declare the phase passed. Phase 20 and later gates were not started.
