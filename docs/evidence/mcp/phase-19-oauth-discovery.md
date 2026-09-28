# Phase 19 — OAuth discovery and protected resource (2026-09-28)

Initial result: **BLOCKED; the resource identity gate failed in the deployed configuration**. Final result after migration: **PASS** (2026-09-28; details below).

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

## Canonical migration and full retest (2026-09-28)

The initial blocked attempt above is preserved as the first event in this report. Work resumed from the user-specified checkpoint `57f56961c5f1714be4751c592b9c64e23772fcb9`, verified as the then-current `main` and `origin/main`. The canonical migration used the existing MCP application and its existing delegated scope; no second MCP identity was created.

### Domain and Azure hostname

- Microsoft Graph initially showed `smartdigest.app` absent from the tenant's domain list. The domain was added to the supported Entra verification flow. Public DNS returned the exact Entra TXT `MS=ms62521210` and Azure ownership TXT for `asuid.mcp.smartdigest.app`, plus the CNAME from `mcp.smartdigest.app` to `ca-mcp-sakai-dev.redsand-d8b00261.koreacentral.azurecontainerapps.io`. Cloudflare was changed by the user; both 1.1.1.1 and 8.8.8.8 independently returned the expected records. `smartdigest.app` is now verified in Entra. Existing root A/AAAA and Google site-verification TXT records remained present. Public CAA lookup was empty, so no CAA change was required.
- Azure's active subscription remained Azure for Students (`55a5701c-411e-45f1-9829-9c80f526d9eb`) and tenant `6831cfbb-6904-4f1a-8dba-0ab09b803a9c`. The existing Container App is `ca-mcp-sakai-dev`, environment `cae-mcp-sakai-dev`, generated backend FQDN `ca-mcp-sakai-dev.redsand-d8b00261.koreacentral.azurecontainerapps.io`, external HTTPS ingress, target port 8000, affinity disabled. No Sakai application or VM change was made.
- Azure validated and SNI-bound `mcp.smartdigest.app` to managed certificate `mc-cae-mcp-sakai--mcp-smartdigest--7680` using CNAME validation. Certificate provisioning is `Succeeded`; an independent TLS handshake verified the certificate chain and SAN `mcp.smartdigest.app`, with validity 2026-09-28 through 2027-03-28. Canonical `/live` and `/ready` both returned HTTP 200 with TLS verification success. The DNS CNAME remains DNS-only and points directly to the generated Container App hostname.

### Entra identity migration

- The existing MCP app registration remains Application ID `2f4af41f-622b-4de8-9ec2-5efb28601b57` (`sakai-mcp-dev-resource`). Its `identifierUris` now include both `https://mcp.smartdigest.app` and the prior `api://2f4af41f-622b-4de8-9ec2-5efb28601b57`. The old identifier was retained as a rollback path; the deployed verifier accepts only the canonical HTTPS audience.
- Delegated scope `mcp.access` remains enabled with scope ID `434508c1-f0a4-41a0-bcd0-0cd16c143542`. The test client's scope permission reference and existing `AllPrincipals` `mcp.access` consent grant remain unchanged. The MCP app's downstream Sakai permission still references Sakai application `fb1fec30-81b2-4f85-9771-b2a2ce3c8f92` and scope ID `77aba539-a35e-4d1b-bd21-5c6130269202`. No audience or OBO boundary was merged.
- A fresh Entra-issued delegated token requested for `https://mcp.smartdigest.app/mcp.access` had audience exactly `https://mcp.smartdigest.app`, scope `mcp.access`, and the expected tenant. OBO produced a distinct Sakai-audience token with `sakai.mcp.access`; inbound and downstream `tid`/`oid` matched.

### Tracked implementation and deployment

- The tracked MCP settings now require `MCP_AUDIENCE` to exactly equal the canonical HTTPS origin and require `MCP_PUBLIC_URL` to be an origin. Protected-resource metadata emits the exact no-trailing-slash resource URI, as recommended for interoperability by the [current versioned MCP authorization specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization). The challenge metadata URL is on the canonical host. The unit/protocol suite verifies the exact metadata representation.
- Bicep now declares the SNI custom-domain binding against the DNS-validated Azure managed certificate. The manual release script sets both canonical public URL and audience, waits until the latest Container App revision is ready before smoke probes, and checks the exact metadata resource. The IaC deployment `mcp-canonical-20260928` succeeded and read back the generated backend FQDN plus revision `ca-mcp-sakai-dev--0000002`.
- Exact MCP source commit `6de2c832eeec020da0b9def762c9c6a6359ddaf0` passed the repository's remote build and image security scan, then deployed successfully in [workflow run 36382843265](https://github.com/BuriAhmad/sakai-mcp/actions/runs/36382843265). A first run exposed a readiness race in its final probe; the tracked script was corrected to wait for latest/ready revision equality, then the exact-commit release passed. Deployed image: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:255d8b2e8f0349824fa953d8e33a8157ef978b8bb3e69bb8fd226c0829c9fc98`. Its scan reported zero critical findings, zero fixable high findings, 44 high findings without a published fix, and zero secrets.

### Repeated Phase 19 gate

| Gate | Evidence | Result |
| --- | --- | --- |
| Unauthenticated `/mcp` challenge | Live external request to `https://mcp.smartdigest.app/mcp`; HTTP 401, Bearer `invalid_token`, canonical `resource_metadata` URL | Pass |
| Protected-resource metadata | Live external GET; `resource` exactly `https://mcp.smartdigest.app`, authorization server is the tenant issuer, scope is `mcp.access`, bearer method is header | Pass |
| Authorization-server metadata | Live GET to advertised issuer's OpenID configuration; HTTP 200 and issuer matches | Pass |
| New canonical MCP token | Fresh Entra token; exact canonical `aud`, `scp=mcp.access`; authenticated MCP initialize HTTP 200 | Pass |
| Wrong audience at MCP | Live Sakai-audience OBO token and a separately issued legacy `api://...` MCP token each received HTTP 401 | Pass |
| Wrong issuer, wrong tenant, missing scope, expired token | Existing locally signed synthetic negative tests exercise each claim independently against the tracked verifier. Entra-issued tokens for these exact claim negatives were not safely or realistically available from this single-tenant issuer; these are not represented as live Entra proof. The updated full local suite passed 40 tests. | Pass (local synthetic only) |
| MCP token at Sakai | Live request to Sakai narrow API returned HTTP 401 | Pass |
| OBO Sakai token at Sakai | Live request returned HTTP 200; token audience/scope were Sakai-specific and `tid`/`oid` matched the inbound human token | Pass |
| Secret/log hygiene | Harness output retained only claim booleans, status codes, issuer metadata, and scopes; no token strings or sensitive Sakai response body were emitted or added to Git/evidence | Pass |

No Phase 20 work was started. Final Phase 19 status: **PASS**.
