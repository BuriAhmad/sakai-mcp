# Phase 6 — Entra configuration and issued-token evidence (2026-09-26)

Status: **PASS for the development tenant token-shape gate**. This is not client-product acceptance or a deployed service test.

The Azure CLI selected the project's expected subscription and tenant before mutation. Three single-tenant registrations now exist: an MCP resource and confidential OBO middle tier exposing `mcp.access`, a distinct Sakai API resource exposing `sakai.mcp.access`, and a public loopback test client. Delegated grants for test client → MCP and MCP → Sakai API were verified. Four synthetic Entra users were created and their directory-extension values were read back through Graph against the intended synthetic Sakai EIDs. Generated test credentials exist only in an ignored, mode-0600 local environment file. The OBO private key and certificate are in an ignored local artifacts directory; only the public certificate was registered with Entra. Neither is in Git. Production credential placement in Key Vault remains Phase 10 work.

The directory extension is registered on the Sakai API resource as a Graph `String` property named `SakaiEid`. Its Sakai API access-token optional claim requires `source: user`; the initial null source emitted no claim. After that correction, a fresh token issued through the public client and certificate-authenticated OBO exchange had this sanitized shape:

| Check | MCP access token | OBO Sakai API access token |
| --- | --- | --- |
| Signature/issuer source | Entra tenant issuer; cryptographic validation in service pending | Same Entra tenant issuer; cryptographic validation in Sakai pending |
| `aud` | MCP application URI | Different Sakai API application URI |
| `scp` | `mcp.access` | `sakai.mcp.access` |
| `tid` and `oid` | Present | Present and equal to MCP token values |
| `extn.SakaiEid` | Absent | Present as a **single-element JSON array**; its sole string equals the synthetic user's Sakai EID |

The audience and scope pairs are disjoint, so each validator must require its own exact pair. The MCP does not parse a Sakai EID from its incoming token. Only after OBO does the Sakai adapter accept the verified downstream `extn.SakaiEid` singleton array. It must reject a missing, blank, non-string, or multi-value claim and never fall back to UPN/email. The `tid + oid` pair is the external audit identity. The exact claim array representation was observed in an issued token; it was not inferred from Graph's `String` property type.

The same upstream-to-OBO assertions were repeated for all four synthetic identities (two students and two instructors): **4/4 PASS** for distinct audiences, equal tenant/object identity across tokens, and each downstream singleton extension matching that identity's Sakai EID. No values or tokens were retained in evidence.

The token tests used MSAL's public-client password grant solely for synthetic sandbox identities and the official certificate-backed OBO method. Tokens, passwords, private keys, personal identifiers, Sakai IDs, announcement text, and grades were not written to this report or Git. A brief failed test before client propagation returned `AADSTS7000218`; a later fresh test issued the MCP token. The first downstream token after optional-claim setup had no extension; setting `source: user` and requesting a fresh token resolved it.

References: [Microsoft Entra optional claims](https://learn.microsoft.com/en-us/entra/identity-platform/optional-claims), [directory extensions](https://learn.microsoft.com/en-us/entra/identity-platform/schema-extensions), [MSAL Python token acquisition/OBO](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens), [MSAL certificate credentials](https://learn.microsoft.com/en-us/entra/msal/python/advanced/client-credentials), [Azure CLI application certificate](https://learn.microsoft.com/en-us/cli/azure/ad/app/credential).

Remaining phase work: client-product specific authorization behavior and Key Vault/runtime credential distribution are later gates. This phase does not claim that a live Sakai endpoint or MCP service validates these tokens yet.
